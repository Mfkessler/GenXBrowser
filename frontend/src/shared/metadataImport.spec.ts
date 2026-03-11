import { describe, expect, it } from 'vitest';

import { resolveColumnMapping, splitDelimitedLine } from './metadataImport';

describe('metadataImport helpers', () => {
  it('preserves manual column mapping when the separator changes but headers stay valid', () => {
    const headers = splitDelimitedLine('sample condition', '\\s+');

    const mapping = resolveColumnMapping(headers, 'obs', {
      idColumn: 'sample',
      valueColumn: 'condition',
    });

    expect(mapping).toEqual({
      idColumn: 'sample',
      valueColumn: 'condition',
    });
  });

  it('repairs invalid mappings with sensible defaults', () => {
    const mapping = resolveColumnMapping(['condition', 'sample_id', 'batch'], 'obs', {
      idColumn: 'missing',
      valueColumn: 'missing-too',
    });

    expect(mapping).toEqual({
      idColumn: 'sample_id',
      valueColumn: 'condition',
    });
  });
});