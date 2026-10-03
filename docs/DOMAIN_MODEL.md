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
