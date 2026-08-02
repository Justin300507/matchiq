import { useState } from "react";
import { ApiError, askAnalyst } from "../api";

export function ChatPanel({ sport, league }: { sport: "nba" | "football"; league?: string }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  function handleAsk() {
    if (!question.trim()) {
      setError("Type a question first.");
      return;
    }
    setIsLoading(true);
    setError(null);
    setAnswer(null);
    askAnalyst(sport, league, question)
      .then((result) => setAnswer(result.answer))
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 503) {
          setError("The AI analyst isn't configured on this deployment yet.");
        } else {
          setError("Couldn't get an answer from the analyst. Please try again later.");
        }
      })
      .finally(() => setIsLoading(false));
  }

  return (
    <div>
      <p className="mb-3 text-xs text-gray-500">
        Ask about the upcoming matches currently shown for this league — e.g. "which match has the highest
        confidence?" or "which team is favored to win by the most?". The analyst only sees MatchIQ's real
        predictions; it doesn't have injury, weather, lineup, or odds data.
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <input
          type="text"
          placeholder="Ask a question about these matches..."
          className="min-w-[260px] flex-1 rounded border border-gray-300 px-2 py-1 text-sm"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
        />
        <button
          type="button"
          onClick={handleAsk}
          disabled={isLoading}
          className="rounded bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {isLoading ? "Asking..." : "Ask"}
        </button>
      </div>

      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      {answer && <p className="mt-3 whitespace-pre-wrap text-sm text-gray-700">{answer}</p>}
    </div>
  );
}
