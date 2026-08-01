export interface TeamOut {
  id: number;
  name: string;
  league: string;
}

export interface PredictionOut {
  game_id: number;
  sport: "nba" | "soccer";
  league: string;
  date: string;
  home_team: TeamOut;
  away_team: TeamOut;
  home_win_prob: number;
  draw_prob: number | null;
  away_win_prob: number;
  predicted_home_score: number;
  predicted_away_score: number;
}

export interface ExplanationFactorOut {
  name: string;
  label: string;
  relative_influence_pct: number;
}

export interface ExplanationOut {
  game_id: number;
  factors: ExplanationFactorOut[];
  model_confidence: "High" | "Medium" | "Low";
}
