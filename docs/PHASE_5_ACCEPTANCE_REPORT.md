# Phase 5 acceptance report: M04 Preventive Maintenance

This report does not claim Team Lead approval. Not applied to Supabase (not requested; additive migrations `workorders.0003` and `maintenance.0001` only, when requested). Decision record: D-043. Contract: `docs/integrations/maintenance-workorders.md`. Manual guide: `docs/manual-tests/PHASE_5_MANUAL_TEST.md`.

## Status
**M04: IMPLEMENTED; automated verification on local PostgreSQL 16 (see the final regression figure in `docs/PHASE_4_5_6_INTEGRATION_REPORT.md`); browser verified in the built-in pane on a local QA database (`fieldops_qa`, not Supabase); database verified.**

## Automated results
| Check | Result |
|---|---|
| New tests | `test_m04_recurrence` (pure date / meter maths), `test_m04_maintenance` (services, generation, duplicates, checklist, reminders, Celery), `test_m04_concurrency` (real threads), `test_m04_api`, `test_m04_ui`, `test_migrations_phase5`, plus one backfill test in `test_phase2_rules` |
| `ruff check src tests` | clean |
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | no drift (also on a fresh database in `test_migrations_phase5`) |
| Migrations | `workorders.0003` (nullable `source_type` / `source_id`, backfill of request-sourced orders, pair check, partial unique per PM source), `maintenance.0001` (new app) |
| Earlier full run | 513 passed, 7 failed; all 7 were self-inflicted (see defects) and fixed |

## Feature matrix
| Feature | Code | Test | API | DB | UI | Browser |
|---|---|---|---|---|---|---|
| Plans (per asset, priority, checklist) | yes | yes | yes | yes | yes | yes |
| Time schedules (daily ... yearly, interval, lead days, window, reminder) | yes | yes | yes | yes | yes | yes |
| Meter schedules (interval on the M02 meter) | yes | yes | yes | yes | yes | yes (1200 h, every 500, next 1500) |
| Generation only through the M06 service (PREVENTIVE, source) | yes | yes | yes | yes | yes | yes |
| Duplicate prevention (row lock + unique sequence + unique PM source + idempotent tasks) | yes | yes + threads | n/a | constraints | n/a | yes (guard) |
| Missed cycles collapsed (OUR DECISION) | yes | yes | n/a | yes | n/a | n/a |
| M08 plan checklist becomes a required checklist | yes | yes | n/a | yes | n/a | via tests |
| Disable / re-enable without backlog | yes | yes | yes | yes | yes | yes |
| Celery beat `generate_due_maintenance` (15 min) and `generate_schedule` | yes | yes | n/a | n/a | n/a | n/a |

## Security matrix (all PASS)
Alpha vs Beta plan / schedule / cycle (404 on every verb); site-scoped users see only their sites; roles without `maintenance.create|update|generate` get 403; suspended organization, retired asset and inactive meter never generate.

## Defects found and fixed during the phase
| # | Severity | Defect | Fix + regression test |
|---|---|---|---|
| 1 | Medium | Task `generate_schedule` used `.unscoped()` (caught by the tenant guard test) | takes `organization_id`, runs inside `tenant_context` |
| 2 | Low | `pending_required_counts` mixed UUID and str keys | normalized to str |
| 3 | Low | OpenAPI enum name collision on the plan serializer | uses `WorkOrder.Priority.choices` |
| 4 | Test | six migration tests failed while the SLA app was added without a migration | migration generated; re-verified in the final run |

## Browser evidence (built-in pane, local QA database)
Plan -> meter schedule -> scheduler run -> work order shows its PM source -> second run generates nothing -> four viewport sizes checked. Database: one cycle per work order, no duplicates, no orphans.

## Remaining decisions / limits
- CLARIFICATION REQUIRED: the missed-cycle COLLAPSE policy (one order for the latest occurrence) is our decision.
- Not implemented: floating cadence from the completion date, per-schedule assignee defaults, spare-part templates on plans.
