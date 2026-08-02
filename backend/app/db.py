from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str):
    if not database_url.startswith("sqlite"):
        return create_engine(database_url)

    connect_args = {"check_same_thread": False}
    if ":memory:" in database_url:
        # In-memory SQLite: share a single connection across threads so a
        # session created in one thread (e.g. a test fixture) remains usable
        # from the worker threads FastAPI dispatches sync routes to.
        return create_engine(database_url, connect_args=connect_args, poolclass=StaticPool)
    return create_engine(database_url, connect_args=connect_args)


def get_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
