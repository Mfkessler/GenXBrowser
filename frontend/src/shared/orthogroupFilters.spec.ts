import { describe, expect, it } from 'vitest';

import {
  buildOrthogroupOnlyFilters,
  buildOrthogroupScopedFilters,
  hasNonOrthogroupFilters,
  omitFilterKey,
} from './orthogroupFilters';

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

  it('builds an orthogroup-only filter payload', () => {
    expect(buildOrthogroupOnlyFilters('OG0000078')).toEqual({
      ortho_id: {
        value: 'OG0000078',
        strict: false,
        empty: false,
      },
    });
  });

  it('removes the orthogroup filter when deriving highlight filters', () => {
    expect(omitFilterKey({
      ortho_id: {
        value: 'OG0000078',
        strict: false,
        empty: false,
      },
      module_colors: {
        value: 'black',
        strict: false,
        empty: false,
      },
    })).toEqual({
      module_colors: {
        value: 'black',
        strict: false,
        empty: false,
      },
    });
  });

  it('detects whether additional non-orthogroup filters are active', () => {
    expect(hasNonOrthogroupFilters({
      ortho_id: {
        value: 'OG0000078',
        strict: false,
        empty: false,
      },
    })).toBe(false);

    expect(hasNonOrthogroupFilters({
      ortho_id: {
        value: 'OG0000078',
        strict: false,
        empty: false,
      },
      module_colors: {
        value: 'black',
        strict: false,
        empty: false,
      },
    })).toBe(true);
  });
});