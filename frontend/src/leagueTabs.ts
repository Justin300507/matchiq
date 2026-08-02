export interface LeagueTab {
  label: string;
  sport: "nba" | "football";
  league?: string;
}

// NBA is temporarily removed from the tab list (kept in the backend and
// the sport union type so it's a one-line add-back, not a rebuild).
export const LEAGUE_TABS: LeagueTab[] = [
  { label: "EPL", sport: "football", league: "EPL" },
  { label: "La Liga", sport: "football", league: "La Liga" },
  { label: "Serie A", sport: "football", league: "Serie A" },
  { label: "Bundesliga", sport: "football", league: "Bundesliga" },
  { label: "Ligue 1", sport: "football", league: "Ligue 1" },
  { label: "Champions League", sport: "football", league: "Champions League" },
];
