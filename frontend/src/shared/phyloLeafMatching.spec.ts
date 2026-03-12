import { describe, expect, it } from 'vitest';

import { buildPhyloMetricKeys, matchLeafToDataset, resolvePhyloLeafMatch } from './phyloLeafMatching';

describe('phylo leaf matching', () => {
  it('builds key variants for prefixed and unprefixed transcript identifiers', () => {
    expect(buildPhyloMetricKeys('arabidopsis_thaliana', 'AT1G26310.1.Araport11.447', 'AT')).toEqual([
      'AT1G26310.1.Araport11.447',
      'AT_AT1G26310.1.Araport11.447',
      'arabidopsis_thaliana_AT1G26310.1.Araport11.447',
      'Arabidopsis_thaliana_AT1G26310.1.Araport11.447',
    ]);
  });

  it('extracts the dataset and transcript id from code-prefixed leaves', () => {
    expect(matchLeafToDataset(
      'AT_AT1G26310.1.Araport11.447',
      ['arabidopsis_thaliana', 'oryza_sativa'],
      { arabidopsis_thaliana: 'AT', oryza_sativa: 'OS' },
    )).toEqual({
      tableName: 'arabidopsis_thaliana',
      geneId: 'AT1G26310.1.Araport11.447',
      matchedPrefix: 'AT',
    });
  });

  it('resolves lowercase prefixed leaves against stored metrics keys', () => {
    const metrics = {
      arabidopsis_thaliana: {
        'AT_AT1G26310.1.Araport11.447': { normalizationTissue: { flower: [1] } },
        'AT1G26310.1.Araport11.447': { normalizationTissue: { flower: [1] } },
      },
    };

    expect(resolvePhyloLeafMatch(
      'at_AT1G26310.1.Araport11.447',
      metrics,
      { arabidopsis_thaliana: 'AT' },
    )).toEqual({
      tableName: 'arabidopsis_thaliana',
      geneId: 'AT1G26310.1.Araport11.447',
      matchedPrefix: 'AT',
      matchedKey: 'AT1G26310.1.Araport11.447',
    });
  });

  it('falls back to bare transcript ids when trees do not include a species prefix', () => {
    const metrics = {
      arabidopsis_thaliana: {
        'AT1G26310.1.Araport11.447': { normalizationTissue: { flower: [1] } },
      },
      oryza_sativa: {
        'LOC_Os03g54160.1.MSUv7.0': { normalizationTissue: { leaf: [2] } },
      },
    };

    expect(resolvePhyloLeafMatch(
      'LOC_Os03g54160.1.MSUv7.0',
      metrics,
      { arabidopsis_thaliana: 'AT', oryza_sativa: 'OS' },
    )).toEqual({
      tableName: 'oryza_sativa',
      geneId: 'LOC_Os03g54160.1.MSUv7.0',
      matchedPrefix: '',
      matchedKey: 'LOC_Os03g54160.1.MSUv7.0',
    });
  });
});