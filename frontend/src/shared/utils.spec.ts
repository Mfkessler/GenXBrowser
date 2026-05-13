import { describe, expect, it } from 'vitest';

import { compareValues } from './utils';

describe('compareValues', () => {
  it('sorts list metadata by normalized complete set key', () => {
    expect(compareValues(['GO:2', 'GO:1'], ['GO:1', 'GO:2'], 'asc')).toBe(0);
    expect(compareValues(['GO:1'], ['GO:1', 'GO:2'], 'asc')).toBeLessThan(0);
    expect(compareValues(['GO:1'], ['GO:1', 'GO:2'], 'desc')).toBeGreaterThan(0);
  });
});