from sqlalchemy.orm import Session

from app.models_db import Match

DEFAULT_RATING = 1500.0
K_FACTOR = 20.0


def compute_elo_ratings(db: Session, sport: str) -> dict[int, float]:
    """Standard Elo, processing every final match for the sport in
    chronological order. Every team starts at 1500; a real historical
    power rating emerges from the actual sequence of results — nothing
    fabricated, no external rating data needed."""
    matches = (
        db.query(Match)
        .filter(Match.sport == sport, Match.status == "final")
        .order_by(Match.date.asc())
        .all()
    )

    ratings: dict[int, float] = {}
    for match in matches:
        home_rating = ratings.get(match.home_team_id, DEFAULT_RATING)
        away_rating = ratings.get(match.away_team_id, DEFAULT_RATING)

        expected_home = 1 / (1 + 10 ** ((away_rating - home_rating) / 400))
        if match.home_score > match.away_score:
            actual_home = 1.0
        elif match.home_score < match.away_score:
            actual_home = 0.0
        else:
            actual_home = 0.5

        delta = K_FACTOR * (actual_home - expected_home)
        ratings[match.home_team_id] = home_rating + delta
        ratings[match.away_team_id] = away_rating - delta

    return ratings
