"""Unit tests for app/database.py: engine/session configuration, the
sqlite/"real database" branch, and the get_db dependency's close-on-exit
contract.

Assumption: the module reads DATABASE_URL and derives `_connect_args` once,
at import time, so the "defaults to sqlite" and "honors DATABASE_URL"
criteria can't be observed on the already-imported `app.database` singleton
(every other test module, and app.main, depends on that one instance staying
put). Those cases load a second, throwaway copy of the same source file via
importlib instead of mutating or reloading the shared module -- see
`_load_database_module` below.
"""

import importlib.util
import sys
from types import ModuleType

import pytest
from sqlalchemy.orm import DeclarativeBase, Session

import app.database as database


def _load_database_module(monkeypatch: pytest.MonkeyPatch, database_url: str | None) -> ModuleType:
    """Import a fresh copy of app/database.py under a throwaway module name,
    with DATABASE_URL set as given (or unset) for that import only.

    A fresh copy, not a reload of `app.database` itself, so the engine and
    Base every other test (and app.main) already holds stay exactly as they
    were.
    """
    if database_url is None:
        monkeypatch.delenv("DATABASE_URL", raising=False)
    else:
        monkeypatch.setenv("DATABASE_URL", database_url)

    spec = importlib.util.spec_from_file_location(
        f"app_database_under_test_{id(monkeypatch)}", database.__file__
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def test_database_url_defaults_to_sqlite_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = _load_database_module(monkeypatch, None)
    assert fresh.DATABASE_URL == "sqlite:///./app.db"


def test_database_url_honors_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    fresh = _load_database_module(monkeypatch, "sqlite:///./other.db")
    assert fresh.DATABASE_URL == "sqlite:///./other.db"
    assert str(fresh.engine.url) == "sqlite:///./other.db"


def test_sqlite_url_disables_check_same_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """SQLite connections are single-thread by default, which breaks under
    FastAPI's sync dependency running in a threadpool; the module must turn
    that check off for sqlite URLs."""
    fresh = _load_database_module(monkeypatch, "sqlite:///./app.db")
    assert fresh._connect_args == {"check_same_thread": False}


def test_non_sqlite_url_does_not_set_check_same_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """A real database server has no such restriction, and psycopg does not
    accept a `check_same_thread` connect argument -- it must not be passed."""
    fresh = _load_database_module(
        monkeypatch, "postgresql+psycopg://user:pass@localhost/testdb"
    )
    assert fresh._connect_args == {}


def test_base_is_a_declarative_base_models_can_inherit() -> None:
    assert issubclass(database.Base, DeclarativeBase)


def test_models_register_on_the_shared_base() -> None:
    """app.models inherits app.database.Base; its tables must land on that
    same Base's metadata, or app.main's `Base.metadata.create_all` would
    silently create nothing for them."""
    import app.models  # noqa: F401 -- import registers the tables as a side effect

    assert "users" in database.Base.metadata.tables
    assert "documents" in database.Base.metadata.tables


def test_get_db_yields_a_usable_session() -> None:
    gen = database.get_db()
    session = next(gen)
    try:
        assert isinstance(session, Session)
    finally:
        gen.close()


def test_get_db_closes_the_session_after_normal_use(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = {"called": False}

    class _FakeSession:
        def close(self) -> None:
            closed["called"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: _FakeSession())

    gen = database.get_db()
    session = next(gen)
    assert isinstance(session, _FakeSession)
    assert closed["called"] is False  # not closed while still in use

    with pytest.raises(StopIteration):
        next(gen)
    assert closed["called"] is True


def test_get_db_closes_the_session_even_when_the_consumer_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A handler that raises mid-request must not leak its DB session --
    FastAPI throws the exception back into the dependency generator at the
    yield point, and the `finally` must still run."""
    closed = {"called": False}

    class _FakeSession:
        def close(self) -> None:
            closed["called"] = True

    monkeypatch.setattr(database, "SessionLocal", lambda: _FakeSession())

    gen = database.get_db()
    next(gen)

    class _Boom(Exception):
        pass

    with pytest.raises(_Boom):
        gen.throw(_Boom())

    assert closed["called"] is True
