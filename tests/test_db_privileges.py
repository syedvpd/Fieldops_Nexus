"""Audit finding S-2: the production RUNTIME role must not be able to TRUNCATE (a table owner always can, and
TRUNCATE bypasses the append-only row trigger). Proves the privilege model of ``scripts/harden_db_roles.py`` on the
local test PostgreSQL inside a throw-away schema; nothing outside it is touched."""
import importlib.util
import pathlib

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "harden_db_roles.py"


def _load():
    spec = importlib.util.spec_from_file_location("harden_db_roles", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runtime_role_has_dml_but_no_truncate_ddl_or_trigger_rights():
    mod = _load()
    with connection.cursor() as cur:
        cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
        if not cur.fetchone()[0]:
            pytest.skip("needs a superuser test database to create throw-away roles")
        cur.execute("CREATE ROLE rt_migrator NOLOGIN")
        cur.execute("CREATE ROLE rt_app NOLOGIN")
        cur.execute("CREATE SCHEMA rt_priv AUTHORIZATION rt_migrator")
        cur.execute("SET ROLE rt_migrator")
        cur.execute("CREATE TABLE rt_priv.ledger (id int primary key, note text)")
        cur.execute("RESET ROLE")
        for stmt in mod.grant_statements("rt_priv", "rt_migrator", "rt_app"):
            cur.execute(stmt)
        # a table created LATER by the migrator inherits the same limited grants
        cur.execute("SET ROLE rt_migrator")
        cur.execute("CREATE TABLE rt_priv.later (id int primary key)")
        cur.execute("RESET ROLE")
        for table in ("ledger", "later"):
            cur.execute("SELECT has_table_privilege('rt_app', %s, 'INSERT'), has_table_privilege('rt_app', %s, 'DELETE'),"
                        " has_table_privilege('rt_app', %s, 'TRUNCATE'), has_table_privilege('rt_app', %s, 'TRIGGER'),"
                        " has_table_privilege('rt_app', %s, 'REFERENCES')", [f"rt_priv.{table}"] * 5)
            ins, dele, trunc, trig, ref = cur.fetchone()
            assert ins and dele, table
            assert not trunc and not trig and not ref, table
        cur.execute("SELECT has_schema_privilege('rt_app', 'rt_priv', 'CREATE')")
        assert cur.fetchone()[0] is False  # no DDL
        # behaviourally: the role really cannot truncate
        cur.execute("SET ROLE rt_app")
        cur.execute("INSERT INTO rt_priv.ledger VALUES (1, 'x')")
        with pytest.raises(Exception) as exc:
            with connection.cursor() as c2:
                c2.execute("SAVEPOINT s")
                try:
                    c2.execute("TRUNCATE rt_priv.ledger")
                finally:
                    c2.execute("ROLLBACK TO SAVEPOINT s")
        assert "permission denied" in str(exc.value).lower()
        cur.execute("RESET ROLE")
