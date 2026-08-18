"""Diagnostic Clank v0.1 -- Archivist. Local loopback GUI.

Read-only investigator + evidence/incident archive. No autonomous
diagnosis, no remediation, no production authority of any kind -- see
clank_runtime.knowledge.incidents module docstring for the laws this
upholds. This module is the presentation layer only; all storage/history
rules live in clank_runtime.knowledge.store.DiagnosticKnowledgeStore.
"""
from __future__ import annotations

import html
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from clank_runtime.knowledge.attachments import AttachmentQuarantined
from clank_runtime.knowledge.clankops_record import extract_clankops_record
from clank_runtime.knowledge.inbox import AgentFamily, OutputType
from clank_runtime.knowledge.incidents import ClaimVerification, IncidentClassification, IncidentStatus, RootCauseCertainty
from clank_runtime.knowledge.store import DiagnosticKnowledgeStore
from clank_runtime.registry.core import ClankRegistration, ClankRegistry
from diagnostic_clank.paths import StatePaths

# Known fleet Clank ids, seeded as registry identity metadata only -- this
# has zero side effects on any other Clank's actual state. An owner can
# still type/select "fleet-wide" or any registered id; the registry is
# data, not a closed source enum (see ClankRegistry docstring).
KNOWN_CLANK_IDS = (
    "watch-clank", "smartphone-clank", "smartwatch-clank", "feature-phone-clank",
    "tablet-clank", "chinese-tech-wire", "korean-tech-wire", "semiconductor-intelligence",
    "oem-radar", "free-game-tracker",
)


def build_registry() -> ClankRegistry:
    reg = ClankRegistry()
    for cid in KNOWN_CLANK_IDS:
        reg.register(ClankRegistration(clank_id=cid, display_name=cid.replace("-", " ").title()))
    return reg


def e(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _style() -> str:
    return """<style>
:root{--bg:#0a0f1a;--card:#111a2b;--line:#233047;--text:#e8edf7;--muted:#8fa0bd;--blue:#6fb3ff;--green:#6fdc9a;--amber:#f2c14e;--red:#ff8080;--purple:#b79bff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.app{min-height:100vh;display:grid;grid-template-columns:190px 1fr;grid-template-rows:60px 1fr}
header{grid-column:1/3;display:flex;align-items:center;gap:12px;padding:0 18px;background:#0d1422;border-bottom:1px solid var(--line)}
.brand{font-weight:800;font-size:16px}.brand small{display:block;color:var(--muted);font-weight:400;font-size:10px}
.badge{display:inline-block;background:#2a1f4d;color:var(--purple);border:1px solid #4a3a80;border-radius:5px;padding:3px 8px;font-size:10px;font-weight:800;letter-spacing:.05em}
.spacer{flex:1}
aside{background:#0d1422;border-right:1px solid var(--line);padding:12px}
.nav{display:block;color:#c8d3e8;padding:9px 12px;border-radius:6px;margin:2px 0;font-weight:600}
.nav.active{background:#233047;color:#fff}
.nav-cta{display:block;text-align:center;background:#3a5ad9;color:#fff!important;border-radius:6px;padding:10px;margin:6px 0;font-weight:800}
.nav-cta.alt{background:#2a2a5a}
main{padding:20px;max-width:1100px;width:100%;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:18px 0 8px}
.muted{color:var(--muted)}
.grid4{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}
.stat{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.stat b{display:block;font-size:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;color:var(--muted);font-size:10px;letter-spacing:.05em;padding:6px;border-bottom:1px solid var(--line)}
td{padding:8px 6px;border-bottom:1px solid #1a2438;vertical-align:top}
tr:hover td{background:#141f33}
.pill{display:inline-block;border-radius:5px;padding:2px 7px;font-size:10px;font-weight:800}
.pill.OPEN{background:#3a2f10;color:var(--amber)}.pill.RESOLVED{background:#123a26;color:var(--green)}
.pill.PARTIAL{background:#1a2f4a;color:var(--blue)}.pill.DISPUTED,.pill.CONTRADICTED{background:#3a1616;color:var(--red)}
.pill.SUPERSEDED{background:#241a3a;color:var(--purple)}.pill.REPORTED{background:#232323;color:#ccc}
.pill.CORROBORATED,.pill.VERIFIED{background:#123a26;color:var(--green)}
form label{display:block;margin:10px 0 4px;font-weight:700;font-size:11.5px;color:#c8d3e8}
input[type=text],select,textarea{width:100%;background:#0d1422;border:1px solid var(--line);color:var(--text);border-radius:5px;padding:8px;font:inherit}
textarea{resize:vertical}
button{background:#3a5ad9;color:#fff;border:0;border-radius:6px;padding:9px 16px;font-weight:800;cursor:pointer;font-size:12.5px}
button.secondary{background:#233047}
.empty{padding:30px;text-align:center;color:var(--muted)}
.kv{display:grid;grid-template-columns:160px 1fr;gap:6px;margin:4px 0}
.kv b{color:var(--muted);font-weight:600}
.rawbox{white-space:pre-wrap;background:#0d1422;border:1px solid var(--line);border-radius:6px;padding:12px;max-height:500px;overflow:auto;font-family:ui-monospace,monospace;font-size:11.5px}
.footer{text-align:center;color:var(--muted);padding:20px;font-size:11px}
</style>"""


def _nav(active: str) -> str:
    items = [("overview", "/", "Overview"), ("incidents", "/incidents", "Incidents"),
             ("reports", "/reports", "Agent Reports"), ("file-inbox", "/file-inbox", "File Inbox"), ("evidence", "/evidence", "Raw Evidence"),
             ("search", "/search", "Search")]
    links = "".join(f'<a class="nav{" active" if k == active else ""}" href="{href}">{label}</a>' for k, href, label in items)
    return (f'{links}<div style="height:1px;background:#233047;margin:10px 0"></div>'
            f'<a class="nav-cta" href="/incidents/new">+ ADD L</a>'
            f'<a class="nav-cta alt" href="/reports/new">IMPORT REPORT</a>')


def _shell(active: str, title: str, body: str) -> str:
    return f'''<!doctype html><html><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{e(title)} · Diagnostic Clank</title>{_style()}</head><body><div class=app>
<header><div class=brand>Diagnostic Clank<small>Local Archivist</small></div>
<span class=badge>DIAGNOSTIC CLANK v0.1 · LOCAL ARCHIVIST / FIELD TEST</span><span class=spacer></span></header>
<aside>{_nav(active)}</aside><main>{body}</main></div></body></html>'''


def status_pill(value: str) -> str:
    return f'<span class="pill {e(value)}">{e(value)}</span>'


# ---------------------------------------------------------------------------
# page renderers
# ---------------------------------------------------------------------------

def render_overview(store: DiagnosticKnowledgeStore) -> str:
    incidents = store.incidents.list(limit=5)
    reports = store.inbox.list(limit=5)
    all_incidents = store.incidents.list(limit=10000)
    open_count = sum(1 for i in all_incidents if i.status == IncidentStatus.OPEN)
    body = f'''<h1>Overview</h1><p class=muted>Local knowledge history archive. Nothing here has authority to change any Clank.</p>
<div class=grid4>
<div class=stat><div class=muted>Incidents</div><b>{len(all_incidents)}</b></div>
<div class=stat><div class=muted>Open</div><b>{open_count}</b></div>
<div class=stat><div class=muted>Agent reports</div><b>{len(store.inbox.list(limit=100000))}</b></div>
<div class=stat><div class=muted>Attachments</div><b>{store.attachments._con.execute("SELECT COUNT(*) c FROM attachments").fetchone()["c"]}</b></div>
</div>
<h2>Recent incidents</h2>{_incident_table(incidents)}
<h2>Recent agent reports</h2>{_report_table(reports)}'''
    return _shell("overview", "Overview", body)


def _incident_table(incidents) -> str:
    if not incidents:
        return '<div class=card><div class=empty>No incidents yet.<br>Click <b>+ ADD L</b> to record the first one.</div></div>'
    rows = "".join(
        f'<tr><td><a href="/incidents/{e(i.incident_id)}">{e(i.title)}</a></td>'
        f'<td>{e(i.clank_id)}</td><td>{status_pill(i.status.value)}</td>'
        f'<td>{", ".join(e(c.value) for c in i.classification) or "—"}</td>'
        f'<td>{e(i.updated_at.strftime("%Y-%m-%d %H:%M"))}</td></tr>'
        for i in incidents
    )
    return f'<div class=card><table><thead><tr><th>Title</th><th>Clank</th><th>Status</th><th>Classification</th><th>Updated</th></tr></thead><tbody>{rows}</tbody></table></div>'


def _report_table(reports) -> str:
    if not reports:
        return '<div class=card><div class=empty>No agent reports yet.<br>Click <b>IMPORT REPORT</b> to paste the first one.</div></div>'
    rows = "".join(
        f'<tr><td><a href="/reports/{e(r.output_id)}">{e(r.output_id[:8])}</a></td>'
        f'<td>{e(r.agent_family.value)}</td><td>{e(r.primary_clank_id)}</td>'
        f'<td>{e(r.output_type.value)}</td><td>{e(r.created_at.strftime("%Y-%m-%d %H:%M"))}</td></tr>'
        for r in reports
    )
    return f'<div class=card><table><thead><tr><th>ID</th><th>Agent</th><th>Clank</th><th>Type</th><th>Ingested</th></tr></thead><tbody>{rows}</tbody></table></div>'


def render_incidents_list(store: DiagnosticKnowledgeStore, clank_filter: str, status_filter: str) -> str:
    incidents = store.incidents.list(clank_id=clank_filter or None, status=status_filter or None, limit=500)
    opts_status = "".join(f'<option value="{s.value}" {"selected" if status_filter==s.value else ""}>{s.value}</option>' for s in IncidentStatus)
    body = f'''<h1>Incidents</h1>
<form method=get class=card style="display:flex;gap:10px;align-items:end">
<div><label>Clank</label><input type=text name=clank value="{e(clank_filter)}" placeholder="e.g. smartwatch-clank"></div>
<div><label>Status</label><select name=status><option value="">All</option>{opts_status}</select></div>
<div><button>Filter</button></div><div><a href="/incidents">Clear</a></div>
</form>{_incident_table(incidents)}'''
    return _shell("incidents", "Incidents", body)


def render_incident_new_form(registry: ClankRegistry) -> str:
    clank_opts = "".join(f'<option value="{e(c)}">{e(c)}</option>' for c in registry.list_ids()) + '<option value="fleet-wide">fleet-wide</option>'
    class_opts = "".join(f'<option value="{c.value}">{c.value}</option>' for c in IncidentClassification)
    status_opts = "".join(f'<option value="{s.value}">{s.value}</option>' for s in IncidentStatus)
    body = f'''<h1>+ Add L</h1><p class=muted>Fast field-test logging. Nothing is required except Clank and title.</p>
<form method=post action="/incidents" class=card>
<label>Clank / project *</label><select name=clank_id required>{clank_opts}</select>
<label>Title *</label><input type=text name=title required placeholder="What happened, in one line">
<label>What happened</label><textarea name=narrative rows=3></textarea>
<label>Expected behaviour</label><textarea name=expected_behaviour rows=2></textarea>
<label>Observed behaviour</label><textarea name=observed_behaviour rows=2></textarea>
<label>Classification (multi-select, optional)</label><select name=classification multiple size=6>{class_opts}</select>
<label>Severity</label><input type=text name=severity placeholder="e.g. P1, minor, unknown">
<label>Status</label><select name=status>{status_opts}</select>
<label>Reported by</label><input type=text name=reported_by placeholder="owner / claude / codex / grok">
<label>Root cause (if known)</label><input type=text name=root_cause>
<label>Resolution (if known)</label><textarea name=resolution rows=2></textarea>
<label>Lesson / notes</label><textarea name=lessons rows=2></textarea>
<label>Optional URL / reference</label><input type=text name=reference_url>
<div style="margin-top:14px"><button>Save incident</button></div>
</form>'''
    return _shell("incidents", "Add L", body)


def render_incident_detail(store: DiagnosticKnowledgeStore, incident_id: str) -> tuple[int, str]:
    inc = store.incidents.get(incident_id)
    if inc is None:
        return 404, _shell("incidents", "Not found", "<div class=card>Incident not found.</div>")
    claims = store.incidents.claims_for(incident_id)
    claim_rows = "".join(
        f'<tr id="claim-{e(c.claim_id)}"><td>{status_pill(c.status.value)}</td><td>{e(c.text)}</td><td>{e(c.source)}</td>'
        f'<td>{e(c.created_at.strftime("%Y-%m-%d %H:%M"))}</td>'
        f'<td>{f"→ superseded by <a href=#claim-{e(c.superseded_by)}>{e(c.superseded_by[:8])}</a>" if c.superseded_by else f'<a href="#" onclick="return supersede(\'{e(c.claim_id)}\',\'{e(c.text[:60]).replace(chr(39), chr(96))}\')">Supersede this</a>'}</td></tr>'
        for c in claims
    )
    evidence_rows = "".join(
        f'<li><a href="/reports/{e(oid)}">{e(oid[:8])}</a></li>' for oid in inc.raw_evidence_ids
    )
    atts = store.attachments.for_incident(incident_id)
    att_rows = "".join(
        f'<li><a href="/attachments/{e(a.attachment_id)}/download">{e(a.original_filename)}</a> '
        f'({a.size_bytes} bytes, sha256 {e(a.content_hash[:12])}…)</li>' for a in atts
    )
    related = "".join(f'<li><a href="/incidents/{e(rid)}">{e(rid[:8])}</a></li>' for rid in inc.related_incident_ids)
    status_opts = "".join(f'<option value="{s.value}" {"selected" if s==inc.status else ""}>{s.value}</option>' for s in IncidentStatus)
    claim_status_opts = "".join(f'<option value="{s.value}">{s.value}</option>' for s in ClaimVerification)
    body = f'''<h1>{e(inc.title)}</h1>
<div class=card><div class=kv><b>Clank</b><span>{e(inc.clank_id)}</span></div>
<div class=kv><b>Status</b><span>{status_pill(inc.status.value)}</span></div>
<div class=kv><b>Classification</b><span>{", ".join(e(c.value) for c in inc.classification) or "—"}</span></div>
<div class=kv><b>Severity</b><span>{e(inc.severity) or "—"}</span></div>
<div class=kv><b>Reported by</b><span>{e(inc.reported_by) or "—"}</span></div>
<div class=kv><b>Expected behaviour</b><span>{e(inc.expected_behaviour) or "—"}</span></div>
<div class=kv><b>Observed behaviour</b><span>{e(inc.observed_behaviour) or "—"}</span></div>
<div class=kv><b>Root cause</b><span>{e(inc.root_cause) or "UNKNOWN"} ({e(inc.root_cause_certainty.value)})</span></div>
<div class=kv><b>Resolution</b><span>{e(inc.resolution) or "—"}</span></div>
<div class=kv><b>Lessons</b><span>{e(inc.lessons) or "—"}</span></div>
<div class=kv><b>Reference</b><span>{f'<a href="{e(inc.reference_url)}" target=_blank>{e(inc.reference_url)}</a>' if inc.reference_url else "—"}</span></div>
<div class=kv><b>Created / Updated</b><span>{e(inc.created_at)} / {e(inc.updated_at)}</span></div>
</div>
<div class=card><form method=post action="/incidents/{e(inc.incident_id)}/status" style="display:flex;gap:8px;align-items:end">
<div><label>Change status</label><select name=status>{status_opts}</select></div><button>Update</button></form></div>

<h2>Claim history</h2><div class=card>
{'<table><thead><tr><th>Status</th><th>Text</th><th>Source</th><th>When</th><th></th></tr></thead><tbody>' + claim_rows + '</tbody></table>' if claims else '<div class=empty>No claims recorded yet.</div>'}
<form method=post action="/incidents/{e(inc.incident_id)}/claims" style="margin-top:12px" id=claim-form>
<label>Add claim / observation</label><textarea name=text id=claim-text rows=2 required></textarea>
<label>Source</label><input type=text name=source placeholder="owner / claude / codex / grok">
<label>Status</label><select name=status id=claim-status>{claim_status_opts}</select>
<label>Supersedes claim <span id=supersede-target class=muted>(none — click "Supersede this" on a claim above, or paste a claim_id)</span></label>
<input type=text name=supersedes id=claim-supersedes placeholder="paste claim_id or leave blank">
<div style="margin-top:10px"><button>Add claim</button></div>
</form></div>
<script>function supersede(id, preview){{
document.getElementById('claim-supersedes').value=id;
document.getElementById('supersede-target').textContent='(superseding: '+preview+'...)';
document.getElementById('claim-status').value='contradicted';
document.getElementById('claim-text').focus();
document.getElementById('claim-form').scrollIntoView({{behavior:'smooth'}});
return false;
}}</script>

<h2>Raw evidence</h2><div class=card>{f'<ul>{evidence_rows}</ul>' if evidence_rows else '<div class=empty>No linked reports.</div>'}
<form method=post action="/incidents/{e(inc.incident_id)}/link-evidence">
<label>Link agent report by output_id</label><input type=text name=output_id placeholder="paste output_id">
<div style="margin-top:10px"><button class=secondary>Link</button></div></form></div>

<h2>Attachments</h2><div class=card>{f'<ul>{att_rows}</ul>' if att_rows else '<div class=empty>No attachments.</div>'}
<form method=post action="/incidents/{e(inc.incident_id)}/attachments" enctype=multipart/form-data>
<label>Attach file (screenshot/log/text/markdown/json)</label><input type=file name=file required>
<div style="margin-top:10px"><button class=secondary>Upload</button></div></form></div>

<h2>Related incidents</h2><div class=card>{f'<ul>{related}</ul>' if related else '<div class=empty>None linked.</div>'}
<form method=post action="/incidents/{e(inc.incident_id)}/relate">
<label>Relate incident by id</label><input type=text name=related_incident_id placeholder="paste incident_id">
<div style="margin-top:10px"><button class=secondary>Relate</button></div></form></div>'''
    return 200, _shell("incidents", inc.title, body)


def render_reports_list(store: DiagnosticKnowledgeStore) -> str:
    reports = store.inbox.list(limit=500)
    body = f'<h1>Agent Reports</h1>{_report_table(reports)}'
    return _shell("reports", "Agent Reports", body)


def render_report_new_form() -> str:
    agent_opts = "".join(f'<option value="{a.value}">{a.value}</option>' for a in AgentFamily)
    type_opts = "".join(f'<option value="{t.value}">{t.value}</option>' for t in OutputType)
    body = f'''<h1>Import Report</h1><p class=muted>Paste a complete Claude / Codex / Grok / owner report. The exact text is preserved verbatim as raw evidence; a CLANKOPS_RECORD footer (if present) is extracted deterministically.</p>
<form method=post action="/reports" class=card>
<label>Agent</label><select name=agent_family>{agent_opts}</select>
<label>Clank / project</label><input type=text name=primary_clank_id placeholder="e.g. smartwatch-clank, or fleet-wide">
<label>Output type</label><select name=output_type>{type_opts}</select>
<label>Session label (optional)</label><input type=text name=session_label>
<label>Raw report text *</label><textarea name=raw_text rows=18 required placeholder="Paste the complete report here, verbatim..."></textarea>
<div style="margin-top:14px"><button>Import report</button></div>
</form>'''
    return _shell("reports", "Import Report", body)


def render_report_detail(store: DiagnosticKnowledgeStore, output_id: str) -> tuple[int, str]:
    rec = store.inbox.get(output_id)
    if rec is None:
        return 404, _shell("reports", "Not found", "<div class=card>Report not found.</div>")
    claims = store.inbox.claims_for(output_id)
    claim_rows = "".join(f'<li>{status_pill(c.status.value)} {e(c.text)}</li>' for c in claims)
    atts = store.attachments.for_output(output_id)
    att_rows = "".join(f'<li><a href="/attachments/{e(a.attachment_id)}/download">{e(a.original_filename)}</a></li>' for a in atts)
    # CLANKOPS_RECORD is never persisted separately -- always re-derived from
    # the immutable raw_text, proving derived knowledge stays reconstructible.
    cor = extract_clankops_record(rec.raw_text)
    cor_html = ""
    if not cor.is_empty():
        cor_rows = "".join(
            f'<div class=kv><b>{e(field)}</b><span>{e(value)}</span></div>'
            for field, value in cor.model_dump().items() if value is not None
        )
        cor_html = f'<h2>CLANKOPS_RECORD (deterministically extracted)</h2><div class=card>{cor_rows}</div>'
    body = f'''<h1>Agent Report {e(output_id[:8])}</h1>{cor_html}''' + f'''
<div class=card>
<div class=kv><b>Agent</b><span>{e(rec.agent_family.value)}</span></div>
<div class=kv><b>Clank</b><span>{e(rec.primary_clank_id)}</span></div>
<div class=kv><b>Related Clanks</b><span>{", ".join(e(c) for c in rec.related_clank_ids) or "—"}</span></div>
<div class=kv><b>Type</b><span>{e(rec.output_type.value)}</span></div>
<div class=kv><b>Ingested</b><span>{e(rec.created_at)}</span></div>
<div class=kv><b>SHA-256</b><span>{e(rec.raw_text_hash)}</span></div>
<div class=kv><b>Detected git revision</b><span>{e(rec.related_git_revision) or "—"}</span></div>
<div class=kv><b>Session</b><span>{e(rec.session_label) or "—"}</span></div>
</div>
<h2>Auto-extracted claims (heuristic, deterministic)</h2><div class=card>{f'<ul>{claim_rows}</ul>' if claim_rows else '<div class=empty>None extracted.</div>'}</div>
<h2>Attachments</h2><div class=card>{f'<ul>{att_rows}</ul>' if att_rows else '<div class=empty>No attachments.</div>'}
<form method=post action="/reports/{e(output_id)}/attachments" enctype=multipart/form-data>
<label>Attach file</label><input type=file name=file required>
<div style="margin-top:10px"><button class=secondary>Upload</button></div></form></div>
<h2>Raw report (verbatim)</h2><div class="card rawbox">{e(rec.raw_text)}</div>'''
    return 200, _shell("reports", f"Report {output_id[:8]}", body)


def render_evidence_list(store: DiagnosticKnowledgeStore) -> str:
    reports = store.inbox.list(limit=500)
    body = f'<h1>Raw Evidence</h1><p class=muted>All immutable raw evidence, inspectable without querying SQLite directly.</p>{_report_table(reports)}'
    return _shell("evidence", "Raw Evidence", body)


def render_search(store: DiagnosticKnowledgeStore, query: str) -> str:
    results_html = ""
    if query.strip():
        results = store.search_all(query)
        inc_rows = "".join(
            f'<tr><td><a href="/incidents/{e(i.incident_id)}">{e(i.title)}</a></td><td>{e(i.clank_id)}</td>{status_pill(i.status.value)}</tr>'
            for i in results["incidents"]
        )
        rep_rows = "".join(
            f'<tr><td><a href="/reports/{e(r.output_id)}">{e(r.output_id[:8])}</a></td><td>{e(r.agent_family.value)}</td><td>{e(r.primary_clank_id)}</td></tr>'
            for r in results["reports"]
        )
        results_html = f'''<h2>Incidents ({len(results["incidents"])})</h2>
<div class=card>{f'<table><tbody>{inc_rows}</tbody></table>' if inc_rows else '<div class=empty>No matching incidents.</div>'}</div>
<h2>Agent reports ({len(results["reports"])})</h2>
<div class=card>{f'<table><tbody>{rep_rows}</tbody></table>' if rep_rows else '<div class=empty>No matching reports.</div>'}</div>'''
    body = f'''<h1>Search</h1>
<form method=get class=card style="display:flex;gap:10px"><input type=text name=q value="{e(query)}" placeholder="title, clank, agent, classification, raw report text, root cause, resolution, lessons..."><button>Search</button></form>
{results_html}'''
    return _shell("search", "Search", body)


def render_ingest_landing() -> str:
    body = '''<h1>Ingest</h1><p class=muted>Two ways to add knowledge:</p>
<div class=card><h2>+ Add L</h2><p class=muted>Log an incident manually -- fast, minimal required fields.</p><a class="nav-cta" style="display:inline-block;width:auto;padding:10px 20px" href="/incidents/new">+ ADD L</a></div>
<div class=card><h2>Import Report</h2><p class=muted>Paste a complete Claude/Codex/Grok/owner report verbatim.</p><a class="nav-cta alt" style="display:inline-block;width:auto;padding:10px 20px" href="/reports/new">IMPORT REPORT</a></div>'''
    return _shell("overview", "Ingest", body)


# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------


def render_file_inbox(store: DiagnosticKnowledgeStore, scan_summary: str = "") -> str:
    from diagnostic_clank.paths import resolve_report_paths
    rp = resolve_report_paths()
    def _list(dir_path, limit=50):
        if not dir_path.is_dir():
            return []
        files = sorted(
            [f for f in dir_path.iterdir() if f.is_file() and not f.name.endswith(".reason.txt")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return files[:limit]
    inbox_files = _list(rp.inbox)
    processed_files = _list(rp.processed)
    quarantined = _list(rp.quarantine)
    def rows(files, empty):
        if not files:
            return f'<div class=empty>{empty}</div>'
        body = "".join(
            f"<tr><td>{e(f.name)}</td><td class=muted>{e(f.stat().st_size)} B</td></tr>"
            for f in files
        )
        return f"<table><tr><th>File</th><th>Size</th></tr>{body}</table>"
    summary_html = f'<div class=card>{e(scan_summary)}</div>' if scan_summary else ""
    body = (
        f'<h1>File Inbox</h1>'
        f'<p class=muted>Logical root: <code>CLANKOPS_REPORT_ROOT</code> resolved to '
        f'<code>{e(rp.root)}</code></p>'
        f'{summary_html}'
        f'<form method=post action="/file-inbox/scan" class=card>'
        f'<button type=submit>Scan inbox now</button> '
        f'<span class=muted>Preserves raw evidence by content hash; moves to processed/ or quarantine/</span>'
        f'</form>'
        f'<div class=grid4>'
        f'<div class=stat><div class=muted>Inbox</div><b>{len(inbox_files)}</b></div>'
        f'<div class=stat><div class=muted>Processed</div><b>{len(processed_files)}</b></div>'
        f'<div class=stat><div class=muted>Quarantine</div><b>{len(quarantined)}</b></div>'
        f'<div class=stat><div class=muted>Agent reports (DB)</div><b>{len(store.inbox.list(limit=100000))}</b></div>'
        f'</div>'
        f'<h2>Inbox</h2><div class=card>{rows(inbox_files, "Empty")}</div>'
        f'<h2>Processed</h2><div class=card>{rows(processed_files, "None yet")}</div>'
        f'<h2>Quarantine</h2><div class=card>{rows(quarantined, "None")}</div>'
    )
    return _shell("file-inbox", "File Inbox", body)


def serve(paths: StatePaths, host: str = "127.0.0.1", port: int = 0) -> tuple[HTTPServer, DiagnosticKnowledgeStore]:
    registry = build_registry()
    store = DiagnosticKnowledgeStore(paths.db_path, paths.evidence_dir, paths.quarantine_dir, registry)

    class Handler(BaseHTTPRequestHandler):
        def _html(self, status: int, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _redirect(self, location: str) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            self.end_headers()

        def _json(self, status: int, obj: object) -> None:
            data = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            qs = parse_qs(parsed.query)
            if path == "/healthz":
                self._json(200, {"application": "DiagnosticClank", "status": "ok", "db": str(store.db_path)})
                return
            if path == "/":
                self._html(200, render_overview(store)); return
            if path == "/incidents/new":
                self._html(200, render_incident_new_form(registry)); return
            if path == "/incidents":
                self._html(200, render_incidents_list(store, qs.get("clank", [""])[0], qs.get("status", [""])[0])); return
            if path.startswith("/incidents/"):
                incident_id = path.rsplit("/", 1)[1]
                status, body = render_incident_detail(store, incident_id)
                self._html(status, body); return
            if path == "/reports/new":
                self._html(200, render_report_new_form()); return
            if path == "/file-inbox":
                self._html(200, render_file_inbox(store)); return
            if path == "/reports":
                self._html(200, render_reports_list(store)); return
            if path.startswith("/reports/"):
                output_id = path.rsplit("/", 1)[1]
                status, body = render_report_detail(store, output_id)
                self._html(status, body); return
            if path == "/evidence":
                self._html(200, render_evidence_list(store)); return
            if path == "/search":
                self._html(200, render_search(store, qs.get("q", [""])[0])); return
            if path == "/ingest":
                self._html(200, render_ingest_landing()); return
            if path.startswith("/attachments/") and path.endswith("/download"):
                attachment_id = path.split("/")[2]
                att = store.attachments.get(attachment_id)
                if att is None:
                    self.send_error(404); return
                data = store.attachments.read_bytes(attachment_id)
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", f'attachment; filename="{att.original_filename}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_error(404)

        def _read_form(self) -> dict[str, list[str]]:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            return parse_qs(body)

        def _read_multipart(self) -> tuple[dict[str, list[str]], bytes | None, str | None]:
            import cgi
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length", "0"))
            fs = cgi.FieldStorage(
                fp=self.rfile, headers=self.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": ctype, "CONTENT_LENGTH": str(length)},
            )
            fields: dict[str, list[str]] = {}
            file_bytes, file_name = None, None
            for key in fs.keys():
                item = fs[key]
                if getattr(item, "filename", None):
                    file_bytes = item.value if isinstance(item.value, bytes) else item.value.encode("utf-8")
                    file_name = item.filename
                else:
                    fields.setdefault(key, []).append(item.value)
            return fields, file_bytes, file_name

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            content_type = self.headers.get("Content-Type", "")
            try:
                if path == "/incidents":
                    form = self._read_form()
                    inc = store.incidents.create(
                        clank_id=form.get("clank_id", [""])[0].strip(),
                        title=form.get("title", [""])[0].strip(),
                        classification=[IncidentClassification(v) for v in form.get("classification", [])],
                        severity=form.get("severity", [None])[0] or None,
                        status=IncidentStatus(form.get("status", ["OPEN"])[0]),
                        reported_by=form.get("reported_by", [None])[0] or None,
                        expected_behaviour=form.get("expected_behaviour", [None])[0] or None,
                        observed_behaviour=form.get("observed_behaviour", [None])[0] or None,
                        root_cause=form.get("root_cause", [None])[0] or None,
                        root_cause_certainty=RootCauseCertainty.HYPOTHESIS if form.get("root_cause", [""])[0] else RootCauseCertainty.UNKNOWN,
                        resolution=form.get("resolution", [None])[0] or None,
                        lessons=(form.get("lessons", [None])[0] or None) or (form.get("narrative", [None])[0] or None),
                        reference_url=form.get("reference_url", [None])[0] or None,
                    )
                    self._redirect(f"/incidents/{inc.incident_id}"); return
                if path.startswith("/incidents/") and path.endswith("/status"):
                    incident_id = path.split("/")[2]
                    form = self._read_form()
                    store.incidents.update_status(incident_id, IncidentStatus(form.get("status", ["OPEN"])[0]))
                    self._redirect(f"/incidents/{incident_id}"); return
                if path.startswith("/incidents/") and path.endswith("/claims"):
                    incident_id = path.split("/")[2]
                    form = self._read_form()
                    text = form.get("text", [""])[0].strip()
                    supersedes = form.get("supersedes", [""])[0].strip()
                    status = ClaimVerification(form.get("status", ["REPORTED"])[0])
                    source = form.get("source", [None])[0] or None
                    if not text:
                        self._redirect(f"/incidents/{incident_id}"); return
                    if supersedes:
                        store.incidents.supersede_claim(supersedes, text, source=source, status=status)
                    else:
                        store.incidents.add_claim(incident_id, text, source=source, status=status)
                    self._redirect(f"/incidents/{incident_id}"); return
                if path.startswith("/incidents/") and path.endswith("/link-evidence"):
                    incident_id = path.split("/")[2]
                    form = self._read_form()
                    output_id = form.get("output_id", [""])[0].strip()
                    if output_id and store.inbox.get(output_id) is not None:
                        store.incidents.link_evidence(incident_id, output_id)
                    self._redirect(f"/incidents/{incident_id}"); return
                if path.startswith("/incidents/") and path.endswith("/relate"):
                    incident_id = path.split("/")[2]
                    form = self._read_form()
                    related_id = form.get("related_incident_id", [""])[0].strip()
                    if related_id and store.incidents.get(related_id) is not None:
                        store.incidents.relate(incident_id, related_id)
                    self._redirect(f"/incidents/{incident_id}"); return
                if path.startswith("/incidents/") and path.endswith("/attachments"):
                    incident_id = path.split("/")[2]
                    fields, file_bytes, file_name = self._read_multipart()
                    if file_bytes is not None:
                        try:
                            store.attachments.save(content=file_bytes, original_filename=file_name or "upload", incident_id=incident_id)
                        except AttachmentQuarantined:
                            pass  # invalid input never damages canonical state; silently quarantined
                    self._redirect(f"/incidents/{incident_id}"); return
                if path.startswith("/reports/") and path.endswith("/attachments"):
                    output_id = path.split("/")[2]
                    fields, file_bytes, file_name = self._read_multipart()
                    if file_bytes is not None:
                        try:
                            store.attachments.save(content=file_bytes, original_filename=file_name or "upload", output_id=output_id)
                        except AttachmentQuarantined:
                            pass
                    self._redirect(f"/reports/{output_id}"); return
                if path == "/reports":
                    form = self._read_form()
                    raw_text = form.get("raw_text", [""])[0]
                    clank_id = form.get("primary_clank_id", ["fleet-wide"])[0].strip() or "fleet-wide"
                    if clank_id != "fleet-wide" and registry.get(clank_id) is None:
                        registry.register(ClankRegistration(clank_id=clank_id, display_name=clank_id))
                    result = store.ingest_report(
                        agent_family=AgentFamily(form.get("agent_family", ["misc"])[0]),
                        primary_clank_id=clank_id,
                        raw_text=raw_text,
                        output_type=OutputType(form.get("output_type", ["general_note"])[0]),
                        session_label=form.get("session_label", [None])[0] or None,
                    )
                    self._redirect(f"/reports/{result.output.output_id}"); return
                if path == "/file-inbox/scan":
                    from diagnostic_clank.report_pipeline import scan_and_ingest
                    from diagnostic_clank.paths import resolve_report_paths, resolve_state_paths
                    reports = resolve_report_paths()
                    scan = scan_and_ingest(store, reports)
                    summary = (
                        f"scanned={scan.scanned} ingested={scan.ingested} "
                        f"duplicates={scan.duplicates} quarantined={scan.quarantined}"
                    )
                    self._html(200, render_file_inbox(store, summary)); return
                self.send_error(404)
            except (KeyError, ValueError) as exc:
                self._html(400, _shell("overview", "Error", f'<div class=card>Request error: {e(exc)}</div>'))

        def log_message(self, *_: object) -> None:
            pass

    # Single-threaded on purpose: local single-user tool, and the shared
    # sqlite3 connections in DiagnosticKnowledgeStore are not safe to touch
    # from multiple threads at once (ThreadingHTTPServer would spawn a new
    # thread per request and hit sqlite3's cross-thread guard).
    server = HTTPServer((host, port), Handler)
    return server, store
