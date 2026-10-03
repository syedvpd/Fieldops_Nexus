# Contract: M09 Inventory <-> M06 Work Orders <-> M07 Workspace

Owner of stock truth: **M09** (`apps/inventory`). Owner of the work-order lifecycle: **M06** (`apps/workorders`). M07 (`apps/workspace`) only orchestrates. Decision: D-042.

## Data
- `inventory.WorkOrderPart` = part requirement of a work order (requested / issued / consumed / returned, status, warehouse). One line per (work order, part).
- `inventory.PartReservation` = stock-side hold of one line (1:1). Sum of ACTIVE holds per (warehouse, part) equals `StockBalance.reserved`.
- `inventory.StockMovement` = append-only ledger; carries `work_order` and `part_line` for work-order movements.
- `workorders.WorkOrderMaterial.part_line` (nullable FK, `workorders.0002`): set only by M09 consumption. NULL rows are the Phase 2 free-text lines (non-stocked consumables, move no stock); they are unchanged.

## Calls
| Direction | Call | Rule |
|---|---|---|
| M07 / UI / API -> M09 | `inventory.services.request_part / reserve / release / issue / return_stock / consume / reconcile / cancel_line` | permission for the work order's site checked by the caller, everything else (tenant, site == warehouse site, state, quantities, locks, ledger, audit) by the service |
| M09 -> M06 | `workorders.services.record_material(..., part_line=line)` from `consume` | M06 keeps its own assignee / state rule (`assert_recordable`); M09 never writes `WorkOrderMaterial` directly |
| M06 -> M09 | `inventory.services.part_blockers(wo)` inside `closure_blockers` | issued but not consumed / returned parts block closure |
| M06 -> M09 | `on_work_order_closed(wo)` after CLOSE | releases reservations, cancels never-issued lines, reconciles finished lines |
| M06 -> M09 | `on_work_order_cancelled(wo)` after CANCEL | releases reservations; refuses (whole transition rolls back) while issued stock is outstanding |

M09 reads the work-order state; it never changes it. State gates: request while DRAFT..ON_HOLD, reserve / issue while PLANNED..ON_HOLD, consume while IN_PROGRESS / ON_HOLD / COMPLETED / SUPERVISOR_REVIEW, return from PLANNED through SUPERVISOR_REVIEW.

## Locking
Work order -> part line -> reservation -> balance (two balances in primary-key order). M06's `transition` locks the work order first and calls the hooks afterwards, so both modules take locks in the same order.

## Visibility
A technician sees the catalogue and the part lines of the work orders they can see (M06 visibility); never stock levels, movements or reservations (`inventory.view`, site-scoped, required for those).
