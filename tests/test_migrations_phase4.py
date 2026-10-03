"""Fresh-database migration check for Phase 4 (new uniquely named database in the test container, never an
existing one): M09 tables, constraints, the M06 link column and the synced permissions exist, no drift."""
import subprocess
import sys
import uuid

import psycopg
import pytest

from tests.test_migrations_phase1 import ROOT, _db_url, _env


@pytest.fixture(scope="module")
def fresh_db_url():
    name = f"fresh_p4_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(_db_url("postgres"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    return _db_url(name)


def test_phase4_schema_on_a_fresh_database(fresh_db_url):
    proc = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with psycopg.connect(fresh_db_url) as conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'")}
        for t in ("inventory_warehouse", "inventory_part", "inventory_stockbalance", "inventory_stockmovement",
                  "inventory_workorderpart", "inventory_partreservation"):
            assert t in tables, t
        columns = {r[0] for r in conn.execute(
            "select column_name from information_schema.columns where table_name='workorders_workordermaterial'")}
        assert "part_line_id" in columns
        names = {r[0] for r in conn.execute("select conname from pg_constraint")} | {
            r[0] for r in conn.execute("select indexname from pg_indexes")}
        for n in ("uniq_warehouse_code_per_org", "uniq_part_number_per_org", "uniq_balance_per_warehouse_part",
                  "balance_on_hand_nonneg", "balance_reserved_nonneg", "balance_reserved_lte_on_hand",
                  "movement_changes_balance", "uniq_part_line_per_work_order",
                  "part_line_consumed_returned_lte_issued", "reservation_active_has_qty"):
            assert n in names, n
        codes = {r[0] for r in conn.execute("select code from rbac_permission")}
        assert {"inventory.view", "inventory.part.manage", "inventory.receive", "inventory.issue",
                "inventory.consume", "inventory.reserve", "inventory.return"} <= codes
    drift = subprocess.run([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], cwd=ROOT,
                           env=_env(fresh_db_url), capture_output=True, text=True, timeout=120)
    assert drift.returncode == 0, drift.stdout[-1500:]
