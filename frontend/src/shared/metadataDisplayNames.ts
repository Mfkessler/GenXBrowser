/**
 * Mapping of technical metadata field names to human-readable display names
 */

import { getEntityIdLabel } from "./dataTypeLabels";
import { beautifyLabel } from "./utils";
import { useColumnsStore } from "@/stores/columns";

export const metadataDisplayNames: Record<string, string> = {
  // Core identifiers - gene_id is dynamic, genename stays as "Gene Name"
  gene_id: getEntityIdLabel(),
  genename: "Gene Name",
  
  // Descriptions
  description: "Description",
  description_long: "Long Description",
  
  // Groupings
  ortho_id: "Orthogroup",
  hog: "HOG",
  family: "Family",
  
  // Annotations
  ecnumber: "EC Number",
  go_terms: "GO Terms",
  ipr_id: "InterPro",
  ipr_desc: "InterPro Desc",
  pfam_id: "Pfam",
  pfam_desc: "Pfam Desc",
  uniprot_term: "UniProt Term",
  
  // Transcription factors
  is_tf: "Is Transcription Factor",
  tf_family: "TF Family",
  
  // WGCNA modules
  module_colors: "Module",
  
  // Sequences
  protein_seq: "Protein Sequence",
  rna_seq: "RNA Sequence",
  
  // Phylogenetic
  newick_str: "Newick String",
  
  // Sample metadata (common column side colors)
  tissue: "Tissue",
  tissue_type: "Tissue Type",
  tissue_types: "Tissue Types",
  species: "Species",
  sample_id: "Sample ID",
  condition: "Condition",
  replicate: "Replicate",
  batch: "Batch",
  developmental_stage: "Developmental Stage",
  treatment: "Treatment",
  assigned: "Assigned Reads",
  pct_unmapped: "% Unmapped",
  pct_no_feature: "% No Feature",
  pct_trimmed: "% Trimmed",
};

/**
 * Get display name for a field.
 * Priority: backendDisplayName (explicit) > backend config (from columns store) > static mapping > beautified label
 * @param fieldName - The technical field name
 * @param backendDisplayName - Optional display name from backend config (Admin Panel)
 */
export function getDisplayName(fieldName: string, backendDisplayName?: string): string {
  // Explicit backend display name takes priority (passed from component)
  if (backendDisplayName) {
    return backendDisplayName;
  }
  
  // Try to get display_name from columns store (backend config / Admin Panel)
  try {
    const columnsStore = useColumnsStore();
    // Check row columns
    const rowCol = columnsStore.rowColumns.find(c => c.column_name === fieldName);
    if (rowCol?.display_name) {
      return rowCol.display_name;
    }
    // Check col columns
    const colCol = columnsStore.colColumns.find(c => c.column_name === fieldName);
    if (colCol?.display_name) {
      return colCol.display_name;
    }
  } catch {
    // Store might not be available yet (during initialization)
  }
  
  // Then check static frontend mappings
  return metadataDisplayNames[fieldName] || beautifyLabel(fieldName);
}

/**
 * Fields that contain sequences (should be excluded by default from tooltips)
 */
export const sequenceFields = ["protein_seq", "rna_seq", "newick_str"];

/**
 * Verbose fields that should be excluded by default from tooltips
 * (too long for typical tooltip display)
 */
export const verboseFields = ["description_long"];

/**
 * Fields that are typically arrays/lists
 */
export const arrayFields = [
  "go_terms",
  "ipr_id",
  "pfam_id",
  "uniprot_term",
  "family",
  "ipr_desc",
  "pfam_desc",
];
