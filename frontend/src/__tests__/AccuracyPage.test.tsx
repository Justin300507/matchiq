import "@testing-library/jest-dom";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccuracyPage } from "../pages/AccuracyPage";
import * as api from "../api";
import type { BacktestOut } from "../types";

const footballResult: BacktestOut = {
  sport: "football", predictions_evaluated: 200, model_accuracy: 0.586, model_log_loss: 0.65,
  model_brier_score: 0.23, baseline_accuracy: 0.53, baseline_log_loss: 15.2, baseline_brier_score: 0.47,
  labels: ["H", "D", "A"], confusion_matrix: [[50, 10, 5], [8, 20, 7], [12, 9, 40]], roc_auc: 0.72,
  reliability_bins: [{ bin_start: 0.8, bin_end: 0.9, avg_confidence: 0.85, observed_accuracy: 0.8, count: 20 }],
};

describe("AccuracyPage", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders backtest metrics, confusion matrix, and reliability bins once loaded", async () => {
    vi.spyOn(api, "fetchAccuracy").mockResolvedValue(footballResult);

    render(<MemoryRouter><AccuracyPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("58.6%")).toBeInTheDocument());
    expect(screen.getByText("53.0%")).toBeInTheDocument();
    expect(screen.getByText("0.720")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
    expect(screen.getByText(/80% actual · n=20/)).toBeInTheDocument();
    // Rendered with a CSS `capitalize` class, so the DOM text itself is lowercase.
    expect(screen.getByText("football")).toBeInTheDocument();
  });

  it("shows Unavailable rather than a fake ROC AUC when it's undefined", async () => {
    vi.spyOn(api, "fetchAccuracy").mockResolvedValue({
      ...footballResult, confusion_matrix: [], roc_auc: null, reliability_bins: [],
    });

    render(<MemoryRouter><AccuracyPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText("Unavailable")).toBeInTheDocument());
  });

  it("shows a friendly message when there is no trained model", async () => {
    vi.spyOn(api, "fetchAccuracy").mockRejectedValue(new Error("503"));

    render(<MemoryRouter><AccuracyPage /></MemoryRouter>);

    await waitFor(() => expect(screen.getByText(/no trained model available yet for football/i)).toBeInTheDocument());
  });
});
