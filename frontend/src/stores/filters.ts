import { defineStore } from "pinia";

/**
 * How multiple selected values for the same metadata column are combined.
 *  - "or"  : at least one of the values must match (default)
 *  - "and" : every selected value must match
 */
export type FilterMatchMode = "or" | "and";
export type FilterChainOperator = "and" | "or";

const FILTER_CHAIN_STORAGE_KEY = "genxbrowser-filter-chain-operators";
const FILTER_CHAIN_GROUPS_STORAGE_KEY = "genxbrowser-filter-chain-groups";

export interface FilterValue {
  value: string;
  /** How multiple values combine. Default "or". */
  match_mode?: FilterMatchMode;
  /** Whether values must match exactly (true, default) or as substrings. */
  exact?: boolean;
  /** When true, keep only rows/samples with a non-empty, non-null metadata value. */
  has_value?: boolean;
}

export interface FilterChainPayload {
  columns: string[];
  operators: FilterChainOperator[];
  groups?: Record<string, FilterChainGroup>;
}

export interface FilterChainGroup {
  open?: number;
  close?: number;
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
  /** Current user-defined order for active row-level filter categories. */
  filterChainColumns: string[];
  /** Saved operators keyed by unordered filter-column pairs. */
  filterChainOperators: Record<string, FilterChainOperator>;
  /** Saved explicit parentheses keyed by filter-column name. */
  filterChainGroups: Record<string, FilterChainGroup>;
  filterChainHydrated: boolean;
  filterChainVersion: number;
}

function hasLocalStorage(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function pairKey(left: string, right: string): string {
  return [left, right].sort().join("::");
}

function isActiveFilter(filter?: FilterValue): boolean {
  if (!filter) return false;
  if (filter.has_value) return true;
  return String(filter.value ?? "").trim() !== "";
}

function normalizeOperator(value: unknown): FilterChainOperator {
  return String(value).toLowerCase() === "or" ? "or" : "and";
}

export const useFiltersStore = defineStore("filters", {
  state: (): FiltersState => ({
    tags: new Set(),
    table_names: new Set(),
    filters: {},
    columns: [],
    datasetIdFilters: {},
    idColumnName: "gene_id",
    filterChainColumns: [],
    filterChainOperators: {},
    filterChainGroups: {},
    filterChainHydrated: false,
    filterChainVersion: 0,
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
    activeFilterKeys: (state): string[] => Object.entries(state.filters)
      .filter(([, filter]) => isActiveFilter(filter))
      .map(([key]) => key),
  },
  actions: {
    hydrateFilterChainOperators() {
      if (this.filterChainHydrated) return;
      this.filterChainHydrated = true;
      if (!hasLocalStorage()) return;
      try {
        const raw = window.localStorage.getItem(FILTER_CHAIN_STORAGE_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw) as Record<string, unknown>;
        this.filterChainOperators = Object.fromEntries(
          Object.entries(parsed).map(([key, value]) => [key, normalizeOperator(value)]),
        );
      } catch {
        this.filterChainOperators = {};
      }
      try {
        const raw = window.localStorage.getItem(FILTER_CHAIN_GROUPS_STORAGE_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw) as Record<string, FilterChainGroup>;
        this.filterChainGroups = Object.fromEntries(
          Object.entries(parsed).map(([column, group]) => [
            column,
            {
              open: Number(group?.open || 0),
              close: Number(group?.close || 0),
            },
          ]),
        );
      } catch {
        this.filterChainGroups = {};
      }
    },
    persistFilterChainOperators() {
      if (!hasLocalStorage()) return;
      window.localStorage.setItem(
        FILTER_CHAIN_STORAGE_KEY,
        JSON.stringify(this.filterChainOperators),
      );
    },
    persistFilterChainGroups() {
      if (!hasLocalStorage()) return;
      window.localStorage.setItem(
        FILTER_CHAIN_GROUPS_STORAGE_KEY,
        JSON.stringify(this.filterChainGroups),
      );
    },
    getPairOperator(left: string, right: string): FilterChainOperator {
      this.hydrateFilterChainOperators();
      return this.filterChainOperators[pairKey(left, right)] ?? "and";
    },
    setPairOperator(left: string, right: string, operator: FilterChainOperator) {
      this.hydrateFilterChainOperators();
      this.filterChainOperators = {
        ...this.filterChainOperators,
        [pairKey(left, right)]: operator,
      };
      this.filterChainVersion += 1;
      this.persistFilterChainOperators();
    },
    togglePairOperator(left: string, right: string) {
      const next = this.getPairOperator(left, right) === "and" ? "or" : "and";
      this.setPairOperator(left, right, next);
    },
    syncFilterChainColumns(activeKeys: string[]) {
      const activeSet = new Set(activeKeys);
      this.filterChainColumns = [
        ...this.filterChainColumns.filter((column) => activeSet.has(column)),
        ...activeKeys.filter((column) => !this.filterChainColumns.includes(column)),
      ];
    },
    setFilterChainColumns(columns: string[]) {
      const seen = new Set<string>();
      this.filterChainColumns = columns.filter((column) => {
        if (seen.has(column)) return false;
        seen.add(column);
        return true;
      });
      this.filterChainVersion += 1;
    },
    getFilterChainGroups(columns: string[]): Record<string, FilterChainGroup> {
      this.hydrateFilterChainOperators();
      const columnSet = new Set(columns);
      return Object.fromEntries(
        Object.entries(this.filterChainGroups)
          .filter(([column]) => columnSet.has(column))
          .map(([column, group]) => [
            column,
            {
              open: Number(group.open || 0),
              close: Number(group.close || 0),
            },
          ]),
      );
    },
    setFilterChainGroups(groups: Record<string, FilterChainGroup>) {
      this.hydrateFilterChainOperators();
      const nextGroups: Record<string, FilterChainGroup> = {};
      for (const [column, group] of Object.entries(groups)) {
        const normalizedGroup = {
          open: Number(group.open || 0),
          close: Number(group.close || 0),
        };
        if (normalizedGroup.open || normalizedGroup.close) {
          nextGroups[column] = normalizedGroup;
        }
      }
      this.filterChainGroups = nextGroups;
      this.filterChainVersion += 1;
      this.persistFilterChainGroups();
    },
    normalizeFilterChainGroups(
      columns: string[],
      groups?: Record<string, FilterChainGroup>,
    ): Record<string, FilterChainGroup> {
      const sourceGroups = groups ?? this.filterChainGroups;
      const columnSet = new Set(columns);
      const normalized: Record<string, FilterChainGroup> = {};
      for (const [column, group] of Object.entries(sourceGroups)) {
        if (!columnSet.has(column)) continue;
        const normalizedGroup = {
          open: Math.max(0, Number(group.open || 0)),
          close: Math.max(0, Number(group.close || 0)),
        };
        if (normalizedGroup.open || normalizedGroup.close) {
          normalized[column] = normalizedGroup;
        }
      }

      let depth = 0;
      for (const column of columns) {
        depth += normalized[column]?.open || 0;
        depth -= normalized[column]?.close || 0;
        if (depth < 0) return {};
      }
      if (depth !== 0) return {};
      return normalized;
    },
    buildFilterChainPayload(filters: Record<string, FilterValue>): FilterChainPayload | null {
      this.hydrateFilterChainOperators();
      const activeKeys = Object.entries(filters)
        .filter(([, filter]) => isActiveFilter(filter))
        .map(([key]) => key);
      if (activeKeys.length < 2) return null;

      const activeSet = new Set(activeKeys);
      const columns = [
        ...this.filterChainColumns.filter((column) => activeSet.has(column)),
        ...activeKeys.filter((column) => !this.filterChainColumns.includes(column)),
      ];
      const operators = columns.slice(0, -1).map((column, index) => (
        this.getPairOperator(column, columns[index + 1])
      ));
      const groups = this.normalizeFilterChainGroups(columns);
      return {
        columns,
        operators,
        ...(Object.keys(groups).length > 0 ? { groups } : {}),
      };
    },
    setFilter(key: string, filter: FilterValue) {
      this.filters[key] = filter;
    },
    setFilters(newFilters: Record<string, FilterValue>) {
      this.filters = { ...newFilters };
      this.syncFilterChainColumns(Object.entries(this.filters)
        .filter(([, filter]) => isActiveFilter(filter))
        .map(([key]) => key));
    },
    removeFilter(key: string) {
      delete this.filters[key];
      this.syncFilterChainColumns(this.activeFilterKeys);
    },
    clearFilters() {
      this.filters = {};
      this.filterChainColumns = [];
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
          if (key === 'tags' || key === 'table_names') {
            this[key] = new Set(Array.isArray(value) ? value : []);
          } else if (key === 'filters') {
            this.filters = value as FiltersState['filters'];
          } else if (key === 'columns') {
            this.columns = value as FiltersState['columns'];
          } else if (key === 'datasetIdFilters') {
            this.datasetIdFilters = value as FiltersState['datasetIdFilters'];
          } else if (key === 'idColumnName') {
            this.idColumnName = value as FiltersState['idColumnName'];
          } else if (key === 'filterChainColumns') {
            this.filterChainColumns = value as FiltersState['filterChainColumns'];
          } else if (key === 'filterChainOperators') {
            this.filterChainOperators = value as FiltersState['filterChainOperators'];
          } else if (key === 'filterChainGroups') {
            this.filterChainGroups = value as FiltersState['filterChainGroups'];
          } else {
            return;
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
        filterChainColumns: [...this.filterChainColumns],
        filterChainGroups: { ...this.filterChainGroups },
        filterChainVersion: this.filterChainVersion,
      };
    },
  },
});
