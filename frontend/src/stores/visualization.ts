import { defineStore } from "pinia";
import { DEFAULT_TRAIT_COLUMN, normalizeDefaultTraitColumn, normalizeDefaultTraitColumns } from "@/shared/defaultTrait";

export interface ExpressionDisplayState {
  optionId: string; // 'tpm', 'tmm', 'getmm', 'log2', 'zscore', 'raw'
  layer: string | null; // 'tpm', 'tmm', 'getmm', 'X', or null for auto-select
  transform: 'raw' | 'log2' | 'zscore';
}

export type ClusterMethod = 'average' | 'complete' | 'ward';
export type ClusterDistance = 'correlation' | 'euclidean';

export interface ClusteringState {
  clusterRows: boolean;
  clusterCols: boolean;
  method: ClusterMethod;
  distance: ClusterDistance;
  isComputing: boolean;
  rowOrder: number[] | null;  // Computed cluster order for rows
  colOrder: number[] | null;  // Computed cluster order for columns
  rowOrdersByDataset: Record<string, number[]>;
  colOrdersByDataset: Record<string, number[]>;
}

export interface PhyloTreeState {
  collapsedNodes: string[];  // Node IDs (topology-derived) that are collapsed
  zoomTransform: { k: number; x: number; y: number };  // D3 zoom transform state
  resetCounter: number;  // Incremented on reset to trigger watcher
  selectedOrthogroup: string;  // Currently selected orthogroup for phylotree view
  branchLengthMode: 'cladogram' | 'phylogram';  // Tree x-axis interpretation
  groupingColumn: string;  // Sample metadata column used to aggregate expression
}

export interface CompareState {
  plotType: 'line' | 'box' | 'violin';
  plotHeight: number;
  selectedOrthogroup: string;
  expression: string;
  selectedSpecies: string[];
  showAllTranscripts: boolean;
  groupingColumn: string;
}

export interface VisualizationState {
  rowLabel: boolean;
  colLabel: boolean;
  rowSideColors: string[];
  colSideColors: string[];
  rowOrder: { name: string; order: "asc" | "desc" };
  colOrder: { name: string; order: "asc" | "desc" };
  customColOrder: {
    enabled: boolean;
    mode: "metadata" | "samples";
    metadataColumn: string;
    metadataValues: string[];
    sampleNames: string[];
  };
  colorScale: string;
  expressionDisplay: ExpressionDisplayState;
  legend: boolean;
  oraRowSideColor: boolean;
  oraColumnName: string;
  oraOrder: { name: string; order: "asc" | "desc" };
  significance: string;
  oraTopN: number;
  oraMinCount: number;
  oraGoDepthFilter: string;
  oraAvailableGoDepths: number[];
  oraTooltipFields: string[];
  // Tooltip configuration
  tooltipFields: string[] | null;
  showSequencesInTooltip: boolean;
  sequencePreviewLength: number;
  // Clustering configuration
  clustering: ClusteringState;
  // PhyloTree view state
  phyloTree: PhyloTreeState;
  // Compare view state
  compare: CompareState;
}

function cloneOrderMap(
  value?: Record<string, number[]> | null,
  fallback: Record<string, number[]> = {},
): Record<string, number[]> {
  const source = value && typeof value === 'object' ? value : fallback;
  return Object.fromEntries(
    Object.entries(source).filter(([, order]) => Array.isArray(order)).map(([key, order]) => [key, [...order]]),
  );
}

function normalizePhyloTreeState(state?: Partial<PhyloTreeState> | null): PhyloTreeState {
  const defaults = getDefaultState().phyloTree;
  const zoom = state?.zoomTransform ?? defaults.zoomTransform;

  return {
    ...defaults,
    ...state,
    collapsedNodes: Array.isArray(state?.collapsedNodes) ? [...state.collapsedNodes] : defaults.collapsedNodes,
    zoomTransform: {
      k: typeof zoom.k === 'number' && Number.isFinite(zoom.k) ? zoom.k : defaults.zoomTransform.k,
      x: typeof zoom.x === 'number' && Number.isFinite(zoom.x) ? zoom.x : defaults.zoomTransform.x,
      y: typeof zoom.y === 'number' && Number.isFinite(zoom.y) ? zoom.y : defaults.zoomTransform.y,
    },
    selectedOrthogroup: typeof state?.selectedOrthogroup === 'string' ? state.selectedOrthogroup : defaults.selectedOrthogroup,
    branchLengthMode: state?.branchLengthMode === 'phylogram' || state?.branchLengthMode === 'cladogram'
      ? state.branchLengthMode
      : defaults.branchLengthMode,
    groupingColumn: typeof state?.groupingColumn === 'string' ? state.groupingColumn : defaults.groupingColumn,
    resetCounter: typeof state?.resetCounter === 'number' ? state.resetCounter : defaults.resetCounter,
  };
}

function normalizeCompareState(state?: Partial<CompareState> | null): CompareState {
  const defaults = getDefaultState().compare;

  return {
    ...defaults,
    ...state,
    selectedSpecies: Array.isArray(state?.selectedSpecies) ? [...state.selectedSpecies] : defaults.selectedSpecies,
    selectedOrthogroup: typeof state?.selectedOrthogroup === 'string' ? state.selectedOrthogroup : defaults.selectedOrthogroup,
    groupingColumn: typeof state?.groupingColumn === 'string' ? state.groupingColumn : defaults.groupingColumn,
  };
}

function getDefaultState(): VisualizationState {
  return {
    rowLabel: true,
    colLabel: true,
    rowSideColors: [],  // Will be initialized with ['ortho_id'] if available
    colSideColors: [],
    rowOrder: { name: "", order: "asc" },
    colOrder: { name: "", order: "asc" },
    customColOrder: {
      enabled: false,
      mode: "metadata",
      metadataColumn: DEFAULT_TRAIT_COLUMN,
      metadataValues: [],
      sampleNames: [],
    },
    colorScale: "VIRIDIS",
    expressionDisplay: {
      optionId: "tpm",  // Must match EXPRESSION_OPTIONS id - TPM as default for heatmap
      layer: "tpm",
      transform: "raw"
    },
    legend: true,
    oraRowSideColor: true,
    oraColumnName: "ortho_id",
    oraOrder: { name: "", order: "asc" },
    significance: "0.01",
    oraTopN: 10,
    oraMinCount: 3,
    oraGoDepthFilter: "",
    oraAvailableGoDepths: [],
    oraTooltipFields: ["attribute_name", "go_name", "subset_count", "expected_count", "background_count", "fold_enrichment"],  // Default: attribute + GO name + core enrichment metrics
    tooltipFields: [] as string[], // [] = show no optional metadata in hover tooltip by default
    showSequencesInTooltip: false,
    sequencePreviewLength: 100,
    // Clustering defaults
    clustering: {
      clusterRows: false,
      clusterCols: false,
      method: 'average',      // UPGMA - standard for gene expression
      distance: 'correlation', // Pearson correlation (1-r) - best for expression data
      isComputing: false,
      rowOrder: null,
      colOrder: null,
      rowOrdersByDataset: {},
      colOrdersByDataset: {},
    },
    // PhyloTree view state
    phyloTree: {
      collapsedNodes: [],
      zoomTransform: { k: 1, x: 0, y: 0 },
      resetCounter: 0, // Incremented on reset to trigger watcher
      selectedOrthogroup: '',  // Will be auto-selected when OGs are loaded
      branchLengthMode: 'cladogram',  // Default: cladogram (better readability with skewed branch lengths)
      groupingColumn: '',
    },
    // Compare view state
    compare: {
      plotType: 'line',
      plotHeight: 500,
      selectedOrthogroup: '',
      expression: 'tpm',
      selectedSpecies: [],
      showAllTranscripts: false,
      groupingColumn: '',
    },
  };
}

export const useVisualizationStore = defineStore("visualization", {
  state: (): VisualizationState => getDefaultState(),
  actions: {
    initialize(id_column: string, availableRowColumns?: string[], availableColColumns?: string[]) {
      // Set config-dependent data here
      this.rowOrder.name = id_column;
      this.colOrder.name = DEFAULT_TRAIT_COLUMN;
      this.oraColumnName = "ortho_id"; // Default ORA grouping column — requires ortho_id data
      this.oraOrder.name = "p_value";
      
      // Set default rowSideColors to include 'ortho_id' if available
      if (availableRowColumns && availableRowColumns.includes('ortho_id') && this.rowSideColors.length === 0) {
        this.rowSideColors = ['ortho_id'];
      }
      
      if (availableColColumns && availableColColumns.includes(DEFAULT_TRAIT_COLUMN) && this.colSideColors.length === 0) {
        this.colSideColors = [DEFAULT_TRAIT_COLUMN];
      }
    },
    toggleRowLabel() {
      this.rowLabel = !this.rowLabel;
    },
    toggleColLabel() {
      this.colLabel = !this.colLabel;
    },
    setRowSideColors(selection: string[]) {
      this.rowSideColors = selection;
    },
    setColSideColors(selection: string[]) {
      this.colSideColors = selection;
    },
    setRowOrderName(name: string) {
      this.rowOrder.name = name;
      if (name) {
        this.setClusterRows(false);
      }
    },
    toggleRowOrder() {
      if (this.rowOrder.order === "asc") {
        this.rowOrder.order = "desc";
      } else {
        this.rowOrder.order = "asc";
      }
    },
    setColOrderName(name: string) {
      this.colOrder.name = name;
      if (name) {
        this.setClusterCols(false);
        this.customColOrder.enabled = false;
      }
    },
    setCustomColOrderState(state: Partial<VisualizationState["customColOrder"]>) {
      if (state.enabled) {
        this.setClusterCols(false);
        this.colOrder.name = "";
      }
      this.customColOrder = {
        ...this.customColOrder,
        ...state,
        metadataValues: state.metadataValues ? [...state.metadataValues] : this.customColOrder.metadataValues,
        sampleNames: state.sampleNames ? [...state.sampleNames] : this.customColOrder.sampleNames,
      };
    },
    toggleColOrder() {
      if (this.colOrder.order === "asc") {
        this.colOrder.order = "desc";
      } else {
        this.colOrder.order = "asc";
      }
    },
    setColorScale(scale: string) {
      this.colorScale = scale;
    },
    setExpressionDisplay(optionId: string, layer: string | null, transform: 'raw' | 'log2' | 'zscore') {
      this.expressionDisplay = {
        optionId,
        layer,
        transform
      };
    },
    toggleLegend() {
      this.legend = !this.legend;
    },
    setTooltipFields(fields: string[] | null) {
      this.tooltipFields = fields;
    },
    setOraTooltipFields(fields: string[]) {
      this.oraTooltipFields = fields;
    },
    setOraAvailableGoDepths(depths: number[]) {
      const uniqueDepths = Array.from(new Set(depths.filter((depth) => Number.isInteger(depth) && depth >= 0))).sort((a, b) => a - b);
      this.oraAvailableGoDepths = uniqueDepths;
      if (this.oraGoDepthFilter && !uniqueDepths.includes(Number(this.oraGoDepthFilter))) {
        this.oraGoDepthFilter = "0";
      }
    },
    setOraGoDepthFilter(depth: string | number) {
      const numericDepth = Number(depth);
      this.oraGoDepthFilter = Number.isInteger(numericDepth) && numericDepth > 0 ? String(numericDepth) : "0";
    },
    toggleShowSequencesInTooltip() {
      this.showSequencesInTooltip = !this.showSequencesInTooltip;
    },
    setSequencePreviewLength(length: number) {
      this.sequencePreviewLength = length;
    },
    // Clustering actions
    setClusterRows(enabled: boolean) {
      this.clustering.clusterRows = enabled;
      this.clustering.rowOrder = null;
      this.clustering.rowOrdersByDataset = {};
      if (enabled) {
        this.rowOrder.name = "";
      }
    },
    setClusterCols(enabled: boolean) {
      this.clustering.clusterCols = enabled;
      this.clustering.colOrder = null;
      this.clustering.colOrdersByDataset = {};
      if (enabled) {
        this.colOrder.name = "";
        this.customColOrder.enabled = false;
      }
    },
    setClusterMethod(method: ClusterMethod) {
      this.clustering.method = method;
      // Reset computed orders when method changes
      this.clustering.rowOrder = null;
      this.clustering.colOrder = null;
      this.clustering.rowOrdersByDataset = {};
      this.clustering.colOrdersByDataset = {};
    },
    setClusterDistance(distance: ClusterDistance) {
      this.clustering.distance = distance;
      // Reset computed orders when distance metric changes
      this.clustering.rowOrder = null;
      this.clustering.colOrder = null;
      this.clustering.rowOrdersByDataset = {};
      this.clustering.colOrdersByDataset = {};
    },
    setClusteringComputing(isComputing: boolean) {
      this.clustering.isComputing = isComputing;
    },
    setClusterRowOrder(order: number[] | null, datasetKey?: string) {
      if (datasetKey) {
        if (order) {
          this.clustering.rowOrdersByDataset = {
            ...this.clustering.rowOrdersByDataset,
            [datasetKey]: [...order],
          };
        } else {
          const remaining = { ...this.clustering.rowOrdersByDataset };
          delete remaining[datasetKey];
          this.clustering.rowOrdersByDataset = remaining;
        }
      }
      this.clustering.rowOrder = order;
    },
    setClusterColOrder(order: number[] | null, datasetKey?: string) {
      if (datasetKey) {
        if (order) {
          this.clustering.colOrdersByDataset = {
            ...this.clustering.colOrdersByDataset,
            [datasetKey]: [...order],
          };
        } else {
          const remaining = { ...this.clustering.colOrdersByDataset };
          delete remaining[datasetKey];
          this.clustering.colOrdersByDataset = remaining;
        }
      }
      this.clustering.colOrder = order;
    },
    getClusterRowOrder(datasetKey?: string) {
      return datasetKey ? (this.clustering.rowOrdersByDataset[datasetKey] ?? null) : this.clustering.rowOrder;
    },
    getClusterColOrder(datasetKey?: string) {
      return datasetKey ? (this.clustering.colOrdersByDataset[datasetKey] ?? null) : this.clustering.colOrder;
    },
    // PhyloTree actions
    toggleNodeCollapsed(nodeId: string) {
      const index = this.phyloTree.collapsedNodes.indexOf(nodeId);
      if (index === -1) {
        this.phyloTree.collapsedNodes.push(nodeId);
      } else {
        this.phyloTree.collapsedNodes.splice(index, 1);
      }
    },
    setNodeCollapsed(nodeId: string, collapsed: boolean) {
      const index = this.phyloTree.collapsedNodes.indexOf(nodeId);
      if (collapsed && index === -1) {
        this.phyloTree.collapsedNodes.push(nodeId);
      } else if (!collapsed && index !== -1) {
        this.phyloTree.collapsedNodes.splice(index, 1);
      }
    },
    setPhyloTreeZoom(transform: { k: number; x: number; y: number }) {
      this.phyloTree.zoomTransform = normalizePhyloTreeState({ zoomTransform: transform }).zoomTransform;
    },
    resetPhyloTreeState() {
      this.phyloTree.collapsedNodes = [];
      this.phyloTree.zoomTransform = { k: 1, x: 0, y: 0 };
      this.phyloTree.resetCounter++; // Trigger watcher
    },
    setPhyloCollapsedNodes(ids: string[]) {
      this.phyloTree.collapsedNodes = [...ids];
    },
    setBranchLengthMode(mode: 'cladogram' | 'phylogram') {
      this.phyloTree.branchLengthMode = mode;
    },
    // PhyloTree state setter (like setCompareState)
    setPhyloTreeState(state: Partial<PhyloTreeState>) {
      this.phyloTree = normalizePhyloTreeState({ ...this.phyloTree, ...state });
    },
    // Compare actions
    setCompareState(state: Partial<CompareState>) {
      // Explicitly handle arrays to ensure reactivity
      if (state.selectedSpecies !== undefined) {
        this.compare.selectedSpecies = [...state.selectedSpecies];
      }
      if (state.plotType !== undefined) {
        this.compare.plotType = state.plotType;
      }
      if (state.plotHeight !== undefined) {
        this.compare.plotHeight = state.plotHeight;
      }
      if (state.selectedOrthogroup !== undefined) {
        this.compare.selectedOrthogroup = state.selectedOrthogroup;
      }
      if (state.expression !== undefined) {
        this.compare.expression = state.expression;
      }
      if (state.showAllTranscripts !== undefined) {
        this.compare.showAllTranscripts = state.showAllTranscripts;
      }
      if (state.groupingColumn !== undefined) {
        this.compare.groupingColumn = state.groupingColumn;
      }
    },
    /**
     * Initialize default SideColors after columns are available.
     * Should be called from HeatmapComponent after data is fetched.
     */
    initializeDefaultSideColors(availableRowColumns: string[], availableColColumns: string[]) {
      // Only set defaults if not already configured
      if (this.rowSideColors.length === 0 && availableRowColumns.includes('ortho_id')) {
        this.rowSideColors = ['ortho_id'];
      }
      if (this.colSideColors.length === 0 && availableColColumns.includes(DEFAULT_TRAIT_COLUMN)) {
        this.colSideColors = [DEFAULT_TRAIT_COLUMN];
      }
    },
    reset() {
      const defaultState = getDefaultState();
      const row_id_column = this.rowOrder.name;

      this.$patch(defaultState);

      this.initialize(row_id_column);
    },
    replaceState(newState: Partial<VisualizationState>) {
      Object.entries(newState).forEach(([key, value]) => {
        if (key in this) {
          if (key === 'phyloTree') {
            this.phyloTree = normalizePhyloTreeState({ ...this.phyloTree, ...(value as Partial<PhyloTreeState>) });
          } else if (key === 'compare') {
            this.compare = normalizeCompareState({ ...this.compare, ...(value as Partial<CompareState>) });
          } else if (key === 'customColOrder') {
            const customOrder = value as Partial<VisualizationState["customColOrder"]>;
            this.customColOrder = {
              ...this.customColOrder,
              ...customOrder,
              metadataColumn: normalizeDefaultTraitColumn(customOrder.metadataColumn ?? this.customColOrder.metadataColumn),
              metadataValues: Array.isArray(customOrder.metadataValues) ? [...customOrder.metadataValues] : this.customColOrder.metadataValues,
              sampleNames: Array.isArray(customOrder.sampleNames) ? [...customOrder.sampleNames] : this.customColOrder.sampleNames,
            };
          } else if (key === 'colSideColors') {
            this.colSideColors = Array.isArray(value) ? normalizeDefaultTraitColumns(value as string[]) : this.colSideColors;
          } else if (key === 'colOrder') {
            const order = value as VisualizationState["colOrder"];
            this.colOrder = { ...this.colOrder, ...order, name: normalizeDefaultTraitColumn(order.name) };
          } else if (key === 'clustering') {
            const clustering = value as Partial<ClusteringState>;
            this.clustering = {
              ...this.clustering,
              ...clustering,
              rowOrder: Array.isArray(clustering.rowOrder)
                ? [...clustering.rowOrder]
                : clustering.rowOrder === null
                  ? null
                  : this.clustering.rowOrder,
              colOrder: Array.isArray(clustering.colOrder)
                ? [...clustering.colOrder]
                : clustering.colOrder === null
                  ? null
                  : this.clustering.colOrder,
              rowOrdersByDataset: cloneOrderMap(clustering.rowOrdersByDataset, this.clustering.rowOrdersByDataset),
              colOrdersByDataset: cloneOrderMap(clustering.colOrdersByDataset, this.clustering.colOrdersByDataset),
            };
          } else {
            this[key] = value;
          }
        }
      });
    },
    toObject() {
      return {
        rowLabel: this.rowLabel,
        colLabel: this.colLabel,
        rowSideColors: [...this.rowSideColors], // shallow copy arrays
        colSideColors: [...this.colSideColors],
        rowOrder: { ...this.rowOrder }, // shallow copy object
        colOrder: { ...this.colOrder },
        customColOrder: {
          ...this.customColOrder,
          metadataValues: [...this.customColOrder.metadataValues],
          sampleNames: [...this.customColOrder.sampleNames],
        },
        colorScale: this.colorScale,
        expressionDisplay: { ...this.expressionDisplay },
        legend: this.legend,
        oraRowSideColor: this.oraRowSideColor,
        oraColumnName: this.oraColumnName,
        oraOrder: { ...this.oraOrder },
        significance: this.significance,
        oraTopN: this.oraTopN,
        oraMinCount: this.oraMinCount,
        oraGoDepthFilter: this.oraGoDepthFilter,
        oraTooltipFields: [...this.oraTooltipFields],
        ...(this.tooltipFields !== null ? { tooltipFields: [...this.tooltipFields] } : {}),
        showSequencesInTooltip: this.showSequencesInTooltip,
        sequencePreviewLength: this.sequencePreviewLength,
        clustering: {
          ...this.clustering,
          rowOrder: this.clustering.rowOrder ? [...this.clustering.rowOrder] : null,
          colOrder: this.clustering.colOrder ? [...this.clustering.colOrder] : null,
          rowOrdersByDataset: cloneOrderMap(this.clustering.rowOrdersByDataset),
          colOrdersByDataset: cloneOrderMap(this.clustering.colOrdersByDataset),
        },
        phyloTree: {
          collapsedNodes: [...this.phyloTree.collapsedNodes],
          zoomTransform: { ...this.phyloTree.zoomTransform },
          resetCounter: this.phyloTree.resetCounter,
          selectedOrthogroup: this.phyloTree.selectedOrthogroup,
          branchLengthMode: this.phyloTree.branchLengthMode,
          groupingColumn: this.phyloTree.groupingColumn,
        },
        compare: {
          plotType: this.compare.plotType,
          plotHeight: this.compare.plotHeight,
          selectedOrthogroup: this.compare.selectedOrthogroup,
          expression: this.compare.expression,
          selectedSpecies: [...this.compare.selectedSpecies],
          showAllTranscripts: this.compare.showAllTranscripts,
          groupingColumn: this.compare.groupingColumn,
        },
      };
    },
  },
});
