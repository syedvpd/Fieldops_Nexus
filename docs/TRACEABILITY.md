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
| M07 | Technician Workspace | `workspace` | 3 |
| M08 | Inspection & Checklist Engine | `checklists` | 3 |
| M09 | Spare Parts & Inventory | `inventory` | 4 |
| M10 | Warranty / AMC / Contract | `contracts` | 7 (IMPLEMENTED: D-049, `docs/FINAL_HPE_TRACEABILITY_REPORT.md`) |
| M11 | SLA & Escalation | `sla` | 6 (IMPLEMENTED: D-044, `docs/integrations/sla-requests-workorders.md`; tests `tests/test_m11_*.py`, `tests/test_migrations_phase6.py`) |
| M12 | QR / Barcode | `identification` | 8 (IMPLEMENTED: D-050) |
| M13 | Client / Requester Portal | `portal` | 8 (IMPLEMENTED: D-051) |
| M14 | Operational Dashboards | `dashboards` | 9 (IMPLEMENTED: D-052; formulas are implementation assumptions pending Team Lead confirmation, D-057; `ReportSnapshot`, D-054) |
| M15 | Audit & Compliance | `audit` (extends) | 9 (IMPLEMENTED: D-053) |

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
| Site hierarchy | M01 | 1 | IMPLEMENTED (tests + partial browser audit; approval pending) |
| Asset registry | M02 | 1 | IMPLEMENTED (tests; browser audit partial; approval pending) |
| Asset hierarchy | M03 | 1 | IMPLEMENTED (tests; browser audit partial; approval pending) |
| Service request | M05 | 2 | IMPLEMENTED (local PostgreSQL tests; browser pass pending; approval pending) |
| Work-order core | M06 | 2 | IMPLEMENTED (local PostgreSQL tests; browser pass pending; approval pending) |
| Checklist templates | M08 | 3 | IMPLEMENTED (local PostgreSQL tests; browser deferred; approval pending) |
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
| Role templates, site-scoped roles | Impl (Blueprint 06) | `rbac/role_templates.py`; site scope DONE in Phase 1 (`tests/test_site_scope.py`, D-025) |


## Phase 1 requirements -> evidence (HPE section 7.2 / 8)
Legend: IMPLEMENTED / PARTIAL / FUTURE.
| HPE requirement | Status | Where / evidence |
|---|---|---|
| M01 organizations | IMPLEMENTED (Phase 0) | `tenancy` |
| M01 sites | IMPLEMENTED | `sites.Site`, `/api/v1/sites/`, `/app/sites/`; `tests/test_sites.py`, `test_ui_phase1.py` |
| M01 buildings/zones, service areas | IMPLEMENTED | `sites.Zone` (BUILDING/ZONE/SERVICE_AREA tree, cycle-free); `/api/v1/zones/`, site tree |
| M01 operating calendars | IMPLEMENTED | `OperatingCalendar` + `CalendarHoliday`; `/api/v1/calendars/`, `/calendar-holidays/` |
| M01 contact hierarchy | IMPLEMENTED | `SiteContact` escalation order; `/api/v1/site-contacts/` |
| M02 asset ID, category, model, serial, purchase/commission dates | IMPLEMENTED | `assets.Asset`, `AssetCategory`; uniqueness + date constraints; `tests/test_assets.py` |
| M02 location | IMPLEMENTED | site + zone, same-org/site checks, `AssetLocationHistory` |
| M02 owner | IMPLEMENTED | `Asset.owner` (active membership of the org) |
| M02 warranty | IMPLEMENTED via M10 | `warranty_ref` stays a reference; real coverage = `contracts.CoverageAgreement` / `evaluate` (D-049) |
| M02 status (controlled workflow) | IMPLEMENTED | `assets/workflow.py`, `change_status`, matrix test of every state x action; PATCH of status rejected |
| M02 status/change history | IMPLEMENTED | `AssetStatusHistory` (append-only), `/assets/{id}/history/`, `/changes/` (audit before/after) |
| M02 documents | IMPLEMENTED | `AssetDocument` via `files.services.attach`, site-scoped download |
| AssetMeter | IMPLEMENTED | `/api/v1/meters/`, monotonic readings (M04 consumes later) |
| M03 parent-child, components, replaceable parts, tree | IMPLEMENTED | `AssetComponent`, `assets/hierarchy.py`, `/assets/{id}/tree/`, HTMX tree; `tests/test_hierarchy.py` |
| API group Assets (`/assets/`, `/assets/{id}/history/`, `/meters/`) | IMPLEMENTED | OpenAPI clean |
| Backend RBAC + role boundaries (Day-30 focus) | IMPLEMENTED | RBAC matrix + site scope + IDOR tests |
| Lifecycle state control (Day-30 focus) | IMPLEMENTED | D-027 |
| Schema quality (Day-30 focus) | IMPLEMENTED | constraints, indexes, fresh-DB migration test, no drift |
| Journey 1: site + asset hierarchy + status/change history | IMPLEMENTED (browser run PARTIAL) | manual guide sections 2-5, 8 |
| UI desktop/tablet/mobile | PARTIAL | 375px overflow check on 4 pages; full 4-size sweep pending |

## Phase 2 requirements -> evidence (HPE section 7.2 / 8)
| Requirement | Status | Evidence |
|---|---|---|
| M05 failure reporting, severity, asset linkage, service impact | IMPLEMENTED | `incidents.ServiceRequest`, `POST /service-requests/`, UI `/app/incidents/new/`; `tests/test_phase2_journey.py`, `tests/test_phase2_rules.py` |
| M05 photos / files | IMPLEMENTED | evidence upload through `files.Attachment` (type/size validated), site-scoped download (`files.access`); `test_evidence_validation_and_download_scope` |
| M05 downtime start / end | IMPLEMENTED | `incidents.Downtime` (+ DB check end >= start), ends on work-order completion or manually; `test_downtime_rules`, journey |
| M05 triage / approval, state chain | IMPLEMENTED | `incidents/workflow.py` (D-035), invalid/system transitions rejected; `test_request_machine_terminal_and_system_steps`, `test_system_actions_are_not_callable_by_hand` |
| M05 approved request creates / links a real work order | IMPLEMENTED | `create_work_order_for_request` (one live WO per request, DB partial unique index); `test_create_work_order_requires_approved_request_and_permission`, `test_one_live_work_order_per_request_db_constraint` |
| M06 create / plan / prioritise / assign / dispatch | IMPLEMENTED | `workorders/workflow.py`, `services.transition`; technician overlap / inactive / cross-tenant refused; `test_assignment_validation`, `test_technician_overlap_is_refused_but_other_windows_and_people_are_fine` |
| M06 execute, pause (hold/resume), complete | IMPLEMENTED | assignee-only rule, reasons, notes + evidence rule; `test_only_assignee_or_dispatcher_executes`, `test_completion_needs_notes_and_evidence_only_for_corrective` |
| M06 labor / material / time capture | IMPLEMENTED (free-text lines for non-stocked consumables; stock-backed lines come from M09 consumption, D-042) | `WorkOrderLabor`, `WorkOrderMaterial`; `test_close_blockers_and_labor_rules`, `test_material_validation` |
| M06 supervisor review and closure rules | IMPLEMENTED | review, rework, close guards; checklist completion is enforced since Phase 3 (D-040): `test_closure_matrix_*`, `test_malicious_completion_of_work_through_api_is_blocked` |
| Never DRAFT -> CLOSED | IMPLEMENTED | `test_work_order_machine_has_no_shortcuts`; API 409 in the journey |
| M05 <-> M06 integration (start / resolve / rework / cancel) | IMPLEMENTED | `on_work_order_*` hooks; `test_rework_loop_and_reopen`, `test_cancel_returns_request_to_approved_and_allows_new_work_order` |
| RBAC, tenant isolation, site scope, IDOR | IMPLEMENTED | `test_unauthenticated_and_reader`, `test_role_boundaries`, `test_cross_tenant_isolation_both_directions`, `test_site_scoped_user_sees_only_their_site`, `test_technician_sees_only_assigned_work`, UI `test_forbidden_roles_and_foreign_objects` |
| Audit (create, update, every transition, assignment, labor, material, evidence, downtime) | IMPLEMENTED | journey asserts audit counts and actor/before/after |
| Browser + Supabase evidence | NOT DONE | stopped by the Team Lead (D-034); guide: `docs/manual-tests/PHASE_2_MANUAL_TEST.md` |

## Phase 3 requirement matrix (M08 / M07)
Status: IMPLEMENTED = code + automated test on local PostgreSQL. Browser evidence is DEFERRED for every row (Team Lead decision: browser / responsive / Supabase acceptance at the end of the project).
| Requirement | Status | Evidence |
|---|---|---|
| M08 checklist templates (HPE 7.2): create, edit draft, items, reorder, required/optional, types, validation | IMPLEMENTED | `checklists.services`; `test_template_lifecycle_items_reorder_and_audit`, `test_item_configuration_is_validated`, UI `test_template_management_ui_end_to_end_and_permissions` |
| M08 template versioning, frozen active templates, history stays understandable | IMPLEMENTED | D-039; `test_active_template_is_frozen_and_new_version_keeps_history`, `test_deactivated_template_cannot_start_new_inspections` |
| M08 inspection execution, response persistence, invalid values rejected, refresh preserves state | IMPLEMENTED | `test_responses_persist_validate_and_flag_exceptions`, `test_invalid_responses_are_rejected_all_or_nothing`, UI `test_required_checklist_blocks_ui_completion_until_inspection_completed` |
| M08 mandatory fields + exception findings + evidence requirements | IMPLEMENTED | `test_required_items_exceptions_and_evidence_gate_completion`, `test_exception_needs_finding_and_evidence_through_ui`, `test_evidence_api_validation_and_download_authorisation` |
| M08 completed inspection is authoritative / immutable; duplicate completion and duplicate execution refused; concurrent completion serialised | IMPLEMENTED | `test_completed_inspection_is_immutable_and_cannot_be_completed_twice`, `test_duplicate_execution_on_same_work_order_is_refused`, `test_concurrent_completion_is_serialised` |
| M08 -> M06 closure / completion blocker (real DB state, one mechanism) | IMPLEMENTED | `test_closure_matrix_*` (no required checklist / not started / incomplete / complete / re-block), `test_closure_blocker_reads_db_state_not_a_flag`, `test_malicious_completion_of_work_through_api_is_blocked`, UI + journey |
| M07 technician job queue, job detail, start / hold / resume / complete through M06 services | IMPLEMENTED | `test_my_jobs_*`, `test_start_hold_resume_via_workspace_and_invalid_state_rejected`, `test_workspace_refuses_planner_and_supervisor_actions_and_other_roles` |
| M07 notes, evidence, labor/time, material information (free text, no stock) | IMPLEMENTED | `test_notes_labor_material_evidence_persist_and_validate`; M09 boundary recorded in D-041 |
| M07 checklist execution UI (HTMX) | IMPLEMENTED (render + POST tested; HTMX behaviour verified through the HX-Request fragment / redirect responses, not in a browser) | `test_required_checklist_blocks_ui_completion_*`, `test_stale_form_after_completion_*` |
| Tenant isolation, site scope, IDOR (API + HTML + attachment download) | IMPLEMENTED | `test_cross_tenant_everything_is_invisible_and_unusable`, `test_site_scope_limits_inspection_visibility`, `test_evidence_download_follows_inspection_scope_and_tenancy`, `test_unauthenticated_inactive_and_cross_tenant_access` |
| Audit of template / inspection / finding / note actions | IMPLEMENTED | audit assertions in the M08 and M07 tests and in the journey |
| HPE journey incident -> work order -> technician -> checklist -> finding -> evidence -> labor -> complete -> review -> close | IMPLEMENTED (API + HTML, no DB injection) | `test_full_journey_incident_to_closed_through_api_and_html` |
| Browser, responsive 1920/1366/768/390, console/network, Supabase audit | **DEFERRED** by the Team Lead | `docs/manual-tests/PHASE_3_MANUAL_TEST.md` |

## Phase 4 (M09 Spare Parts & Inventory) - HPE section 7.2 / 8.1
| Requirement | Status | Evidence |
|---|---|---|
| Warehouse / site stock (HPE CONFIRMED) | IMPLEMENTED | `Warehouse` (site-bound), `StockBalance`; `test_m09_inventory`, `test_m09_api::test_warehouse_permissions_site_scope_and_tenancy` |
| Parts, min / max / reorder information (HPE CONFIRMED) | IMPLEMENTED (information + low-stock flag only) | `Part` defaults, balance overrides; `test_levels_and_low_stock_flag` |
| Issue / return with stock movements, transactional, never `quantity -= N` (HPE CONFIRMED) | IMPLEMENTED | `inventory.services._apply`; `test_stock_10_issue_2_return_1_then_issue_10_is_rejected`, `assert_ledger_consistent`, DB checks `test_database_refuses_negative_or_over_reserved_balances_and_movement_edits` |
| Concurrency (HPE CONFIRMED) | IMPLEMENTED | `tests/test_m09_concurrency.py` (last unit, oversell, reserve, same-line, first receipt, opposite transfers = deadlock fix) |
| Reservations: on-hand / reserved / available | IMPLEMENTED | `PartReservation`; `test_reservation_on_hand_reserved_available_and_cannot_overreserve`, `test_release_returns_availability_and_issue_uses_the_reservation` |
| Transfer (HPE CONFIRMED) | IMPLEMENTED | paired TRANSFER_OUT / TRANSFER_IN with shared reference; `test_transfer_writes_paired_movements` |
| Consumption against work orders (HPE CONFIRMED) | IMPLEMENTED | `consume` -> M06 material row (`part_line`); `test_consume_writes_the_m06_material_row_and_respects_ownership` |
| Part Request REQUESTED -> RESERVED -> ISSUED -> CONSUMED / RETURNED -> RECONCILED (HPE CONFIRMED) | IMPLEMENTED (CANCELLED added, D-042) | `workflow.py`, `WorkOrderPart.status`; API/UI flow tests |
| M06 closure / cancel integration | IMPLEMENTED (OUR DECISION) | `test_closure_is_blocked_by_outstanding_parts_then_reconciles_the_lines`, `test_cancelling_a_work_order_releases_reservations_but_not_with_issued_stock` |
| M07 uses the M09 contract | IMPLEMENTED | `test_full_flow_through_ui_pages_and_workspace`, `test_workspace_part_endpoints_are_scoped_to_my_jobs` |
| Journey 5: inventory issue / return -> stock movement -> WO linkage (HPE CONFIRMED) | IMPLEMENTED (browser verified locally) | `docs/PHASE_4_ACCEPTANCE_REPORT.md` |

## Phase 5 (M04 Preventive Maintenance) - HPE section 7.2 / 8.1
| Requirement | Status | Evidence |
|---|---|---|
| Time-based schedules (HPE CONFIRMED) | IMPLEMENTED (daily / weekly / monthly / quarterly / yearly x interval, site timezone) | `recurrence.py`; `test_m04_recurrence`, `test_every_frequency_generates_on_the_right_day`, `test_due_date_uses_the_site_timezone` |
| Meter-based schedules (HPE CONFIRMED) | IMPLEMENTED on the existing M02 meters (no second meter system) | `test_meter_based_due_follows_the_hpe_example` (1200 h, every 500 -> 1500) |
| Recurring job generation = real work orders (HPE CONFIRMED; Journey 2) | IMPLEMENTED through `workorders.services.create_work_order` | `test_time_based_generation_creates_a_real_planned_work_order`, API / UI journeys |
| PM source recorded on the work order | IMPLEMENTED (`source_type` / `source_id`, D-043) | `test_database_enforces_one_work_order_per_cycle`, WO detail / API |
| Scheduler idempotent, concurrency-safe, no duplicates (HPE CONFIRMED) | IMPLEMENTED | `test_running_generation_twice...`, `tests/test_m04_concurrency.py`, `test_failed_generation_rolls_back_completely_and_the_retry_creates_exactly_one`, Celery tests |
| Missed / overdue cycles (HPE CONFIRMED requirement, policy OUR DECISION) | IMPLEMENTED as collapse; TEAM LEAD DECISION D-045 (2026-10-03) | `test_missed_cycles_are_collapsed_into_the_latest_one` |
| Maintenance windows, reminders (HPE CONFIRMED) | IMPLEMENTED (window in site time, working-day shift, reminder once per occurrence) | `test_planned_window_moves_to_the_next_working_day_of_the_site_calendar`, `test_reminder_is_sent_once_per_occurrence` |
| Checklists on PM work (HPE CONFIRMED; M08 authoritative) | IMPLEMENTED | `test_plan_checklist_becomes_a_required_checklist_of_the_generated_work_order` |
| Disabled PM does not generate; re-enable resumes | IMPLEMENTED | `test_disabled_plan_and_schedule_never_generate_and_reenabling_resumes_without_replay` |
| PM lifecycle GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED | IMPLEMENTED (derived from the M06 order) | `selectors.cycle_state`; API `state` |

## Final run (Phases 7-9 + audit)
Full matrices: `docs/FINAL_HPE_TRACEABILITY_REPORT.md`, `FINAL_DAY_90_ACCEPTANCE_REPORT.md`, `FINAL_BUSINESS_WORKFLOW_ACCEPTANCE_REPORT.md`, `FINAL_SECURITY_AUDIT.md`, `FINAL_DATABASE_INTEGRITY_REPORT.md`, `FINAL_BROWSER_ACCEPTANCE_REPORT.md`, `FINAL_RELEASE_READINESS_REPORT.md`. Manual guide: `docs/manual-tests/PHASE_7_9_MANUAL_TEST.md`.


## HPE 8.2 entity equivalents and HPE 8.4 Celery families (final reconciliation, D-054 / D-056)
| HPE entity / rule | Where it lives | Status |
|---|---|---|
| Incident / ServiceRequest | `incidents.ServiceRequest` (`kind`), D-035 | IMPLEMENTED (equivalent) |
| WorkOrderAssignment | `WorkOrder.assigned_to` + `WorkOrderEvent` | IMPLEMENTED (equivalent) |
| ClosureApproval | review -> close transition + M13 confirmation + M15 "Closures" | IMPLEMENTED (equivalent) |
| Warranty, ServiceContract | `contracts.CoverageAgreement` (WARRANTY / AMC / CONTRACT) | IMPLEMENTED |
| TechnicianProfile, Shift | `Membership` + technician role + `MembershipRole.site`; site `OperatingCalendar` | IMPLEMENTED (equivalent); Team Lead confirmation requested |
| ReportSnapshot | `dashboards.ReportSnapshot` + daily Celery fan-out | IMPLEMENTED |
| IntegrationEvent | none (no external system defined) | HPE CLARIFICATION REQUIRED |
| Celery: PM reminders / generation | `maintenance.tasks.fan_out_maintenance` (15 min) | IMPLEMENTED |
| Celery: SLA escalation | `sla.tasks.fan_out_sla_monitor` (60 s) | IMPLEMENTED |
| Celery: contract / warranty expiry alerts | `contracts.tasks.fan_out_renewal_alerts` (6 h) | IMPLEMENTED |
| Celery: report snapshots | `dashboards.tasks.fan_out_report_snapshots` (daily) | IMPLEMENTED |

## Dashboard formula status (D-052 / D-057)
| KPI | Definition as implemented | Approval status |
|---|---|---|
| MTTR, MTBF, technician utilization (8 h/day), PM compliance, parts consumption, overdue | `dashboards.metrics.KPI_DEFINITIONS` | OUR IMPLEMENTATION ASSUMPTION; TEAM LEAD CONFIRMATION REQUIRED (no recorded approval) |
| Open work orders, SLA breaches, downtime hours, open incidents, low stock | plain counts / sums over persisted rows, reconciled against SQL in `tests/test_m14_dashboards.py` | no business definition needed beyond the status sets in `KPI_DEFINITIONS` |
