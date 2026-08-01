import type { PredictionOut } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export async function fetchUpcomingPredictions(sport: "nba" | "soccer"): Promise<PredictionOut[]> {
  const response = await fetch(`${API_BASE_URL}/predictions/upcoming?sport=${sport}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch predictions: ${response.status}`);
  }
  return response.json();
}
