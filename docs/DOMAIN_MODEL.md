# Domain model (Phase 0)

```
User (identity; is_platform_admin)
Organization (tenant; status ACTIVE|SUSPENDED)
  |- Membership (user x org; INVITED|ACTIVE|SUSPENDED)  -- MembershipRole --> Role
  |- Role (per org; is_owner, system_key) -- RolePermission --> Permission (global catalog)
  |- Notification (recipient, level, link, read_at)
  |- Attachment (generic target, sha256, read_permission)
  `- AuditLog (append-only; organization nullable for platform events)
```
- Tenant-owned (`TenantOwnedModel`): Membership, Role, Notification, Attachment. Indirect (via parent): RolePermission, MembershipRole. Global: Permission, User, Organization. AuditLog: nullable org, own manager.
- Constraints: unique lower(email); unique lower(org name) and slug; unique (user, org); unique role name per org (case-insensitive); one system role per key per org; unique (role, permission) and (membership, role).
- Invariants (services): an org always keeps >= 1 Owner; only Owners grant/revoke Owner; roles must belong to the same org; users cannot change their own access.

Future entities from HPE section 8.2 are added by their phase (Site, Zone, Asset, ... see `TRACEABILITY.md`); each extends `TenantOwnedModel`.

# Phase 1 additions (M01, M02, M03)
```
Organization
  `- Site (code unique/org, status ACTIVE|INACTIVE, timezone, contact info)
       |- Zone (BUILDING | ZONE | SERVICE_AREA; parent -> tree inside the site, max depth 6)
       |- OperatingCalendar (working days 1-7, hours or 24x7, one default per site) -- CalendarHoliday
       |- SiteContact (escalation_order unique per site)
       `- Asset (asset_tag unique/org; (manufacturer, serial) unique/org; status; zone optional; owner = Membership)
            |- AssetCategory (per org)            |- AssetStatusHistory (append-only)
            |- AssetLocationHistory (append-only) |- AssetDocument -> files.Attachment
            |- AssetMeter -- AssetMeterReading (monotonic)
            `- AssetComponent (parent -> child OneToOne; ASSEMBLY|COMPONENT|REPLACEABLE_PART)
rbac.MembershipRole.site (nullable): organization-wide when NULL, else limited to that site
```
- All new tables extend `TenantOwnedModel` (organization FK, fail-closed manager). Referenced objects are checked for the same organization in services (zone must belong to the asset's site; hierarchy edges must share organization and site).
- Constraints: lower(site code) per org; zone name per parent and code per site; one default calendar per site; holiday per (calendar, date); contact order per site; lower(asset_tag) per org; commission_date >= purchase_date; meter reading >= 0; component parent != child and quantity >= 1.
- Status values: ACTIVE, UNDER_MAINTENANCE, OUT_OF_SERVICE, RETIRED, DISPOSED (see D-027).

## Phase 2 additions (M05 / M06)
```
Asset ---< ServiceRequest (number INC-/SR-; kind; severity; service_impact; status; reported_by = Membership; site = asset.site)
              |- Downtime (one per request; started_at, ended_at)
              |- ServiceRequestHistory (append-only)
              |- Attachment (evidence)
              `---< WorkOrder (source_request nullable; at most one LIVE per request)
Asset ---< WorkOrder (number WO-; work_type; priority; status; assigned_to = Membership; planned window)
              |- WorkOrderEvent (append-only: transitions, re-assignments)
              |- WorkOrderLabor (technician, date, hours 0<h<=24)   |- WorkOrderMaterial (free text; stock is M09)
              `- Attachment (evidence)
core.DocumentSequence (organization, key, last_value): number allocation
```
- Constraints: unique number per organization; `uniq_live_work_order_per_request` (partial, excludes CANCELLED/CLOSED); downtime end >= start; plan window ordered; labor hours in (0, 24]; material quantity > 0.

## Phase 3 additions (M08 / M07)
```
ChecklistTemplate (key = family, version, status DRAFT/ACTIVE/INACTIVE, work_type blank=any, is_required)
   `---< ChecklistItem (position, prompt, item_type TEXT/NUMERIC/BOOLEAN/SELECTION, required, options, exception_options, min/max/unit, evidence_required)
   `---< Inspection (template version, work_order nullable, asset, site, status IN_PROGRESS/COMPLETED, started_by / completed_by = Membership)
              |---< InspectionResponse (item, value_text | value_number | value_bool, is_exception) - one per item
              |       `- Attachment (evidence)
              `---< Finding (item?, work_order?, asset, site, severity, status OPEN/RESOLVED, resolution)  `- Attachment (evidence)
WorkOrder ---< WorkNote (M07, append-only technician note)
```
- Constraints: one ACTIVE version per checklist key; unique (key, version); unique item position per template (deferred); min <= max; one inspection per (work order, template version); completed inspection has `completed_at`; one response per (inspection, item); note body not empty.

