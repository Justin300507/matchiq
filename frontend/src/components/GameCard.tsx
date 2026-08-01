import { useState } from "react";
import { Link } from "react-router-dom";
import { fetchExplanation } from "../api";
import { ConfidenceBadge } from "./ConfidenceBadge";
import type { ExplanationOut, PredictionOut } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function signedPct(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

export function GameCard({ prediction }: { prediction: PredictionOut }) {
  const [isOpen, setIsOpen] = useState(false);
  const [explanation, setExplanation] = useState<ExplanationOut | null>(null);
  const [explainError, setExplainError] = useState<string | null>(null);
  const [isLoadingExplanation, setIsLoadingExplanation] = useState(false);

  function handleToggleWhy() {
    if (isOpen) {
      setIsOpen(false);
      return;
    }
    setIsOpen(true);
    if (explanation || isLoadingExplanation) {
      return;
    }
    setIsLoadingExplanation(true);
    setExplainError(null);
    fetchExplanation(prediction.game_id)
      .then(setExplanation)
      .catch(() => setExplainError("Couldn't load the explanation. Please try again later."))
      .finally(() => setIsLoadingExplanation(false));
  }

  return (
    <div className="rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex justify-between text-sm text-gray-500">
        <span>{prediction.league}</span>
        <span>{new Date(prediction.date).toLocaleDateString()}</span>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <Link to={`/team/${prediction.home_team.id}`} className="font-semibold hover:underline">
          {prediction.home_team.name}
        </Link>
        <span className="text-lg font-bold">{Math.round(prediction.predicted_home_score)}</span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <Link to={`/team/${prediction.away_team.id}`} className="font-semibold hover:underline">
          {prediction.away_team.name}
        </Link>
        <span className="text-lg font-bold">{Math.round(prediction.predicted_away_score)}</span>
      </div>

      <div className="mt-3 h-2 w-full overflow-hidden rounded bg-gray-200">
        <div className="h-full bg-blue-500" style={{ width: pct(prediction.home_win_prob) }} />
      </div>
      <div className="mt-1 flex justify-between text-xs text-gray-600">
        <span>Home <span>{pct(prediction.home_win_prob)}</span></span>
        {prediction.draw_prob !== null && <span>Draw <span>{pct(prediction.draw_prob)}</span></span>}
        <span>Away <span>{pct(prediction.away_win_prob)}</span></span>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <ConfidenceBadge confidence={prediction.model_confidence} />
        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleToggleWhy}
            className="text-xs font-medium text-blue-600 hover:underline"
          >
            {isOpen ? "Hide explanation" : "Why?"}
          </button>
          <Link to={`/match/${prediction.game_id}`} className="text-xs font-medium text-blue-600 hover:underline">
            Full match
          </Link>
        </div>
      </div>

      {isOpen && (
        <div className="mt-2 rounded border border-gray-100 bg-gray-50 p-3 text-xs">
          {isLoadingExplanation && <p className="text-gray-500">Loading explanation...</p>}
          {explainError && <p className="text-red-600">{explainError}</p>}
          {explanation && (
            <ul className="space-y-1">
              {explanation.factors.map((factor) => (
                <li key={factor.name} className="flex justify-between">
                  <span className="text-gray-600">{factor.label}</span>
                  <span className={factor.relative_influence_pct >= 0 ? "text-green-700" : "text-red-700"}>
                    {signedPct(factor.relative_influence_pct)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
