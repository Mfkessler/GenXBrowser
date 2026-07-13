import { defineStore } from "pinia";
import axios from "axios";

import { type MetaFormat } from "@/shared/MetaFormat";
import { API_BASE_URL } from "@/shared/Config";
import { DEFAULT_TRAIT_COLUMN } from "@/shared/defaultTrait";
import { getEntityLabel } from "@/shared/dataTypeLabels";
import { useFiltersStore } from "@/stores/filters";

export interface ColumnsState {
  rowColumns: MetaFormat[];
  colColumns: MetaFormat[];
  // Columns available for filtering in the Samples tab
  filterableColColumns: MetaFormat[];
  // Columns available for Column Order dropdown (includes the default trait pseudo-column)
  orderableColColumns: MetaFormat[];
  // Cached distinct values for specific columns
  distinctValues: Record<string, string[]>;
  // Currently loaded sample metadata rows from active visualizations
  sampleMetadata: Record<string, unknown>[];
  sampleMetadataByTable: Record<string, Record<string, unknown>[]>;
}

// Columns to hide from sample-metadata column selectors
const HIDDEN_COL_COLUMNS = ['type', 'ismeta'];

export const useColumnsStore = defineStore("columns", {
  state: (): ColumnsState => ({
    rowColumns: [],
    colColumns: [],
    filterableColColumns: [],
    orderableColColumns: [],
    distinctValues: {},
    sampleMetadata: [],
    sampleMetadataByTable: {},
  }),
  actions: {
    setRowColumns(columns: MetaFormat[]) {
      // The id/row-identifier column's display name is always driven by the frontend's
      // own Genes/Isoforms terminology (VITE_DATA_TYPE, see dataTypeLabels.ts) — e.g.
      // "Transcript" everywhere this app is deployed with VITE_DATA_TYPE=Isoforms — rather
      // than whatever generic fallback name the backend config happens to have (it has no
      // knowledge of VITE_DATA_TYPE at all; see ConfigManager.ID_COLUMN_NAME). This keeps
      // it consistent with every other Gene/Transcript label in the app (getEntityLabel*),
      // and fixes it showing as the backend's literal "Gene ID" auto-fallback on instances
      // configured for Isoforms terminology.
      const idColumnName = useFiltersStore().idColumnName;
      this.rowColumns = columns
        .filter(c => !c.is_default_trait)
        .map(c => (
          c.column_name === idColumnName
            ? { ...c, display_name: getEntityLabel() }
            : c
        ));
    },
    setColColumns(columns: MetaFormat[]) {
      // Filter out hidden internal columns
      const cleaned = columns.filter(c => !HIDDEN_COL_COLUMNS.includes(c.column_name.toLowerCase()));
      const defaultTraitEntry = cleaned.find(c => c.is_default_trait);
      const regularColumns = cleaned.filter(c => !c.is_default_trait);

      if (defaultTraitEntry) {
        const defaultTraitDisplayName = defaultTraitEntry.display_name || defaultTraitEntry.column_name;

        // For filtering: use the configured source column directly because it has the actual values.
        this.filterableColColumns = [
          {
            column_name: defaultTraitEntry.column_name,
            type: defaultTraitEntry.type || "text",
            display_name: defaultTraitDisplayName,
            is_default_trait: true,
          },
          ...regularColumns,
        ];

        // For ordering/coloring: expose the role as a single pseudo-column so the
        // configured source column does not appear twice.
        this.orderableColColumns = [
          ...regularColumns,
          { column_name: DEFAULT_TRAIT_COLUMN, type: "text", display_name: defaultTraitDisplayName },
        ];

        this.colColumns = [
          ...regularColumns,
          { column_name: DEFAULT_TRAIT_COLUMN, type: "text", display_name: defaultTraitDisplayName },
        ];
      } else {
        this.filterableColColumns = cleaned;
        this.orderableColColumns = [
          ...cleaned,
          { column_name: DEFAULT_TRAIT_COLUMN, type: "text" },
        ];
        this.colColumns = [
          ...cleaned,
          { column_name: DEFAULT_TRAIT_COLUMN, type: "text" },
        ];
      }
    },
    setSampleMetadata(records: Record<string, unknown>[], tableName = "__default") {
      this.sampleMetadataByTable[tableName] = records;
      const bySample = new Map<string, Record<string, unknown>>();
      for (const tableRecords of Object.values(this.sampleMetadataByTable)) {
        for (const record of tableRecords) {
          const sampleName = String(record.column_name ?? "");
          if (sampleName) bySample.set(sampleName, record);
        }
      }
      this.sampleMetadata = [...bySample.values()];
    },
    // Set distinct values for a column
    setDistinctValues(columnName: string, values: string[]) {
      this.distinctValues[columnName] = values;
    },
    // Get distinct values for a column
    getDistinctValues(columnName: string): string[] {
      return this.distinctValues[columnName] || [];
    },
    // Get the actual column name for filtering
    getActualColumnName(displayName: string): string {
      return displayName; // h5ad names are the standard — no mapping needed
    },
    // Refresh columns from backend (called after admin config save)
    async refreshColumns() {
      try {
        const [metaResponse, columnMetaResponse] = await Promise.all([
          axios.get(`${API_BASE_URL}/api/columns`, { params: { meta: true, columns: false } }),
          axios.get(`${API_BASE_URL}/api/columns`, { params: { columns: true } }),
        ]);
        this.setRowColumns(metaResponse.data);
        this.setColColumns(columnMetaResponse.data);
      } catch (e) {
        console.warn('Failed to refresh columns from backend', e);
      }
    },
  },
  getters: {
    allColumns(state): MetaFormat[] {
      return [...state.rowColumns, ...state.filterableColColumns];
    },
    defaultTraitColumnName(state): string | null {
      const defaultTraitColumn = state.filterableColColumns.find(c => c.is_default_trait);
      return defaultTraitColumn?.column_name || null;
    },
    traitValues(state): string[] {
      const defaultTraitColumn = state.filterableColColumns.find(c => c.is_default_trait);
      if (defaultTraitColumn) {
        return state.distinctValues[defaultTraitColumn.column_name] || [];
      }
      return [];
    },
  },
});
