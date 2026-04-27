import type { FilterValue } from '@/stores/filters';

export function omitFilterKey(
  baseFilters: Record<string, FilterValue>,
  filterKey = 'ortho_id',
): Record<string, FilterValue> {
  return Object.fromEntries(
    Object.entries(baseFilters).filter(([key]) => key !== filterKey),
  );
}

export function buildOrthogroupOnlyFilters(
  orthogroup: string,
  filterKey = 'ortho_id',
): Record<string, FilterValue> {
  return buildOrthogroupScopedFilters({}, orthogroup, filterKey);
}

export function hasNonOrthogroupFilters(
  baseFilters: Record<string, FilterValue>,
  filterKey = 'ortho_id',
): boolean {
  return Object.keys(omitFilterKey(baseFilters, filterKey)).length > 0;
}

export function buildOrthogroupScopedFilters(
  baseFilters: Record<string, FilterValue>,
  orthogroup: string,
  filterKey = 'ortho_id',
): Record<string, FilterValue> {
  const trimmedOrthogroup = orthogroup.trim();

  if (!trimmedOrthogroup) {
    return { ...baseFilters };
  }

  return {
    ...baseFilters,
    [filterKey]: {
      value: trimmedOrthogroup,
    },
  };
}