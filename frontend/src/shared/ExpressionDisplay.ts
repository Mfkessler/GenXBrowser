/**
 * Expression Display Configuration (inspired by CoNExUS)
 * ======================================================
 * Defines available expression layers, transformations, and their metadata.
 * Used for heatmaps, phylogenetic trees, and comparison views.
 */

export interface LayerDescription {
  name: string;
  short: string;
  description: string;
  useCase: string;
  isLog: boolean;
}

export interface TransformRecommendation {
  preferred: string | null;
  fallbacks: string[];
  reasoning: string;
  avoid?: string[];
}

export interface ExpressionOption {
  id: string;
  label: string;
  layer: string | null; // null means auto-select
  transform: 'raw' | 'log2' | 'zscore';
  description: string;
  useCase: string;
}

// Layer metadata (matches backend LAYER_DESCRIPTIONS)
export const LAYER_DESCRIPTIONS: Record<string, LayerDescription> = {
  X: {
    name: 'Raw Counts',
    short: 'RAW',
    description: 'Main expression matrix - unprocessed read counts',
    useCase: 'Direct count data from sequencing',
    isLog: false,
  },
  tpm: {
    name: 'TPM',
    short: 'TPM',
    description:
      'Transcripts Per Million. Within-sample normalization that accounts for gene length and sequencing depth.',
    useCase: 'Compare gene expression levels WITHIN a single sample',
    isLog: false,
  },
  tmm: {
    name: 'TMM',
    short: 'TMM',
    description:
      'Trimmed Mean of M-values (edgeR). Between-sample normalization for comparing expression across samples.',
    useCase: 'Compare expression levels BETWEEN different samples/conditions',
    isLog: false,
  },
  getmm: {
    name: 'GeTMM',
    short: 'GeTMM',
    description:
      'Gene-length corrected TMM. Combines between-sample TMM normalization with gene-length correction (similar to TPM).',
    useCase: 'Accounts for gene length AND provides between-sample normalization.',
    isLog: false,
  },
  'log-cpm': {
    name: 'log-CPM',
    short: 'logCPM',
    description: 'Log2 Counts Per Million - already log-transformed normalized counts',
    useCase: 'Pre-transformed data for downstream analysis',
    isLog: true,
  },
};

// Transform-to-layer recommendations (matches backend)
export const TRANSFORM_LAYER_RECOMMENDATIONS: Record<string, TransformRecommendation> = {
  log2: {
    preferred: 'tpm',
    fallbacks: ['tmm', 'X'],
    reasoning: 'Log2(x+1) on TPM provides comparable log-expression values',
    avoid: ['log-cpm'], // Already log-transformed
  },
  zscore: {
    preferred: 'getmm', // GeTMM is gene-length corrected AND between-sample normalized
    fallbacks: ['tmm', 'tpm', 'log-cpm', 'X'],
    reasoning: 'GeTMM provides gene-length correction with between-sample normalization, optimal for Z-score',
  },
  raw: {
    preferred: null, // User chooses
    fallbacks: [],
    reasoning: 'Display values directly from selected layer without transformation',
  },
};

// Expression display options for dropdown (with section headers)
export const EXPRESSION_OPTIONS: ExpressionOption[] = [
  // === Normalized Values ===
  {
    id: 'tpm',
    label: 'TPM (within-sample)',
    layer: 'tpm',
    transform: 'raw',
    description: 'Transcripts Per Million - normalized for gene length and sequencing depth',
    useCase: 'Compare genes within the same sample',
  },
  {
    id: 'tmm',
    label: 'TMM (between-sample)',
    layer: 'tmm',
    transform: 'raw',
    description: 'Trimmed Mean of M-values - normalized for library size differences',
    useCase: 'Compare expression across different samples',
  },
  {
    id: 'getmm',
    label: 'GeTMM (gene-length corrected)',
    layer: 'getmm',
    transform: 'raw',
    description: 'Gene-length corrected TMM - best of both worlds',
    useCase: 'Cross-sample comparisons with gene-length correction',
  },

  // === Transformations ===
  {
    id: 'log2',
    label: 'Log₂ (on TPM)',
    layer: null, // Auto-select (prefers tpm)
    transform: 'log2',
    description: 'Log₂(x+1) transformation applied to TPM values',
    useCase: 'Compress dynamic range for better visualization',
  },
  {
    id: 'zscore',
    label: 'Z-Score (on GeTMM)',
    layer: null, // Auto-select (prefers getmm)
    transform: 'zscore',
    description: 'Standardized values (mean=0, SD=1) on GeTMM-normalized data',
    useCase: 'Highlight relative expression patterns across samples',
  },
  {
    id: 'zscore-tpm',
    label: 'Z-Score (on TPM)',
    layer: 'tpm',
    transform: 'zscore',
    description: 'Standardized values (mean=0, SD=1) on TPM-normalized data',
    useCase: 'Z-score with within-sample gene length normalization',
  },

  // === Raw Data ===
  {
    id: 'raw',
    label: 'Raw Counts',
    layer: 'raw',
    transform: 'raw',
    description: 'Unprocessed read counts directly from sequencing',
    useCase: 'Raw data for custom normalization or QC',
  },
];

// Section headers for dropdown grouping
export const EXPRESSION_SECTIONS = [
  {
    label: '— Normalized Values —',
    optionIds: ['tpm', 'tmm', 'getmm'],
  },
  {
    label: '— Transformations —',
    optionIds: ['log2', 'zscore', 'zscore-tpm'],
  },
  {
    label: '— Raw Data —',
    optionIds: ['raw'],
  },
];

// Tooltip text for the Expression label
export const EXPRESSION_INFO_TOOLTIP = `
<strong>Expression Display Methods:</strong><br/>
<br/>
<strong>Normalized Values:</strong> Scale expression for fair comparisons<br/>
• <strong>TPM</strong>: Compare genes <em>within</em> a sample<br/>
• <strong>TMM</strong>: Compare expression <em>between</em> samples<br/>
• <strong>GeTMM</strong>: Gene-length corrected TMM<br/>
<br/>
<strong>Transformations:</strong> Mathematical adjustments for visualization<br/>
• <strong>Log₂</strong>: Compress range (makes fold-changes symmetric)<br/>
• <strong>Z-Score (GeTMM)</strong>: Standardize with gene-length correction<br/>
• <strong>Z-Score (TPM)</strong>: Standardize with within-sample normalization<br/>
<br/>
<strong>Raw Data:</strong> Unprocessed counts from sequencing
`;

// Helper function to get option by ID
export function getExpressionOption(id: string): ExpressionOption | undefined {
  return EXPRESSION_OPTIONS.find((opt) => opt.id === id);
}

// Helper function to get layer description
export function getLayerDescription(layer: string): LayerDescription | undefined {
  return LAYER_DESCRIPTIONS[layer];
}
