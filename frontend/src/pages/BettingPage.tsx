import { useEffect, useState } from "react";
import { fetchUpcomingPredictions } from "../api";
import { LEAGUE_TABS, type LeagueTab } from "../leagueTabs";
import { combineLegs, edgePct, expectedValuePct, impliedProbability, kellyFraction } from "../lib/betting";
import type { PredictionOut } from "../types";

type Outcome = "home" | "draw" | "away";

interface Leg {
  key: string;
  matchLabel: string;
  odds: number;
  modelProb: number;
}

function outcomeLabel(outcome: Outcome): string {
  if (outcome === "home") return "Home";
  if (outcome === "away") return "Away";
  return "Draw";
}

function outcomeProb(prediction: PredictionOut, outcome: Outcome): number {
  if (outcome === "home") return prediction.home_win_prob;
  if (outcome === "away") return prediction.away_win_prob;
  return prediction.draw_prob ?? 0;
}

export function BettingPage() {
  const [activeTab, setActiveTab] = useState<LeagueTab>(LEAGUE_TABS[0]);
  const [matches, setMatches] = useState<PredictionOut[]>([]);
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const [outcome, setOutcome] = useState<Outcome>("home");
  const [oddsInput, setOddsInput] = useState("2.00");
  const [legs, setLegs] = useState<Leg[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setOutcome("home");
    fetchUpcomingPredictions(activeTab.sport, activeTab.league)
      .then((data) => {
        setMatches(data);
        setSelectedGameId(data[0]?.game_id ?? null);
      })
      .catch(() => setMatches([]));
  }, [activeTab]);

  const selectedMatch = matches.find((m) => m.game_id === selectedGameId) ?? null;

  function handleAddLeg() {
    const odds = Number(oddsInput);
    if (!selectedMatch) {
      setError("Pick a match first.");
      return;
    }
    if (!Number.isFinite(odds) || odds <= 1) {
      setError("Enter decimal odds greater than 1.00.");
      return;
    }
    if (outcome === "draw" && selectedMatch.draw_prob === null) {
      setError("This sport has no draw outcome.");
      return;
    }
    setError(null);
    setLegs((prev) => [
      ...prev,
      {
        key: `${selectedMatch.game_id}-${outcome}-${prev.length}-${Date.now()}`,
        matchLabel: `${selectedMatch.home_team.name} vs ${selectedMatch.away_team.name} (${outcomeLabel(outcome)})`,
        odds,
        modelProb: outcomeProb(selectedMatch, outcome),
      },
    ]);
  }

  function handleRemoveLeg(key: string) {
    setLegs((prev) => prev.filter((leg) => leg.key !== key));
  }

  const combined = legs.length > 0 ? combineLegs(legs.map((leg) => ({ modelProb: leg.modelProb, decimalOdds: leg.odds }))) : null;
  const combinedImplied = combined ? impliedProbability(combined.combinedOdds) : 0;

  return (
    <div>
      <h1 className="text-xl font-bold">Betting Tools</h1>
      <p className="mt-2 max-w-2xl text-sm text-gray-600">
        This page compares MatchIQ's real model probabilities against odds you enter yourself — MatchIQ doesn't
        fetch, store, or invent bookmaker odds. Nothing here is a prediction of profit or a recommendation to bet;
        it's simply where our model's probability estimate differs from the odds you supply. The full-Kelly stake
        shown is the theoretical aggressive maximum — most practitioners bet a fraction of it.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {LEAGUE_TABS.map((tab) => (
          <button
            key={tab.label}
            className={`rounded px-3 py-1 text-sm ${activeTab.label === tab.label ? "bg-blue-600 text-white" : "bg-gray-100"}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="mt-4 rounded border border-gray-100 bg-gray-50 p-4">
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            Match
            <select
              className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
              value={selectedGameId ?? ""}
              onChange={(e) => setSelectedGameId(Number(e.target.value))}
            >
              {matches.map((m) => (
                <option key={m.game_id} value={m.game_id}>
                  {m.home_team.name} vs {m.away_team.name}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Outcome
            <select
              className="ml-2 rounded border border-gray-300 px-2 py-1 text-sm"
              value={outcome}
              onChange={(e) => setOutcome(e.target.value as Outcome)}
            >
              <option value="home">Home</option>
              {activeTab.sport === "soccer" && <option value="draw">Draw</option>}
              <option value="away">Away</option>
            </select>
          </label>
          <label className="text-sm">
            Decimal odds
            <input
              type="number"
              step="0.01"
              min="1.01"
              className="ml-2 w-24 rounded border border-gray-300 px-2 py-1 text-sm"
              value={oddsInput}
              onChange={(e) => setOddsInput(e.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={handleAddLeg}
            className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700"
          >
            Add to bet slip
          </button>
        </div>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {legs.length > 0 && (
        <div className="mt-4 rounded border border-gray-100 bg-gray-50 p-4">
          <p className="mb-2 text-xs font-semibold text-gray-700">
            Bet slip ({legs.length} {legs.length === 1 ? "leg" : "legs — parlay"})
          </p>
          <ul className="space-y-2 text-sm">
            {legs.map((leg) => {
              const implied = impliedProbability(leg.odds);
              return (
                <li key={leg.key} className="flex items-center justify-between rounded bg-white p-2">
                  <div>
                    <p className="font-medium">{leg.matchLabel}</p>
                    <p className="text-xs text-gray-500">
                      Model {Math.round(leg.modelProb * 100)}% · Implied {Math.round(implied * 100)}% · Odds{" "}
                      {leg.odds.toFixed(2)}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleRemoveLeg(leg.key)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    Remove
                  </button>
                </li>
              );
            })}
          </ul>

          {combined && (
            <div className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
              <div>
                <p className="text-xs text-gray-500">Model probability</p>
                <p className="font-semibold">{(combined.combinedProb * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Implied probability</p>
                <p className="font-semibold">{(combinedImplied * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Edge (model − implied)</p>
                <p
                  className={`font-semibold ${
                    edgePct(combined.combinedProb, combinedImplied) >= 0 ? "text-green-700" : "text-red-700"
                  }`}
                >
                  {edgePct(combined.combinedProb, combinedImplied).toFixed(1)} pts
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Expected value</p>
                <p
                  className={`font-semibold ${
                    expectedValuePct(combined.combinedProb, combined.combinedOdds) >= 0
                      ? "text-green-700"
                      : "text-red-700"
                  }`}
                >
                  {expectedValuePct(combined.combinedProb, combined.combinedOdds).toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Combined odds</p>
                <p className="font-semibold">{combined.combinedOdds.toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500">Full Kelly stake</p>
                <p className="font-semibold">
                  {(kellyFraction(combined.combinedProb, combined.combinedOdds) * 100).toFixed(1)}% of bankroll
                </p>
              </div>
            </div>
          )}
          {legs.length > 1 && (
            <p className="mt-3 text-xs text-gray-400">
              Combined probability assumes the selected matches are statistically independent of each other.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
