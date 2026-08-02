import random
from datetime import datetime, timedelta
from pathlib import Path

from app.db import Base, get_engine, get_session_factory
from app.features.build_features import compute_features
from app.ml.explain import explain_prediction
from app.models_db import Match, Team


def _train_and_save_artifact(db, sport, labels, artifact_dir: Path) -> dict:
    import joblib
    from xgboost import XGBClassifier, XGBRegressor

    from app.features.build_features import build_training_dataframe
    from app.ml.train import FEATURE_COLUMNS

    df = build_training_dataframe(db, sport)
    df = df[df["result"].isin(labels)]
    X = df[FEATURE_COLUMNS]
    y = df["result"].map({label: i for i, label in enumerate(labels)})

    if len(labels) == 2:
        classifier = XGBClassifier(n_estimators=20, max_depth=3)
    else:
        classifier = XGBClassifier(n_estimators=20, max_depth=3, objective="multi:softprob", num_class=len(labels))
    classifier.fit(X, y)
    regressor_home = XGBRegressor(n_estimators=10, max_depth=2).fit(X, df["home_score"])
    regressor_away = XGBRegressor(n_estimators=10, max_depth=2).fit(X, df["away_score"])

    artifact = {
        "classifier": classifier,
        "regressor_home": regressor_home,
        "regressor_away": regressor_away,
        "feature_columns": FEATURE_COLUMNS,
        "labels": labels,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, artifact_dir / f"{sport}_latest.joblib")
    return artifact


def make_db_with_synthetic_matches(sport, league, n_teams=6, n_matches=150, allow_draws=False):
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = get_session_factory(engine)()

    random.seed(42)
    teams = [Team(external_id=str(i), sport=sport, league=league, name=f"Team{i}") for i in range(n_teams)]
    db.add_all(teams)
    db.commit()

    for day in range(n_matches):
        home, away = random.sample(teams, 2)
        home_strong = home.id == teams[0].id
        if allow_draws:
            home_score = random.randint(0, 3) + (2 if home_strong else 0)
            away_score = random.randint(0, 3)
        else:
            home_score = random.randint(95, 115) + (10 if home_strong else 0)
            away_score = random.randint(90, 110)
        db.add(Match(
            external_id=f"m{day}",
            sport=sport,
            league=league,
            date=datetime(2025, 1, 1) + timedelta(days=day),
            home_team_id=home.id,
            away_team_id=away.id,
            home_score=home_score,
            away_score=away_score,
            status="final",
        ))
    db.commit()
    return db, teams


def test_explain_prediction_returns_all_seven_factors_for_binary_model(tmp_path: Path):
    db, teams = make_db_with_synthetic_matches("nba", "NBA")
    artifact = _train_and_save_artifact(db, "nba", ["H", "A"], tmp_path)

    target = Match(
        external_id="target", sport="nba", league="NBA",
        date=datetime(2025, 1, 1) + timedelta(days=160),
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(target)
    db.commit()

    features = compute_features(db, target)
    explanation = explain_prediction(artifact, features)

    assert len(explanation.factors) == 7
    factor_names = {f.name for f in explanation.factors}
    assert factor_names == set(artifact["feature_columns"])
    assert explanation.model_confidence in ("High", "Medium", "Low")

    # Sorted by strength of influence, strongest first.
    influences = [abs(f.relative_influence_pct) for f in explanation.factors]
    assert influences == sorted(influences, reverse=True)

    # Relative influences should sum (in absolute terms) to ~100%, since
    # they're normalized shares of the total margin swing toward/away from
    # a home win.
    assert abs(sum(abs(f.relative_influence_pct) for f in explanation.factors) - 100.0) < 0.01


def test_explain_prediction_returns_all_seven_factors_for_multiclass_model(tmp_path: Path):
    db, teams = make_db_with_synthetic_matches("football", "EPL", allow_draws=True, n_matches=200)
    artifact = _train_and_save_artifact(db, "football", ["H", "D", "A"], tmp_path)

    target = Match(
        external_id="target", sport="football", league="EPL",
        date=datetime(2025, 1, 1) + timedelta(days=210),
        home_team_id=teams[0].id, away_team_id=teams[1].id,
        home_score=None, away_score=None, status="scheduled",
    )
    db.add(target)
    db.commit()

    features = compute_features(db, target)
    explanation = explain_prediction(artifact, features)

    assert len(explanation.factors) == 7
    assert explanation.model_confidence in ("High", "Medium", "Low")
