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
      },
    };

    const scopedFilters = buildOrthogroupScopedFilters(baseFilters, 'og0001');

    expect(scopedFilters).toEqual({
      gene_id: {
        value: 'AT1G01010',
      },
      ortho_id: {
        value: 'og0001',
        exact: false,
      },
    });
    expect(baseFilters).not.toHaveProperty('ortho_id');
  });

  it('builds an orthogroup-only filter payload', () => {
    expect(buildOrthogroupOnlyFilters('OG0000078')).toEqual({
      ortho_id: {
        value: 'OG0000078',
        exact: false,
      },
    });
  });

  it('removes the orthogroup filter when deriving highlight filters', () => {
    expect(omitFilterKey({
      ortho_id: {
        value: 'OG0000078',
      },
      module_colors: {
        value: 'black',
      },
    })).toEqual({
      module_colors: {
        value: 'black',
      },
    });
  });

  it('detects whether additional non-orthogroup filters are active', () => {
    expect(hasNonOrthogroupFilters({
      ortho_id: {
        value: 'OG0000078',
      },
    })).toBe(false);

    expect(hasNonOrthogroupFilters({
      ortho_id: {
        value: 'OG0000078',
      },
      module_colors: {
        value: 'black',
      },
    })).toBe(true);
  });
});