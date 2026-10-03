"""Fresh-database migration check for Phase 5 (new uniquely named database in the test container, never an
existing one): M04 tables, constraints, the M06 source columns and the synced permissions exist, no drift."""
import subprocess
import sys
import uuid

import psycopg
import pytest

from tests.test_migrations_phase1 import ROOT, _db_url, _env


@pytest.fixture(scope="module")
def fresh_db_url():
    name = f"fresh_p5_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(_db_url("postgres"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    return _db_url(name)


def test_phase5_schema_on_a_fresh_database(fresh_db_url):
    proc = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with psycopg.connect(fresh_db_url) as conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'")}
        for t in ("maintenance_maintenanceplan", "maintenance_maintenanceschedule", "maintenance_maintenancecycle"):
            assert t in tables, t
        columns = {r[0] for r in conn.execute(
            "select column_name from information_schema.columns where table_name='workorders_workorder'")}
        assert {"source_type", "source_id"} <= columns
        names = {r[0] for r in conn.execute("select conname from pg_constraint")} | {
            r[0] for r in conn.execute("select indexname from pg_indexes")}
        for n in ("uniq_plan_name_per_asset", "schedule_trigger_fields", "schedule_window_ranges",
                  "uniq_time_schedule_per_plan", "uniq_meter_schedule_per_plan", "uniq_cycle_per_schedule_sequence",
                  "work_order_source_pair", "uniq_work_order_per_pm_source"):
            assert n in names, n
        codes = {r[0] for r in conn.execute("select code from rbac_permission")}
        assert {"maintenance.view", "maintenance.create", "maintenance.update", "maintenance.generate"} <= codes
    drift = subprocess.run([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], cwd=ROOT,
                           env=_env(fresh_db_url), capture_output=True, text=True, timeout=120)
    assert drift.returncode == 0, drift.stdout[-1500:]
