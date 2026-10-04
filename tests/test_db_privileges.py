"""Audit finding S-2: the production RUNTIME role must not be able to TRUNCATE (a table owner always can, and
TRUNCATE bypasses the append-only row trigger), nor run DDL, nor be a superuser / bypass row security. Proves the
privilege model of ``scripts/harden_db_roles.py`` on the local test PostgreSQL inside a throw-away schema and
throw-away roles (all rolled back with the test transaction); nothing else is touched."""
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


def _need_superuser(cur):
    cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
    if not cur.fetchone()[0]:
        pytest.skip("needs a superuser test database to create throw-away roles")


def _denied(cur, sql_text):
    """Runs ``sql_text`` as the current (runtime) role and returns the error text; the transaction survives."""
    cur.execute("SAVEPOINT probe")
    try:
        cur.execute(sql_text)
    except Exception as exc:  # noqa: BLE001 - psycopg raises several error classes for a refused statement
        cur.execute("ROLLBACK TO SAVEPOINT probe")
        return str(exc).lower()
    cur.execute("ROLLBACK TO SAVEPOINT probe")
    return None


def test_runtime_role_has_dml_but_no_truncate_ddl_or_trigger_rights():
    mod = _load()
    with connection.cursor() as cur:
        _need_superuser(cur)
        cur.execute("CREATE ROLE rt_migrator NOLOGIN")
        cur.execute("CREATE ROLE rt_app NOLOGIN")
        cur.execute("CREATE SCHEMA rt_priv AUTHORIZATION rt_migrator")
        cur.execute("SET ROLE rt_migrator")
        cur.execute("CREATE TABLE rt_priv.ledger (id int primary key, note text)")
        cur.execute("RESET ROLE")
        for stmt in mod.grant_statements("rt_priv", "rt_migrator", "rt_app"):
            cur.execute(stmt)
        # a table created LATER by the migrator inherits the same limited grants (default privileges)
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
        assert cur.fetchone()[0] is False  # no CREATE on the application schema
        # behaviourally, as the runtime role: DML works, TRUNCATE and every DDL statement is refused
        cur.execute("SET ROLE rt_app")
        cur.execute("INSERT INTO rt_priv.ledger VALUES (1, 'x')")
        cur.execute("UPDATE rt_priv.ledger SET note = 'y' WHERE id = 1")
        assert "permission denied" in _denied(cur, "TRUNCATE rt_priv.ledger")
        for ddl in ("ALTER TABLE rt_priv.ledger ADD COLUMN extra int", "DROP TABLE rt_priv.ledger",
                    "CREATE TABLE rt_priv.sneaky (id int)"):
            err = _denied(cur, ddl)
            assert err and ("permission denied" in err or "must be owner" in err), ddl
        cur.execute("RESET ROLE")


def test_runtime_role_attributes_are_forced_to_least_privilege():
    mod = _load()
    with connection.cursor() as cur:
        _need_superuser(cur)
        cur.execute("CREATE ROLE rt_risky NOLOGIN SUPERUSER BYPASSRLS CREATEROLE CREATEDB")
        for stmt in mod.role_attribute_statements("rt_risky"):
            cur.execute(stmt)
        cur.execute("SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles WHERE rolname = 'rt_risky'")
        assert cur.fetchone() == (False, False, False, False)
