import { describe, expect, it } from 'vitest';

import { getBlastConfig } from './blast';

describe('blast helpers', () => {
  it('builds a BLAST form configuration that opens the search form instead of submitting a job', () => {
    const config = getBlastConfig('ATGC', 'rna', 'refseq_rna');

    expect(config.url).toBe('https://blast.ncbi.nlm.nih.gov/Blast.cgi');
    expect(config.params).toMatchObject({
      CMD: 'Web',
      PAGE_TYPE: 'BlastSearch',
      PROGRAM: 'blastn',
      BLAST_PROGRAMS: 'blastn',
      DATABASE: 'refseq_rna',
      QUERY: 'ATGC',
    });
  });
});