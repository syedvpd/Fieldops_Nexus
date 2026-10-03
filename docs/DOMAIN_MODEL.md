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
