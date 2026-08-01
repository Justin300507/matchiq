import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAccuracy } from "../api";
import type { BacktestOut } from "../types";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-gray-200 p-3 text-center">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

function SportAccuracy({ sport }: { sport: "nba" | "soccer" }) {
  const [backtest, setBacktest] = useState<BacktestOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setBacktest(null);
    setError(null);
    fetchAccuracy(sport)
      .then(setBacktest)
      .catch(() => setError(`No trained model available yet for ${sport}.`));
  }, [sport]);

  if (error) {
    return <p className="text-sm text-gray-500">{error}</p>;
  }

  if (backtest === null) {
    return <p className="text-sm text-gray-500">Loading...</p>;
  }

  return (
    <div>
      <h3 className="text-lg font-semibold capitalize">{sport}</h3>
      <p className="mt-1 text-xs text-gray-500">
        Backtested on {backtest.predictions_evaluated.toLocaleString()} held-out historical matches the model never
        trained on.
      </p>
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Winner accuracy" value={`${(backtest.model_accuracy * 100).toFixed(1)}%`} />
        <StatCard label="Brier score" value={backtest.model_brier_score.toFixed(3)} />
        <StatCard label="Log loss" value={backtest.model_log_loss.toFixed(3)} />
        <StatCard label="Baseline accuracy" value={`${(backtest.baseline_accuracy * 100).toFixed(1)}%`} />
        <StatCard label="Baseline Brier" value={backtest.baseline_brier_score.toFixed(3)} />
      </div>
    </div>
  );
}

export function AccuracyPage() {
  return (
    <div>
      <Link to="/" className="text-sm text-blue-600 hover:underline">&larr; Back</Link>
      <h2 className="mt-2 text-xl font-bold">Historical accuracy</h2>
      <p className="mt-1 text-sm text-gray-500">
        A genuine backtest against held-out historical results — not a log of predictions actually served, since
        MatchIQ doesn't persist a prediction history yet. Lower Brier score and log loss are better; higher accuracy
        is better. No ROI-vs-market comparison is shown, since MatchIQ doesn't have bookmaker odds data.
      </p>

      <div className="mt-6 space-y-8">
        <SportAccuracy sport="nba" />
        <SportAccuracy sport="soccer" />
      </div>
    </div>
  );
}
