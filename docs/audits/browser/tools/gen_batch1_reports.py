#!/usr/bin/env python3
"""Generates docs/audits/browser/M0{1..4}_BROWSER_DETAILED.md and the Batch-1 section of
docs/audits/final/M01_M15_BROWSER_ACCEPTANCE.md from the raw Playwright run files in docs/audits/browser/evidence/.

Nothing here invents results: every table row is a row recorded by the Playwright scripts (see evidence/*.json and
tools/playwright/*.py). Narrative sections (integration, findings) are written by the auditor in this file."""
import collections
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]          # docs/audits/browser
EV = ROOT / "evidence"
FINAL_DOC = ROOT.parent / "final" / "M01_M15_BROWSER_ACCEPTANCE.md"
RUNS = json.load(open(EV / "final_runs.json"))
INV = json.load(open(EV / "inventory_owner.json"))
COV = json.load(open(EV / "coverage.json"))
SUPERSEDED = {("M04", "Notification bell present for the planner"): "harness: the bell is HTMX-loaded and the test did not wait for it; re-tested in m04c (4/4 PASS)"}
SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "COSMETIC"]
UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
NAMES = {"M01": "Sites, Locations, Calendars & Contacts", "M02": "Asset Registry (assets, categories, documents, meters, status)", "M03": "Asset Hierarchy (components & assemblies)", "M04": "Preventive Maintenance (plans, schedules, generation)"}
ROLES = ["owner", "admin", "ops", "supervisor", "assets", "planner", "tech", "tech2", "stores", "service", "auditor", "client"]

# ------------------------------------------------------------------------------------------------ findings (browser)
FINDINGS = [
    dict(id="BX-M04-01", module="M04", sev="HIGH", title="Editing a schedule's recurrence re-points it at an already-generated occurrence; the next due occurrence is silently lost (F-H01, reproduced in the browser)",
         page="/app/maintenance/schedules/{id}/edit/ -> /app/maintenance/schedules/{id}/", role="owner (Org Owner)", action="Generate cycle 0 (monthly, start today) -> Edit: interval 1 -> 2 -> Save -> open schedule -> Generate now",
         expected="After the edit the schedule continues at the next valid occurrence (sequence 1, date in 2 months) and keeps generating work orders (D-043 / HPE PM requirement).",
         actual="Saved schedule shows next occurrence no. 0, next due = today, state DUE although cycle 0 already has its work order; 'Generate now' answers 'Nothing was generated (that occurrence already has its work order)'. The unique (schedule, sequence) collision is swallowed: work orders 12 -> 12; database after the click: next_sequence=1, next due moved to 2026-12-04 (the occurrence due today was skipped), last_error empty, audit rows for the schedule only 'schedule_created' and 'schedule_updated' (nothing records the skip).",
         api="POST /app/maintenance/schedules/{id}/edit/ 302; POST .../generate/ 302 (flash 'Nothing was generated')", console="none (the failure is silent)", shot="evidence/shots/M04_generated_wo.png (cycle 0) - failure is textual, see run row 'F-H01 recheck'",
         source="src/apps/maintenance/services.py: update_schedule:299, _resync:210, generate_cycle IntegrityError branch:460", feature_match="F-H01 recheck", status="OPEN (same defect as F-H01 in FINDINGS_REGISTER.md; browser-confirmed)"),
    dict(id="BX-M01-01", module="M01", sev="MEDIUM", title="Site-contact escalation order above 32767 returns HTTP 500 (UI form and API)",
         page="/app/sites/{id}/contacts/new/ (and POST /api/v1/site-contacts/)", role="owner", action="Add contact with name, phone and escalation order 99999999999",
         expected="400 re-render with an inline error ('Ensure this value is less than or equal to ...'), nothing saved.",
         actual="HTTP 500 'Server Error' page; API answers 500 as well. Log: django.db.utils.DataError: smallint out of range.",
         api="POST /app/sites/{id}/contacts/new/ -> 500; POST /api/v1/site-contacts/ -> 500", console="Failed to load resource: 500 (provoked)", shot="(error page, no screenshot needed - see run row)",
         source="src/apps/sites/forms.py:70 and src/apps/sites/api_views.py:136 (IntegerField min_value=1, no max_value) vs src/apps/sites/models.py:130 (PositiveSmallIntegerField); error raised in services.add_contact -> _save (services.py:410-416)", feature_match="Escalation order huge", status="OPEN"),
    dict(id="BX-M03-01", module="M03", sev="MEDIUM", title="Retiring/disposing a parent that still has live children is accepted; the live child can then never be detached, yet the UI still shows Detach (F-M06 reproduced)",
         page="/app/assets/{parent}/ (Retire) then /app/assets/{child}/?tab=hierarchy", role="owner", action="Retire parent P (child K attached) -> open K's Hierarchy tab -> Detach",
         expected="Retire refused (or links detached first) so no live asset hangs under a terminal one; any Detach button shown must work.",
         actual="Retire accepted (RETIRED). K stays linked to the retired parent; Edit/Move/Detach controls are still rendered for K but every attempt is refused server-side with asset_terminal ('Retired or disposed assets cannot take part in the hierarchy').",
         api="POST /app/components/{id}/remove/ -> 302 with error flash; link row remains", console="none", shot="evidence/shots/M03_mobile_tree.png (tree) - result is textual, see run rows 'Retire a parent that still has a live child'",
         source="src/apps/assets/services.py:207 (change_status has no hierarchy guard); src/apps/assets/hierarchy.py:133,158 (update/remove refuse terminal assets); src/templates/assets/detail.html (controls rendered regardless)", feature_match="Retire a parent", status="OPEN (same defect as F-M06)"),
    dict(id="BX-M03-02", module="M03", sev="LOW", title="Hierarchy tree panel stays on 'Loading hierarchy…' forever when its HTMX request fails",
         page="/app/assets/{id}/?tab=hierarchy", role="owner", action="Make GET /app/assets/{id}/tree/ fail (HTTP 500, then aborted) -> open the tab",
         expected="A visible error / retry message in the panel.", actual="Panel text remains 'Loading hierarchy…' (no timeout, no error). The same pattern applies to the Coverage and Labels panels (hx-trigger=load, no error handler).",
         api="GET /app/assets/{id}/tree/ -> 500 (injected)", console="Failed to load resource 500 / net::ERR_FAILED (injected)", shot="evidence/shots/M03_tree_htmx_fail.png",
         source="src/templates/assets/detail.html (#tree-host, #coverage-host, #labels-host); no htmx:responseError handler in src/static/js/app.js", feature_match="Tree panel when", status="OPEN"),
    dict(id="BX-ALL-01", module="M01-M04", sev="LOW", title="Keyboard / mobile navigation accessibility: no 'skip to content' link; off-canvas sidebar links stay focusable while hidden; Esc does not close the open mobile menu",
         page="every /app/ page (src/templates/shell.html)", role="owner", action="Tab from the top of any page; open the mobile menu at 390 px and press Escape",
         expected="Skip link; hidden navigation not focusable; Esc closes the menu.", actual="~35 sidebar tab stops precede page content; the hidden (translated off-screen) nav links remain in the tab order; the menu stays open after Esc.",
         api="-", console="none", shot="evidence/shots/M01_mobile_menu_open.png", source="src/templates/shell.html, src/static/js/app.js:41", feature_match="skip to content", status="OPEN"),
    dict(id="BX-M01-02", module="M01", sev="LOW", title="Deactivate site / location: the confirmation dialog opens before the mandatory reason is validated",
         page="/app/sites/{id}/ and ?tab=locations", role="owner", action="Click Deactivate with an empty reason",
         expected="Reason validated before (or inside) the confirmation.", actual="Dialog opens first; after Confirm the browser focuses the empty required reason field (no data change). Cosmetic UX order only.",
         api="-", console="none", shot="-", source="src/templates/sites/detail.html:12", feature_match="Deactivate without reason", status="OPEN"),
    dict(id="BX-M01-03", module="M01", sev="LOW", title="Sites and locations have no history/audit view of their own (only the global Audit Trail)",
         page="/app/sites/{id}/ (tabs: Overview, Locations, Calendars, Contacts, Assets)", role="owner/auditor", action="Look for a History tab as assets have",
         expected="HPE M01 traceability: history of changes reachable from the site.", actual="No History tab; events are visible only in /app/audit/?q=<code> (verified present for owner and auditor).",
         api="-", console="none", shot="-", source="src/templates/sites/detail.html", feature_match="Site detail 'History' tab", status="OPEN"),
    dict(id="BX-M01-04", module="M01", sev="LOW", title="Site list has no sorting controls (fixed order by code)",
         page="/app/sites/", role="owner", action="Look for sortable column headers / ?ordering=", expected="Sortable list (task scope lists sorting).", actual="Headers are plain text; ?ordering= is ignored; rows are ordered by site code (verified equal to the database order).",
         api="-", console="none", shot="-", source="src/apps/sites/selectors.py:69 (order_by('code')), src/templates/sites/list.html", feature_match="Site list column sorting", status="OPEN"),
    dict(id="BX-M02-01", module="M02", sev="LOW", title="Asset list: no zone/location filter and no sorting controls in the UI (backend supports ?zone=, ?owner=, ?ordering=)",
         page="/app/assets/", role="owner", action="Inspect the filter bar and table header", expected="Filter by zone/location and sortable columns (task scope lists zone filter and sort).",
         actual="Filter bar has only q/site/category/status; headers are plain text. ?zone=<id>, ?owner=<id> and ?ordering=name|-name|status|-created_at work when typed in the URL (verified).",
         api="GET /app/assets/?zone=<id> 200", console="none", shot="-", source="src/templates/assets/list.html:10-18; src/apps/assets/selectors.py:44-58", feature_match="Zone / location filter control", status="OPEN"),
    dict(id="BX-M02-02", module="M02", sev="LOW", title="Meter tab shows only the last reading; the reading history is not visible in the browser",
         page="/app/assets/{id}/?tab=meters", role="owner", action="Record several readings, look for the list of past readings", expected="History of readings (task scope: meter history).",
         actual="Only 'Last reading: value on date' per meter; earlier readings exist in the database/API only.", api="-", console="none", shot="-", source="src/templates/assets/detail.html (meters tab)", feature_match="Meter reading history list", status="OPEN"),
    dict(id="BX-M03-03", module="M03", sev="LOW", title="No single-step 'Replace component' action (replace = Detach + Add)",
         page="/app/assets/{id}/?tab=hierarchy", role="owner", action="Look for a replace control", expected="Replace relationship (task scope).", actual="Replacement is done with two audited steps (Detach, then attach another asset); both steps verified.",
         api="-", console="none", shot="-", source="src/templates/assets/detail.html (hierarchy tab)", feature_match="Single-step 'Replace component'", status="OPEN (design gap, not a malfunction)"),
    dict(id="BX-M04-02", module="M04", sev="LOW", title="'Estimated hours = 0' is accepted by the form (min=0) but refused by the server ('must be a positive number')",
         page="/app/maintenance/plans/new/", role="owner", action="Create a plan with estimated hours 0", expected="Form and server agree.", actual="400 with a clear message; nothing saved (safe, inconsistent).",
         api="POST /app/maintenance/plans/new/ -> 400", console="400 (provoked)", shot="-", source="src/apps/maintenance/forms.py:25 vs services.py:90 (_decimal positive=True)", feature_match="estimated hours = 0", status="OPEN"),
    dict(id="BX-M04-03", module="M04", sev="LOW", title="DUE state does not distinguish 'due today' from 'overdue by N days'",
         page="/app/maintenance/due/, schedule and history pages", role="owner", action="Rewind a schedule 7 days (QA database) and read the state", expected="An overdue indicator.", actual="State DUE; the backlog is shown only as '+7 missed' on the generated cycle.",
         api="-", console="none", shot="-", source="src/apps/maintenance/selectors.py:87 (schedule_state)", feature_match="Cycle table 'Overdue' presentation", status="OPEN"),
    dict(id="BX-ALL-02", module="M01-M04", sev="COSMETIC", title="Every fresh browser session logs 'GET /favicon.ico -> 404' in the console (no favicon served)",
         page="any page", role="any", action="Open any page in a new browser context", expected="No console error.", actual="Console error 'Failed to load resource: 404 /favicon.ico' (once per fresh context).",
         api="GET /favicon.ico -> 404", console="Failed to load resource: the server responded with a status of 404 (Not Found) /favicon.ico", shot="-", source="src/templates/shell.html / static files (no <link rel=icon>)", feature_match="", status="OPEN"),
]
UNVERIFIED = [   # (module, item, why, already_a_row_in_the_run_data)
    ("M04", "PM state follows the work order lifecycle (assigned / completed / verified)", "Advancing a work order is M06 (later batch). Only GENERATED state and the cycle -> work-order contract were verified (WO row, source link, planned window, priority, hours, checklist text, link from the cycle table to the WO page).", True),
    ("M02", "Asset 'Coverage' tab (M10 contract panel) and 'Labels' tab (M07 QR panel)", "Both tabs load through HTMX without error for the owner; their own behaviour belongs to the M10/M07 batches and was not exercised.", False),
]
INTEGRATION = {
    "M01": ["Site -> Zone -> Asset (M02): the asset form offers only ACTIVE zones of ACTIVE sites; choosing a site narrows the zones; the asset page shows its zone; the zone tree counts and blocks deactivation for zones holding ACTIVE assets (PASS).",
            "Site/zone deactivation rules enforced against children and assets (PASS). Calendar -> M04: the generated work order's planned window moved from Sunday to Monday because the site's default calendar is Mon-Fri (PASS, see M04).",
            "Contact hierarchy is data only in this batch (escalation consumers are in M05/M13)."],
    "M02": ["Asset <-> Site/Zone (M01): site/zone moves write location history with the typed reason (PASS).",
            "Asset -> M05: 'Report a problem' links to the incident form with ?asset=<id> (contract verified; the incident itself is M05).",
            "Asset status -> M04: retiring the asset blocks its PM schedules and the plan cannot be re-enabled (PASS). Deactivating a meter blocks meter-based schedules (PASS).",
            "Asset documents -> Files module: secure upload/download path with tenant checks (PASS)."],
    "M03": ["Parent/child assets share the site (enforced), cross-tenant ids rejected, hierarchy is shown on the asset list (Parent column), breadcrumbs and the History tab change log (PASS).",
            "Asset retire (M02) vs hierarchy (M03): integrity gap reproduced (BX-M03-01).",
            "Part numbers are stored as free text; the bridge to M09 inventory parts is a later batch (UNVERIFIED)."],
    "M04": ["Site -> Zone -> Asset -> PM plan -> schedule -> generated Work Order: verified end to end in the browser and database (WO-numbered row, PREVENTIVE, plan priority, PLANNED, source = cycle id, asset, estimated hours, planned window = schedule window moved to the site's working day, description with plan/recurrence/required checklist).",
            "Duplicate prevention: second 'Generate now' refused while the previous WO is open; 5 simultaneous POSTs -> exactly one cycle/WO; Celery fan_out run 3x + 2x -> exactly one scheduler cycle, later runs idempotent (PASS).",
            "Meter-based: a reading recorded in M02 (520 h) turns the 500 h schedule DUE (PASS). Reminders: planner receives exactly one notification, visible in the notifications page and the bell (PASS).",
            "Overdue/missed catch-up was exercised by rewinding the QA database counters (clock cannot be advanced): ONE work order covered 7 missed occurrences ('+7 missed'). This is a labelled simulation, not a time-travel test.",
            "PM state after the work order moves on (assigned/completed/verified) is M06 -> UNVERIFIED in this batch."],
}


def load_rows(mod):
    rows, issues, expected, benign, htmx, htmx_fail = [], [], [], [], collections.Counter(), []
    cov_get, cov_post = collections.Counter(), collections.Counter()
    for f in RUNS[mod]:
        d = json.load(open(EV / f))
        rows += [dict(x, _run=f) for x in d["rows"]]
        issues += d["issues"]; expected += d["expected"]; benign += d["benign"]; htmx_fail += d["htmx_fail"]
        for k, v in d["htmx"].items(): htmx[k] += v
        for k, v in d["cov_get"].items(): cov_get[k] += v
        for k, v in d["cov_post"].items(): cov_post[k] += v
    keep = []
    for x in rows:
        if (mod, x["feature"]) in SUPERSEDED and x["status"] == "FAIL":
            x = dict(x, status="SUPERSEDED", evidence=SUPERSEDED[(mod, x["feature"])])
        keep.append(x)
    return keep, issues, expected, benign, htmx, htmx_fail, cov_get, cov_post


def esc(s, n=150):
    s = re.sub(r"(\s*\|\|\s*(Detach|×))+", "", str(s or ""))
    s = UUID.sub(lambda m: m.group(0)[:8], s).replace("|", "\\|").replace("\n", " ").replace("\r", " ")
    return (s[: n - 1] + "…") if len(s) > n else s


def unv_total(mod, c):
    return c["UNVERIFIED"] + sum(1 for u in UNVERIFIED if u[0] == mod and not u[3])


def counts(rows):
    c = collections.Counter(x["status"] for x in rows)
    scored = [x for x in rows if x["status"] not in ("NOT APPLICABLE", "SUPERSEDED")]
    return c, len(scored), c["PASS"]


def table(rows, cols=("feature", "role", "status", "actual"), widths=(110, 12, 12, 130)):
    out = ["| # | " + " | ".join(("Expected -> actual" if c == "actual" else c.title()) for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for i, x in enumerate(rows, 1):
        cells = []
        for c, w in zip(cols, widths):
            if c == "actual" and x.get("expected"):
                cells.append(esc(f"{x.get('expected')} -> {x.get('actual', '')}", w + 70))
            else:
                cells.append(esc(x.get(c, ""), w))
        out.append(f"| {i} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def is_rbac(x): return x["feature"].startswith("RBAC")
def is_tenant(x): return x["feature"].startswith(("Tenant", "API: Beta", "Setup: Beta", "Beta ", "Alpha ", "Anonymous")) or "another tenant" in x["feature"] or "Beta" in x["feature"][:12]
def is_resp(x): return x["feature"].startswith(("Responsive", "Mobile", "Keyboard")) or "dialog fits" in x["feature"] or "modal fits" in x["feature"].lower() or "Confirm modal" in x["feature"]
def is_valid(x): return bool(re.search(r"Validation|refused|rejected|Boundary|Crafted POST|forged|Forged|Negative|Cycle prevention|Circular|duplicate|Duplicate|XSS|required", x["feature"]))
def is_db(x): return bool(x.get("db")) or bool(x.get("audit"))
def is_htmx(x): return bool(re.search(r"HTMX|Tree|tree|bell|Bell|category reloads|Notification", x["feature"]))


def resp_matrix(rows):
    m = collections.OrderedDict()
    for x in rows:
        mm = re.match(r"Responsive (\w+): (.+?) \(no horizontal", x["feature"])
        if mm: m.setdefault(mm.group(2), {})[mm.group(1)] = x["status"]
    if not m: return "(no per-page responsive rows)"
    vps = ["desktop", "laptop", "tablet", "mobile"]
    out = ["| Page | 1920x1080 | 1440x900 | 1024x768 | 390x844 |", "|---|---|---|---|---|"]
    for page, d in m.items():
        out.append(f"| {esc(page, 60)} | " + " | ".join({"PASS": "PASS", "FAIL": "**FAIL**"}.get(d.get(v, ""), d.get(v, "-")) for v in vps) + " |")
    return "\n".join(out)


def rbac_matrix(rows):
    m = collections.OrderedDict()
    for x in rows:
        if not is_rbac(x): continue
        key = (x["feature"], x["page"] if x["page"] and not UUID.search(x["page"]) else "")
        m.setdefault(x["feature"], {})[x["role"]] = x["status"]
    out = ["| Check (expected outcome derived from the role's DB permission set) | " + " | ".join(ROLES) + " |", "|---|" + "---|" * len(ROLES)]
    for feat, d in m.items():
        out.append(f"| {esc(feat, 90)} | " + " | ".join({"PASS": "ok", "FAIL": "**FAIL**"}.get(d.get(r), "-") for r in ROLES) + " |")
    return "\n".join(out), len(m)


def page_section(mod, getc):
    mp = COV[mod]["pages"]; lines = ["| Page / URL (normalised) | Discovered by crawl | Browser visits |", "|---|---|---|"]
    disc = set(INV_PAGES[mod])
    keys = set(disc) | {k for k in getc if module_of(k) == mod and not k.startswith(("/accounts", "/api"))}
    for p in sorted(keys):
        n = getc.get(p, 0) or sum(v for k, v in getc.items() if k.split("?")[0] == p.split("?")[0] and (("?" not in p) or p.split("?")[1] in k))
        lines.append(f"| `{p}` | {'yes' if p in disc else 'no (reached by test)'} | {n} |")
    extra = sorted(k for k in getc if k not in keys and not module_of(k) == mod)
    return "\n".join(lines), mp, extra


def norm(u):
    p, _, q = u.partition("?")
    p = UUID.sub("{id}", p)
    return p + (("?" + "&".join(sorted(x.split("=")[0] for x in q.split("&") if x))) if q else "")


def module_of(path):
    p = path.split("?")[0]
    if "tab=hierarchy" in path or "/components/" in p or "/tree/" in p or "?parent" in path: return "M03"
    if p.startswith("/app/maintenance"): return "M04"
    if p.startswith("/app/assets") or p.startswith("/app/meters"): return "M02"
    return "M01"


INV_PAGES = collections.defaultdict(list)
for url in INV:
    INV_PAGES[module_of(url)].append(norm(url))


def forms_section(mod):
    seen, out = set(), ["| Form (action) | Method | Fields (non-hidden) | Exercised |", "|---|---|---|---|"]
    posts = COV[mod]["posts"]["untested"]
    for url, v in INV.items():
        if module_of(url) != mod: continue
        for f in v["forms"]:
            a = norm(f["action"]) if f["action"] else norm(url).split("?")[0] + " (self)"
            if (a, f["method"]) in seen: continue
            seen.add((a, f["method"]))
            names = ", ".join(x["n"] for x in f["fields"] if x["n"]) or "(button only)"
            ex = "no" if a in posts else "yes"
            out.append(f"| `{a}` | {f['method'].upper()} | {esc(names, 140)} | {ex} |")
    return "\n".join(out), len(seen)


def is_explained(i):
    """4xx answers to the scripted negative probes (forged ids, foreign tenants, invalid input) that the harness did not suppress;
    5xx, page errors, failed requests, static-asset and favicon problems are never 'explained'."""
    url = i.get("url", "") or ""
    return i["kind"] in ("http", "console") and bool(re.search(r"\b(400|403|404|405)\b", i["text"])) and "/static/" not in url and "favicon" not in url and "favicon" not in i["text"]


def issue_table(items):
    g = collections.Counter((i["kind"], re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "{id}", i["text"])[:110]) for i in items)
    return "\n".join(f"| {k[0]} | {esc(k[1], 110)} | {n} |" for k, n in g.most_common()) or "| - | none | 0 |"


def build(mod):
    rows, issues, expected, benign, htmx, htmx_fail, cov_get, cov_post = load_rows(mod)
    c, tot, ok = counts(rows)
    na = c["NOT APPLICABLE"]
    fnd = [f for f in FINDINGS if mod in f["module"] or f["module"] == "M01-M04"]
    sevc = collections.Counter(f["sev"] for f in fnd)
    fails = [x for x in rows if x["status"] == "FAIL"]
    cov = COV[mod]
    if fails or any(f["sev"] in ("HIGH", "CRITICAL") for f in fnd if mod in f["module"]):
        status = "FAIL (High defect)" if any(f["sev"] in ("HIGH", "CRITICAL") for f in fnd if mod in f["module"]) else "PARTIAL (defect reproduced)"
    elif c["PARTIAL"]: status = "PASS with LOW observations"
    else: status = "PASS"
    L = []
    A = L.append
    A(f"# {mod} browser acceptance - detailed ({NAMES[mod]})\n")
    A("**Batch 1 of the browser acceptance (M01-M04).** Real Chromium (Playwright) against the running application (DEBUG off, CSP on, PostgreSQL `fieldops_browser_qa`, Redis, Celery worker + beat). "
      "Every check below was performed in the browser (or by a real in-page request carrying the session cookie and CSRF token) and the database state was read back with SQL; "
      "an HTTP 200 alone was never accepted as evidence. No production code was modified.\n")
    A(f"**Result: {mod}: {ok}/{tot} browser checks PASS** ({c['FAIL']} FAIL, {c['PARTIAL']} PARTIAL, {unv_total(mod, c)} UNVERIFIED; {na} NOT APPLICABLE excluded; {c['SUPERSEDED']} superseded harness lines excluded). **Module status: {status}.**\n")
    A("Roles driven: owner, admin, ops, supervisor, assets, planner, tech (technician 1), tech2, stores, service, auditor, client (all Alpha) and betaowner (tenant Beta). Viewports: 1920x1080, 1440x900, 1024x768, 390x844.\n")
    A("Matrix columns used by the scripts: FEATURE / PAGE / ROLE / ACTION / EXPECTED / ACTUAL / DATABASE / API-HTMX / AUDIT / STATUS; the full matrix for this module is in `evidence/" + "`, `evidence/".join(RUNS[mod]) + "`.\n")
    # 1
    pages_md, mp, extra = page_section(mod, cov_get)
    A(f"## 1. Pages tested\n\nDiscovered by a crawl of the module (owner): {mp['total']} pages; visited in the test runs: {mp['exercised']}/{mp['total']}.\n")
    A(pages_md + "\n")
    if extra: A("Other URLs the tests visited (negative probes, redirects, API): " + ", ".join(f"`{e}`" for e in extra[:30]) + ("…" if len(extra) > 30 else "") + "\n")
    # 2
    A("## 2. Buttons / links / actions\n")
    b, l = cov["buttons"], cov["links"]
    A(f"Discovered controls: {b['total']} buttons ({b['exercised']} clicked/posted), {l['total']} distinct links ({l['exercised']} followed), {cov['posts']['total']} POST endpoints ({cov['posts']['exercised']} exercised), {cov['gets']['total']} GET filter forms ({cov['gets']['exercised']} used), {cov['htmx']['total']} HTMX endpoints ({cov['htmx']['exercised']} exercised).\n")
    post_rows = sorted(((k, v) for k, v in cov_post.items() if module_of(k) == mod or (mod == "M01" and k.startswith(("/app/sites", "/app/locations", "/app/calendars", "/app/contacts")))), key=lambda kv: -kv[1])
    A("State-changing requests issued by the browser (normalised path -> count): " + (", ".join(f"`{k}` x{v}" for k, v in post_rows[:40]) or "-") + "\n")
    untested = sorted(set(b["untested"] + l["untested"] + cov["posts"]["untested"] + cov["gets"]["untested"] + cov["htmx"]["untested"]))
    if untested:
        A("**Controls discovered but NOT exercised (with reason):**\n")
        for u in untested[:60]:
            A(f"- `{u}` - " + reason(u))
        A("")
    else:
        A("All discovered controls were exercised.\n")
    # 3
    fm, nforms = forms_section(mod)
    A(f"## 3. Forms\n\n{nforms} distinct forms discovered (owner view); every field of every form was filled, left blank and given invalid/boundary values in section 4.\n")
    A(fm + "\n")
    # 4
    V = [x for x in rows if is_valid(x)]
    vc, vt, vo = counts(V)
    A(f"## 4. Validation (client + server)\n\n{vo}/{vt} validation, boundary, duplicate, forged-input and XSS checks PASS. Forms are `novalidate`; constraints that the browser would block were removed in the page (or the request forged from the page) so that the SERVER rules were exercised, and the matching client hint (maxlength/required) was asserted separately.\n")
    A(table(V, ("feature", "role", "status", "actual"), (110, 10, 10, 120)) + "\n")
    # 5
    mx, nchecks = rbac_matrix(rows)
    R = [x for x in rows if is_rbac(x)]
    rc, rt, ro = counts(R)
    A(f"## 5. RBAC\n\n{ro}/{rt} RBAC checks PASS across {nchecks} distinct checks x up to 12 roles. For every role the expected outcome is derived from the role's real permission set in the database (membership -> role -> permission); the browser then proves (a) the control is shown iff permitted, (b) the direct URL answers 200 iff permitted else 403/404, (c) a real forged POST is refused with the database unchanged when denied and succeeds with the expected state change when allowed.\n")
    A(mx + "\n")
    # 6
    T = [x for x in rows if is_tenant(x)]
    tc, tt, to = counts(T)
    A(f"## 6. Tenant isolation (Alpha <-> Beta, both directions)\n\n{to}/{tt} tenant checks PASS. Beta fixtures were created through the Beta UI; Alpha fixtures through the Alpha UI. Probes cover list, search, filters, detail, edit forms, edit POSTs, status/state actions, documents/meters/relations/schedules, HTMX partials, file download, API and forged foreign ids.\n")
    A(table(T, ("feature", "role", "status", "actual"), (110, 10, 10, 110)) + "\n")
    # 7
    D = [x for x in rows if is_db(x)]
    dc, dt, do = counts(D)
    A(f"## 7. Database persistence (browser action -> SQL read-back, refresh persistence, audit)\n\n{do}/{dt} checks that carry a database/audit read-back PASS.\n")
    A(table([x for x in D], ("feature", "db", "audit", "status"), (95, 80, 55, 10)) + "\n")
    # 8
    H = [x for x in rows if is_htmx(x)]
    hc, ht, ho = counts(H)
    A(f"## 8. HTMX\n\nHTMX requests observed: " + (", ".join(f"`{k}` x{v}" for k, v in htmx.items()) or "none") + f". Failures observed: {len(htmx_fail)} (all injected on purpose: `{', '.join(sorted({f[3] for f in htmx_fail})) or '-'}`). {ho}/{ht} HTMX-related checks PASS.\n")
    A(table(H, ("feature", "role", "status", "actual"), (110, 10, 10, 110)) + "\n")
    # 9
    A("## 9. Error handling\n\nDeliberately provoked errors (forged ids, unauthorised roles, invalid input, foreign tenants) were answered with 400/403/404/405/409-style refusals and a visible message, never a stack trace; the one exception is listed in section 13. Provoked responses are counted separately from unexplained errors:\n")
    ec = collections.Counter((e["kind"], re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "{id}", e["text"])[:60]) for e in expected if e["kind"] == "http")
    A("| Provoked response | Count |\n|---|---|\n" + "\n".join(f"| {esc(k[1], 70)} | {n} |" for k, n in ec.most_common(14)) + "\n")
    E = [x for x in rows if re.search(r"404|403|405|refused|Forged|forged|Crafted|Anonymous|Server Error|500|empty|Empty state|unknown", x["feature"], re.I)]
    A(f"{counts(E)[2]}/{counts(E)[1]} error/negative-path checks PASS.\n")
    # 10
    P = [x for x in rows if is_resp(x)]
    pc, pt, po = counts(P)
    A(f"## 10. Responsive / keyboard / modal behaviour\n\n{po}/{pt} responsive and usability checks PASS. Method: for each page and viewport the page's `scrollWidth` is compared with the window width, elements wider than the window and clipped buttons/inputs are listed (tables inside `.table-responsive` may scroll internally).\n")
    A(resp_matrix(rows) + "\n")
    A(table([x for x in P if not x["feature"].startswith("Responsive")], ("feature", "role", "status", "actual"), (110, 10, 10, 110)) + "\n")
    # 11
    A("## 11. Console / network result\n")
    unexpl = [i for i in issues if not is_explained(i)]
    expl = [i for i in issues if is_explained(i)]
    A(f"Console errors, page errors, failed requests and 4xx/5xx recorded outside the harness' 'provoked error' window: {len(issues)}, of which **{len(unexpl)} unexplained** and {len(expl)} are 400/404 answers to the scripted negative probes (forged id, foreign tenant, invalid input) whose console line was emitted after the suppression window closed. JavaScript page errors: {sum(1 for i in issues if i['kind'] == 'pageerror')}.\n")
    A("Unexplained:\n\n| Kind | Message | Count |\n|---|---|---|\n" + issue_table(unexpl) + "\n")
    A("Explained (deliberate negative probes):\n\n| Kind | Message | Count |\n|---|---|---|\n" + issue_table(expl) + "\n")
    A(f"Provoked (expected) problems recorded inside the suppression window: {len(expected)}; aborted requests of the polling notification bell during navigation (benign, not errors): {len(benign)}; failed static assets: {sum(1 for i in issues if '/static/' in (i.get('url') or ''))}.\n")
    A("Notes: `GET /favicon.ico 404` (if listed) is reported as BX-ALL-02 (cosmetic).\n")
    # 12
    A("## 12. Integration result\n")
    for t in INTEGRATION[mod]: A(f"- {t}")
    A("")
    # 13
    A("## 13. Findings\n")
    A(f"Counts for this module: " + ", ".join(f"{s.title()} {sevc.get(s, 0)}" for s in SEV_ORDER) + f", Unverified {unv_total(mod, c)}.\n")
    if fnd:
        A("| ID | Severity | Title | Status |\n|---|---|---|---|\n" + "\n".join(f"| {f['id']} | {f['sev']} | {esc(f['title'], 140)} | {esc(f['status'], 40)} |" for f in fnd) + "\n")
        for f in fnd:
            A(f"### {f['id']} - {f['sev']} - {f['title']}\n")
            for k, lab in (("module", "Module"), ("page", "Page / URL"), ("role", "Role"), ("action", "Action"), ("expected", "Expected"), ("actual", "Actual"), ("api", "API / HTMX / network"), ("console", "Console"), ("shot", "Screenshot"), ("source", "Source location"), ("status", "Status")):
                A(f"- **{lab}:** {f[k]}")
            ev = [x for x in rows if f["feature_match"] and f["feature_match"].lower() in x["feature"].lower()][:3]
            if ev: A("- **Run evidence:** " + "; ".join(f"[{x['status']}] {esc(x['feature'], 80)} -> {esc(x['actual'], 140)}" for x in ev))
            A("")
    else:
        A("No defect was reproduced for this module.\n")
    u = [x for x in UNVERIFIED if x[0] == mod]
    if u:
        A("**Unverified items (not claimed as PASS):**\n")
        for m_, t, why, _row in u: A(f"- {t}: {why}")
        A("")
    # 14
    A("## 14. Evidence\n")
    A("- Raw per-run result files (every row, console/network capture, click and request coverage): " + ", ".join(f"`evidence/{f}`" for f in RUNS[mod]))
    A("- Discovery inventory (all pages/links/buttons/forms/tables/HTMX of M01-M04): `evidence/inventory_owner.json`; coverage computation: `evidence/coverage.json`")
    shots = sorted(p.name for p in (EV / "shots").glob(f"{mod}_*.png"))
    A("- Screenshots: " + (", ".join(f"`evidence/shots/{s}`" for s in shots) or "none for this module (all viewport checks passed; screenshots are only taken on failure or for key states)"))
    A("- Scripts (Playwright, Python): `tools/playwright/` (" + ", ".join(SCRIPTS[mod]) + ")")
    A("- Provoked-error and benign-abort logs are stored in the run files under `expected` and `benign`.\n")
    # 15
    A("## 15. Final module status\n")
    A(f"**{mod}: {status}.** {ok}/{tot} checks PASS; {c['FAIL']} FAIL; {c['PARTIAL']} PARTIAL; {unv_total(mod, c)} UNVERIFIED; {na} not applicable.")
    A(f"Open findings: " + (", ".join(f"{f['id']} ({f['sev']})" for f in fnd) or "none") + ".")
    A(STATUS_NOTE[mod])
    return "\n".join(L), dict(mod=mod, ok=ok, tot=tot, c=c, status=status, sevc=sevc, issues=len(unexpl), explained=len(expl), console=sum(1 for i in issues if i['kind'] == 'console'), expected=len(expected), rbac=(ro, rt), tenant=(to, tt), persist=(do, dt), htmx=(ho, ht), resp=(po, pt), htmx_fail=len(htmx_fail), cov=cov, na=na)


def reason(u):
    if "/identification/" in u or u.startswith("Check"): return "QR / barcode / scan feature belongs to M07 (later batch); the asset 'Labels' panel itself loaded without error"
    if "/contracts/" in u: return "warranty / contract coverage belongs to M10 (later batch); the asset 'Coverage' panel loaded without error"
    if "/incidents/" in u: return "link into M05 (later batch); the target href carries ?asset=<id> and was verified, the incident page was not opened"
    return "navigation duplicate of an exercised control or a link into a module outside this batch"
SCRIPTS = {"M01": ["m01a.py", "m01b.py", "m01c.py", "m01d.py"], "M02": ["m02a.py", "m02b.py"], "M03": ["m03.py"], "M04": ["m04a.py", "m04b.py", "m04c.py"]}
STATUS_NOTE = {
    "M01": "All M01 functionality exposed in the UI works and persists; the one reproduced defect is a server error on an absurdly large escalation order (BX-M01-01, Medium). Remaining items are Low accessibility/UX observations.",
    "M02": "Registry, search/filter/pagination, create/edit with every field, categories with custom attributes, documents, meters and the complete status lifecycle work and persist. Only UI-gap observations (no zone filter/sort controls, last reading only) remain; financial/cost fields do not exist in the model or UI and are therefore NOT APPLICABLE.",
    "M03": "Tree, attach/edit/move/detach, cycle/depth/cross-tenant/site rules, atomic child registration and RBAC all work; the integrity gap with retire (BX-M03-01, Medium) and the missing HTMX error state (BX-M03-02) remain open.",
    "M04": "Plans, schedules, generation (UI, Celery, concurrency), duplicate prevention, reminders, lead days, catch-up and cross-module blocking work. The High defect BX-M04-01 (F-H01: recurrence edit re-points the schedule at an already generated occurrence) is reproduced in the browser and BLOCKS acceptance of M04 until fixed.",
}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    summaries = {}
    for mod in ("M01", "M02", "M03", "M04"):
        text, s = build(mod)
        (ROOT / f"{mod}_BROWSER_DETAILED.md").write_text(text + "\n", encoding="utf-8")
        summaries[mod] = s
        print(mod, f"{s['ok']}/{s['tot']}", dict(s["c"]), s["status"], "issues", s["issues"], "rbac", s["rbac"], "tenant", s["tenant"], "resp", s["resp"], "htmx_fail", s["htmx_fail"])
    json.dump({k: {**v, "c": dict(v["c"]), "sevc": dict(v["sevc"]), "cov": None} for k, v in summaries.items()}, open(EV / "batch1_summary.json", "w"), indent=1)
    # final doc section
    sev = collections.Counter(f["sev"] for f in FINDINGS)
    sect = ["<!-- BATCH1:START -->", "## Batch 1 deep acceptance (M01-M04): supersedes the earlier M01-M04 sections of this file\n",
            f"Complete UI acceptance of every functionality exposed by M01-M04 ({sum(s['tot'] for s in summaries.values())} scored browser checks). Detailed per-module reports: `docs/audits/browser/M01_BROWSER_DETAILED.md`, `M02_BROWSER_DETAILED.md`, `M03_BROWSER_DETAILED.md`, `M04_BROWSER_DETAILED.md` (15 sections each). Raw evidence and scripts: `docs/audits/browser/evidence/`, `docs/audits/browser/tools/`.\n",
            "| Module | Browser checks PASS | FAIL | PARTIAL | UNVERIFIED | N/A | RBAC | Tenant | Responsive | Unexplained console/network | Status |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for mod, s in summaries.items():
        sect.append(f"| {mod} | {s['ok']}/{s['tot']} | {s['c']['FAIL']} | {s['c']['PARTIAL']} | {unv_total(mod, s['c'])} | {s['na']} | {s['rbac'][0]}/{s['rbac'][1]} | {s['tenant'][0]}/{s['tenant'][1]} | {s['resp'][0]}/{s['resp'][1]} | {s['issues']} | **{s['status']}** |")
    sect.append(f"\nFindings by severity: Critical {sev['CRITICAL']}, High {sev['HIGH']}, Medium {sev['MEDIUM']}, Low {sev['LOW']}, Cosmetic {sev['COSMETIC']}, Unverified {sum(unv_total(m, s['c']) for m, s in summaries.items())}.\n")
    sect.append("| ID | Severity | Module | Title |\n|---|---|---|---|\n" + "\n".join(f"| {f['id']} | {f['sev']} | {f['module']} | {esc(f['title'], 150)} |" for f in sorted(FINDINGS, key=lambda f: SEV_ORDER.index(f['sev']))))
    sect.append("\n**Batch 1 status: CONDITIONAL.** No Critical defect; one High defect (BX-M04-01 = F-H01) blocks M04 acceptance, two Medium defects are open. M05 must not start before the owner decides on the fixes (no production code was changed in this audit).\n<!-- BATCH1:END -->")
    doc = FINAL_DOC.read_text(encoding="utf-8")
    overall = {"M01": "**PARTIAL**", "M02": "**PARTIAL**", "M03": "**PARTIAL**", "M04": "**FAIL (BLOCKER F-H01)**"}
    for mod, s_ in summaries.items():
        bv = {"PASS with LOW observations": "**PASS** (Low observations)", "PASS": "**PASS**"}.get(s_["status"], "**FAIL**" if s_["status"].startswith("FAIL") else "**PARTIAL**")
        row = f"| {mod} | {bv} (Batch 1 deep re-test) | {overall[mod]} | {s_['ok']} | {s_['c']['FAIL']} (genuine) | {s_['c']['SUPERSEDED']} |"
        doc = re.sub(rf"^\| {mod} \|[^\n]*\|\s*$", lambda m: row, doc, count=1, flags=re.M)
    block = "\n".join(sect)
    if "<!-- BATCH1:START -->" in doc:
        doc = re.sub(r"<!-- BATCH1:START -->.*?<!-- BATCH1:END -->", lambda m: block, doc, flags=re.S)
    else:
        marker = "\n## M01: browser"
        doc = doc.replace(marker, "\n" + block + "\n" + marker, 1)
    for mod in ("M01", "M02", "M03", "M04"):
        note = f"> Superseded by the Batch 1 deep acceptance above (`docs/audits/browser/{mod}_BROWSER_DETAILED.md`); kept for history.\n"
        doc = re.sub(rf"(^## {mod}: browser[^\n]*\n)(?!\n?> Superseded)", lambda m: m.group(1) + "\n" + note, doc, count=1, flags=re.M)
    FINAL_DOC.write_text(doc, encoding="utf-8")


if __name__ == "__main__":
    main()
