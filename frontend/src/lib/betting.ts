// Pure math only — no odds are fetched, stored, or invented here. The
// caller supplies decimal odds (from wherever they got them); every
// probability compared against them is MatchIQ's own real model output.

export interface BetLeg {
  modelProb: number;
  decimalOdds: number;
}

export function impliedProbability(decimalOdds: number): number {
  return 1 / decimalOdds;
}

export function edgePct(modelProb: number, impliedProb: number): number {
  return (modelProb - impliedProb) * 100;
}

export function expectedValuePct(modelProb: number, decimalOdds: number): number {
  return (modelProb * decimalOdds - 1) * 100;
}

// Full-Kelly stake as a fraction of bankroll. Clipped at 0 — a negative
// edge never suggests a stake, only that the model disagrees with the odds.
export function kellyFraction(modelProb: number, decimalOdds: number): number {
  const b = decimalOdds - 1;
  if (b <= 0) return 0;
  const q = 1 - modelProb;
  const f = (b * modelProb - q) / b;
  return Math.max(0, f);
}

// Combines legs as a single all-must-win bet (a parlay when there's more
// than one leg). This assumes the legs are statistically independent —
// true for unrelated matches, not verified beyond that.
export function combineLegs(legs: BetLeg[]): { combinedProb: number; combinedOdds: number } {
  const combinedProb = legs.reduce((acc, leg) => acc * leg.modelProb, 1);
  const combinedOdds = legs.reduce((acc, leg) => acc * leg.decimalOdds, 1);
  return { combinedProb, combinedOdds };
}
