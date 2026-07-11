/**
 * Composable for separating gene/transcript filters from sample filters.
 * This ensures consistent filter handling across all visualization components.
 */
import { computed, type ComputedRef } from "vue";
import { storeToRefs } from "pinia";
import { useFiltersStore, type FilterChainPayload, type FilterValue } from "@/stores/filters";
import { useColumnsStore } from "@/stores/columns";

export function useFilterSeparation() {
  const filtersStore = useFiltersStore();
  const columnStore = useColumnsStore();
  const { filters } = storeToRefs(filtersStore);
  const filterChainVersion = computed(() => filtersStore.filterChainVersion);

  /**
   * Gene/Transcript filters: filters that apply to row-level data
   * These are columns defined in columnStore.rowColumns
   */
  const geneFilters = computed(() => {
    const geneColNames = new Set(columnStore.rowColumns.map((c) => c.column_name));
    return Object.fromEntries(
      Object.entries(filters.value).filter(([key]) => geneColNames.has(key))
    );
  });

  /**
   * Sample filters: filters that apply to column-level/sample data
   * These are columns defined in columnStore.filterableColColumns
   */
  const sampleFilters = computed(() => {
    const sampleColNames = new Set(
      columnStore.filterableColColumns.map((c) => c.column_name)
    );
    return Object.fromEntries(
      Object.entries(filters.value).filter(([key]) => sampleColNames.has(key))
    );
  });

  /**
   * Check if any sample filters are currently active
   */
  const hasSampleFilters = computed(() => {
    return Object.keys(sampleFilters.value).length > 0;
  });

  /**
   * Check if any gene filters are currently active
   */
  const hasGeneFilters = computed(() => {
    return Object.keys(geneFilters.value).length > 0;
  });

  /**
   * Returns gene filters merged with the per-dataset ID filter for a given table,
   * with any columns disabled in that dataset's local filter chain stripped out.
   * Use this in analysis views that fetch data for a specific dataset.
   */
  function getMergedGeneFilters(tableName: string): ComputedRef<Record<string, FilterValue>> {
    return computed(() => {
      const base = geneFilters.value;
      const dsFilter = filtersStore.datasetIdFilters[tableName];
      const merged = dsFilter ? { ...base, [filtersStore.idColumnName]: dsFilter } : { ...base };
      const disabled = filtersStore.getDisabledColumnsForDataset(tableName);
      for (const column of Object.keys(disabled)) {
        if (disabled[column]) delete merged[column];
      }
      return merged;
    });
  }

  /**
   * Returns all filters merged with the per-dataset ID filter for a given table,
   * with any columns disabled in that dataset's local filter chain stripped out.
   * Use this in components that send unsplit filters (ORA, Phylo).
   */
  function getMergedAllFilters(tableName: string): ComputedRef<Record<string, FilterValue>> {
    return computed(() => {
      const base = filters.value;
      const dsFilter = filtersStore.datasetIdFilters[tableName];
      const merged = dsFilter ? { ...base, [filtersStore.idColumnName]: dsFilter } : { ...base };
      const disabled = filtersStore.getDisabledColumnsForDataset(tableName);
      for (const column of Object.keys(disabled)) {
        if (disabled[column]) delete merged[column];
      }
      return merged;
    });
  }

  function getFilterChainPayload(
    filterPayload: Record<string, FilterValue>,
    datasetId?: string | null,
  ): FilterChainPayload | null {
    return filtersStore.buildFilterChainPayload(filterPayload, datasetId);
  }

  return {
    filters,
    geneFilters,
    sampleFilters,
    hasSampleFilters,
    hasGeneFilters,
    filterChainVersion,
    getMergedGeneFilters,
    getMergedAllFilters,
    getFilterChainPayload,
  };
}
