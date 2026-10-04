# HPE Day-90 acceptance audit: the seven journeys, executed for real

**Verdict: HPE Day-90 CONDITIONAL.** All seven journeys were executed end to end in a real browser (plus Celery for the timed parts) against PostgreSQL, with UI, database and audit verified. Every journey passes on its main path. Journey 2 has a reproduced HIGH blocker on the edit path (F-H01), journey 7 has rework-branch defects (F-M01/F-M02), and the day-90 hardening/deployment items carry open conditions (F-H02, F-M18, F-M11). "Real" means: real services, real PostgreSQL rows, real Celery worker/beat, real audit rows, no mocks of application code; the only synthetic elements are the seed data and the compressed SLA targets (1/3 minutes) used to observe elapsed time.

| # | Journey | Result | Key evidence |
|---|---|---|---|
| 1 | Register site + asset hierarchy -> show status -> show change history | **PASS** | Owner created site `AUD-10342`, 4-level zones (Block A > Floor 1 > Room 101 > Service Area N), asset with category attributes, hierarchy P > C1 > G, status chain via UI with reasons. History tab and `GET /assets/{id}/history/`, `/changes/` (field-level diffs), `/location-history/` return who/when/why; DB: one `assets_assetstatushistory` row per change; audit `asset.created/updated/status_changed/component_*` |
| 2 | Create PM plan -> scheduler -> generated work order | **PASS (main path); BLOCKER F-H01 on schedule edit** | Planner created plan + weekly schedule via UI; "Due & upcoming" showed it DUE; WO-000001 generated (PREVENTIVE, HIGH, source PM, required checklist); duplicate generation refused; next cycle advanced; later closed -> cycle VERIFIED. Celery beat generated WO-000025 by itself for a DAILY schedule within one 15-minute tick and two extra runs created no duplicate. **Editing the interval silently stopped generation (reproduced: 1 WO in 10 weeks instead of 5)** |
| 3 | Assign technician -> checklist -> spare parts -> labor -> complete work order | **PASS** | WO-000001: planner assign + dispatch; technician (390 px) start, hold/resume, part request; stores reserve + issue; technician consume; checklist with an out-of-range numeric (blocked until a finding is recorded), labor 2.5 h, note, photo; complete; supervisor review + close after stores returned the unused part; parts RECONCILED; asset UNDER_MAINTENANCE then ACTIVE; 10-state event trail; 14 audit rows |
| 4 | Create high-priority request -> SLA timer -> escalation | **PASS** | INC-000001 (HIGH) with HIGH target set to 1 min response / 3 min resolution: Celery beat detected the response breach (10:51:25), 50 % warning (10:52:25), resolution breach (10:53:25), level-2 escalation (10:54:25, +1 min rule); in-app notifications and emails to Service Manager (breaches) and Operations Manager (escalation); acknowledge in the UI; pause on TRIAGED and resume (INC-000002); late completion recorded MET_LATE |
| 5 | Inventory issue -> work order linkage -> movement -> return/reconciliation | **PASS** | Ledger for BRG-6205: RECEIPT 20, RESERVE 2, ISSUE 2, RETURN 1; on-hand 19 after the cycle; part line RECONCILED on close; `SUM(movements) = balance` for every balance (SQL); insufficient stock and over-issue rejected; technician cannot issue |
| 6 | QR/barcode -> identify asset -> create service event | **PASS** | QR + Code128 generated for PMP-001, printable label; typed (lower-case) barcode and camera scan (Chromium synthetic capture device streaming the real QR) opened the asset; "Report a problem" created INC-000003 with a linked `ScanEvent`; invalid/foreign/anonymous/client scans give no data; 15 failures -> 429; replace revokes the old label (warning, API 410). Physical phone camera UNVERIFIED |
| 7 | Client request -> technician completion -> client confirmation -> closed request -> audit/dashboard evidence | **PASS (main path); rework branch F-M01/F-M02/F-M03** | Client on a 390 px screen submitted INC-000002 with a photo; service manager triaged/approved; planner created and dispatched WO-000011; technician completed (checklist, labor, evidence); client saw "Resolved: please confirm", the visit window and technician name (no internal data), confirmed; supervisor closed; service manager closed the request. Evidence: 11 audit actions, request history trail, evidence ZIP for the WO (timeline, approvals, labor, SLA, checklists, audit trail, manifest with hashes), dashboards equal SQL |

## Day-30 / Day-60 / Day-90 gates against the findings

| Gate | HPE deliverable | Verdict | Open items |
|---|---|---|---|
| Day 30 | Auth/RBAC | PASS (F-M17 to be decided/recorded) | F-M07 |
| | Site hierarchy, asset registry/hierarchy | PASS (M01 PASS, M02 PASS, M03 PARTIAL) | F-M06, F-M19 |
| | Service request, WO core, checklist templates | PARTIAL | F-M01, F-M02, F-M04 |
| | DB schema, CI/CD | PASS (schema, migrations) / CI run history UNVERIFIED | L44 |
| Day 60 | PM scheduler | **BLOCKER** | F-H01 |
| | Assignment/dispatch, technician workspace, inspections | PASS | L15 |
| | Inventory reservations/issues/returns | PASS | L23-L25 |
| | SLA engine, notifications, beta dashboards | PASS / PARTIAL (F-M10) | F-M10 |
| Day 90 | Warranty/AMC, client portal, QR | PASS / PARTIAL (F-M09 portal) | F-M09, F-M11 |
| | Analytics, audit/export | PARTIAL | F-M10, F-M14, F-M15 |
| | Security hardening | CONDITIONAL | **F-H02**, F-M16, F-M17, F-M18 |
| | Performance | UNVERIFIED (not measured) | U07 |
| | Tests | PASS: 746 passed, 93 % coverage; no Playwright suite in CI | L57 |
| | Deployment, KT docs | CONDITIONAL | F-M18, U02, U06 |

## Must fix before HPE Day-90 acceptance

1. F-H01 (PM edit silently stops generation) and add the regression test.
2. F-H02 + F-M18 (audit/ledger tamper resistance and least-privilege DB role, verified on the production database).
3. F-M01/F-M02/F-M03 (request <-> work-order lifecycle coupling and downtime).
4. F-M07 (API site scope), F-M09 (disabled portal client), F-M10 (low-stock KPI), F-M14 (JWT audit), F-M11 (Redis resilience), F-M04 (checklist applicability).
5. Decide and record F-M15 (platform audit visibility) and F-M17 (Admin trust).
6. Run the remaining UNVERIFIED items (U02-U07) before the acceptance review.
