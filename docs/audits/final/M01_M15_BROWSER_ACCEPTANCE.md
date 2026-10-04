# Browser acceptance: M01-M15 (Playwright against the running application)

Environment: Django (DEBUG off, CSP on) on :8098 against PostgreSQL 16 (`fieldops_browser_qa`, fresh migration + service-layer seed), Redis :6390, Celery worker + beat, Chromium 1194 driven by Playwright 1.63. Viewports 1920x1080, 1440x900, 1024x768, 390x844. Every scenario below is a recorded line in `evidence/browser_results.jsonl`; UI actions were checked against the database (psql) and the audit table, not against HTTP 200. Screenshots are in `evidence/`.

**Verdict rules.** *Browser verdict*: what the Playwright/runtime scenarios of that module showed (PASS = every HPE-scope behaviour worked; PARTIAL = works but at least one defect was reproduced at runtime; FAIL = HPE core flow broken). *Overall verdict* (browser + code audit): PASS only if no MEDIUM-or-higher finding is assigned to the module (LOW findings allowed); PARTIAL = at least one MEDIUM finding (runtime or static); FAIL = a HIGH defect in the module's own behaviour. F-H02 (audit immutability) is HIGH but its production exposure is UNVERIFIED and the module's own flows work, so M15 stays PARTIAL with the condition stated.

| Module | Browser verdict | Overall verdict (browser + code) | Pass lines | Fail lines (genuine) | Superseded harness lines |
|---|---|---|---|---|---|
| M01 | **PASS** | **PARTIAL** | 39 | 0 | 1 |
| M02 | **PARTIAL** | **PARTIAL** | 46 | 1 | 0 |
| M03 | **PARTIAL** | **PARTIAL** | 22 | 2 | 2 |
| M04 | **PARTIAL** | **FAIL (BLOCKER F-H01)** | 16 | 1 | 0 |
| M05 | **PARTIAL** | **PARTIAL** | 13 | 4 | 1 |
| M06 | **PASS** | **PASS** | 39 | 0 | 8 |
| M07 | **PASS** | **PASS** | 15 | 0 | 0 |
| M08 | **PARTIAL** | **PARTIAL** | 19 | 0 | 3 |
| M09 | **PASS** | **PASS** | 25 | 0 | 2 |
| M10 | **PASS** | **PARTIAL** | 11 | 0 | 1 |
| M11 | **PASS** | **PASS** | 9 | 0 | 0 |
| M12 | **PARTIAL** | **PARTIAL** | 22 | 0 | 4 |
| M13 | **PARTIAL** | **PARTIAL** | 11 | 1 | 0 |
| M14 | **PARTIAL** | **PARTIAL** | 15 | 1 | 0 |
| M15 | **PASS** | **PARTIAL** | 13 | 0 | 0 |

## M01: browser PASS; overall PARTIAL

Create/edit/list/search/filter, unique code (case-insensitive), timezone/email validation, 4-level nested zones, cycle prevention (UI list + crafted POST), calendars/contacts, deactivate/reactivate with confirm + reason, rule 'site with active assets cannot be deactivated', tenant isolation both ways, 4 viewports. Static MEDIUM: concurrent zone move race (F-M19).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Duplicate site code rejected | A site with this code already exists. |
| PASS | Duplicate code: DB has exactly 1 row | 1 |
| PASS | XSS payload in site name is escaped on render | stored name rendered escaped |
| PASS | Edit site persists | Audit Plant One (edited)/Madurai |
| PASS | Create site via form | url=http://127.0.0.1:8098/app/sites/67ba8ac9-0c57-4b4f-9a6f-53ab902baa77/ id=67ba8ac9-0c57-4b4f-9a6f-53ab902baa77 |
| PASS | Site owned by active org (organization_id) | t |
| PASS | Duplicate site code rejected, 1 DB row | count=1 msg=A site with this code already exists. |
| PASS | Case-insensitive duplicate code rejected | count=1 msg=A site with this code already exists. |
| PASS | Invalid timezone rejected | count=0 msg=Unknown timezone 'Mars/Olympus'. |
| PASS | Bad contact email rejected | count=0 msg=Enter a valid email address. |
| PASS | XSS payload in site name rendered escaped |  |
| PASS | Edit site persists to DB | Audit Plant One (edited)/Madurai |
| PASS | Create+edit audited (site.*) | site.created,site.updated |
| PASS | 4-level nested zones persisted (UI->DB) | Block A>-;Floor 1>Block A;Room 101>Floor 1;Service Area N>Room 101 |
| PASS | Locations tab renders hierarchy |  |
| PASS | Zone edit parent dropdown excludes self and descendants (cycle prevention in UI) | ['(top level of the site)'] |
| PASS | Backend rejects zone cycle on crafted POST | parent='' msg=Select a valid choice. That choice is not one of the available choices. |
| PASS | Create operating calendar | Calendar created. |
| PASS | Calendar with end<start rejected | End time must be after start time. |
| PASS | Add site contact | Contact added. |
| SUPERSEDED | Deactivate site with reason (state machine) | harness: confirm dialog not awaited; re-run PASS |
| PASS | Reactivate site | ACTIVE |
| PASS | Deactivating a site that still has ACTIVE assets/zones | status after=ACTIVE msg= (business rule: see note) |
| PASS | Search filter |  |
| PASS | Status filter |  |
| PASS | Console/network on M01 flow | console=[('error', 'Failed to load resource: the server responded with a status of 400 (Bad Request)'), ('error', 'Failed to load resource: the server responded with a status of 400 (Bad Request)'), ('error', 'Failed to load resou |
| PASS | BETA owner opening ALPHA site URL | 404 |
| PASS | BETA site list excludes ALPHA sites |  |
| PASS | BETA owner opening ALPHA site edit URL | 404 |
| PASS | ALPHA owner opening BETA site URL | 404; beta sees own=200 |
| PASS | Deactivate site with reason + confirm dialog (UI->DB->audit) | INACTIVE site.created,site.updated,site.deactivated |
| PASS | Cannot add location to INACTIVE site | This site is inactive. |
| PASS | Reactivate site (UI->DB) | ACTIVE site.created,site.updated,site.deactivated,site.reactivated |
| PASS | Deactivate site that has ACTIVE assets (rule probe) | HYD-1 status after=ACTIVE; msg=Site has 5 active asset(s); retire, dispose or move them first.  (HPE/workflow rule on this not stated in digest; behaviour recorded) |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 5 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 5 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 5 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 5 pages | [] |
| PASS | Site-scoped role (planner limited to BLR-1): site list shows only BLR-1 | Sites & locations / Physical sites, their buildings, zones and service areas. / All statuses / Active / Inactive / Filter / CODE	NAME	CITY	LOCATIONS	ACTIVE ASSETS	STATUS / BLR-1	Bangalore Service Depot	Bangalore	1	 |
| PASS | Site-scoped role: direct URL of an out-of-scope site -> 404 | 404 |

## M02: browser PARTIAL; overall PARTIAL

Category with custom attributes, register with owner/dates/warranty reference, uniqueness, validation, edit, full status machine via UI with reasons + history + audit, invalid transitions blocked, location history, document upload/download/validation, meters (monotonic, negative rejected), cross-tenant UI/POST denied. FAIL (RUNTIME, API): meter reading written to an out-of-scope site through REST while the HTML view denied it (F-M07). Caveats: no financial fields exist (UNVERIFIED requirement U10); site-move propagation is a static finding (F-M08).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Create asset category with custom attributes | Category created. |
| PASS | Register asset (UI->DB) with attrs, owner, dates | Asset AST-10557 registered. |
| PASS | Initial status ACTIVE + custom attributes stored | ACTIVE/415/2025-01-10 |
| PASS | Status history row created on register |  |
| PASS | Duplicate asset tag (case-insens) rejected | count=1 An asset with this tag already exists. |
| PASS | Duplicate serial per manufacturer rejected | count=1 An asset with this manufacturer and serial number already exists. |
| PASS | Commission date before purchase date rejected | count=0 Commissioning date cannot be before the purchase date. |
| PASS | Required custom attribute enforced | count=0 This field is required. |
| PASS | Zone from different site rejected (crafted POST) | 400 |
| PASS | Edit asset persists | Asset saved. |
| PASS | Detail shows identity, location, owner, lifecycle, coverage | Assets AST-10557 Audit Asset EDITED Active AST-10557 · AuditCat10557 · HYD-1 · Building A Report a p |
| PASS | Asset status mark_out_of_service via UI -> OUT_OF_SERVICE | OUT_OF_SERVICE |
| PASS | Asset status return_to_service via UI -> ACTIVE | ACTIVE |
| PASS | Asset status start_maintenance via UI -> UNDER_MAINTENANCE | UNDER_MAINTENANCE |
| PASS | Asset status complete_maintenance via UI -> ACTIVE | ACTIVE |
| PASS | Invalid transition ACTIVE->retire blocked server-side | http=302 status=ACTIVE |
| PASS | Transition without reason rejected | 302 |
| PASS | Unknown action rejected | 302 |
| PASS | Status history has one row per change (1+5) | 6 |
| PASS | History tab shows status changes with actor/reason |  |
| PASS | Status changes audited | asset.created,asset.updated,asset.status_changed,asset.status_changed,asset.status_changed,asset.status_changed,asset.status_changed |
| PASS | Location move recorded in location history | 2 |
| PASS | Upload asset document | Document uploaded. |
| PASS | Executable upload rejected | File type '.exe' is not allowed. |
| PASS | Fake PDF (bad magic bytes) rejected | File content does not match its extension. |
| PASS | Download document returns uploaded bytes | audit_doc.txt |
| PASS | Create meter |  |
| PASS | Meter readings: 100,150 stored; decreasing 120 rejected | 100.000,150.000 |
| PASS | Negative reading rejected |  |
| PASS | BETA owner -> ALPHA asset detail | 404 |
| PASS | BETA owner -> ALPHA asset edit | 404 |
| PASS | BETA owner -> ALPHA asset tree | 404 |
| PASS | BETA cross-tenant status POST | 404 |
| PASS | BETA cross-tenant meter reading POST | 404 |
| PASS | BETA asset list excludes ALPHA assets |  |
| PASS | ALPHA owner -> BETA asset | 404 |
| PASS | Asset list search |  |
| PASS | Asset list filters present | ['q', 'site', 'category', 'status'] |
| PASS | M02 console/network (5xx / JS exceptions) | [][] |
| PASS | Asset returned to ACTIVE after WO closed (coupling) | ACTIVE |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 7 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 7 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 7 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 7 pages | [] |
| FAIL | F-M07 RUNTIME: user with meter-record permission scoped to BLR-1 only (org-wide read) records a reading on a HYD-1 asset: HTML view denied, REST API ACCEPTED | API=201 (row stored=1); HTML=403 (row stored=0) |
| PASS | Site-scoped role: out-of-scope asset URL -> 404 | 404 |
| PASS | Site-scoped role: asset API returns only in-scope assets | 3 rows sites=['BLR-1'] |

## M03: browser PARTIAL; overall PARTIAL

Attach child, 3-level tree, re-parent, edit relationship, detach, UI hides illegal choices, backend rejects cycle/self/already-parented/cross-site/cross-tenant. FAIL: retiring a parent with children leaves an undetachable tree (F-M06, RUNTIME). No atomic replace operation (L06).

| Status | Scenario | Evidence / note |
|---|---|---|
| SUPERSEDED | Tree view renders all descendants | harness: tree loads via HTMX; first run did not wait; re-run PASS |
| SUPERSEDED | Re-parent subtree (C1 under C2) | harness: wrong form field name in first run; re-run PASS |
| PASS | Create 4 assets for hierarchy | {'P': '3ab93eb0-e814-4a12-9600-25f726402241', 'C1': '6c8807a2-5b80-439a-8a38-25b628ebd7ff', 'C2': '375d14d3-9dcf-41d1-82f2-fb35777b7d97', 'G': '70914de8-b051-4eca-b694-b6709d4a67de'} |
| PASS | Attach child C1 to parent P (UI) |  |
| PASS | 3-level tree persisted (P>C1>G, P>C2) | 3 |
| PASS | Tree view renders all descendants | Assets H3P-10619 Hier P Active H3P-10619 · Pump · HYD-1 Report a problem Edit Next: Start maintenance Overview Documents Meters History Hierarchy Cove |
| PASS | UI prevents cycle: ancestor not offered as child | offered=None |
| PASS | Cycle via crafted POST (P under G) rejected by backend | http=302 rows_as_child=0 |
| PASS | Self-parent via crafted POST rejected by backend | http=302 rows_as_child=0 |
| PASS | Re-add already-parented child (C1 under C2) rejected by backend | http=302 rows_as_child=1 |
| PASS | Child from a different site rejected | 302 |
| PASS | Cross-tenant child rejected | 302 |
| PASS | Edit relationship persists | 7PN-EDIT |
| PASS | Re-parent subtree (C1 under C2) | http=302 parent=375d14d3-9dcf-41d1-82f2-fb35777b7d97 |
| PASS | Re-parent cycle (C2 under its own descendant G) rejected | 302 |
| PASS | Detach component | 302 |
| PASS | Hierarchy changes audited | asset.component_added,asset.component_moved,asset.component_removed,asset.component_updated |
| FAIL | PROBE: retire a parent that still has live children | parent status=RETIRED remaining links=1 (static finding M03-1: stuck hierarchy) |
| FAIL | PROBE: children of retired parent can still be detached | http=302 |
| PASS | BETA cross-tenant hierarchy write | 404 |
| PASS | BETA reads ALPHA hierarchy tree | 404 |
| PASS | M03 console/network (5xx/JS) | [] |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 1 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 1 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 1 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 1 pages | [] |

## M04: browser PARTIAL; overall FAIL (BLOCKER F-H01)

Plan + weekly schedule via UI, DUE listing, generate-now creates a PREVENTIVE WO with checklist gate, duplicate prevention (UI + crafted POST), next cycle advances, cycle shown VERIFIED after WO close, audited. **BLOCKER F-H01**: editing the recurrence silently stops generation (reproduced). Celery-beat generation timing: see section 'Beat'.

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Planner creates PM plan (UI->DB) | Plan Pump quarterly 10651 created. Add a schedule so it generates work. |
| PASS | Create weekly schedule | Schedule created: every 1 week. 1/2026-10-10 |
| PASS | Due & upcoming lists the new schedule as DUE | Due & upcoming / Enabled schedules, soonest first. DUE = an occurrence is due now (the scheduler generates it; you can also generate it here). / All states / Due / Scheduled / All sites / AUD-1 / AUD-10342 / BLR-1 / HY |
| PASS | Generate now creates PM work order (PREVENTIVE, HIGH, source=PM) | cycles=1 wo=WO-000001/PLANNED/PREVENTIVE/HIGH/PREVENTIVE_MAINTENANCE msg=Work order WO-000001 generated. |
| PASS | Duplicate prevention: second Generate-now creates no 2nd cycle/WO | The previous cycle's work order is still open: finish it before generating the next occurrence early. |
| PASS | Crafted repeat generate POST creates no duplicate | 302 |
| PASS | Next cycle advanced after generation | 2/2026-10-17 |
| PASS | PM WO carries required checklist (blocker) |  |
| PASS | Schedule/cycle generation audited | maintenance.cycle_generated,maintenance.plan_created,maintenance.schedule_created |
| PASS | PM history shows cycle as VERIFIED after WO CLOSED | PM history / Every generated cycle with its work order. PM state follows the work order: generated, assigned, completed, verified (closed). / All plans / BUGPROBE weekly->biweekly (HVAC-001) / GEN-001 500-hou |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 5 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 5 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 5 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 5 pages | [] |
| PASS | Celery beat (fan_out_maintenance, 15 min) generated the due PM work order by itself (trigger=scheduler, PREVENTIVE, source PM) for a DAILY schedule starting today; schedule advanced to next day | WO-000025 created 11:34:25 within one beat tick of the schedule becoming due; next due 2026-10-05 |
| PASS | Duplicate execution: two extra fan_out_maintenance runs create no second cycle (still 1 cycle) | idempotent by UNIQUE(schedule,sequence) |
| FAIL | F-H01 reproduced via real service layer: after weekly->biweekly edit the scheduler produced 1 WO in 10 weeks (expected ~5), no error shown | tools/m04_edit_bug.py; sequences 1-8 existed; new k'=5 collided; last_error empty |

## M05: browser PARTIAL; overall PARTIAL

Incident via UI (asset, severity, impact), client request, triage/approve/work-order creation, invalid + system-only actions refused, duplicate WO creation blocked, request closes after client confirmation. FAIL (RUNTIME): reopen -> 500 (F-M01), request/WO divergence (F-M02), downtime left open after reject (F-M03).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Create HIGH incident via UI (asset-linked, severity, impact) | http://127.0.0.1:8098/app/incidents/0ae4f922-02ea-4169-8112-893c569af15e/ |
| PASS | Triage NEW->TRIAGED | TRIAGED |
| PASS | Approve TRIAGED->APPROVED | APPROVED |
| PASS | Invalid transition APPROVED->close rejected | APPROVED |
| PASS | System-only action not callable by user | 302 APPROVED |
| PASS | Planner creates work order from approved request (M05->M06) | WORK_ORDER_CREATED wo=d30c67cc-8bff-4450-a0c4-1e3cc06d4936 Work order WO-000011 created. |
| PASS | Duplicate create-work-order does not create 2nd live WO | 302 |
| SUPERSEDED | Request auto-moves to RESOLVED when WO completed (M06->M05) | harness: ordering in aborted run; re-run PASS |
| PASS | Request auto-moves to RESOLVED when WO completed (M06->M05) | RESOLVED |
| PASS | Service manager closes request (CONFIRMED->CLOSED) | CLOSED |
| FAIL | M05-01 runtime: reopen after WO COMPLETED then create replacement WO | status=500 Server error. Please quote the X-Request-ID header when reporting this.; request=APPROVED; old WO=COMPLETED |
| FAIL | M05-03 runtime: supervisor rejects review after client already CONFIRMED -> request/WO divergence | WO=IN_PROGRESS request=CONFIRMED |
| FAIL | M05-03 runtime: request can be CLOSED while its WO is back IN_PROGRESS (rework) | close http=200 request=CLOSED WO=IN_PROGRESS |
| FAIL | M05-02 runtime: REJECTED request leaves its downtime record OPEN (inflates downtime KPIs) | 2026-10-04 09:05:12.8881+00/OPEN |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 4 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 4 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 4 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 4 pages | [] |

## M06: browser PASS; overall PASS

Create/edit/plan (validation)/assign/dispatch/start/hold/resume/complete/review/close/cancel/reassign via UI; technician double-booking 409; closure blockers (labor, notes, checklist, outstanding issued parts); RBAC per role; duplicate/invalid transitions safe; state trail + 14 audit rows. Lifecycle-coupling defects are filed under M05.

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Planner assigns technician (PLANNED->ASSIGNED) | Work order updated. |
| PASS | Planner dispatches (ASSIGNED->DISPATCHED) | DISPATCHED |
| PASS | Technician records labor 2.5h | Time recorded. |
| PASS | Labor: Zero hours rejected | 302 |
| PASS | Labor: Negative hours rejected | 302 |
| PASS | Labor: 25 hours/day rejected | 302 |
| PASS | Complete IN_PROGRESS->COMPLETED (UI) with notes, labor, checklist | COMPLETED Work order updated. |
| PASS | RBAC: technician cannot review/close (crafted POST) | COMPLETED |
| PASS | RBAC: planner cannot start review | 403 COMPLETED |
| PASS | Supervisor starts review COMPLETED->SUPERVISOR_REVIEW | SUPERVISOR_REVIEW |
| PASS | Close blocked while issued part not reconciled / open request line | SUPERVISOR_REVIEW The work order cannot be closed yet: 1.000 x BRG-6205 issued but not consumed or returned. // Cannot be closed yet: 1.000 x BRG-6205 issued but not consumed or returned. |
| PASS | Supervisor closes WO (SUPERVISOR_REVIEW->CLOSED) | CLOSED Work order updated. // This work order is closed and read-only. |
| PASS | WO event history (state trail) | DRAFT>PLANNED>ASSIGNED>DISPATCHED>IN_PROGRESS>ON_HOLD>IN_PROGRESS>COMPLETED>SUPERVISOR_REVIEW>CLOSED |
| PASS | WO transitions audited | 14 audit rows for the WO |
| PASS | Invalid transition from CLOSED rejected | CLOSED |
| PASS | Duplicate close rejected (409/safe) | 302 |
| SUPERSEDED | Plan DRAFT->PLANNED | harness: plan form needs planned start/end; re-run PASS |
| PASS | Plan with end before start rejected | DRAFT The planned end cannot be before the planned start. |
| PASS | Plan DRAFT->PLANNED | PLANNED Work order updated. |
| PASS | Assign technician (->ASSIGNED) | ASSIGNED |
| PASS | tech1 cannot open full WO page of unassigned order | 404 |
| PASS | API: tech1 GET other tech's WO | 404 |
| PASS | Dispatch (->DISPATCHED) | DISPATCHED |
| PASS | Corrective WO cannot complete without evidence (and labor) | 302 IN_PROGRESS |
| SUPERSEDED | Corrective WO completes with checklist + labor + evidence + notes | harness: checklist not yet completed (harness); re-run PASS |
| SUPERSEDED | Corrective WO cannot complete without labor/evidence even with checklist done | harness: labor/evidence already recorded by the aborted run; labor gates CLOSE; re-tested |
| SUPERSEDED | Corrective WO cannot complete without evidence photo | harness: same cause |
| SUPERSEDED | Resolution notes shorter than 10 chars rejected | harness: WO already COMPLETED in that run; re-tested |
| INFO | NOTE: previous 3 negative-closure FAILs are harness-ordering artifacts (labor+evidence had already been recorded by the earlier aborted run); re-tested on fresh WO later |  |
| PASS | Supervisor start review | SUPERVISOR_REVIEW |
| PASS | Supervisor closes WO after client confirmation | CLOSED |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 5 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 5 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 5 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 5 pages | [] |
| PASS | Edit draft WO (title/priority) persists | Saved. |
| PASS | Technician double-booking blocked (409 technician_conflict) when windows overlap | tech1 assign refused: 'already committed to WO-000020 in this time window' |
| PASS | Reassign dispatched WO via UI (reason required) persisted | ops@alpha.qa.test Technician changed. |
| SUPERSEDED | Complete without labor hours is blocked (closure rule) | harness: wrong expectation: labor gates closure, not completion |
| SUPERSEDED | Complete with notes < 10 chars blocked | harness: WO already COMPLETED in that run |
| PASS | Complete with labor + notes succeeds (OTHER type) | COMPLETED |
| PASS | Cancel draft WO with reason | CANCELLED |
| PASS | CANCELLED WO is terminal (plan rejected) |  |
| SUPERSEDED | Close without labor hours blocked (closure rule; labor is a CLOSE requirement, complete does not need it) | harness: labor had been recorded after completion by the same run; re-tested on a fresh WO |
| INFO | NOTE: earlier 'complete without labor blocked' FAIL lines are a wrong expectation — labor is enforced at CLOSE |  |
| PASS | Complete WITHOUT labor: allowed (labor only gates closure) | COMPLETED |
| PASS | CLOSE without labor hours blocked with clear message | 409 {'error': {'code': 'closure_blocked', 'message': 'The work order cannot be closed yet: No labor / time has been recorded.', 'details': {'blockers': ['No labor / time has been recorded.']}, 'request_id |
| PASS | Site-scoped role: creating a WO for an out-of-scope asset refused | 404 |
| PASS | Site-scoped role: work-order API shows no out-of-scope WOs | 1 rows |

## M07: browser PASS; overall PASS

Technician sees only own jobs (list, page, API all 404 for others), start/hold/resume/complete on 390 px, note, labor, photo evidence, part request/consume, checklist execution, site & route card; 4 viewports.

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Technician starts work (mobile 390px) DISPATCHED->IN_PROGRESS | IN_PROGRESS |
| PASS | Asset status coupling: asset UNDER_MAINTENANCE on WO start | UNDER_MAINTENANCE |
| PASS | Complete blocked while required checklist not started (crafted POST) | 302 |
| PASS | Hold with reason IN_PROGRESS->ON_HOLD | Work order updated. // On hold: Waiting for access permit |
| PASS | Resume ON_HOLD->IN_PROGRESS | IN_PROGRESS |
| PASS | Technician saves work note | Note saved. |
| PASS | Technician uploads photo evidence | Evidence uploaded. |
| PASS | Technician sees only own work: tech1 cannot open tech2's job | 404 |
| PASS | My Jobs list excludes other technicians' orders |  |
| PASS | tech1 cannot start tech2's job (crafted POST) | 404 ASSIGNED |
| PASS | Tech2 starts (IN_PROGRESS) | IN_PROGRESS |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 3 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 3 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 3 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 3 pages | [] |

## M08: browser PARTIAL; overall PARTIAL

Builder (4 item types, mandatory, range, unit, exception options, evidence flag), validation, activate/freeze/new-version, execution on mobile with exception -> finding -> completion, immutable completed inspection. FAIL: required checklists are not scoped to assets (F-M04, RUNTIME).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Out-of-range numeric (30 not in 50-100) cannot complete without finding | IN_PROGRESS / Still needed to complete: Question 1 is required: Oil level checked Question 2 is required: Coolant level (%) // * // * |
| PASS | Record finding against checklist item | Finding recorded. // Still needed to complete: Question 1 is required: Oil level checked Question 2  |
| SUPERSEDED | Exception + finding allows completion | harness: confirm dialog not awaited; re-run PASS |
| SUPERSEDED | Exception answer + recorded finding allows inspection completion (UI) | harness: confirm dialog not awaited (800 ms); re-run PASS |
| PASS | Exception answer + recorded finding allows inspection completion (UI, mobile; confirm dialog) | COMPLETED |
| PASS | Completed inspection immutable (crafted save) | 302 |
| SUPERSEDED | Mandatory-item + selection checklist completes when all answered in range (UI) | harness: confirm dialog not awaited; re-run PASS |
| PASS | Corrective checklist (boolean/numeric/selection) completed in UI | inspection COMPLETED (earlier FAIL entries were harness timing: confirm dialog not awaited) |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 3 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 3 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 3 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 3 pages | [] |
| PASS | Create checklist template (draft, required, work type) | http://127.0.0.1:8098/app/checklists/8a56547d-77ff-4654-8e3d-cf14689b2d06/ |
| PASS | Cannot activate a template with no questions (UI button disabled + crafted POST rejected) | 302 |
| PASS | Numeric min>max rejected | The maximum cannot be below the minimum. |
| PASS | Selection item without options rejected | A selection item needs at least two options. |
| PASS | Add 4 question types with mandatory, range, unit, exception options, evidence flag | 4 |
| PASS | Activate template with questions | Checklist updated. // This version is frozen so that 0 past inspections stay understandable. Create  |
| PASS | Active template is frozen (no edit UI) | no add form (template not draft) |
| PASS | Frozen template: crafted POST add item rejected | 302 |
| PASS | New version creates DRAFT v2 copy; v1 stays ACTIVE until v2 activated | 1:ACTIVE,2:DRAFT |
| PASS | BETA opening ALPHA checklist | 404 |

## M09: browser PASS; overall PASS

Part/warehouse create + validation, receive, adjust (never below zero), reserve/issue/consume/return/reconcile with ledger invariant checked in SQL, over-issue/insufficient stock rejected, technician cannot issue, closure blocked by unreturned issued part. Dashboard KPI mismatch filed under M14 (F-M10).

| Status | Scenario | Evidence / note |
|---|---|---|
| SUPERSEDED | Technician requests part (REQUESTED) | harness: SQL column error in my check; part request itself worked |
| PASS | Request more than stock/limit rejected or held without negative stock | Part requested; stores will reserve and issue it. // Before you can complete: Required checklist 'Generator preventive s lines= |
| PASS | Stores reserves 2 (REQUESTED->RESERVED), reserved counter | RESERVED/req 2.000/iss 0.000/con 0.000/ret 0.000 bal=20.000/2.000 Stock reserved. |
| PASS | Insufficient stock reserve (9999 vs 8) rejected; no negative/over-reserved balance | REQUESTED/req 9999.000/iss 0.000/con 0.000/ret 0.000 bal=8.000/0.000 msg=Insufficient available stock. |
| PASS | Stores issues 2 (RESERVED->ISSUED); on_hand decremented | ISSUED/req 2.000/iss 2.000/con 0.000/ret 0.000 bal=18.000/0.000 |
| PASS | Over-issue beyond requested rejected (crafted POST) | http=302 bal=18.000/0.000 |
| PASS | Technician consumes 1 (ISSUED, consumed 1) | ISSUED/req 2.000/iss 2.000/con 1.000/ret 0.000 Consumption recorded. |
| PASS | RBAC: technician cannot issue stock (crafted POST) | http=403 |
| PASS | Stores returns unused 1 to stock | CONSUMED/iss 2.000/con 1.000/ret 1.000 Stock returned. |
| PASS | Cancel unissued request line | CANCELLED/iss 0.000/con 0.000/ret 0.000 |
| PASS | Part lines reconciled on close | RECONCILED/iss 2.000/con 1.000/ret 1.000 / CANCELLED/iss 0.000/con 0.000/ret 0.000 |
| PASS | Stock after cycle: 20 - 2 issued + 1 returned = 19 on hand | 19.000/0.000 |
| PASS | Ledger movements for BRG-6205 | RECEIPT:20.000, RECEIPT:5.000, RESERVE:2.000, ISSUE:2.000, RETURN:1.000 |
| PASS | Ledger invariant: SUM(movements)==balance for ALL balances | 0 |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 7 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 7 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 7 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 7 pages | [] |
| PASS | Create part with min/max/reorder (UI->DB) | Part UIP-12877 created. |
| PASS | Duplicate part number (case-insens) rejected | A part with this part number already exists. |
| PASS | min>max stock rejected | The maximum level cannot be below the minimum level. |
| PASS | Create warehouse (UI->DB) | Warehouse UIW12877 created. |
| PASS | Receive stock (UI) creates balance + RECEIPT movement | c8935701-2b2e-4a79-aa6d-d148bae3195d/3.000 Received 3 x UIP-12877. |
| PASS | Adjust below zero rejected (no negative stock) | The adjustment would cut into reserved stock or go below zero. |
| PASS | Adjust -1 with reason (ADJUSTMENT movement) | RECEIPT:3.000,ADJUSTMENT:1.000 |
| PASS | Low-stock filter lists the part (2 <= min 5) | Stock / On hand, reserved and available per warehouse. Every change is a movement. / Receive stock / Transfer / All warehouses / BLR-WH / HYD-WH / RB1AE5 / RB4F9F / UIW |
| SUPERSEDED | M14-001 runtime: dashboard Low-stock KPI equals stock list low=1 count | harness: my assertion logic was wrong; see the M14 FAIL line (defect confirmed) |

## M10: browser PASS; overall PARTIAL

Provider, warranty/AMC/contract create, overlap rule, end<start rejected, expiry list incl. lapsed, coverage engine panel on WO, renewal alert delivered through the real Celery worker. Static MEDIUM F-M13 (alert consumed when no recipients).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Create warranty (UI->DB) covering PMP-001, expires in 20 days | Warranty WAR-11482 created. // Expires in 20 days (24 Oct 2026). It has not been renewed. |
| PASS | Overlapping same-kind agreement on the same asset rejected | Asset PMP-001 already has an active warranty (WAR-11482) overlapping 2026-09-24 to 2027-04-22. |
| PASS | AMC (different kind) may coexist with warranty on same asset | Annual maintenance contract AMC-11482 created. |
| PASS | End date before start rejected | The end date cannot be before the start date. |
| PASS | Create already-lapsed agreement (renewal workflow input) | Service contract OLD-11482 created. // This agreement expired on 29 Sep 2026; it no longer makes any |
| PASS | Expiring coverage lists soon-to-expire and lapsed | Expiring coverage / Active agreements ending within 60 days, and active agreements that have already lapsed. / 30 days / 60 days / 90 days / 180 days / 365 days / Apply / Expiring soon / REFERENCE	TYPE	PROVIDER	SITE	ENDS	DAYS LEFT |
| SUPERSEDED | Coverage engine on WO: corrective on warranted asset eligible; preventive excluded by agreement exclusion | harness: panel loads via HTMX; re-run PASS |
| PASS | Coverage engine: work type excluded by agreement (INSPECTION) -> not covered by that warranty; other types covered; HTMX panel on WO | Coverage & eligibility (judged on 04 Oct 2026) / Covering /  / Eligible. covered by annual maintenance contract AMC-11482 (Cummins Service India) until 2027-07-31 AMC-11482 /  / Record this check / Job / Description / — / Asset /  |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 5 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 5 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 5 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 5 pages | [] |

## M11: browser PASS; overall PASS

Targets/rules edited in UI; real elapsed time with Celery beat: response breach, 50 % warning, resolution breach, escalation level 2 at +1 min, notifications to the configured roles, acknowledge in UI, pause on TRIAGED + resume, MET_LATE recorded. 24/7 clock is INTENTIONAL (I01).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Edit SLA target HIGH to 1/3 min via UI | 1/3 Target saved. Items already being tracked keep their due times. |
| PASS | Add escalation rule (RESOLUTION, +1 min after breach, level 2) | Escalation rule added. |
| PASS | Acknowledge breach in UI (persisted + who) | ACKNOWLEDGED/784fd926-5a46-4e6f-8b1c-392c457656b8 |
| PASS | Real elapsed-time SLA: response breach, 50% warning, resolution breach, escalation level 2 fired by Celery beat at configured offsets | INC-000001: due 10:50:56 -> BREACHED 10:51:25; WARNING 10:52:25; resolution due 10:52:56 -> BREACHED 10:53:25; ESCALATED 10:54:25 (+1 min rule); in-app notifications to Service Manager (x2) and Operations Manager (level 2). Detect |
| PASS | Late resolution of request recorded as MET_LATE (INC-000002) | tracking COMPLETED resolution_state=MET_LATE |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 5 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 5 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 5 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 5 pages | [] |

## M12: browser PARTIAL; overall PARTIAL

QR + Code128 generation, printable label, typed and camera (synthetic device) scan, invalid code, service event creation from scan, replace/revoke, 429 after 15 failures, cross-tenant/anonymous/client denied. Redis outage turns every scan into a 500 (F-M11).

| Status | Scenario | Evidence / note |
|---|---|---|
| SUPERSEDED | Generate QR + Code128 labels (UI->DB) | harness: SQL column error in my check; labels were generated; re-run PASS |
| PASS | Generate QR + Code128 labels (UI->DB) | BARCODE:FMPU5CRU7L93:true ; QR:0phPUmmyK0LCcHCpPGzlxg:true |
| PASS | Token is opaque (not derived from tag/uuid) and long enough | qr_len=22 barcode_len=12 |
| PASS | Printable label page renders SVG QR + barcode | svgs=16 |
| PASS | Scan (typed barcode, lowercase) resolves asset | http://127.0.0.1:8098/app/s/fmpu5cru7l93/ |
| PASS | Invalid code -> not recognised (no asset data) | Label not recognised / This code is not a valid label for any organization you can access, or you cannot view its asset. Check the code or ask an administrator. / Try again |
| PASS | Scan -> create service event (incident) from asset page | http://127.0.0.1:8098/app/incidents/200a74b6-8d56-444a-8bc8-d897c4ef9eb0/ INC-000003 created for PMP-001. |
| PASS | Scan event persisted and linked to the created request | ERROR:  column "outcome" does not exist,LINE 1: select outcome from identification_scanevent order by create...,               ^ |
| PASS | BETA user scanning ALPHA QR: no asset data (tenant isolation) | 404 'Label not recognised\nThis code is not a valid label for any organization you can access, or you cannot view its asset. C' |
| PASS | Anonymous scan redirected to sign-in, no asset data | http://127.0.0.1:8098/accounts/login/?next=/app/s/0phPUmmyK0LCcHCpPGzlxg/ |
| PASS | Client/requester scanning internal QR: denied | 404 'Label not recognised\nThis code is not a valid label for any organization you can access, or you cann' |
| SUPERSEDED | Brute-force: repeated invalid scans get throttled (429) | harness: limit is 15 failures; first run made 15; re-run PASS (429) |
| PASS | Brute-force: invalid scans throttled after limit (15 failures / 10 min -> 429) | [429, 429, 429, 429, 429] |
| PASS | While throttled even a VALID token is refused (cannot interleave guessing) | 429 |
| PASS | BETA API scan/resolve of ALPHA token | 404 {'error': {'code': 'not_found', 'message': 'Label not found.', 'details': {}, 'request_id': '5796f9518419414f8a2d50e6d52 |
| SUPERSEDED | Replace label: old QR token no longer resolves | harness: expectation too strict: revoked label shows a warning by design (INTENTIONAL I07) |
| PASS | Replace requires reason; old token kept as revoked history |  |
| PASS | Revoked/replaced label behaviour: authorised user sees asset with 'revoked or replaced, do not rely' warning; API returns 410 REVOKED; unauthorised/foreign still 404 | design decision (shows warning not silent failure); recorded as observation not defect |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 2 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 2 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 2 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 2 pages | [] |
| SUPERSEDED | Camera scan path (Chromium fake capture device streaming the real label QR): live video -> ZXing decode -> server resolve -> asset opens | harness: first QR was small; re-run PASS (see L32) |
| PASS | Camera scan of foreign-tenant QR: no asset data | ('http://127.0.0.1:8098/app/s/sVtxe55fov0NKSZ-jjFmCQ/?open=asset', 'Label not recognised / This code is not a valid label for any organization you can access, or you cannot view its asset. Check the code or ask an administrator. / |
| PASS | Camera scan of non-FieldOps QR text: rejected cleanly | ('http://127.0.0.1:8098/app/identification/scan/', 'Scan an asset label / Point the camera at the QR code on the asset. The asset opens automatically. / Camera / That code is not a FieldOps asset label. Keep scanning o') |
| INFO | LIMITATION: no physical phone camera; used Chromium synthetic capture device (MJPEG of the real QR) — physical-camera behaviour UNVERIFIED |  |
| PASS | Camera scan path (Chromium synthetic capture device streaming the real label QR): live video -> ZXing decode -> server resolve -> asset opens | http://127.0.0.1:8098/app/assets/f63bfc37-315c-4c49-a7c0-65bd98c57408/ |

## M13: browser PARTIAL; overall PARTIAL

Client sees only granted assets, submits with attachment on 390 px, tracks status, sees visit window/technician but no internal data, confirms, request closes; client has no access to any internal page or API. FAIL: a disabled account keeps read access (F-M09, RUNTIME); reopen path 500 (F-M01).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Client submits request with attachment (mobile 390px) | http://127.0.0.1:8098/app/portal/requests/848a2b00-51dc-40f5-8170-ccbeab134c0f/ Request INC-000002 submitted. We will keep you updated here. // We have your request and will review |
| PASS | Request persisted linked to asset, reporter=client, status NEW | INC-000002/NEW/HIGH/INCIDENT/t/t |
| PASS | Attachment stored and linked |  |
| PASS | Client sees request status page | My requests / INC-000002 / Server room AC not cooling / Received /  / INC-000002 · HVAC-001 · Building A HVAC Unit · submitted 04 Oct 2026 10:50 /  / We have your request and will review it shortly. / Received / Approv |
| PASS | Client sees tech/visit info but NOT internal fields (labor, parts, notes, SLA) | Scheduled visit / Status / Quality check / Planned / Sun 04 Oct 2026, 11:52 – 13:52 / Technician / Alpha Technician Two / Progress / Received / 04 Oct 2026 10:50 / Under review / 04 Oct 2026 10:50 / Approved / 04 Oct 2026 10:50 /  |
| PASS | Client confirms fix (RESOLVED->CONFIRMED) while WO still in SUPERVISOR_REVIEW | request=CONFIRMED wo=SUPERVISOR_REVIEW (observation: allowed before supervisor closes -> M05-03) |
| PASS | Client sees closed request |  |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 4 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 4 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 4 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 4 pages | [] |
| FAIL | M13-001 runtime: DISABLED portal account — REST list/read still works (HTML blocked, API create blocked) | API list=200 assets=200 create=404 html=(200, 'My requests New request All Open Needs my confirmation Closed Filter INC-000009 ') |

## M14: browser PARTIAL; overall PARTIAL

KPIs equal direct SQL (open 12, overdue 9, created 5, completed 2, closed 2, assets 17+2, requests 3, breaches 4, movements 7), site/date filters, inverted/invalid inputs, foreign site, empty states, Beta isolation, technician/client denied, API = UI. FAIL: Low-stock KPI 0 vs list 1 (F-M10, RUNTIME).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Site filter (BLR-1) shows only that site's data (0 open WO) | Open work orders 0 now Overdue work 0 past planned end, not  |
| PASS | Date range with no data renders zeros / empty states (no crash) | Created 0 in the period Completed 0 in t |
| PASS | Inverted date range handled | The start date is after the end date. Operations dashboard · FieldOps Nexus |
| PASS | Invalid site param does not 500 | Operations dashboard · FieldOps Nexus |
| PASS | Foreign (BETA) site id as filter shows no BETA data / denied |  |
| PASS | BETA dashboard shows only BETA data (1 asset) | Reset / Assets / 1 / now / Failures / 0 / downtimes started in the period / Downtime / 0.0 h / clipped to the period / MTTR / n/a / mean time to |
| PASS | Technician denied org dashboards (permission-sensitive) | 403 |
| PASS | Technician 'My work summary' available | My work summary / Only your own assigned jobs and hours, 05 Sep 2026 – 04 Oct 2026. / Open my jobs / From / To / Apply / My open jobs / 0 / now / Overdue / 0 / Completed / 1 /  |
| PASS | Client denied dashboards | 403 |
| PASS | API dashboards/operations (auditor) 200 + same numbers | {'filters': {'site': None, 'from': '2026-09-05', 'to': '2026-10-04'}, 'data': {'kpis': {'open_total': 12, 'overdue': 9, 'created': 5, 'completed': 2,  |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 5 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 5 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 5 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 5 pages | [] |
| FAIL | M14-001 CONFIRMED at runtime: dashboard 'Low-stock balances' = 0 while stock list low=1 shows 1 (part-level minimum ignored by KPI) | dashboard 0 vs list 1 (UIP-part on hand 2, part min 5). Supersedes the PASS line above. |
| PASS | Site-scoped role: dashboards not available or scoped | FX FieldOps Nexus Access denied  You do not have permission to do this. If you t |

## M15: browser PASS; overall PARTIAL

Audit list/search/filters/detail, CSV/XLSX/PDF exports (formula-safe, audited), per-WO evidence ZIP with manifest hashes, API PATCH/DELETE 403 for all, Beta isolation. Medium findings: JWT logins unaudited (F-M14), platform audit exposure (F-M15), and the DB-level TRUNCATE gap (F-H02).

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Audit trail list renders rows (paginated) | rows on page=25 |
| PASS | Audit search by object (WO-000011) |  |
| PASS | Audit entry detail shows actor/action/target/before-after/request id/IP | Audit trail / Entry / auth.login / When / 2026-10-04T10:59:50.913394+00:00 / Actor / auditor@alpha.qa.test / Target / auditor@alpha.qa.test accounts.user 1a7afd90-b3c8-48f3-9c2f-17c4df24bc83 / Site / — / IP / Request / 127.0 |
| PASS | Evidence package ZIP for closed WO-000011 (client-origin) | 200 ['approvals.csv', 'audit_trail.csv', 'checklists.json', 'coverage_checks.csv', 'labor.csv', 'materials.csv', 'parts.csv', 'request_history.csv', 'sla.json', 'stock_movements.csv', 'summary.json', 'timeline.csv', 'evidence/work |
| PASS | CSV export downloads (auditor, audit.export) | 200 text/csv; charset=utf-8 attachment; filename="audit-alpha-field-services-20261004-105952.csv" |
| PASS | CSV export neutralises formula-leading cells | [] |
| PASS | XLSX export | 200 |
| PASS | PDF export | 200 |
| PASS | Exports themselves are audited | 4 |
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 2 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 2 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 2 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 2 pages | [] |

## Cross-cutting: Platform console / onboarding (Super Admin)

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Super Admin creates organization + owner invitation (UI->DB) | Organization created. An activation email was sent to owner@gamma-13919.test. http://127.0.0.1:8098/platform/organizations/173da195-1b18-4494-aaab-5c01eebd746a/ |
| PASS | Owner membership INVITED, role Owner, audit organization.created | INVITED organization.created |
| PASS | Duplicate organization slug rejected | An organization with this name or slug already exists. |
| PASS | Org Owner cannot open the platform console (403/404) | 403 |
| PASS | Org Owner cannot call platform API | 403 |
| PASS | Owner activates account from the emailed link, sets a strong password, membership becomes ACTIVE | http://127.0.0.1:8098/accounts/login/ |
| PASS | Activation link cannot be reused after the password is set | FX FieldOps Nexus Link expired or invalid  This activation link can no longer be used. Ask your organization administrat |
| PASS | New org owner signs in and lands in own empty org (no data from other tenants) | Dashboard · Gamma Works 13919 |
| PASS | New org sees zero sites/assets of other orgs |  |
| PASS | New org seeded with system roles (owner, admin, ops, planner, tech, stores, ...) | 11 roles |
| PASS | Weak/common password rejected on change | This password is too short. It must contain at least 12 characters. // This password is too common. |
| PASS | Super Admin suspends organization with reason (UI dialog) | organization.created,organization.suspended |
| PASS | Suspended org: existing session blocked in UI and API | html=403 'FX FieldOps Nexus Organization suspended  Access to this organization has been suspended by the platform administrator. Contact support.  Sign out' api=403 |
| PASS | Suspended org: fresh login cannot reach app data | http://127.0.0.1:8098/app/ FX FieldOps Nexus Organization suspended  Access to this organization has been suspended by the platform administrator. Contact support.  Si |
| PASS | Suspending Gamma does not affect Alpha users | 200 |
| PASS | Super Admin reactivates organization | ACTIVE organization.created,organization.suspended,organization.activated |
| PASS | Reactivated org: owner can use the app | 200 |
| FAIL | M15-002 runtime: platform org page 'Recent activity' lists tenant operational events | Recent activity auth.login 04 Oct 2026 11:39 · owner@alpha.qa.test · owner@alpha.qa.test auth.login 04 Oct 2026 11:38 · owner@alpha.qa.test · owner@alpha.qa.test auth.login 04 Oct 2026 11:37 · owner@alpha.qa.test · owner |

## Cross-cutting: State-machine negative tests (all five machines)

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | PM: technician cannot generate a cycle (API) | 403 |
| PASS | PM: auditor cannot generate a cycle (API) | 403 |
| PASS | PM: client cannot generate a cycle (API) | 403 |
| PASS | PM: stores cannot generate a cycle (API) | 403 |
| PASS | PM: planner manual generate while previous cycle still open is refused (no duplicate) | 409 {'error': {'code': 'previous_cycle_open', 'message': "The previous cycle's work order is still open: finish it before ge |
| SUPERSEDED | Asset: technician cannot change status (API) | 403 |
| SUPERSEDED | Asset: duplicate start_maintenance rejected 409, state unchanged | 409/409 {'error': {'code': 'invalid_transition', 'message': "asset_status: action 'start_maintenance' is not |
| PASS | Asset: OUT_OF_SERVICE -> DISPOSED (terminal) and further changes refused | DISPOSED |
| PASS | Asset: DISPOSED asset is read-only (PATCH refused) | 409 |
| PASS | Request: duplicate triage rejected 409 | 200/409 |
| PASS | Request: reject without reason refused | 400 {'error': {'code': 'reason_required', 'message': 'A reason is required.', 'details': {}, 'request_id |
| PASS | Request: TRIAGED -> REJECTED (terminal) with reason | 200 |
| PASS | Request: REJECTED is terminal (approve refused) | 409 |
| PASS | Request: technician cannot approve/triage | 403 |
| PASS | WO: complete from PLANNED refused (409) | 403 |
| INFO | NOTE: the two preceding 'Asset: technician cannot change status' / 'duplicate start_maintenance' FAIL lines are harness state errors (LAP-001 was already UNDER_MAINTENANCE through an open WO); the technician got 403 and the duplicate start got 409 as required |  |
| PASS | Asset: technician denied status change (403) and a repeat start_maintenance is refused 409 (state machine), disposal of an asset that still has an open (COMPLETED) work order is ALLOWED (see F-M06) | 403 / 409 / dispose accepted |

## Cross-cutting: Celery

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Worker stopped: invite API still succeeds (email task queued in Redis) | 201 |

## Cross-cutting: Redis outage experiments

| Status | Scenario | Evidence / note |
|---|---|---|
| FAIL | Redis DOWN: REST API requests | GET /api/v1/assets/ -> 500 (throttle uses cache)  |
| PASS | Redis DOWN: HTML pages (sessions in DB) still work | 200 |
| PASS | Redis DOWN: invite -> 5xx after DB commit (user saved, email lost) | http=500 |
| FAIL | Redis DOWN: QR scan (throttle counter in cache) | 500 |
| FAIL | Redis DOWN: HTML invite -> user committed to DB, request errors, email never queued | saved=1 title='' |
| PASS | Redis restored: API and readiness recover without app restart | 200/200 |

## Cross-cutting: Security probes (browser)

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Security headers on app pages (CSP nonce, XFO DENY, nosniff, referrer) | default-src 'self'; script-src 'self' 'nonce-iuF5qjU3MTlYHNWS_z4GWA'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; f |
| PASS | Open redirect via login next=https://evil.example/ | http://127.0.0.1:8098/app/ |
| PASS | Open redirect via login next=//evil.example/ | http://127.0.0.1:8098/app/ |
| PASS | Open redirect via login next=/\evil.example | http://127.0.0.1:8098/app/ |
| PASS | Open redirect via login next=javascript:alert(1) | http://127.0.0.1:8098/app/ |
| PASS | CSRF: HTML POST without token rejected | 403 |
| PASS | CSRF: session-authenticated API POST without token rejected | 403 |
| PASS | Session cookie invalid after logout (server-side invalidation) | 401 |
| PASS | Brute force: 5+ failures lock the account+IP; correct password then refused | after lock url=http://127.0.0.1:8098/accounts/login/ text='FX\nFieldOps Nexus\nToo many sign-in attempts\n\nFor security, sign-in for this account from this device is paused after 5 failed attempts. Plea' |
| PASS | Login error does not reveal whether the account exists | 'Invalid email or password.' vs 'Invalid email or password.' |
| PASS | Attachment download IDOR: beta sees none; client cannot read internal WO evidence / asset docs; anon redirected | {"owner": {"WO1 evidence": 200, "req2 client attachment": 200, "asset manual": 200, "WO2 evidence": 200}, "tech1(assigned WO1)": {"WO1 evidence": 403, "req2 client attachment": 403, "asset manual": 403, "WO2 evidence": 403}, "tech |
| PASS | Upload >10 MB rejected with message | File exceeds the 10 MB limit. |
| PASS | Stored XSS / template-injection payloads in 6 entity types render inert across 15 pages (incl. audit, search, dashboards) | bad=[] dialogs=[] |
| PASS | Cross-tenant UPLOAD onto foreign asset/WO/request/inspection (API multipart + HTML): rejected, no attachment stored | [('/api/v1/assets/8a4d0504-1aee-4e3a-952a-d82', 404), ('/api/v1/work-orders/ecc4092c-fe0c-406b-9cc', 404), ('/api/v1/service-requests/848a2b00-51dc-40f', 404), ('/api/v1/inspections/97a8ba9f-eccc-45c0-8b4', 404), ('/app/assets/8a4 |

## Cross-cutting: API probes

| Status | Scenario | Evidence / note |
|---|---|---|
| SUPERSEDED | Mass assignment: client-supplied status/organization/id ignored on asset create |  |
| PASS | JWT + X-Organization naming a non-member org rejected | 403 |
| PASS | Mass assignment: organization/id/status in body cannot override tenant or state (status rejected 400; org/id ignored) | true/acb27324-6792-4877-8d98-b0e6cbdfc5f6 |

## Cross-cutting: Shell/UI

| Status | Scenario | Evidence / note |
|---|---|---|
| FAIL | Shell organization switcher: choosing the other org via dropdown switches context (SEC-001) | before='7\nAlpha Field Services\nBeta Industries\nAlpha Technician One' after='7\nAlpha Field Services\nBeta Industries\nAlpha Technician One' url=http://127.0.0.1:8098/app/ |

## Cross-cutting: RBAC runtime probes

| Status | Scenario | Evidence / note |
|---|---|---|
| FAIL | SEC-002 runtime: Org Admin can create a role holding ALL permissions and assign it to self (no 'only grant what you hold' rule) | create=201 assign=200 export_after=200 |
| FAIL | SEC-002 runtime: non-owner Admin may modify an Owner's member record (full_name) | 200 |

## Cross-cutting: Responsive: users/roles/organization

| Status | Scenario | Evidence / note |
|---|---|---|
| PASS | Responsive desktop 1920x1080: no horizontal overflow on 3 pages | [] |
| PASS | Responsive laptop 1440x900: no horizontal overflow on 3 pages | [] |
| PASS | Responsive tablet 1024x768: no horizontal overflow on 3 pages | [] |
| PASS | Responsive mobile 390x844: no horizontal overflow on 3 pages | [] |

