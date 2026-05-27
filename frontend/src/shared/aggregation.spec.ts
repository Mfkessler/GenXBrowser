import { describe, expect, it } from 'vitest';

import { mean, median } from './aggregation';

describe('aggregation helpers', () => {
  it('computes the arithmetic mean for two values', () => {
    expect(mean([1.613, 2.963])).toBeCloseTo(2.288, 6);
  });

  it('computes the arithmetic mean for a single value', () => {
    expect(mean([1.613])).toBeCloseTo(1.613, 6);
  });

  it('computes the median for even-length arrays', () => {
    expect(median([4, 1, 2, 3])).toBe(2.5);
  });
});