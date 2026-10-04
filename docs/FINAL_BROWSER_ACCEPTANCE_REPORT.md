# Final browser acceptance report (2026-10-03)

Environment: local QA database `fieldops_qa_final` (PostgreSQL 16 in Docker, freshly migrated and seeded through the services),
`config.settings.dev`, `runserver 127.0.0.1:8098`, driven in the Claude desktop **built-in browser pane**. Two organizations
(QA Alpha with 2 sites, QA Beta with 1), 11 Alpha personas (owner, operations, planner, technician, supervisor, stores, asset
manager, service manager, auditor, site-scoped auditor, two portal clients). Seed/helper scripts live outside the repo (scratch).

Scope performed: the NEW modules M10, M12, M13, M14, M15 plus the continuous request journey that crosses M05/M06/M07/M13.
**Not performed (see "Gaps"): the visible M01-M08 audit.** Do not read this report as browser verification of M01-M08 (D-048).

| # | Scenario (real UI clicks) | Result | Browser -> DB evidence |
|---|---|---|---|
| 1 | Asset manager: asset P-100 > Coverage tab (HTMX panel loads, "Not covered") | PASS | panel computed by backend |
| 2 | Create provider "Grundfos Service" (form > flash > list) | PASS | `contracts_serviceprovider` row, audit `contract.provider_created` |
| 3 | Create warranty GF-2026-001 from the asset (asset + site pre-filled, dates, "Preventive" excluded) | PASS | `contracts_coverageagreement` 1 row, 1 covered asset, exclusion PREVENTIVE, audit `contract.agreement_created` with `site_id` |
| 4 | Asset > Labels: generate QR and barcode; printable label page renders both | PASS | 2 active `identification_assetidentifier` rows, audit `qr.generated` x2 |
| 5 | Scan page: typed lowercase barcode code resolves the asset | PASS | `scanevent` + audit `qr.scanned` |
| 6 | Anonymous open of a QR link redirects to sign-in with `next` (no asset data) | PASS | - |
| 7 | Technician opens the QR link, reports "Seal leaking" (severity High) | PASS | INC-000001 created, `scanevent.service_request` linked, audits `incident.created`, `qr.service_event_created` |
| 8 | Beta owner opens Alpha's QR link; opens Alpha's asset URL | PASS (denied) | "Label not recognised" / 404; no data shown |
| 9 | Client A: lands on `/app/portal/` (mobile-width), only P-100 offered, submits request | PASS | INC-000002 `reported_by` = client; audits `incident.created`, `portal.request_submitted` |
| 10 | Staff side (service layer, scratch script): triage, approve, work order, assign, dispatch, start, evidence, labor, complete | n/a | INC-000002 RESOLVED, WO-000001 COMPLETED |
| 11 | Client sees "Resolved: please confirm", visit window and technician name, clicks "Yes, it is fixed" | PASS | status CONFIRMED, `confirmed_at` set, audit `portal.request_confirmed` |
| 12 | Client opens `/app/work-orders/` (Access denied) and calls work-order, asset, audit APIs (403) | PASS (denied) | only `/api/v1/portal/requests/` answers 200 |
| 13 | Staff close WO and request (scratch script), auditor opens Operations and Service dashboards | PASS | Created 1 / Completed 1 / Closed 1, labor 2.0 h = 0.8 % utilization, requests 2 (1 new, 1 closed), from clients 1: all equal direct SQL |
| 14 | Auditor: audit list, "Closures" category (shows the request and WO closures), filters present | PASS | rows carry site codes |
| 15 | Auditor: CSV / XLSX / PDF export downloads (fetch from the page) and `format=exe` | PASS | 200 with correct content types and attachment names; 400 for unknown format |
| 16 | Responsive: dashboards, audit, agreements, scan, reports at 390x844, 768x1024, 1366x768, 1920x1080 | PASS | `scrollWidth` <= viewport on every checked page (no horizontal overflow); tables scroll inside their own container |

Console / network (EXPECTED vs UNEXPECTED): every logged error came from a deliberate negative test (404 foreign object, 403 client
privilege probes, 400 unknown export format). No 500, no JavaScript exception, no failed static asset, no unexpected redirect.

Defect found and fixed during the run: dashboard home copy still said dashboards "appear as modules are delivered" (Low, fixed).
Dev-only note: with `DEBUG=True` a missing URL shows Django's debug 404 (lists URL patterns); production uses the project 404 page.

## Gaps (honest)
- **M01-M08 visible browser audit not performed** (the Team Lead's first message of this run said to skip it; the master spec lists it as
  mandatory). Their browser status stays as recorded in MODULE_STATUS (partial / outstanding, D-048).
- Camera scanning could not be exercised (no camera / BarcodeDetector in the pane): the typed-code fallback was verified; the camera path is NOT VERIFIED.
- Not clicked in the browser: WO page coverage panel "Record this check", agreement edit / renew / deactivate / add-remove asset, provider
  edit / deactivate, portal staff pages (`/app/portal/accounts/`), client file attachments through the file picker, client "still not working"
  (reopen). These are covered by automated UI tests (`test_m10_contracts`, `test_m13_portal`).
- M09 / M04 / M11 browser re-check from the master spec was not repeated (their earlier QA-database browser evidence is in the Phase 4-6 reports).
