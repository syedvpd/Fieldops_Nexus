# Project map (read this instead of searching)

Root: `fieldops-nexus/`. Python path root is `src/`. Settings: `config.settings.{dev,test,prod}`.

## Entry points
- `manage.py`, `src/config/{settings/base.py,urls.py,celery.py,wsgi.py,asgi.py}`; URL routing for all apps is in `src/config/urls.py` (API router at `/api/v1/`, UI under `/app/`, platform under `/platform/`).
- Infra: `Dockerfile`, `docker-compose.yml` (db, redis, migrate, web, worker, beat, nginx), `deploy/nginx/`, `.github/workflows/ci.yml`, `scripts/bootstrap_env.py`, `requirements.lock`, `.env.example`.

## Apps (`src/apps/`)
| app | purpose | key files |
|---|---|---|
| core | shared kernel | `sequences.py` + `DocumentSequence` (INC-/WO- numbers), `tenant.py` (contextvar + TenantManager), `models.py` (BaseModel, TenantOwnedModel), `workflow.py` (StateMachine), `exceptions.py`, `api.py` (envelope, pagination), `uploads.py`, `health.py`, `logging.py`, `middleware.py`, `net.py` (client IP behind proxy + Axes username; see D-023), `apiutils.py` (pagination/ID param/require_permission helpers) |
| accounts | User, auth | `models.py` (email login, `is_platform_admin`), `views.py`, `services.py` (activation links), `tasks.py` (invite email), `signals.py` (login audit), `api.py`, mgmt cmds `create_platform_admin` (hidden prompt) and `diagnose_login` |
| tenancy | Organization, Membership | `models.py`, `services.py` (create/suspend org, invite/update/deactivate member), `selectors.py` (resolve membership), `middleware.py`, `api.py` (TenantAPIMixin, HasOrgPermission), `views.py`, `api_views.py` |
| rbac | Permission/Role/MembershipRole | `catalog.py` (register), `permissions.py`, `role_templates.py`, `services.py` (has_permission(site), SiteScope/site_scope, role CRUD, owner rules, set_membership_assignments), `views.py`, `api_views.py` |
| audit | append-only AuditLog | `models.py`, `services.py` (`record`), `selectors.py`, views, api, migration 0002 = DB trigger |
| notifications | in-app + email | `services.py` (`notify`), `tasks.py`, views (bell), api |
| files | Attachment + secure download | `services.py` (`attach`), `views.py`, `access.py` (per-target download authorisation registry) |
| platform_admin | Super Admin console | `views.py`, `api_views.py` (org list/create/suspend, platform audit) |
| sites | M01 | `models.py` (Site, Zone, OperatingCalendar, CalendarHoliday, SiteContact), `workflow.py` (activation), `services.py`, `selectors.py` (scope-restricted reads, zone tree), `api_views.py`, `views.py`, `forms.py`, `permissions.py`, `navigation.py`, `urls.py` |
| assets | M02 + M03 | `models.py`, `workflow.py` (asset status machine), `services.py` (registry, status, moves, documents, meters), `hierarchy.py` (M03 rules, tree), `selectors.py`, `api_views.py`, `views.py`, `forms.py`, `permissions.py`, `navigation.py`, `management/commands/seed_phase1_demo.py` |
| incidents | M05 | `models.py` (ServiceRequest, Downtime, ServiceRequestHistory), `workflow.py`, `services.py` (+ `on_work_order_*` hooks, `create_work_order_for_request`), `selectors.py`, `api_views.py`, `views.py`, `forms.py`, `permissions.py`, `navigation.py`, `urls.py` |
| workorders | M06 | `models.py` (WorkOrder, WorkOrderEvent, WorkOrderLabor, WorkOrderMaterial), `workflow.py`, `services.py` (transition, reassign, labor/material/evidence, `closure_blockers`), `selectors.py`, `api_views.py`, `views.py`, `forms.py`, `permissions.py`, `navigation.py`, `urls.py` |
| checklists | M08 | `models.py` (ChecklistTemplate, ChecklistItem, Inspection, InspectionResponse, Finding), `workflow.py`, `services.py` (templates, versions, inspections, responses, findings, completion, `checklist_blockers`), `selectors.py`, `api_views.py`, `views.py`, `forms.py`, `permissions.py`, `navigation.py`, `urls.py` |
| workspace | M07 | `models.py` (WorkNote), `services.py` (notes; everything else calls M06/M08), `selectors.py` (my jobs), `views.py` (jobs, job, checklist execution), `forms.py`, `navigation.py`, `urls.py` |
| ui | shell | `navigation.py` (+`navigation_items.py`), `context_processors.py`, `mixins.py` (TenantPermissionMixin), `views.py` (home, org switch, search), `forms.py` (BootstrapFormMixin), `templatetags/ui_tags.py` |

## Templates/static
`src/templates/{base,public,shell}.html`, `components/_*.html` (page_header, pagination, form_field, empty_state, timeline, workflow_bar, file_upload, messages), per-app dirs. CSS `src/static/css/app.css`, JS `src/static/js/app.js`, Bootstrap 5.3.3 + HTMX 2.0.4 in `src/static/lib/` (refetch: `scripts/fetch_static_libs.py`).

## Scripts (`scripts/`)
`bootstrap_env.py` (.env for local compose), `bootstrap_prod_env.py` (.env.prod for Supabase), `provision_supabase.py` (role+schema), `fetch_static_libs.py`, `smoke_stack.py` (HTTP smoke test).

## Docs
Permanent knowledge: `docs/PROJECT_SOURCE_OF_TRUTH.md`, `docs/FIELDOPS_NEXUS_MASTER_BUSINESS_WORKFLOW.md`, `docs/modules/M01..M15_*.md` (one file per module). `docs/integrations/sites-assets-contracts.md` (Phase 1 plan + contracts for later modules). `docs/` ARCHITECTURE, DOMAIN_MODEL, DECISIONS, TRACEABILITY (gates, Day-30 table, journeys), MODULE_STATUS, DEVELOPMENT_RULES, DEPLOYMENT, CHECKPOINT_PHASE_0, `manual-tests/` (one guide per phase), `blueprint/` (source). Skills: `.claude/skills/*` (on-demand, short, link to docs).

## Tests (`tests/`)
`conftest.py` (fixtures: platform_admin, org_a/org_b, owner_a/b, tech_a/b, make_org, make_member, as_user), `test_login_integration.py` (browser-faithful login/Axes/proxy regression suite), `test_tenant_isolation.py`, `test_rbac.py`, `test_audit.py`, `test_onboarding_auth.py`, `test_ui.py`, `test_ui_actions.py`, `test_core.py`, Phase 1: `test_sites.py`, `test_assets.py`, `test_hierarchy.py`, `test_site_scope.py`, `test_ui_phase1.py`, `test_migrations_phase1.py`; Phase 2: `test_phase2_journey.py` (API journey), `test_phase2_rules.py` (negative/RBAC/tenant/scope), `test_ui_phase2.py` (HTML journey).

## How to add a module (checklist)
1. `src/apps/<name>/` (+ add to `INSTALLED_APPS`), models extend `TenantOwnedModel`; `makemigrations <name>`.
2. `permissions.py` (register codes), `navigation.py`, `services.py`, `selectors.py`, `api_views.py`, `views.py`, `urls.py` (include in `config/urls.py`, router in same file).
3. Declare the StateMachine; audit every transition.
4. Tests: happy, invalid, wrong role, unauthenticated, wrong org, wrong site/object, invalid state, IDOR.
5. Update `MODULE_STATUS.md`, `TRACEABILITY.md`, this map.

## Environments
- Python venv lives OUTSIDE the repo: `C:\Users\HP\.venvs\fieldops-nexus\Scripts\python.exe` (recreate from `requirements.lock` + pytest pytest-django pytest-cov ruff). Set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=src`.
- Tests: Docker Postgres container `fieldops-test-pg` on `localhost:55432` (user `fieldops`, test-only password in `docs/DEPLOYMENT.md` pattern), `DJANGO_SETTINGS_MODULE=config.settings.test`.
- Compose stack: project `fieldops` -> http://localhost:8080 (see DEPLOYMENT.md).
- Prod: Supabase `fieldops-nexus-prod-sg` (schema `fieldops`, role `fieldops_app`), Render Key Value `red-db086bhsrm7s73eg3340`; secrets only in git-ignored `.env.prod`.
- Shell tip: the bash/PowerShell cwd can reset between calls; `Set-Location` to the project root in every command; use absolute paths with file tools.

- Supabase (D-031): project `fieldops-nexus-prod-sg`, schema `fieldops` (not `public`). Run Django against it with `.claude/run_prod.ps1` (git-excluded; loads `.env.prod`, local Redis on :6390). QA user passwords in git-ignored `.env.qa-users`. `staticfiles/` is git-ignored (`collectstatic` output).
- Phase 2: `docs/integrations/incidents-workorders.md` (contracts), `docs/manual-tests/PHASE_2_MANUAL_TEST.md`. Templates: `src/templates/incidents/`, `src/templates/workorders/`. Worktree note: session worktrees do not contain the git-excluded helpers (`.claude/run_prod.ps1`) or secrets; those live only in the main checkout. Phase 3 prompt: `docs/prompts/PHASE_3_EXECUTION_PROMPT.md`.
- Phase 3: `docs/integrations/checklists-workorders.md` (contract), `docs/manual-tests/PHASE_3_MANUAL_TEST.md`, `docs/PHASE_3_ACCEPTANCE_REPORT.md`. Templates `src/templates/checklists/`, `src/templates/workspace/`. Tests: `tests/test_m08_checklists.py` (services, API, closure matrix, tenant/site), `tests/test_m07_workspace.py` (HTML UI + full journey), `tests/test_migrations_phase3.py`, shared builders `tests/phase3_support.py` (+ `p3` fixture in `conftest.py`).
- Phases 4-6 prompt: `docs/prompts/PHASE_4_5_6_EXECUTION_PROMPT.md` (M09 Inventory, M04 PM, M11 SLA).
