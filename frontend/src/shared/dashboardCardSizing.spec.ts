import { describe, expect, it } from "vitest";

import { getMirroredCardStyle, measureOccupiedHeight, readCardBoxSize, subtractDynamicRegionsHeight } from "./dashboardCardSizing";

describe("dashboard card sizing helpers", () => {
  it("rounds positive card dimensions from DOM rects", () => {
    expect(readCardBoxSize({ width: 321.4, height: 218.6 })).toEqual({
      width: 321,
      height: 219,
    });
  });

  it("ignores empty card measurements", () => {
    expect(readCardBoxSize({ width: 0, height: 218.6 })).toBeNull();
    expect(readCardBoxSize({ width: 321.4, height: 0 })).toBeNull();
  });

  it("creates an exact mirrored height style for analysis cards", () => {
    expect(getMirroredCardStyle({ width: 321, height: 219 })).toEqual({
      minHeight: "219px",
      height: "219px",
    });
  });

  it("subtracts dynamic (filter-chip) region heights from the card's total height", () => {
    expect(subtractDynamicRegionsHeight(300, [40, 20])).toBe(240);
  });

  it("never returns a negative core height", () => {
    expect(subtractDynamicRegionsHeight(50, [100])).toBe(0);
  });

  it("ignores appended filter-chip growth so mirrored analysis cards stay stable", () => {
    // Card starts at 300px with no chips; appending a chip row grows the card to 340px,
    // but the dynamic region itself (chip row incl. margins) also measures 40px — so the
    // "core" structural height mirrored onto Analysis cards must stay at 300px both times.
    expect(subtractDynamicRegionsHeight(300, [])).toBe(300);
    expect(subtractDynamicRegionsHeight(340, [40])).toBe(300);
  });

  it("measures an element's full occupied height (border-box height + vertical margins)", () => {
    expect(measureOccupiedHeight({ height: 24 }, { marginTop: "8px", marginBottom: "8px" })).toBe(40);
    expect(measureOccupiedHeight({ height: 24 }, { marginTop: "", marginBottom: "" })).toBe(24);
  });
});