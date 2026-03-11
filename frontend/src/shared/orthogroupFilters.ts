import type { FilterValue } from '@/stores/filters';

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
      strict: false,
      empty: false,
    },
  };
}