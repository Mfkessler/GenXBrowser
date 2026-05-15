import { describe, expect, it } from 'vitest';

import { filterMetadataRows, uniqueMetadataValues } from './sampleMetadataFilters';

const rows = [
  { column_name: 's1', tissue: 'adult', assigned: true, pct_unmapped: 2 },
  { column_name: 's2', tissue: 'flower', assigned: true, pct_unmapped: 7 },
  { column_name: 's3', tissue: 'root', assigned: false, pct_unmapped: 12 },
  { column_name: 's4', tissue: 'seed', assigned: true, pct_unmapped: 20 },
];

describe('sample metadata filters', () => {
  it('intersects pipe-delimited exact tissue filters with dataset metadata', () => {
    const filtered = filterMetadataRows(
      rows,
      { tissue: { value: 'adult|flower|missing', exact: true, match_mode: 'or' } },
      new Set(['tissue']),
    );

    expect(uniqueMetadataValues(filtered, 'tissue')).toEqual(['adult', 'flower']);
  });

  it('keeps exact, bulk, and numeric sample filters combined', () => {
    const filtered = filterMetadataRows(
      rows,
      {
        tissue: { value: 'adult|flower|root|seed', exact: true, match_mode: 'or' },
        assigned: true,
        pct_unmapped: { value: [0, 10] },
      },
      new Set(['tissue', 'assigned', 'pct_unmapped']),
    );

    expect(filtered.map((row) => row.column_name)).toEqual(['s1', 's2']);
  });

  it('supports non-exact text matching without matching unknown columns', () => {
    const filtered = filterMetadataRows(
      rows,
      {
        tissue: { value: 'flow', exact: false },
        species_only_filter: { value: 'ignored' },
      },
      new Set(['tissue']),
    );

    expect(uniqueMetadataValues(filtered, 'tissue')).toEqual(['flower']);
  });
});