import { describe, expect, it } from 'vitest';

import { buildPhyloRouteTarget } from './phyloNavigation';

describe('phylo navigation helper', () => {
  it('preserves the current table selection and injects the orthogroup query', () => {
    expect(
      buildPhyloRouteTarget('arabidopsis_thaliana,solanum_lycopersicum', 'arabidopsis_thaliana', 'OG0001', {
        filters: '{"tf_family":{"value":"MIKC"}}',
      })
    ).toEqual({
      name: 'phylogenetic analysis',
      params: {
        table_names: 'arabidopsis_thaliana,solanum_lycopersicum',
      },
      query: {
        filters: '{"tf_family":{"value":"MIKC"}}',
        orthogroup: 'OG0001',
      },
    });
  });

  it('falls back to the active dataset when the current route has no table_names parameter', () => {
    expect(buildPhyloRouteTarget(undefined, 'solanum_lycopersicum', 'OG0002')).toEqual({
      name: 'phylogenetic analysis',
      params: {
        table_names: 'solanum_lycopersicum',
      },
      query: {
        orthogroup: 'OG0002',
      },
    });
  });
});