import { useState } from "react";
import { GameList } from "../components/GameList";

interface Tab {
  label: string;
  sport: "nba" | "soccer";
  league?: string;
}

const TABS: Tab[] = [
  { label: "NBA", sport: "nba" },
  { label: "EPL", sport: "soccer", league: "EPL" },
  { label: "La Liga", sport: "soccer", league: "La Liga" },
  { label: "Serie A", sport: "soccer", league: "Serie A" },
  { label: "Bundesliga", sport: "soccer", league: "Bundesliga" },
  { label: "Ligue 1", sport: "soccer", league: "Ligue 1" },
  { label: "Champions League", sport: "soccer", league: "Champions League" },
];

export function HomePage() {
  const [activeTab, setActiveTab] = useState<Tab>(TABS[0]);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.label}
            className={`rounded px-3 py-1 ${activeTab.label === tab.label ? "bg-blue-600 text-white" : "bg-gray-100"}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="mt-6">
        <GameList sport={activeTab.sport} league={activeTab.league} />
      </div>
    </div>
  );
}
