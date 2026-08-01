import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TeamPage } from "../pages/TeamPage";
import * as api from "../api";
import type { TeamProfileOut } from "../types";

function renderAtTeam(teamId: number) {
  return render(
    <MemoryRouter initialEntries={[`/team/${teamId}`]}>
      <Routes>
        <Route path="/team/:teamId" element={<TeamPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("TeamPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading state before data arrives", () => {
    vi.spyOn(api, "fetchTeamProfile").mockReturnValue(new Promise(() => {}));
    renderAtTeam(7);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it("renders team name, record, and stats once loaded", async () => {
    const profile: TeamProfileOut = {
      team_id: 7, team_name: "Lakers", league: "NBA", matches_played: 10,
      wins: 6, draws: 0, losses: 4, goals_for_avg: 108.2, goals_against_avg: 104.5,
      home_win_rate: 0.7, away_win_rate: 0.5, last5_form: "WWLWL", elo_rating: 1550.2,
    };
    vi.spyOn(api, "fetchTeamProfile").mockResolvedValue(profile);

    renderAtTeam(7);

    await waitFor(() => expect(screen.getByText("Lakers")).toBeInTheDocument());
    expect(screen.getByText("1550")).toBeInTheDocument();
    expect(screen.getByText("WWLWL")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("shows an error message when the fetch fails", async () => {
    vi.spyOn(api, "fetchTeamProfile").mockRejectedValue(new Error("boom"));

    renderAtTeam(7);

    await waitFor(() => expect(screen.getByText(/couldn't load this team's profile/i)).toBeInTheDocument());
  });
});
