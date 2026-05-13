import { describe, expect, it } from 'vitest';

import {
  createVisibleColorMapping,
  getListMetadataColor,
  getListMetadataKey,
  normalizeMetadataList,
  SharedColorRegistry,
} from './colorMapping';

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

  it('creates deterministic array mappings from normalized keys', () => {
    const mapping = createVisibleColorMapping('go_terms', 'array', [
      ['GO:2', 'GO:1'],
      ['GO:1', 'GO:2'],
      ['GO:3'],
    ]);

    expect(mapping['GO:1|GO:2']).toBe(getListMetadataColor(['GO:1', 'GO:2']));
    expect(mapping['GO:3']).toBe(getListMetadataColor(['GO:3']));
  });

  it('keeps overlapping list sets stable through the shared registry', () => {
    const registry = new SharedColorRegistry();
    registry.registerValues('go_terms', 'array', [['GO:2', 'GO:1']]);
    const first = registry.getMapping('go_terms')?.['GO:1|GO:2'];

    registry.registerValues('go_terms', 'array', [['GO:1', 'GO:2'], ['GO:4']]);
    const second = registry.getMapping('go_terms')?.['GO:1|GO:2'];

    expect(first).toBe(second);
  });

  it('preserves numeric values in the shared registry for continuous color scales', () => {
    const registry = new SharedColorRegistry();
    registry.registerValues('assigned', 'bigint', [10, 20, 30]);

    const mapping = registry.getMapping('assigned');

    expect(mapping?.getColor?.(20)).not.toBe('#eeeeee');
    expect(mapping?.getColor?.(20)).toMatch(/^rgb\(/);
  });
});
