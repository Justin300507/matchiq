from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory

app = FastAPI(title="MatchIQ API")

_settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in _settings.allowed_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = get_engine(_settings.database_url)
Base.metadata.create_all(_engine)
_SessionFactory = get_session_factory(_engine)


def get_db():
    db = _SessionFactory()
    try:
        yield db
    finally:
        db.close()


def get_artifact_dir():
    return _settings.artifact_dir


from app.routers import accuracy, chat, predictions, teams

app.include_router(predictions.router)
app.include_router(teams.router)
app.include_router(accuracy.router)
app.include_router(chat.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
