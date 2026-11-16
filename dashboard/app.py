from __future__ import annotations

import html
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from orchestrator.main import Orchestrator, DEFAULT_DB
from dashboard.approval_service import (
    DB_PATH, connect, list_reviews, get_review, record_decision
)

HOST = "127.0.0.1"
PORT = int(os.environ.get("NEXORA_DASHBOARD_PORT", "8000"))


def esc(value):
    return html.escape(str(value if value is not None else ""))


def page(title, content):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} | Nexora</title>
<style>
* {{ box-sizing:border-box; }}
body {{ margin:0; background:#f3f5f9; color:#172033;
       font-family:Segoe UI,Arial,sans-serif; }}
header {{ background:#111c35; color:white; padding:22px 5%; }}
header h1 {{ margin:0; font-size:25px; }}
header p {{ margin:6px 0 0; color:#c7d1e5; }}
main {{ max-width:1180px; margin:28px auto; padding:0 20px; }}
.panel {{ background:white; border:1px solid #e1e6ef; border-radius:12px;
          padding:22px; margin-bottom:20px; }}
h2 {{ margin-top:0; font-size:20px; }}
small,.muted {{ color:#667085; }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ text-align:left; padding:12px 9px; border-bottom:1px solid #edf0f5;
         vertical-align:top; }}
th {{ color:#667085; font-size:12px; text-transform:uppercase; }}
input,textarea {{ width:100%; padding:11px; border:1px solid #ccd3df;
                  border-radius:7px; margin:6px 0 14px; font:inherit; }}
textarea {{ min-height:125px; resize:vertical; }}
button,.button {{ display:inline-block; background:#244b9b; color:white;
                  padding:10px 15px; border:0; border-radius:7px;
                  cursor:pointer; text-decoration:none; font:inherit; }}
button.reject {{ background:#a52c38; }}
button.approve {{ background:#18734b; }}
pre {{ white-space:pre-wrap; overflow-wrap:anywhere; background:#f7f8fb;
       border:1px solid #e7eaf0; padding:16px; border-radius:8px; }}
.pill {{ display:inline-block; padding:4px 9px; border-radius:20px;
         background:#edf1f7; font-size:12px; }}
.pill.approved {{ background:#e1f4e9; color:#17633c; }}
.pill.rejected {{ background:#fde8e8; color:#982b35; }}
.pill.pending {{ background:#fff3d7; color:#815b0b; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr));
         gap:14px; }}
.metric {{ background:#f7f8fb; border-radius:9px; padding:14px; }}
.metric strong {{ display:block; font-size:23px; margin-top:5px; }}
a {{ color:#244b9b; }}
.actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
label {{ font-weight:600; }}
.notice {{ padding:12px; border-radius:8px; background:#fff4dc; margin:12px 0; }}
@media(max-width:700px) {{ table {{ font-size:13px; }} th,td {{ padding:8px 5px; }} }}
</style>
</head>
<body>
<header><h1>NEXORA</h1><p>Agentic Sales Automation · Human Review Console</p></header>
<main>{content}</main>
</body></html>"""


def render_home(message=""):
    reviews = list_reviews()
    total = len(reviews)
    pending = sum(
        1 for r in reviews
        if r["approval"] and r["approval"]["status"] == "pending"
    )
    approved = sum(
        1 for r in reviews
        if r["approval"] and r["approval"]["status"] == "approved"
    )
    rejected = sum(
        1 for r in reviews
        if r["approval"] and r["approval"]["status"] == "rejected"
    )

    rows = []
    for r in reviews:
        approval = r["approval"]
        status = approval["status"] if approval else "not_ready"
        lead = r["outputs"].get("intake", {})
        score = r["outputs"].get("scoring", {}).get("lead_score", "—")
        priority = r["outputs"].get("scoring", {}).get("lead_priority", "—")
        team = r["outputs"].get("routing", {}).get("assigned_team", "—")
        rows.append(f"""
        <tr>
          <td><b>{esc(lead.get('lead_name') or 'Unknown lead')}</b><br>
              <small>{esc(lead.get('company_name') or r.get('lead_company'))}</small></td>
          <td>{esc(score)} / 100<br><small>{esc(priority)}</small></td>
          <td>{esc(team)}</td>
          <td><span class="pill {esc(status)}">{esc(status.replace('_',' '))}</span></td>
          <td><a href="/review/{quote(r['run_id'])}">Open review →</a></td>
        </tr>""")

    table = (
        "<table><thead><tr><th>Lead</th><th>Score</th><th>Assigned team</th>"
        "<th>Approval</th><th>Review</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
        if rows else "<p class='muted'>No workflow runs yet. Submit a lead below to start.</p>"
    )

    content = f"""
    <h2>Sales review dashboard</h2>
    {f"<div class='notice'>{esc(message)}</div>" if message else ""}
    <div class="grid">
      <div class="metric">Workflow runs<strong>{total}</strong></div>
      <div class="metric">Pending review<strong>{pending}</strong></div>
      <div class="metric">Approved<strong>{approved}</strong></div>
      <div class="metric">Rejected<strong>{rejected}</strong></div>
    </div>
    <section class="panel" style="margin-top:20px">
      <h2>Lead pipeline</h2>{table}
    </section>
    <section class="panel">
      <h2>Submit a new lead</h2>
      <p class="muted">Paste lead information. The real Nexora orchestrator will process it.</p>
      <form method="post" action="/submit">
        <label for="raw_text">Lead information</label>
        <textarea id="raw_text" name="raw_text" required
          placeholder="My name is Rahul Sharma. I am Operations Director at ABC Manufacturing Pvt Ltd. My email is rahul@example.com. Industry: Manufacturing. We have 450 employees. We need to automate finance workflows."></textarea>
        <button type="submit">Process lead</button>
      </form>
    </section>
    <p class="muted">Local dashboard · Database: {esc(DB_PATH.name)} · No email is sent by this dashboard.</p>
    """
    return page("Dashboard", content)


def render_review(run_id, message=""):
    r = get_review(run_id)
    if not r:
        return page("Not found", "<section class='panel'>Workflow run not found. <a href='/'>Back</a></section>"), 404

    outputs = r["outputs"]
    lead = outputs.get("intake", {})
    scoring = outputs.get("scoring", {})
    routing = outputs.get("routing", {})
    communication = outputs.get("communication", {})
    qa = outputs.get("qa", {})
    approval = r["approval"]
    status = approval["status"] if approval else "not_ready"

    checks = qa.get("checks", [])
    if isinstance(checks, dict):
        checks_text = json.dumps(checks, indent=2)
    else:
        checks_text = json.dumps(checks, indent=2)

    stage_sections = []
    stage_order = [
        "intake", "research", "qualification", "scoring",
        "routing", "strategy", "communication", "qa"
    ]

    for stage in stage_order:
        output = outputs.get(stage)
        if output is not None:
            stage_sections.append(
                f"<h3>{esc(stage.replace('_', ' ').title())}</h3>"
                f"<pre>{esc(json.dumps(output, indent=2, ensure_ascii=False))}</pre>"
            )

    stage_details_html = (
        '<section class="panel"><h2>Complete workflow stage details</h2>'
        + "".join(stage_sections)
        + '</section>'
    )

    body = f"""
    <p><a href="/">← Back to dashboard</a></p>
    <h2>Lead review</h2>
    {f"<div class='notice'>{esc(message)}</div>" if message else ""}
    <section class="panel">
      <div class="grid">
        <div class="metric">Lead<strong>{esc(lead.get('lead_name'))}</strong></div>
        <div class="metric">Company<strong>{esc(lead.get('company_name'))}</strong></div>
        <div class="metric">Lead score<strong>{esc(scoring.get('lead_score','—'))}/100</strong></div>
        <div class="metric">Priority<strong>{esc(scoring.get('lead_priority','—'))}</strong></div>
      </div>
      <p><b>Email:</b> {esc(lead.get('email'))}</p>
      <p><b>Industry:</b> {esc(lead.get('industry'))}</p>
      <p><b>Employees:</b> {esc(lead.get('employee_count'))}</p>
      <p><b>Assigned team:</b> {esc(routing.get('assigned_team'))}</p>
      <p><b>Assigned role:</b> {esc(routing.get('assigned_role'))}</p>
      <p><b>Run ID:</b> <small>{esc(run_id)}</small></p>
    </section>
    <section class="panel">
      <h2>Generated email draft</h2>
      <p><b>To:</b> {esc(communication.get('recipient'))}</p>
      <p><b>Subject:</b> {esc(communication.get('subject'))}</p>
      <pre>{esc(communication.get('email_body') or 'No email draft available.')}</pre>
      <h3>Follow-up message</h3>
      <pre>{esc(communication.get('follow_up_message') or 'No follow-up message.')}</pre>
    </section>
    <section class="panel">
      <h2>Quality assurance</h2>
      <p><b>QA status:</b> {esc(qa.get('qa_status','Not available'))}</p>
      <p><b>Passed checks:</b> {esc(qa.get('passed_checks','—'))}
         &nbsp; <b>Failed checks:</b> {esc(qa.get('failed_checks','—'))}</p>
      <pre>{esc(checks_text)}</pre>
    </section>
    {stage_details_html}
    <section class="panel">
      <h2>Human decision</h2>
      <p>Current status: <span class="pill {esc(status)}">{esc(status.replace('_',' '))}</span></p>
      """
    if r["eligible_for_approval"] and status == "pending":
        body += f"""
        <form method="post" action="/decision">
          <input type="hidden" name="run_id" value="{esc(run_id)}">
          <label>Reviewer name</label>
          <input name="reviewer" required maxlength="100" placeholder="Your name">
          <label>Comments / rejection reason</label>
          <textarea name="comments" placeholder="Add review notes. A reason is required when rejecting."></textarea>
          <div class="actions">
            <button class="approve" name="decision" value="approved">Approve draft</button>
            <button class="reject" name="decision" value="rejected">Reject draft</button>
          </div>
        </form>
        <p class="muted">Approval records a human decision only. It does not send the email.</p>
        """
    elif approval:
        body += f"""
        <p><b>Reviewer:</b> {esc(approval.get('reviewer'))}</p>
        <p><b>Decision time:</b> {esc(approval.get('decided_at'))}</p>
        <p><b>Comments:</b> {esc(approval.get('comments'))}</p>
        <p class="muted">This decision is recorded and cannot be overwritten from this screen.</p>
        """
    else:
        body += "<div class='notice'>This workflow is not eligible for approval. Check that it completed and passed QA.</div>"
    body += "</section>"
    return page("Lead review", body), 200


class DashboardHandler(BaseHTTPRequestHandler):
    def _send(self, content, status=200):
        data = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def _form(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length > 120000:
            raise ValueError("Form submission is too large.")
        raw = self.rfile.read(length).decode("utf-8")
        return {k: v[0] for k, v in parse_qs(raw).items()}

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(render_home())
        elif parsed.path.startswith("/review/"):
            run_id = parsed.path[len("/review/"):]
            content, status = render_review(run_id)
            self._send(content, status)
        else:
            self._send(page("Not found", "<p>Page not found. <a href='/'>Home</a></p>"), 404)

    def do_POST(self):
        try:
            form = self._form()
            if self.path == "/submit":
                raw_text = form.get("raw_text", "").strip()
                if not raw_text:
                    raise ValueError("Lead information is required.")
                orchestrator = Orchestrator(db_path=DB_PATH)
                try:
                    summary = orchestrator.process_lead({"raw_text": raw_text})
                finally:
                    orchestrator.close()
                self._redirect("/?message=" + quote(
                    f"Lead processed. Workflow status: {summary.get('status')}."
                ))
                return

            if self.path == "/decision":
                run_id = form.get("run_id", "")
                record_decision(
                    run_id=run_id,
                    decision=form.get("decision", ""),
                    reviewer=form.get("reviewer", ""),
                    comments=form.get("comments", ""),
                )
                self._redirect("/review/" + quote(run_id) + "?message=Decision%20recorded")
                return

            self._send(page("Not found", "<p>Unknown action.</p>"), 404)
        except Exception as exc:
            self._send(page("Action failed",
                f"<section class='panel'><h2>Action failed</h2><p>{esc(exc)}</p><a href='/'>Back</a></section>"), 400)

    def log_message(self, fmt, *args):
        print("[dashboard]", fmt % args)


def main():
    # Initialize the workflow and approval tables before serving requests.
    conn = connect(DB_PATH)
    conn.close()
    print(f"Nexora dashboard: http://{HOST}:{PORT}")
    print(f"Database: {DB_PATH}")
    server = ThreadingHTTPServer((HOST, PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
