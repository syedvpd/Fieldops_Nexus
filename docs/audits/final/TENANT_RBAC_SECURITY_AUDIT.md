# Tenant isolation, RBAC and security audit

Scope: Phases 5, 6 and 16 of the audit brief. Principals used (all real sessions): Super Admin (`superadmin@platform`), Alpha Owner, Alpha Admin, Operations Manager, Maintenance Supervisor, Asset Manager, Maintenance Planner, Technician One/Two, Stores Manager, Service Manager, Auditor, Client/Requester, Beta Owner, Beta Technician, anonymous. Role mapping (the brief's names -> implementation): Super Admin = `is_platform_admin`; Organization Owner = role `Organization Owner`; Planner = `Maintenance Planner`; Technician = `Technician`; Stores = `Stores Manager`; Service Manager = `Service Manager`; Auditor = `Auditor / Report Consumer`; Client = `Client / Requester`; extra roles: Admin, Operations Manager, Supervisor, Asset Manager.

**Verdicts: Tenant isolation PASS. RBAC PASS with two MEDIUM exceptions (F-M07 API site-scope gap, F-M17 Admin self-escalation). Security CONDITIONAL (F-H02 and the MEDIUM items below).**

## 1. Tenant isolation (ALPHA <-> BETA, both directions)

| Attack | Method | Result |
|---|---|---|
| Object-ID / UUID substitution on 52 detail endpoints | Beta session requests Alpha IDs and Alpha session requests Beta IDs (`api_idor.py`) | 51 x 404, 1 x 403 (`calendar-holidays`, identical to a random UUID); **0 data leaks** |
| Workflow/action endpoints on foreign objects | `POST` to 104 action endpoints with a foreign ID | 76 x 404, 17 x 403 (method not mapped), 7 x 400 (validation before lookup, **identical for a random UUID: no existence oracle**), 4 x 415 (multipart upload routes; re-tested with real multipart POSTs to API and HTML upload endpoints of asset, WO, request and inspection: all 404, no file stored) |
| Counts per list endpoint | 70 list endpoints x Alpha owner vs Beta owner | disjoint data (e.g. assets 19 vs 1, sites 6 vs 1, audit 463 vs 24); no Alpha rows in Beta lists |
| HTML object pages | Beta owner opens Alpha site/asset/WO/incident/checklist/audit URLs; Alpha opens Beta URLs | 404 on every object page (`html_matrix.json`: 25 x 404 for Beta on Alpha detail pages) |
| UI POSTs to foreign objects | status transition, meter reading, hierarchy add (foreign child, foreign parent) | 404 / validation error; DB unchanged (checked in SQL) |
| Cross-tenant child in hierarchy, cross-tenant FK in forms | crafted POST with foreign asset/site/zone IDs | rejected (400/404) |
| Attachment download IDOR | 4 files x 8 principals + anonymous | Beta: 404 on all; client: 404 on internal WO evidence and asset documents, 200 only on its own request attachment; anonymous 302 to login; other technician 404 on files of a WO not assigned to them |
| QR resolution | Beta scans an Alpha QR (UI + API); anonymous; client | "Label not recognised" / 404 identical to an unknown token; anonymous redirected to login; client denied |
| Dashboards / audit / exports | Beta dashboards, audit list, audit detail, export, evidence ZIP | Beta sees only Beta data; foreign site ID as filter shows nothing; evidence ZIP for a foreign WO 404 |
| X-Organization header | JWT + header naming a non-member org | 403 `not_a_member` |
| Super Admin | all `/app/` URLs and tenant APIs | redirected to `/platform/`; tenant APIs 403 (Org Owner never implies platform admin) |
| Background jobs | per-org Celery fan-out | each task wraps `tenant_context(org)`; suspended orgs skipped (static); renewal alert/ SLA monitor/ PM fan-out observed with two orgs |

Result: **no cross-tenant read or write was achieved in any direction.** Residual (defence in depth, not exploitable today): F-M20 (no DB-level tenant FK guard), L46 (a tenant admin can attach any existing global user to its org without consent; D-006).

## 2. RBAC matrices

### 2.1 REST list endpoints, status/row-count per principal (representative endpoint per group; full data `evidence/api_sweep.json`)

| Group (representative list endpoint) | owner | admin | ops | supervisor | assets | planner | tech | stores | service | auditor | client | betaowner | platform | anon |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sites/zones/calendars (`sites/`) | 200/6 | 200/6 | 200/6 | 200/6 | 200/6 | 200/6 | 200/6 | 200/6 | 200/6 | 200/6 | 403 | 200/1 | 403 | 401 |
| assets (`assets/`) | 200/19 | 200/19 | 200/19 | 200/19 | 200/19 | 200/19 | 200/19 | 200/19 | 200/19 | 200/19 | 403 | 200/1 | 403 | 401 |
| incidents (`service-requests/`) | 200/3 | 200/3 | 200/3 | 200/3 | 403 | 200/3 | 200/3 | 403 | 200/3 | 200/3 | 403 | 200/0 | 403 | 401 |
| work orders (`work-orders/`) | 200/14 | 200/14 | 200/14 | 200/14 | 200/14 | 200/14 | 200/1 | 200/14 | 200/14 | 200/14 | 403 | 200/0 | 403 | 401 |
| maintenance (`maintenance-plans/`) | 200/4 | 200/4 | 200/4 | 200/4 | 403 | 200/4 | 403 | 403 | 403 | 200/4 | 403 | 200/0 | 403 | 401 |
| checklists/inspections (`checklist-templates/`) | 200/2 | 200/2 | 200/2 | 200/2 | 403 | 200/2 | 403 | 403 | 403 | 200/2 | 403 | 200/0 | 403 | 401 |
| inventory (`parts/`) | 200/3 | 200/3 | 200/3 | 200/3 | 403 | 200/3 | 200/3 | 200/3 | 403 | 200/3 | 403 | 200/1 | 403 | 401 |
| contracts (`coverage-agreements/`) | 200/4 | 200/4 | 200/4 | 403 | 200/4 | 200/4 | 403 | 403 | 200/4 | 200/4 | 403 | 200/0 | 403 | 401 |
| SLA (`sla-profiles/`) | 200/2 | 200/2 | 200/2 | 200/2 | 403 | 200/2 | 403 | 403 | 200/2 | 200/2 | 403 | 200/0 | 403 | 401 |
| QR (`asset-identifiers/`) | 200/3 | 200/3 | 200/3 | 403 | 200/3 | 403 | 403 | 403 | 403 | 200/3 | 403 | 200/0 | 403 | 401 |
| portal (`portal/requests/`) | 200/0 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 200/1 | 200/0 | 403 | 401 |
| dashboards (`dashboards/`) | 200 | 200 | 200 | 200 | 200 | 403 | 403 | 403 | 200 | 200 | 403 | 200 | 403 | 401 |
| audit (`audit-logs/`) | 200/463 | 200/463 | 200/463 | 403 | 403 | 403 | 403 | 403 | 403 | 200/463 | 403 | 200/24 | 403 | 401 |
| admin (`members/`) | 200/12 | 200/12 | 200/12 | 403 | 403 | 403 | 403 | 403 | 403 | 200/12 | 403 | 200/2 | 403 | 401 |
| platform (`platform/organizations/`) | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 200/2 | 401 |

Reading: `200/n` = allowed, n rows; `403` = denied; `401` = unauthenticated. No anonymous 200; no 5xx among 980 requests. Technician sees 1 of 14 work orders (own assignment only). Client reaches only the portal endpoints. Auditor/Owner/Admin read audit; only Owner and Auditor may export (`audit-logs/export/` 200 for them, 403 for Admin, per template). Platform admin gets 403 on every tenant endpoint.

Observations (LOW, finding L53): `findings/`, `inspections/`, `work-order-parts/` return 200 with an empty list to principals that lack the permission (other endpoints return 403); GET on POST-only action routes returns 403, not 405.

### 2.2 Write permissions: 11 roles x 18 state-changing API calls (`rbac_matrix.py`, valid bodies; 2xx = allowed, 400/409 = passed the permission gate but failed validation/state, 403/404 = denied)

| Role | site.create | asset.create | incident.create | wo.create | wo.cancel | incident.triage | part.create | stock.receive | role.manage | user.invite | maint.create | sla.manage | contract.create | org.update | audit.patch | audit.delete | checklist.create | warehouse.create |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| owner | 201 | 201 | 201 | 201 | 200 | 200 | 201 | 201 | 201 | 400 | 201 | 409 | 400 | 200 | 403 | 403 | 201 | 201 |
| admin | 201 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 201 | 400 | 403 | 403 | 403 | 200 | 403 | 403 | 403 | 403 |
| ops | 403 | 403 | 201 | 201 | 200 | 409 | 403 | 403 | 403 | 403 | 201 | 403 | 403 | 403 | 403 | 403 | 201 | 403 |
| supervisor | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 201 | 403 |
| assets | 201 | 201 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 400 | 403 | 403 | 403 | 403 | 403 |
| planner | 403 | 403 | 403 | 201 | 200 | 403 | 403 | 403 | 403 | 403 | 201 | 403 | 403 | 403 | 403 | 403 | 201 | 403 |
| tech | 403 | 403 | 201 | 403 | 404 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| stores | 403 | 403 | 403 | 403 | 403 | 403 | 201 | 201 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 201 |
| service | 403 | 403 | 201 | 403 | 403 | 409 | 403 | 403 | 403 | 403 | 403 | 409 | 400 | 403 | 403 | 403 | 403 | 403 |
| auditor | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |
| client | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 | 403 |

Reading: results match the role templates in `rbac/role_templates.py` exactly: Auditor and Client are denied every write; Technician can only create incidents; Stores can only create parts/warehouses/receive stock; Planner creates/cancels WOs and maintenance plans/checklists; Supervisor only checklists; Service Manager only incidents (409 on triage = permission passed, state not NEW); Operations Manager incidents/WOs/PM/checklists; Asset Manager sites/assets (and contracts, 400 = validation). **`PATCH`/`DELETE` of an audit row is 403 for every role including Owner.**

### 2.3 HTML pages, 78 URLs x 12 roles (`html_matrix.json`)

| Role | 200 | 403 | 404 | 5xx |
|---|---|---|---|---|
| admin | 59 | 19 | 0 | 0 |
| ops | 60 | 18 | 0 | 0 |
| supervisor | 45 | 33 | 0 | 0 |
| assets | 30 | 48 | 0 | 0 |
| planner | 50 | 28 | 0 | 0 |
| tech2 | 23 | 52 | 3 | 0 |
| stores | 33 | 45 | 0 | 0 |
| service | 39 | 39 | 0 | 0 |
| auditor | 56 | 22 | 0 | 0 |
| client | 8 | 70 | 0 | 0 |
| betaowner | 53 | 0 | 25 | 0 |
| platform | 78 | 0 | 0 | 0 |

Client: 8 reachable pages (portal, notifications, search). Technician: 23 pages (assets read, workspace, own dashboard). No 5xx for any role. Platform admin: all 78 redirect to the platform console.

### 2.4 Direct backend denial (not only hidden buttons)

Crafted POSTs with valid CSRF were sent for: technician start/complete on another technician's WO (404), technician issue stock (403), technician review/close (denied, WO unchanged), planner start review (403), client access to every internal page and API (403/404), Beta writes to Alpha objects (404), asset transition without reason (rejected), unknown action (rejected), system-only request action (rejected). DB state was re-read after each attempt.

### 2.5 Authorization defects found

- **F-M17 (RUNTIME):** Org Admin created a role containing all 94 permissions, assigned it to itself and could then call `audit-logs/export/` (200); Admin also edited the Owner's member record (200). Needs a Team Lead decision (accept "Admin is trusted" and record it, or enforce "grant only what you hold; only an Owner may modify an Owner").
- **F-M07 (RUNTIME for meter readings):** REST asset documents and meter readings skip the site-scoped permission check (a user whose `asset.meter.record` is scoped to BLR-1 stored a reading on a HYD-1 asset via the API: 201; the HTML view returned 403). Site scoping elsewhere held: a planner limited to BLR-1 saw only BLR-1 sites/assets/WOs, got 404 on out-of-scope URLs and could not create a WO for an out-of-scope asset.
- **F-M09 (RUNTIME):** a disabled portal client still reads its history (UI and API).
- **L46:** global user name editable by any org admin; existing users auto-activated into an inviting org.

## 3. Security probes (adversarial, non-destructive)

| Probe | Result |
|---|---|
| Stored XSS / template injection (`"><img onerror>`, `<script>`, `{{7*7}}`) in site name, incident title/description/impact, WO title/description, part name, SLA/contract/checklist names; rendered on 15 pages incl. audit, search, dashboards, workspace | inert everywhere; no dialog, `window.__xss` never set, `{{7*7}}` not evaluated |
| CSP | nonce-based `script-src 'self'`; `object-src 'none'`, `frame-ancestors 'none'`; crawl of 78 pages as Owner: **0** CSP violations, JS errors or failed requests; one functional CSP break found (F-M16) |
| Security headers (dev and under prod settings) | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy same-origin, Permissions-Policy, COOP same-origin, HSTS 1 y + preload (prod), Secure CSRF cookie (prod) |
| CSRF | HTML POST and session-authenticated API POST without token -> 403, DB unchanged |
| Open redirect | login `next` = `https://evil`, `//evil`, `/\evil`, `javascript:` -> all land on `/app/` |
| Brute force | 5 failures lock username+IP for 15 min (lockout page), correct password then refused; QR: 15 failed scans -> 429, even a valid token is refused while throttled |
| Account enumeration | identical error for existing and non-existing accounts |
| Session | logout invalidates the server-side session (copied cookie -> 401) |
| File upload | executable (`.exe`) rejected, fake PDF (magic-byte mismatch) rejected, >10 MB rejected with a message; stored names are UUID paths; downloads forced `application/octet-stream`, `attachment`, `nosniff` |
| Mass assignment | `organization`, `id`, `created_by`, `is_active` ignored; explicit `status` rejected with 400 |
| JWT | bad password 401; Bearer works; foreign `X-Organization` 403 |
| API robustness | `page_size` capped at 200; bad page 404; filters with injection strings return 0 rows (parameterised); no SQL string building (`.raw/.extra` absent; the only raw SQL is parameterised) |
| Host header / debug | bad Host -> 400; DEBUG off; project 404/500 pages; `/admin/` not mounted; schema/docs require auth |
| Secrets | none tracked (`.env.example` placeholders only); `.env*` ignored |
| Redirect/path traversal/zip-slip | `next` params whitelisted; upload names sanitised; evidence ZIP entry names sanitised (static) |
| Audit tampering | API 403, ORM guards, row trigger; **TRUNCATE/owner path open (F-H02)** |

## 4. Security findings summary

HIGH: F-H02. MEDIUM: F-M07, F-M09, F-M11 (availability), F-M14, F-M15, F-M16, F-M17, F-M18, F-M20. LOW: L31, L36, L46-L52. UNVERIFIED: U01, U06, U09. Details and fixes: `FINDINGS_REGISTER.md`.

## 5. Verified sound (evidence-based)

- Fail-closed `TenantManager`; every view/viewset is mixin-protected (AST scan of all `views.py`/`api_views.py`); all 21 `.unscoped()` uses are in tenancy/rbac/platform/accounts/notifications and are filtered by user/org.
- Explicit serializer field lists (no `__all__`); `organization` is not editable.
- Membership resolution only among the caller's own ACTIVE memberships; suspended orgs blocked.
- Password policy (12+ chars, validators), activation/reset tokens single-use with 3-day expiry, throttled login (UI and JWT).
- CSV/XLSX formula injection neutralised; exports capped (10 000 rows) and audited.
- QR tokens: 128-bit opaque (QR) / 60-bit alphabet without lookalikes (barcode), not derived from asset tag/UUID, raw tokens never audited (fingerprints only).
