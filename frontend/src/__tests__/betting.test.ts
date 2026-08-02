import { describe, expect, it } from "vitest";
import { combineLegs, edgePct, expectedValuePct, impliedProbability, kellyFraction } from "../lib/betting";

describe("impliedProbability", () => {
  it("converts decimal odds to implied probability", () => {
    expect(impliedProbability(2.5)).toBeCloseTo(0.4, 5);
    expect(impliedProbability(2)).toBeCloseTo(0.5, 5);
  });
});

describe("edgePct", () => {
  it("returns the percentage-point gap between model and implied probability", () => {
    expect(edgePct(0.5, 0.4)).toBeCloseTo(10, 5);
    expect(edgePct(0.4, 0.5)).toBeCloseTo(-10, 5);
  });
});

describe("expectedValuePct", () => {
  it("computes EV per unit stake as a percentage", () => {
    // model thinks 50%, odds imply 40% (2.5) -> positive EV
    expect(expectedValuePct(0.5, 2.5)).toBeCloseTo(25, 5);
    // model agrees exactly with fair odds -> EV is 0
    expect(expectedValuePct(0.5, 2.0)).toBeCloseTo(0, 5);
  });
});

describe("kellyFraction", () => {
  it("computes the full-Kelly stake fraction for a positive edge", () => {
    // b=1.5, p=0.5, q=0.5 -> (1.5*0.5 - 0.5) / 1.5 = 0.1667
    expect(kellyFraction(0.5, 2.5)).toBeCloseTo(0.1667, 3);
  });

  it("clips at zero when there is no edge", () => {
    expect(kellyFraction(0.3, 2.0)).toBe(0);
  });
});

describe("combineLegs", () => {
  it("multiplies probabilities and odds across legs", () => {
    const result = combineLegs([
      { modelProb: 0.6, decimalOdds: 1.8 },
      { modelProb: 0.5, decimalOdds: 2.2 },
    ]);
    expect(result.combinedProb).toBeCloseTo(0.3, 5);
    expect(result.combinedOdds).toBeCloseTo(3.96, 5);
  });

  it("returns identity values for a single leg", () => {
    const result = combineLegs([{ modelProb: 0.6, decimalOdds: 1.8 }]);
    expect(result.combinedProb).toBeCloseTo(0.6, 5);
    expect(result.combinedOdds).toBeCloseTo(1.8, 5);
  });
});
