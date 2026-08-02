import { useEffect, useState } from "react";
import { fetchSimulation } from "../api";
import type { SimulationOut } from "../types";

function bar(pct: number, colorClass: string) {
  return (
    <div className="h-3 w-full overflow-hidden rounded bg-gray-200">
      <div className={`h-full ${colorClass}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function SimulationPanel({ gameId }: { gameId: number }) {
  const [simulation, setSimulation] = useState<SimulationOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setSimulation(null);
    setError(null);
    fetchSimulation(gameId)
      .then(setSimulation)
      .catch(() => setError("Couldn't run the simulation. Please try again later."));
  }, [gameId]);

  if (error) {
    return <p className="text-sm text-red-600">{error}</p>;
  }

  if (simulation === null) {
    return <p className="text-sm text-gray-500">Running {10000} Monte Carlo simulations...</p>;
  }

  return (
    <div>
      <p className="mb-3 text-xs text-gray-500">
        Based on {simulation.n_simulations.toLocaleString()} simulated outcomes, sampling score variance from the model's own historical prediction error.
      </p>

      <div className="space-y-2 text-sm">
        <div>
          <div className="flex justify-between"><span>Home win</span><span>{simulation.home_win_pct.toFixed(1)}%</span></div>
          {bar(simulation.home_win_pct, "bg-blue-500")}
        </div>
        {simulation.draw_pct !== null && (
          <div>
            <div className="flex justify-between"><span>Draw</span><span>{simulation.draw_pct.toFixed(1)}%</span></div>
            {bar(simulation.draw_pct, "bg-gray-400")}
          </div>
        )}
        <div>
          <div className="flex justify-between"><span>Away win</span><span>{simulation.away_win_pct.toFixed(1)}%</span></div>
          {bar(simulation.away_win_pct, "bg-red-500")}
        </div>
      </div>

      {simulation.top_scorelines.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 text-xs font-semibold text-gray-700">Most likely scorelines</p>
          <ul className="text-sm text-gray-600">
            {simulation.top_scorelines.map((s) => (
              <li key={`${s.home_score}-${s.away_score}`} className="flex justify-between">
                <span>{s.home_score} - {s.away_score}</span>
                <span>{s.frequency_pct.toFixed(1)}%</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
