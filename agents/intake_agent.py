"""Intake Agent â€” Nexora Technologies Agentic Sales System (Step 1).

Takes a raw inbound lead (email / form text) and returns structured JSON.

Rules enforced (see prompts/agent_instructions.md):
  * Never invent missing information -> unavailable fields are null.
  * Distinguish facts from assumptions -> every note is tagged FACT / ASSUMPTION / FLAG.
  * Never marks a lead as qualified, never sends email, never writes to the CRM.
    The only CRM access is a READ-ONLY lookup function.

This implementation is deterministic (regex / rule based) so it runs offline with no
API key. The public contract (`run_intake`) is the same one an LLM-backed version
would use, so it can be swapped in later without touching the orchestrator.

Usage:
    python agents/intake_agent.py test_cases/normal_lead.json
    python agents/intake_agent.py --all
"""

from __future__ import annotations

import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
CRM_FILE = ROOT / "database" / "mock_crm.json"
LOG_FILE = ROOT / "logs" / "intake_agent.log.jsonl"

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
    "aol.com", "proton.me", "protonmail.com", "live.com", "rediffmail.com",
}
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "guerrillamail.com", "10minutemail.com", "yopmail.com",
}
PLACEHOLDER_DOMAINS = {"example.com", "test.com", "domain.com"}
SPAM_PHRASES = ("click here", "you have won", "winner", "crypto", "guaranteed returns", "act now")

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
STRICT_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")

INDUSTRY_KEYWORDS = {
    "logistics": ["logistics", "freight", "supply chain", "shipping", "warehouse"],
    "healthcare": ["healthcare", "hospital", "clinic", "pharma", "medical"],
    "retail": ["retail", "e-commerce", "ecommerce", "stores"],
    "manufacturing": ["manufacturing", "factory", "factories", "production plant"],
    "financial services": ["finance", "banking", "bank", "insurance", "fintech", "capital"],
    "education": ["university", "school", "edtech", "education"],
    "real estate": ["real estate", "property developer", "realty"],
    "telecom": ["telecom", "telecommunications"],
    "information technology": ["software", "it services", "saas"],
}

REQ_VERBS = re.compile(
    r"(?i)\b(need|needs|looking for|looking to|want|wants|require|requires|automate|"
    r"interested in|seeking|help with|struggling with|would like to (?!go live))\b"
)

CURRENCY = r"(?:USD|US\$|\$|â‚¹|INR|Rs\.?|â‚¬|EUR|Â£|GBP)"
AMOUNT = r"\d[\d,]*(?:\.\d+)?\s?(?:k|K|m|M|lakhs?|crores?)?"
BUDGET_CONTEXT = re.compile(r"(?i)\b(budget|allocat\w*|spend|invest\w*|afford|approved|funding)\b")


# --------------------------------------------------------------------------- #
# Read-only CRM lookup tool
# --------------------------------------------------------------------------- #
def crm_lookup(email: Optional[str], company: Optional[str], name: Optional[str]) -> list[dict]:
    """READ-ONLY lookup against the mock CRM. Never creates or modifies records."""
    records = json.loads(CRM_FILE.read_text(encoding="utf-8"))["records"]
    matches = []
    for rec in records:
        if email and rec["email"].lower() == email.lower():
            matches.append({**rec, "match_type": "email_exact"})
        elif company and _norm(rec["company"]) == _norm(company):
            sim = difflib.SequenceMatcher(None, _norm(rec["name"]), _norm(name or "")).ratio()
            matches.append({**rec, "match_type": "company_and_name" if sim >= 0.8 else "company_only"})
    return matches


def _norm(s: str) -> str:
    s = re.sub(r"(?i)\b(pvt|ltd|llc|inc|limited|services|technologies|corp)\b\.?", "", s or "")
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


# --------------------------------------------------------------------------- #
# Field extractors
# --------------------------------------------------------------------------- #
def _strip_headers(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if not re.match(r"(?i)^\s*(from|to|cc|subject|date)\s*:", l))


def _extract_email(text: str, notes: list[str], flags: list[str]) -> Optional[str]:
    found = []
    for e in EMAIL_RE.findall(text):
        e = e.rstrip(".").lower()
        if e not in found:
            found.append(e)
    if not found:
        return None

    sender = None
    m = re.search(r"(?im)^\s*from\s*:.*?(" + EMAIL_RE.pattern + ")", text)
    if m:
        sender = m.group(1).rstrip(".").lower()

    chosen = sender or (found[0] if len(found) == 1 else None)
    if len(found) > 1:
        flags.append(f"Multiple different email addresses found: {', '.join(found)}.")
        if chosen:
            notes.append(f"FACT: Sender address from the 'From' header was used: {chosen}.")
        else:
            flags.append("Could not determine which email is the prospect's; email set to null.")
    if not chosen:
        return None

    if not STRICT_EMAIL_RE.match(chosen):
        flags.append(f"Email '{chosen}' is malformed.")
        return None
    domain = chosen.split("@")[1]
    if domain in FREE_EMAIL_DOMAINS:
        flags.append(f"'{chosen}' is a free/personal email domain, not a business email.")
    if domain in DISPOSABLE_DOMAINS:
        flags.append(f"'{chosen}' uses a disposable email domain.")
    if domain in PLACEHOLDER_DOMAINS or chosen.startswith(("test@", "fake@", "asdf@")):
        flags.append(f"'{chosen}' looks like a placeholder/test address.")
    return chosen


def _extract_name(text: str, notes: list[str]) -> Optional[str]:
    cap = r"[A-Z][a-z'\-]+"
    candidates = []
    m = re.search(r"(?i:my name is|this is|i am|i'm)\s+(" + cap + r"(?:\s+" + cap + r"){1,2})\b", text)
    if m:
        candidates.append(m.group(1))
    m = re.search(r"(?im)^\s*name\s*:\s*(" + cap + r"(?:\s+" + cap + r"){1,2})\s*$", text)
    if m:
        candidates.append(m.group(1))
    m = re.search(r"(?im)^\s*from\s*:\s*\"?(" + cap + r"(?:\s+" + cap + r"){1,2})\"?\s*<", text)
    if m:
        candidates.append(m.group(1))
    m = re.search(r"(?im)(?:regards|best|thanks|thank you|sincerely|cheers)[,!]?\s*\n\s*[-â€“â€”]?\s*(" + cap + r"(?:\s+" + cap + r"){0,2})\s*$", text)
    if m:
        candidates.append(m.group(1))
    m = re.search(r"(?m)^\s*[-â€“â€”]\s*(" + cap + r"(?:\s+" + cap + r"){0,2})\s*$", text)
    if m:
        candidates.append(m.group(1))

    full = [c for c in candidates if len(c.split()) >= 2]
    if full:
        return full[0]
    if candidates:
        notes.append(f"FACT: Only a partial name ('{candidates[0]}') was provided; full name unavailable.")
    return None


def _extract_company(text: str) -> Optional[str]:
    tok = r"[A-Z][\w&'\-]*"
    name = tok + r"(?:\s+(?:" + tok + r"|&))*"
    patterns = [
        r"(?im)^\s*company\s*:\s*(" + name + r")\s*$",
        r"\b(?:CEO|Founder|Co-founder|Owner|President)\s+of\s+(" + name + r")",
        r"\b(?:COO|CEO|CTO|CFO|CIO|CMO|VP|Director|Manager|Head|Founder|Owner|President|Lead|Officer)\b[^.\n]{0,40}\b(?:at|for)\s+(" + name + r")",
        r"(?i:\bwork(?:ing)?\s+(?:at|for|with))\s+(" + name + r")",
        r"(?i:\brepresenting)\s+(" + name + r")",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None


def _extract_industry(text: str, notes: list[str]) -> Optional[str]:
    m = re.search(r"(?i)\bindustry\s*:\s*([^\n.;]+)", text)
    if m:
        return m.group(1).strip().lower()
    m = re.search(r"(?i)\b(?:we are|we're|i work in|operate in)\s+(?:a|an|in the)?\s*([a-z][a-z &/\-]{2,30}?)\s+(?:company|firm|business|provider|startup|organization|sector|industry)\b", text)
    if m:
        stated = m.group(1).strip().lower()
        for label, kws in INDUSTRY_KEYWORDS.items():
            if any(k in stated for k in kws):
                return label
        return stated
    low = text.lower()
    for label, kws in INDUSTRY_KEYWORDS.items():
        hit = next((k for k in kws if k in low), None)
        if hit:
            notes.append(f"ASSUMPTION: Industry '{label}' inferred from the word '{hit}'; not explicitly stated.")
            return label
    return None


def _to_int(s: str) -> int:
    return int(s.replace(",", ""))


def _extract_employees(text: str, flags: list[str]) -> Optional[int]:
    vals = []
    pats = [
        r"(?i)\b(\d[\d,]*)\+?\s*(?:employees|staff members|staff|team members|people)\b",
        r"(?i)\b(?:team|workforce|headcount|company)\s+of\s+(?:about|around|approximately|roughly)?\s*(\d[\d,]*)",
        r"(?i)\b(\d[\d,]*)[- ]person\b",
    ]
    for p in pats:
        for m in re.finditer(p, text):
            v = _to_int(m.group(1))
            if v not in vals:
                vals.append(v)
    if len(vals) > 1:
        flags.append(f"Conflicting employee counts stated: {', '.join(f'{v:,}' for v in vals)}; employee_count set to null.")
        return None
    return vals[0] if vals else None


def _extract_budget(text: str, notes: list[str], flags: list[str]) -> Optional[str]:
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        if not BUDGET_CONTEXT.search(sentence):
            continue
        for m in re.finditer(r"(" + CURRENCY + r"\s?" + AMOUNT + r"(?:\s?(?:-|â€“|to)\s?" + CURRENCY + r"?\s?" + AMOUNT + r")?)", sentence):
            val = m.group(1).strip()
            if val not in found:
                found.append(val)
        for m in re.finditer(r"(?i)(\d[\d,]*(?:\.\d+)?\s?(?:k|m)?)\s?(USD|INR|dollars|rupees|euros)\b", sentence):
            val = m.group(0).strip()
            if val not in found:
                found.append(val)
    if len(found) > 1:
        flags.append(f"Conflicting budget figures stated: {', '.join(found)}; budget set to null.")
        return None
    if found:
        notes.append(f"FACT: Budget stated by the prospect as '{found[0]}' (as written, not normalised).")
    return found[0] if found else None


def _extract_urgency(text: str, flags: list[str]) -> Optional[str]:
    # Respect an explicitly labelled urgency field.
    explicit = re.findall(
        r"(?i)(?:^|[\n.;])\s*urgency\s*:\s*(high|medium|low)\b",
        text
    )
    if len(set(x.lower() for x in explicit)) > 1:
        flags.append("Conflicting explicitly stated urgency levels; urgency set to null.")
        return None
    if explicit:
        return explicit[0].lower()
    months = "January|February|March|April|May|June|July|August|September|October|November|December"
    high = [
        r"(?i)\b(urgent(?:ly)?|asap|immediately|right away|as soon as possible)\b",
        r"(?i)\b(within (?:the next )?\d+\s+(?:days?|weeks?|months?))\b",
        r"(?i)\b(by (?:the end of )?(?:Q[1-4]|" + months + r"|next (?:week|month|quarter))(?:\s+\d{4})?)\b",
        r"(?i)\b(next (?:week|month|quarter))\b",
    ]
    low = [r"(?i)\b(no (?:rush|hurry)|just exploring|exploring options|just looking|just researching)\b"]
    hi_hits, lo_hits = [], []
    for p in high:
        for m in re.finditer(p, text):
            if m.group(1).lower() not in [h.lower() for h in hi_hits]:
                hi_hits.append(m.group(1))
    for p in low:
        for m in re.finditer(p, text):
            lo_hits.append(m.group(1))
    # drop hits fully contained in a longer hit (e.g. "next quarter" inside "by next quarter")
    hi_hits = [h for h in hi_hits if not any(h != o and h.lower() in o.lower() for o in hi_hits)]
    if hi_hits and lo_hits:
        flags.append(f"Conflicting urgency signals: '{hi_hits[0]}' vs '{lo_hits[0]}'; urgency set to null.")
        return None
    if hi_hits:
        return "; ".join(hi_hits)
    if lo_hits:
        return lo_hits[0]
    return None


def _extract_requirements(text: str) -> list[str]:
    body = _strip_headers(text)
    reqs = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", body):
        s = s.strip().strip("-â€“â€” ")
        s = re.sub(r"(?i)^(hi|hello|hey|dear [^,]+)( there| team| nexora team)?[,!]?\s+", "", s)
        # "we need it ASAP" / "we need this by Q3" is timing, not a requirement
        probe = re.sub(r"(?i)\bneeds?\s+(?:it|this|that)\b", "", s)
        if len(s) > 12 and REQ_VERBS.search(probe) and s not in reqs:
            reqs.append(s)
    return reqs[:6]


def _suspicious_checks(text: str, name: Optional[str], flags: list[str]) -> None:
    low = text.lower()
    for ph in SPAM_PHRASES:
        if ph in low:
            flags.append(f"Spam-like phrase detected: '{ph}'.")
    if len(re.findall(r"https?://", low)) > 3:
        flags.append("Unusually many URLs in the message.")
    if name and re.fullmatch(r"(?i)(test|asdf|xxx|foo bar|john doe)(\s+\w+)?", name):
        flags.append(f"Name '{name}' looks like a placeholder.")


def _domain_company_check(email: Optional[str], company: Optional[str], notes: list[str]) -> None:
    if not email or not company:
        return
    domain = email.split("@")[1]
    if domain in FREE_EMAIL_DOMAINS:
        return
    label = re.sub(r"[^a-z0-9]", "", domain.split(".")[0])
    tokens = [t for t in re.findall(r"[a-z0-9]+", company.lower()) if len(t) > 3]
    if tokens and not any(t in label or label in t for t in tokens) and label not in "".join(tokens):
        notes.append(f"FLAG: Email domain '{domain}' does not obviously match company '{company}'. Not verified.")


# --------------------------------------------------------------------------- #
# Duplicate detection
# --------------------------------------------------------------------------- #
def _duplicate_status(email, company, name, notes, lookup: Callable) -> str:
    if not email and not company:
        notes.append("FACT: Duplicate check skipped: neither email nor company available.")
        return "unknown"
    try:
        matches = lookup(email, company, name)
    except Exception as exc:  # lookup tool failure must not crash intake
        notes.append(f"FLAG: CRM lookup failed ({type(exc).__name__}: {exc}); duplicate status unknown.")
        return "unknown"
    if not matches:
        notes.append("FACT: No matching record found in CRM lookup.")
        return "not_duplicate"
    for m in matches:
        notes.append(f"FACT: CRM match {m['crm_id']} ({m['name']}, {m['company']}) via {m['match_type']}.")
    if any(m["match_type"] == "email_exact" for m in matches):
        return "duplicate"
    return "possible_duplicate"


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def run_intake(lead_input: dict, lookup: Callable = crm_lookup) -> dict:
    """Process one inbound lead and return the structured intake result."""
    text = (lead_input or {}).get("raw_text") or ""
    notes: list[str] = []
    flags: list[str] = []

    if not text.strip():
        return {
            "lead_name": None, "company_name": None, "email": None, "industry": None,
            "employee_count": None, "requirements": [], "budget": None, "urgency": None,
            "missing_fields": ["lead_name", "company_name", "email", "industry", "employee_count",
                               "requirements", "budget", "urgency"],
            "duplicate_status": "unknown", "validation_status": "invalid",
            "notes": ["FLAG: Empty inquiry; nothing to extract."],
        }

    email = _extract_email(text, notes, flags)
    name = _extract_name(text, notes)
    company = _extract_company(text)
    industry = _extract_industry(text, notes)
    employees = _extract_employees(text, flags)
    requirements = _extract_requirements(text)
    budget = _extract_budget(text, notes, flags)
    urgency = _extract_urgency(text, flags)

    _suspicious_checks(text, name, flags)
    _domain_company_check(email, company, notes)

    result = {
        "lead_name": name,
        "company_name": company,
        "email": email,
        "industry": industry,
        "employee_count": employees,
        "requirements": requirements,
        "budget": budget,
        "urgency": urgency,
    }
    missing = [k for k in ("lead_name", "company_name", "email", "industry", "employee_count",
                           "requirements", "budget", "urgency") if not result[k]]
    result["missing_fields"] = missing
    result["duplicate_status"] = _duplicate_status(email, company, name, notes, lookup)

    core_missing = [m for m in ("lead_name", "company_name", "requirements") if m in missing]
    if not email:
        status = "invalid"
        notes.append("FLAG: No usable email address; the lead cannot be contacted or deduplicated reliably.")
    elif flags or any(n.startswith("FLAG") for n in notes):
        status = "needs_review"
    elif core_missing:
        status = "incomplete"
    else:
        status = "valid"
    result["validation_status"] = status
    result["notes"] = [f"FLAG: {f}" for f in flags] + notes
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _log(case_id: str, output: dict) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "agent": "intake_agent",
             "case_id": case_id, "output": output}
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    paths = sorted((ROOT / "test_cases").glob("*.json")) if argv[0] == "--all" else [Path(a) for a in argv]
    for p in paths:
        case = json.loads(p.read_text(encoding="utf-8"))
        out = run_intake(case["input"])
        _log(case.get("case_id", p.stem), out)
        print(f"=== {p.name} ===")
        print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
