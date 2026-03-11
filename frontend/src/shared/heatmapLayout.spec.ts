import { describe, expect, it } from 'vitest';

import { getHeatmapCardMinHeight, getHeatmapGridTemplate } from './heatmapLayout';

describe('heatmap layout helpers', () => {
  it('uses the full width for a single heatmap', () => {
    expect(getHeatmapGridTemplate(1)).toBe('minmax(0, 1fr)');
  });

  it('switches to an auto-fit grid for multiple heatmaps', () => {
    expect(getHeatmapGridTemplate(2)).toBe('repeat(auto-fit, minmax(min(100%, 30rem), 1fr))');
  });

  it('keeps two heatmaps flexible but gives larger galleries a minimum card height', () => {
    expect(getHeatmapCardMinHeight(2)).toBe('0');
    expect(getHeatmapCardMinHeight(3)).toBe('28rem');
  });
});