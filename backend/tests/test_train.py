import random
from datetime import datetime, timedelta
from pathlib import Path

from app.db import Base, get_engine, get_session_factory
from app.ml.train import train_sport_models
from app.models_db import Match, Team


def make_db_with_synthetic_matches(n_teams=6, n_matches=120):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    random.seed(42)
    teams = [Team(external_id=str(i), sport="nba", league="NBA", name=f"Team{i}") for i in range(n_teams)]
    db.add_all(teams)
    db.commit()

    # Team 0 is a "strong" team that wins most home games, giving the model
    # a real signal to learn (unlike pure-random labels, which no model can beat).
    for day in range(n_matches):
        home, away = random.sample(teams, 2)
        home_strong = home.id == teams[0].id
        home_score = random.randint(95, 115) + (10 if home_strong else 0)
        away_score = random.randint(90, 110)
        db.add(Match(
            external_id=f"m{day}",
            sport="nba",
            league="NBA",
            date=datetime(2025, 1, 1) + timedelta(days=day),
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=home_score,
            away_score=away_score,
            status="final",
        ))
    db.commit()
    return db


def test_train_sport_models_saves_artifact_when_it_beats_baseline(tmp_path: Path):
    db = make_db_with_synthetic_matches()

    result = train_sport_models(db, sport="nba", artifact_dir=tmp_path)

    assert "model_metrics" in result
    assert "baseline_metrics" in result
    artifact_path = tmp_path / "nba_latest.joblib"
    if result["beat_baseline"]:
        assert artifact_path.exists()
        assert result["artifact_path"] == str(artifact_path)
    else:
        assert not artifact_path.exists()
