# Workflow acceptance audit (five mandatory state machines + cross-module integration)

**Verdict: Mandatory workflows CONDITIONAL.** All five state machines exist, are enforced only through services, and passed valid, invalid, unauthorized, duplicate and direct-API-bypass tests with database and audit verification. The conditions are defects at the seams between machines (F-H01 PM edit, F-M01/F-M02/F-M03 request vs work-order coupling, F-M06 asset retire vs hierarchy).

Method: each machine was driven through the browser (UI buttons with confirm dialogs, forms) and through crafted POST/API calls with a valid session+CSRF to prove the backend, not the UI, is authoritative. After every step the database (psql) and the audit table were read. Scenario lines: `evidence/browser_results.jsonl`.

## 1. State-machine matrix (PASS unless stated)

| Check | Service Request (M05) | Work Order (M06) | PM lifecycle (M04) | Part request (M09) | Asset status (M02) |
|---|---|---|---|---|---|
| States exist | NEW, TRIAGED, APPROVED, REJECTED, WORK_ORDER_CREATED, IN_SERVICE, RESOLVED, CONFIRMED, CLOSED (+system actions) | DRAFT, PLANNED, ASSIGNED, DISPATCHED, IN_PROGRESS, ON_HOLD, COMPLETED, SUPERVISOR_REVIEW, CLOSED (+CANCELLED, `reject_review`: D-036) | derived: SCHEDULED/DUE/GENERATED/ASSIGNED/COMPLETED/VERIFIED + next cycle (D-043, not a StateMachine object: INTENTIONAL) | REQUESTED, RESERVED, ISSUED, CONSUMED, RETURNED, RECONCILED (+CANCELLED) | ACTIVE, UNDER_MAINTENANCE, OUT_OF_SERVICE, RETIRED, DISPOSED |
| Valid path in browser | INC-000002: NEW>TRIAGED>APPROVED>WORK_ORDER_CREATED>IN_SERVICE>RESOLVED>CONFIRMED>CLOSED (client, service manager, planner, technician, supervisor roles) | WO-000001/000011: DRAFT>PLANNED>ASSIGNED>DISPATCHED>IN_PROGRESS>(ON_HOLD>IN_PROGRESS)>COMPLETED>SUPERVISOR_REVIEW>CLOSED | plan -> schedule -> DUE list -> generated WO (manual) and by Celery beat (WO-000025) -> closed -> VERIFIED in history -> next cycle date advanced | BRG-6205: REQUESTED>RESERVED>ISSUED>(consume 1)>(return 1)>RECONCILED on WO close; BELT: REQUESTED>CANCELLED | ACTIVE>UNDER_MAINTENANCE>OUT_OF_SERVICE>ACTIVE; ... >RETIRED; ... >DISPOSED (UI + API) |
| Alternative branch | REJECTED (reason required) | ON_HOLD/resume, CANCELLED (draft, reason), `reject_review` | missed cycles collapse (D-045, static + tests) | cancel unissued line | complete_maintenance |
| Invalid transitions refused | close from APPROVED; approve after REJECTED; triage twice -> 409 | start/plan from CLOSED/CANCELLED; complete from PLANNED; complete before checklist -> blocked | generate while previous cycle open -> 409 `previous_cycle_open`; disabled plan/inactive meter (static) | over-issue beyond requested, reserve > available, adjust below zero -> rejected; issued-not-consumed blocks close | retire from ACTIVE; return_to_service from DISPOSED; edit of a DISPOSED asset -> 409 |
| Unauthorized refused (backend) | technician triage/approve 403; client any internal action 403/404 | technician review/close, planner start review, other technician start -> 403/404; DB unchanged | technician/auditor/client/stores `generate` 403 | technician issue stock 403 | technician status change 403 |
| Duplicate/idempotent | second triage 409; second create-work-order creates no 2nd live WO | second close 409, one CLOSED event | repeated generate/extra beat runs: still 1 cycle (UNIQUE) | repeat issue beyond line quantity refused | second start_maintenance 409 |
| Direct API bypass | system-only actions (`link_work_order`, `work_order_cancelled`) not callable | crafted POST to `/transition/` and HTML endpoints: same result as UI | crafted generate POST: no duplicate | crafted HTML/API POSTs enforced the same rules | crafted POSTs enforced |
| DB persistence | `incidents_servicerequesthistory` trail equals UI | `workorders_workorderevent` trail DRAFT>...>CLOSED (10 states) | `maintenance_maintenancecycle` rows, schedule next_sequence/next_due_date | `inventory_workorderpart` + `inventory_stockmovement` ledger; invariant SUM(movements)=balance held for all balances | `assets_assetstatushistory` one row per change; status equals last history for all assets |
| History / audit | 11 audit actions on INC-000002 incl. portal confirm | 14 audit rows on WO-000001; CSV evidence ZIP lists the same | `maintenance.plan_created/schedule_created/cycle_generated` | `stock.reserved/issued/returned`, `part_line.*` | `asset.status_changed` x5 with reasons |
| Tenant isolation | Beta crafted transition on Alpha request -> 404 | 404 | 404 on generate | 404 | 404 |
| **Defects** | **F-M01** (reopen+create WO -> 500), **F-M02** (confirm/close while WO in review/rework), **F-M03** (downtime left open after reject) | none in the machine; F-M04 makes the checklist gate produce bogus data | **F-H01 (BLOCKER)**: editing the recurrence silently stops generation; F-M05 checklist bypass | L23-L25 only | **F-M06** retire/dispose ignores hierarchy and open work orders (an asset was disposed while a COMPLETED WO was open) |

Role-based sign-off observed: planner cannot start/close work (403), technician cannot review/close, supervisor cannot create WOs, stores cannot touch work orders, client cannot see any of it. Technician double-booking is refused (`409 technician_conflict`: "already committed to WO-000020 in this time window").

## 2. Closure rules (HPE: "closure requires checklist, resolution notes and required evidence according to work type")

Verified in the UI/API: required checklist must be completed (blocker text shown on the technician screen); resolution notes of at least 10 characters; labor hours >= 1 and parts reconciled gate **closure** (complete is allowed without them, close returns `409 closure_blocked` with a blockers list); photo evidence is required for CORRECTIVE (blocker "Attach at least one photo / file as evidence" shown) and not for OTHER; an issued-but-unreturned part blocks closure. Gaps: any attachment counts as evidence (L16), open findings do not block closure (D-061).

## 3. Cross-module integration (Phase 8)

| Link | Verdict | Evidence |
|---|---|---|
| M01 -> M02 | PASS | asset requires an active site and a zone of the same site (crafted POST with a foreign-site zone -> 400); a site with active assets cannot be deactivated ("Site has 5 active asset(s)") |
| M02 -> M03 | PARTIAL | hierarchy enforces same org/site, no cycles/self/re-parent of a parented child; retire ignores links (F-M06) |
| M02 -> M04 | PASS | plans/schedules/meters bound to the asset; meter-based plan seeded; Celery beat generated WO-000025 |
| M02 -> M05 | PASS | incidents/requests are asset-linked; "Report a problem" from the asset and from QR creates INC with asset |
| M05 -> M06 | PARTIAL | create WO from approved request, completion moves the request to RESOLVED; rework/reopen gaps (F-M01, F-M02) |
| M06 -> M07 | PASS | workspace is a thin layer over M06/M08/M09; scoping to assigned jobs verified |
| M06 -> M08 | PARTIAL | required checklist gate works but not asset-scoped (F-M04) |
| M06 -> M09 | PASS | part lines, reservations, issue/consume/return, closure blockers, reconcile on close |
| M04 -> M06 | PASS (BLOCKER on edit) | generated WOs are PREVENTIVE with source=PM and checklist association; F-H01 |
| M05/M06 -> M11 | PASS | SLA tracking auto-created for requests and work orders (profiles applied by type/priority); pause on configured state (TRIAGED), resume, warning/breach/escalation/ack/MET_LATE |
| M02/M06 -> M10 | PASS | asset coverage line and WO "Coverage & eligibility" panel from the real engine; exclusions honoured; agreement can pin an SLA profile (static + tests) |
| M02 -> M12 | PASS | labels, scan -> asset -> service event (INC-000003), replace/revoke, throttling |
| M13 -> M05 | PASS (rework PARTIAL) | client requests are real incidents (`reported_by` = client membership); portal projections are client-safe |
| ALL -> M14 | PASS (one KPI defect) | KPIs equal SQL; F-M10 |
| ALL critical operations -> M15 | PARTIAL | audited: all state changes, stock, exports, QR scans, role/member changes, uploads; **not audited**: JWT sign-ins/refresh, single failed logins, attachment downloads, SLA pause/resume/reopen/cancel, platform audit viewing, permission-denied attempts (F-M14, L30, L36) |
| WO <-> asset status coupling | PASS | WO start -> asset UNDER_MAINTENANCE; WO close -> ACTIVE (observed on PMP-001) |

## 4. Verdict by machine

| Machine | Verdict |
|---|---|
| Service Request | PARTIAL (F-M01, F-M02, F-M03) |
| Work Order | PASS |
| PM | PARTIAL, **BLOCKER F-H01** |
| Part Request | PASS |
| Asset | PARTIAL (F-M06) |
