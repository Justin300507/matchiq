import { useState } from "react";
import { ChatPanel } from "../components/ChatPanel";
import { GameList } from "../components/GameList";
import { LEAGUE_TABS, type LeagueTab } from "../leagueTabs";

export function HomePage() {
  const [activeTab, setActiveTab] = useState<LeagueTab>(LEAGUE_TABS[0]);

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        {LEAGUE_TABS.map((tab) => (
          <button
            key={tab.label}
            className={`rounded px-3 py-1 ${activeTab.label === tab.label ? "bg-blue-600 text-white" : "bg-gray-100"}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="mt-6 rounded border border-gray-100 bg-gray-50 p-4">
        <p className="mb-2 text-xs font-semibold text-gray-700">Ask the analyst</p>
        <ChatPanel sport={activeTab.sport} league={activeTab.league} />
      </div>

      <div className="mt-6">
        <GameList sport={activeTab.sport} league={activeTab.league} />
      </div>
    </div>
  );
}
