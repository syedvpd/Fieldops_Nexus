# FieldOps Nexus: final production-readiness and HPE acceptance audit (Phase 1, read-only)

Audit date 2026-10-04. Branch `ccr-a9c54b8b-icbtpz` @ `95dfc50`. **No source file, migration, configuration or test was changed.** Evidence base: the running application (Django on PostgreSQL 16, Redis, Celery worker + beat) driven by Playwright/Chromium at four viewports, HTTP/API probes, direct SQL, a real gunicorn run under the production settings, the complete test suite, and four parallel read-only static audits whose claims I re-verified at runtime wherever it was possible. Companion reports (all in this folder): `FINDINGS_REGISTER.md`, `M01_M15_TRACEABILITY_MATRIX.md`, `M01_M15_BROWSER_ACCEPTANCE.md`, `WORKFLOW_ACCEPTANCE_AUDIT.md`, `TENANT_RBAC_SECURITY_AUDIT.md`, `DATABASE_DOMAIN_AUDIT.md`, `API_AUDIT.md`, `CELERY_REDIS_EMAIL_AUDIT.md`, `DEPLOYMENT_READINESS_AUDIT.md`, `HPE_DAY90_ACCEPTANCE_AUDIT.md`, `AUDIT_EXECUTION_LOG.md`; raw evidence in `evidence/`, reproduction scripts in `tools/`.

## Executive status

| Module | Overall | Browser | Reason (finding IDs in `FINDINGS_REGISTER.md`) |
|---|---|---|---|
| M01 Site & Location | **PARTIAL** | PASS | zone move race, no lock (F-M19, static); everything exercised passed |
| M02 Asset Registry | **PARTIAL** | PARTIAL | REST site-scope gap reproduced (F-M07), site move not propagated (F-M08); financial fields absent (UNVERIFIED) |
| M03 Asset Hierarchy | **PARTIAL** | PARTIAL | retire/dispose leaves an undetachable tree (F-M06, reproduced) |
| M04 Preventive Maintenance | **FAIL (BLOCKER)** | PARTIAL | editing a schedule's recurrence silently stops generation (F-H01, reproduced); F-M05 |
| M05 Incident / Breakdown | **PARTIAL** | PARTIAL | reopen -> HTTP 500 (F-M01), request/WO divergence (F-M02), downtime left open (F-M03) |
| M06 Work Order Management | **PASS** | PASS | LOW findings only (labor duplicate guard, race, N+1) |
| M07 Technician Workspace | **PASS** | PASS | none above LOW |
| M08 Inspection & Checklist | **PARTIAL** | PARTIAL | required checklists not asset-scoped (F-M04, reproduced) |
| M09 Spare Parts & Inventory | **PASS** | PASS | LOW findings only; ledger invariant holds |
| M10 Warranty / AMC / Contract | **PARTIAL** | PASS | renewal alert consumed with no recipients (F-M13, static) |
| M11 SLA & Escalation | **PASS** | PASS | real elapsed-time breach/escalation verified; LOW findings (24/7 clock is INTENTIONAL) |
| M12 QR / Barcode | **PARTIAL** | PARTIAL | every scan 500s when Redis is down (F-M11) |
| M13 Client Portal | **PARTIAL** | PARTIAL | disabled client keeps read access (F-M09, reproduced); reopen path (F-M01) |
| M14 Operational Dashboards | **PARTIAL** | PARTIAL | low-stock KPI contradicts the stock list (F-M10, reproduced) |
| M15 Audit & Compliance | **PARTIAL** | PASS | DB-level immutability gap (F-H02, production exposure UNVERIFIED), JWT logins unaudited (F-M14), platform audit exposure (F-M15) |

| Dimension | Status |
|---|---|
| **Code audit** | **CONDITIONAL** (0 Critical, 2 High, 20 Medium; 746/746 tests; ruff, check, migrations, OpenAPI clean) |
| **Browser acceptance** | **CONDITIONAL** (all 15 modules exercised; ~400 recorded scenarios; defects listed above) |
| **Mandatory workflows** | **CONDITIONAL** (all five machines enforce valid/invalid/unauthorized/duplicate/bypass correctly; coupling defects at the seams) |
| **Tenant isolation** | **PASS** (no leak in any attack, both directions) |
| **RBAC** | **PASS**, with two MEDIUM exceptions that must be fixed or formally accepted: F-M07 (API site scope), F-M17 (Admin self-escalation) |
| **Security** | **CONDITIONAL** (F-H02 and the MEDIUM items; no XSS/CSRF/IDOR/open-redirect/upload/injection weakness found) |
| **Database** | **CONDITIONAL** (strong constraints, numbering, ledger; F-H02, F-M20; two lifecycle defects leave inconsistent rows) |
| **API** | **CONDITIONAL** (F-M07, F-M14, Redis 500s; schema validates; HPE alias routes undocumented) |
| **Celery/Redis** | **CONDITIONAL** (SLA/PM/renewal verified live and idempotent, auto-recovers; Redis outage = API outage; interval schedules reset on restart) |
| **Deployment** | **CONDITIONAL** (prod boot, HTTPS/HSTS, health, graceful shutdown, fail-fast verified; DB hardening conflicts with migrate-on-start; Docker, Supabase, SMTP, Python 3.12 UNVERIFIED) |
| **HPE Day-90** | **CONDITIONAL** (7/7 journeys pass on their main path; PM edit blocker; rework branch defects) |

## OVERALL: RELEASE CANDIDATE: FIXES REQUIRED

The platform is a real, working multi-tenant ERP, not a mock: persisted state machines, enforced RBAC and tenancy, real asynchronous jobs, real audit. It is **not** release-ready: one reproduced HIGH defect silently loses preventive maintenance, the audit-immutability promise is not enforced against the database owner (production state unverified), several request/work-order lifecycle paths end in inconsistent data or a 500, and the production DB-hardening design conflicts with how the service starts. None of these needs a redesign; all have small, local fixes (see `FINDINGS_REGISTER.md`).

---

## 1. What is genuinely PASS (with runtime evidence)

- **Tenant isolation**: 52 detail + 104 action endpoints, 70 lists x 14 principals, 78 pages x 12 roles, files, uploads, QR, dashboards, audit, exports, workflow POSTs: 0 leaks, no existence oracle.
- **Backend RBAC**: 11 roles x 18 write calls match the templates; client/auditor denied everything; audit rows cannot be patched/deleted via API even by the Owner; site-scoped planner confined to its site in UI and API.
- **Workflows**: all five state machines through the UI with DB/audit verification (full SR -> WO -> parts -> checklist -> labor -> review -> close loop; PM generation and duplicate prevention; asset lifecycle; part lifecycle with ledger invariant).
- **Real asynchronous behaviour**: SLA breach/warning/escalation at exact offsets from Celery beat; PM generated by beat; renewal alerts via the worker; worker/beat recover from a Redis outage by themselves.
- **M07/M09/M11 and the client portal journey** (mobile-first): technician workspace, stock ledger, SLA engine, client request -> confirmation -> closure -> evidence ZIP.
- **Security basics**: stored XSS/template injection inert across 15 pages, CSRF enforced, open-redirect safe, login lockout and no enumeration, logout invalidates sessions, upload validation, secure headers and CSP (0 violations in a 78-page crawl), HSTS/secure cookies/Host validation under prod settings.
- **Engineering hygiene**: 746 tests passed in one uninterrupted run (356 s; 93 % line coverage), `ruff` clean, `check --deploy` clean, no migration drift, fresh-DB migration (53 migrations), OpenAPI 0 warnings, graceful shutdown (2.2 s) and fail-fast supervision.
- **Responsive UI**: no horizontal overflow on any audited page at 1920x1080, 1440x900, 1024x768, 390x844 (15 module groups x 4 viewports).

## 2. Genuinely PARTIAL

M01-M05, M08, M10, M12-M15 as in the table; the PM lifecycle (F-H01/F-M05); request/work-order coupling; checklist gating; audit completeness (JWT login, downloads, SLA pause/resume not audited); portal access control; Celery operational robustness (Redis outage, interval beats).

## 3. Genuinely FAIL

- **F-H01** editing a PM schedule's recurrence silently stops generating work orders (reproduced with the real service layer: 1 WO in 10 weeks instead of 5; no error, no audit).
- **F-M01** reopen after a completed work order -> HTTP 500 and a dead end.
- **F-M02/F-M03** request confirmed/closed while the work order is in review/rework; downtime stays open after reject (inflated KPIs).
- **F-M04** unrelated required checklists forced onto other asset types (bogus data).
- **F-M06** retire/dispose leaves an undetachable asset tree.
- **F-M07** REST API lets a user write meter readings outside their permitted site (HTML denies).
- **F-M09** a disabled portal client keeps reading its history.
- **F-M10** low-stock KPI 0 vs 1 in the list it drills into.
- **F-M11** Redis down: every REST call and every QR scan returns 500; invitations saved without email.
- **F-M16** organization-switch dropdown blocked by the CSP.

## 4. What is missing

- Asset financial information (cost/vendor/currency): no field exists; HPE digest silent (UNVERIFIED requirement).
- Atomic "replace component" operation and queryable replacement history (L06); overnight operating calendars (L03).
- `IntegrationEvent`, `TechnicianProfile`, `Shift` as tables (documented equivalents; INTENTIONAL).
- Automated browser (Playwright) tests and any concurrency tests for M01-M03 (L57); a production-like CI job with Redis and the Docker image.
- Auditing of API sign-ins, attachment downloads, SLA pause/resume (F-M14, L30, L36).

## 5. Documentation mismatches only

- `docs/FINAL_RECONCILIATION_REPORT.md` says one clean full-suite run was never achieved: it **is** achievable (746 passed here).
- `docs/MODULE_STATUS.md` still lists M01-M08 browser acceptance as outstanding (now performed here); D-050 says QR throttling is not implemented (it is, and works); asset form help text says coverage "arrives with the warranty module" (C04).
- OpenAPI omits the 72 HPE-named alias routes (documented decision in code, undocumented for integrators; L55).
- `docs/module-verification` accuracy note lists steps "described from spec/code": the corresponding flows were executed here and worked; I did not diff individual button labels against the guides.

## 6. Intentionally out of scope / deliberate (INTENTIONAL I01-I11)

24/7 SLA clock; derived PM lifecycle and catch-up collapse; no segregation of duties between request/WO actors; no offline mode; functional-equivalent entities; hidden alias routes; revoked-QR warning page; Super Admin redirect to the platform console; stock adjustments without second approval; auto-activation of existing users on invitation; direct ACTIVE -> OUT_OF_SERVICE not allowed.

## 7. Remains UNVERIFIED (U01-U10)

Production Supabase role/privilege state and credentials hygiene; Docker image/compose stack; Python 3.12; Chrome/Edge/Firefox/Safari; physical phone camera; SMTP/Brevo delivery and Render health-probe behaviour; load/performance; race conditions identified only statically; htmx history cache after logout; asset financial-field requirement.

## 8. What must be fixed before HPE acceptance (ordered)

1. **F-H01** PM recurrence edit (+ regression test with existing cycles; surface skipped cycles).
2. **F-H02 + F-M18** TRUNCATE/ledger/history triggers, apply and verify the least-privilege role split on the production database, move migrations to a migrator step, rotate the Supabase admin password.
3. **F-M01, F-M02, F-M03** request <-> work-order <-> downtime lifecycle (guards, clean 409, void downtime).
4. **F-M07, F-M09, F-M17** authorization gaps (API site scope; disabled portal client; decide/record or enforce Admin escalation rules).
5. **F-M11, F-M12** Redis resilience (fail-open throttle/scan limiter, non-fatal `.delay()` with outbox) and crontab schedules.
6. **F-M04, F-M05** checklist applicability and PM-plan checklist enforcement.
7. **F-M10, F-M14, F-M15, F-M16, F-M06, F-M08, F-M13** KPI predicate, JWT audit, platform audit policy, CSP switcher, asset retire/move guards, renewal alert recipients.
8. Re-run the UNVERIFIED items (Docker/CI run, Supabase verification, Firefox/Edge, phone camera, SMTP, load) and add a Playwright smoke suite plus the missing concurrency tests to CI.

## 9. How this audit can be reproduced

`docs/audits/final/tools/` contains the seed adaptation, the Playwright helper library and the scenario scripts (`m01.py`, `m02.py`, `m03.py`, `m04.py`, `flow.py`), the API/IDOR/RBAC/crawl sweeps and the PM edit reproduction (`m04_edit_bug.py`). They need the audit environment described in `AUDIT_EXECUTION_LOG.md` (local PostgreSQL, Redis, the repo's `browser_qa` settings). Passwords are generated at seed time and never stored in the repository.
