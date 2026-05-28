import { beautifyLabel } from "./utils";
import { useColumnsStore } from "@/stores/columns";

export function getDisplayName(fieldName: string, backendDisplayName?: string): string {
  if (backendDisplayName) {
    return backendDisplayName;
  }

  try {
    const columnsStore = useColumnsStore();
    const rowColumn = columnsStore.rowColumns.find((column) => column.column_name === fieldName);
    if (rowColumn?.display_name) {
      return rowColumn.display_name;
    }

    const sampleColumn = columnsStore.colColumns.find((column) => column.column_name === fieldName);
    if (sampleColumn?.display_name) {
      return sampleColumn.display_name;
    }
  } catch {
    // The Pinia store may not be available during early module initialization.
  }

  return beautifyLabel(fieldName);
}

export const sequenceFields = ["protein_seq", "rna_seq", "newick_str"];

export const verboseFields = ["description_long"];

export const arrayFields = [
  "go_terms",
  "ipr_id",
  "pfam_id",
  "uniprot_term",
  "family",
  "ipr_desc",
  "pfam_desc",
];
