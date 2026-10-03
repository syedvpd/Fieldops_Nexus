# Module status

Legend: NOT STARTED / IN PROGRESS / VERIFIED (code + tests + live check) / APPROVED (human manual test passed).
Nothing is APPROVED until the Team Lead completes the manual test for that phase.

| Phase | Scope | Status | Evidence |
|---|---|---|---|
| 0 | Foundation (tenancy, RBAC, auth, audit, notifications, files, API/UI shell, Celery/Redis, Docker, CI) | **IMPLEMENTED; login incident FIXED and re-verified (automated + real-browser); awaiting Team Lead manual approval** | `docs/INCIDENT_2026-10-03_LOGIN.md` (root cause, fix, 18 regression tests, browser acceptance); 128 tests on PostgreSQL 16; ruff clean; 32 migrations on fresh local DB and Supabase; Docker stack + `scripts/smoke_stack.py`; manual guide `docs/manual-tests/PHASE_0_MANUAL_TEST.md` (corrected). Earlier "PASS" for login in `CHECKPOINT_PHASE_0.md` is superseded by the incident record |
| 1 | M01 Site & Location, M02 Asset Registry, M03 Asset Hierarchy | NOT STARTED | |
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
- Site-scoped roles need the Site model: added in Phase 1 (`MembershipRole.site`).
- M15 reports/exports (audit export CSV/XLSX/PDF) and org-level login-history views: Phase 9.
- Production deploy (web/worker) not yet created: needs a Git remote; Redis for prod pending (Render free Key Value quota already used).
- Prod Supabase has no schema yet; `migrate` must be run with the DB password supplied by the Team Lead.
- LOW: 8 drf-spectacular warnings (untyped `{id}` path params on non-model ViewSets; `MeView` lacks a serializer). Schema still generates; fix with `OpenApiParameter`/serializer annotations before Day-30 docs freeze.
- No browser-matrix (Chrome/Edge/Firefox) or load testing yet (Final phase).
