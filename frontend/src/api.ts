import type { PredictionOut } from "./types";

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
