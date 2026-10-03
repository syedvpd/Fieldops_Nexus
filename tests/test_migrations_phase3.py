"""Fresh-database migration check for Phase 3 (new uniquely named database in the test container, never an
existing one): M08 / M07 tables, constraints and the synced permissions exist, and there is no drift."""
import subprocess
import sys
import uuid

import psycopg
import pytest

from tests.test_migrations_phase1 import ROOT, _db_url, _env


@pytest.fixture(scope="module")
def fresh_db_url():
    name = f"fresh_p3_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(_db_url("postgres"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    return _db_url(name)


def test_phase3_schema_on_a_fresh_database(fresh_db_url):
    proc = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with psycopg.connect(fresh_db_url) as conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'")}
        for t in ("checklists_checklisttemplate", "checklists_checklistitem", "checklists_inspection",
                  "checklists_inspectionresponse", "checklists_finding", "workspace_worknote"):
            assert t in tables, t
        names = {r[0] for r in conn.execute("select conname from pg_constraint")} | {
            r[0] for r in conn.execute("select indexname from pg_indexes")}
        for n in ("uniq_checklist_version", "uniq_active_checklist_per_key", "uniq_checklist_item_position",
                  "checklist_item_range", "uniq_inspection_per_work_order_template",
                  "inspection_completed_has_timestamp", "uniq_response_per_item", "work_note_body_not_empty"):
            assert n in names, n
        codes = {r[0] for r in conn.execute("select code from rbac_permission")}
        assert {"checklist.view", "checklist.manage", "checklist.execute", "inspection.view", "inspection.execute",
                "inspection.review"} <= codes
    drift = subprocess.run([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], cwd=ROOT,
                           env=_env(fresh_db_url), capture_output=True, text=True, timeout=120)
    assert drift.returncode == 0, drift.stdout[-1500:]
