"""Test harness — makes `app` importable and gives every test a DISPOSABLE Postgres schema.

WHY A DISPOSABLE SCHEMA, NOT `public`. The store is append-only by design — the triggers reject
UPDATE and DELETE, which is the Finding A legal-artefact guarantee — so a test suite writing into
the real `public` schema would permanently insert junk it can never remove, and those test vendors
would show up in real cohort benchmarks forever. Each test that needs a store therefore gets its
OWN schema (`tprm_test_<uuid>`), created fresh and dropped whole afterwards. `DROP SCHEMA CASCADE`
is DDL, not a row mutation, so the append-only triggers do not block cleanup. Same Neon database
the app uses; the real data is never touched.

The DSN comes from `DATABASE_URL` (env or backend/.env). No DSN -> the suite skips the DB tests
clearly rather than silently doing nothing, because there is no local-file fallback any more.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))


def _dsn() -> str:
    """The Postgres DSN, from the environment or backend/.env. The suite runs against the same
    Neon database the app uses — but every test lands in its own throwaway schema (below)."""
    dsn = os.environ.get("DATABASE_URL", "").strip()
    if dsn:
        return dsn
    env = _BACKEND / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return ""


def _unpooled(dsn: str) -> str:
    """Neon's POOLER rejects `search_path` as a connection startup option (PgBouncer transaction
    mode also would not keep it stable across the autocommit statements this store runs). The
    schema-isolation the test harness needs therefore requires the UNPOOLED endpoint — which is
    the same host with `-pooler` removed. The app keeps using the pooled endpoint; only the tests,
    which set a per-run search_path, switch to unpooled."""
    return dsn.replace("-pooler.", ".")


@pytest.fixture(scope="session")
def dsn() -> str:
    value = _dsn()
    if not value:
        pytest.skip("DATABASE_URL not set — the suite needs the Postgres DSN (see backend/.env)")
    return _unpooled(value)


@pytest.fixture
def store(dsn):  # noqa: ANN001
    """A store in a fresh, isolated schema, dropped whole when the test ends.

    Function-scoped on purpose: append-only means a schema cannot be cleaned BETWEEN tests (you
    cannot DELETE the rows), so isolation has to be a fresh schema per test. That costs a schema
    create/drop per test against Neon; correctness on an append-only store is worth the round trip.
    """
    from app.pg_store import PostgresStore

    schema = f"tprm_test_{uuid.uuid4().hex[:12]}"
    st = PostgresStore(dsn, schema=schema)
    try:
        yield st
    finally:
        try:
            with st._conn.cursor() as cur:  # noqa: SLF001 — the harness owns this store
                cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        finally:
            st.close()
