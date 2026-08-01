import type { PredictionOut } from "../types";

function pct(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function GameCard({ prediction }: { prediction: PredictionOut }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4 shadow-sm">
      <div className="flex justify-between text-sm text-gray-500">
        <span>{prediction.league}</span>
        <span>{new Date(prediction.date).toLocaleDateString()}</span>
      </div>

      <div className="mt-2 flex items-center justify-between">
        <span className="font-semibold">{prediction.home_team.name}</span>
        <span className="text-lg font-bold">{Math.round(prediction.predicted_home_score)}</span>
      </div>
      <div className="mt-1 flex items-center justify-between">
        <span className="font-semibold">{prediction.away_team.name}</span>
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
    </div>
  );
}
