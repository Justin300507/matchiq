import random
from datetime import datetime, timedelta
from pathlib import Path

from app.db import Base, get_engine, get_session_factory
from app.features.build_features import build_training_dataframe
from app.ml.backtest import run_backtest
from app.ml.train import FEATURE_COLUMNS
from app.models_db import Match, Team


def make_db_with_synthetic_matches(n_teams=6, n_matches=150):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    random.seed(7)
    teams = [Team(external_id=str(i), sport="nba", league="NBA", name=f"Team{i}") for i in range(n_teams)]
    db.add_all(teams)
    db.commit()

    for day in range(n_matches):
        home, away = random.sample(teams, 2)
        home_strong = home.id == teams[0].id
        home_score = random.randint(95, 115) + (10 if home_strong else 0)
        away_score = random.randint(90, 110)
        db.add(Match(
            external_id=f"m{day}", sport="nba", league="NBA",
            date=datetime(2025, 1, 1) + timedelta(days=day),
            home_team_id=home.id, away_team_id=away.id,
            home_score=home_score, away_score=away_score, status="final",
        ))
    db.commit()
    return db


def _train_artifact(db, sport, labels):
    from xgboost import XGBClassifier, XGBRegressor

    df = build_training_dataframe(db, sport)
    df = df[df["result"].isin(labels)]
    X = df[FEATURE_COLUMNS]
    y = df["result"].map({label: i for i, label in enumerate(labels)})

    classifier = XGBClassifier(n_estimators=20, max_depth=3)
    classifier.fit(X, y)
    regressor_home = XGBRegressor(n_estimators=10, max_depth=2).fit(X, df["home_score"])
    regressor_away = XGBRegressor(n_estimators=10, max_depth=2).fit(X, df["away_score"])

    return {
        "classifier": classifier,
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": FEATURE_COLUMNS,
        "labels": labels,
    }


def test_run_backtest_evaluates_the_held_out_split():
    db = make_db_with_synthetic_matches()
    artifact = _train_artifact(db, "nba", ["H", "A"])

    result = run_backtest(db, "nba", artifact)

    assert result.sport == "nba"
    assert result.predictions_evaluated > 0
    assert 0.0 <= result.model_accuracy <= 1.0
    assert 0.0 <= result.baseline_accuracy <= 1.0
    assert result.model_brier_score >= 0.0


def test_run_backtest_returns_zeroed_result_with_no_data(tmp_path: Path):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()
    artifact = {"classifier": None, "feature_columns": FEATURE_COLUMNS, "labels": ["H", "A"]}

    result = run_backtest(db, "nba", artifact)

    assert result.predictions_evaluated == 0
    assert result.model_accuracy == 0.0
