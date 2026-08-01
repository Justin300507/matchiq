from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def get_engine(database_url: str):
    return create_engine(database_url)


def get_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)
