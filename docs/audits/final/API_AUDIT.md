# API audit

**Verdict: API CONDITIONAL.** The REST surface is consistent (envelope, status codes, tenancy, RBAC) and the schema validates with zero warnings. Open items: an intra-tenant site-scope gap on two write routes (F-M07), JWT sign-ins unaudited (F-M14), all REST endpoints fail with 500 if Redis is down (F-M11), HPE alias routes undocumented in OpenAPI (L55), and a few consistency nits (L53, L54).

## 1. Inventory

- 268 URL patterns under `/api/v1/` (excluding format suffixes), 196 documented paths / 258 operations / 206 schemas in the generated OpenAPI. The 72 undocumented routes are the HPE-named aliases in `src/config/api_aliases.py` (`/stock/`, `/reserve/`, `/issue/`, `/return/`, `/slas/`, `/breaches/`, `/escalations/`, `/schedules/`, `/checklists/`, `/client/requests/`, `/generate-work-orders/`) which are the same viewsets re-exposed under HPE's short names (INTENTIONAL, decision recorded in the module docstring). The canonical routes (`/maintenance-schedules/`, `/stock-balances/`, `/work-order-parts/`, `/sla-profiles/`, `/sla-breaches/`, `/portal/requests/`...) are documented.
- HPE "mandatory API groups" check: assets (`/assets/`, `/assets/{id}/history/`, `/meters/`) present; maintenance (`/maintenance-plans/`, `/schedules/`, `/generate-work-orders/`) present; work orders (`/work-orders/`, `/assign/`, `/start/`, `/hold/`, `/complete/` as real routes plus `/transition/`) present; inspections (`/checklists/`, `/inspections/`, `/findings/`) present; inventory (`/parts/`, `/stock/`, `/reserve/`, `/issue/`, `/return/`) present; SLA (`/slas/`, `/breaches/`, `/escalations/`) present; portal (`/client/requests/`, `/status/`) present.
- Auth: session cookie (with CSRF) and JWT bearer (`/api/v1/auth/token/`, `/refresh/`); `X-Organization` (slug) only selects among the caller's own ACTIVE memberships.

## 2. Authentication, authorization, tenant scope (runtime)

| Check | Result |
|---|---|
| 70 list endpoints x 14 principals (980 requests) | no anonymous 200, no 5xx; 401 for anonymous; client limited to portal routes; technician sees 1/14 work orders; platform admin 403 on tenant routes (`TENANT_RBAC_SECURITY_AUDIT.md` section 2.1) |
| 52 detail + 104 action endpoints with foreign IDs, both directions | 0 leaks, no existence oracle |
| 11 roles x 18 write calls | match role templates; audit row `PATCH`/`DELETE` 403 for all |
| JWT with a non-member `X-Organization` | 403 `not_a_member` |
| Unmapped DRF action | denied (403) by design (`permission_map`), including GET on POST-only routes (L53) |
| Throttling | `anon 30/min`, `user 600/min`, `login 10/min` configured; login additionally locked by axes (5 failures); throttle identity trusts client `X-Forwarded-For` (L47) |

## 3. Validation, serialization, errors

- Uniform error envelope `{"error": {"code", "message", "details", "request_id"}}`; 400 field-level validation (`details.fields`), 404 for foreign/non-existent/malformed IDs (identical bodies), 409 for state conflicts (`invalid_transition`, `technician_conflict`, `closure_blocked` with a blockers list), 403 permission, 429 QR throttle, 410 for revoked QR.
- Mass assignment: explicit serializer fields; `organization`/`id`/`created_by` ignored, `status` rejected with a clear 400 telling the caller to use `/assets/{id}/transition/`.
- State transitions: `POST /work-orders/{id}/transition/` and the HPE-named routes share the service layer; invalid/duplicate/unauthorized transitions return 409/403 without side effects (verified with DB reads).
- 500 paths found: reopen then create WO (F-M01), Redis outage (F-M11).

## 4. Pagination, filtering, ordering

- Envelope `{count, next, previous, results}`; `page_size` default 25, capped at 200 (`page_size=100000` returns 21 rows of 21); invalid page -> 404.
- Filters via `django-filter` plus explicit selectors; **unknown filter values or ordering fields are silently ignored** (`?status=BOGUS` -> 200 with 0 rows; `?ordering=nonexistent` -> default order; `?ordering=organization__name` accepted without effect) (L54).
- Injection strings in `q`/`search` return empty results (parameterised queries).

## 5. Idempotency and transactions

- Natural idempotency: PM generation (DB uniques), SLA monitor (dedupe keys), create-work-order-from-request (one live WO per request), repeated close/transition (409 with unchanged state).
- Not idempotent: stock `receive/adjust/transfer` and labor entries (L25, L14). Every mutating service is `transaction.atomic` with its audit row.

## 6. OpenAPI accuracy

- `manage.py spectacular --validate --fail-on-warn` -> 0 warnings. Both `cookieAuth` and `jwtAuth` schemes present; only the two token endpoints are unauthenticated in the schema. The docs/schema endpoints require authentication (anonymous 401, verified under prod settings).
- Spot checks: `WorkOrderTransitionRequest` documents JSON, form and multipart bodies; the actual 400 for a missing `action` matches. No operation documents its 4xx responses (all 258 lack an explicit 4xx response entry; the error envelope is not in the schema) (LOW; add the envelope component and standard 401/403/404/409 responses).
- Documentation vs behaviour mismatches: alias routes absent (L55); no mention that `GET` on action routes returns 403.

## 7. Findings

F-M07 (site scope gap on `documents`/`readings` POST), F-M11 (Redis), F-M14 (JWT audit), F-M01 (500), L47, L48 (refresh tokens not revocable), L53-L55. Regression tests needed are listed per finding in `FINDINGS_REGISTER.md`.
