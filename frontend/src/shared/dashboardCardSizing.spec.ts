import { describe, expect, it } from "vitest";

import { getMirroredCardStyle, readCardBoxSize } from "./dashboardCardSizing";

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
});