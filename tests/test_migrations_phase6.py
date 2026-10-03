"""Fresh-database migration check for Phase 6 (new uniquely named database in the test container, never an
existing one): M11 tables, constraints, indexes and the synced permissions exist, no drift."""
import subprocess
import sys
import uuid

import psycopg
import pytest

from tests.test_migrations_phase1 import ROOT, _db_url, _env


@pytest.fixture(scope="module")
def fresh_db_url():
    name = f"fresh_p6_{uuid.uuid4().hex[:12]}"
    admin = psycopg.connect(_db_url("postgres"), autocommit=True)
    try:
        admin.execute(f'CREATE DATABASE "{name}"')
    finally:
        admin.close()
    return _db_url(name)


def test_phase6_schema_on_a_fresh_database(fresh_db_url):
    proc = subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], cwd=ROOT, env=_env(fresh_db_url),
                          capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stderr[-2000:]
    with psycopg.connect(fresh_db_url) as conn:
        tables = {r[0] for r in conn.execute(
            "select table_name from information_schema.tables where table_schema='public'")}
        for t in ("sla_slaprofile", "sla_slatarget", "sla_escalationrule", "sla_slatracking", "sla_slaevent",
                  "sla_slabreach"):
            assert t in tables, t
        names = {r[0] for r in conn.execute("select conname from pg_constraint")} | {
            r[0] for r in conn.execute("select indexname from pg_indexes")}
        for n in ("uniq_sla_profile_name_per_org", "uniq_active_sla_profile_org_scope",
                  "uniq_active_sla_profile_site_scope", "uniq_sla_target_per_priority", "sla_response_minutes_pos",
                  "sla_resolution_gte_response", "uniq_escalation_rule_step", "escalation_has_recipient",
                  "sla_one_subject", "uniq_sla_tracking_per_request", "uniq_sla_tracking_per_work_order",
                  "sla_paused_has_timestamp", "uniq_sla_event_dedupe", "uniq_sla_breach_per_target"):
            assert n in names, n
        codes = {r[0] for r in conn.execute("select code from rbac_permission")}
        assert {"sla.view", "sla.acknowledge", "sla.manage", "sla.process"} <= codes
    drift = subprocess.run([sys.executable, "manage.py", "makemigrations", "--check", "--dry-run"], cwd=ROOT,
                           env=_env(fresh_db_url), capture_output=True, text=True, timeout=120)
    assert drift.returncode == 0, drift.stdout[-1500:]
