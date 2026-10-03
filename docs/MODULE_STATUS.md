# Module status

Legend: NOT STARTED / IN PROGRESS / VERIFIED (code + tests + live check) / APPROVED (human manual test passed).
Nothing is APPROVED until the Team Lead completes the manual test for that phase.

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| 0 | Foundation (tenancy, RBAC, auth, audit, notifications, files, API/UI shell, Celery/Redis, Docker, CI) | **IMPLEMENTED; login incident FIXED and re-verified (automated + real-browser); awaiting Team Lead manual approval** | `docs/INCIDENT_2026-10-03_LOGIN.md` (root cause, fix, 18 regression tests, browser acceptance); 128 tests on PostgreSQL 16; ruff clean; 32 migrations on fresh local DB and Supabase; Docker stack + `scripts/smoke_stack.py`; manual guide `docs/manual-tests/PHASE_0_MANUAL_TEST.md` (corrected). Earlier "PASS" for login in `CHECKPOINT_PHASE_0.md` is superseded by the incident record |
| 1 | M01 Site & Location, M02 Asset Registry, M03 Asset Hierarchy (+ site-scoped RBAC) | **IMPLEMENTED; automated checks pass; browser acceptance audit PARTIAL; awaiting Team Lead approval** | Commits `f21c745`, `511d559`. 271 tests on PostgreSQL 16 (unit, API, RBAC, tenant/IDOR, site scope, UI, fresh-DB migration, drift), ruff clean, OpenAPI 0 warnings. Migrations `sites.0001`, `assets.0001`, `rbac.0002` applied to Supabase schema `fieldops` (35 migrations). Real-browser evidence so far: M01 site create/edit/lifecycle and a 4-level location tree (UI = API = DB = audit); earlier throwaway-stack pass of calendars/contacts, asset create/edit/status/history, hierarchy tree, scoped-user IDOR, 375px overflow. NOT yet browser-verified: M02 documents/meters/filters, M03 re-parent/cycle/self-parent, cross-tenant and read-only roles, 4-size responsive sweep, console/network review. Manual guide `docs/manual-tests/PHASE_1_MANUAL_TEST.md` |
| 2 | M05 Incident/Request + M06 Work Orders | NOT STARTED | |
| 3 | M08 Checklist/Inspection, M07 Technician Workspace | NOT STARTED | |
| 4 | M09 Inventory | NOT STARTED | |
| 5 | M04 Preventive Maintenance | NOT STARTED | |
| 6 | M11 SLA & Escalation | NOT STARTED | |
| 7 | M10 Warranty/AMC/Contract | NOT STARTED | |
| 8 | M12 QR + M13 Client Portal | NOT STARTED | |
| 9 | M14 Dashboards + M15 Audit/Compliance | NOT STARTED | |
| Final | HPE seven-journey acceptance, security/perf hardening, KT docs | NOT STARTED | |

## Phase 0 known gaps (carried forward)
- Site-scoped roles: DONE in Phase 1 (`MembershipRole.site`, D-025).
- M15 reports/exports (audit export CSV/XLSX/PDF) and org-level login-history views: Phase 9.
- Production deploy (web/worker) not yet created: needs a Git remote; Redis for prod pending (Render free Key Value quota already used).
- Supabase `fieldops` schema has all migrations through Phase 1 (35) plus persistent QA organizations/users (D-031). Production web/worker hosting is still pending.
- OpenAPI warnings: FIXED in Phase 1 (schema generates with 0 warnings).
- No browser-matrix (Chrome/Edge/Firefox) or load testing yet (Final phase).

## Phase 1 known gaps
- No asset document removal/versioning; no QR/labels (M12); warranty is a free-text reference (M10); no bulk import/export (M15).
- Super Admin password in Supabase must be set by the Team Lead (`changepassword`); the QA test-user passwords were echoed once into a chat transcript and should be rotated before any real deployment.
- Direct ACTIVE -> OUT_OF_SERVICE is intentionally not allowed (D-027): needs Team Lead confirmation.
