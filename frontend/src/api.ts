import type {
  BacktestOut,
  ChatResponse,
  ExplanationOut,
  MarketOddsOut,
  MatchContextOut,
  PredictionOut,
  SimulationOut,
  TeamProfileOut,
  WhatIfOut,
} from "./types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchUpcomingPredictions(sport: "nba" | "football", league?: string): Promise<PredictionOut[]> {
  const params = new URLSearchParams({ sport });
  if (league) {
    params.set("league", league);
  }
  const response = await fetch(`${API_BASE_URL}/predictions/upcoming?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch predictions: ${response.status}`);
  }
  return response.json();
}

export async function fetchPrediction(gameId: number): Promise<PredictionOut> {
  const response = await fetch(`${API_BASE_URL}/predictions/${gameId}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch prediction: ${response.status}`);
  }
  return response.json();
}

export async function fetchMatchContext(gameId: number): Promise<MatchContextOut> {
  const response = await fetch(`${API_BASE_URL}/predictions/${gameId}/context`);
  if (!response.ok) {
    throw new Error(`Failed to fetch match context: ${response.status}`);
  }
  return response.json();
}

export async function fetchExplanation(gameId: number): Promise<ExplanationOut> {
  const response = await fetch(`${API_BASE_URL}/predictions/${gameId}/explain`);
  if (!response.ok) {
    throw new Error(`Failed to fetch explanation: ${response.status}`);
  }
  return response.json();
}

export async function fetchSimulation(gameId: number): Promise<SimulationOut> {
  const response = await fetch(`${API_BASE_URL}/predictions/${gameId}/simulate`);
  if (!response.ok) {
    throw new Error(`Failed to fetch simulation: ${response.status}`);
  }
  return response.json();
}

export async function fetchWhatIf(gameId: number, overrides: Record<string, number>): Promise<WhatIfOut> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(overrides)) {
    params.set(key, String(value));
  }
  const response = await fetch(`${API_BASE_URL}/predictions/${gameId}/whatif?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch what-if simulation: ${response.status}`);
  }
  return response.json();
}

export async function fetchTeamProfile(teamId: number): Promise<TeamProfileOut> {
  const response = await fetch(`${API_BASE_URL}/teams/${teamId}/profile`);
  if (!response.ok) {
    throw new Error(`Failed to fetch team profile: ${response.status}`);
  }
  return response.json();
}

export async function fetchMarketOdds(gameId: number): Promise<MarketOddsOut> {
  const response = await fetch(`${API_BASE_URL}/predictions/${gameId}/market-odds`);
  if (!response.ok) {
    throw new Error(`Failed to fetch market odds: ${response.status}`);
  }
  return response.json();
}

export async function fetchAccuracy(sport: "nba" | "football"): Promise<BacktestOut> {
  const response = await fetch(`${API_BASE_URL}/accuracy?sport=${sport}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch accuracy: ${response.status}`);
  }
  return response.json();
}

export async function askAnalyst(sport: "nba" | "football", league: string | undefined, question: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sport, league: league ?? null, question }),
  });
  if (!response.ok) {
    throw new ApiError(`Failed to get an answer: ${response.status}`, response.status);
  }
  return response.json();
}
