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
  model_confidence: "High" | "Medium" | "Low";
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

export interface ScorelineOut {
  home_score: number;
  away_score: number;
  frequency_pct: number;
}

export interface SimulationOut {
  game_id: number;
  home_win_pct: number;
  draw_pct: number | null;
  away_win_pct: number;
  top_scorelines: ScorelineOut[];
  n_simulations: number;
}

export interface RecentResultOut {
  date: string;
  opponent_name: string;
  is_home: boolean;
  team_score: number;
  opponent_score: number;
  result: "W" | "D" | "L";
}

export interface MatchContextOut {
  game_id: number;
  home_recent_form: RecentResultOut[];
  away_recent_form: RecentResultOut[];
  head_to_head: RecentResultOut[];
}

export interface PredictionSummaryOut {
  home_win_prob: number;
  draw_prob: number | null;
  away_win_prob: number;
  predicted_home_score: number;
  predicted_away_score: number;
  model_confidence: "High" | "Medium" | "Low";
}

export interface WhatIfOut {
  game_id: number;
  overrides_applied: Record<string, number>;
  original: PredictionSummaryOut;
  counterfactual: PredictionSummaryOut;
}

export interface ReliabilityBinOut {
  bin_start: number;
  bin_end: number;
  avg_confidence: number;
  observed_accuracy: number;
  count: number;
}

export interface BacktestOut {
  sport: string;
  predictions_evaluated: number;
  model_accuracy: number;
  model_log_loss: number;
  model_brier_score: number;
  baseline_accuracy: number;
  baseline_log_loss: number;
  baseline_brier_score: number;
  labels: string[];
  confusion_matrix: number[][];
  roc_auc: number | null;
  reliability_bins: ReliabilityBinOut[];
}

export interface TeamProfileOut {
  team_id: number;
  team_name: string;
  league: string;
  matches_played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for_avg: number;
  goals_against_avg: number;
  home_win_rate: number;
  away_win_rate: number;
  last5_form: string;
  elo_rating: number;
}

export interface ChatResponse {
  answer: string;
}
