export type MetadataImportTarget = 'var' | 'obs';

export interface ColumnMapping {
  idColumn: string;
  valueColumn: string;
}

export function splitDelimitedLine(line: string, separator: string): string[] {
  if (separator === '\\s+' || separator === '\s+') {
    return line.trim().split(/\s+/).filter((column: string) => column);
  }

  const actualSeparator = separator === '\\t' ? '\t' : separator;
  return line.split(actualSeparator).map((column: string) => column.trim());
}

export function getDefaultColumnMapping(
  headers: string[],
  target: MetadataImportTarget,
): ColumnMapping {
  const defaultId = target === 'var' ? 'gene_id' : 'sample_id';
  const idColumn = headers.find((header: string) => header.toLowerCase() === defaultId)
    || headers.find((header: string) => header.toLowerCase().includes('id'))
    || headers[0]
    || '';

  const valueColumn = headers.find((header: string) => header !== idColumn)
    || headers[1]
    || '';

  return { idColumn, valueColumn };
}

export function resolveColumnMapping(
  headers: string[],
  target: MetadataImportTarget,
  current: ColumnMapping,
): ColumnMapping {
  if (headers.length < 2) {
    return { idColumn: '', valueColumn: '' };
  }

  const availableHeaders = new Set(headers);
  const defaults = getDefaultColumnMapping(headers, target);

  let idColumn = availableHeaders.has(current.idColumn) ? current.idColumn : defaults.idColumn;

  let valueColumn = availableHeaders.has(current.valueColumn) ? current.valueColumn : '';
  if (!valueColumn || valueColumn === idColumn) {
    valueColumn = headers.find((header: string) => header !== idColumn && header === current.valueColumn)
      || headers.find((header: string) => header !== idColumn)
      || '';
  }

  if (!valueColumn && headers.length >= 2) {
    const repairedId = headers.find((header: string) => header !== current.valueColumn) || defaults.idColumn;
    idColumn = repairedId;
    valueColumn = headers.find((header: string) => header !== repairedId) || '';
  }

  return { idColumn, valueColumn };
}