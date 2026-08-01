import argparse
import logging

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, get_engine, get_session_factory
from app.ingestion.nba_client import fetch_games
from app.ingestion.normalize import normalize_nba_game, normalize_soccer_game, upsert_game
from app.ingestion.soccer_client import LEAGUE_CODES, fetch_matches

logger = logging.getLogger(__name__)


def backfill_nba(db: Session, api_key: str, seasons: list[str]) -> int:
    count = 0
    for season in seasons:
        start_date, end_date = f"{season[:4]}-10-01", f"{season[-4:]}-06-30"
        cursor = None
        while True:
            page = fetch_games(api_key, start_date, end_date, cursor=cursor)
            for raw in page["data"]:
                try:
                    upsert_game(db, normalize_nba_game(raw))
                    count += 1
                except Exception:
                    logger.warning("Skipping unparseable NBA game %r", raw.get("id"), exc_info=True)
                    db.rollback()
            cursor = page["meta"]["next_cursor"]
            if cursor is None:
                break
    return count


def backfill_soccer(db: Session, api_key: str, leagues: list[str], seasons: list[int]) -> int:
    count = 0
    for league in leagues:
        for season in seasons:
            page = fetch_matches(api_key, league, season)
            for raw in page["matches"]:
                try:
                    upsert_game(db, normalize_soccer_game(raw, league))
                    count += 1
                except Exception:
                    logger.warning("Skipping unparseable soccer match %r", raw.get("id"), exc_info=True)
                    db.rollback()
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--nba-seasons", nargs="*", default=["2023-2024", "2024-2025", "2025-2026"])
    parser.add_argument("--soccer-seasons", nargs="*", type=int, default=[2023, 2024, 2025])
    args = parser.parse_args()

    settings = get_settings()
    engine = get_engine(settings.database_url)
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    nba_count = backfill_nba(db, settings.nba_api_key, args.nba_seasons)
    soccer_count = backfill_soccer(db, settings.football_data_api_key, list(LEAGUE_CODES.keys()), args.soccer_seasons)
    print(f"Backfilled {nba_count} NBA games and {soccer_count} soccer games")
