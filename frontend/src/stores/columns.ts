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
}

// Tissue column names that should be recognized (including 'tissue' from h5ad)
const TISSUE_COLUMNS = ['tissue_col', 'tissue_x_col', 'tissue_type_col', 'tissue'];

// Columns to hide from sample-metadata column selectors
const HIDDEN_COL_COLUMNS = ['type', 'ismeta'];

export const useColumnsStore = defineStore("columns", {
  state: (): ColumnsState => ({
    rowColumns: [],
    colColumns: [],
    filterableColColumns: [],
    orderableColColumns: [],
    distinctValues: {},
  }),
  actions: {
    setRowColumns(columns: MetaFormat[]) {
      // If both 'og' and 'orthogroup' exist, hide 'orthogroup' (it's just an alias)
      const hasOg = columns.some(c => c.column_name === 'og');
      const hasOrthogroup = columns.some(c => c.column_name === 'orthogroup');
      
      // Filter out tissue_col - it's a sample property, not a gene property
      const filteredColumns = columns.filter(c => c.column_name !== 'tissue_col');
      
      if (hasOg && hasOrthogroup) {
        this.rowColumns = filteredColumns.filter(c => c.column_name !== 'orthogroup');
      } else {
        this.rowColumns = filteredColumns;
      }
    },
    setColColumns(columns: MetaFormat[]) {
      // Filter out hidden internal columns
      const cleaned = columns.filter(c => !HIDDEN_COL_COLUMNS.includes(c.column_name.toLowerCase()));
      // Check for tissue columns
      const tissueColumns = cleaned.filter(c => TISSUE_COLUMNS.includes(c.column_name));
      const nonTissueColumns = cleaned.filter(c => !TISSUE_COLUMNS.includes(c.column_name));
      
      // Find any tissue column (tissue_col or tissue)
      const tissueColEntry = columns.find(c => c.column_name === 'tissue_col') 
                          || columns.find(c => c.column_name === 'tissue');
      
      if (tissueColEntry) {
        // For filtering: use the tissue column directly (it has the actual values)
        this.filterableColColumns = [
          { 
            column_name: tissueColEntry.column_name, 
            type: tissueColEntry.type || "text",
            display_name: "Tissue"
          },
          ...nonTissueColumns,
        ];
        
        // For ordering: include tissue_types pseudo-column
        this.orderableColColumns = [
          { column_name: tissueColEntry.column_name, type: "string" },
          ...nonTissueColumns,
          { column_name: "tissue_types", type: "string" },
        ];
        
        // colColumns for ColSideColors: Only tissue_types (no duplicate)
        this.colColumns = [
          ...nonTissueColumns,
          { column_name: "tissue_types", type: "string" },
        ];
      } else {
        // No tissue_col - keep original columns
        this.filterableColColumns = columns;
        this.orderableColColumns = [
          ...columns,
          { column_name: "tissue_types", type: "string" },
        ];
        this.colColumns = [
          ...columns,
          { column_name: "tissue_types", type: "string" },
        ];
      }
    },
    // Set distinct values for a column
    setDistinctValues(columnName: string, values: string[]) {
      this.distinctValues[columnName] = values;
    },
    // Get distinct values for a column
    getDistinctValues(columnName: string): string[] {
      return this.distinctValues[columnName] || [];
    },
    // Helper to get the actual column name for filtering
    getActualColumnName(displayName: string): string {
      return displayName; // No mapping needed anymore, we use tissue_col directly
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
      const tissueCol = state.filterableColColumns.find(c => 
        TISSUE_COLUMNS.includes(c.column_name)
      );
      return tissueCol?.column_name || null;
    },
    // Get cached tissue values
    tissueValues(state): string[] {
      const tissueCol = state.filterableColColumns.find(c => 
        TISSUE_COLUMNS.includes(c.column_name)
      );
      if (tissueCol) {
        return state.distinctValues[tissueCol.column_name] || [];
      }
      return [];
    },
  },
});
