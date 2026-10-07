"""Unit tests for app.database: engine construction, the session factory
and the request-scoped `get_db` dependency.

These exercise app.database directly rather than through the running
FastAPI app -- the application starting up and serving requests at all is
already covered by test_health.py and the service-level suites. The point
here is the plumbing itself: a session handed out by `get_db` is usable and
is closed whether the caller finishes normally or raises, SQLite's
cross-thread restriction really is lifted the way the module's docstring
promises, `SessionLocal`'s autoflush/expire settings behave as configured,
and `DATABASE_URL` actually drives which engine gets built.
"""

import importlib
import threading

import pytest
from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, Session, mapped_column

import app.database as db_module
from app.database import Base, SessionLocal, engine, get_db

# ------------------------------------------------------------- get_db ----


def test_get_db_yields_a_working_session():
    gen = get_db()
    session = next(gen)
    try:
        assert session.execute(text("SELECT 1")).scalar() == 1
    finally:
        gen.close()


def test_get_db_closes_the_session_when_the_generator_is_exhausted_normally(monkeypatch):
    closed = []
    original_close = Session.close

    def tracking_close(self):
        closed.append(self)
        return original_close(self)

    monkeypatch.setattr(Session, "close", tracking_close)

    gen = get_db()
    session = next(gen)
    with pytest.raises(StopIteration):
        next(gen)

    assert session in closed


def test_get_db_closes_the_session_even_when_the_handler_raises(monkeypatch):
    """FastAPI tears a sync dependency's generator down by throwing the
    handler's exception back into it. The `finally` in get_db has to close
    the session on that path too, not only on the happy one."""
    closed = []
    original_close = Session.close

    def tracking_close(self):
        closed.append(self)
        return original_close(self)

    monkeypatch.setattr(Session, "close", tracking_close)

    gen = get_db()
    session = next(gen)

    with pytest.raises(RuntimeError):
        gen.throw(RuntimeError("handler blew up"))

    assert session in closed


# ----------------------------------------------------- cross-thread use --


def test_sqlite_connections_survive_crossing_threads():
    """The whole reason app/database.py sets `check_same_thread: False` is
    that FastAPI runs a sync dependency in its threadpool, not on whatever
    thread first touched the engine. Reproduce exactly that: check a
    connection out on this thread, then again from a different one, and
    require no error -- with the restriction left on, the second checkout
    raises `ProgrammingError: SQLite objects created in a thread can only
    be used in that same thread`."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    errors = []

    def worker():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - failure path only
            errors.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert errors == []


# ------------------------------------------------------------ SessionLocal

# Table names unique to this module so they don't collide with app.models's
# tables (same Base, same shared metadata) or with each other. Created at
# import time (not inside a fixture) so the physical table exists before
# *any* test in the suite runs -- including other modules' autouse fixtures
# that sweep every table `Base.metadata` knows about (see test_auth.py's
# `_clean_state`), which would otherwise hit a table registered in metadata
# but never created.


class _AutoflushProbe(Base):
    __tablename__ = "_database_test_autoflush_probe"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)


class _ExpireProbe(Base):
    __tablename__ = "_database_test_expire_probe"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String)


Base.metadata.create_all(bind=engine, tables=[_AutoflushProbe.__table__, _ExpireProbe.__table__])


def test_sessionlocal_disables_autoflush_before_queries():
    """SQLAlchemy's default (`autoflush=True`) would flush the pending
    insert before the SELECT runs, so the row would already be visible.
    `SessionLocal` turns that off (see app/database.py), so it must not be."""
    session = SessionLocal()
    try:
        session.add(_AutoflushProbe(id=101, name="pending"))

        seen_before_flush = session.query(_AutoflushProbe).filter_by(id=101).first()
        assert seen_before_flush is None

        session.commit()

        seen_after_commit = session.query(_AutoflushProbe).filter_by(id=101).first()
        assert seen_after_commit is not None
    finally:
        session.rollback()
        session.close()


def test_sessionlocal_does_not_expire_objects_on_commit():
    """SQLAlchemy's default (`expire_on_commit=True`) clears an instance's
    loaded attributes on commit, so the next attribute access re-queries the
    row. `SessionLocal` sets `expire_on_commit=False` (see app/database.py)
    specifically so a handler can still read the object it just committed
    without an extra round trip -- verify the attribute survives in the
    instance's own `__dict__` rather than being lazily reloaded."""
    session = SessionLocal()
    try:
        obj = _ExpireProbe(id=202, name="before-commit")
        session.add(obj)
        session.commit()

        assert "name" in obj.__dict__
        assert obj.name == "before-commit"
    finally:
        session.close()


# -------------------------------------------------------- DATABASE_URL ---


def test_database_url_defaults_to_a_local_sqlite_file_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        reloaded = importlib.reload(db_module)
        assert reloaded.DATABASE_URL == "sqlite:///./app.db"
        assert reloaded.engine.dialect.name == "sqlite"
    finally:
        importlib.reload(db_module)


def test_database_url_override_builds_an_engine_for_that_database(monkeypatch):
    """Pointing DATABASE_URL at Postgres has to actually change which
    engine gets built -- not just change a string nobody reads. create_engine
    does not connect eagerly, so this is safe to assert without a live
    Postgres server."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/example")
    try:
        reloaded = importlib.reload(db_module)
        assert reloaded.DATABASE_URL.startswith("postgresql")
        assert reloaded.engine.dialect.name == "postgresql"
    finally:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        importlib.reload(db_module)
