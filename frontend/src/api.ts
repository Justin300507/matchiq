import type { ExplanationOut, MatchContextOut, PredictionOut, SimulationOut, TeamProfileOut } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchUpcomingPredictions(sport: "nba" | "soccer", league?: string): Promise<PredictionOut[]> {
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

export async function fetchTeamProfile(teamId: number): Promise<TeamProfileOut> {
  const response = await fetch(`${API_BASE_URL}/teams/${teamId}/profile`);
  if (!response.ok) {
    throw new Error(`Failed to fetch team profile: ${response.status}`);
  }
  return response.json();
}
