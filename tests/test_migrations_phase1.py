"""Fresh-database migration check: applies every migration to a brand-new, uniquely named database inside the
test container (never touches or drops an existing database), verifies the Phase 1 schema, and checks drift."""
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _db_url(name: str) -> str:
    base = os.environ["DATABASE_URL"]
    parts = urlsplit(base)
    return urlunsplit(parts._replace(path=f"/{name}"))


def _env(url: str) -> dict:
    env = {**os.environ, "DATABASE_URL": url, "DJANGO_SETTINGS_MODULE": "config.settings.test",
           "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    return env


@pytest.fixture(scope="module")
def fresh_db_url():
    name = f"fresh_p1_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(_db_url("postgres"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    return _db_url(name)


def test_all_migrations_apply_to_a_fresh_database(fresh_db_url):
    proc = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with psycopg.connect(fresh_db_url) as conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'")}
        for t in ("sites_site", "sites_zone", "sites_operatingcalendar", "sites_calendarholiday", "sites_sitecontact",
                  "assets_asset", "assets_assetcategory", "assets_assetcomponent", "assets_assetdocument",
                  "assets_assetmeter", "assets_assetmeterreading", "assets_assetstatushistory",
                  "assets_assetlocationhistory"):
            assert t in tables, t
        cols = {r[0] for r in conn.execute(
            "select column_name from information_schema.columns where table_name='rbac_membershiprole'")}
        assert "site_id" in cols
        # permission catalog and system roles are synced by post_migrate on a fresh database
        codes = {r[0] for r in conn.execute("select code from rbac_permission")}
        assert {"site.view", "asset.change_status", "asset.hierarchy.manage"} <= codes
        applied = {r[0] for r in conn.execute("select app from django_migrations")}
        assert {"sites", "assets", "rbac"} <= applied
        constraints = {r[0] for r in conn.execute("select conname from pg_constraint")} | {
            r[0] for r in conn.execute("select indexname from pg_indexes")}  # expression uniques are indexes
        for c in ("uniq_site_code_per_org", "uniq_asset_tag_per_org", "component_not_self",
                  "uniq_membership_role_orgwide", "uniq_membership_role_site", "meter_reading_gte_0"):
            assert c in constraints, c


def test_second_migrate_is_a_noop_and_there_is_no_drift(fresh_db_url):
    again = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                           capture_output=True, text=True, timeout=300)
    assert again.returncode == 0 and "No migrations to apply" in again.stdout
    drift = subprocess.run([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], cwd=ROOT,
                           env=_env(fresh_db_url), capture_output=True, text=True, timeout=300)
    assert drift.returncode == 0, drift.stdout + drift.stderr


def test_seed_command_builds_valid_demo_data(org_a, owner_a):
    from django.core.management import call_command

    from apps.assets.models import Asset, AssetComponent
    from apps.sites.models import Site

    call_command("seed_phase1_demo", org=org_a.slug)
    call_command("seed_phase1_demo", org=org_a.slug)  # idempotent
    assert Site.objects.unscoped().filter(organization=org_a).count() == 2
    assert Asset.objects.unscoped().filter(organization=org_a, asset_tag="GEN-001").count() == 1
    assert AssetComponent.objects.unscoped().filter(organization=org_a).count() == 5
