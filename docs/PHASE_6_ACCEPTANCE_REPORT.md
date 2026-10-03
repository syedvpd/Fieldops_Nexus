# Phase 6 acceptance report: M11 SLA & Escalation

This report does not claim Team Lead approval. Not applied to Supabase (not requested; additive migration `sla.0001` only, together with `inventory.0001`, `workorders.0002/0003`, `maintenance.0001`, when requested). Decision record: D-044. Contract: `docs/integrations/sla-requests-workorders.md`. Manual guide: `docs/manual-tests/PHASE_6_MANUAL_TEST.md`.

## Status
**M11: IMPLEMENTED; automated verification on local PostgreSQL 16 (final regression figure in `docs/PHASE_4_5_6_INTEGRATION_REPORT.md`); browser verified in the built-in pane on a local QA database (`fieldops_qa`, not Supabase); database verified.** HPE CONFIRMED scope only: response / resolution targets by priority, automated escalation, breach tracking, supervisor alerts. Pause states and business-hours semantics are OUR decisions (wall-clock only).

## Automated results
| Check | Result |
|---|---|
| New tests | `test_m11_sla` 25 (controllable clock: start, T0..T4 journey, duplicates, Celery, retry, pause / resume, work-order SLA, configuration limits, append-only), `test_m11_api_ui` 9 (RBAC, tenant, IDOR, site scope, metrics, buttons, forms, open-redirect guard), `test_m11_concurrency` 2 (6 racing monitors; 5 racing acknowledgers), `test_migrations_phase6`, `test_integration_p456` 2 (M04 -> M06 -> M08 -> M09 -> M11 and incident -> work order on the request's clock) |
| `ruff check src tests` | clean |
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | no drift |
| Migrations | `sla.0001` (new app, 6 tables, check / unique constraints) |

## Feature matrix
| Feature | Code | Test | API | DB | UI | Browser |
|---|---|---|---|---|---|---|
| Profiles / targets / rules (limits, validation, audit) | yes | yes | yes | yes | yes | profile page + forms |
| Tracking started from persisted `created_at` (M05, M06 hooks) | yes | yes | yes | yes | yes | yes |
| Warning -> breach -> escalation -> notification | yes | yes | n/a | yes | yes | yes (full T0..T4) |
| Pause / resume (configured states only) | yes | yes | n/a | yes | yes | via tests |
| Idempotency (unique breach / event, row lock) | yes | yes + threads | n/a | constraints | n/a | repeated `Run check now` = 0/0/0 |
| Acknowledge breach (site-scoped RBAC) | yes | yes | yes | yes | yes | yes |
| Metrics for M14 (`/api/v1/sla-metrics/`) | yes | yes | yes | n/a | summary cards | yes |
| SLA panels on request and work-order pages | yes | yes | n/a | n/a | yes | request page via tests |

## Browser evidence (built-in pane, local QA database)
Service manager created a HIGH incident profile (respond 1 min, resolve 3 min, warn 50 %) with four rules through the services; a HIGH incident was reported. `Run check now` produced: warning (0.8 min), response breach (after 1 min), resolution warning, resolution breach, then escalation level 2 once 1 minute had passed; further runs reported 0 / 0 / 0. Operations manager acknowledged a breach in the UI. Four viewport sizes (1920x1080, 1366x768, 768x1024, 390x844) rendered without horizontal page scroll; console: no errors.

## Database evidence (QA database)
Events: STARTED 1, WARNING 2, BREACHED 2, ESCALATED 1, ACKNOWLEDGED 1. Breaches: RESPONSE open, RESOLUTION acknowledged at level 2. Notifications: operations manager 3 (1 warning, 2 critical), service manager 1 (escalation). Audit: `sla.tracking_started`, `sla.breach_detected` x2, `sla.breach_acknowledged`, plus configuration actions. Duplicate breaches 0; cross-tenant breach / tracking pairs 0.

## Security matrix (all PASS in tests)
Alpha vs Beta tracking / profile / breach (404 on every verb); foreign role id in a rule (404 / rejected); technician no SLA access; operations manager cannot manage profiles or run the monitor; supervisor / planner cannot acknowledge; site-scoped member sees only their site; `next` parameter cannot redirect off-site.

## Defects found and fixed during the phase
| # | Severity | Defect | Fix + regression test |
|---|---|---|---|
| 1 | Medium | A target met right after a resume was judged against the unshifted due time (the pause was synced after the target check) | pause / resume is synced first in both hooks; `test_pause_only_for_configured_states_and_due_times_shift` |

## Remaining decisions / limits
- TEAM LEAD DECISION D-047 (2026-10-03): 24/7 elapsed clock minutes, no business hours. Pause states per profile remain OUR IMPLEMENTATION DECISION (D-044).
- Not implemented: contract / customer SLAs (M10), customer SLA view (M13), dashboards (M14), e-mail / SMS channels.
- Pause / resume and the work-order SLA were verified by automated tests, not in the pane.
