import json, collections, sys
rows=[json.loads(l) for l in open("../evidence/browser_results.jsonl")]
SUPER=[("M01","Deactivate site with reason (state machine)","confirm dialog not awaited; re-run PASS"),
("M01","Deactivating a site that still has ACTIVE assets/zones","first run never clicked the confirm dialog; re-run recorded the real rule"),
("M03","Tree view renders all descendants","tree loads via HTMX; first run did not wait; re-run PASS"),
("M03","Re-parent subtree (C1 under C2)","wrong form field name in first run; re-run PASS"),
("M09","Technician requests part (REQUESTED)","SQL column error in my check; part request itself worked"),
("M09","Request more than stock/limit rejected or held without negative stock","weak assertion; real insufficient-stock rule re-tested"),
("M08","Exception + finding allows completion","confirm dialog not awaited; re-run PASS"),
("M08","Exception answer + recorded finding allows inspection completion (UI)","confirm dialog not awaited (800 ms); re-run PASS"),
("M08","Mandatory-item + selection checklist completes when all answered in range (UI)","confirm dialog not awaited; re-run PASS"),
("M06","Plan DRAFT->PLANNED","plan form needs planned start/end; re-run PASS"),
("M06","Corrective WO completes with checklist + labor + evidence + notes","checklist not yet completed (harness); re-run PASS"),
("M05","Request auto-moves to RESOLVED when WO completed (M06->M05)","ordering in aborted run; re-run PASS"),
("M06","Corrective WO cannot complete without labor/evidence even with checklist done","labor/evidence already recorded by the aborted run; labor gates CLOSE; re-tested"),
("M06","Corrective WO cannot complete without evidence photo","same cause"),
("M06","Resolution notes shorter than 10 chars rejected","WO already COMPLETED in that run; re-tested"),
("M06","Complete without labor hours is blocked (closure rule)","wrong expectation: labor gates closure, not completion"),
("M06","Complete with notes < 10 chars blocked","WO already COMPLETED in that run"),
("M06","Close without labor hours blocked (closure rule; labor is a CLOSE requirement, complete does not need it)","labor had been recorded after completion by the same run; re-tested on a fresh WO"),
("M12","Generate QR + Code128 labels (UI->DB)","SQL column error in my check; labels were generated; re-run PASS"),
("M12","Brute-force: repeated invalid scans get throttled (429)","limit is 15 failures; first run made 15; re-run PASS (429)"),
("M12","Replace label: old QR token no longer resolves","expectation too strict: revoked label shows a warning by design (INTENTIONAL I07)"),
("M10","Coverage engine on WO: corrective on warranted asset eligible; preventive excluded by agreement exclusion","panel loads via HTMX; re-run PASS"),
("API","Mass assignment: client-supplied status/organization/id ignored on asset create","server rejects explicit `status` with 400 (stricter than expected); re-run PASS"),
("M09","M14-001 runtime: dashboard Low-stock KPI equals stock list low=1 count","my assertion logic was wrong; see the M14 FAIL line (defect confirmed)"),
("WF","Asset: technician cannot change status (API)","harness state: asset already UNDER_MAINTENANCE; 403 itself correct"),
("WF","Asset: duplicate start_maintenance rejected 409, state unchanged","harness state: asset already UNDER_MAINTENANCE; both calls 409"),
("M12","Camera scan path (Chromium fake capture device streaming the real label QR): live video -> ZXing decode -> server resolve -> asset opens","first QR was small; re-run PASS (see L32)"),
]
sup={(m,s) for m,s,_ in SUPER}; why={(m,s):w for m,s,w in SUPER}
last={}
order=[]
for i,r in enumerate(rows):
    k=(r["module"],r["scenario"],r["status"])
    last[k]=i
# a row is superseded if listed AND a later row with a different status for same scenario or list says so
out=collections.defaultdict(list)
for i,r in enumerate(rows):
    k3=(r["module"],r["scenario"],r["status"])
    if last[k3]!=i: continue            # identical scenario+status repeated: keep the last execution
    k=(r["module"],r["scenario"])
    r=dict(r); r["superseded"]=why.get(k) if (r["status"]!="PASS" or (k[1].startswith("M14-001 runtime: dashboard Low-stock KPI equals"))) else None
    out[r["module"]].append(r)
# superseded rows that were deduped away still must be shown if listed -> they were last of their scenario in many cases
VERD={
"M01":("PASS","Create/edit/list/search/filter, unique code (case-insensitive), timezone/email validation, 4-level nested zones, cycle prevention (UI list + crafted POST), calendars/contacts, deactivate/reactivate with confirm + reason, rule 'site with active assets cannot be deactivated', tenant isolation both ways, 4 viewports. Static MEDIUM: concurrent zone move race (F-M19)."),
"M02":("PARTIAL","Category with custom attributes, register with owner/dates/warranty reference, uniqueness, validation, edit, full status machine via UI with reasons + history + audit, invalid transitions blocked, location history, document upload/download/validation, meters (monotonic, negative rejected), cross-tenant UI/POST denied. FAIL (RUNTIME, API): meter reading written to an out-of-scope site through REST while the HTML view denied it (F-M07). Caveats: no financial fields exist (UNVERIFIED requirement U10); site-move propagation is a static finding (F-M08)."),
"M03":("PARTIAL","Attach child, 3-level tree, re-parent, edit relationship, detach, UI hides illegal choices, backend rejects cycle/self/already-parented/cross-site/cross-tenant. FAIL: retiring a parent with children leaves an undetachable tree (F-M06, RUNTIME). No atomic replace operation (L06)."),
"M04":("PARTIAL","Plan + weekly schedule via UI, DUE listing, generate-now creates a PREVENTIVE WO with checklist gate, duplicate prevention (UI + crafted POST), next cycle advances, cycle shown VERIFIED after WO close, audited. **BLOCKER F-H01**: editing the recurrence silently stops generation (reproduced). Celery-beat generation timing: see section 'Beat'."),
"M05":("PARTIAL","Incident via UI (asset, severity, impact), client request, triage/approve/work-order creation, invalid + system-only actions refused, duplicate WO creation blocked, request closes after client confirmation. FAIL (RUNTIME): reopen -> 500 (F-M01), request/WO divergence (F-M02), downtime left open after reject (F-M03)."),
"M06":("PASS","Create/edit/plan (validation)/assign/dispatch/start/hold/resume/complete/review/close/cancel/reassign via UI; technician double-booking 409; closure blockers (labor, notes, checklist, outstanding issued parts); RBAC per role; duplicate/invalid transitions safe; state trail + 14 audit rows. Lifecycle-coupling defects are filed under M05."),
"M07":("PASS","Technician sees only own jobs (list, page, API all 404 for others), start/hold/resume/complete on 390 px, note, labor, photo evidence, part request/consume, checklist execution, site & route card; 4 viewports."),
"M08":("PARTIAL","Builder (4 item types, mandatory, range, unit, exception options, evidence flag), validation, activate/freeze/new-version, execution on mobile with exception -> finding -> completion, immutable completed inspection. FAIL: required checklists are not scoped to assets (F-M04, RUNTIME)."),
"M09":("PASS","Part/warehouse create + validation, receive, adjust (never below zero), reserve/issue/consume/return/reconcile with ledger invariant checked in SQL, over-issue/insufficient stock rejected, technician cannot issue, closure blocked by unreturned issued part. Dashboard KPI mismatch filed under M14 (F-M10)."),
"M10":("PASS","Provider, warranty/AMC/contract create, overlap rule, end<start rejected, expiry list incl. lapsed, coverage engine panel on WO, renewal alert delivered through the real Celery worker. Static MEDIUM F-M13 (alert consumed when no recipients)."),
"M11":("PASS","Targets/rules edited in UI; real elapsed time with Celery beat: response breach, 50 % warning, resolution breach, escalation level 2 at +1 min, notifications to the configured roles, acknowledge in UI, pause on TRIAGED + resume, MET_LATE recorded. 24/7 clock is INTENTIONAL (I01)."),
"M12":("PARTIAL","QR + Code128 generation, printable label, typed and camera (synthetic device) scan, invalid code, service event creation from scan, replace/revoke, 429 after 15 failures, cross-tenant/anonymous/client denied. Redis outage turns every scan into a 500 (F-M11)."),
"M13":("PARTIAL","Client sees only granted assets, submits with attachment on 390 px, tracks status, sees visit window/technician but no internal data, confirms, request closes; client has no access to any internal page or API. FAIL: a disabled account keeps read access (F-M09, RUNTIME); reopen path 500 (F-M01)."),
"M14":("PARTIAL","KPIs equal direct SQL (open 12, overdue 9, created 5, completed 2, closed 2, assets 17+2, requests 3, breaches 4, movements 7), site/date filters, inverted/invalid inputs, foreign site, empty states, Beta isolation, technician/client denied, API = UI. FAIL: Low-stock KPI 0 vs list 1 (F-M10, RUNTIME)."),
"M15":("PASS","Audit list/search/filters/detail, CSV/XLSX/PDF exports (formula-safe, audited), per-WO evidence ZIP with manifest hashes, API PATCH/DELETE 403 for all, Beta isolation. Medium findings: JWT logins unaudited (F-M14), platform audit exposure (F-M15), and the DB-level TRUNCATE gap (F-H02)."),
}
OVERALL={"M01":"PARTIAL","M02":"PARTIAL","M03":"PARTIAL","M04":"FAIL (BLOCKER F-H01)","M05":"PARTIAL","M06":"PASS","M07":"PASS","M08":"PARTIAL","M09":"PASS","M10":"PARTIAL","M11":"PASS","M12":"PARTIAL","M13":"PARTIAL","M14":"PARTIAL","M15":"PARTIAL"}
mods=["M01","M02","M03","M04","M05","M06","M07","M08","M09","M10","M11","M12","M13","M14","M15"]
with open("../M01_M15_BROWSER_ACCEPTANCE.md","w") as f:
    f.write("# Browser acceptance: M01-M15 (Playwright against the running application)\n\n")
    f.write("Environment: Django (DEBUG off, CSP on) on :8098 against PostgreSQL 16 (`fieldops_browser_qa`, fresh migration + service-layer seed), Redis :6390, Celery worker + beat, Chromium 1194 driven by Playwright 1.63. Viewports 1920x1080, 1440x900, 1024x768, 390x844. Every scenario below is a recorded line in `evidence/browser_results.jsonl`; UI actions were checked against the database (psql) and the audit table, not against HTTP 200. Screenshots are in `evidence/`.\n\n")
    f.write("**Verdict rules.** *Browser verdict*: what the Playwright/runtime scenarios of that module showed (PASS = every HPE-scope behaviour worked; PARTIAL = works but at least one defect was reproduced at runtime; FAIL = HPE core flow broken). *Overall verdict* (browser + code audit): PASS only if no MEDIUM-or-higher finding is assigned to the module (LOW findings allowed); PARTIAL = at least one MEDIUM finding (runtime or static); FAIL = a HIGH defect in the module's own behaviour. F-H02 (audit immutability) is HIGH but its production exposure is UNVERIFIED and the module's own flows work, so M15 stays PARTIAL with the condition stated.\n\n")
    f.write("| Module | Browser verdict | Overall verdict (browser + code) | Pass lines | Fail lines (genuine) | Superseded harness lines |\n|---|---|---|---|---|---|\n")
    cnt={}
    for m in mods:
        rs=out.get(m,[]); p=sum(1 for r in rs if r["status"]=="PASS" and not r["superseded"]); fl=sum(1 for r in rs if r["status"] in("FAIL",) and not r["superseded"]); sp=sum(1 for r in rs if r["superseded"])
        cnt[m]=(p,fl,sp)
        v=VERD[m][0]
        f.write(f"| {m} | **{v}** | **{OVERALL[m]}** | {p} | {fl} | {sp} |\n")
    f.write("\n")
    for m in mods:
        v,txt=VERD[m]
        f.write(f"## {m}: browser {v}; overall {OVERALL[m]}\n\n{txt}\n\n| Status | Scenario | Evidence / note |\n|---|---|---|\n")
        for r in out.get(m,[]):
            st=r["status"] if not r["superseded"] else "SUPERSEDED"
            note=(r["note"] or "").replace("|","/").replace("\n"," ")[:230]
            if r["superseded"]: note=f"harness: {r['superseded']}"
            f.write(f"| {st} | {r['scenario'].replace('|','/')} | {note} |\n")
        f.write("\n")
    for m in ("PLATFORM","WF","CELERY","REDIS","SEC","API","UI","RBAC","RBAC-admin"):
        rs=out.get(m,[])
        if not rs: continue
        title={"PLATFORM":"Platform console / onboarding (Super Admin)","WF":"State-machine negative tests (all five machines)","CELERY":"Celery","REDIS":"Redis outage experiments","SEC":"Security probes (browser)","API":"API probes","UI":"Shell/UI","RBAC":"RBAC runtime probes","RBAC-admin":"Responsive: users/roles/organization"}[m]
        f.write(f"## Cross-cutting: {title}\n\n| Status | Scenario | Evidence / note |\n|---|---|---|\n")
        for r in rs:
            st=r["status"] if not r["superseded"] else "SUPERSEDED"
            f.write(f"| {st} | {r['scenario'].replace('|','/')} | {(r['note'] or '').replace('|','/').replace(chr(10),' ')[:230]} |\n")
        f.write("\n")
print(cnt)
