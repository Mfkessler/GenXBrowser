/**
 * Dynamic Data Type Labels Configuration
 * 
 * Provides terminology based on VITE_DATA_TYPE environment variable:
 * - "Isoforms" → Uses "Transcript/Transcripts" terminology
 * - "Genes" (or any other value) → Uses "Gene/Genes" terminology
 * 
 * This allows the same application to be used for different data types
 * (gene-level expression vs. transcript/isoform-level expression).
 */

export type DataType = 'Isoforms' | 'Genes';

// Read from environment variable, default to 'Genes'
const dataType: DataType = (import.meta.env.VITE_DATA_TYPE as DataType) || 'Genes';

/**
 * Get the singular form (e.g., "Gene" or "Transcript")
 */
export function getEntityLabel(): string {
  return dataType === 'Isoforms' ? 'Transcript' : 'Gene';
}

/**
 * Get the plural form (e.g., "Genes" or "Transcripts")
 */
export function getEntityLabelPlural(): string {
  return dataType === 'Isoforms' ? 'Transcripts' : 'Genes';
}

/**
 * Get lowercase singular form (e.g., "gene" or "transcript")
 */
export function getEntityLabelLower(): string {
  return getEntityLabel().toLowerCase();
}

/**
 * Get lowercase plural form (e.g., "genes" or "transcripts")
 */
export function getEntityLabelPluralLower(): string {
  return getEntityLabelPlural().toLowerCase();
}

/**
 * Get the ID label (e.g., "Gene ID" or "Transcript ID")
 */
export function getEntityIdLabel(): string {
  return `${getEntityLabel()} ID`;
}

/**
 * Get the metadata label (e.g., "Gene Metadata" or "Transcript Metadata")
 */
export function getEntityMetadataLabel(): string {
  return `${getEntityLabel()} Metadata`;
}

/**
 * Get the count label (e.g., "Gene Count" or "Transcript Count")
 */
export function getEntityCountLabel(): string {
  return `${getEntityLabel()} Count`;
}

/**
 * Get the set label (e.g., "Gene Set" or "Transcript Set")
 */
export function getEntitySetLabel(): string {
  return `${getEntityLabel()} Set`;
}

/**
 * Get minimum count label for ORA (e.g., "Minimum Gene Count")
 */
export function getMinimumCountLabel(): string {
  return `Minimum ${getEntityLabel()} Count`;
}

/**
 * Get columns label for admin (e.g., "Gene Metadata Columns" or "Transcript Metadata Columns")
 */
export function getEntityMetadataColumnsLabel(): string {
  return `${getEntityLabel()} Metadata Columns`;
}

/**
 * Export current data type for conditional logic if needed
 */
export const currentDataType: DataType = dataType;

/**
 * Check if using Isoforms/Transcripts terminology
 */
export function isIsoformMode(): boolean {
  return dataType === 'Isoforms';
}

/**
 * Check if using Genes terminology
 */
export function isGeneMode(): boolean {
  return dataType === 'Genes';
}
