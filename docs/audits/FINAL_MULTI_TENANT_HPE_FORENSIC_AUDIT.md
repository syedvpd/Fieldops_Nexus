# FieldOps Nexus: Multi-Tenant + HPE 15-Module Forensic Audit

Date 2026-10-03. Branch `main` @ `a4e8186`. Audit only: no product code, migration or data was changed.
Source of truth for requirements: HPE-PRD-2026-FOPS02 (`HPE_VPD_90_Day_ERP_Project_Requirements (1).md`, sections 7-12), then repo docs. Status words used: IMPLEMENTED / PARTIAL / MISSING / BROKEN / NOT VERIFIED. No percentage or overall score is given.

**Evidence method.** Every claim below was taken from code, a live route walk, a test run or a git command run in this audit. Docs and earlier reports were used only as claims to check. Items I did not exercise myself are labelled NOT VERIFIED.

---

## 1. Executive summary

- M01-M09 and M11 exist as real Django apps with models, migrations, services, state machines, API, UI, audit hooks and tests.
- **M10, M12, M13 and M14 do not exist in code** (no app, no model, no route, no test). **M15 exists only as a read-only audit log** (list, detail, filters, append-only trigger). It has no export, reports, evidence pack, retention or closure-approval entity.
- Tenant isolation is architecturally strong: fail-closed manager, direct `organization` FK on all tenant models, backend permission map on all 144 tenant API routes, and a dynamic cross-tenant sweep run in this audit (section 7).
- HPE Day-90 acceptance journeys 6 (QR) and 7 (client portal, dashboard) **cannot be demonstrated**. Journeys 1-5 are implemented (journey 3 only as separate pieces, see section 10).
- Browser acceptance for M01-M08 is documented as outstanding by the Team Lead (D-048) and I did not re-run it. No staging URL, no Git remote, no CI run, no PRs exist, so HPE section 3 and 11 evidence is absent.
- Open P0: none found with evidence. Open P1: five missing modules, Owner dashboard has no operational KPIs, and the Git/CI/staging evidence gap.

---

## 2. Intended multi-tenant architecture
Platform Super Admin creates an Organization and invites its Owner. The Owner activates the account and manages users, roles, sites and operations. Every other organization is invisible to them. One user account per person; `User -> Membership(org) -> MembershipRole(role, optional site) -> Permission`.

## 3. Actual multi-tenant architecture (verified in code)

| Question | Answer | Evidence |
|---|---|---|
| Organization model | `tenancy.Organization` (ACTIVE/SUSPENDED, never hard-deleted) | `src/apps/tenancy/models.py` |
| User to org | `tenancy.Membership` (user, organization, INVITED/ACTIVE/SUSPENDED), unique per (user, org) | same file |
| Roles per org | `rbac.Role(TenantOwnedModel)`, unique name per org, `system_key` templates, `is_owner` | `rbac/models.py` |
| Permissions | Global catalog `rbac.Permission` (82 codes) via `RolePermission`; owner role implies all | `rbac/catalog.py`, `rbac/services.py:95` |
| Role assignment | `MembershipRole(membership, role, site NULL=org-wide)` | `rbac/models.py` |
| Direct tenant ownership | 40+ models extend `TenantOwnedModel` (org FK PROTECT, not editable) | `core/models.py` |
| Indirect ownership | `RolePermission` (via role), `MembershipRole` (via membership). `AuditLog.organization` is nullable (NULL = platform event) | models |
| Tenant context | `TenantContextMiddleware` starts NO_TENANT (empty querysets); sessions resolve an ACTIVE membership; API resolves it after auth in `TenantAPIMixin`; `X-Organization` only selects among own memberships | `tenancy/middleware.py`, `tenancy/api.py` |
| Queryset scoping | `TenantManager` filters on the active org; `.unscoped()` is the only bypass | `core/tenant.py` |
| Create endpoints | `TenantOwnedModel.save()` forces the active org and blocks a cross-tenant write | `core/models.py:30` |
| Celery | Per-org loop with `tenant_context(org)`, suspended orgs skipped | `maintenance/tasks.py`, `sla/tasks.py` |
| Super Admin separation | `/platform/` and `/api/v1/platform/` run in PLATFORM mode, platform admins only. Platform admin holds no tenant permissions | `platform_admin/views.py` docstring, `tenancy/api.py` |

`.unscoped()` appears in 8 files (accounts, notifications, platform_admin, rbac, tenancy). All filter by `organization` or by the user's own memberships. A static test guards the allow-list.

**Design weaknesses (not exploits):**
- No Postgres Row Level Security (D-004: "optional later hardening").
- Same-tenant parent/child links (asset to site, WO to asset, etc.) are enforced in services and the scoped manager only. There are no composite FKs, so a hand-written SQL insert could cross tenants. P2.
- In PLATFORM mode `TenantManager` is **unfiltered**. Safe today because platform views only touch Organization/Membership/AuditLog, but any future platform view that lists tenant models would return every tenant's data. P2 (guard rail).

---

## 4. Super Admin flow audit

| Step | Status | Evidence |
|---|---|---|
| Create org + owner in one action | IMPLEMENTED | `tenancy.services.create_organization`, `platform_admin/views.py`, `tests/test_onboarding_auth.py::test_full_onboarding_invite_activate_login` |
| Invitation email via Celery on commit | IMPLEMENTED (task queued on commit, locmem email tested) | `accounts/services.py:queue_invitation_email`, `accounts/tasks.py` |
| Token expiry and one-time use | IMPLEMENTED: Django token generator, `PASSWORD_RESET_TIMEOUT` 3 days, token invalid after password set. Test `test_activation_link_is_single_use` | `config/settings/base.py:137` |
| Password policy, lockout | IMPLEMENTED: min 12 chars, Axes 5 failures per user+IP, 15 min cooloff | `base.py:132-155` |
| Activate/suspend org | IMPLEMENTED (reason required) | `test_suspend_and_reactivate_org_blocks_ui` |
| Platform view of tenant operational data | NOT EXPOSED by policy: console shows organization metadata, member counts and platform audit only | `platform_admin/views.py` |
| Real SMTP delivery | NOT VERIFIED (console/locmem backend only; no SMTP creds configured) | `base.py:199` |
| Platform configuration management | MISSING (no platform-level settings screen) P3 |

Policy note: invited existing users are activated immediately with no acceptance step (D-006). Any org Owner can therefore attach any existing account to their org. P2, Team Lead decision.

## 5. Organization Owner flow audit

Owner holds all 82 registered permissions (`is_owner`). Backend still checks every call through `HasOrgPermission`.

| Area | Can Owner do it? | Evidence |
|---|---|---|
| Users, roles, permissions | Invite, edit, deactivate; create custom roles; assign roles per site | `tenancy/services.py`, `rbac/services.py`, `/app/users`, `/app/roles` |
| Sites, zones, calendars, contacts | Full CRUD with lifecycle | M01 |
| Assets, hierarchy, meters, documents | Yes | M02/M03 |
| PM, incidents, WO, technicians, checklists, inventory, SLA | Yes | M04-M09, M11 |
| Warranty/AMC/contracts | **No such module** | M10 |
| QR | **No** | M12 |
| Client requests / portal | **No** (role `client_requester` exists with **0 permissions**) | `rbac/role_templates.py` |
| Dashboards | **Only 3 counts** (active members, pending invites, roles) plus recent audit | `ui/views.py:home` |
| Audit | List, filter, detail; **no export** | `audit/views.py` |

Role template defects:
- Templates reference permission patterns that match nothing: `contract.*`, `qr.*`, `portal.*`, `report.*`, `audit.export`. They are inert.
- `client_requester` resolves to 0 permissions.
- The `admin` role gets `*.view` only for operational modules, so it cannot create assets or work orders. This is acceptable but should be a documented decision.

## 6. RBAC audit

- Backend enforcement: all 144 tenant API routes use `TenantAPIMixin` + `permission_map`; unmapped action = denied. My route walk found **0 unmapped actions**.
- Status PATCH: asset, work order and service request serializers reject `status` in PATCH (code at `assets/api_views.py:84`, `workorders/api_views.py:71`, `incidents/api_views.py:82`).
- Site scope: `MembershipRole.site`; only permissions registered `site_scoped=True` are honoured per site (D-025). Tests: `tests/test_site_scope.py` (15).
- HTML views: `TenantPermissionMixin.required_permission`. Technician sees assigned work only (`work_order.view_assigned`).
- Role matrix (template to permission count): owner 82, admin 32, operations_manager 50, asset_manager 17, planner 25, supervisor 22, technician 18, stores 16, service_manager 16, auditor 17, client_requester 0.
- Not testable because the module is missing: Client/Requester, Audit/Compliance export, Warranty roles.

## 7. Tenant isolation audit

**Dynamic sweep run in this audit** (script kept outside the repo, temporary test file deleted after the run). Org Alpha data was created through the real services: sites, zones, assets, WO in progress, service request, checklist template, inventory part and stock, SLA profile. The Beta owner then attacked every Alpha object on every detail route and every action route with every method the route allows, through the DRF API (header `X-Organization: beta`) and through the HTML UI (session). Results are in section 7.1.

### 7.1 Sweep result
**API (Beta owner vs Alpha objects, every method each route allows):**
- 15 of 31 detail resource families had an Alpha object to attack (Membership, Role, Site, Asset, AssetCategory, AssetMeter, ServiceRequest, WorkOrder, ChecklistTemplate, Part, Warehouse, StockBalance, StockMovement, MaintenancePlan, SLAProfile) with all their nested action routes.
- **85 attack requests denied (404/403). 0 cross-tenant reads or writes succeeded.**
- 4 requests returned something else, none a leak: 2 were a 301 caused by my script mis-building a nested path (script artefact), 2 were `POST /sla-profiles/{A}/rules|targets/` returning 400 with only "field required" errors and no Alpha data. Those two show the body is validated before ownership is checked. No data returned, so LOW; the module's own cross-tenant tests (`test_m11_api_ui.py`) cover the success path.
- List endpoints (no id) fetched as Beta: **0 Alpha ids appeared in any response.**
- NOT attacked (no Alpha data in my fixture, so unproven by this sweep): audit-logs detail, notifications, zones, calendars, holidays, site-contacts, asset-components, inspections, findings, part-reservations, work-order-parts, maintenance-schedules/cycles, sla-trackings/breaches, platform organizations. Existing tests cover most of these (see 7.2), but this sweep did not.

**HTML UI (session of Beta owner, GET and POST against Alpha ids):** 83 routes with a single object id; 28 attacked with real Alpha ids; 44 requests denied (404/403); the other 12 were 405 (POST not allowed on read-only pages, no data returned); **0 leaks**. The 55 remaining routes (mostly action routes such as `transition/<action>`, `evidence`, `labor`) could not be hit with my fixture and are NOT VERIFIED by this sweep.

**Not exercised here:** exports (none exist), QR (none), portal (none), dashboards (none), Celery across two orgs.

### 7.2 Tenant table

| Area | Tenant A | Tenant B | Isolation verified? | Evidence |
|---|---|---|---|---|
| Organization | own only | own only | YES | `test_header_cannot_grant_membership`, `test_session_org_cannot_be_forged` |
| Users/Members | scoped | scoped | YES | `test_api_member_idor`, `test_ui_member_detail_idor` |
| Roles | scoped | scoped | YES | `test_api_role_idor`, `test_assigning_foreign_role_rejected` |
| Sites/zones | scoped | scoped | YES | sweep + `test_sites.py` |
| Assets / hierarchy | scoped | scoped | YES | sweep + `test_assets.py`, `test_hierarchy.py` (cross-tenant parent rejected) |
| PM | scoped | scoped | YES | sweep + `test_m04_api.py` |
| Incidents / WO | scoped | scoped | YES | sweep + `test_phase2_rules.py::test_cross_tenant_isolation_both_directions` |
| Technicians | membership-scoped | same | YES | WO assignment validation test |
| Checklists | scoped | scoped | YES | `test_m08_checklists.py` |
| Inventory | scoped | scoped | YES | sweep + `test_m09_api.py` |
| SLA | scoped | scoped | YES | `test_m11_api_ui.py` |
| Contracts | n/a | n/a | N/A, module missing | |
| QR | n/a | n/a | N/A, module missing | |
| Client portal | n/a | n/a | N/A, module missing | |
| Dashboard | home shows only org counts | same | YES, but not a real dashboard | `ui/views.py` |
| Audit | `for_organization(org)` | same | YES | `test_api_audit_idor_and_listing_scoped` |
| Files/attachments | per-target checker, org filter | same | YES | `files/views.py`, tests per module |
| Notifications | recipient + org | same | YES | `test_notifications_scoped_to_org_and_recipient` |
| Search | users and roles only, org-scoped | same | YES (narrow scope) | `ui/views.py:search` |
| Celery | per-org `tenant_context` | same | PARTIAL: code reviewed, tests exist, not run across two orgs by me |

Not covered by an isolation test: exports (none exist), QR (none), portal (none).

## 8. Module-by-module audit

For space, each module uses the required A-Q fields in compact form. Common to M01-M09, M11: models extend `TenantOwnedModel`; API via `TenantAPIMixin`; UI under `/app/...`; transitions audited via `audit.record` in the same transaction. Tenant proof is the sweep plus the module test files named below.

### M01 Site & Location Master: IMPLEMENTED (browser NOT VERIFIED)
- **HPE**: organizations, sites, buildings/zones, service areas, calendars, contact hierarchy (7.2).
- **DB**: `Site`, `Zone` (BUILDING/ZONE/SERVICE_AREA tree), `OperatingCalendar`, `CalendarHoliday`, `SiteContact`. Unique code per org.
- **Backend/API**: `sites/services.py` (activation workflow, dependency protection: deactivate refused while active assets exist, D-029). `/api/v1/sites|zones|calendars|calendar-holidays|site-contacts/`.
- **Gaps**: HPE entity `Shift` not modelled (P2). Technician `TechnicianProfile` absent (P2).
- **Tests**: `test_sites.py` (29), `test_site_scope.py` (15), `test_ui_phase1.py`, `test_migrations_phase1.py`. **Risk**: LOW.

### M02 Asset Registry: IMPLEMENTED (browser NOT VERIFIED)
- **DB**: `Asset`, `AssetCategory`, `AssetStatusHistory` + `AssetLocationHistory` (append-only), `AssetDocument`, `AssetMeter`, `AssetMeterReading`. Status machine `assets/workflow.py`; direct PATCH of status rejected.
- **Gaps**: warranty is a free-text `warranty_ref` only (PARTIAL against HPE "warranty"; coverage is M10). No document removal/versioning. Direct ACTIVE to OUT_OF_SERVICE not allowed (D-027 pending approval).
- **Tests**: `test_assets.py` (31). **Risk**: LOW.

### M03 Asset Hierarchy: IMPLEMENTED
- `AssetComponent` edges (single parent per child), same org AND same site, no self/cycle (A to B to C to A rejected, advisory lock vs races), depth <= 8, cross-tenant rejected (`assets/hierarchy.py:66-78`). M03 does not own PM generation (M04 does). Meters live in M02 (conflict C-2 open).
- **Tests**: `test_hierarchy.py` (15). **Risk**: LOW.

### M04 Preventive Maintenance: IMPLEMENTED
- `MaintenancePlan`, `MaintenanceSchedule`, `MaintenanceCycle`; time and meter based; windows; reminders; generation through the M06 service; **DB unique constraint per cycle** and `source_type/source_id` on the WO. Celery `generate_due_maintenance` every 15 min, per-org transaction, idempotent. Missed cycles collapse to one catch-up WO (D-045 Team Lead decision).
- **API deviation**: HPE example `/generate-work-orders/` is implemented as `/maintenance-schedules/{id}/generate/`. P3.
- **Tests**: `test_m04_*` (52 incl. real-thread concurrency). **Risk**: LOW. Scheduler fans out serially over all orgs (section 14).

### M05 Incident / Breakdown / Service Request: IMPLEMENTED (browser NOT VERIFIED)
- One model `ServiceRequest` with `kind` INCIDENT or SERVICE_REQUEST (documented in D-035, not silently merged). `Downtime`, `ServiceRequestHistory`. HPE chain NEW to CLOSED implemented; `reopen` is OUR DECISION. System transitions are not callable by hand. DB: one live WO per request.
- **Gaps**: HPE entity `Incident` as separate table and `ClosureApproval` entity not modelled (closure uses state `CONFIRMED`). Client-originated requests missing (needs M13). P2.
- **Tests**: `test_phase2_rules.py` (31), `test_phase2_journey.py`. **Risk**: LOW.

### M06 Work Order Management: IMPLEMENTED
- Machine DRAFT, PLANNED, ASSIGNED, DISPATCHED, IN_PROGRESS, ON_HOLD, COMPLETED, SUPERVISOR_REVIEW, CLOSED (+CANCELLED, reject_review as OUR DECISIONS). Only `/transition/` changes status; generic PATCH rejects it. `closure_blockers` enforces checklist, notes, evidence, parts. Assignment checks inactive/overlapping technicians.
- **Gaps**: HPE entity `WorkOrderAssignment` replaced by `assigned_to` field (no assignment history table; events table covers it, P3). HPE example paths `/assign/ /start/ /hold/ /complete/` are one `transition` endpoint (P3).
- **Tests**: `test_phase2_*`, `test_integration_p456.py`. **Risk**: LOW.

### M07 Technician Workspace: IMPLEMENTED (HTMX/responsive NOT VERIFIED)
- `/app/workspace/`, `WorkNote`; everything else delegates to M06/M08/M09 services; visibility `work_order.view_assigned`. HPE "route/site details" is site/asset context only, no routing (P3).
- **Tests**: `test_m07_workspace.py` (18). **Risk**: MEDIUM until browser/mobile run.

### M08 Inspection & Checklist Engine: IMPLEMENTED
- Templates with versions, frozen when active, items of 4 types, required/exception options; `Inspection`, `InspectionResponse`, `Finding`; completed inspection immutable; closure gate.
- **Tests**: `test_m08_checklists.py` (30). **Risk**: LOW.

### M09 Spare Parts & Inventory: IMPLEMENTED (browser verified locally per docs, not re-run)
- `Warehouse`, `Part`, `StockBalance`, `StockMovement` (ledger), `PartReservation`, `WorkOrderPart`. DB CHECKs: on_hand >= 0, reserved <= on_hand, movement qty > 0. Row locks; REQUESTED, RESERVED, ISSUED, CONSUMED/RETURNED, RECONCILED. Transfer paired movements. 7 real-thread concurrency tests.
- **API deviation**: HPE `/stock/ /reserve/ /issue/ /return/` live under `/stock-balances/` and `/work-order-parts/{id}/...` (P3). **Risk**: LOW.

### M10 Warranty / AMC / Contract: **MISSING**
No app, model, route, test. Only `Asset.warranty_ref` text. HPE needs: coverage terms, provider, SLA, exclusions, expiry, renewal alerts, eligible claim validation, entities `Warranty`, `ServiceContract`, expiry Celery alerts. Planned app `coverage` (Phase 7). **Risk**: HIGH (Day-90 requirement). P1.

### M11 SLA & Escalation: IMPLEMENTED
- `SLAProfile`, `SLATarget` (per priority), `EscalationRule`, `SLATracking` (one per request / WO by partial unique), `SLAEvent`, `SLABreach` (unique per target). Response vs resolution distinct; pause only on configured states; 24/7 clock (D-047). Celery `monitor_sla` every 60 s; dedupe keys prevent duplicate escalation.
- **Gaps**: HPE paths `/slas/ /escalations/` are `/sla-profiles/`, `/sla-profiles/{id}/rules/` (P3). Contract-derived SLA needs M10.
- **Tests**: `test_m11_*` (32 incl. 2 real-thread). **Risk**: LOW/MEDIUM (scale, section 14).

### M12 QR / Barcode: **MISSING**
No app, model, route. Needs opaque non-secret identifier, label generation, scan resolution inside the tenant, create service event from asset. HPE Day-90 journey 6 cannot run. P1. **Risk**: HIGH.

### M13 Client / Requester Portal: **MISSING**
No app, no `/api/v1/client/requests/`, no portal UI. Role `client_requester` is empty. HPE journey 7 cannot run. P1. **Risk**: HIGH.

### M14 Operational Dashboards: **MISSING**
No `dashboards` app. Org home shows 3 real counts (members, invites, roles). `GET /api/v1/sla-metrics/` exists (SLA only). Not present: MTTR, MTBF, downtime, open WO, technician utilization, PM compliance, parts consumption, `ReportSnapshot`, snapshot Celery. Nothing is hardcoded (the existing numbers come from queries), so there is no fake data, only absence. P1. **Risk**: HIGH.

### M15 Audit & Compliance: PARTIAL
- IMPLEMENTED: `AuditLog` (actor, org, action, target, before/after, IP, request id, timestamp), triple-layer append-only (model, queryset, Postgres trigger migration 0002), list/detail/filter UI + `/api/v1/audit-logs` (read-only, `audit.view`), org-scoped. Audit calls exist in every service module (counts: sites 17, assets 15, checklists 18, inventory 15, sla 12, maintenance 9, workorders 8, incidents 7).
- MISSING: export (CSV/XLSX/PDF) and evidence export, role-controlled reports, `ClosureApproval` entity, retention policy, login/export audit of exports, `audit.export` permission (referenced in templates, never registered).
- **Tests**: `test_audit.py` (5). P1 for export (HPE 4.2/7.2 "evidence exports, role-controlled reports"). **Risk**: MEDIUM.

### Module table

| Module | Expected scope (HPE 7.2) | Actual | DB | Backend | API | UI | RBAC | Tenant | Tests | Integration | Status | Gaps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| M01 | sites, zones, calendars, contacts | all | yes | yes | yes | yes | site-scoped | verified | 29+15 | assets, WO | IMPLEMENTED | Shift entity |
| M02 | registry, history, docs, warranty | all but coverage | yes | yes | yes | yes | yes | verified | 31 | M01, M04, M05 | IMPLEMENTED | warranty text only |
| M03 | hierarchy | all | yes | yes | yes | yes | yes | verified | 15 | M09 bridge | IMPLEMENTED | none |
| M04 | PM schedules/generation | all | yes | yes | yes | yes | yes | verified | 52 | M06, M08 | IMPLEMENTED | path naming |
| M05 | incident/request | single model | yes | yes | yes | yes | yes | verified | 31+ | M06, M11 | IMPLEMENTED | client origin |
| M06 | WO lifecycle | all | yes | yes | yes | yes | yes | verified | 40+ | M05, M08, M09 | IMPLEMENTED | assignment history |
| M07 | tech workspace | all | yes | yes | via M06 | yes | yes | verified | 18 | M06, M08, M09 | IMPLEMENTED | routing, browser unverified |
| M08 | checklists | all | yes | yes | yes | yes | yes | verified | 30 | M06 | IMPLEMENTED | none |
| M09 | inventory | all | yes | yes | yes | yes | yes | verified | 57 | M06, M07 | IMPLEMENTED | none |
| M10 | warranty/AMC | nothing | no | no | no | no | patterns inert | n/a | 0 | none | MISSING | everything |
| M11 | SLA | all except contract link | yes | yes | yes | yes | yes | verified | 32 | M05, M06 | IMPLEMENTED | M10 link |
| M12 | QR | nothing | no | no | no | no | no | n/a | 0 | none | MISSING | everything |
| M13 | portal | nothing | no | no | no | no | empty role | n/a | 0 | none | MISSING | everything |
| M14 | dashboards | 3 org counts + SLA metrics | no | no | partial | minimal | n/a | n/a | 0 | none | MISSING | all KPIs, snapshots |
| M15 | audit & compliance | log + viewer | yes | partial | read only | yes | yes | verified | 5 | all services | PARTIAL | export, reports, closure approval, retention |

## 9. Cross-module integration audit

| Link | Status | Evidence |
|---|---|---|
| M05 request to M06 WO and back (start/resolve/rework/cancel hooks) | IMPLEMENTED | `incidents.services.on_work_order_*`, `create_work_order_for_request` |
| M04 to M06 (PM creates WO via M06 service) | IMPLEMENTED | `test_integration_p456.py` |
| M06 to M08 closure gate | IMPLEMENTED | `workorders.services.closure_blockers` |
| M06/M07 to M09 (reserve/issue/consume, close/cancel hooks) | IMPLEMENTED | `inventory.services.on_work_order_*` |
| M05/M06 to M11 SLA hooks | IMPLEMENTED | `test_integration_p456.py::test_incident_to_work_order_runs_on_the_requests_clock` |
| M02/M03 to M12 QR | MISSING | |
| Asset to M10 coverage to WO eligibility | MISSING | |
| M13 portal to M05 | MISSING | |
| All to M14 dashboards | MISSING | |
| All to M15 audit | IMPLEMENTED for M01-M09, M11 (record in same transaction) | |

## 10. Master business workflow audit

| Workflow | Expected | Actual | Broken/missing link | Evidence |
|---|---|---|---|---|
| Asset registration | Org, site, zone, asset, hierarchy, QR, dashboard, audit | up to hierarchy + audit | QR, dashboard | M01-M03 |
| Breakdown | asset, incident, triage, approve, WO, assign, dispatch, tech, checklist, parts, labor, complete, review, close, resolve, audit, dashboard | all up to audit | dashboard | `test_full_journey_incident_to_closed_through_api_and_html` |
| PM | plan, schedule, due, WO, tech, checklist, inventory, complete, verify, next cycle | implemented | dashboard | `test_pm_order_flows_through_checklist_inventory_and_sla` |
| Work order | lifecycle | implemented | none | M06 |
| Technician | workspace | implemented | browser/mobile unverified | M07 |
| Checklist | execute + gate | implemented | none | M08 |
| Inventory | reserve, issue, consume/return, reconcile, ledger | implemented | dashboard | M09 |
| SLA | select, timers, pause, breach, escalate, notify | implemented | dashboard | M11 |
| Warranty | coverage, eligibility, WO context | **missing** | whole module | |
| QR | scan, asset, service event | **missing** | whole module | |
| Client portal | request, track, confirm, close | **missing** | whole module | |
| Dashboard | KPIs from DB | **missing** | whole module | |
| Audit | capture and export | capture only | export/reports | |

## 11. Database audit
- 45 migrations apply; `makemigrations --check` reports no drift (run in this audit). Ruff passes. `manage.py check`: no issues.
- Strong constraints: unique per org (codes, names, numbers), partial uniques (one live WO per request, one PM WO per cycle, one SLA tracking per subject, one breach per target), CHECKs on stock, hours, SLA minutes, dates.
- 40 composite indexes lead with `organization`.
- Gaps: no composite same-tenant FKs; no RLS (P2). `Permission` is global by design. Notification and DocumentSequence are tenant-owned.
- Production migration to Supabase is recorded by docs (45); I did not query Supabase (NOT VERIFIED).

## 12. API audit
Route walk of the live URLconf: 302 routes, 153 under `/api/`. 144 tenant routes (all `TenantAPIMixin` + permission map), 3 auth routes, `schema/` and `docs/` (public), platform routes under `PlatformAPIMixin`. Full table: generated from `permission_map` per viewset; inventory kept in the audit scratch run, summarised here by group:

Sites, zones, calendars, contacts (M01); assets, categories, meters, readings, components, documents, history (M02/M03); service-requests (+ transition, create-work-order, history, downtime, evidence); work-orders (+ transition, reassign, labor, materials, evidence, events, closure); parts, warehouses, stock-balances, stock-movements, part-reservations, work-order-parts (+ reserve, issue, return, consume, reconcile, release, cancel); maintenance-plans/schedules/cycles; checklist-templates, inspections, findings; sla-profiles, sla-trackings (+ `process`, gated by `sla.process`), sla-breaches, sla-metrics; members, roles, organization, audit-logs, notifications.

Findings:
- `GET /api/v1/schema/` and `/docs/` are anonymous (drf-spectacular default). P3.
- No endpoint returns 200 and does nothing found in the route walk; not exhaustively executed.
- Absent HPE groups: `/client/requests/`, `/status/`, HPE-named `/slas/`, `/checklists/`, `/stock/`. P1 (portal) / P3 (naming).

## 13. UI / HTMX audit
- Server-rendered Bootstrap 5 + HTMX; viewport meta present. Nav: Overview, Operations, Assets and Locations, Inventory, Maintenance, Service levels, Administration, Compliance.
- HTML sweep: every tenant HTML detail route with one UUID was probed as Beta against Alpha ids (GET and POST). See 7.1.
- Browser acceptance: M01-M08 browser acceptance is **NOT VERIFIED** (D-048). M09, M04, M11 browser-verified on a local QA database per docs; I did not re-verify. Responsive 4-size sweep and Chrome/Edge/Firefox: NOT VERIFIED. No E2E test suite in the repo (`tests/e2e` does not exist).
- UI absent: dashboards, QR labels, portal, warranty/contracts, audit export. Global search covers users and roles only.

## 14. Celery / Redis audit

| Task | Schedule | Tenant context | Idempotent | Retry | Notes |
|---|---|---|---|---|---|
| `monitor_sla` | 60 s | per-org `tenant_context`, ACTIVE orgs only | yes (dedupe keys, unique breach) | OperationalError x5 | scans all ACTIVE trackings of every org each run, serially |
| `generate_due_maintenance` | 15 min | per-org | yes (DB unique per cycle) | per-schedule task retries | serial org loop |
| `send_invitation_email` | on commit | by user/org ids | n/a | OSError backoff | |
| `send_notification_email` | on demand | | | OSError backoff | |
| `clear_expired_sessions` | daily | n/a | yes | | |
| Warranty/AMC/contract expiry alerts | none | | | | MISSING (HPE 8.4) |
| Report snapshots | none | | | | MISSING (HPE 8.4, `ReportSnapshot`) |
| PM reminders | inside PM run | per-org | once per occurrence | | |

Redis in prod: pending per docs (free-tier quota used). NOT VERIFIED.

## 15. Security / IDOR audit
- IDOR sweep: section 7.1.
- Secrets: `.env`, `.env.prod`, `.env.qa-users` are git-ignored and untracked; tracked-file scan found only test/CI placeholder credentials.
- Login throttle, CSRF, secure cookies in prod, HSTS in prod settings. DRF throttles anon 30/min, user 600/min. Upload validation by extension, MIME and size (`core/uploads.py`).
- JWT access 15 min, refresh rotation on.
- Open items: public OpenAPI schema (P3); D-006 auto-activation of existing users (P2); QA passwords were echoed into a chat transcript (per MODULE_STATUS, rotate before real use, P2); RLS absent (P2).
- OWASP review and dependency/secret scanning pipeline: NOT VERIFIED (not found in repo).

## 16. Browser acceptance status
Not performed in this audit. Docs say M01-M08 outstanding (D-048), M09/M04/M11 local-QA verified. No staging URL.

## 17. Automated test coverage
- 555 tests collected. Ruff clean, no migration drift, `manage.py check` clean.
- Run result in this audit: one unbroken full run was **not** achieved. The first full run (with a wrong DB password) was discarded. The second run showed only passes up to ~92%, then the process exited with code 255 for a reason I did not determine (it overlapped with other work in this session). I then re-ran the final eight files (`test_site_scope, test_sites, test_tenant_isolation, test_ui, test_ui_actions, test_ui_phase1, test_ui_phase2, test_phase2_rules`): **165 passed**. No failed test was observed anywhere. Treat "555 pass" as NOT VERIFIED in a single run until re-run clean.

| Category | Where | Notes |
|---|---|---|
| Unit | `test_m04_recurrence`, `test_core`, model tests | |
| API | `test_m09_api`, `test_m04_api`, `test_m11_api_ui`, `test_phase2_*` | |
| Integration/journey | `test_phase2_journey`, `test_integration_p456`, `test_m07_workspace` full journey | one PM journey, one breakdown journey; **no** QR/portal/warranty journey |
| RBAC | `test_rbac` (17), `test_site_scope` | |
| Tenant | `test_tenant_isolation` (18), per-module cross-tenant tests | |
| Workflow | machine matrix tests per module | |
| Database | `test_migrations_phase1..6`, constraint tests | |
| Concurrency/Celery | `test_m04_concurrency`, `test_m09_concurrency`, `test_m11_concurrency` | real threads |
| Security | `test_login_integration` (17), audit trigger | |
| Browser/E2E | none in repo | |

No tests exist for: dashboards, QR, portal, warranty, audit export, org-wide fan-out at scale, email delivery through SMTP.

## 18. HPE traceability (HPE-PRD-2026-FOPS02)

| HPE requirement | Status | Evidence |
|---|---|---|
| 7.2 M01 sites, zones, service areas, calendars, contacts | IMPLEMENTED | M01 |
| 7.2 M02 registry fields, location, owner, status, docs | IMPLEMENTED | M02 |
| 7.2 M02 warranty | PARTIAL | text field only |
| 7.2 M03 hierarchy | IMPLEMENTED | M03 |
| 7.2 M04 time/meter schedules, recurring, checklists, windows, reminders | IMPLEMENTED | M04 |
| 7.2 M05 failure, severity, files, linkage, downtime, impact | IMPLEMENTED | M05 |
| 7.2 M06 create to close with labor/material/time | IMPLEMENTED | M06 |
| 7.2 M07 jobs, site details, checklist, notes, attachments, parts, time, evidence | IMPLEMENTED (route details: PARTIAL) | M07 |
| 7.2 M08 templates, mandatory, exceptions | IMPLEMENTED | M08 |
| 7.2 M09 stock, issue/return, reservations, min-max, transfer, consumption | IMPLEMENTED | M09 |
| 7.2 M10 warranty/AMC/coverage/claim validation | MISSING | |
| 7.2 M11 targets, escalation, breach, supervisor alerts | IMPLEMENTED | M11 |
| 7.2 M12 QR | MISSING | |
| 7.2 M13 portal | MISSING | |
| 7.2 M14 MTTR, MTBF, downtime, open WO, utilization, SLA breaches, PM compliance, parts consumption | MISSING | |
| 7.2 M15 audit logs, closure approvals, change history, evidence exports, role-controlled reports | PARTIAL | |
| 8.1 five state machines | IMPLEMENTED (PM derived from WO state, `selectors.cycle_state`) | |
| 8.2 entities TechnicianProfile, Shift, WorkOrderAssignment, ClosureApproval, Warranty, ServiceContract, ReportSnapshot, IntegrationEvent, Incident (separate) | MISSING (9) | grep of all `models.py` |
| 8.3 API groups Assets, Maintenance, Work Orders, Inspections, Inventory, SLA | IMPLEMENTED with different path names | |
| 8.3 Portal API | MISSING | |
| 8.4 PM no duplicates, missed cycles | IMPLEMENTED | |
| 8.4 invalid technician allocation prevented | IMPLEMENTED | |
| 8.4 SLA response vs resolution, pause only configured | IMPLEMENTED | |
| 8.4 inventory movements, consistency | IMPLEMENTED | |
| 8.4 controlled asset status/downtime | IMPLEMENTED | |
| 8.4 closure needs checklist, notes, evidence | IMPLEMENTED | |
| 8.4 QR opaque identifiers | MISSING | |
| 8.4 Celery: reminders, SLA, contract/warranty alerts, report snapshots | PARTIAL (warranty/contract alerts and snapshots missing) | |
| 2.2 audit includes export and login actions | PARTIAL (login yes, export none) | |
| 2.2 rate limiting | IMPLEMENTED (DRF throttles) | |
| 2.2 OWASP review before Day 90 | NOT VERIFIED | |
| 9 Day-90 journeys 1-5 | IMPLEMENTED (automated); browser NOT VERIFIED | |
| 9 Day-90 journeys 6, 7 | MISSING | |
| 3.1 / 11 GitHub URL, tags, PRs, staging, CI evidence | MISSING (no remote, no staging branch, no PRs, CI never run) | `git remote -v` empty |
| 12.3 handover: ER diagram | MISSING (no ERD found) | |
| 12.3 handover: README, `.env.example`, Dockerfile, compose, lockfile | IMPLEMENTED (README, `.env.example`, `requirements.lock`) | |

## 19. Missing requirements (all P1 unless noted)
M10, M12, M13, M14 (all), M15 export/reports/closure approval (P1), warranty/contract Celery alerts, `ReportSnapshot` job, HPE entities listed above (P2), ER diagram (P1 for handover), GitHub remote/tags/PRs/staging/CI run (P1), `Shift`/`TechnicianProfile` (P2).

## 20. Partial implementations
M15 (log only), M02 warranty (text), M07 (no routing, browser unverified), Celery (2 of 4 HPE job families), tenant isolation of Celery (reviewed, not cross-org tested by me).

## 21. Broken implementations
No broken implementation was found with evidence. Defects of lesser class: inert permission patterns in role templates and an empty `client_requester` role (P2).

## 22. Unverified areas
Single-run full test result; browser M01-M08 and the 4-size responsive sweep; Chrome/Edge/Firefox; SMTP delivery; Supabase state; Redis in prod; OWASP/dependency scan; load/query-count review (no N+1 or timing run); multi-org Celery fan-out; concurrency beyond the recorded tests.

## 23. Documentation vs code conflicts
- `core/tenant.py` docstring says the `.unscoped()` allow-list is in `tests/test_static_guards.py`, which does not exist. It lives in `tests/test_tenant_isolation.py::test_unscoped_is_only_used_in_trusted_modules` (PROJECT_MAP is right).
- `docs/TRACEABILITY.md` says "110 tests" for Phase 0; `MODULE_STATUS.md` says 128; current total is 555.
- PROJECT_MAP "Apps" table omits `sla`, and its test list omits Phase 4-6 files (they are listed only in trailing notes).
- TRACEABILITY lists M10 app as `coverage`, M12 `qr`, M13 `portal`, M14 `dashboards`; none exist (consistent with "NOT STARTED", not a conflict, but the planned names are unverified).
- Open numbering/ownership conflicts already recorded: C-2 meters M02 vs M03. No renumbering done.
- HPE says incident and service request are separate entities (8.2); the repo merges them with `kind` (D-035, documented). Team Lead should confirm this satisfies HPE.

## 24. Items needing Team Lead attention
1. D-006: existing accounts auto-added to another org without consent.
2. Incident and Service Request as one table vs HPE's two entities.
3. C-2 meters M02/M03.
4. Whether the `admin` role should hold operational permissions.
5. D-027 direct ACTIVE to OUT_OF_SERVICE.
6. HPE API path naming deviations (accept or alias).
7. Whether schema/docs should be public.
8. Supabase RLS or composite FKs as defence in depth.

## 25. Exact remaining work (recommended order)
1. Re-run full suite once cleanly; record count and timing. (small)
2. **M10 Warranty/AMC/Contract** (entities, coverage engine, eligibility at WO create, expiry Celery, permissions, UI, tests). P1.
3. **M12 QR**: opaque token model, label render, tenant-scoped scan resolver, "create request from asset". P1.
4. **M13 Portal**: client memberships/role permissions, `/api/v1/client/requests/`, status, attachments, confirm/close, only own org (and own requests). P1.
5. **M14 Dashboards**: KPI services with documented queries (MTTR, MTBF, downtime, open WO, utilization, SLA, PM compliance, parts consumption), `ReportSnapshot` + Celery, Owner home. Isolation test: A transaction changes A only. P1.
6. **M15 completion**: export CSV/XLSX/PDF with `audit.export`, audit of exports, evidence download, closure-approval entity, retention note. P1.
7. Fix role templates (register real permission codes, give `client_requester` real ones).
8. Full browser acceptance M01-M15, 4 sizes, three browsers; `tests/e2e` journeys 1-7.
9. Hardening: query-count/N+1 pass, SLA/PM fan-out (per-org subtasks, `next_check_at` index), schema auth, OWASP + secret/dependency scan, ER diagram, user/admin/KT docs.
10. Git governance: remote, `staging` branch, PRs, tags, first CI run, staging URL.

## 26. Final release / acceptance readiness
Not release-ready against HPE section 12.1: four mandatory modules and the M15 export are absent, Day-90 journeys 6 and 7 cannot be shown, and the Git/CI/staging/ER-diagram evidence does not exist. The implemented M01-M09 and M11 core is consistent with its tests and has no defect I could demonstrate; its browser acceptance remains open.

---

## Final answer format

**A. Definitely working (code + test evidence):** tenant fail-closed scoping, backend permission map on all tenant API routes, status-PATCH rejection, org onboarding and single-use activation, audit append-only trigger, M01-M03, M04 (idempotent generation), M05/M06 workflows and hooks, M08 gate, M09 ledger and constraints, M11 timers and dedupe, ruff and migration-drift clean.

**B. Partially working:** M15 (log only), M07 (browser/mobile unverified, no routing), Celery jobs (2 of 4 HPE families), M02 warranty (text).

**C. Missing:** M10, M12, M13, M14, audit export/reports, 9 HPE entities, portal API, Git remote/CI/staging/ER diagram.

**D. Broken:** nothing demonstrated broken. Role templates with inert patterns / empty client role are defects.

**E. Not verified:** single-run full suite, browser M01-M08 and responsive/cross-browser, SMTP, Supabase and Redis prod, OWASP scan, performance.

**F. Tenant isolation verdict:** see 7.1 for the live sweep. Code review plus tests show no cross-tenant read or write path in implemented modules. Residual risks: no RLS, no DB-level same-tenant FK, PLATFORM-mode manager unfiltered.

**G. Super Admin to Owner flow:** create org, invite, token (3-day, single-use), password, activate, login: IMPLEMENTED and tested; real SMTP NOT VERIFIED.

**H. Owner end-to-end:** Owner can run users, roles, sites, assets, PM, incidents, WOs, checklists, inventory and SLA end to end; cannot manage contracts, QR, client portal, and has no operational dashboard.

**I. HPE requirements still unsatisfied:** M10, M12, M13, M14, M15 export/reports, journeys 6-7, handover items (ER diagram, Git evidence), Celery alerts/snapshots.

**J. Doc/implementation conflicts:** section 23.

**K. Next implementation order:** section 25.

**L. Final acceptance blockers:** M10, M12, M13, M14, M15 export, zero browser evidence for M01-M08, no Git/CI/staging evidence, unverified full test run.
