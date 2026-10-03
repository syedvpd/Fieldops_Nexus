# Contract: M04 Preventive Maintenance -> M06 Work Orders (+ M02 meters, M01 calendars, M08 checklists)

M04 (`apps/maintenance`) creates maintenance DEMAND. The work order is owned by M06 for its whole life; M04 never edits it after creation. Decision: D-043.

## Calls
| Direction | Call | Rule |
|---|---|---|
| M04 -> M06 | `workorders.services.create_work_order(..., work_type="PREVENTIVE", source_type="PREVENTIVE_MAINTENANCE", source_id=<cycle id>, planned_start/end, priority, estimated_hours)` | the only way a PM order is created; M06 validates tenant, asset state, window |
| M04 -> M06 | `workorders.services.transition(wo, action="plan", actor=None-or-user, membership=None)` | puts the new order into PLANNED (the window is set); assignment, dispatch, execution, closure stay M06 |
| M04 <- M02 | `AssetMeter` + `AssetMeterReading` (latest reading by `read_at`, `created_at`) | meters and the monotonic-reading rule belong to M02; M04 stores no readings |
| M04 <- M01 | `Site.timezone` (due dates are site-local calendar dates) and the default `OperatingCalendar` (planned window moves to the next working day; the due date does not) | |
| M08 -> M04 | `maintenance.services.required_checklist_key(wo)` (lazy import) called from `checklists.services.required_templates` | the plan's checklist becomes required for that order; M08 decides blockers and execution |
| M06 -> M04 | none | the cycle's PM state is derived from the work-order status (`selectors.cycle_state`) |

## Work-order source
`WorkOrder.source_type` / `source_id` (migration `workorders.0003`): `SERVICE_REQUEST` (id = request, backfilled from `source_request`), `PREVENTIVE_MAINTENANCE` (id = `MaintenanceCycle.id`), blank = created directly. DB: type and id come together; `UNIQUE (source_id) WHERE source_type = PREVENTIVE_MAINTENANCE`.

## Idempotency
1. `generate_cycle` locks the schedule row; a concurrent worker waits and then finds the occurrence already generated.
2. `UNIQUE (schedule, sequence)` on cycles and the partial unique index on work orders make a duplicate impossible even if (1) is bypassed.
3. Tasks do nothing when nothing is due, so retries / repeated beats are harmless. A failure rolls back cycle + order + schedule advance and is recorded in `last_error`.
Missed occurrences are collapsed into one order (`skipped` counts the rest). Disabled plan / schedule, suspended organization, retired asset or inactive meter: no generation.
