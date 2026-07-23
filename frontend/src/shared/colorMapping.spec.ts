import { describe, expect, it } from 'vitest';
import * as d3 from 'd3';

import {
  createVisibleColorMapping,
  getListMetadataColor,
  getListMetadataKey,
  normalizeMetadataList,
  SharedColorRegistry,
} from './colorMapping';
import { getCategoricalColors } from './Colorscales';

describe('list metadata color mapping', () => {
  it('normalizes list values alphabetically', () => {
    expect(normalizeMetadataList(['GO:0008150', 'GO:0005634'])).toEqual([
      'GO:0005634',
      'GO:0008150',
    ]);
    expect(getListMetadataKey(['GO:0008150', 'GO:0005634'])).toBe('GO:0005634|GO:0008150');
  });

  it('assigns identical colors regardless of input order', () => {
    const first = getListMetadataColor(['GO:1', 'GO:2']);
    const second = getListMetadataColor(['GO:2', 'GO:1']);

    expect(first).toBe(second);
    expect(first).toMatch(/^#[0-9a-f]{6}$/);
  });

  it('creates distinct array mappings from normalized keys', () => {
    const mapping = createVisibleColorMapping('go_terms', 'array', [
      ['GO:2', 'GO:1'],
      ['GO:1', 'GO:2'],
      ['GO:3'],
    ]);

    expect(mapping['GO:1|GO:2']).toMatch(/^#[0-9a-f]{6}$/);
    expect(mapping['GO:1|GO:2']).not.toBe(mapping['GO:3']);
  });

  it('keeps overlapping list sets stable through the shared registry', () => {
    const registry = new SharedColorRegistry();
    registry.registerValues('go_terms', 'array', [['GO:2', 'GO:1']]);
    const first = registry.getMapping('go_terms')?.['GO:1|GO:2'];

    registry.registerValues('go_terms', 'array', [['GO:1', 'GO:2'], ['GO:4']]);
    const second = registry.getMapping('go_terms')?.['GO:1|GO:2'];

    expect(first).toBe(second);
  });

  it('keeps all 19 categorical colors distinct across incremental heatmap registrations', () => {
    const registry = new SharedColorRegistry();
    registry.registerValues('condition', 'text', ['adult', 'breakfruit']);
    const initialAdultColor = registry.getMapping('condition')?.adult;

    registry.registerValues(
      'condition',
      'text',
      Array.from({ length: 19 }, (_, index) => `condition-${index}`),
    );
    const mapping = registry.getMapping('condition')!;
    const colors = Object.values(mapping).filter((color): color is string => typeof color === 'string');

    expect(mapping.adult).toBe(initialAdultColor);
    expect(colors).toHaveLength(21);
    expect(new Set(colors)).toHaveLength(21);
  });

  it('keeps each color in an optimized 31-category palette perceptually separated', () => {
    const colors = getCategoricalColors(31);
    const distances = colors.flatMap((color, index) =>
      colors.slice(index + 1).map((other) => {
        const first = d3.lab(color);
        const second = d3.lab(other);
        return Math.hypot(first.l - second.l, first.a - second.a, first.b - second.b);
      }),
    );
    const whiteContrast = (color: string) => {
      const { r, g, b } = d3.rgb(color);
      const luminance = [r, g, b]
        .map((channel) => {
          const normalized = channel / 255;
          return normalized <= 0.04045
            ? normalized / 12.92
            : ((normalized + 0.055) / 1.055) ** 2.4;
        })
        .reduce((total, channel, index) => total + channel * [0.2126, 0.7152, 0.0722][index], 0);
      return 1.05 / (luminance + 0.05);
    };

    expect(new Set(colors)).toHaveLength(31);
    expect(Math.min(...distances)).toBeGreaterThan(26);
    expect(Math.min(...colors.map(whiteContrast))).toBeGreaterThanOrEqual(3);
  });

  it('rebuilds categorical mappings deterministically after all heatmaps register', () => {
    const firstRegistry = new SharedColorRegistry();
    firstRegistry.registerValues('default_trait', 'text', ['seed', 'flower']);
    firstRegistry.registerValues('default_trait', 'text', ['adult', 'root']);
    firstRegistry.refreshMappings();

    const secondRegistry = new SharedColorRegistry();
    secondRegistry.registerValues('default_trait', 'text', ['adult', 'root']);
    secondRegistry.registerValues('default_trait', 'text', ['seed', 'flower']);
    secondRegistry.refreshMappings();

    expect(firstRegistry.getMapping('default_trait')).toEqual(secondRegistry.getMapping('default_trait'));
  });

  it('preserves numeric values in the shared registry for continuous color scales', () => {
    const registry = new SharedColorRegistry();
    registry.registerValues('assigned', 'bigint', [10, 20, 30]);

    const mapping = registry.getMapping('assigned');

    expect(mapping?.getColor?.(20)).not.toBe('#eeeeee');
    expect(mapping?.getColor?.(20)).toMatch(/^rgb\(/);
  });
});
