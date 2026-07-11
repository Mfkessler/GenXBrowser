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
const FILTER_CHAIN_NOTS_STORAGE_KEY = "genxbrowser-filter-chain-nots";

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
  /** Columns whose mask should be logically negated (NOT). */
  nots?: string[];
}

export interface FilterChainGroup {
  open?: number;
  close?: number;
}

/** A single filter chain's structural configuration (order/operators/parens/negation). */
export interface FilterChainState {
  columns: string[];
  operators: Record<string, FilterChainOperator>;
  groups: Record<string, FilterChainGroup>;
  nots: Record<string, boolean>;
  /**
   * Columns completely excluded from this (local) chain — unlike NOT, a disabled
   * column's filter is dropped from the effective query entirely for this dataset.
   * Only meaningful for dataset-local chains; the global chain never disables columns
   * (removing the filter value from the sidebar already achieves that there).
   */
  disabled: Record<string, boolean>;
}

function emptyFilterChainState(): FilterChainState {
  return { columns: [], operators: {}, groups: {}, nots: {}, disabled: {} };
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
  /** Saved NOT (negation) toggle keyed by filter-column name. */
  filterChainNots: Record<string, boolean>;
  filterChainHydrated: boolean;
  filterChainVersion: number;
  /**
   * Dataset-specific filter chain overrides. When a dataset id has an entry
   * here, it takes precedence over the global filter chain for that dataset
   * (see `getEffectiveChainPerDataset`). Datasets without an entry inherit
   * the global chain.
   */
  localDatasetChains: Record<string, FilterChainState>;
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
    filterChainNots: {},
    filterChainHydrated: false,
    filterChainVersion: 0,
    localDatasetChains: {},
  }),
  getters: {
    /**
     * Returns the global filters merged with the per-dataset ID filter for a given table,
     * with any columns disabled in that dataset's local chain stripped out entirely.
     * Used by analysis views and CatalogEntry to get the effective filters for one dataset.
     */
    getMergedFilters: (state) => (tableName: string): Record<string, FilterValue> => {
      const dsFilter = state.datasetIdFilters[tableName];
      const merged: Record<string, FilterValue> = dsFilter
        ? { ...state.filters, [state.idColumnName]: dsFilter }
        : { ...state.filters };
      const disabled = state.localDatasetChains[tableName]?.disabled;
      if (!disabled) return merged;
      for (const column of Object.keys(disabled)) {
        if (disabled[column]) delete merged[column];
      }
      return merged;
    },
    activeFilterKeys: (state): string[] => Object.entries(state.filters)
      .filter(([, filter]) => isActiveFilter(filter))
      .map(([key]) => key),
    /** Whether the given dataset has a localized (dataset-specific) filter chain override. */
    hasLocalChain: (state) => (datasetId: string): boolean => !!state.localDatasetChains[datasetId],
    /**
     * Columns completely excluded (disabled) from a dataset's local chain. Empty for
     * datasets without a local override, since the global chain never disables columns.
     */
    getDisabledColumnsForDataset: (state) => (datasetId?: string | null): Record<string, boolean> => (
      (datasetId && state.localDatasetChains[datasetId]?.disabled) || {}
    ),
    /**
     * Returns the effective filter chain structure (order/operators/groups/nots) for a
     * dataset: its local override if one exists, otherwise the global chain.
     */
    getEffectiveChainPerDataset: (state) => (datasetId?: string | null): FilterChainState & { isLocal: boolean } => {
      const local = datasetId ? state.localDatasetChains[datasetId] : undefined;
      if (local) {
        return { ...local, isLocal: true };
      }
      return {
        columns: state.filterChainColumns,
        operators: state.filterChainOperators,
        groups: state.filterChainGroups,
        nots: state.filterChainNots,
        disabled: {},
        isLocal: false,
      };
    },
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
      try {
        const raw = window.localStorage.getItem(FILTER_CHAIN_NOTS_STORAGE_KEY);
        if (!raw) return;
        const parsed = JSON.parse(raw) as Record<string, unknown>;
        this.filterChainNots = Object.fromEntries(
          Object.entries(parsed).filter(([, value]) => !!value).map(([column]) => [column, true]),
        );
      } catch {
        this.filterChainNots = {};
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
    persistFilterChainNots() {
      if (!hasLocalStorage()) return;
      window.localStorage.setItem(
        FILTER_CHAIN_NOTS_STORAGE_KEY,
        JSON.stringify(this.filterChainNots),
      );
    },
    /** Ensures a (initially empty) local chain override exists for a dataset. */
    ensureLocalChain(datasetId: string) {
      if (this.localDatasetChains[datasetId]) return;
      this.localDatasetChains = {
        ...this.localDatasetChains,
        [datasetId]: emptyFilterChainState(),
      };
    },
    /**
     * Copies the current EFFECTIVE chain (global, since a dataset can only be
     * localized while it still inherits) into a new mutable local override for
     * `datasetId`, scoped to `activeColumns`. Subsequent edits to that dataset's
     * chain (via the `datasetId` argument on the setters below) apply only to
     * this dataset and no longer follow the global chain.
     */
    localizeDatasetChain(datasetId: string, activeColumns: string[]) {
      this.hydrateFilterChainOperators();
      const columns = [
        ...this.filterChainColumns.filter((column) => activeColumns.includes(column)),
        ...activeColumns.filter((column) => !this.filterChainColumns.includes(column)),
      ];
      const operators: Record<string, FilterChainOperator> = {};
      for (let i = 0; i < columns.length - 1; i += 1) {
        operators[pairKey(columns[i], columns[i + 1])] = this.getPairOperator(columns[i], columns[i + 1]);
      }
      const groups = this.getFilterChainGroups(columns);
      const nots: Record<string, boolean> = {};
      for (const column of columns) {
        if (this.filterChainNots[column]) nots[column] = true;
      }
      this.localDatasetChains = {
        ...this.localDatasetChains,
        [datasetId]: { columns, operators, groups, nots, disabled: {} },
      };
      this.filterChainVersion += 1;
    },
    /** Discards a dataset's local override so it goes back to inheriting the global chain. */
    resetDatasetChain(datasetId: string) {
      if (!this.localDatasetChains[datasetId]) return;
      const copy = { ...this.localDatasetChains };
      delete copy[datasetId];
      this.localDatasetChains = copy;
      this.filterChainVersion += 1;
    },
    getPairOperator(left: string, right: string, datasetId?: string | null): FilterChainOperator {
      this.hydrateFilterChainOperators();
      const operators = datasetId ? this.localDatasetChains[datasetId]?.operators ?? {} : this.filterChainOperators;
      return operators[pairKey(left, right)] ?? "and";
    },
    setPairOperator(left: string, right: string, operator: FilterChainOperator, datasetId?: string | null) {
      this.hydrateFilterChainOperators();
      if (datasetId) {
        this.ensureLocalChain(datasetId);
        this.localDatasetChains = {
          ...this.localDatasetChains,
          [datasetId]: {
            ...this.localDatasetChains[datasetId],
            operators: {
              ...this.localDatasetChains[datasetId].operators,
              [pairKey(left, right)]: operator,
            },
          },
        };
      } else {
        this.filterChainOperators = {
          ...this.filterChainOperators,
          [pairKey(left, right)]: operator,
        };
        this.persistFilterChainOperators();
      }
      this.filterChainVersion += 1;
    },
    togglePairOperator(left: string, right: string, datasetId?: string | null) {
      const next = this.getPairOperator(left, right, datasetId) === "and" ? "or" : "and";
      this.setPairOperator(left, right, next, datasetId);
    },
    /** Returns whether `column` is negated (NOT) — dataset-local override if present, else global. */
    getNot(column: string, datasetId?: string | null): boolean {
      this.hydrateFilterChainOperators();
      const nots = datasetId ? this.localDatasetChains[datasetId]?.nots ?? {} : this.filterChainNots;
      return !!nots[column];
    },
    setNot(column: string, value: boolean, datasetId?: string | null) {
      this.hydrateFilterChainOperators();
      if (datasetId) {
        this.ensureLocalChain(datasetId);
        const nots = { ...this.localDatasetChains[datasetId].nots };
        if (value) nots[column] = true; else delete nots[column];
        this.localDatasetChains = {
          ...this.localDatasetChains,
          [datasetId]: { ...this.localDatasetChains[datasetId], nots },
        };
      } else {
        const nots = { ...this.filterChainNots };
        if (value) nots[column] = true; else delete nots[column];
        this.filterChainNots = nots;
        this.persistFilterChainNots();
      }
      this.filterChainVersion += 1;
    },
    toggleNot(column: string, datasetId?: string | null) {
      this.setNot(column, !this.getNot(column, datasetId), datasetId);
    },
    /**
     * Whether `column` is completely excluded from a dataset's local chain (and thus from
     * the effective query for that dataset). Only meaningful with a `datasetId` — the
     * global chain never disables columns.
     */
    getDisabled(column: string, datasetId?: string | null): boolean {
      if (!datasetId) return false;
      return !!this.localDatasetChains[datasetId]?.disabled[column];
    },
    setDisabled(column: string, value: boolean, datasetId?: string | null) {
      if (!datasetId) return;
      this.ensureLocalChain(datasetId);
      const disabled = { ...this.localDatasetChains[datasetId].disabled };
      if (value) disabled[column] = true; else delete disabled[column];
      this.localDatasetChains = {
        ...this.localDatasetChains,
        [datasetId]: { ...this.localDatasetChains[datasetId], disabled },
      };
      this.filterChainVersion += 1;
    },
    toggleDisabled(column: string, datasetId?: string | null) {
      this.setDisabled(column, !this.getDisabled(column, datasetId), datasetId);
    },
    syncFilterChainColumns(activeKeys: string[]) {
      const activeSet = new Set(activeKeys);
      this.filterChainColumns = [
        ...this.filterChainColumns.filter((column) => activeSet.has(column)),
        ...activeKeys.filter((column) => !this.filterChainColumns.includes(column)),
      ];
    },
    setFilterChainColumns(columns: string[], datasetId?: string | null) {
      const seen = new Set<string>();
      const deduped = columns.filter((column) => {
        if (seen.has(column)) return false;
        seen.add(column);
        return true;
      });
      if (datasetId) {
        this.ensureLocalChain(datasetId);
        this.localDatasetChains = {
          ...this.localDatasetChains,
          [datasetId]: { ...this.localDatasetChains[datasetId], columns: deduped },
        };
      } else {
        this.filterChainColumns = deduped;
      }
      this.filterChainVersion += 1;
    },
    getFilterChainGroups(columns: string[], datasetId?: string | null): Record<string, FilterChainGroup> {
      this.hydrateFilterChainOperators();
      const columnSet = new Set(columns);
      const sourceGroups = datasetId ? this.localDatasetChains[datasetId]?.groups ?? {} : this.filterChainGroups;
      return Object.fromEntries(
        Object.entries(sourceGroups)
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
    setFilterChainGroups(groups: Record<string, FilterChainGroup>, datasetId?: string | null) {
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
      if (datasetId) {
        this.ensureLocalChain(datasetId);
        this.localDatasetChains = {
          ...this.localDatasetChains,
          [datasetId]: { ...this.localDatasetChains[datasetId], groups: nextGroups },
        };
      } else {
        this.filterChainGroups = nextGroups;
        this.persistFilterChainGroups();
      }
      this.filterChainVersion += 1;
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
    /**
     * Builds the filter-chain payload sent to the backend for a given filter set.
     * When `datasetId` is provided, the dataset's local chain override is used if
     * one exists (see `getEffectiveChainPerDataset`); otherwise the global chain
     * is used. Columns disabled in that dataset's local chain are dropped entirely
     * (as if their filter didn't exist), regardless of whether `filters` still
     * contains a value for them. A chain is only emitted when there are 2+ active
     * filters to combine, OR a single active filter is negated (NOT) — negation
     * requires the chain path even with just one column.
     */
    buildFilterChainPayload(filters: Record<string, FilterValue>, datasetId?: string | null): FilterChainPayload | null {
      this.hydrateFilterChainOperators();
      const chain = this.getEffectiveChainPerDataset(datasetId);
      const activeKeys = Object.entries(filters)
        .filter(([key, filter]) => isActiveFilter(filter) && !chain.disabled[key])
        .map(([key]) => key);
      if (activeKeys.length === 0) return null;

      const activeSet = new Set(activeKeys);
      const columns = [
        ...chain.columns.filter((column) => activeSet.has(column)),
        ...activeKeys.filter((column) => !chain.columns.includes(column)),
      ];
      const nots = columns.filter((column) => chain.nots[column]);
      if (columns.length < 2 && nots.length === 0) return null;

      const operators = columns.slice(0, -1).map((column, index) => (
        chain.operators[pairKey(column, columns[index + 1])] ?? "and"
      ));
      const groups = this.normalizeFilterChainGroups(columns, chain.groups);
      return {
        columns,
        operators,
        ...(Object.keys(groups).length > 0 ? { groups } : {}),
        ...(nots.length > 0 ? { nots } : {}),
      };
    },
    setFilter(key: string, filter: FilterValue) {
      this.filters[key] = filter;
      this.syncFilterChainColumns(this.activeFilterKeys);
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
          } else if (key === 'filterChainNots') {
            this.filterChainNots = value as FiltersState['filterChainNots'];
          } else if (key === 'localDatasetChains') {
            this.localDatasetChains = value as FiltersState['localDatasetChains'];
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
        filterChainOperators: { ...this.filterChainOperators },
        filterChainGroups: { ...this.filterChainGroups },
        filterChainNots: { ...this.filterChainNots },
        localDatasetChains: { ...this.localDatasetChains },
        filterChainVersion: this.filterChainVersion,
      };
    },
  },
});
