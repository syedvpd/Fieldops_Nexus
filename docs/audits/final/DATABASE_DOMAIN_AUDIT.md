# Database and domain audit

Method: `\d`/`pg_constraint`/`pg_trigger` on the live audit database (PostgreSQL 16, fresh `migrate` of 53 migrations), model and migration review, and invariant queries after the browser/Celery runs. **Verdict: Database CONDITIONAL**: structure, constraints, numbering, ledger and tenancy are strong; the open items are the DB-level immutability gap (F-H02), no DB backstop for tenant FKs (F-M20) and two lifecycle-integrity defects that leave inconsistent rows (F-M03 open downtime, F-M06 stuck hierarchy).

## 1. Schema facts (measured)

| Metric | Value |
|---|---|
| Tables / foreign keys / CHECK / UNIQUE constraints / indexes (incl. unique) | 74 / 211 / 66 / 37 / 473 (145 unique) |
| Migrations applied on an empty DB | 53, no errors; `migrate --plan` afterwards: nothing; `makemigrations --check`: no changes (no drift) |
| Float/real columns | **0** (all quantities are `Decimal` with explicit precision: 14,3 stock; 16,3 meters; 5,2 labor) |
| Tenant-bearing tables without `organization_id` | none, except children of org-bound parents (`rbac_membershiprole`, `rbac_rolepermission`) and global identity/catalogue tables (`accounts_user*`, `tenancy_organization`, `rbac_permission`) |
| Triggers | one: `audit_auditlog_immutable` (row-level BEFORE UPDATE/DELETE) |
| `on_delete` | business FKs PROTECT; CASCADE only for owned children (holidays, targets/rules, exclusions, covered assets, portal grants, role permissions, notifications); no hard-delete path for sites/zones/assets |
| Reversible migrations | the only `RunPython` (`workorders.0003`) is additive and idempotent with a noop reverse; `audit.0002` RunSQL has a reverse (which removes the immutability trigger) |

## 2. Invariants checked after the audit's workflows (SQL)

| Invariant | Result |
|---|---|
| `SUM(stock movements)` equals every `StockBalance` (on-hand and reserved) | 0 mismatches |
| `on_hand >= 0`, `reserved >= 0`, `reserved <= on_hand` | 0 violations |
| Asset status equals the latest status-history row | 0 mismatches |
| WO site equals asset site | 0 mismatches (but see F-M08: nothing prevents divergence after an asset move) |
| Duplicate WO / request numbers per org | 0 |
| More than one live WO per request | 0 (and the constraint turned a reopen collision into the F-M01 500) |
| Cross-tenant references (asset->site, WO->asset, membership role->role) | 0 |
| Open downtime on REJECTED/CLOSED requests | **1** (the F-M03 reproduction) |
| Audit rows | 851 (7 platform-level with `organization_id` NULL) |

## 3. HPE entity list -> implementation

Org FK = `organization_id` present and NOT NULL. "Equivalent" entities are recorded decisions (D-054/D-061); they are not defects unless noted.

| HPE entity | Implemented as (table) | Org FK | Key constraints / indexes | Notes |
|---|---|---|---|---|
| Organization | `tenancy_organization` | root | unique slug, `uniq_org_name_ci` | |
| User | `accounts_user` | global identity | `uniq_user_email_ci` | memberships bind users to orgs |
| Role / Permission | `rbac_role`, `rbac_permission`, `rbac_rolepermission`, `rbac_membershiprole` | role yes; others via parents | `uniq_role_name_per_org`, `uniq_system_role_per_org`, partial uniques on membership roles | no DB guard for cross-org role assignment (F-M20) |
| Site | `sites_site` | yes | `uniq_site_code_per_org` (lower(code)), idx (org,status) | |
| Zone | `sites_zone` | yes | unique name per parent/site, code per site; **no self-parent CHECK** (L02) | cycle prevention in service only (F-M19) |
| Calendar/holiday/contact | `sites_operatingcalendar`, `sites_calendarholiday`, `sites_sitecontact` | yes | one default calendar per site; `contact_order_gte_1` | overnight shifts not representable (L03) |
| Asset | `assets_asset` | yes | `uniq_asset_tag_per_org` (lower), unique serial per manufacturer, commission>=purchase CHECK, idx org+status/site/category | no financial fields (U10) |
| AssetCategory | `assets_assetcategory` | yes | unique per org; JSON attribute definitions | |
| AssetComponent | `assets_assetcomponent` | yes | `UNIQUE child_id` (forest), `component_not_self`, quantity>=1 | retire guard missing (F-M06) |
| AssetMeter + readings | `assets_assetmeter`, `assets_assetmeterreading` | yes | unique name per asset, `value>=0` | monotonic only in service (L05) |
| AssetStatusHistory (+ location) | `assets_assetstatushistory`, `assets_assetlocationhistory` | yes | idx (asset,-created_at) | ORM-append-only only (L08) |
| AssetDocument / Attachment | `assets_assetdocument`, `files_attachment` | yes | size>=0; generic object_id (no DB FK to the target) | per-target download checkers |
| MaintenancePlan / Schedule / Cycle | `maintenance_maintenanceplan`, `_maintenanceschedule`, `_maintenancecycle` | yes | `UNIQUE(schedule,sequence)`, `UNIQUE(source_id) WHERE PM`, `OneToOne(work_order)`, schedule trigger/window CHECKs | sequence collision after recurrence edit (F-H01) |
| ChecklistTemplate / Item | `checklists_checklisttemplate`, `_checklistitem` | yes | `uniq_checklist_version`, one ACTIVE version per key, min<=max CHECK | applicability by work type only (F-M04) |
| Inspection / Response / Finding | `checklists_inspection`, `_inspectionresponse`, `_finding` | yes | unique (WO, template), unique (inspection,item), completed has timestamp | |
| ServiceRequest / Incident | `incidents_servicerequest` (`kind=INCIDENT`) | yes | `uniq_request_number_per_org`, idx org+status/site/asset/severity | single table by decision |
| WorkOrder | `workorders_workorder` | yes | `uniq_work_order_number_per_org`, `uniq_live_work_order_per_request`, `uniq_work_order_per_pm_source`, plan-window CHECK | |
| WorkOrderAssignment | `WorkOrder.assigned_to` + `workorders_workorderevent` | yes | event table append-only via ORM | equivalent |
| LaborEntry | `workorders_workorderlabor` | yes | `0 < hours <= 24` | no duplicate/overlap guard (L14) |
| DowntimeRecord | `incidents_downtime` | yes | `UNIQUE request_id`, end>start | F-M03 |
| ClosureApproval | SUPERVISOR_REVIEW->CLOSED transition + `closed_by/closed_at` + event + audit | n/a | | equivalent (G-1) |
| Warehouse / Part / StockBalance | `inventory_warehouse`, `_part`, `_stockbalance` | yes | unique code/part per org; `UNIQUE(warehouse,part)`; `on_hand>=0`, `reserved>=0`, `reserved<=on_hand` | |
| StockMovement | `inventory_stockmovement` | yes | quantity>0; `movement_changes_balance` CHECK | ORM-append-only only (L08) |
| PartReservation / WorkOrderPart | `inventory_partreservation`, `_workorderpart` | yes | unique per line; quantity CHECKs | |
| Warranty / ServiceContract | `contracts_coverageagreement` (`kind` WARRANTY/AMC/SERVICE_CONTRACT) + covered assets, exclusions, checks, providers | yes | `uniq_agreement_ref_per_org`, end>=start | overlap rule in service only (L27) |
| SLAProfile / EscalationRule | `sla_slaprofile`, `_slatarget`, `_escalationrule`, `_slatracking`, `_slabreach`, `_slaevent` | yes | partial uniques for active org/site scope; rule level 1-3; dedupe keys | |
| Notification | `notifications_notification` | yes | idx (org,recipient,read_at) | |
| AuditLog | `audit_auditlog` | org NULLABLE (platform events) | immutable row trigger; 5 indexes; org FK PROTECT | TRUNCATE not trapped (F-H02) |
| ReportSnapshot | `dashboards_reportsnapshot` | yes | unique (org,kind,period) | |
| IntegrationEvent | **not implemented** (no HPE consumer/contract) | n/a | | INTENTIONAL I05 |
| TechnicianProfile / Shift | Membership + role / OperatingCalendar | n/a | | equivalent (G-1) |

## 4. Transactions, locking and numbering

- Every service mutation runs in `transaction.atomic` and writes its audit row in the same transaction (verified for sites, assets, incidents, work orders, checklists, maintenance, inventory, contracts, QR, portal, SLA, tenancy, RBAC).
- `select_for_update` on all stock mutations; lock order work order -> line -> reservation -> balance (transfer: balances in pk order). Observed behaviour: insufficient stock, over-issue and below-zero adjustments rejected; ledger invariant held after reserve/issue/consume/return/reconcile/adjust. Possible deadlock in `_wind_down` (L23).
- Document numbering (`core_documentsequence`): atomic `UPDATE ... SET last_value=last_value+1`, `UNIQUE(org,key)`; WO/request numbers also carry DB uniques (verified: 22 WOs, 10 requests, no gaps/duplicates).
- Race-condition protection present and tested for stock (M09), PM generation (M04), SLA monitor (M11); **absent and untested** for M01 zone moves and M03 update/remove (F-M19, L07).
- Idempotency: stock `receive/adjust/transfer` and labor have no duplicate-submit guard (L25, L14; duplicate 1.5 h labor rows were observed after a repeated submit).

## 5. Findings from this audit that are database-relevant

F-H02 (immutability), F-M20 (tenant FK backstop), F-H01 (sequence unique key vs recurrence edit), F-M03 (open downtime rows), F-M06 (orphaned hierarchy links), F-M08 (denormalised site not propagated), L02, L05, L08, L09, L25, L27. Full text: `FINDINGS_REGISTER.md`.

## 6. Verified sound

Case-insensitive uniqueness for site code, asset tag, part number, user email; DB-level stock CHECKs; unique live WO per request; unique PM cycle per schedule+sequence and per PM source; per-org numbering; PROTECT-by-default deletes; no floats; migrations apply cleanly from scratch and show no drift; `migrate` and `makemigrations` clean under prod settings; audit rows carry `site_id` and are indexed for scoped reads.
