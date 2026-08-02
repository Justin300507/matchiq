import logging
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory
from app.ingestion.nba_client import fetch_games
from app.ingestion.normalize import (
    normalize_nba_game,
    normalize_soccer_game,
    upsert_game,
)
from app.ingestion.soccer_client import LEAGUE_CODES, fetch_matches

logger = logging.getLogger(__name__)


def sync_recent(db: Session, nba_api_key: str, football_api_key: str, days_back: int = 3, days_forward: int = 7) -> int:
    today_utc = datetime.now(timezone.utc).date()
    start = (today_utc - timedelta(days=days_back)).isoformat()
    end = (today_utc + timedelta(days=days_forward)).isoformat()

    count = 0
    nba_page = fetch_games(nba_api_key, start, end)
    for raw in nba_page["data"]:
        try:
            upsert_game(db, normalize_nba_game(raw))
            count += 1
        except Exception:
            logger.warning("Skipping unparseable NBA game %r", raw.get("id"), exc_info=True)
            db.rollback()

    current_season = today_utc.year if today_utc.month >= 7 else today_utc.year - 1
    for league in LEAGUE_CODES:
        try:
            soccer_page = fetch_matches(football_api_key, league, current_season)
        except requests.exceptions.RequestException:
            # A competition's fixture list for the current season may not be
            # published yet (e.g. Champions League group-stage dates aren't
            # confirmed until closer to kickoff) — skip it, not the whole sync.
            logger.warning("Skipping %s season=%s: fixtures not available", league, current_season, exc_info=True)
            continue
        for raw in soccer_page["matches"]:
            try:
                upsert_game(db, normalize_soccer_game(raw, league))
                count += 1
            except Exception:
                logger.warning("Skipping unparseable football match %r", raw.get("id"), exc_info=True)
                db.rollback()

    return count


if __name__ == "__main__":
    settings = get_settings()
    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()
    total = sync_recent(db, settings.nba_api_key, settings.football_data_api_key)
    print(f"Synced {total} games")
