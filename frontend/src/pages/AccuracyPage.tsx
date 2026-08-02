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

function ConfusionMatrix({ labels, matrix }: { labels: string[]; matrix: number[][] }) {
  if (labels.length === 0 || matrix.length === 0) {
    return null;
  }
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-semibold text-gray-700">Confusion matrix (rows = actual, columns = predicted)</p>
      <table className="border-collapse text-xs">
        <thead>
          <tr>
            <th className="border border-gray-200 p-2"></th>
            {labels.map((label) => (
              <th key={label} className="border border-gray-200 p-2 font-medium">{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={labels[i]}>
              <th className="border border-gray-200 p-2 font-medium">{labels[i]}</th>
              {row.map((count, j) => (
                <td
                  key={labels[j]}
                  className={`border border-gray-200 p-2 text-center ${i === j ? "bg-green-50 font-semibold" : ""}`}
                >
                  {count}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReliabilityDiagram({ bins }: { bins: BacktestOut["reliability_bins"] }) {
  if (bins.length === 0) {
    return null;
  }
  return (
    <div className="mt-4">
      <p className="mb-2 text-xs font-semibold text-gray-700">
        Reliability (predicted confidence vs. how often that confidence was actually correct)
      </p>
      <div className="space-y-1">
        {bins.map((bin) => (
          <div key={bin.bin_start} className="flex items-center gap-2 text-xs">
            <span className="w-24 text-gray-500">
              {Math.round(bin.bin_start * 100)}–{Math.round(bin.bin_end * 100)}%
            </span>
            <div className="relative h-3 flex-1 rounded bg-gray-100">
              <div className="absolute inset-y-0 left-0 rounded bg-gray-300" style={{ width: `${bin.avg_confidence * 100}%` }} />
              <div className="absolute inset-y-0 left-0 rounded bg-blue-600" style={{ width: `${bin.observed_accuracy * 100}%` }} />
            </div>
            <span className="w-32 text-gray-500">
              {Math.round(bin.observed_accuracy * 100)}% actual · n={bin.count}
            </span>
          </div>
        ))}
      </div>
      <p className="mt-1 text-xs text-gray-400">
        Blue bar = observed accuracy in that confidence bucket; gray bar = the model's average stated confidence
        there. A well-calibrated model has the blue bar roughly matching the bucket's confidence range.
      </p>
    </div>
  );
}

function SportAccuracy({ sport }: { sport: "nba" | "football" }) {
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
        <StatCard label="ROC AUC" value={backtest.roc_auc === null ? "Unavailable" : backtest.roc_auc.toFixed(3)} />
        <StatCard label="Baseline accuracy" value={`${(backtest.baseline_accuracy * 100).toFixed(1)}%`} />
        <StatCard label="Baseline Brier" value={backtest.baseline_brier_score.toFixed(3)} />
      </div>

      <ConfusionMatrix labels={backtest.labels} matrix={backtest.confusion_matrix} />
      <ReliabilityDiagram bins={backtest.reliability_bins} />
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
        is better. ROC AUC shows "Unavailable" rather than a fake number whenever the held-out set doesn't contain
        both outcomes. Prediction drift (performance changing over time) isn't shown for the same reason — it would
        need a persisted history of predictions actually served, which doesn't exist yet.
      </p>

      <div className="mt-6 space-y-8">
        {/* NBA is temporarily removed from the UI — kept in the backend and API. */}
        <SportAccuracy sport="football" />
      </div>
    </div>
  );
}
