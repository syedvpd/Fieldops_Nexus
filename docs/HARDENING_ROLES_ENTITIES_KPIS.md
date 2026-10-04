# Hardening notes: role templates, HPE entity equivalents, dashboard formulas (2026-10-03)

Separate file on purpose: `DECISIONS.md`, `TRACEABILITY.md` and `docs/audits/` were being edited by the parallel hardening session, so
this note carries no edits to them. Fold the two tables below into `DECISIONS.md` / `TRACEABILITY.md` after that session finishes.

## 1. Role templates versus the real permission catalog (item 4)
Audit method: `scripts`-free check in `tests/test_hardening_roles.py` (resolves every template pattern against `rbac.catalog`).
Findings on the current catalog (94 permissions): **no inert pattern remains**. `contract.*`, `qr.*`, `portal.*`, `report.*` and
`audit.export` were inert only before M10-M15 registered their permissions; they now resolve. One real defect found and fixed:
`*.view` (admin, operations manager, auditor) also granted `portal.request.view`, a client-portal permission. Fix: `RoleTemplate.excludes`
(wildcard matches removed unless the permission is named literally); admin, operations manager and auditor exclude `portal.request.*`.
Resulting rules enforced by tests: `client_requester` = exactly `portal.request.create|view|confirm` (nothing internal); only
`client_requester` and the owner hold `portal.request.*`; `audit.export` = owner + auditor; `portal.manage` = owner + service manager;
`qr.generate` = owner + asset manager; every registered permission is reachable by some role; owner = all 94; seeded database roles equal
the template resolution. Seeding stays additive: organizations seeded earlier (including Supabase) keep `portal.request.view` on their
admin / operations / auditor roles until an administrator removes it (documented, not forced).

## 2. HPE entity equivalents (item 5): no duplicate models created
| HPE entity | Equivalent in the implementation | Verdict |
|---|---|---|
| TechnicianProfile | `tenancy.Membership` with the Technician role (permissions `work_order.start/complete/...`, site scope via `MembershipRole.site`); the assignment rules require an ACTIVE membership with start rights (`workorders.services` assignment validation) | valid functional equivalent; HPE lists no technician attributes (skills, certifications) in scope or journeys |
| Shift | none as a table. HPE scope text never specifies shifts; availability is enforced by planned-window overlap (`ACTIVE_ASSIGNMENT_STATES`, no overlapping commitment) and M01 `OperatingCalendar` (working days, holidays) which shifts PM windows | not required by any scope sentence or acceptance journey; **gap only for the utilization capacity input** (see 3) |
| WorkOrderAssignment | `WorkOrder.assigned_to` + append-only `WorkOrderEvent(action, from/to status, assigned_to, actor, reason, time)` + audit `work_order.status_changed` / `work_order.reassigned` | valid (full assignment history) |
| ClosureApproval | the SUPERVISOR_REVIEW -> CLOSED transition (permission `work_order.close`, `closed_by`, `closed_at`, `review_started_at`, WorkOrderEvent, audit with `metadata.action = close`) and for requests CONFIRMED -> CLOSED (`incident.close`); M15 category "Closures" / "Approvals" lists them | valid; the approver, time and reason are persisted and exportable |
Missing behavior: none found that the HPE scope sentences require. Open for the Team Lead only if shift planning (shift calendars, per-shift
capacity) is wanted: it would be new scope, not a rename.

## 3. Dashboard formulas (item 6)
`DECISIONS.md` D-052 records the formulas as OUR IMPLEMENTATION DECISION; no Team Lead approval is recorded. They are NOT silently changed.
Unresolved assumptions needing Team Lead confirmation (exact text, as implemented in `dashboards/metrics.py`):
- MTTR = average (restored - failed) of incident downtimes that ENDED in the window.
- MTBF = (assets in scope x window hours - downtime hours) / failures started in the window; shown only with at least one failure.
- Technician utilization = labor hours recorded in the window / (days x 8 h); the 8 h/day capacity is an assumption because no shift data exists (see Shift above).
- PM compliance = on time / (on time + late + missed) over time-based cycles due in the window up to today; cancelled work orders excluded; meter-based cycles are not judged.
- Parts consumption = ISSUE minus RETURN ledger quantity in the window.
- Overdue = pre-completion work orders past `planned_end`. Windows are UTC days.
