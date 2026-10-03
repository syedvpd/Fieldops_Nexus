---
name: tenant-isolation
description: How tenant isolation and RBAC work in FieldOps and the exact tests every new endpoint needs. Load when adding models/endpoints or reviewing security.
---
- Models: `TenantOwnedModel` -> `objects` is fail-closed; use `Model.objects.for_organization(org)` explicitly in services; `.unscoped()` only in allow-listed modules (static test).
- Celery/management code: wrap in `core.tenant.tenant_context(org)`.
- API: `TenantAPIMixin` + `permission_map` (unmapped = 403). `__member__` pseudo-permission only for strictly self-scoped data.
- Detail lookups must filter by organization (and site scope from M01) and return 404 for foreign objects.
- Required tests per endpoint: allowed role; wrong role; unauthenticated (401); foreign-org object (404/403); header naming a non-member org (403 `not_a_member`); suspended org; suspended membership; wrong site scope; invalid state (409). Copy patterns from `tests/test_tenant_isolation.py` and `tests/test_rbac.py`.
