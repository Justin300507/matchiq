const CONFIDENCE_STYLES: Record<"High" | "Medium" | "Low", string> = {
  High: "bg-green-100 text-green-800",
  Medium: "bg-yellow-100 text-yellow-800",
  Low: "bg-red-100 text-red-800",
};

export function ConfidenceBadge({ confidence }: { confidence: "High" | "Medium" | "Low" }) {
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${CONFIDENCE_STYLES[confidence]}`}>
      {confidence} confidence
    </span>
  );
}
