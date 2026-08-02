import { useEffect, useState } from "react";
import { fetchUpcomingPredictions } from "../api";
import type { PredictionOut } from "../types";
import { GameCard } from "./GameCard";

export function GameList({ sport, league }: { sport: "nba" | "football"; league?: string }) {
  const [predictions, setPredictions] = useState<PredictionOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPredictions(null);
    setError(null);
    fetchUpcomingPredictions(sport, league)
      .then(setPredictions)
      .catch(() => setError("Couldn't load predictions. Please try again later."));
  }, [sport, league]);

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (predictions === null) {
    return <p className="text-gray-500">Loading predictions...</p>;
  }

  if (predictions.length === 0) {
    return <p className="text-gray-500">No upcoming games right now.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {predictions.map((prediction) => (
        <GameCard key={prediction.game_id} prediction={prediction} />
      ))}
    </div>
  );
}
