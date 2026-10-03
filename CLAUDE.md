# FieldOps Nexus: permanent engineering rules

Multi-tenant SaaS ERP (Enterprise Asset, Maintenance & Field Service), HPE-PRD-2026-FOPS02. ONE integrated app, not 15.
Start every session by reading `docs/PROJECT_MAP.md` (where everything is) and `docs/MODULE_STATUS.md` (what is done).

## Permanent knowledge (read first, every session; the repository is the project's memory)
`docs/PROJECT_SOURCE_OF_TRUTH.md` (priority rules, golden/critical rules, definition of done, verification rules, open conflicts), `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md` (business workflow, modules, state machines, boundaries, dependencies), and `docs/modules/Mxx_*.md` for the module you touch. Then `docs/DECISIONS.md`, `docs/MODULE_STATUS.md`, `docs/TRACEABILITY.md`, `docs/DOMAIN_MODEL.md`, `docs/DEVELOPMENT_RULES.md`.

## Source of truth (priority, D-032)
1. Explicit HPE PRD requirement -> 2. master business/workflow docs (`docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md`, `docs/modules/`) -> 3. recorded Team Lead decision -> 4. documented decision/assumption (`docs/DECISIONS.md`) -> 5. existing implementation if it contradicts none of 1-4 -> 6. general engineering assumptions. `docs/blueprint/` is working material below level 2.
Label anything HPE is silent on: HPE CONFIRMED / OUR IMPLEMENTATION DECISION / CLARIFICATION REQUIRED / EXAMPLE; never present an implementation decision as an HPE requirement. If documents conflict: stop, identify the conflict, prefer the higher source, record it in DECISIONS.md; conflicts needing the Team Lead are listed in PROJECT_SOURCE_OF_TRUTH section 8 (do not resolve them silently). Ambiguity that affects architecture, security, data model, workflow, tenant isolation or irreversible behaviour: STOP AND ASK. Module numbers M01-M15 are HPE's and are never renumbered; Django apps use meaningful names. A module is done only with browser + PostgreSQL + audit + integration + negative tests evidence (never "tests pass" alone). Do not start the next phase with unresolved Critical/High defects.

## Working rules (token efficiency)
1. Read only files relevant to the task; use `docs/PROJECT_MAP.md` instead of searching. Read only the relevant `docs/blueprint/*` files.
2. Targeted tests while developing; full regression only at phase end. `pytest tests/test_x.py -q --tb=short`.
3. Reports are short: files changed, tests + result, migrations, decisions, blockers.
4. Persist discoveries in docs (`docs/integrations/<a>-<b>.md`), not conversation.
5. Bounded tasks: backend (models+services+API+tests) then UI. Make routine decisions yourself; log significant ones in `docs/DECISIONS.md`. Ask only for conflicting requirements, security/destructive ambiguity or missing production secrets.
6. After creating files, update `docs/PROJECT_MAP.md` (one line per file/dir).
7. Every phase ends with `docs/manual-tests/PHASE_N_MANUAL_TEST.md` (exact test data/credentials, URLs, clicks, expected results, negative/security checks, result sheet) plus a short phase summary to the Team Lead.
8. Environment: venv outside repo (`C:\Users\HP\.venvs\fieldops-nexus`), local/test DB = Docker Postgres, prod = Supabase schema `fieldops` via `.env.prod` (git-ignored; never print secrets). Do not name directories `vendor` (some tools skip them).

## Non-negotiable safety
NEVER: DROP DATABASE/SCHEMA, TRUNCATE app tables, flush/reset a DB, delete/rewrite applied migrations, force-push, rewrite Git history, commit secrets, bypass tenant isolation or backend RBAC, fake APIs/success messages/metrics, build dead buttons or frontend-only workflows.
Tests use the dedicated local Docker Postgres (`test_*` DB created by pytest). Never point tests at Supabase/production. Never touch the unknown Postgres on :5432.

## Architecture invariants
- Layers: view/API (thin) -> `services.py` (rules, `transaction.atomic`, audit) -> models. Selectors for reads.
- Tenant data models extend `core.models.TenantOwnedModel` (org FK + fail-closed `TenantManager`). `.unscoped()` only in the allow-list in `tests/test_tenant_isolation.py`.
- Authorization = identity + ACTIVE membership + permission + tenant object + site scope (from M01) + valid state. `X-Organization`/session only SELECTS among the user's own memberships.
- API views: `TenantAPIMixin` + `permission_map` (unmapped action = denied). HTML views: `TenantPermissionMixin.required_permission`.
- Workflows: declare a `core.workflow.StateMachine`; change state only via `apply()` inside a service, then `audit.record(...)` in the same transaction.
- New permissions: `<app>/permissions.py` (`register(...)`), nav: `<app>/navigation.py`; both autodiscovered. Add role-template patterns in `rbac/role_templates.py` if needed.
- Org Owner is an org role; it never implies `is_platform_admin`.
- Every state-changing button posts to a real endpoint that checks permission, tenant, object, state, persists, audits, and has a test.

## Definition of done
Requirement mapped + models/migration + service + API + RBAC + tenant isolation + state machine + UI + audit + tests (unit/API/RBAC/tenant/integration) + regression + manual-test steps + docs updated. Never call a module complete if an integration is a stub.

## Commands (see README for setup)
`pytest -q` | `ruff check src tests` | `python manage.py makemigrations --check --dry-run` | `python manage.py migrate`
