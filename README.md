# FieldOps Nexus

Multi-tenant Enterprise Asset, Maintenance & Field Service ERP (HPE-PRD-2026-FOPS02) for VPD Technologies.
Django 5.2 · DRF · PostgreSQL · Redis · Celery · HTMX/Bootstrap.

**Status:** Phase 0 (foundation) verified. See `docs/MODULE_STATUS.md`. Architecture: `docs/ARCHITECTURE.md`. Where things are: `docs/PROJECT_MAP.md`.

## Quick start (local)
```bash
python -m venv .venv && .venv/Scripts/activate        # Windows; use source .venv/bin/activate elsewhere
pip install -r requirements.lock pytest pytest-django pytest-cov ruff
python scripts/bootstrap_env.py
docker compose up -d --build                          # full stack at http://localhost:8080
```
Create the first Super Admin (hidden prompt, asked twice; never put the password on the command line or in a double-quoted PowerShell string):
```bash
docker compose exec web python manage.py create_platform_admin --email you@example.com --full-name "Your Name"
docker compose exec web python manage.py diagnose_login --email you@example.com    # if sign-in is ever rejected
```
Sign in at `/accounts/login/` -> Platform console -> New organization -> the owner receives an activation email (console/worker log in dev).

## Tests
```bash
docker run -d --name fieldops-test-pg -e POSTGRES_USER=fieldops -e POSTGRES_PASSWORD=test_only -e POSTGRES_DB=fieldops -p 55432:5432 postgres:16-alpine
export DJANGO_SETTINGS_MODULE=config.settings.test DATABASE_URL=postgres://fieldops:test_only@localhost:55432/fieldops
pytest -q          # ruff check src tests ; python manage.py makemigrations --check --dry-run
```
API docs: `/api/v1/docs/` (Swagger), schema `/api/v1/schema/`. Health: `/health/live/`, `/health/ready/`.

## Docs
`docs/` : ARCHITECTURE, DECISIONS, DOMAIN_MODEL, TRACEABILITY (Day 30/60/90 + 7 journeys), MODULE_STATUS, DEVELOPMENT_RULES, DEPLOYMENT, PROJECT_MAP, and `docs/blueprint/` (source blueprint).
