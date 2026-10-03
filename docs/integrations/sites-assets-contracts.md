# Phase 1 plan and integration contracts: M01 Sites, M02 Assets, M03 Hierarchy

Dependency direction: `core/tenancy/rbac/audit/files` -> **M01 `sites`** -> **M02 `assets`** (+ M03 `assets.hierarchy`) -> later modules.
`sites` never imports `assets` at module level (it reads `site.assets` / `assets.workflow.TERMINAL_STATES` lazily for the "active assets" rules). Later modules import only the **service functions and read selectors listed below**, never write asset tables directly.

## Plan (as implemented)
- **Understanding:** HPE M01 = organizations, sites, buildings/zones, service areas, operating calendars, contact hierarchy. M02 = asset ID, category, model, serial, purchase/commission dates, location, owner, warranty, status, documents (+ AssetMeter, AssetStatusHistory entities, `/assets/`, `/assets/{id}/history/`, `/meters/` API group). M03 = parent-child assemblies, components, replaceable parts, relationship tree. Asset status is a controlled workflow (HPE 8.4).
- **Schema impact:** new apps `sites` (Site, Zone, OperatingCalendar, CalendarHoliday, SiteContact) and `assets` (AssetCategory, Asset, AssetStatusHistory, AssetLocationHistory, AssetDocument, AssetMeter, AssetMeterReading, AssetComponent); `rbac.MembershipRole.site` (nullable FK) with replaced uniqueness constraints (migrations `sites.0001`, `assets.0001`, `rbac.0002`).
- **Permissions:** `site.*`, `zone.*`, `calendar.*`, `asset.*` (see `sites/permissions.py`, `assets/permissions.py`); all except `site.create` and `asset.category.manage` are *site-scopable*.
- **State machine:** `assets/workflow.py` (documented transitions; only `assets.services.change_status` applies them).
- **API / UI / tests:** see `docs/TRACEABILITY.md` (Phase 1 evidence) and `docs/manual-tests/PHASE_1_MANUAL_TEST.md`.

## Site scope (rbac) contract
- `MembershipRole.site IS NULL` = organization-wide; otherwise the role's *site-scopable* permissions apply to that site only. Owner is always organization-wide. A site assignment can never grant non-scopable permissions (user.*, role.*, organization.*, `site.create`, `asset.category.manage`).
- `rbac.services.has_permission(membership, code, site=None)`: org-wide grants, or (with `site`) a grant for that site. `has_permission_anywhere` is the endpoint gate. `site_scope(membership, code)` returns a `SiteScope` (`all_sites` / `site_ids`, `.filter(qs, "site_id")`, `.allows(site)`) that every list/detail query must use. Detail lookups of out-of-scope or foreign objects answer **404**; visible-but-not-permitted answers **403**.
- Files: `files.access.register("<app>.<model>", checker)` lets a module authorise attachment downloads per target (assets register `assets.assetdocument` -> `asset.view` for the asset's site).

## Stable contracts for later modules
| Consumer | Needs | Use |
|---|---|---|
| M04 PM | assets, categories, meters/readings, hierarchy, status | read `assets.selectors.assets_for/get_asset/meters_for`, `AssetMeterReading` ordered by `read_at`; readings are monotonic (`record_reading(meter, value, read_at, source="pm")`); PM must not edit assets. |
| M05 Incident, M06 Work Order | asset FK, site/zone, status transitions, downtime | reference `assets.Asset` by FK (PROTECT); to change asset status call `assets.services.change_status(asset, action=..., reason=..., actor=..., source="incident")` (validated, history + audit atomic). **Direct writes to `Asset.status` are forbidden.** Downtime windows belong to M05 (`DowntimeRecord`), not to asset tables. |
| M07/M08 | asset context, hierarchy | `assets.hierarchy.ancestors/build_tree/root_of` (bounded: `MAX_DEPTH=8`). |
| M09 Inventory | replaceable parts | `AssetComponent.part_number` (+`quantity`) is the bridge; M09 should map `part_number` to `Part`, not duplicate hierarchy. |
| M10 Warranty/AMC | coverage per asset | `Asset.warranty_ref` is a free-text pointer only; M10 adds its own `Warranty`/`ServiceContract` models with an FK to `Asset` and may later replace/normalise the text field. |
| M11 SLA | site operating calendars | `sites.OperatingCalendar` (working days 1-7, hours in site time zone, 24x7 flag) + `CalendarHoliday`; default calendar = `is_default`. SLA pause/business-hours logic lives in M11. |
| M12 QR | opaque asset identity | `Asset.id` is a UUID (non-sequential); `asset_tag` is human-readable and non-secret. QR payloads must use a separate opaque token (M12), not `asset_tag`. |
| M13 Portal / M14 / M15 | counts, history | `AssetStatusHistory`, `AssetLocationHistory` (append-only), `assets.selectors.change_log` (audit based). |
| Any | tenant + scope | `TenantOwnedModel`, `rbac.site_scope`, `audit.record`. |

## Events / hooks
No asynchronous event bus exists yet (IntegrationEvent entity is Phase 8/9). Phase 1 therefore exposes **synchronous service entry points** and audit actions (`asset.status_changed`, `asset.location_changed`, `asset.component_*`, `asset.meter_reading_recorded`, `site.deactivated`, ...). When `IntegrationEvent` arrives, the same service functions are the single place to publish from.

## Known gaps / not in Phase 1
- Document removal/versioning (upload + secure download only); asset QR/labels (M12); warranty logic (M10); PM/WO/incident links (later phases); bulk import/export (M15).
- No Postgres RLS (same as Phase 0 decision D-004).
