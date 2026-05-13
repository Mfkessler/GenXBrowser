import { defineStore } from "pinia";
import axios from "axios";

import { type MetaFormat } from "@/shared/MetaFormat";
import { API_BASE_URL } from "@/shared/Config";

export interface ColumnsState {
  rowColumns: MetaFormat[];
  colColumns: MetaFormat[];
  // Columns available for filtering in the Samples tab
  filterableColColumns: MetaFormat[];
  // Columns available for Column Order dropdown (includes tissue_types)
  orderableColColumns: MetaFormat[];
  // Cached distinct values for specific columns (e.g., tissue types)
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
      // Filter out columns that are sample-level (is_tissue marks the tissue col as obs-only)
      this.rowColumns = columns.filter(c => !c.is_tissue);
    },
    setColColumns(columns: MetaFormat[]) {
      // Filter out hidden internal columns
      const cleaned = columns.filter(c => !HIDDEN_COL_COLUMNS.includes(c.column_name.toLowerCase()));
      // Find the column the admin has marked as the tissue role
      const tissueColEntry = cleaned.find(c => c.is_tissue);
      const nonTissueColumns = cleaned.filter(c => !c.is_tissue);

      if (tissueColEntry) {
        const tissueDisplayName = tissueColEntry.display_name || tissueColEntry.column_name;

        // For filtering: use the tissue column directly (it has the actual values)
        this.filterableColColumns = [
          {
            column_name: tissueColEntry.column_name,
            type: tissueColEntry.type || "text",
            display_name: tissueDisplayName,
            is_tissue: true,
          },
          ...nonTissueColumns,
        ];

        // For ordering: use only the tissue_types pseudo-column so the Tissue option
        // matches the ColSideColors/SampleColor option and does not appear twice.
        this.orderableColColumns = [
          ...nonTissueColumns,
          { column_name: "tissue_types", type: "text", display_name: tissueDisplayName },
        ];

        // colColumns for ColSideColors: tissue_types pseudo-column carries the admin display name
        this.colColumns = [
          ...nonTissueColumns,
          { column_name: "tissue_types", type: "text", display_name: tissueDisplayName },
        ];
      } else {
        // No tissue column configured — keep original columns as-is
        this.filterableColColumns = cleaned;
        this.orderableColColumns = [
          ...cleaned,
          { column_name: "tissue_types", type: "text" },
        ];
        this.colColumns = [
          ...cleaned,
          { column_name: "tissue_types", type: "text" },
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
    // Get tissue column name if it exists
    tissueColumnName(state): string | null {
      const tissueCol = state.filterableColColumns.find(c => c.is_tissue);
      return tissueCol?.column_name || null;
    },
    // Get cached tissue values
    tissueValues(state): string[] {
      const tissueCol = state.filterableColColumns.find(c => c.is_tissue);
      if (tissueCol) {
        return state.distinctValues[tissueCol.column_name] || [];
      }
      return [];
    },
  },
});
