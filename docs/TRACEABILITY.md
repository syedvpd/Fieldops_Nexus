# Traceability: HPE-PRD-2026-FOPS02

HPE module numbers are kept exactly as in the Blueprint. "HPE" = explicit in the HPE document; "Impl" = FieldOps implementation decision.

## Module -> Django app -> phase
| ID | Module | App (planned) | Phase |
|---|---|---|---|
| M01 | Site & Location Master | `sites` | 1 |
| M02 | Asset Registry | `assets` | 1 |
| M03 | Asset Hierarchy | `assets` (hierarchy) | 1 |
| M04 | Preventive Maintenance | `maintenance` | 5 |
| M05 | Incident / Breakdown | `incidents` | 2 |
| M06 | Work Order Management | `workorders` | 2 |
| M07 | Technician Workspace | `technician` | 3 |
| M08 | Inspection & Checklist Engine | `inspections` | 3 |
| M09 | Spare Parts & Inventory | `inventory` | 4 |
| M10 | Warranty / AMC / Contract | `coverage` | 7 |
| M11 | SLA & Escalation | `sla` | 6 |
| M12 | QR / Barcode | `qr` | 8 |
| M13 | Client / Requester Portal | `portal` | 8 |
| M14 | Operational Dashboards | `dashboards` | 9 |
| M15 | Audit & Compliance | `audit` (extends) | 9 |

## Review gates (mandatory acceptance milestones, in addition to our phases)
| Gate | HPE deliverables | Our phases covering it | Status |
|---|---|---|---|
| Day 15 | repo baseline, README, architecture notes, branch strategy, schema/migrations, auth skeleton, CI | Phase 0 | evidence ready (needs Git remote + tag) |
| **Day 30** (30-35% scope) | Auth/RBAC; site hierarchy; asset registry; asset hierarchy; service request; WO core; checklist templates; DB schema; CI/CD; GitHub tag | Phase 0 + 1 + 2 + M08 templates (Phase 3 start) | Phase 0 done |
| Day 45 | new modules, async jobs, API docs delta, coverage, defect list | Phases 3-4 | |
| **Day 60** (65-75%) | PM scheduler; assignment/dispatch; technician workspace; inspections; inventory reservations/issues/returns; SLA engine; notifications; beta dashboards | Phases 3, 4, 5, 6 | |
| Day 75 | hardening build | Final hardening | |
| **Day 90** (100%) | Warranty/AMC; client portal; QR; analytics; audit/export; security hardening; performance; tests; deployment; KT docs | Phases 7, 8, 9 + Final | |

## Day-30 gate, item by item (HPE section 9: "Asset persistence, role boundaries, lifecycle state control, schema quality, code governance")
| HPE Day-30 deliverable | Module | Phase | Status |
|---|---|---|---|
| Auth / RBAC | foundation | 0 | DONE (110 tests; manual approval pending) |
| Site hierarchy | M01 | 1 | not started |
| Asset registry | M02 | 1 | not started |
| Asset hierarchy | M03 | 1 | not started |
| Service request | M05 | 2 | not started |
| Work-order core | M06 | 2 | not started |
| Checklist templates | M08 (templates part only) | 3, pulled forward right after Phase 2 | not started |
| DB schema (clean, migrations, constraints) | all | every phase | Phase 0 schema done and applied to fresh local DB and Supabase |
| CI/CD | foundation | 0 | workflow written; not yet run on GitHub (no remote) |
| GitHub tag | governance | 0/1 | blocked: no Git remote yet (local repo only) |
Day-30 target is 30-35% of scope; schedule risk: Phases 1-2 plus M08 templates must land before the Day-30 review build.

## Day-90 acceptance journeys -> E2E tests (to be written as `tests/e2e/test_journey_N.py`)
1. Register site + asset hierarchy, show status/change history. (Ph 1)
2. PM plan -> scheduler generates WO without duplicates. (Ph 5)
3. Assign technician -> checklist -> parts -> labor -> complete WO. (Ph 3-4)
4. High-priority request -> SLA response/resolution timers -> escalation. (Ph 6)
5. Inventory issue/return -> stock movements -> WO linkage. (Ph 4)
6. QR/barcode -> asset -> service event. (Ph 8)
7. Client request closed only after technician completion + confirmation; audit + dashboard. (Ph 8-9)

## Foundation requirements -> evidence (Phase 0)
| Requirement | Source | Evidence |
|---|---|---|
| Python/Django/DRF/PostgreSQL/Redis/Celery | HPE 2 | Django 5.2 LTS (>= 4.2), DRF, PG16, Redis 7, Celery 5.6; live stack verified |
| Backend-enforced RBAC | HPE 1.2/2.2 | `tests/test_rbac.py` (matrix, unmapped=deny, owner rules) |
| Auditable, append-only audit | HPE 2.2 | `tests/test_audit.py` incl. DB trigger |
| Login throttling, CSRF, secure sessions | HPE 2.2 | `tests/test_login_integration.py` (18: CSRF-enforced PBKDF2 browser flow, per user+IP lockout with bystander unaffected, proxy IP, spoofing), security headers test; real-browser acceptance in `docs/INCIDENT_2026-10-03_LOGIN.md` |
| Upload validation | HPE 2.2 | `tests/test_core.py` upload tests |
| OpenAPI | HPE 2 | `/api/v1/schema/`, `/api/v1/docs/`; schema test |
| Health endpoints, structured logging | HPE 2 | `/health/live|ready`, JSON logs with request id |
| Docker, CI/CD | HPE 2 | `Dockerfile`, `docker-compose.yml`, `.github/workflows/ci.yml` |
| Multi-tenant SaaS, Super Admin, org onboarding | Impl (Blueprint 02) | `tests/test_onboarding_auth.py`, `test_tenant_isolation.py` |
| Role templates, site-scoped roles | Impl (Blueprint 06) | `rbac/role_templates.py`; site scope in Phase 1 |
