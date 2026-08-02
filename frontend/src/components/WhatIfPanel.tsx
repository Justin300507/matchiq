import { useState } from "react";
import { fetchWhatIf } from "../api";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { WhatIfOut } from "../types";

// Mirrors app/ml/explain.py's _FEATURE_LABELS — these are the only real
// inputs the model uses, so they're the only levers a "what-if" can honestly
// offer (no lineup/injury/weather data exists to simulate against).
const FEATURE_OPTIONS: { name: string; label: string }[] = [
  { name: "home_form_last5", label: "Home team's recent form" },
  { name: "away_form_last5", label: "Away team's recent form" },
  { name: "home_win_rate_home", label: "Home team's home advantage" },
  { name: "away_win_rate_away", label: "Away team's away form" },
  { name: "h2h_home_win_rate", label: "Head-to-head history" },
  { name: "home_rest_days", label: "Home team's rest advantage" },
  { name: "away_rest_days", label: "Away team's rest advantage" },
];

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function WhatIfPanel({ gameId }: { gameId: number }) {
  const [feature, setFeature] = useState(FEATURE_OPTIONS[0].name);
  const [value, setValue] = useState("0.8");
  const [result, setResult] = useState<WhatIfOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleRun() {
    const parsed = Number(value);
    if (Number.isNaN(parsed)) {
      setError("Enter a valid number.");
      return;
    }
    setIsLoading(true);
    setError(null);
    fetchWhatIf(gameId, { [feature]: parsed })
      .then(setResult)
      .catch(() => setError("Couldn't run the what-if simulation. Please try again later."))
      .finally(() => setIsLoading(false));
  }

  return (
    <div>
      <p className="mb-3 text-xs text-gray-500">
        Change one of the model's real inputs and see how the prediction shifts. This is a genuine counterfactual
        using the actual trained model — not a lineup/injury/weather simulator, since MatchIQ has no such data.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <label className="text-sm">
          Feature
          <select
            className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
            value={feature}
            onChange={(e) => setFeature(e.target.value)}
          >
            {FEATURE_OPTIONS.map((f) => (
              <option key={f.name} value={f.name}>{f.label}</option>
            ))}
          </select>
        </label>
        <label className="text-sm">
          New value
          <input
            type="number"
            step="0.1"
            className="ml-2 w-24 rounded border border-gray-300 px-2 py-1 text-sm"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={handleRun}
          disabled={isLoading}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? "Running..." : "Run what-if"}
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}

      {result && (
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <p className="mb-1 font-semibold text-gray-700">Original</p>
            <ConfidenceBadge confidence={result.original.model_confidence} />
            <p className="mt-1 text-gray-600">Home {pct(result.original.home_win_prob)}</p>
            {result.original.draw_prob !== null && (
              <p className="text-gray-600">Draw {pct(result.original.draw_prob)}</p>
            )}
            <p className="text-gray-600">Away {pct(result.original.away_win_prob)}</p>
          </div>
          <div>
            <p className="mb-1 font-semibold text-gray-700">Counterfactual</p>
            <ConfidenceBadge confidence={result.counterfactual.model_confidence} />
            <p className="mt-1 text-gray-600">Home {pct(result.counterfactual.home_win_prob)}</p>
            {result.counterfactual.draw_prob !== null && (
              <p className="text-gray-600">Draw {pct(result.counterfactual.draw_prob)}</p>
            )}
            <p className="text-gray-600">Away {pct(result.counterfactual.away_win_prob)}</p>
          </div>
        </div>
      )}
    </div>
  );
}
