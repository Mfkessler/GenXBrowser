import { defineStore } from "pinia";

import { beautifyLabel } from "@/shared/utils";

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
}

export interface PhyloTreeState {
  collapsedNodes: string[];  // Node IDs (topology-derived) that are collapsed
  zoomTransform: { k: number; x: number; y: number };  // D3 zoom transform state
  resetCounter: number;  // Incremented on reset to trigger watcher
  selectedOrthogroup: string;  // Currently selected orthogroup for phylotree view
  branchLengthMode: 'cladogram' | 'phylogram';  // Tree x-axis interpretation
}

export interface CompareState {
  plotType: 'line' | 'box' | 'violin';
  plotHeight: number;
  selectedOrthogroup: string;
  expression: string;
  selectedSpecies: string[];
  showAllTranscripts: boolean;
}

export interface VisualizationState {
  rowLabel: boolean;
  colLabel: boolean;
  rowSideColors: string[];
  colSideColors: string[];
  rowOrder: { name: string; order: "asc" | "desc" };
  colOrder: { name: string; order: "asc" | "desc" };
  colorScale: string;
  expressionDisplay: ExpressionDisplayState;
  hideEmpty: boolean;
  legend: boolean;
  oraRowSideColor: boolean;
  oraColumnName: string;
  oraOrder: { name: string; order: "asc" | "desc" };
  significance: string;
  oraTopN: number;
  oraMinCount: number;
  oraTopologicalFilter: boolean;
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

function getDefaultState(): VisualizationState {
  return {
    rowLabel: true,
    colLabel: true,
    rowSideColors: [],  // Will be initialized with ['ortho_id'] if available
    colSideColors: [],  // Will be initialized with ['tissue_types'] if available
    rowOrder: { name: "", order: "asc" },
    colOrder: { name: "", order: "asc" },
    colorScale: "VIRIDIS",
    expressionDisplay: {
      optionId: "tpm",  // Must match EXPRESSION_OPTIONS id - TPM as default for heatmap
      layer: "tpm",
      transform: "raw"
    },
    hideEmpty: true,  // Default: hide empty columns
    legend: true,
    oraRowSideColor: true,
    oraColumnName: "ortho_id",
    oraOrder: { name: "", order: "asc" },
    significance: "0.01",
    oraTopN: 50,
    oraMinCount: 3,
    oraTopologicalFilter: false,  // Default: false for GO term topological filtering
    oraTooltipFields: ["attribute_name", "go_name", "subset_count", "expected_count", "background_count", "fold_enrichment"],  // Default: attribute + GO name + core enrichment metrics
    tooltipFields: null, // null = uninitialized (show all); [] = user deselected all (show none)
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
    },
    // PhyloTree view state
    phyloTree: {
      collapsedNodes: [],
      zoomTransform: { k: 1, x: 0, y: 0 },
      resetCounter: 0, // Incremented on reset to trigger watcher
      selectedOrthogroup: '',  // Will be auto-selected when OGs are loaded
      branchLengthMode: 'cladogram',  // Default: cladogram (better readability with skewed branch lengths)
    },
    // Compare view state
    compare: {
      plotType: 'line',
      plotHeight: 500,
      selectedOrthogroup: '',
      expression: 'tpm',
      selectedSpecies: [],
      showAllTranscripts: false,
    },
  };
}

export const useVisualizationStore = defineStore("visualization", {
  state: (): VisualizationState => getDefaultState(),
  actions: {
    initialize(id_column: string, availableRowColumns?: string[], availableColColumns?: string[]) {
      // Set config-dependent data here
      this.rowOrder.name = id_column;
      this.colOrder.name = "tissue_types"; // Default column order — assumes tissue_types is available
      this.oraColumnName = "ortho_id"; // Default ORA grouping column — requires ortho_id data
      this.oraOrder.name = "p_value";
      
      // Set default rowSideColors to include 'ortho_id' if available
      if (availableRowColumns && availableRowColumns.includes('ortho_id') && this.rowSideColors.length === 0) {
        this.rowSideColors = ['ortho_id'];
      }
      
      // Set default colSideColors to include 'tissue_types' if available
      if (availableColColumns && availableColColumns.includes('tissue_types') && this.colSideColors.length === 0) {
        this.colSideColors = ['tissue_types'];
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
    toggleHideEmpty() {
      this.hideEmpty = !this.hideEmpty;
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
    toggleShowSequencesInTooltip() {
      this.showSequencesInTooltip = !this.showSequencesInTooltip;
    },
    setSequencePreviewLength(length: number) {
      this.sequencePreviewLength = length;
    },
    // Clustering actions
    setClusterRows(enabled: boolean) {
      this.clustering.clusterRows = enabled;
      if (!enabled) {
        this.clustering.rowOrder = null;
      }
    },
    setClusterCols(enabled: boolean) {
      this.clustering.clusterCols = enabled;
      if (!enabled) {
        this.clustering.colOrder = null;
      }
    },
    setClusterMethod(method: ClusterMethod) {
      this.clustering.method = method;
      // Reset computed orders when method changes
      this.clustering.rowOrder = null;
      this.clustering.colOrder = null;
    },
    setClusterDistance(distance: ClusterDistance) {
      this.clustering.distance = distance;
      // Reset computed orders when distance metric changes
      this.clustering.rowOrder = null;
      this.clustering.colOrder = null;
    },
    setClusteringComputing(isComputing: boolean) {
      this.clustering.isComputing = isComputing;
    },
    setClusterRowOrder(order: number[] | null) {
      this.clustering.rowOrder = order;
    },
    setClusterColOrder(order: number[] | null) {
      this.clustering.colOrder = order;
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
      this.phyloTree.zoomTransform = transform;
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
      Object.assign(this.phyloTree, state);
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
      if (this.colSideColors.length === 0 && availableColColumns.includes('tissue_types')) {
        this.colSideColors = ['tissue_types'];
      }
    },
    reset() {
      const defaultState = getDefaultState();
      const row_id_column = this.rowOrder.name;

      Object.entries(defaultState).forEach(([key, value]) => {
        (this as any)[key] = value;
      });

      this.initialize(row_id_column);
    },
    replaceState(newState: Partial<VisualizationState>) {
      Object.entries(newState).forEach(([key, value]) => {
        if (key in this) {
          this[key] = value;
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
        colorScale: this.colorScale,
        expressionDisplay: { ...this.expressionDisplay },
        hideEmpty: this.hideEmpty,
        legend: this.legend,
        oraRowSideColor: this.oraRowSideColor,
        oraColumnName: this.oraColumnName,
        oraOrder: { ...this.oraOrder },
        significance: this.significance,
        oraTopN: this.oraTopN,
        oraMinCount: this.oraMinCount,
        tooltipFields: this.tooltipFields !== null ? [...this.tooltipFields] : null,
        showSequencesInTooltip: this.showSequencesInTooltip,
        sequencePreviewLength: this.sequencePreviewLength,
        clustering: { ...this.clustering },
        phyloTree: {
          collapsedNodes: [...this.phyloTree.collapsedNodes],
          zoomTransform: { ...this.phyloTree.zoomTransform },
          selectedOrthogroup: this.phyloTree.selectedOrthogroup,
          branchLengthMode: this.phyloTree.branchLengthMode,
        },
        compare: {
          plotType: this.compare.plotType,
          plotHeight: this.compare.plotHeight,
          selectedOrthogroup: this.compare.selectedOrthogroup,
          expression: this.compare.expression,
          selectedSpecies: [...this.compare.selectedSpecies],
          showAllTranscripts: this.compare.showAllTranscripts,
        },
      };
    },
  },
});
