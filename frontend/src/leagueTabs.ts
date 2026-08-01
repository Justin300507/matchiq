export interface LeagueTab {
  label: string;
  sport: "nba" | "soccer";
  league?: string;
}

export const LEAGUE_TABS: LeagueTab[] = [
  { label: "NBA", sport: "nba" },
  { label: "EPL", sport: "soccer", league: "EPL" },
  { label: "La Liga", sport: "soccer", league: "La Liga" },
  { label: "Serie A", sport: "soccer", league: "Serie A" },
  { label: "Bundesliga", sport: "soccer", league: "Bundesliga" },
  { label: "Ligue 1", sport: "soccer", league: "Ligue 1" },
  { label: "Champions League", sport: "soccer", league: "Champions League" },
];
