import "@testing-library/jest-dom";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "../components/ChatPanel";
import * as api from "../api";

describe("ChatPanel", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a validation message instead of fetching when the question is blank", () => {
    const spy = vi.spyOn(api, "askAnalyst");

    render(<ChatPanel sport="nba" />);
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByText(/type a question first/i)).toBeInTheDocument();
  });

  it("asks the analyst and shows the answer", async () => {
    const spy = vi.spyOn(api, "askAnalyst").mockResolvedValue({
      answer: "The Lakers vs Celtics match has the highest home win probability.",
    });

    render(<ChatPanel sport="nba" />);
    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), {
      target: { value: "Which match is most confident?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByText(/highest home win probability/i)).toBeInTheDocument());
    expect(spy).toHaveBeenCalledWith("nba", undefined, "Which match is most confident?");
  });

  it("shows a not-configured message on a 503 response", async () => {
    vi.spyOn(api, "askAnalyst").mockRejectedValue(new api.ApiError("Failed to get an answer: 503", 503));

    render(<ChatPanel sport="soccer" league="EPL" />);
    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Any picks?" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByText(/isn't configured/i)).toBeInTheDocument());
  });

  it("shows a generic error message on other failures", async () => {
    vi.spyOn(api, "askAnalyst").mockRejectedValue(new Error("boom"));

    render(<ChatPanel sport="nba" />);
    fireEvent.change(screen.getByPlaceholderText(/ask a question/i), { target: { value: "Any picks?" } });
    fireEvent.click(screen.getByRole("button", { name: /ask/i }));

    await waitFor(() => expect(screen.getByText(/couldn't get an answer/i)).toBeInTheDocument());
  });
});
