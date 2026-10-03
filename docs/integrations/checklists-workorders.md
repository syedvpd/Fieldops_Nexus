# Phase 3 contracts: M08 Checklists <-> M06 Work Orders <-> M07 Workspace

Dependency direction: `workorders` (M06) <- `checklists` (M08) <- `workspace` (M07). M06 imports M08 only lazily inside `workorders.services.checklist_blockers`; M08 imports M06 models/services for execution rules; M07 imports both and owns only `WorkNote`.

## Who owns what
| Concern | Owner | Notes |
|---|---|---|
| Work-order lifecycle (states, assignment, labor, material, evidence, closure rule list) | M06 `workorders.services` | the single state machine; M07 never edits `WorkOrder.status` |
| Checklist templates, versions, inspections, answers, findings, inspection completion | M08 `checklists.services` | M06 never reads M08 tables directly |
| Technician screens, technician notes | M07 `workspace` | orchestration + `WorkNote` only |
| Stock for parts used | M09 (not built) | M06 `WorkOrderMaterial` stays free text; the workspace says "no stock is moved" |

## Checklist <-> work order contract (D-040)
| Event | Effect | Implemented by |
|---|---|---|
| Technician starts a checklist on an IN_PROGRESS work order | `Inspection(IN_PROGRESS)` for (work order, template version); duplicate of the same checklist refused | `checklists.services.start_inspection` (assignee / dispatcher via `workorders.services.assert_can_execute`) |
| Work order `complete` action | refused with `checklist_incomplete` (409) while a required checklist is not COMPLETED | `workorders.services.transition` -> `checklist_blockers` |
| Work order `close` action / `GET /work-orders/{id}/closure/` | `closure_blocked` / blockers list contains the checklist reasons | `workorders.services.closure_blockers` = M06 rules + `checklist_blockers` |
| `GET /inspections/requirements/?work_order=` | per-checklist state (NOT_STARTED / IN_PROGRESS / COMPLETED), required flag, blockers | `checklists.selectors.requirements_for` |
| Work order ON_HOLD / not IN_PROGRESS | answers, findings, evidence and completion of its inspections are refused (`work_order_not_in_progress`) | `checklists.services._assert_wo_running` |
| Rework (`reject_review`) | completed inspections stay COMPLETED (they are history); a newly activated required checklist re-blocks | D-040 |

"Required" = ACTIVE template with `is_required`, and `work_type` blank or equal to the work order's type. Satisfied = a COMPLETED inspection of any version of the same checklist `key` on that order. An unfinished inspection of a required checklist always blocks (deactivation cannot skip it). No required template = M06 behaviour unchanged.

## Workspace -> owner calls
| Workspace action | Calls |
|---|---|
| Dispatch / Start / Hold / Resume / Complete | `workorders.services.transition` (permission from `ACTION_PERMISSIONS`; other actions are refused in the workspace) |
| Time | `workorders.services.record_labor` (technician = caller; hours 0 < h <= 24, not future) |
| Material | `workorders.services.record_material` (free text; no stock) |
| Evidence | `workorders.services.add_evidence` -> `files.services.attach` |
| Note | `workspace.services.add_note` (same state / assignee rule: `workorders.services.assert_recordable`) |
| Start checklist / answers / findings / evidence / complete | `checklists.services.start_inspection / save_responses / add_finding / add_*_evidence / complete_inspection` |

## Evidence access
`files.access` checkers: `checklists.inspectionresponse` and `checklists.finding` follow `checklists.selectors.can_see_inspection` (site scope with `inspection.view`, or the starter / assigned technician with `inspection.execute`). Out of scope answers 404.

## Contracts for later modules
| Consumer | Needs | Use |
|---|---|---|
| M04 PM | checklist per PM task | create work orders with `work_type="PREVENTIVE"`; a required template with that work type is applied automatically |
| M09 Inventory | parts issue / return | replace M06 free-text material; M07 material form then calls M09 |
| M11 SLA / M14 Dashboards | findings and inspection timings | read `Inspection.started_at / completed_at`, `Finding.severity / status` (no stored aggregates) |
| M12 QR | start an inspection from an asset | `start_inspection(..., asset=...)` already supports standalone inspections (API); UI entry point is not built |
