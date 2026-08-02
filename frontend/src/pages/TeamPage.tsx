import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchTeamProfile } from "../api";
import type { TeamProfileOut } from "../types";

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-gray-200 p-3 text-center">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

export function TeamPage() {
  const { teamId } = useParams<{ teamId: string }>();
  const [profile, setProfile] = useState<TeamProfileOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setProfile(null);
    setError(null);
    fetchTeamProfile(Number(teamId))
      .then(setProfile)
      .catch(() => setError("Couldn't load this team's profile. Please try again later."));
  }, [teamId]);

  if (error) {
    return <p className="text-red-600">{error}</p>;
  }

  if (profile === null) {
    return <p className="text-gray-500">Loading team profile...</p>;
  }

  return (
    <div>
      <Link to="/" className="text-sm text-blue-600 hover:underline">&larr; Back</Link>
      <h2 className="mt-2 text-xl font-bold">{profile.team_name}</h2>
      <p className="text-sm text-gray-500">{profile.league}</p>

      <p className="mt-4 text-sm text-gray-600">
        Record: {profile.wins}-{profile.draws}-{profile.losses} over {profile.matches_played} tracked matches.
        {profile.last5_form && <> Last 5: <span className="font-mono">{profile.last5_form}</span></>}
      </p>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Elo power rating" value={profile.elo_rating.toFixed(0)} />
        <StatCard label="Avg scored" value={profile.goals_for_avg.toFixed(1)} />
        <StatCard label="Avg conceded" value={profile.goals_against_avg.toFixed(1)} />
        <StatCard label="Home win rate" value={`${Math.round(profile.home_win_rate * 100)}%`} />
        <StatCard label="Away win rate" value={`${Math.round(profile.away_win_rate * 100)}%`} />
      </div>

      <p className="mt-6 text-xs text-gray-400">
        Elo power rating is computed from this team's actual match history (standard Elo, starting at 1500). Stats
        shown are all derived from real results — MatchIQ doesn't have injury, tactical, or pressing-style data, so
        those metrics aren't shown here rather than being estimated.
      </p>
    </div>
  );
}
