"""The store factory — Postgres only, no local-file fallback.

The factory used to switch between SQLite and Postgres on DATABASE_URL. There is no switch any
more: a defensible, reconstructible evidence trail is the product, and a weaker persistence
guarantee is not a substitute for it. So the only behaviours to lock down are that a missing DSN
fails loudly, and a present DSN constructs a PostgresStore with it.
"""

from __future__ import annotations

import pytest

from app import pg_store, storage
from app.config import Settings


def test_missing_dsn_fails_loudly(monkeypatch):
    """No silent fallback: an unconfigured store is an error the operator can see, not a quiet
    downgrade to something with weaker guarantees."""
    monkeypatch.setattr(storage, "get_settings", lambda: Settings(database_url=""))
    with pytest.raises(storage.StorageNotConfigured, match="DATABASE_URL"):
        storage.get_store()


class _FakePG:
    """Stands in for PostgresStore so the factory can be tested without a live connection."""

    def __init__(self, dsn, *, conn=None, on_close=None) -> None:
        self.dsn, self.conn, self._on_close = dsn, conn, on_close

    def close(self) -> None:
        if self._on_close is not None:
            self._on_close(self.conn)


def test_get_store_constructs_postgres_with_the_dsn(monkeypatch):
    """With DATABASE_URL set the factory builds a PostgresStore on that DSN.

    The no-pool path: `psycopg_pool` is an optional dependency, and without it the factory must
    still hand back a working store rather than failing — a missing optional package should slow
    the app down, not stop it.
    """
    monkeypatch.setattr(storage, "get_settings",
                        lambda: Settings(database_url="postgresql://u:p@h/db"))
    monkeypatch.setattr(pg_store, "PostgresStore", _FakePG)
    monkeypatch.setattr(storage, "_get_pool", lambda dsn: None)

    store = storage.get_store()
    assert store.dsn == "postgresql://u:p@h/db"
    assert store.conn is None, "with no pool the store opens its own connection"
    store.close()


def test_get_store_borrows_from_the_pool_and_returns_the_connection(monkeypatch):
    """The pooled path — the one production takes.

    The store's lifecycle is per-operation but the *connection's* is not: it is lent by the
    process-wide pool and must go back on `close()`. A store that closed the connection outright,
    or leaked it, would drain the pool over a few hundred requests — which is the failure this
    locks down, because it would surface as a slow hang under load rather than as an error.
    """
    monkeypatch.setattr(storage, "get_settings",
                        lambda: Settings(database_url="postgresql://u:p@h/db"))
    monkeypatch.setattr(pg_store, "PostgresStore", _FakePG)
    sentinel = object()
    returned: list[object] = []

    class FakePool:
        def getconn(self) -> object:
            return sentinel

        def putconn(self, conn: object) -> None:
            returned.append(conn)

    monkeypatch.setattr(storage, "_get_pool", lambda dsn: FakePool())

    store = storage.get_store()
    assert store.conn is sentinel, "the store must use the lent connection, not open its own"
    assert returned == [], "not returned while the store is still in use"
    store.close()
    assert returned == [sentinel], "close() returns the connection to the pool"


def test_a_failed_store_construction_does_not_leak_the_connection(monkeypatch):
    """If schema setup raises, the borrowed connection still goes back.

    Otherwise a transient DDL failure would permanently cost the pool a slot, and enough of them
    would wedge the process in a way a restart is the only cure for.
    """
    monkeypatch.setattr(storage, "get_settings",
                        lambda: Settings(database_url="postgresql://u:p@h/db"))
    sentinel = object()
    returned: list[object] = []

    class Exploding:
        def __init__(self, dsn, *, conn=None, on_close=None) -> None:
            raise RuntimeError("schema setup failed")

    class FakePool:
        def getconn(self) -> object:
            return sentinel

        def putconn(self, conn: object) -> None:
            returned.append(conn)

    monkeypatch.setattr(pg_store, "PostgresStore", Exploding)
    monkeypatch.setattr(storage, "_get_pool", lambda dsn: FakePool())

    with pytest.raises(RuntimeError, match="schema setup failed"):
        storage.get_store()
    assert returned == [sentinel]


def test_store_protocol_is_satisfied_by_postgres():
    """The Protocol is the contract the app codes against; PostgresStore must structurally match
    it, so a missing method is caught here rather than at a request in production."""
    for name in ("put", "get", "for_vendor", "verify", "put_score", "latest_score",
                 "score_history", "put_findings", "findings_for_vendor", "put_profile",
                 "latest_profile", "cohort_peers", "cohort_signal_bands", "cohort_members",
                 "close"):
        assert callable(getattr(pg_store.PostgresStore, name)), f"PostgresStore lacks {name}()"
