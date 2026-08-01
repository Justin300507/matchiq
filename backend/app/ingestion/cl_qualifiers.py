import argparse
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory
from app.ingestion.api_football_client import CHAMPIONS_LEAGUE_ID, fetch_fixtures
from app.ingestion.normalize import normalize_api_football_fixture, upsert_game

logger = logging.getLogger(__name__)

# football-data.org already covers the Champions League league/group stage
# onward; this only fills the qualifying-round gap it doesn't track, so any
# round without "qualifying" or "play-off" in its name is skipped to avoid
# ingesting duplicate (differently-numbered) copies of the same matches.
_QUALIFYING_ROUND_KEYWORDS = ("qualifying", "play-off", "playoff", "preliminary")


def _is_qualifying_round(round_name: str) -> bool:
    normalized = round_name.strip().lower()
    return any(keyword in normalized for keyword in _QUALIFYING_ROUND_KEYWORDS)


def sync_cl_qualifiers(db: Session, api_key: str, season: int) -> int:
    page = fetch_fixtures(api_key, CHAMPIONS_LEAGUE_ID, season)

    count = 0
    for raw in page["response"]:
        round_name = raw.get("league", {}).get("round", "")
        if not _is_qualifying_round(round_name):
            continue
        try:
            upsert_game(db, normalize_api_football_fixture(raw))
            count += 1
        except Exception:
            logger.warning("Skipping unparseable CL qualifier fixture %r", raw.get("fixture", {}).get("id"), exc_info=True)
            db.rollback()

    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    args = parser.parse_args()

    settings = get_settings()
    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()
    total = sync_cl_qualifiers(db, settings.api_football_key, args.season)
    print(f"Synced {total} Champions League qualifying/play-off fixtures")
