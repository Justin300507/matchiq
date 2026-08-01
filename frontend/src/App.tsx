import { Link, Route, Routes } from "react-router-dom";
import { HomePage } from "./pages/HomePage";
import { TeamPage } from "./pages/TeamPage";

export default function App() {
  return (
    <div className="mx-auto max-w-6xl p-6">
      <div className="flex items-center gap-4">
        <Link to="/" className="text-2xl font-bold">MatchIQ</Link>
      </div>

      <div className="mt-6">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/team/:teamId" element={<TeamPage />} />
        </Routes>
      </div>
    </div>
  );
}
