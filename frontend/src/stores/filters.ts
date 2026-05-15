import { defineStore } from "pinia";

/**
 * How multiple selected values for the same metadata column are combined.
 *  - "or"  : at least one of the values must match (default)
 *  - "and" : every selected value must match
 */
export type FilterMatchMode = "or" | "and";

export interface FilterValue {
  value: string;
  /** How multiple values combine. Default "or". */
  match_mode?: FilterMatchMode;
  /** Whether values must match exactly (true, default) or as substrings. */
  exact?: boolean;
}

export interface FiltersState {
  tags: Set<string>;
  table_names: Set<string>;
  filters: Record<string, FilterValue>;
  columns: string[];
  /** Per-dataset ID filters keyed by table_name */
  datasetIdFilters: Record<string, FilterValue>;
  /** Name of the transcript/gene ID column (from config) */
  idColumnName: string;
}

export const useFiltersStore = defineStore("filters", {
  state: (): FiltersState => ({
    tags: new Set(),
    table_names: new Set(),
    filters: {},
    columns: [],
    datasetIdFilters: {},
    idColumnName: "gene_id",
  }),
  getters: {
    /**
     * Returns the global filters merged with the per-dataset ID filter for a given table.
     * Used by analysis views and CatalogEntry to get the effective filters for one dataset.
     */
    getMergedFilters: (state) => (tableName: string): Record<string, FilterValue> => {
      const dsFilter = state.datasetIdFilters[tableName];
      if (!dsFilter) return { ...state.filters };
      return {
        ...state.filters,
        [state.idColumnName]: dsFilter,
      };
    },
  },
  actions: {
    setFilter(key: string, filter: FilterValue) {
      this.filters[key] = filter;
    },
    setFilters(newFilters: Record<string, FilterValue>) {
      this.filters = { ...newFilters };
    },
    removeFilter(key: string) {
      delete this.filters[key];
    },
    clearFilters() {
      this.filters = {};
    },
    addTag(tag: string) {
      this.tags.add(tag);
    },
    setTags(tags: string[]) {
      this.tags = new Set(tags);
    },
    removeTag(tag: string) {
      this.tags.delete(tag);
    },
    setTableNames(table_names: string[]) {
      this.table_names = new Set(table_names);
    },
    setColumns(newColumns: string[]) {
      this.columns = newColumns;
    },
    addColumn(column: string) {
      if (!this.columns.includes(column)) {
        this.columns.push(column);
      }
    },
    removeColumn(column: string) {
      this.columns = this.columns.filter((c) => c !== column);
    },
    clearColumns() {
      this.columns = [];
    },
    // Per-dataset ID filter actions
    setIdColumnName(name: string) {
      this.idColumnName = name;
    },
    setDatasetIdFilter(tableName: string, filter: FilterValue) {
      this.datasetIdFilters = { ...this.datasetIdFilters, [tableName]: filter };
    },
    removeDatasetIdFilter(tableName: string) {
      const copy = { ...this.datasetIdFilters };
      delete copy[tableName];
      this.datasetIdFilters = copy;
    },
    clearDatasetIdFilters() {
      this.datasetIdFilters = {};
    },
    replaceState(newState: Partial<FiltersState>) {
      Object.entries(newState).forEach(([key, value]) => {
        if (key in this) {
          // Convert arrays back to Sets for tags and table_names
          if (key === 'tags' || key === 'table_names') {
            this[key] = new Set(Array.isArray(value) ? value : []);
          } else {
            (this as any)[key] = value;
          }
        }
      });
    },
    toObject() {
      return {
        tags: Array.from(this.tags),
        table_names: Array.from(this.table_names),
        filters: { ...this.filters },
        datasetIdFilters: { ...this.datasetIdFilters },
        idColumnName: this.idColumnName,
      };
    },
  },
});
