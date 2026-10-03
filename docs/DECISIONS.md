# Decision log

Format: ID, decision, why, consequence. All are FieldOps implementation decisions unless marked HPE.

- **D-001 Django 5.2 LTS.** HPE requires 4.2+; 5.2 is the current LTS. Python 3.12 in Docker, 3.11+ supported.
- **D-002 Functional app names; M-numbers are traceability only** (`docs/TRACEABILITY.md`).
- **D-003 UUID primary keys** everywhere: no enumerable IDs in URLs/APIs (also helps M12 QR requirement).
- **D-004 Tenant model.** Every tenant record carries `organization` FK (PROTECT). Default manager `TenantManager` filters by the active org and is FAIL-CLOSED in the request cycle (starts as "no tenant" -> empty). Escape hatch `.unscoped()` is allow-listed by a test. Cross-tenant writes are rejected in `save()`. Postgres RLS is optional later hardening (not required now).
- **D-005 Roles are per-organization rows** seeded from additive templates (`rbac/role_templates.py`, fnmatch patterns over the registered permission catalog). Orgs may edit defaults and create custom roles. Owner role = implicit all permissions, locked, not editable. Seeded defaults are defaults, not restrictions.
- **D-006 Invitation of existing users.** An existing account invited to another org is activated immediately and notified (no acceptance step). Revisit if consent is required.
- **D-007 No plaintext passwords.** Owners/users activate via signed, expiring (3 days), single-use token links and choose their own password (>= 12 chars, Django validators). Platform admin created by CLI reading `FIELDOPS_ADMIN_PASSWORD`/prompt, never argv.
- **D-008 Platform admin has no tenant rights.** `is_platform_admin` is independent of org roles; Owner never inherits it; platform console runs in explicit PLATFORM tenant mode.
- **D-009 Active-org selection.** Session (UI) or `X-Organization` header (API) only SELECTS among the caller's own ACTIVE memberships; nothing is granted by the value (tested).
- **D-010 API auth:** JWT (simplejwt, 15 min access / rotating refresh) + session; login throttled; axes lockout (5 failures / 15 min).
- **D-011 Error envelope** `{"error":{code,message,details,request_id}}` for all API errors.
- **D-012 Audit immutability in 3 layers:** model/queryset guards + PostgreSQL trigger blocking UPDATE/DELETE. TRUNCATE is not trapped (would break test flush); organizations are never hard-deleted (PROTECT).
- **D-013 Workflow engine** `core.workflow.StateMachine`; services own transitions + audit in one transaction.
- **D-014 UI:** Django templates + HTMX + Bootstrap 5 (vendored, pinned; no runtime CDN). No React until a widget justifies it.
- **D-015 Static files** via WhiteNoise inside the app image (Nginx proxies); media on a volume; S3-compatible storage later if needed.
- **D-016 Environments.** Local/test: Docker Postgres (never Supabase). Production DB: Supabase Postgres project `fieldops-nexus-prod-sg` (ap-southeast-1) via Django `DATABASE_URL` (Django migrations, not Supabase migrations). Redis: Render Key Value (Singapore) when available.
- **D-017 Site-scoped permissions** deferred to Phase 1 because they need `sites.Site`.
- **D-019 Supabase isolation.** Production tables live in schema `fieldops` owned by least-privilege role `fieldops_app` (created by `scripts/provision_supabase.py`). `anon`/`authenticated`/`service_role` have no USAGE on it, so Supabase's REST Data API cannot reach tenant data; Django remains the only gateway. The Supabase "RLS disabled" advisory is therefore not exploitable for these tables; RLS may still be added as defence in depth. The admin (`postgres`) credential is used only for provisioning.
- **D-020 Third-party static files** live in `src/static/lib/` (renamed from `vendor/`, which some tools skip), fetched by `scripts/fetch_static_libs.py` with source-map comments stripped.
- **D-021 Local HTTP stack toggles:** `DJANGO_SECURE_COOKIES`/`DJANGO_SECURE_SSL_REDIRECT` default to secure; compose sets them false for http://localhost:8080 only. Nginx forwards `Host` with port (`$http_host`) so Django's CSRF origin check works.
- **D-022 Git/CI.** Local repo initialised with `main`; baseline commit = verified Phase 0 (needed so per-phase sessions can use git worktrees). GitHub remote pending (connector failed). Branch model per `DEVELOPMENT_RULES.md`: each phase on `feature/phase-N-*`, merged to `main` after Team Lead approval.
- **D-023 Login throttling model (incident 2026-10-03).** Axes locks on the *combination* username+IP (not either), using the credential key Django actually passes (`username`), normalised (strip/lower). Client IP comes from `apps/core/net.client_ip`, which trusts `X-Forwarded-For` only for `TRUSTED_PROXY_COUNT` hops from the right (0 = never). Same function feeds the audit log. Lockout shows a friendly 429 page. Nginx rate-limits only credential POSTs. Super Admin stays `is_platform_admin` without `is_staff`/`is_superuser`. Details: `docs/INCIDENT_2026-10-03_LOGIN.md`.
- **D-024 Operator-facing secrets handling.** Passwords are never passed on a command line or typed inside double-quoted PowerShell strings; use the hidden prompt (`create_platform_admin`, `changepassword`, `diagnose_login`) or single-quoted values.
- **D-018 Celery:** `acks_late`, JSON, time limit; beat runs `clearsessions` daily; module phases add PM/SLA/expiry tasks. Tasks touching tenant data must use `tenant_context(org)`.
