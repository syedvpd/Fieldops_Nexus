# API tester quick start

Swagger UI: `/api/v1/docs/` · OpenAPI schema: `/api/v1/schema/`. No real passwords appear here; ask the Team Lead for the QA password of the seeded `*.test` users.

1. **Open Swagger** at `/api/v1/docs/`.
2. **`POST /api/v1/auth/token/`** with `{"email": "tech@alpha.test", "password": "YOUR_PASSWORD"}`. Wrong credentials and inactive accounts both return `401`; more than 10 attempts/min returns `429`.
3. **Copy `access`** from the response (valid 15 minutes; `refresh` lasts 1 day).
4. Click **Authorize**.
5. Paste the token into **`jwtAuth`** (token only, Swagger adds `Bearer`). Ignore `cookieAuth`: it is the browser session of the web UI, accepted by the same endpoints but not meant for API consumers.
6. **`GET /api/v1/auth/me/`** confirms identity and returns the organizations you can act in (`slug` is what `X-Organization` takes).
7. **Test module endpoints.** Every operation shows its required permission, request schema (required fields marked), enums, and `400/401/403/404/409` error responses. Lists return `{count, next, previous, results}` (`page`, `page_size`). Renew with `POST /api/v1/auth/token/refresh/` `{"refresh": "YOUR_REFRESH_TOKEN"}`.
8. **Negative RBAC:** repeat a write with a lower-privilege user (table below) and expect `403`; with no token expect `401`; a state-invalid action (e.g. start a DRAFT work order) returns `409`.
9. **Tenant isolation:** log in as `owner@alpha.test`, create/list a record, copy its id; log in as `owner@beta.test` and request that id: expect `404` (never `200`). Lists must never contain the other organization's rows.

## Tenant selection (real behaviour)
All tenant-owned data is scoped to the caller's active organization. A user with exactly one active membership needs nothing extra. A user with several sends `X-Organization: <org slug or id>`. The header only **selects among your own memberships** (otherwise `403 not_a_member`); it never grants access. A suspended organization returns `403 organization_suspended`.

## Roles to use
Source of truth for what each role may do: `rbac/role_templates.py`, `ROLE_ACCESS_ACCEPTANCE.md`, `ROLE_NAVIGATION_MATRIX.md`. Seeded users (Alpha unless stated):

| Role | User | Expect 200/201 | Expect 403 |
|---|---|---|---|
| Owner | owner@alpha.test | everything in the org incl. `/members/`, `/roles/`, `/organization/` | `/platform/organizations/` (not a platform admin) |
| Operations Manager | ops@alpha.test | work orders, service requests, assets, parts, SLA, dashboards, audit view | `/members/`, `/roles/` |
| Maintenance Supervisor | supervisor@alpha.test | work orders (assign, review, close), service requests, inspections, dashboards | `/contract-providers/` write, `/members/`, audit |
| Maintenance Planner | planner@alpha.test | maintenance plans/schedules/generate, work-order create/plan | `/members/`, audit-logs |
| Technician | tech@alpha.test | own assigned work orders (start/hold/complete, labor, evidence), scan | `/sites/`, `/assets/` lists, `/parts/`, `/members/`, `POST /work-orders/` |
| Asset Manager | assets@alpha.test | sites, assets, meters, identifiers | `/stock-balances/receive/`, `/sla-profiles/` write, `/members/` |
| Auditor | auditor@beta.test, reader@alpha.test (read-only) | all reads, audit-logs, report-snapshots | every `POST/PATCH/DELETE` |
| Client / Requester | client@alpha.test | `/portal/requests/`, `/portal/assets/` (own only) | every non-portal endpoint |
| Super Admin | platform admin | `/platform/organizations/` (platform scope only) | tenant data of any organization |
| Beta users | owner@beta.test, tech@beta.test | their own organization | any Alpha object (`404`) |
