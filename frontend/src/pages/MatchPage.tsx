import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchExplanation, fetchMatchContext, fetchPrediction } from "../api";
import { ConfidenceBadge } from "../components/ConfidenceBadge";
import { RecentFormList } from "../components/RecentFormList";
import { SimulationPanel } from "../components/SimulationPanel";
import { WhatIfPanel } from "../components/WhatIfPanel";
import type { ExplanationOut, MatchContextOut, PredictionOut } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function signedPct(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

export function MatchPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const id = Number(gameId);

  const [prediction, setPrediction] = useState<PredictionOut | null>(null);
  const [context, setContext] = useState<MatchContextOut | null>(null);
  const [explanation, setExplanation] = useState<ExplanationOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPrediction(null);
    setContext(null);
    setExplanation(null);
    setError(null);

    fetchPrediction(id).then(setPrediction).catch(() => setError("Couldn't load this match. Please try again later."));
    fetchMatchContext(id).then(setContext).catch(() => {});
    fetchExplanation(id).then(setExplanation).catch(() => {});
  }, [id]);

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (prediction === null) {
    return <p className="text-gray-500">Loading match...</p>;
  }

  return (
    <div>
      <Link to="/" className="text-sm text-blue-600 hover:underline">&larr; Back</Link>

      <div className="mt-2 flex items-center justify-between text-sm text-gray-500">
        <span>{prediction.league}</span>
        <span>{new Date(prediction.date).toLocaleString()}</span>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-4 text-center">
        <div>
          <Link to={`/team/${prediction.home_team.id}`} className="text-lg font-semibold hover:underline">
            {prediction.home_team.name}
          </Link>
          <div className="text-2xl font-bold">{Math.round(prediction.predicted_home_score)}</div>
        </div>
        <div>
          <Link to={`/team/${prediction.away_team.id}`} className="text-lg font-semibold hover:underline">
            {prediction.away_team.name}
          </Link>
          <div className="text-2xl font-bold">{Math.round(prediction.predicted_away_score)}</div>
        </div>
      </div>

      <div className="mt-4 flex justify-center">
        <ConfidenceBadge confidence={prediction.model_confidence} />
      </div>

      <div className="mt-3 flex justify-center gap-6 text-sm text-gray-600">
        <span>Home {pct(prediction.home_win_prob)}</span>
        {prediction.draw_prob !== null && <span>Draw {pct(prediction.draw_prob)}</span>}
        <span>Away {pct(prediction.away_win_prob)}</span>
      </div>

      {explanation && (
        <div className="mt-6 rounded border border-gray-100 bg-gray-50 p-4">
          <p className="mb-2 text-xs font-semibold text-gray-700">Why this prediction</p>
          <ul className="space-y-1 text-sm">
            {explanation.factors.map((factor) => (
              <li key={factor.name} className="flex justify-between">
                <span className="text-gray-600">{factor.label}</span>
                <span className={factor.relative_influence_pct >= 0 ? "text-green-700" : "text-red-700"}>
                  {signedPct(factor.relative_influence_pct)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-6 rounded border border-gray-100 bg-gray-50 p-4">
        <p className="mb-2 text-xs font-semibold text-gray-700">Monte Carlo simulation</p>
        <SimulationPanel gameId={id} />
      </div>

      <div className="mt-6 rounded border border-gray-100 bg-gray-50 p-4">
        <p className="mb-2 text-xs font-semibold text-gray-700">What-if</p>
        <WhatIfPanel gameId={id} />
      </div>

      {context && (
        <div className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-3">
          <RecentFormList title={`${prediction.home_team.name} — last 10`} results={context.home_recent_form} />
          <RecentFormList title={`${prediction.away_team.name} — last 10`} results={context.away_recent_form} />
          <RecentFormList title="Head-to-head" results={context.head_to_head} />
        </div>
      )}

      <p className="mt-6 text-xs text-gray-400">
        MatchIQ doesn't have lineup, injury, xG, or possession data, so those aren't shown here rather than being
        estimated or faked.
      </p>
    </div>
  );
}
