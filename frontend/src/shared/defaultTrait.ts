export const DEFAULT_TRAIT_COLUMN = "default_trait";
export const LEGACY_DEFAULT_TRAIT_COLUMN = "tissue_types";

export function isDefaultTraitColumn(columnName: string): boolean {
  return columnName === DEFAULT_TRAIT_COLUMN || columnName === LEGACY_DEFAULT_TRAIT_COLUMN;
}

export function normalizeDefaultTraitColumn(columnName: string): string {
  return columnName === LEGACY_DEFAULT_TRAIT_COLUMN ? DEFAULT_TRAIT_COLUMN : columnName;
}

export function normalizeDefaultTraitColumns(columnNames: string[]): string[] {
  return columnNames.map(normalizeDefaultTraitColumn);
}
