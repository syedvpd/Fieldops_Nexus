"""Fresh-database migration check for Phase 2 (new uniquely named database in the test container, never an
existing one): tables, constraints and the synced Phase 2 permissions exist, and there is no model/migration drift."""
import subprocess
import sys
import uuid

import psycopg
import pytest

from tests.test_migrations_phase1 import ROOT, _db_url, _env


@pytest.fixture(scope="module")
def fresh_db_url():
    name = f"fresh_p2_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(_db_url("postgres"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    return _db_url(name)


def test_phase2_schema_on_a_fresh_database(fresh_db_url):
    proc = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with psycopg.connect(fresh_db_url) as conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'")}
        for t in ("core_documentsequence", "incidents_servicerequest", "incidents_downtime",
                  "incidents_servicerequesthistory", "workorders_workorder", "workorders_workorderevent",
                  "workorders_workorderlabor", "workorders_workordermaterial"):
            assert t in tables, t
        names = {r[0] for r in conn.execute("select conname from pg_constraint")} | {
            r[0] for r in conn.execute("select indexname from pg_indexes")}
        for n in ("uniq_request_number_per_org", "uniq_work_order_number_per_org", "uniq_live_work_order_per_request",
                  "downtime_end_after_start", "work_order_plan_window_ordered", "work_order_labor_hours_range",
                  "work_order_material_qty_pos", "uniq_sequence_per_org_key"):
            assert n in names, n
        codes = {r[0] for r in conn.execute("select code from rbac_permission")}
        assert {"incident.triage", "incident.approve", "work_order.assign", "work_order.close",
                "work_order.view_assigned"} <= codes
    drift = subprocess.run([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], cwd=ROOT,
                           env=_env(fresh_db_url), capture_output=True, text=True, timeout=120)
    assert drift.returncode == 0, drift.stdout[-1500:]
