# OpenAPI schema / endpoint contract audit

Scope: `/api/v1/schema/` generated from the live DRF code (258 operations over 196 paths, 278 component schemas). Method: generate the schema, resolve every `$ref`, and compare each operation with its URL pattern, view code (`_validated(...)`/`paginate(...)` calls) and serializer. Guard: `tests/test_openapi_contract.py`. HPE-named aliases (`/schedules/`, `/stock/`, `/reserve/`, ...) are the same viewsets and are deliberately hidden from the schema (see `config/api_aliases.py`).

## Defects found and fixed
| # | Defect | Fix |
|---|---|---|
| 1 | 69 collection/list/create operations required a phantom `{id}` path parameter (class-level `ID_PARAM`) | `apps/core/openapi.py::postprocess` keeps only path params present in the URL |
| 2 | Every paginated list was documented as a bare array although the API returns `{count,next,previous,results}` | `FieldOpsAutoSchema._get_paginator` wraps exactly the actions whose code paginates (`Paginated*List` schemas) |
| 3 | `GET /coverage/` documented as an array; it returns one `CoverageResult` | `extend_schema_serializer(many=False)` |
| 4 | 14 responses were generic `object` (asset changes/validate/validate-link, dashboards, checklist requirements, schedule generate, portal status/attachments, scan report, create-work-order, SLA metrics/process, work-order closure) | typed serializers in `apps/core/openapi_schemas.py` (+ `CreatedWorkOrderSerializer`); dashboard section id is an enum |
| 5 | `work-orders/{id}/assign|start|hold|complete` accepted an untyped object body | `WorkOrderAssign/Start/Hold/CompleteSerializer` (real accepted fields, required marked) |
| 6 | Every operation inherited the `TenantAPIMixin` docstring as its description | docstring turned into a comment; each operation now states its required **Permission** |
| 7 | Tenant selection (`X-Organization`) undocumented | `OrganizationHeader` component parameter on every secured operation, described as selector-only |
| 8 | Error responses undocumented | `ErrorResponse` envelope; 401/403 on all secured operations, 404 with path id, 400 on writes, 409 on state-changing POST/PATCH/DELETE |
| 9 | Token/refresh/me lacked purpose, examples, error text; security schemes undescribed | descriptions + placeholder examples; `jwtAuth` kept as the API mechanism, `cookieAuth` kept and explained as the browser session |

## Audit table
Counts are from the generated schema. "Request" = write operations with a typed `requestBody` / write operations (bodyless ones are explicit `request=None` actions, verified not to read `request.data`). "Response" = operations with a typed success response. `$ref` valid: all 100%.

| Module | Endpoint group | Endpoints | Request schema | Response schema | $ref | Issues |
|---|---|---|---|---|---|---|
| M01 | sites, zones, calendars, calendar-holidays, site-contacts | 26 | 11/13 typed bodies (2 explicit no-body actions) | 26/26 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M02 | asset-categories, assets, meters (docs, history, changes, validate) | 27 | 11/13 typed bodies (2 explicit no-body actions) | 27/27 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M03 | asset-components | 5 | 2/2 typed bodies (0 explicit no-body actions) | 5/5 | valid | none |
| M04 | maintenance-plans, -schedules, -cycles | 17 | 4/9 typed bodies (5 explicit no-body actions) | 17/17 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M05 | service-requests | 11 | 6/6 typed bodies (0 explicit no-body actions) | 11/11 | valid | none |
| M06/M07 | work-orders (+ labor, materials, evidence) | 18 | 11/11 typed bodies (0 explicit no-body actions) | 18/18 | valid | none |
| M08 | checklist-templates, inspections, findings | 24 | 11/14 typed bodies (3 explicit no-body actions) | 24/24 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M09 | parts, warehouses, stock-balances, stock-movements, part-reservations, work-order-parts | 35 | 14/20 typed bodies (6 explicit no-body actions) | 35/35 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M10 | contract-providers, coverage-agreements, coverage-checks, coverage | 20 | 9/12 typed bodies (3 explicit no-body actions) | 20/20 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M11 | sla-profiles, sla-trackings, sla-breaches, sla-metrics | 18 | 6/10 typed bodies (4 explicit no-body actions) | 18/18 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M12 | scan, asset-identifiers | 7 | 5/5 typed bodies (0 explicit no-body actions) | 7/7 | valid | none |
| M13 | portal, portal-accounts | 15 | 6/9 typed bodies (3 explicit no-body actions) | 15/15 | valid | no-body actions are intentional (request=None, do not read request.data) |
| M14 | dashboards, report-snapshots | 4 | 0/0 typed bodies (0 explicit no-body actions) | 4/4 | valid | none |
| M15 | audit-logs | 4 | 0/0 typed bodies (0 explicit no-body actions) | 4/4 | valid | none |
| Cross | auth, organization, members, roles, permissions, notifications, platform | 27 | 11/15 typed bodies (4 explicit no-body actions) | 27/27 | valid | no-body actions are intentional (request=None, do not read request.data) |

## Totals
1. Endpoints audited: **258**
2. Valid request schemas: **107 / 107 operations that take a body** (32 of 139 write operations are explicit no-body actions)
3. Valid response schemas: **258 / 258**
4. Broken `$ref`: **0** (unused schemas: 0)
5. Missing schemas: **0**
6. Incorrect schemas: **0 known** after the fixes (before: every paginated list, GET /coverage/, 14 generic responses and 4 untyped bodies were wrong)
7. Generic/empty schemas: **0** responses (guarded by test); `DashboardSection.data` is an intentionally open dict
8. Incorrect parameters: **0** (69 phantom path params removed)
9. Incorrect status codes: none found (create=201, actions=200, delete=204, resend=202; checked structurally and by the existing API test suites)
10. Incorrect content types: **0** (file endpoints are multipart only; others JSON + form)
11. Fixed issues: 9 (table above)
12. Remaining issues: see below

## Remaining issues (non-blocking)
- Worked examples exist only for auth (token, refresh, me); other write endpoints rely on the generated schema (types, required, enums, descriptions). More examples can be added per endpoint without code changes elsewhere.
- Dashboard `data` payloads differ per section and are described, not field-typed.
- Per-endpoint 409 is documented on state-changing POST/PATCH/DELETE as "where applicable"; not every such endpoint can actually return it.
- Status codes were verified structurally and by the existing endpoint tests, not by a runtime call to each of the 258 operations.
