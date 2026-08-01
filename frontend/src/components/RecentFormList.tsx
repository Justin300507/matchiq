import type { RecentResultOut } from "../types";

const RESULT_STYLES: Record<RecentResultOut["result"], string> = {
  W: "bg-green-100 text-green-800",
  D: "bg-gray-100 text-gray-800",
  L: "bg-red-100 text-red-800",
};

export function RecentFormList({ title, results }: { title: string; results: RecentResultOut[] }) {
  if (results.length === 0) {
    return (
      <div>
        <p className="text-xs font-semibold text-gray-700">{title}</p>
        <p className="text-sm text-gray-400">No tracked history yet.</p>
      </div>
    );
  }

  return (
    <div>
      <p className="mb-1 text-xs font-semibold text-gray-700">{title}</p>
      <ul className="space-y-1 text-sm">
        {results.map((r) => (
          <li key={`${r.date}-${r.opponent_name}`} className="flex items-center justify-between">
            <span className={`mr-2 rounded px-1.5 text-xs font-medium ${RESULT_STYLES[r.result]}`}>{r.result}</span>
            <span className="flex-1 text-gray-600">
              {r.is_home ? "vs" : "@"} {r.opponent_name}
            </span>
            <span className="text-gray-500">{r.team_score}-{r.opponent_score}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
