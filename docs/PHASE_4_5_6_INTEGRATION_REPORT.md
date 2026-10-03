# Phases 4 + 5 + 6 integration report (M09 Inventory, M04 Preventive Maintenance, M11 SLA & Escalation)

This report does not claim Team Lead approval. Results are from automated tests on local PostgreSQL 16 (Docker) and browser verification in the built-in pane on a local QA database.

## Verification summary
| Check | Result |
|---|---|
| Full regression (`pytest tests`, fresh test database) | **553 passed** in 17 min; plus `tests/test_integration_p456.py` 2 passed (555 total) |
| `ruff check src tests` | clean |
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | no drift |
| OpenAPI `spectacular --validate --fail-on-warn` | 0 warnings, 0 errors (two warnings caused by M11 - duplicate serializer name, unnamed enum - were fixed) |

## Wiring (who calls whom)
| From -> to | Mechanism | Evidence |
|---|---|---|
| M04 -> M06 | `maintenance.services.generate_cycle` -> `workorders.services.create_work_order(source_type="PREVENTIVE_MAINTENANCE", source_id)` + `plan` transition | `test_m04_*`, integration test |
| M04 -> M08 | plan `checklist_key` -> `checklists.services.required_templates` (completion guard, pending counts) | `test_m04_maintenance`, integration test (completion refused until the checklist is done) |
| M09 -> M06 / M07 | part lines, reservation, issue, consume writes `WorkOrderMaterial`; closure blocker; close reconciles; cancel releases | `test_m09_*`, integration test |
| M06 -> M09 | `on_work_order_closed/_cancelled` hooks in `workorders.services.transition` | `test_m09_inventory` |
| M05 / M06 -> M11 | hooks `on_request_created/updated/status_changed`, `on_work_order_created/changed` | `test_m11_sla`, integration tests |
| M11 -> notifications | `notifications.services.notify` (role / assignee recipients, after the event row exists) | `test_m11_sla`, QA database |
| M11 -> audit | `audit.record` for every state change | `test_m11_sla`, QA database |
| Celery | beat: `generate-due-maintenance` (15 min), `monitor-sla` (60 s) | `test_m04_maintenance`, `test_m11_sla` |

## Combined journey (automated, real services, no direct row edits)
`tests/test_integration_p456.py::test_pm_order_flows_through_checklist_inventory_and_sla`: org / site / asset -> SLA profile for preventive work orders -> PM plan with a required checklist -> schedule due -> PM work order (PLANNED, source = PM, SLA tracking started from `created_at`) -> planner assigns (SLA response met) -> dispatch -> start -> technician requests a part -> stores reserves and issues -> technician consumes (M06 material row written) -> hold (SLA paused) -> resume (due time shifted) -> completion refused until the M08 checklist is done -> inspection completed -> labor + completion -> supervisor review -> close -> SLA resolution met, no breach, audit rows once each, stock ledger consistent, no closure blockers.
`test_incident_to_work_order_runs_on_the_requests_clock`: incident -> triage (response met) -> approve -> work order from the request (no second SLA clock) -> overdue resolution breached by the monitor.

## Browser verification (built-in pane, local QA database `fieldops_qa`)
- M09 (Phase 4): part / warehouse forms, receive, reserve, issue, technician request, RBAC refusal.
- M04 (Phase 5): plan -> meter schedule -> scheduler -> WO with PM source -> duplicate guard -> four viewports.
- M11 (Phase 6): profile with tiny targets, HIGH incident, `Run check now` through warning, response breach, resolution breach and level-2 escalation, repeat runs create nothing, acknowledge in the UI, four viewports (1920x1080, 1366x768, 768x1024, 390x844), no console errors.
- Console / network classification: no UNEXPECTED errors. Expected: 403 / 404 pages for the negative checks.

## Database verification (local QA database)
No duplicate breaches or events; no cross-tenant pairs; one cycle per PM work order; stock balances equal the sum of their movements (`assert_ledger_consistent` after every scenario in tests, SQL spot checks in the QA database).

## Defects found during Phases 4-6 (all fixed with regression tests)
High: 1 (transfer deadlock, M09). Medium: 4 (consume view 500 on a foreign id; stale-instance inactive checks; `.unscoped()` in a PM task; SLA pause synced after the target check). Low: 3. Open Critical / High: none known.

## Open decisions for the Team Lead
1. M04 missed-cycle policy (collapse into one work order) - OUR decision (D-043).
2. M09 negative adjustments (no second approver), no costing (D-042).
3. M11 pause states and business hours: wall-clock only (D-044).
4. Phase 1-3 browser audit remains owed.

## Supabase
See the section appended below when the migrations were applied.
