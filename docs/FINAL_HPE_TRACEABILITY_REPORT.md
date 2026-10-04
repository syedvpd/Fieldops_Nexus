# Final HPE traceability report (HPE-PRD-2026-FOPS02), 2026-10-03

Legend. **VERIFIED** = implemented + automated tests (unit / API / RBAC / tenant / negative) + PostgreSQL evidence + browser evidence of the
principal flow. **PARTIALLY VERIFIED** = implemented and tested, browser evidence missing or partial. **NOT VERIFIED** = no evidence.
Row-level detail for M01-M09/M11 lives in `docs/TRACEABILITY.md` (phase matrices); module owners are in `docs/modules/`.
"Browser" = built-in browser pane on a local QA database; M04/M09/M11 browser evidence comes from the Phase 4-6 reports, the new modules
from `docs/FINAL_BROWSER_ACCEPTANCE_REPORT.md`. M01-M08 visible audit was NOT performed in this run (D-048 stays open).

## A. Module scopes (HPE 7.2)
| Module | HPE scope item | Implementation | API | UI | Tests | Browser | Status |
|---|---|---|---|---|---|---|---|
| M01 | organizations, sites, buildings / zones / service areas, operating calendars, contact hierarchy | `tenancy`, `sites` | `/organizations`, `/sites`, `/zones`, `/calendars`, `/site-contacts` | `/app/sites/*` | `test_sites`, `test_site_scope` | partial (Phase 1 audit stopped) | PARTIALLY VERIFIED |
| M02 | asset id, category, model, serial, dates, location, owner, warranty, status, documents | `assets` | `/assets`, `/assets/{id}/history`, `/meters` | `/app/assets/*` | `test_assets` | partial | PARTIALLY VERIFIED (warranty now real through M10) |
| M03 | parent-child assemblies, components, replaceable parts, tree | `assets.hierarchy` | `/asset-components`, `/assets/{id}/tree` | asset Hierarchy tab | `test_hierarchy` | partial | PARTIALLY VERIFIED |
| M04 | time / meter schedules, recurring generation, checklists, windows, reminders | `maintenance` | `/maintenance-plans`, `/schedules` (alias), `/generate-work-orders` | `/app/maintenance/*` | `test_m04_*` (+ concurrency) | QA DB (Phase 5) | VERIFIED |
| M05 | failure reporting, severity, files, asset linkage, downtime, service impact | `incidents` | `/service-requests` | `/app/incidents/*` | `test_phase2_*` | not run | PARTIALLY VERIFIED |
| M06 | create, plan, prioritize, assign, dispatch, pause, complete, close with labor / material / time | `workorders` | `/work-orders` + `/assign /start /hold /complete` | `/app/work-orders/*` | `test_phase2_*`, `test_hpe_api_aliases` | WO staff screens not driven; its effects were checked in the portal, dashboards and audit (this run) | PARTIALLY VERIFIED |
| M07 | assigned jobs, site details, checklist, notes, attachments, parts, time, completion evidence | `workspace` | (uses M06 / M08 / M09) | `/app/workspace/*` | `test_m07_workspace` | not run | PARTIALLY VERIFIED |
| M08 | template-based checklists, mandatory fields, exception findings | `checklists` | `/checklists` (alias), `/checklist-templates`, `/inspections`, `/findings` | `/app/checklists/*` | `test_m08_checklists` | not run | PARTIALLY VERIFIED |
| M09 | stock, issue / return, reservations, min-max, transfer, WO consumption | `inventory` | `/parts`, `/stock`, `/reserve`, `/issue`, `/return` (aliases of `/stock-balances`, `/work-order-parts/*`) | `/app/inventory/*` | `test_m09_*` (+ concurrency) | QA DB (Phase 4) | VERIFIED |
| M10 | coverage, provider, SLA terms, exclusions, expiry, renewal alerts, eligible claim validation | `contracts` (D-049) | `/coverage-agreements`, `/contract-providers`, `/coverage`, `/coverage-checks` | `/app/contracts/*`, asset Coverage tab, WO coverage panel | `test_m10_contracts` (26) | provider + warranty created, asset coverage panel (this run) | VERIFIED (renew / deactivate UI covered by automated tests only) |
| M11 | response / resolution targets, escalation, breach tracking, supervisor alerts | `sla` (D-044) | `/slas`, `/breaches`, `/escalations` (aliases), `/sla-profiles` ... | `/app/sla/*` | `test_m11_*` | QA DB (Phase 6) | VERIFIED |
| M12 | generate / scan labels, open asset profile, create service event | `identification` (D-050) | `/asset-identifiers`, `/scan/resolve`, `/scan/report` | asset Labels tab, scan, resolve, printable label | `test_m12_identification` (21) | QR + barcode, scan, report, cross-tenant (this run); camera NOT VERIFIED | VERIFIED |
| M13 | raise request, status, attachments, scheduled visit, closure details | `portal` (D-051) | `/client/requests` (+ `/status`), `/portal/requests`, `/portal-accounts` | `/app/portal/*` | `test_m13_portal` (19) | submit, progress, visit, confirm, privilege probes (this run) | VERIFIED (file picker not exercised in browser) |
| M14 | MTTR, MTBF, downtime, open WOs, technician utilization, SLA breaches, PM compliance, parts consumption | `dashboards` (D-052) | `/dashboards/<section>` | `/app/dashboards/*` | `test_m14_dashboards` | values reconciled to SQL (this run) | VERIFIED |
| M15 | audit logs, closure approvals, change history, evidence exports, role-controlled reports | `audit` (D-053) | `/audit-logs` (+ `export`) | `/app/audit/*` | `test_m15_audit` | list, category, 3 export formats (this run) | VERIFIED |

## B. State machines (all enforced by `core.workflow.StateMachine` in services; invalid transitions rejected, audited transitions)
| Machine | Evidence | Status |
|---|---|---|
| Service Request NEW > TRIAGED > APPROVED / REJECTED > WORK ORDER CREATED > IN SERVICE > RESOLVED > CONFIRMED > CLOSED | `incidents/workflow.py`; client confirm in browser; system actions refused by hand | VERIFIED |
| Work Order DRAFT > PLANNED > ASSIGNED > DISPATCHED > IN PROGRESS > ON HOLD > COMPLETED > SUPERVISOR REVIEW > CLOSED | `workorders/workflow.py`; `test_work_order_machine_has_no_shortcuts` | VERIFIED (automated + DB) |
| PM SCHEDULED > DUE > GENERATED > ASSIGNED > COMPLETED > VERIFIED > NEXT CYCLE | derived from the WO; `selectors.cycle_state`; dashboard compliance test | VERIFIED |
| Part Request REQUESTED > RESERVED > ISSUED > CONSUMED / RETURNED > RECONCILED | `inventory/workflow.py` | VERIFIED |
| Asset ACTIVE > UNDER MAINTENANCE > OUT OF SERVICE > ACTIVE / RETIRED / DISPOSED | `assets/workflow.py` (D-027) | VERIFIED (automated) |

## C. Complex engineering requirements
| Requirement | Evidence | Status |
|---|---|---|
| PM scheduler: no duplicates, missed cycles | DB unique indexes, scheduler run twice in `test_one_asset_lives_through_every_module`, D-045 | VERIFIED |
| Assignment prevents invalid technician allocation | overlap / inactive / cross-tenant refused (`test_phase2_rules`) | VERIFIED (automated) |
| SLA response vs resolution; pauses only in configured states | D-044, `test_m11_sla` | VERIFIED |
| Inventory issue / return = stock movement, transactional | ledger invariant + concurrency tests; SQL drift check = 0 | VERIFIED |
| Asset status / downtime by controlled transitions | workflow + downtime tests | VERIFIED |
| WO closure needs checklist, notes, evidence per type | `closure_blockers`, `test_closure_matrix_*` | VERIFIED (automated) |
| QR / barcode opaque non-secret identifiers | D-050, tests, browser | VERIFIED |
| Celery: reminders, SLA escalation, contract expiry alerts, report snapshots | tasks `generate_due_maintenance`, `monitor_sla`, `send_renewal_alerts`; report snapshots NOT implemented (dashboards are live aggregates, D-052) | PARTIALLY VERIFIED |
| Backend RBAC, DB persistence, auditable state changes (non-negotiables) | persona matrix, fuzz, audit assertions | VERIFIED |

## D. Mandatory API groups
Assets, Maintenance, Work Orders, Inspections, Inventory, SLA, Portal: every HPE-named path exists (canonical routes plus HPE-named aliases
in `config/api_aliases.py`, same viewsets): `test_hpe_api_aliases`. OpenAPI generates with 0 warnings (aliases are hidden from the schema).
Status: VERIFIED (automated).

## E. Day-90 journeys: see `docs/FINAL_DAY_90_ACCEPTANCE_REPORT.md`.

## F. Gaps against HPE text
| ID | Requirement | Current state | Severity | Recommendation |
|---|---|---|---|---|
| G-1 | Core entities `TechnicianProfile`, `Shift`, `WorkOrderAssignment`, `ClosureApproval` named in the HPE entity list | not separate tables: technician = `Membership` with role, assignment = `assigned_to` + append-only `WorkOrderEvent`, closure approval = SUPERVISOR_REVIEW > CLOSED transition + audit | Medium (naming / modelling) | Team Lead to confirm that the functional equivalents are acceptable (a shift calendar is also the missing input for utilization capacity) |
| G-2 | Report snapshots (Celery) | dashboards compute live aggregates; no snapshot table | Low | add only if volumes demand (D-052) |
| G-3 | M01-M08 browser acceptance | outstanding (D-048) | Medium | run the visible audit when the Team Lead asks |
| G-4 | Production deployment, GitHub tags, 15-day evidence | no Git remote / hosting yet (unchanged since Phase 0) | process | create remote, deploy, apply migrations to Supabase after review |
| G-5 | Camera-based label scanning in a real device | typed-code fallback verified only | Low | test on a phone |
