import { describe, expect, it } from 'vitest';

import { getHeatmapCardMinHeight, getHeatmapGridTemplate } from './heatmapLayout';

describe('heatmap layout helpers', () => {
  it('uses the full width for a single heatmap', () => {
    expect(getHeatmapGridTemplate(1)).toBe('minmax(0, 1fr)');
  });

  it('switches to an auto-fit grid for multiple heatmaps', () => {
    expect(getHeatmapGridTemplate(2)).toBe('repeat(auto-fit, minmax(min(100%, 36rem), 1fr))');
  });

  it('keeps heatmap cards within viewport-aware size constraints', () => {
    expect(getHeatmapCardMinHeight(2)).toBe('clamp(30rem, 68vh, 46rem)');
    expect(getHeatmapCardMinHeight(3)).toBe('34rem');
  });
});
