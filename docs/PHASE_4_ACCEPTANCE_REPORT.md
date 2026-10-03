# Phase 4 acceptance report: M09 Spare Parts & Inventory

This report does not claim Team Lead approval. Not applied to Supabase (the Team Lead did not ask; additive migrations `inventory.0001` and `workorders.0002` only, when requested). Decision record: D-042. Contract: `docs/integrations/inventory-workorders.md`. Manual guide: `docs/manual-tests/PHASE_4_MANUAL_TEST.md`.

## Status
**M09: IMPLEMENTED; automated verification PASS on local PostgreSQL 16; browser verified in the built-in pane against a local QA database (Docker Postgres `fieldops_qa`, not Supabase); database verified.** No known Critical / High defects.

## Automated results
| Check | Result |
|---|---|
| New tests | 67: `test_m09_inventory` 36 (services, ledger invariant, reservations, M06 hooks, DB guards, audit), `test_m09_concurrency` 7 (real threads), `test_m09_api` 12 (RBAC, tenant, IDOR, site scope), `test_m09_ui` 11, `test_migrations_phase4` 1 |
| Full regression | 433 passed without the four fresh-DB migration modules (7m26s) + migration modules run separately (see below); total suite 439 |
| `ruff check src tests` | clean |
| `manage.py check` | no issues |
| `makemigrations --check --dry-run` | no drift (also on a fresh database in `test_migrations_phase4`) |
| OpenAPI (`spectacular --validate --fail-on-warn`) | 0 warnings, 0 errors |
| Migrations | `inventory.0001` (new app), `workorders.0002` (nullable FK `WorkOrderMaterial.part_line`; no existing row touched) |

## Feature matrix
| Feature | Code | Test | API | DB | UI | Browser |
|---|---|---|---|---|---|---|
| Part catalogue CRUD / deactivate | yes | yes | yes | yes | yes | yes |
| Warehouses (site-bound, deactivate refused with stock) | yes | yes | yes | yes | yes | yes |
| Receive / adjust / levels / transfer | yes | yes | yes | yes | yes | receive yes; others via tests |
| Reserve / release / issue / return / consume / reconcile / cancel | yes | yes | yes | yes | yes | reserve, issue, return, bad-quantity rejections yes |
| Ledger invariant (balance = sum of movements, reserved = ACTIVE holds) | yes | `assert_ledger_consistent` after every scenario | n/a | check constraints | n/a | SQL spot check |
| Concurrency (last unit, oversell, reserve, same line, first receipt, opposite transfers) | yes | yes | n/a | row locks | n/a | n/a |
| M06: closure blocker, close reconciles, cancel releases / refuses | yes | yes | yes | yes | n/a | not exercised in browser |
| M07: technician requests / records usage; never touches stock | yes | yes | n/a | yes | yes | request yes (technician); consume via tests |

## Required scenarios
- stock 10, issue 2 -> 8, return 1 -> 9, issue 10 rejected, stock stays 9 and no phantom movement: `test_stock_10_issue_2_return_1_then_issue_10_is_rejected`.
- last unit, two concurrent issues: exactly one succeeds, final stock 0 (never -1): `test_two_concurrent_issues_of_the_last_unit_exactly_one_succeeds`; 6 issuers on 3 units -> 3 succeed.
- on_hand 10, reserved 4, available 6, reserving 7 refused: `test_reservation_on_hand_reserved_available_and_cannot_overreserve`.

## Security matrix (all PASS)
Alpha vs Beta part / warehouse / balance / movement / line (404 on every verb); guessed and malformed UUIDs; user without permission (technician, planner, auditor) cannot receive / issue / adjust / transfer; technician cannot browse stock or reserve / issue / return; technician of another job gets 404; wrong site warehouse (400 `wrong_site`), line committed to another warehouse (409), cross-tenant part / warehouse in every service; zero, negative, non-numeric, over-precise, huge quantities; excess issue / consume / return; inactive part and warehouse (also when the caller holds a stale object); site-scoped stores user limited to its sites; suspended member locked out; CSRF enforced; `next` redirect only to local `/app/` paths.

## Defects found and fixed during the phase
| # | Severity | Defect | Fix + regression test |
|---|---|---|---|
| 1 | High | `transfer` locked the destination balance before the ordered lock of both rows: opposite transfers deadlocked (PostgreSQL `deadlock detected`) | existence ensured without locking, both rows locked in primary-key order; `test_opposite_transfers_do_not_deadlock_and_conserve_stock` |
| 2 | Medium | Workspace consume view answered a foreign / guessed line id with HTTP 500 | `or404` wrapper; `test_workspace_part_endpoints_are_scoped_to_my_jobs` |
| 3 | Medium | Inactive part / warehouse check trusted the caller's (possibly stale) instance | checks read the flag from the database; `test_inactive_part_and_warehouse_are_rejected` |

## Browser evidence (built-in pane, local QA database, stores / technician users)
Created part and warehouse and received 10 through the forms; technician requested 4 in My Jobs and was refused (403) on /app/inventory/stock/; stores reserved 3 (on hand 10, reserved 3), issued 4 (on hand 6, reserved 0), a return of 99 was refused with a message, a return of 1 gave on hand 7. Console: one 403 (EXPECTED, the technician's forbidden page); network: all other requests 200. No horizontal page scroll at 1920x1080, 1366x768, 768x1024, 390x844 on parts, stock, movements, receive and the work-order parts page. Database: movements RECEIPT +10, RESERVE (reserved +3), ISSUE (-4 on hand, -3 reserved), RETURN +1 = balance 7 / 0; line ISSUED 4 / 0 / 1; no cross-tenant movement; audit rows with the actor for every operation.

## Remaining decisions / limits
- CLARIFICATION REQUIRED: negative adjustments need no second approver; no costing / valuation; reorder is information only (D-042).
- Technician consumption through the browser and the M06 closure of a work order with parts were verified by automated tests, not in the pane.
- Phase 1-3 browser audit and Supabase application remain owed (see MODULE_STATUS).
