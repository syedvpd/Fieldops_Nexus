# HPE -> implementation -> evidence traceability matrix (M01-M15)

Source of requirements: `docs/blueprint/01_HPE_TRACEABILITY.md` (HPE digest), the module documents and `docs/TRACEABILITY.md`. Nothing is marked PASS because a file exists: PASS requires runtime evidence (browser/API/DB) in this audit; automated tests are listed as supporting evidence only.

Status vocabulary: **PASS**, **PARTIAL** (works, with a defect or gap), **FAIL**, **MISSING**, **UNVERIFIED**, **INTENTIONAL** (documented decision / out of scope). "Evidence" refers to scenario lines in `evidence/browser_results.jsonl` (module prefix) and to `FINDINGS_REGISTER.md` IDs. Paths are under `src/apps/<app>/` and templates under `src/templates/<app>/`; permission codes are as registered in each app's `permissions.py`.

Legend for columns: **Model/DB** = main tables; **Rule/service** = enforcing function; **API** = REST route; **UI** = URL under `/app/`; **Perm** = permission; **Async/HTMX** = Celery task or HTMX interaction; **Tests** = automated tests (`tests/`).

## Foundation (non-negotiables and cross-cutting)

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Multi-tenant org, Super Admin onboarding, owner invitation | `tenancy_organization`, `tenancy_membership` | `tenancy.services.create_organization/suspend` | `/api/v1/platform/organizations/` | `/platform/organizations/` | `is_platform_admin` | invitation email task | `test_onboarding_auth`, `test_tenant_isolation` | PLATFORM: create org, duplicate slug rejected, activation link single-use, strong-password rule, suspend/reactivate, Alpha unaffected | PASS |
| Tenant isolation | all `TenantOwnedModel` tables | fail-closed `TenantManager` | all | all | n/a | n/a | `test_tenant_isolation`, `test_hardening_tenant` | 52+104 endpoints, 78 pages, files, QR, uploads, dashboards, audit, exports in both directions: 0 leaks (`TENANT_RBAC_SECURITY_AUDIT.md`) | PASS (backstop F-M20) |
| Backend-enforced RBAC | `rbac_*` | `rbac.services.has_permission`, `TenantAPIMixin` | all | `TenantPermissionMixin` | per code | n/a | `test_rbac`, `test_site_scope`, `test_hardening_roles` | 11 roles x 18 writes, 70 endpoints x 14 principals, crafted POSTs | PASS (F-M07, F-M17) |
| Auditable state changes | `audit_auditlog` | `audit.services.record` in the service transaction | `/api/v1/audit-logs/` | `/app/audit/` | `audit.view` | n/a | `test_audit`, `test_m15_*` | every workflow produced audit rows; list/detail/export | PARTIAL (F-H02, F-M14, L30, L36) |
| No mock screens / fake success / dead buttons | n/a | services only | n/a | all templates | n/a | n/a | `test_ui*` | every button clicked produced a persisted change verified in SQL; static scan of `{% url %}`/`hx-post`/forms found no dead targets | PASS |
| Login security (throttle, CSRF, secure sessions) | `axes_*` | axes, CSRF, password validators | `/api/v1/auth/token/` | `/accounts/login/` | n/a | n/a | `test_login_integration` | lockout, enumeration, logout invalidation, CSRF, open redirect | PASS (L47, L48) |

## M01 Site & Location Master

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Organizations | `tenancy_organization` | see foundation | | `/app/organization/` | `organization.update` | | `test_onboarding_auth` | PLATFORM | PASS |
| Sites | `sites_site` | `sites.services.create_site/update/deactivate` | `/api/v1/sites/` | `/app/sites/` | `site.*` | | `test_sites`, `test_ui_phase1` | M01: create/edit/dup/tz/email/XSS, deactivate/reactivate, active-asset rule | PASS |
| Buildings/zones | `sites_zone` | `validate_zone_parent` (depth, cycle, same site) | `/api/v1/zones/` | `/app/sites/{id}/?tab=locations` | `zone.*` | | `test_sites` | 4-level nesting, cycle prevention UI + crafted POST | PASS (F-M19 race, L02) |
| Service areas | `Zone.zone_type=SERVICE_AREA` | same | same | same | | | | created and nested (M01) | PASS |
| Operating calendars | `sites_operatingcalendar`, `_calendarholiday` | `_validate_calendar` | `/api/v1/calendars/` | `/app/sites/{id}/calendars/new/` | `calendar.*` | | `test_sites` | create, end<start rejected | PASS (L03 overnight) |
| Contact hierarchy | `sites_sitecontact` | escalation order unique | `/api/v1/site-contacts/` | `/app/sites/{id}/contacts/new/` | `site.update` | | | add contact | PASS |
| Site-scoped access | `rbac_membershiprole.site` | `rbac.site_scope` | | | | | `test_site_scope` | planner limited to BLR-1: site list, direct site/asset URLs (404), asset and WO APIs, WO create for out-of-scope asset all scoped; REST write gap reproduced (F-M07) | PARTIAL (F-M07) |

## M02 Asset Registry

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Asset ID, category, model, serial | `assets_asset`, `assets_assetcategory` | unique tag/serial; category attributes | `/api/v1/assets/`, `/asset-categories/` | `/app/assets/`, `/app/assets/categories/` | `asset.*` | category reload | `test_assets`, `test_gap_attributes` | M02: create with attributes, duplicates, required attribute, edit | PASS |
| Purchase/commission dates | `purchase_date`, `commission_date` | commission >= purchase | same | asset form | | | `test_assets` | validation rejected | PASS |
| Location | `site`, `zone`, `assets_assetlocationhistory` | `_move`, `_check_refs` | `/assets/{id}/location-history/` | History tab | `asset.update` | | | zone from other site rejected; move recorded | PASS (F-M08) |
| Owner | `Asset.owner` -> membership | | | asset form | | | | owner shown on detail | PASS |
| Warranty | `warranty_ref` free text + M10 coverage | | `/api/v1/coverage/` | Coverage tab | `contract.view` | HTMX panel | `test_m10_*` | coverage line on asset | PASS (stale help text C04) |
| Financial information | none | | | | | | | no cost/vendor/currency fields | UNVERIFIED (U10) |
| Status workflow + history | `assets_assetstatushistory` | `change_status`, `ASSET_STATUS` machine | `/assets/{id}/transition/`, `/history/` | status buttons | `asset.change_status` | | `test_assets`, `test_asset_workflow_coupling` | full chain, invalid blocked, 6 history rows, audit | PASS |
| Documents | `assets_assetdocument`, `files_attachment` | `files.attach`, upload validation | `/assets/{id}/documents/` | Documents tab | `asset.document.manage` | | `test_core` | upload/download/exe/fake-PDF/>10 MB | PASS (F-M07 API scope, L04) |
| Meters/readings | `assets_assetmeter(+reading)` | monotonic under row lock | `/api/v1/meters/` | Meters tab | `asset.meter.record` | | `test_assets` | create, 100/150 stored, decrease/negative rejected | PASS (F-M07, L13) |

## M03 Asset Hierarchy

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Parent-child assemblies, components, replaceable parts | `assets_assetcomponent` | `hierarchy.add/move/update/remove` (advisory lock, depth, cycle) | `/asset-components/`, `/assets/{id}/components/` | Hierarchy tab | `asset.hierarchy.manage` | tree loaded via HTMX | `test_hierarchy` | M03: attach, 3-level tree, re-parent, edit, detach; cycle/self/already-parented/cross-site/cross-tenant rejected | PASS |
| Relationship tree | same | `tree()` | `/assets/{id}/tree/` | tree | | HTMX | | tree renders descendants | PASS |
| Replace component | none (remove + add) | | | | | | | no atomic replace; history only in audit | PARTIAL (L06) |
| Integrity with asset lifecycle | | `change_status` | | | | | | retiring a parent leaves undetachable links | **FAIL** F-M06 |

## M04 Preventive Maintenance

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Time/meter schedules | `maintenance_maintenanceplan/schedule` | `create_schedule`, `recurrence` | `/api/v1/maintenance-plans/`, `/maintenance-schedules/`, `/schedules/` | `/app/maintenance/plans/` | `maintenance.*` | | `test_m04_*` | plan + weekly/daily schedules created in UI | PASS |
| Recurring generation without duplicates | `maintenance_maintenancecycle` (`UNIQUE(schedule,sequence)`) | `generate_cycle` | `/generate-work-orders/`, `/schedules/{id}/generate/` | Generate now | `maintenance.generate` | `fan_out_maintenance` (15 min) | `test_m04_maintenance`, `test_m04_concurrency` | manual + beat generation, duplicate refused (UI, crafted POST, repeated task) | PASS |
| Editing the recurrence | | `update_schedule/_resync` | PATCH schedule | schedule edit | | | single-cycle test only | silently stops generation | **FAIL** F-H01 |
| Checklists | `Plan.checklist_key` | `required_checklist_key` | | plan form | | | | checklist gate shown on generated WO | PARTIAL (F-M05) |
| Maintenance windows | `window_start_time`, `window_hours` | `window_for` (site tz) | | schedule form | | | | planned start/end on WO | PASS (L56 UTC display) |
| Reminders | `reminder_days` | `remind` | | | | task | `test_m04_*` | not triggered (no reminder due in run) | UNVERIFIED |
| Missed/overdue cycles | | collapse policy D-045 | | Due list | | | `test_m04_maintenance` | DUE state listed; collapse by tests only | PARTIAL (INTENTIONAL I02, L10) |
| PM lifecycle states | derived | `selectors.CYCLE_STATES` | `/maintenance-cycles/` | History | | | | GENERATED..VERIFIED observed | INTENTIONAL I02 |

## M05 Incident / Breakdown

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Failure reporting, severity, impact, asset linkage | `incidents_servicerequest` | `create_request` | `/api/v1/service-requests/` | `/app/incidents/new/` | `incident.create` | | `test_phase2_*` | UI + client + QR + API creation | PASS |
| Photos/files | `files_attachment` | `attach` | `/service-requests/{id}/evidence/` | Evidence tab | `incident.attach` | | | client attachment stored, downloads authorised | PASS |
| Downtime start/end | `incidents_downtime` | `set_downtime`, `_end_open_downtime` | `/service-requests/{id}/downtime/` | downtime form | `incident.update` | | | open after reject | **FAIL** F-M03 |
| Request lifecycle | `incidents_servicerequesthistory` | `incidents.workflow` | `/transition/` | workflow bar | `incident.triage/approve/confirm/close` | | | see `WORKFLOW_ACCEPTANCE_AUDIT.md` | PARTIAL (F-M01, F-M02) |

## M06 Work Order Management

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Create/plan/prioritize/assign/dispatch/pause/complete/close | `workorders_workorder`, `_workorderevent` | `workorders.services.transition` | `/work-orders/`, `/assign/`, `/start/`, `/hold/`, `/complete/`, `/transition/` | `/app/work-orders/` | `work_order.*` | | `test_phase2_*`, `test_integration_p456` | full chain, hold/resume, reassign, cancel, edit | PASS |
| Labor / material / time | `workorders_workorderlabor`, `_workordermaterial` | validators | `/work-orders/{id}/labor/`, `/materials/` | Labor & material tab | `work_order.record` | | | labor valid/invalid; duplicates not guarded | PASS (L14) |
| Assignment prevents invalid allocation | | `check_technician` | | | | | | double-booking 409 | PASS (L15 race) |
| Closure requires checklist, notes, evidence by work type | | `closure_blockers` | `/work-orders/{id}/closure/` | blocker list | | | | blockers observed; any attachment = evidence | PASS (L16, F-M04) |

## M07 Technician Workspace

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Assigned jobs only | | `selectors.my_jobs` / `work_orders_for` | (via M06) | `/app/workspace/` | `work_order.view_assigned` | | `test_m07_workspace` | other technician's job 404 in UI/API | PASS |
| Route/site details | | `route_context` | | job card | | | `test_m07_route` | site, address, "Open in maps" | PASS |
| Checklist, notes, attachments, parts, time, completion evidence | `workspace_worknote` + M06/M08/M09 | services | | job page (390 px) | | autosave HTMX | `test_m07_workspace` | all executed on mobile | PASS |

## M08 Inspection & Checklist Engine

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Templates with mandatory fields | `checklists_checklisttemplate/item` | draft-only edits, versions | `/checklist-templates/`, `/checklists/` | `/app/checklists/` | `checklist.manage` | | `test_m08_checklists` | 4 item types, validation, freeze, new version | PASS |
| Exception findings | `checklists_finding`, `_inspectionresponse` | `completion_issues` | `/findings/`, `/inspections/` | workspace inspection | `inspection.execute` | HTMX save | | out-of-range needs finding; completion with finding | PASS |
| Applicability | | `required_templates` (work type only) | | | | | | unrelated generator checklist forced on HVAC | **FAIL** F-M04 |

## M09 Spare Parts & Inventory

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Warehouse/site stock, min-max | `inventory_warehouse/part/stockbalance` | CHECK constraints | `/warehouses/`, `/parts/`, `/stock-balances/` | `/app/inventory/*` | `inventory.*` | | `test_m09_*` | create, validation, receive, adjust | PASS |
| Reservations, issue/return, WO consumption | `inventory_partreservation`, `_workorderpart`, `_stockmovement` | `inventory.services` (row locks) | `/reserve/`, `/issue/`, `/return/`, `/work-order-parts/` | WO parts page | `inventory.reserve/issue/consume/return` | | `test_m09_concurrency` | full lifecycle, ledger invariant | PASS |
| Transfer | movements | `transfer` | `/stock/transfer/` | `/app/inventory/stock/transfer/` | `inventory.transfer` | | `test_m09_*` | form present; not executed | UNVERIFIED |

## M10 Warranty / AMC / Contract

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Coverage, provider, exclusions, expiry | `contracts_*` | overlap rule, `evaluate` | `/coverage-agreements/`, `/contract-providers/`, `/coverage/` | `/app/contracts/*` | `contract.*` | HTMX panels | `test_m10_*` | warranty/AMC/lapsed create, overlap rejected, expiry list | PASS |
| SLA relationship | `CoverageAgreement.sla_profile` | `_coverage_profile` | | agreement form | | | `test_m10_m11_coverage_sla` | profile selectable | PASS |
| Renewal alerts | `renewal_alerted_at` | `run_alerts` | | | | `fan_out_renewal_alerts` | `test_final_celery_snapshots` | delivered through worker | PARTIAL (F-M13) |
| Eligible claim validation | `contracts_coveragecheck` | `evaluate`, `record_check` | `/coverage-checks/` | WO panel | `contract.check` | HTMX | | panel eligibility incl. exclusion | PASS |

## M11 SLA & Escalation

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Response vs resolution targets by priority | `sla_slaprofile/target` | `sla.services` | `/sla-profiles/`, `/slas/` | `/app/sla/profiles/` | `sla.*` | | `test_m11_*` | targets edited, tracking auto-created | PASS |
| Escalation, breach tracking, supervisor alerts | `sla_escalationrule/slabreach/slaevent` | `process_tracking` | `/sla-breaches/`, `/breaches/`, `/escalations/` | `/app/sla/breaches/` | `sla.acknowledge` | `fan_out_sla_monitor` (60 s) | `test_m11_concurrency` | real breach/warning/escalation/ack with notifications | PASS (L28-L30) |
| Pause only in configured states | `pause_states` | `_sync_pause` | | | | | | paused at TRIAGED, resumed | PASS (L29) |
| Calendar vs 24/7 | | wall-clock minutes | | | | | | | INTENTIONAL I01 |

## M12 QR / Barcode

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Generate labels | `identification_assetidentifier` | `generate/replace/revoke` | `/asset-identifiers/` | Labels tab | `qr.*` | HTMX panel | `test_m12_identification` | QR + Code128, printable label | PASS |
| Scan -> asset profile | `identification_scanevent` | `resolve` = lookup then authorize | `/scan/resolve/` | `/app/identification/scan/`, `/app/s/{token}/` | `qr.view` | camera JS | `test_m12_camera_scan` | typed + synthetic-camera scan; invalid/foreign/anonymous/client | PASS (L32, F-M11) |
| Scan -> service event | `ScanEvent.service_request` | `report_from_scan` | `/scan/report/` | asset page | `incident.create` | | | INC-000003 | PASS |
| Opaque non-secret identifiers | | `new_token` | | | | | `test_hardening_scan` | 22/12-char random tokens, not derived | PASS |

## M13 Client / Requester Portal

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Raise request, attachments | `portal_portalaccount/portalassetgrant` | `submit_request` | `/portal/requests/`, `/client/requests/` | `/app/portal/` | `portal.request.*` | | `test_m13_portal` | 390 px submit with photo | PASS |
| Status, scheduled visit, closure details | | client-safe selectors | `/status/` | request page | | | | visit window + technician, no internal data | PASS |
| Confirmation / reopen | | `confirm/reopen` via M05 | `/confirm/`, `/reopen/` | buttons | `portal.request.confirm` | | | confirm -> closed; reopen path | PARTIAL (F-M01, F-M02) |
| Access revocation | | `active_account` | | | `portal.manage` | | | disabled client retains reads | **FAIL** F-M09 |

## M14 Operational Dashboards

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| MTTR, MTBF, downtime | `incidents_downtime`, assets | `metrics.py` | `/api/v1/dashboards/` | `/app/dashboards/?section=assets` | `report.view` | | `test_m14_dashboards` | shown n/a with no failures; formulas documented (D-057) | PARTIAL (L34, F-M03 effect) |
| Open WOs, utilization, PM compliance, parts consumption, SLA breaches | WO, labor, cycles, movements, breaches | `metrics.py` aggregates | same | sections | | | | values equal direct SQL | PASS |
| Low stock | `inventory_stockbalance` | `metrics.py:304` | | inventory section | | | | KPI 0 vs list 1 | **FAIL** F-M10 |
| Report snapshots | `dashboards_reportsnapshot` | `snapshot_organization` | `/report-snapshots/` | | | daily task | `test_final_celery_snapshots` | tests only | PARTIAL |

## M15 Audit & Compliance

| HPE requirement | Model/DB | Rule/service | API | UI | Perm | Async/HTMX | Tests | Browser/runtime evidence | Status |
|---|---|---|---|---|---|---|---|---|---|
| Audit logs, change history | `audit_auditlog` | `audit.record` | `/audit-logs/` | `/app/audit/` | `audit.view` | | `test_audit`, `test_m15_audit` | list/search/detail, site-scoped | PASS |
| Closure approvals | transition + `closed_by` + events | | `/work-orders/{id}/closure/` | | `work_order.review/close` | | | approvals.csv in the evidence ZIP | INTENTIONAL (I05 equivalent) |
| Evidence exports | | `exports.py`, `evidence.py` | `/audit-logs/export/`, `/evidence/` | `/app/audit/export/`, `/app/audit/evidence/work-order/{id}/` | `audit.export` | | `test_m15_evidence` | CSV/XLSX/PDF, evidence ZIP with hashes, formula-safe | PASS (L36-L38) |
| Role-controlled reports | | scope + permission | | `/app/audit/reports/` | | | | auditor/owner only export; admin 403 | PASS |
| Immutability | trigger | | PATCH/DELETE 403 | | | | `test_db_privileges` | DB owner can TRUNCATE | **PARTIAL** F-H02 |
| Security events | | signals | | | | | | JWT sign-ins unaudited | PARTIAL F-M14 |

## Mandatory complex requirements, state machines, API groups

| HPE requirement | Status | Evidence |
|---|---|---|
| PM scheduler: future WOs, no duplicates, missed/overdue | PARTIAL (**F-H01**) | beat generation, duplicates blocked; edit breaks generation |
| Assignment prevents invalid technician allocation | PASS | 409 `technician_conflict` |
| SLA: response vs resolution, pause only in configured states | PASS | real elapsed-time run |
| Inventory issue/return -> movement, transactional consistency | PASS | ledger invariant |
| Asset status/downtime via controlled transitions | PARTIAL | status PASS; downtime F-M03 |
| WO closure requires checklist, notes, evidence by work type | PASS (F-M04 caveat) | blockers observed |
| QR/barcode opaque non-secret identifiers | PASS | tokens random, not derived |
| Celery: reminders, SLA escalation, expiry alerts, snapshots | PARTIAL | SLA/PM/renewal verified; reminders and snapshots not observed; F-M12 |
| State machines SR / WO / PM / Part / Asset | see `WORKFLOW_ACCEPTANCE_AUDIT.md` | PARTIAL / PASS / PARTIAL / PASS / PARTIAL |
| API groups Assets / Maintenance / Work Orders / Inspections / Inventory / SLA / Portal | PASS (HPE names routable; aliases not in OpenAPI, L55) | `API_AUDIT.md` |
| Day-90: security hardening, tests, deployment, KT docs, performance | CONDITIONAL | F-H02, F-M18, U02, U07; tests 746 pass / 93 % coverage |
