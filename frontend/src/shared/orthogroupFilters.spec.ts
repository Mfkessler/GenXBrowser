import { describe, expect, it } from 'vitest';

import { buildOrthogroupScopedFilters } from './orthogroupFilters';

describe('orthogroup filter helper', () => {
  it('adds the selected orthogroup without mutating other filters', () => {
    const baseFilters = {
      gene_id: {
        value: 'AT1G01010',
        strict: false,
        empty: false,
      },
    };

    const scopedFilters = buildOrthogroupScopedFilters(baseFilters, 'og0001');

    expect(scopedFilters).toEqual({
      gene_id: {
        value: 'AT1G01010',
        strict: false,
        empty: false,
      },
      ortho_id: {
        value: 'og0001',
        strict: false,
        empty: false,
      },
    });
    expect(baseFilters).not.toHaveProperty('ortho_id');
  });
});