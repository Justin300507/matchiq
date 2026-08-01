import { useState } from "react";
import { GameList } from "./components/GameList";

export default function App() {
  const [sport, setSport] = useState<"nba" | "soccer">("nba");

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-2xl font-bold">MatchIQ</h1>
      <div className="mt-4 flex gap-2">
        <button
          className={`rounded px-3 py-1 ${sport === "nba" ? "bg-blue-600 text-white" : "bg-gray-100"}`}
          onClick={() => setSport("nba")}
        >
          NBA
        </button>
        <button
          className={`rounded px-3 py-1 ${sport === "soccer" ? "bg-blue-600 text-white" : "bg-gray-100"}`}
          onClick={() => setSport("soccer")}
        >
          Soccer
        </button>
      </div>
      <div className="mt-6">
        <GameList sport={sport} />
      </div>
    </div>
  );
}
