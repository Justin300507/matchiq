import { Link, Route, Routes } from "react-router-dom";
import { AccuracyPage } from "./pages/AccuracyPage";
import { HomePage } from "./pages/HomePage";
import { MatchPage } from "./pages/MatchPage";
import { TeamPage } from "./pages/TeamPage";

export default function App() {
  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex items-center gap-6">
        <Link to="/" className="text-2xl font-bold">MatchIQ</Link>
        <nav className="flex gap-4 text-sm text-gray-600">
          <Link to="/" className="hover:underline">Predictions</Link>
          <Link to="/accuracy" className="hover:underline">Accuracy</Link>
        </nav>
      </div>

      <div className="mt-6">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/team/:teamId" element={<TeamPage />} />
          <Route path="/match/:gameId" element={<MatchPage />} />
          <Route path="/accuracy" element={<AccuracyPage />} />
        </Routes>
      </div>
    </div>
  );
}
