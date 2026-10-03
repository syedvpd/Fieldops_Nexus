# Phase 2 plan and integration contracts: M05 Incident / Request, M06 Work Orders

Dependency direction: `core/tenancy/rbac/audit/files` -> M01 `sites` -> M02/M03 `assets` -> **M05 `incidents`** -> **M06 `workorders`** -> later modules (M07, M08, M09, M11, M14, M15).
`incidents.services` imports `workorders.services` (create a work order from an approved request); `workorders.services` calls back into `incidents.services.on_work_order_*` through a lazy import. Neither module writes the other's tables directly: the request status changes only through the hooks, the work-order rows only through `create_work_order`.

## Plan (as implemented)
- **Understanding:** HPE 7.2 M05 = failure reporting, severity, photos/files, asset linkage, downtime start/end, service impact, triage/approval. M06 = create, plan, prioritise, assign, dispatch, pause, complete, close with labor/material/time capture. Request chain NEW -> TRIAGED -> APPROVED/REJECTED -> WORK ORDER CREATED -> IN SERVICE -> RESOLVED -> CONFIRMED -> CLOSED; work-order chain DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN PROGRESS <-> ON HOLD -> COMPLETED -> SUPERVISOR REVIEW -> CLOSED.
- **Schema impact:** `core.DocumentSequence` (migration `core.0001`); `incidents.ServiceRequest`, `Downtime`, `ServiceRequestHistory` (`incidents.0001`); `workorders.WorkOrder`, `WorkOrderEvent`, `WorkOrderLabor`, `WorkOrderMaterial` (`workorders.0001`). Constraints: unique number per org; one live work order per request (partial unique index, cancelled/closed excluded); downtime end >= start; plan window ordered; labor hours in (0, 24]; material quantity > 0.
- **Permissions:** `incident.{view,create,update,attach,triage,approve,confirm,close,downtime.manage}`, `work_order.{view,view_assigned,create,update,plan,assign,dispatch,start,hold,complete,record,attach,review,close,cancel}`; all site-scoped; `work_order.view` implies `work_order.view_assigned` (D-037).
- **State machines:** `incidents/workflow.py`, `workorders/workflow.py` (D-035, D-036).
- **API:** `/api/v1/service-requests/` (+ `transition`, `create-work-order`, `history`, `downtime`, `evidence`), `/api/v1/work-orders/` (+ `transition`, `reassign`, `events`, `closure`, `labor`, `materials`, `evidence`). UI: `/app/incidents/…`, `/app/work-orders/…`.

## Request <-> work order contract
| Event | M05 effect | Implemented by |
|---|---|---|
| Request APPROVED + user with `work_order.create` | creates a DRAFT work order (type CORRECTIVE, priority from severity, same asset/site, `source_request`) and request -> WORK_ORDER_CREATED, atomically | `incidents.services.create_work_order_for_request` -> `workorders.services.create_work_order` |
| Work order START | request -> IN_SERVICE | `on_work_order_started` |
| Work order COMPLETE | request -> RESOLVED; open downtime ends (`end_source=work_order`); reporter notified | `on_work_order_completed` |
| Work order REJECT_REVIEW (rework) | request RESOLVED -> IN_SERVICE | `on_work_order_reworked` |
| Work order CANCEL | request -> APPROVED (a new work order may be created) | `on_work_order_cancelled` |
| Work order CLOSE | none (request stays RESOLVED until the requester side confirms) | - |
| Requester side | `confirm` / `reopen` (needs `incident.confirm`), then `close` (`incident.close`) | `incidents.services.transition` |

## Contracts for later modules
| Consumer | Needs | Use |
|---|---|---|
| M07 Technician Workspace | the technician's jobs and the execution actions | `workorders.selectors.work_orders_for(membership, org)` (assigned scope), `workorders.services.transition` / `record_labor` / `record_material` / `add_evidence`. M07 must not create a second work-order model. |
| M08 Checklists | closure prerequisite | add the check to `workorders.services.closure_blockers(wo)` (currently NOT enforced: OPEN item from HPE "closure requires checklist completion"). |
| M09 Inventory | parts for a work order | replace/extend `WorkOrderMaterial` (free text today, no stock movement) with issue/return movements owned by M09. |
| M04 PM | demand | create work orders with `workorders.services.create_work_order(..., work_type="PREVENTIVE")` (no `source_request`). |
| M11 SLA | response/resolution clocks | read `ServiceRequest.created_at / triaged_at / resolved_at` and `WorkOrder.dispatched_at / started_at / completed_at`, history/event tables; M11 adds its own tables. |
| M14 Dashboards | MTTR, downtime, open work | `incidents.Downtime`, `WorkOrder` timestamps and `WorkOrderLabor`; no stored aggregates. |
| M13 Portal / M12 QR | entry points | create requests through `incidents.services.create_request` (reporter = membership of the portal user once M13 defines it). |

## Open points (not silently decided)
- Asset status on work start/close ("may become UNDER MAINTENANCE per the approved rule"): no rule recorded, nothing changes automatically (D-035).
- Checklist gate for closure (M08), stock movements (M09), SLA pauses (M11): not part of Phase 2.
- Whether downtime should end at completion (implemented) or at closure.
