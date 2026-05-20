<template>
  <main class="relative flex flex-col flex-1 min-h-[34rem] w-full min-w-0 border border-gray-300 rounded-lg sm:rounded-2xl bg-white shadow-sm overflow-hidden">

    <div v-if="loading && !props.externalLoadingOverlay" class="absolute inset-0 z-50">
      <LoadingOverlay
        primaryStatus="Generating phylogenetic tree..."
        :currentPhaseHint="loadingPhaseHint"
        cancellable
        @cancel="cancelActiveLoad"
      />
    </div>

    <div v-if="newickstr !== null" class="flex-grow relative w-full flex flex-col min-h-0">
      <!-- Phylogenetic Tree Title + Buttons in same row -->
      <div v-if="Object.keys(commonOGs_options).length > 0" class="flex flex-wrap items-center gap-3 mb-1 p-3 bg-gray-50 rounded-lg border border-gray-200 flex-shrink-0 min-w-0">
        <!-- Orthogroup Selector - same styling as Compare view -->
        <div class="flex-grow min-w-0 sm:min-w-48">
          <DropdownMenu
            placeholder="Select orthogroup"
            v-model="selectedOrthogroup"
            :options="commonOGs_options"
          />
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-2 ml-auto flex-shrink-0">
          <button
            aria-label="Share the phylogenetic tree"
            @click="showShareOverlay = true"
            class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white transition"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              fill="currentColor"
              viewBox="0 0 16 16"
            >
              <path
                d="M13.5 1a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3M11 2.5a2.5 2.5 0 1 1 .603 1.628l-6.718 3.12a2.5 2.5 0 0 1 0 1.504l6.718 3.12a2.5 2.5 0 1 1-.488.876l-6.718-3.12a2.5 2.5 0 1 1 0-3.256l6.718-3.12A2.5 2.5 0 0 1 11 2.5m-8.5 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3m11 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3"
              />
            </svg>
          </button>
          <button
            aria-label="Export data"
            @click="showExportModal = true"
            class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white transition"
            v-tooltip="'Export data'"
          >
            <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1m-4-4-4 4m0 0-4-4m4 4V4" />
            </svg>
          </button>
          <button
            class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900 transition"
            @click="emit('openSettingsOverlay')"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-5 w-5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <circle cx="12" cy="12" r="3"/>
              <path
                d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
              />
            </svg>
          </button>
        </div>
      </div>
      <div
        ref="phylotreeContainer"
        id="phylotreeContainer"
        class="bg-white p-1 w-full min-w-0 overflow-hidden flex-1 min-h-[28rem] relative"
      ></div>
    </div>

    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(phylotreeContainer)"
      @close="showShareOverlay = false"
    />

    <ExportModal
      v-if="showExportModal"
      :data="phyloExportPayload.data"
      :columns="phyloExportPayload.columns"
      :columnDisplayNames="phyloExportColumnDisplayNames"
      :metaColumns="phyloExportPayload.metaColumns"
      :sampleColumns="phyloExportPayload.sampleColumns"
      :filename="phyloExportPayload.filename"
      :hasFilters="phyloExportPayload.hasFilters"
      :totalCount="phyloExportPayload.data.length"
      @close="showExportModal = false"
    />

    <!-- Tooltip Modal for detailed cell info -->
    <TooltipModal
      v-if="selectedRowData"
      :show="showTooltipModal"
      :row-data="selectedRowData"
      :table-name="selectedTableName"
      :column-value="selectedColumnValue"
      :cell-value="selectedCellValue"
      :id-column="config.visualization.id_column"
      :heatmap-cols="heatmapCols"
      @close="closeTooltipModal"
    />

    <div v-if="!loading && noNewickResolved && newickstr===null" class="flex-grow relative min-h-[34rem] w-full">
      <NoNewickComponent
        :og="og"
        :show-full-tree="fullTreeAvailable"
        :message="noNewickMessage"
        @show-full-tree="loadFullNewickForOG"
      />
    </div>


  </main>
</template>

<!-- eslint-disable @typescript-eslint/no-explicit-any -->
<script setup lang="ts">

import axios from "axios";
import { storeToRefs } from "pinia";
import { onMounted, onUnmounted, ref, computed, toRaw, watch, unref, inject, nextTick } from 'vue'
import '../assets/phylotree.css'
import * as d3 from "d3";
import { parseNewick } from "@/utils/newick";
import {
  buildHierarchy,
  applyCollapse,
  layout as computePhyloLayout,
  collapseToSpeciesIds,
  type LayoutNode,
  type PhyloDatum,
} from "@/utils/phyloLayout";
import { API_BASE_URL } from "@/shared/Config.ts";
import { COLORSCALES } from "@/shared/Colorscales.ts";
import type { MetaFormat } from "@/shared/MetaFormat.ts";
import type { RowType } from "@/shared/RowType.ts";
import { assign } from "lodash-es";
import { useFiltersStore } from "@/stores/filters.ts";
import { useVisualizationStore } from "@/stores/visualization.ts";
import { useColumnsStore } from "@/stores/columns.ts";
import { getExpressionOption } from "@/shared/ExpressionDisplay.ts";
import ShareOverlay from "@/components/ShareOverlay.vue";
import ExportModal from "@/components/ExportModal.vue";
import LoadingOverlay from "@/components/LoadingOverlay.vue";
import NoNewickComponent from "@/components/NoNewickComponent.vue";
import TooltipModal from "@/components/TooltipModal.vue";
import DropdownMenu from "@/components/DropdownMenu.vue";
import { getDisplayName } from "@/shared/metadataDisplayNames";
import { beautifyLabel } from "@/shared/utils";
import { getEntityIdLabel } from "@/shared/dataTypeLabels";
import {
  omitFilterKey,
  buildOrthogroupOnlyFilters,
  buildOrthogroupScopedFilters,
  hasNonOrthogroupFilters,
} from "@/shared/orthogroupFilters";
import { buildPhyloMetricKeys, matchLeafToDataset, resolvePhyloLeafMatch } from "@/shared/phyloLeafMatching";
import type { Config } from "@/shared/Config";
import { hierarchicalCluster } from "@/shared/clustering";
import { useFilterSeparation } from "@/shared/useFilterSeparation";
import { useRoute, useRouter } from 'vue-router';

const config = inject("config") as Config;
const phylotreeContainer = ref<HTMLDivElement | null>(null);
const showShareOverlay = ref(false);
const showExportModal = ref(false);
const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const columnStore = useColumnsStore();
const {filters} = storeToRefs(filtersStore);
const { sampleFilters } = useFilterSeparation();
const tableData = ref<Record<string, any[]>>({});

// Router for URL state management
const route = useRoute();
const router = useRouter();
const initialUrlParsing = ref(true);

// Available orthogroups (extracted from newick data).
// This is the canonical dropdown source.  It is rebuilt ONLY when the
// catalog filter context (sidebar filters + selected datasets) actually
// changes — never when the user merely picks a different OG from the
// dropdown.  We guard against accidental rebuilds with a signature.
const commonOGs_array = ref<string[]>([]);
let lastOgListFilterSig: string | null = null;

function computeFilterSignature(): string {
  // Sample the catalog filter context: per-dataset merged filters (minus
  // ortho_id), sample filters, and the dataset id filters / filter-chain
  // version.  Anything that changes the catalog-level OG list belongs
  // here; anything that only affects the currently rendered OG (like
  // selectedOrthogroup) does NOT.
  const datasets = props.existingTables && props.existingTables.length > 0
    ? [...props.existingTables]
    : [props.tableName];
  const perDataset = datasets.map((t) => {
    const f = omitFilterKey(filtersStore.getMergedFilters(t));
    return [t, f];
  });
  return JSON.stringify({
    datasets,
    perDataset,
    sample: sampleFilters.value,
    datasetIds: filtersStore.datasetIdFilters,
    chain: filtersStore.filterChainVersion,
  });
}

// Tooltip modal state
const showTooltipModal = ref(false);
const selectedRowData = ref<RowType | null>(null);
const selectedTableName = ref("");
const selectedColumnValue = ref("");
const selectedCellValue = ref<string | number>("");
const heatmapCols = ref<string[]>([]);

// Hidden nodes/species tracking - now managed via visualizationStore.phyloTree
// Local refs for species hiding (not persisted, but could be in future)
const hiddenSpecies = ref<Set<string>>(new Set());
// Use store for collapsed nodes (persisted)
const collapsedNodes = computed(() => new Set(visualizationStore.phyloTree.collapsedNodes));

// Zoom behavior reference
let currentZoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;

// Cached parsed hierarchy of the current tree (used for view-level collapse actions)
const fullHierarchy = ref<d3.HierarchyNode<PhyloDatum> | null>(null);
// Cached metrics from the last data fetch — used for cheap re-render on collapse / mode change.
const lastMetrics = ref<any>(null);

const closeTooltipModal = () => {
  showTooltipModal.value = false;
  selectedRowData.value = null;
  selectedTableName.value = "";
  selectedColumnValue.value = "";
  selectedCellValue.value = "";
};

const emit = defineEmits(['openSettingsOverlay', 'update:tableName', 'update:orthogroupOptions', 'update:loadingState', 'load-cancel']);

const rows = ref<RowType[]>([]);
const columnNames = ref<string[]>([]);
const dataColumnNames = ref<string[]>([]);
const columns = ref<RowType[]>([]);
const newicks = ref<Record<string, string>>({});
const orthogroupCaseMap = ref<Record<string, string>>({});
const highlightedGeneIds = ref<Record<string, Set<string>>>({});
const newickstr = ref<string | null>(null);
const loading = ref(true);
const loadingProgress = ref<number | null>(null);
const loadingPhaseHint = ref("Preparing tree request...");
let loadingProgressStart = 0;
let loadingProgressEnd = 100;
const fullTreeAvailable = ref(false);
const noNewickResolved = ref(false);
const noNewickMessage = ref("");
// Holds the full (unfiltered) Newick loaded via the "Show full tree" button.
// Acts as fallback in renderTreeForSelectedOG so watchers don't wipe it out.
const fullNewick = ref<string | null>(null);
let loadRequestSeq = 0;
let activeAbortController: AbortController | null = null;
// Separate sequence + abort controller for the catalog-level orthogroup
// index fetch (`fetchAllSelected`).  This MUST be independent of the
// render-tree controller above: otherwise concurrent watchers (hashLoading
// + tableNameOptions + selectedOrthogroup) cancel each other mid-flight
// and `commonOGs_array` is never populated, leaving the dropdown empty.
let ogListRequestSeq = 0;
let activeOgListAbortController: AbortController | null = null;
let suppressSelectedOrthogroupWatcher = false;
let activeRenderSignature: string | null = null;
let lastCompletedRenderSignature: string | null = null;

type PhyloLoadTraceWindow = Window & {
  __phyloLoadTrace?: Array<Record<string, unknown>>;
};

function tracePhyloLoad(event: string, details: Record<string, unknown> = {}) {
  if (typeof window === "undefined") return;
  const traceEnabled = import.meta.env.DEV || window.localStorage.getItem("phyloLoadTrace") === "1";
  if (!traceEnabled) return;
  const target = window as PhyloLoadTraceWindow;
  const entry = {
    at: new Date().toISOString(),
    event,
    og: selectedOrthogroup.value,
    loading: loading.value,
    progress: loadingProgress.value,
    ...details,
  };
  target.__phyloLoadTrace = [...(target.__phyloLoadTrace ?? []).slice(-99), entry];
  if (import.meta.env.DEV) console.debug("[PhyloLoad]", entry);
}

function currentRenderSignature(): string {
  return JSON.stringify({
    og: selectedOrthogroupKey(),
    expression: visualizationStore.expressionDisplay,
    colorScale: visualizationStore.colorScale,
    legend: visualizationStore.legend,
    clustering: visualizationStore.clustering,
    groupingColumn: selectedGroupingColumn.value,
    branchLengthMode: visualizationStore.phyloTree.branchLengthMode,
    collapsedNodes: visualizationStore.phyloTree.collapsedNodes,
    tableNames: props.existingTables?.length ? props.existingTables : [props.tableName],
  });
}

function setLoadingProgress(step: number, totalSteps: number) {
  if (totalSteps <= 0) {
    loadingProgress.value = null;
    return;
  }
  const localProgress = Math.min(1, Math.max(0, step / totalSteps));
  loadingProgress.value = loadingProgressStart + (loadingProgressEnd - loadingProgressStart) * localProgress;
}

function setLoadingProgressScope(start: number, end: number) {
  loadingProgressStart = Math.min(100, Math.max(0, start));
  loadingProgressEnd = Math.min(100, Math.max(loadingProgressStart, end));
}

function setLoadingPhaseHint(phaseHint: string) {
  loadingPhaseHint.value = phaseHint;
}

function isCanceledRequest(error: unknown) {
  return axios.isCancel(error) || (axios.isAxiosError(error) && error.code === "ERR_CANCELED");
}

function cancelActiveLoad(emitCancel = true) {
  loadRequestSeq += 1;
  activeAbortController?.abort();
  activeAbortController = null;
  ogListRequestSeq += 1;
  activeOgListAbortController?.abort();
  activeOgListAbortController = null;
  loading.value = false;
  loadingProgress.value = null;
  setLoadingPhaseHint("Load canceled");
  if (emitCancel) emit('load-cancel');
}

watch(
  [loading, loadingProgress, loadingPhaseHint],
  () => emit('update:loadingState', { loading: loading.value, progress: loadingProgress.value, phaseHint: loadingPhaseHint.value }),
  { immediate: true },
);

const selectedGroupingColumn = computed(() => {
  const configured = visualizationStore.phyloTree.groupingColumn;
  if (configured && columnStore.filterableColColumns.some((col) => col.column_name === configured)) {
    return configured;
  }
  return columnStore.tissueColumnName || columnStore.filterableColColumns[0]?.column_name || 'tissue';
});

const groupingColumnLabel = computed(() => {
  const column = columnStore.filterableColColumns.find((col) => col.column_name === selectedGroupingColumn.value);
  return (column?.display_name || selectedGroupingColumn.value || 'sample group').toString();
});

// Selected orthogroup - computed property linked to store
const selectedOrthogroup = computed({
  get: () => visualizationStore.phyloTree.selectedOrthogroup,
  set: (v: string) => {
    if (v === visualizationStore.phyloTree.selectedOrthogroup) return;
    visualizationStore.phyloTree.selectedOrthogroup = v;
  }
});

// Alias for template compatibility
const og = computed(() => selectedOrthogroup.value);

function selectedOrthogroupKey(): string {
  return selectedOrthogroup.value.trim().toLowerCase();
}

// Convert array to Record for DropdownMenu compatibility
const commonOGs_options = computed(() => {
  const record: Record<string, string> = {};
  commonOGs_array.value.forEach((ogItem) => {
    record[ogItem] = ogItem.toUpperCase();
  });
  if (selectedOrthogroup.value && !(selectedOrthogroup.value in record)) {
    record[selectedOrthogroup.value] = selectedOrthogroup.value.toUpperCase();
  }
  return record;
});

// Expose orthogroupOptions to parent
defineExpose({
  orthogroupOptions: commonOGs_options,
  cancelActiveLoad,
  collapseAll: () => collapseAllClades(),
  expandAll: () => visualizationStore.resetPhyloTreeState(),
  collapseToSpecies: () => collapseToSpecies(),
});

const phyloExportPayload = computed(() => {
  const selectedKey = selectedOrthogroupKey();
  const rowsForExport: RowType[] = [];
  const sampleColumnSet = new Set<string>();
  const identifierColumn = config.visualization.id_column;
  const metaColumns = ['dataset', identifierColumn];

  for (const [dataset, datasetData] of Object.entries(tableData.value)) {
    const items = (datasetData as { items?: RowType[] })?.items ?? [];
    for (const row of items) {
      const rowOrthogroup = String(row.ortho_id ?? '').trim().toLowerCase();
      if (selectedKey && rowOrthogroup !== selectedKey) continue;

      const exportRow: RowType = {
        dataset: beautifyLabel(dataset),
        [identifierColumn]: row[identifierColumn],
      };
      for (const [key, value] of Object.entries(row)) {
        if (dataColumnNames.value.includes(key)) {
          exportRow[key] = value;
          sampleColumnSet.add(key);
        }
      }
      rowsForExport.push(exportRow);
    }
  }

  const sampleColumns = dataColumnNames.value.filter((column) => sampleColumnSet.has(column));
  const columns = [...metaColumns, ...sampleColumns];

  return {
    data: rowsForExport.map((row) => {
      const exportRow: RowType = {};
      for (const column of columns) {
        exportRow[column] = row[column];
      }
      return exportRow;
    }),
    columns,
    metaColumns,
    sampleColumns,
    filename: `phylotree_${selectedOrthogroup.value || props.tableName}_${visualizationStore.expressionDisplay.optionId}`,
    hasFilters: Object.keys(filters.value).length > 0,
  };
});

const phyloExportColumnDisplayNames = computed(() => {
  const identifierColumn = config.visualization.id_column;
  const mapping: Record<string, string> = {
    dataset: beautifyLabel('dataset'),
    [identifierColumn]: getDisplayName(identifierColumn),
  };

  for (const column of phyloExportPayload.value.sampleColumns) {
    mapping[column] = column;
  }

  return mapping;
});

// URL state management
function updateUrlFromState() {
  const newQuery: Record<string, string> = { ...route.query } as Record<string, string>;

  if (selectedOrthogroup.value) {
    newQuery.orthogroup = selectedOrthogroup.value;
  } else {
    delete newQuery.orthogroup;
  }

  const plainFilters = filters.value;
  if (plainFilters && Object.keys(plainFilters).length > 0) {
    newQuery.filters = JSON.stringify(plainFilters);
  } else {
    delete newQuery.filters;
  }

  const currentOrthogroup = typeof route.query.orthogroup === "string" ? route.query.orthogroup : undefined;
  const nextOrthogroup = newQuery.orthogroup;
  const currentFilters = typeof route.query.filters === "string" ? route.query.filters : undefined;
  const nextFilters = newQuery.filters;
  if (currentOrthogroup === nextOrthogroup && currentFilters === nextFilters) return;

  void router.replace({
    name: route.name ?? undefined,
    query: newQuery,
  });
}


function getColumnKeys(dataRows: RowType[]): string[] {
  return [...new Set(dataRows.flatMap((row) => Object.keys(row)))];
}


const props = defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
  speciesCodeMap?: Record<string, string>; // table_name -> species_code (e.g., "arabidopsis_thaliana" -> "AT")
  hashLoading?: boolean; // True while parent is loading hash data
  externalLoadingOverlay?: boolean;
  initialOrthogroup?: string | null; // OG from hash load
}>();

const colorSchemes: Record<string, string[]> = {
  set1: [...d3.schemeSet1],
  set2: [...d3.schemeSet2],
  set3: [...d3.schemeSet3],
  paired: [...d3.schemePaired],
  dark2: [...d3.schemeDark2],
  accent: [...d3.schemeAccent],
  category10: [...d3.schemeCategory10],
  observable10: [...d3.schemeObservable10]
};


const selectedCount = ref(0);
selectedCount.value = Object.keys(props.tableName[0]).length;

function waitForPaint(): Promise<void> {
  if (typeof requestAnimationFrame === "undefined") return Promise.resolve();
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

async function showLoadingFrame(options: { preserveProgress?: boolean } = {}) {
  loading.value = true;
  if (!options.preserveProgress) loadingProgress.value = null;
  noNewickResolved.value = false;
  noNewickMessage.value = "";
  await nextTick();
  await waitForPaint();
}

const tableNameOptions = computed(() => {
  return Object.fromEntries(
    Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) || key === props.tableName,
    ),
  );
});


async function fetchData(
  tableName: string,
  rowCount: number,
  requestFilters: Record<string, any> = filtersStore.getMergedFilters(tableName),
  signal?: AbortSignal,
  options: { updateOrthogroupIndex?: boolean } = {},
) {
  try {

    if (rowCount <= 1000 && rowCount > 0) {

      console.log('Phylogenetic Tree - Fetching data with expression mode:', {
        optionId: visualizationStore.expressionDisplay.optionId,
        layer: visualizationStore.expressionDisplay.layer,
        transform: visualizationStore.expressionDisplay.transform
      });

      // Parallelize the 3 independent API calls
      const [exprRes, columnRes, metaRes] = await Promise.all([
        axios.post(
          `${API_BASE_URL}/api/data`,
          {
            table_name: tableName,
            filters: requestFilters,
            filter_chain: filtersStore.buildFilterChainPayload(requestFilters),
            sample_filters: sampleFilters.value,
            layer: visualizationStore.expressionDisplay.layer,
            transform: visualizationStore.expressionDisplay.transform,
          },
          { signal },
        ),
        axios.get<MetaFormat[]>(
          `${API_BASE_URL}/api/columns`,
          {params: {table_name: tableName, meta: false}, signal},
        ),
        axios.post(
          `${API_BASE_URL}/api/data`,
          {
            table_name: tableName + "_meta",
            filters: {},
            sample_filters: sampleFilters.value,
          },
          { signal },
        ),
      ]);

      const data = exprRes.data.data || exprRes.data;
      columnNames.value = getColumnKeys(Array.isArray(data) ? data : Object.values(data));

      //DATA_COLUMNS
      dataColumnNames.value = columnRes.data.map((c) => c.column_name);

      //METADATA
      const colData = metaRes.data.data || metaRes.data;
      columns.value = (Array.isArray(colData) ? colData : []).filter((meta: RowType) =>
        dataColumnNames.value.includes(meta.column_name as string),
      );
      columnStore.setSampleMetadata(columns.value as Record<string, unknown>[], tableName);

      if (options.updateOrthogroupIndex) {
        Object.values(data).map((v) => {
          // Store newick with lowercase OG key to match getAllOGs() filtering
          const ogKey = String(v["ortho_id"]).trim().toLowerCase();
          orthogroupCaseMap.value[ogKey] = String(v["ortho_id"]).trim();
          const newickValue = typeof v["newick_str"] === "string" ? v["newick_str"].trim() : "";
          if (newickValue || !(ogKey in newicks.value)) {
            newicks.value[ogKey] = newickValue;
          }
        })
      }

      const data_full = ref({items: []});
      Object.keys(data).forEach((key) => {
        const concat_array = assign({}, data[key]);
        data_full.value.items.push(concat_array);

      })

      return toRaw(data_full.value);
    }
    return false;
  } catch (e) {
    if (isCanceledRequest(e)) return null;
    console.error("Error fetching data:", e);
  } finally {
  }

}

// Get orthogroups based on selected dataset count:
// - Single dataset: return ALL orthogroups from that dataset (union)
// - Multiple datasets: return ONLY orthogroups present in ALL datasets (intersection)
// Additionally filters to only include orthogroups that have Newick tree data
function getAllOGs(dataRef: Record<string, any>, newicksRef: Record<string, string>): Set<string> {
  const raw = toRaw(unref(dataRef));

  const sets = Object.values(raw)
    .map((plant) => {
      if (!plant) return new Set<string>();
      
      const items = plant?.items ?? [];
      const arr = Array.isArray(items) ? items : Object.values(toRaw(items));

      const ogs = arr
        .map((o: any) => o?.ortho_id)
        .filter((v: any) => v != null && String(v).trim() !== "")
        .map((v: any) => String(v).trim().toLowerCase());

      return new Set(ogs);
    })
    .filter((s) => s.size > 0);

  if (sets.length === 0) return new Set();

  let resultSet: Set<string>;

  // Single dataset: return union (all OGs from that dataset)
  if (sets.length === 1) {
    resultSet = sets[0];
  } else {
    // Multiple datasets: return intersection (only OGs in ALL datasets)
    resultSet = sets.reduce((acc, s) => new Set([...acc].filter((og) => s.has(og))));
  }

  // Filter to only include OGs that have Newick tree data
  return new Set([...resultSet].filter(og => {
    const newickExists = newicksRef[og] && newicksRef[og].trim() !== '';
    return newickExists;
  }));
}


async function fetchAllSelected(options: { keepLoading?: boolean } = {}): Promise<boolean> {
  // Uses its own abort controller / sequence (NOT the shared
  // `activeAbortController` used by `renderTreeForSelectedOG`).  If we
  // shared it, a subsequent `renderTreeForSelectedOG` call from the same
  // watcher chain (or a concurrent watcher) would abort this fetch
  // before `commonOGs_array` is assigned, leaving the dropdown empty.
  // Returns `true` when this request completed successfully, `false` when
  // it was superseded by a newer call.  Callers must check the return value
  // and skip `renderTreeForSelectedOG` on `false` to avoid the double-
  // loading-overlay symptom caused by two concurrent watcher triggers.
  const requestId = ++ogListRequestSeq;
  activeOgListAbortController?.abort();
  const controller = new AbortController();
  activeOgListAbortController = controller;
  setLoadingProgressScope(0, options.keepLoading ? 45 : 100);
  setLoadingPhaseHint("Building orthogroup catalog...");
  await showLoadingFrame();
  setLoadingProgress(0, 1);
  try {
    // Use catalog-selected datasets from existingTables prop
    const selectedDatasets = props.existingTables && props.existingTables.length > 0 
      ? [...props.existingTables] 
      : [props.tableName];
    
    const results: Record<string, any> = {}

    // Clear newicks before fetching to avoid stale data
    newicks.value = {};
    const totalSteps = Math.max(1, selectedDatasets.length + 1);
    let completedSteps = 0;

    // Parallelize multi-species fetch instead of sequential for-loop
    const entries = await Promise.all(
      selectedDatasets.map(async (tableName) => {
        setLoadingPhaseHint("Fetching orthogroup candidates...");
        const optionFilters = omitFilterKey(filtersStore.getMergedFilters(tableName));
        const { data: count } = await axios.post(
          `${API_BASE_URL}/api/count`,
          {
            table_name: tableName,
            filters: optionFilters,
            filter_chain: filtersStore.buildFilterChainPayload(optionFilters),
            sample_filters: sampleFilters.value,
          },
          { signal: controller.signal },
        );
        const rowCount = count.count;
        if (rowCount === 0) {
          setLoadingProgress(++completedSteps, totalSteps);
          return null;
        }
        const data = await fetchData(
          tableName,
          rowCount,
          optionFilters,
          controller.signal,
          { updateOrthogroupIndex: true },
        );
        setLoadingProgress(++completedSteps, totalSteps);
        return data ? { tableName, data } : null;
      })
    );

    if (requestId !== ogListRequestSeq || controller.signal.aborted) return false;

    for (const entry of entries) {
      if (entry) results[entry.tableName] = entry.data;
    }
    tableData.value = results

    // Apply union (single dataset) or intersection (multiple datasets) logic
    // Filter to only include OGs that have Newick tree data
    const filteredOGs = getAllOGs(results, newicks.value);
    const sortedOGs = [...filteredOGs].sort();
    const currentSig = computeFilterSignature();
    // Only rebuild the dropdown list when the catalog filter context
    // actually changed.  This prevents harmless re-runs of
    // `fetchAllSelected` (e.g. a router.replace that retriggers the
    // parent's [id, filters, table_names] watcher and bounces
    // `hashLoading`) from shrinking/clearing the dropdown after the user
    // picks an OG.  We also keep the existing list if a new build came
    // back empty while we already have entries — never silently lose
    // the user's catalog-derived OG options.
    if (lastOgListFilterSig !== currentSig) {
      commonOGs_array.value = sortedOGs;
      lastOgListFilterSig = currentSig;
    } else if (sortedOGs.length > 0 && sortedOGs.length !== commonOGs_array.value.length) {
      // Same filter signature but list size differs — trust the fresh
      // result only if it is non-empty.
      commonOGs_array.value = sortedOGs;
    }
    // else: keep existing commonOGs_array as-is

    // Handle OG selection with persistence and fallback
    // Priority: 1) initialOrthogroup from hash, 2) current store value, 3) first available
    const hashOG = props.initialOrthogroup;
    const currentSelection = hashOG || selectedOrthogroup.value;
    
    suppressSelectedOrthogroupWatcher = true;
    try {
      if (commonOGs_array.value.length > 0) {
        // If current selection is still valid (case-insensitive), keep it; otherwise select first
        const matchingOG = commonOGs_array.value.find(og => og.toLowerCase() === currentSelection?.toLowerCase());
        if (matchingOG) {
          // Use the exact case from commonOGs_array for consistency
          selectedOrthogroup.value = matchingOG;
        } else {
          selectedOrthogroup.value = commonOGs_array.value[0];
        }
      } else {
        // Keep the current selection when the species filter yields no matching OGs,
        // so the "Show full tree" button can still call loadFullNewickForOG with the
        // correct OG id. Only clear if there was truly nothing selected to begin with.
        if (!currentSelection) {
          selectedOrthogroup.value = '';
        }
        // else: leave selectedOrthogroup as-is so NoNewickComponent shows the right OG
        // and loadFullNewickForOG doesn't bail out on the empty-string guard.
      }
      await nextTick();
    } finally {
      suppressSelectedOrthogroupWatcher = false;
    }
    setLoadingProgress(totalSteps, totalSteps);
    return true;
  } catch (error) {
    if (!isCanceledRequest(error)) console.error("Error loading phylogenetic tree data:", error);
    return false;
  } finally {
    if (requestId === ogListRequestSeq) {
      if (!options.keepLoading) loading.value = false
      if (!options.keepLoading) loadingProgress.value = null;
      activeOgListAbortController = null;
    }
  }
}

function computeMetrics(dataRef: any, calcOption: string, codeMap?: Record<string, string>) {

  return Object.fromEntries(
    Object.entries(dataRef.value as Record<string, any>).map(([groupName, groupVal]) => {
      const normalizedGroupVal = groupVal as { items?: RowType[] } | RowType[] | undefined;
      const genes = (Array.isArray(normalizedGroupVal)
        ? normalizedGroupVal
        : Array.isArray(normalizedGroupVal?.items)
          ? normalizedGroupVal.items
          : Object.values(normalizedGroupVal?.items ?? {})) as Array<RowType & { gene_id?: string }>;

      // Look up species code for this group (e.g., "AT" for "arabidopsis_thaliana")
      const speciesCode = codeMap?.[groupName] ?? null

        const groupMap = buildSampleGroupMap(groupName)
        const perGene = Object.fromEntries(genes.flatMap((gene) => {
          const tissueExpression: Record<string, number[]> = {}
          const normalizationTissue: Record<string, number[]> = {}

          const sampleKeys = Object.keys(gene).filter(
            k => /\d+$/.test(k) && typeof gene[k] === "number"
          )

          for (const k of sampleKeys) {
            const tissue = groupMap[k] || "Unknown"
            const value = gene[k]

            if (!tissueExpression[tissue]) tissueExpression[tissue] = []
            tissueExpression[tissue].push(Number(value))
          }

          Object.entries(tissueExpression as Record<string, number[]>).map(([key, value]) => {
              if (calcOption === "mean") {
                const v = mean(value)
                if (!normalizationTissue[key]) normalizationTissue[key] = []
                normalizationTissue[key].push(v)
              } else {
                const v = median(value)
                if (!normalizationTissue[key]) normalizationTissue[key] = []
                normalizationTissue[key].push(v)
              }
            }
          )
          const data = { tissueExpression, normalizationTissue }

          const entries = buildPhyloMetricKeys(groupName, String(gene.gene_id), speciesCode)
            .map((key): [string, typeof data] => [key, data])
          return entries
        })
      )
      return [groupName, perGene]
    })
  )
}

function buildSampleGroupMap(tableName: string): Record<string, string> {
  const groupMap: Record<string, string> = {}
  const records = columnStore.sampleMetadataByTable[tableName] || []
  const groupColumn = selectedGroupingColumn.value
  for (const record of records) {
    const sampleName = String(record.column_name ?? "")
    if (!sampleName) continue
    const rawValue = record[groupColumn]
    groupMap[sampleName] = rawValue !== null && rawValue !== undefined && String(rawValue) !== ""
      ? String(rawValue)
      : "Unknown"
  }
  return groupMap
}

async function fetchOrthogroupDataForAllSpecies(signal?: AbortSignal) {
  if (!selectedOrthogroup.value) return false;

  const allDatasets = Object.keys(props.allTables);
  if (allDatasets.length === 0) return false;
  const originalCaseOrthogroup = orthogroupCaseMap.value[selectedOrthogroupKey()] || selectedOrthogroup.value;

  const entries = await Promise.all(
    allDatasets.map(async (tableName) => {
      const scopedFilters = buildOrthogroupOnlyFilters(originalCaseOrthogroup);

      const { data: count } = await axios.post(`${API_BASE_URL}/api/count`, {
        table_name: tableName,
        filters: scopedFilters,
        filter_chain: filtersStore.buildFilterChainPayload(scopedFilters),
      }, { signal });

      const rowCount = count.count;
      if (rowCount === 0) return null;

      const data = await fetchData(tableName, rowCount, scopedFilters, signal);
      return data ? { tableName, data } : null;
    })
  );

  const results: Record<string, any> = {};
  for (const entry of entries) {
    if (entry) results[entry.tableName] = entry.data;
  }

  if (Object.keys(results).length === 0) {
    return false;
  }

  tableData.value = results;
  return true;
}

async function fetchHighlightedGenesForAllSpecies(signal?: AbortSignal) {
  if (!selectedOrthogroup.value) {
    highlightedGeneIds.value = {};
    return;
  }

  const allDatasets = Object.keys(props.allTables);
  if (allDatasets.length === 0) {
    highlightedGeneIds.value = {};
    return;
  }

  const originalCaseOrthogroup = orthogroupCaseMap.value[selectedOrthogroupKey()] || selectedOrthogroup.value;

  const entries = await Promise.all(
    allDatasets.map(async (tableName) => {
      const mergedFilters = filtersStore.getMergedFilters(tableName);
      const scopedFilters = buildOrthogroupScopedFilters(mergedFilters, originalCaseOrthogroup);

      if (!hasNonOrthogroupFilters(scopedFilters)) {
        return { tableName, geneIds: new Set<string>() };
      }

      const response = await axios.post(
        `${API_BASE_URL}/api/data`,
        {
          table_name: tableName,
          filters: scopedFilters,
          filter_chain: filtersStore.buildFilterChainPayload(scopedFilters),
          columns: [config.visualization.id_column],
        },
        { signal },
      );

      const rows = response.data.data || response.data;
      const geneIds = new Set<string>(
        (Array.isArray(rows) ? rows : []).map((row: RowType) => String(row[config.visualization.id_column] ?? '')).filter(Boolean),
      );

      return { tableName, geneIds };
    })
  );

  highlightedGeneIds.value = Object.fromEntries(
    entries.map(({ tableName, geneIds }) => [tableName, geneIds]),
  );
}

async function fetchFullNewickForSelectedOG(signal?: AbortSignal): Promise<string | null> {
  if (!selectedOrthogroup.value) return null;

  const originalCaseOrthogroup = orthogroupCaseMap.value[selectedOrthogroupKey()] || selectedOrthogroup.value;
  try {
    const response = await axios.get<{ og_id: string; newick?: string | null; available?: boolean }>(
      `${API_BASE_URL}/api/gene_tree/${originalCaseOrthogroup}`,
      { params: { allow_missing: 1 }, signal }
    );
    const newick = response.data.newick;
    return typeof newick === "string" && newick.trim() ? newick : null;
  } catch (error: any) {
    if (isCanceledRequest(error)) return null;
    if (error?.response?.status !== 404) {
      console.error("Failed to check full gene tree:", error);
    }
    return null;
  }
}

function mean(arr: number[]): number {
  if (arr.length > 2) {
    const sum = arr.reduce((acc, val) => acc + val, 0);
    return sum / arr.length;
  } else {
    return arr[0];
  }
}

function median(values: number[]): number {
  values = [...values].sort((a, b) => a - b);
  const half = Math.floor(values.length / 2);
  return (values.length % 2
      ? values[half]
      : (values[half - 1] + values[half]) / 2
  );
}


function resetContainer() {
  if (!phylotreeContainer.value) return;
  d3.select(phylotreeContainer.value).selectAll("*").remove();
}

function getPrefix(name: string): string {
  const m = name.match(/^([^_]+)/)
  return m ? m[1] : name
}

/**
 * Download text content as a file
 */
function downloadTextFile(content: string, filename: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Store for clade highlighting colors
const cladeColors = ref<Map<string, string>>(new Map());
const highlightColorPalette = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#8b5cf6', '#ec4899'];
let nextColorIndex = 0;

async function initPhylotree(
  newick_str: string | null | undefined,
  metrics: any,
  options: { requestId?: number; manageLoading?: boolean } = {},
): Promise<boolean> {
  const isStale = () => options.requestId !== undefined && options.requestId !== loadRequestSeq

  if (isStale()) return false

  if (options.manageLoading) loading.value = true

  if (typeof newick_str !== 'string' || newick_str.trim() === '') {
    if (options.manageLoading) loading.value = false
    return false
  }

  resetContainer()

  const container = phylotreeContainer.value
  if (!container) {
    if (options.manageLoading) loading.value = false
    return false
  }

  // === 1. Parse Newick + build hierarchy + apply persisted collapse state ===
  let rawTree
  try {
    rawTree = parseNewick(newick_str)
  } catch (e) {
    console.error('[PhyloTree] Newick parse error:', e)
    if (options.manageLoading) loading.value = false
    return false
  }

  if (isStale()) return false

  const fullHier = buildHierarchy(rawTree)
  fullHierarchy.value = fullHier
  const collapsedSet = new Set(visualizationStore.phyloTree.collapsedNodes)
  const visibleHier = applyCollapse(fullHier, collapsedSet)

  // === 2. Layout (shared y-scale with heatmap by construction) ===
  const cellSize = 14
  const cellPad = 6
  const rowHeight = cellSize + cellPad  // = 20 px, == heatmap row stride
  const leafCount = visibleHier.leaves().length
  // Adaptive tree width — narrow trees for small OGs, capped for large ones.
  const treeWidth = Math.max(280, Math.min(900, leafCount * 3 + 200))
  const layoutResult = computePhyloLayout(visibleHier, {
    rowHeight,
    treeWidth,
    mode: visualizationStore.phyloTree.branchLengthMode,
  })

  // === 3. Tissues / column clustering / color scale (reused logic) ===
  const groupNames = Object.keys(metrics)
  const tissueSet = new Set<string>()
  for (const group of Object.values(metrics)) {
    for (const gene of Object.values(group as Record<string, any>)) {
      const norm = (gene as any).normalizationTissue ?? {}
      for (const t of Object.keys(norm)) tissueSet.add(t)
    }
  }
  let tissues = orderTissueCategories(Array.from(tissueSet))

  const hasExplicitAxisOrder = visualizationStore.customColOrder.enabled || Boolean(visualizationStore.colOrder.name);
  if (!hasExplicitAxisOrder && visualizationStore.clustering.clusterCols && tissues.length > 2) {
    try {
      const allGenes: { geneId: string; values: number[] }[] = []
      for (const [, genesObj] of Object.entries(metrics)) {
        for (const [geneId, geneData] of Object.entries(genesObj as Record<string, any>)) {
          const tn = (geneData as any)?.normalizationTissue ?? {}
          const values = tissues.map(t => {
            let v = tn[t]
            if (Array.isArray(v)) v = v[0]
            return typeof v === 'number' && Number.isFinite(v) ? v : 0
          })
          allGenes.push({ geneId, values })
        }
      }
      if (allGenes.length > 0) {
        const colProfiles: number[][] = tissues.map((_, colIdx) => allGenes.map(g => g.values[colIdx]))
        const clusterResult = hierarchicalCluster(
          colProfiles,
          visualizationStore.clustering.method,
          visualizationStore.clustering.distance,
        )
        tissues = clusterResult.order.map(idx => tissues[idx])
      }
    } catch (error) {
      console.warn('Column clustering failed, using original order:', error)
    }
  }

  const columnsArr: { tissue: string; colIndex: number }[] =
    tissues.map((tissue, idx) => ({ tissue, colIndex: idx }))

  const allValues: number[] = []
  for (const [, genesObj] of Object.entries(metrics)) {
    const geneIds = Object.keys(genesObj as Record<string, any>)
    geneIds.forEach(geneId => {
      const tn = (genesObj as any)[geneId]?.normalizationTissue ?? {}
      tissues.forEach(t => {
        let v = tn[t]
        if (Array.isArray(v)) v = v[0]
        if (typeof v === 'number' && Number.isFinite(v)) allValues.push(v)
      })
    })
  }
  const minVal = d3.min(allValues) ?? 0
  const maxVal = d3.max(allValues) ?? 1
  const color = d3
    .scaleSequential(COLORSCALES[visualizationStore.colorScale] as (t: number) => string)
    .domain([minVal, maxVal])

  // Species prefix → table-name map (full name + short code)
  const speciesNameToTable: Record<string, string> = {}
  groupNames.forEach(tableName => {
    const sentenceCase = tableName.charAt(0).toUpperCase() + tableName.slice(1)
    speciesNameToTable[sentenceCase] = tableName
    const code = props.speciesCodeMap?.[tableName]
    if (code && !(code in speciesNameToTable)) speciesNameToTable[code] = tableName
  })

  // Species-prefix color scale (matches old behavior)
  const leafNames = layoutResult.leaves
    .filter(l => !l.isCollapsed)
    .map(l => l.hnode.data.name)
  const prefixes = Array.from(new Set(leafNames.map(getPrefix)))
  const selectedScheme = colorSchemes[visualizationStore.colorScale] || d3.schemeSet1
  const prefixColor = d3.scaleOrdinal<string, string>().domain(prefixes).range(selectedScheme as string[])

  heatmapCols.value = tissues

  // Reserve a real SVG header band for rotated tissue labels. The tree and
  // heatmap rows are shifted down together, preserving their shared y-axis,
  // while labels are clipped to the header so they cannot paint over cells.
  const longestTissueLabel = tissues.reduce((max, tissue) => Math.max(max, tissue.length), 0)
  const heatmapLabelHeaderHeight = Math.max(70, Math.min(180, longestTissueLabel * 6.5 + 18))
  const rowY = (y: number) => y + heatmapLabelHeaderHeight

  // === 4. Build SVG ===
  const svgNS = 'http://www.w3.org/2000/svg'
  const svgElement = document.createElementNS(svgNS, 'svg') as SVGSVGElement
  container.innerHTML = ''
  container.appendChild(svgElement)
  const svgSel = d3.select<SVGSVGElement, unknown>(svgElement)

  // zoom-container (kept as class name so ShareOverlay's exporter still works)
  const zoomGroup = svgSel.append('g').attr('class', 'zoom-container')
  const mainGroup = zoomGroup.append('g').attr('class', 'tree-root')

  // --- Branches (elbow style) ---
  const branchGroup = mainGroup.append('g').attr('class', 'branches')
  const branchStroke = 3
  const branchStrokeDefault = '#999'
  const branchStrokeHover = '#a6c550'
  for (const link of layoutResult.links) {
    const path = `M${link.source.x},${rowY(link.source.y)} V${rowY(link.target.y)} H${link.target.x}`
    branchGroup.append('path')
      .attr('class', 'branch')
      .attr('d', path)
      .attr('fill', 'none')
      .attr('stroke', branchStrokeDefault)
      .attr('stroke-width', branchStroke)
      .style('cursor', 'pointer')
      .on('mouseenter', function () {
        d3.select(this).attr('stroke', branchStrokeHover)
      })
      .on('mouseleave', function () {
        d3.select(this).attr('stroke', branchStrokeDefault)
      })
  }

  // --- Nodes (internal + leaves) ---
  const nodeGroup = mainGroup.append('g').attr('class', 'nodes')

  // Apply clade-highlight colours into a map for O(1) lookup
  const cladeColorByNodeId = new Map<string, string>()
  cladeColors.value.forEach((color, nodeId) => cladeColorByNodeId.set(nodeId, color))

  // Pre-compute: for each layout node, the clade highlight (inherited from nearest highlighted ancestor)
  const inheritedHighlight = new Map<LayoutNode, string | null>()
  function findInheritedHighlight(ln: LayoutNode): string | null {
    if (inheritedHighlight.has(ln)) return inheritedHighlight.get(ln)!
    const own = cladeColorByNodeId.get(ln.hnode.data.nodeId)
    if (own) { inheritedHighlight.set(ln, own); return own }
    const parentLn = layoutResult.nodes.find(n => n.hnode === ln.hnode.parent) || null
    const result = parentLn ? findInheritedHighlight(parentLn) : null
    inheritedHighlight.set(ln, result)
    return result
  }

  // --- Render each node ---
  for (const ln of layoutResult.nodes) {
    const datum = ln.hnode.data
    const isLeaf = ln.isLeaf && !ln.isCollapsed
    const isCollapsed = ln.isCollapsed
    const isInternal = !isLeaf && !isCollapsed
    const g = nodeGroup.append('g')
      .attr('class', isInternal ? 'node internal-node' : 'node')
      .attr('transform', `translate(${ln.x},${rowY(ln.y)})`)
      .datum(ln)

    const highlightColor = findInheritedHighlight(ln)

    if (isCollapsed) {
      // Triangle pointing right, size scaled by hidden leaf count
      const fullNode = fullHier.descendants().find(d => d.data.nodeId === datum.nodeId)
      const hiddenLeafCount = fullNode ? fullNode.leaves().length : datum.leafNames.length
      const triSize = Math.max(6, Math.min(20, Math.sqrt(hiddenLeafCount) * 2))
      const triH = rowHeight * 0.8
      g.append('polygon')
        .attr('class', 'node-collapsed')
        .attr('points', `0,${-triH / 2} ${triSize * 2},${-triH / 2} ${triSize * 2},${triH / 2} 0,${triH / 2}`)
        .attr('fill', highlightColor || '#888')
        .attr('stroke', '#333')
        .attr('stroke-width', 0.6)
        .style('cursor', 'pointer')
        .append('title')
        .text(`${hiddenLeafCount} leaves collapsed — click to expand`)
      g.select('polygon')
        .on('click', (event: MouseEvent) => {
          event.stopPropagation()
          visualizationStore.toggleNodeCollapsed(datum.nodeId)
        })
      g.append('text')
        .attr('x', triSize * 2 + 4)
        .attr('y', 0)
        .attr('dominant-baseline', 'middle')
        .attr('font-size', 11)
        .attr('fill', '#444')
        .text(`(${hiddenLeafCount})`)
    } else if (isInternal) {
      g.append('circle')
        .attr('r', 6.4)
        .attr('fill', highlightColor || '#CCC')
        .attr('stroke', highlightColor || '#666')
        .attr('stroke-width', highlightColor ? 2 : 0.5)
        .style('cursor', 'pointer')
        .append('title')
        .text(`Click to collapse — ${datum.leafNames.length} leaves`)
      // Click to collapse, right-click for menu
      g.select('circle')
        .on('click', (event: MouseEvent) => {
          event.stopPropagation()
          visualizationStore.toggleNodeCollapsed(datum.nodeId)
        })
        .on('contextmenu', (event: MouseEvent) => {
          event.preventDefault()
          event.stopPropagation()
          showInternalNodeContextMenu(event, container, datum.nodeId, ln.hnode, metrics)
        })

      // Bootstrap-value display: if the node has a numeric name >= 50 (or >= 0.5 normalized)
      const bv = parseFloat(datum.name)
      if (!isNaN(bv) && bv >= 0) {
        const display = bv <= 1 ? Math.round(bv * 100) : Math.round(bv)
        if (display >= 50) {
          g.append('text')
            .attr('class', 'bootstrap-value')
            .attr('x', -5)
            .attr('y', -6)
            .attr('font-size', '9px')
            .attr('fill', display >= 90 ? '#059669' : display >= 70 ? '#d97706' : '#dc2626')
            .attr('font-weight', display >= 90 ? 'bold' : 'normal')
            .text(String(display))
        }
      }
    } else {
      // Leaf
      const name = datum.name
      const prefix = getPrefix(name)
      const speciesColor = highlightColor || String(prefixColor(prefix))

      const resolvedLeaf = resolvePhyloLeafMatch(name, metrics, props.speciesCodeMap ?? {})
      const shouldHighlightLeaf = resolvedLeaf
        ? highlightedGeneIds.value[resolvedLeaf.tableName]?.has(resolvedLeaf.geneId) ?? false
        : false

      g.append('circle')
        .attr('r', 2)
        .attr('fill', speciesColor)

      const textSel = g.append('text')
        .attr('x', 6)
        .attr('y', 0)
        .attr('dominant-baseline', 'middle')
        .attr('font-size', 11)
        .attr('fill', speciesColor)
        .attr('font-weight', shouldHighlightLeaf ? 800 : 400)
        .attr('stroke', shouldHighlightLeaf ? '#ffffff' : 'none')
        .attr('stroke-width', shouldHighlightLeaf ? 0.8 : 0)
        .attr('paint-order', shouldHighlightLeaf ? 'stroke' : null)
        .text(name)

      if (shouldHighlightLeaf) {
        const textNode = textSel.node() as SVGTextElement | null
        if (textNode) {
          const bbox = textNode.getBBox()
          g.insert('text', 'text')
            .attr('class', 'filtered-leaf-marker')
            .attr('x', bbox.x - 13)
            .attr('y', bbox.y + bbox.height / 2)
            .attr('dominant-baseline', 'middle')
            .attr('fill', '#b45309')
            .attr('font-size', '13px')
            .attr('font-weight', 900)
            .attr('stroke', '#fffbeb')
            .attr('stroke-width', 0.9)
            .attr('paint-order', 'stroke')
            .text('★')
        }
      }

      // Right-click context menu for leaf: species hide/show
      const speciesTableName = matchLeafToDataset(name, groupNames, props.speciesCodeMap ?? {})?.tableName
      if (speciesTableName) {
        g.on('contextmenu', function (event: MouseEvent) {
          event.preventDefault()
          event.stopPropagation()
          showNodeContextMenu(event, container, speciesTableName, metrics)
        })
      }
    }
  }

  // --- Compute right edge of tree (in tree-local coords) for heatmap placement ---
  // Use max(leaf.x) + leaf-label width approximation. For accurate placement after
  // text rendering we measure the bbox now.
  const treeBBox = mainGroup.node()!.getBBox()
  const heatmapX = treeBBox.x + treeBBox.width + 8

  // --- Heatmap (shares y-axis with tree by construction) ---
  const heatmapGroup = mainGroup.append('g')
    .attr('class', 'tree-heatmap')
    .attr('transform', `translate(${heatmapX}, 0)`)

  // Create reusable tooltip div
  const tooltip = d3.select(container)
    .append('div')
    .attr('class', 'phylo-tooltip')
    .style('position', 'absolute')
    .style('visibility', 'hidden')
    .style('background-color', 'white')
    .style('color', '#333')
    .style('font-size', '0.75rem')
    .style('border-radius', '0.375rem')
    .style('padding', '0.25rem 0.5rem')
    .style('min-width', '8rem')
    .style('white-space', 'normal')
    .style('word-wrap', 'break-word')
    .style('max-width', '24rem')
    .style('border', '1px solid #d1d5db')
    .style('box-shadow', '0 1px 2px rgba(0,0,0,0.05)')
    .style('pointer-events', 'auto')
    .style('user-select', 'text')
    .style('z-index', '1000')

  // Render heatmap rows for visible leaves
  for (const ln of layoutResult.leaves) {
    if (ln.isCollapsed) continue
    const name = ln.hnode.data.name
    const resolvedLeaf = resolvePhyloLeafMatch(name, metrics, props.speciesCodeMap ?? {})
    if (!resolvedLeaf) continue
    const matchedTable = resolvedLeaf.tableName
    if (hiddenSpecies.value.has(matchedTable)) continue

    for (const { tissue, colIndex } of columnsArr) {
      const genesObj = metrics[matchedTable]
      if (!genesObj) continue
      const geneObj = genesObj[resolvedLeaf.matchedKey]
      if (!geneObj) continue

      let v: any = geneObj.normalizationTissue?.[tissue]
      if (Array.isArray(v)) v = v[0]
      if (typeof v !== 'number' || !Number.isFinite(v)) continue

      const originalItems = (tableData.value[matchedTable] as { items?: RowType[] } | undefined)?.items ?? []
      const originalRowData = originalItems.find(
        (item: any) => String(item[config.visualization.id_column]) === resolvedLeaf.geneId,
      ) || null

      const cellData = {
        geneId: resolvedLeaf.geneId,
        tissue,
        value: v,
        species: matchedTable,
        tableName: matchedTable,
        geneObj,
        rowData: originalRowData,
      }

      heatmapGroup.append('rect')
        .attr('x', colIndex * (cellSize + cellPad))
        .attr('y', rowY(ln.y) - cellSize / 2)
        .attr('width', cellSize)
        .attr('height', cellSize)
        .attr('fill', color(v))
        .attr('class', 'heatmap-cell')
        .style('cursor', 'pointer')
        .datum(cellData)
        .on('mouseover', function (_event, d) {
          d3.select(this).attr('stroke', 'white').style('stroke-width', 2)
          const entityLabel = getEntityIdLabel()
          const selectedFields = visualizationStore.tooltipFields
          let tooltipHtml = `
            <b>${entityLabel}:</b> ${d.geneId}<br>
            <b>${groupingColumnLabel.value}:</b> ${d.tissue}<br>
            <b>Value:</b> ${typeof d.value === 'number' ? d.value.toFixed(3) : d.value}<br>
            <b>Species:</b> ${d.species}<br>
          `
          if (d.rowData && selectedFields !== null && selectedFields.length > 0) {
            const metaLines = selectedFields
              .filter(field => field !== config.visualization.id_column && d.rowData![field] !== undefined)
              .map(field => {
                let value = d.rowData![field]
                if (Array.isArray(value)) {
                  value = value.length > 3 ? value.slice(0, 3).join(', ') + '...' : value.join(', ')
                }
                return `<b>${getDisplayName(field)}:</b> ${value}`
              })
              .join('<br>')
            if (metaLines) {
              tooltipHtml += `<hr style="margin:4px 0; border-color:#888"/>${metaLines}`
            }
          }
          tooltipHtml += `
            <hr style="margin:4px 0; border-color:#888"/>
            <div style="text-align:center; font-size:0.7rem; color:#6b7280;">Right-click for more details</div>
          `
          tooltip.html(tooltipHtml).style('visibility', 'visible')
        })
        .on('mousemove', function (event) {
          if (!container) return
          const containerRect = container.getBoundingClientRect()
          const tooltipNode = tooltip.node()
          if (!tooltipNode) return
          const tooltipRect = (tooltipNode as HTMLElement).getBoundingClientRect()
          const offsetX = 12
          let xPos = event.clientX - containerRect.left + offsetX
          let yPos = event.clientY - containerRect.top - tooltipRect.height / 2
          if (xPos + tooltipRect.width > containerRect.width) {
            xPos = event.clientX - containerRect.left - tooltipRect.width - offsetX
          }
          xPos = Math.max(0, xPos)
          yPos = Math.max(0, Math.min(yPos, containerRect.height - tooltipRect.height))
          tooltip.style('left', xPos + 'px').style('top', yPos + 'px')
        })
        .on('mouseout', function () {
          d3.select(this).attr('stroke', 'none')
          tooltip.style('visibility', 'hidden')
        })
        .on('contextmenu', function (event, d) {
          event.preventDefault()
          if (d.rowData) {
            selectedRowData.value = d.rowData
            selectedTableName.value = d.tableName
            selectedColumnValue.value = d.tissue
            selectedCellValue.value = d.value
            heatmapCols.value = Array.from(tissueSet)
            showTooltipModal.value = true
          }
        })
    }
  }

  // --- Tissue column labels (rotated -90°, clipped to header band) ---
  const labelClipId = `phylo-heatmap-labels-${Math.random().toString(36).slice(2)}`
  svgSel.append('defs')
    .append('clipPath')
    .attr('id', labelClipId)
    .append('rect')
    .attr('x', -cellSize)
    .attr('y', 0)
    .attr('width', columnsArr.length * (cellSize + cellPad) + cellSize * 2)
    .attr('height', heatmapLabelHeaderHeight)

  const labelGroup = heatmapGroup.append('g')
    .attr('class', 'tree-heatmap-labels')
    .attr('clip-path', `url(#${labelClipId})`)

  const firstLeafY = layoutResult.leaves.length > 0 ? layoutResult.leaves[0].y : 0
  const firstCellTop = rowY(firstLeafY) - cellSize / 2
  const labelBaselineY = Math.min(heatmapLabelHeaderHeight - 8, firstCellTop - 10)
  for (const { tissue, colIndex } of columnsArr) {
    const cx = colIndex * (cellSize + cellPad) + cellSize / 2
    labelGroup.append('text')
      .attr('x', -labelBaselineY)
      .attr('y', cx)
      .attr('text-anchor', 'start')
      .attr('dominant-baseline', 'middle')
      .attr('font-size', 12)
      .attr('transform', 'rotate(-90)')
      .text(tissue.charAt(0).toUpperCase() + tissue.slice(1))
  }

  // --- Legend ---
  const heatmapContentWidth = columnsArr.length > 0
    ? (columnsArr.length - 1) * (cellSize + cellPad) + cellSize
    : 0
  const hasHighlightedLeaves = Object.values(highlightedGeneIds.value).some((geneIds) => geneIds.size > 0)
  if (visualizationStore.legend) {
    const legendWidth = 18
    const legendHeight = 180
    const legendSteps = 40
    const legendGap = cellSize
    const legendY = Math.max(0, rowY(firstLeafY) - 20)
    const legendGroup = mainGroup.append('g')
      .attr('class', 'heatmap-legend')
    const legendValueScale = d3.scaleLinear().domain([minVal, maxVal]).range([legendHeight, 0])
    const stepHeight = legendHeight / legendSteps
    const legendData = d3.range(legendSteps).map(i => {
      const t0 = i / legendSteps
      return { index: i, value: minVal + t0 * (maxVal - minVal) }
    })
    legendGroup.selectAll('rect')
      .data(legendData)
      .enter()
      .append('rect')
      .attr('x', 0)
      .attr('y', d => legendValueScale(d.value))
      .attr('width', legendWidth)
      .attr('height', stepHeight + 1)
      .attr('fill', d => color(d.value))
    legendGroup.append('g')
      .attr('transform', `translate(${legendWidth + 4}, 0)`)
      .call(d3.axisRight(legendValueScale).ticks(5).tickSize(4))
      .selectAll('text')
      .style('font-size', '11px')
    legendGroup.append('text')
      .attr('x', legendWidth / 2)
      .attr('y', -8)
      .attr('text-anchor', 'middle')
      .style('font-size', '11px')
      .text(getExpressionOption(visualizationStore.expressionDisplay.optionId)?.label || 'Expression values')
    const legendBBox = legendGroup.node()?.getBBox()
    const legendMinX = legendBBox ? legendBBox.x : 0
    const legendX = heatmapX + heatmapContentWidth + legendGap - legendMinX
    legendGroup.attr('transform', `translate(${legendX}, ${legendY})`)
    if (hasHighlightedLeaves) {
      const markerLegend = legendGroup.append('g')
        .attr('transform', `translate(-8, ${legendHeight + 28})`)
      markerLegend.append('text')
        .attr('x', 0).attr('y', 0)
        .attr('dominant-baseline', 'middle')
        .attr('fill', '#b45309')
        .attr('font-size', '13px')
        .attr('font-weight', 900)
        .attr('stroke', '#fffbeb').attr('stroke-width', 0.9).attr('paint-order', 'stroke')
        .text('★')
      markerLegend.append('text')
        .attr('x', 12).attr('y', 0)
        .attr('dominant-baseline', 'middle')
        .attr('fill', '#000')
        .style('font-size', '12px')
        .text('passes current filters')
    }
  }

  // === 5. ViewBox + zoom ===
  const finalBBox = mainGroup.node()!.getBBox()
  const padding = 12
  const viewWidth = finalBBox.width + padding * 2
  const viewHeight = finalBBox.height + padding * 2
  // Shift the tree-root so the heatmap labels above row 0 are not clipped.
  mainGroup.attr('transform', `translate(${padding - finalBBox.x}, ${padding - finalBBox.y})`)
  svgElement.setAttribute('viewBox', `0 0 ${viewWidth} ${viewHeight}`)
  // 'xMidYMid meet' keeps the tree centred in the (possibly larger) container,
  // 'meet' guarantees it fits without distortion. 'overflow:hidden' on both the
  // SVG and the parent ensures zoom/pan never bleeds outside the rounded card.
  svgElement.setAttribute('preserveAspectRatio', 'xMidYMid meet')
  svgElement.style.width = '100%'
  svgElement.style.height = '100%'
  svgElement.style.overflow = 'hidden'
  svgElement.style.display = 'block'

  // Zoom + pan
  const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 10])
    .filter((event) => {
      const target = event.target as Element
      const isNode = target.closest('g.node') !== null
      if (event.type === 'wheel') return true
      if (event.type === 'mousedown' && isNode) return false
      if (event.type === 'dblclick' && isNode) return false
      return true
    })
    .on('zoom', (event) => {
      zoomGroup.attr('transform', event.transform.toString())
      visualizationStore.setPhyloTreeZoom({
        k: event.transform.k,
        x: event.transform.x,
        y: event.transform.y,
      })
    })
  svgSel.call(zoomBehavior)
  currentZoomBehavior = zoomBehavior

  const savedTransform = visualizationStore.phyloTree.zoomTransform
  if (savedTransform.k !== 1 || savedTransform.x !== 0 || savedTransform.y !== 0) {
    const t = d3.zoomIdentity.translate(savedTransform.x, savedTransform.y).scale(savedTransform.k)
    svgSel.call(zoomBehavior.transform, t)
  }

  if (options.manageLoading) loading.value = false
  return true
}

function orderTissueCategories(tissues: string[]): string[] {
  const customOrder = visualizationStore.customColOrder;
  if (customOrder.enabled && customOrder.metadataValues.length > 0) {
    const tissueRank = getTissueRankFromAxis(customOrder.metadataValues);
    return [...tissues].sort((a, b) => {
      const aRank = tissueRank.get(a.toLowerCase()) ?? Number.MAX_SAFE_INTEGER;
      const bRank = tissueRank.get(b.toLowerCase()) ?? Number.MAX_SAFE_INTEGER;
      if (aRank !== bRank) return aRank - bRank;
      return a.localeCompare(b);
    });
  }
  if (visualizationStore.colOrder.name && visualizationStore.colOrder.name !== "OLO") {
    return orderAxisCategories(tissues, visualizationStore.colOrder.order);
  }
  return orderAxisCategories(tissues, "asc");
}

function getTissueRankFromAxis(orderedValues: string[]): Map<string, number> {
  return new Map(orderedValues.map((value, index) => [value.toLowerCase(), index]));
}

function orderAxisCategories(tissues: string[], direction: "asc" | "desc"): string[] {
  return [...tissues].sort((a, b) => {
    const comparison = a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
    return direction === "desc" ? -comparison : comparison;
  });
}

// Context menu for leaf nodes (hide / show species)
function showNodeContextMenu(event: MouseEvent, container: HTMLElement, speciesTableName: string, metrics: any) {
  d3.selectAll('.node-context-menu').remove()
  const contextMenu = d3.select(container)
    .append('div')
    .attr('class', 'node-context-menu')
    .style('position', 'absolute')
    .style('left', (event.clientX - container.getBoundingClientRect().left) + 'px')
    .style('top', (event.clientY - container.getBoundingClientRect().top) + 'px')
    .style('background', 'white')
    .style('border', '1px solid #ccc')
    .style('border-radius', '4px')
    .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)')
    .style('z-index', '1000')
    .style('padding', '4px 0')
  const isHidden = hiddenSpecies.value.has(speciesTableName)
  const menuItems = [
    { label: isHidden ? 'Show species' : 'Hide species', action: () => {
      if (isHidden) hiddenSpecies.value.delete(speciesTableName)
      else hiddenSpecies.value.add(speciesTableName)
      void rerenderCurrentTree(metrics)
    }},
    { label: 'Show all species', action: () => {
      hiddenSpecies.value.clear()
      void rerenderCurrentTree(metrics)
    }},
  ]
  menuItems.forEach(item => {
    contextMenu.append('div')
      .style('padding', '6px 12px')
      .style('cursor', 'pointer')
      .style('font-size', '13px')
      .text(item.label)
      .on('mouseover', function () { d3.select(this).style('background', '#f0f0f0') })
      .on('mouseout', function () { d3.select(this).style('background', 'white') })
      .on('click', function () { item.action(); contextMenu.remove() })
  })
  d3.select('body').on('click.contextmenu', function () {
    contextMenu.remove()
    d3.select('body').on('click.contextmenu', null)
  })
}

// Context menu for internal nodes (collapse/expand, export, highlight)
function showInternalNodeContextMenu(event: MouseEvent, container: HTMLElement, nodeId: string, hnode: d3.HierarchyNode<PhyloDatum>, metrics: any) {
  d3.selectAll('.node-context-menu').remove()
  const contextMenu = d3.select(container)
    .append('div')
    .attr('class', 'node-context-menu')
    .style('position', 'absolute')
    .style('left', (event.clientX - container.getBoundingClientRect().left) + 'px')
    .style('top', (event.clientY - container.getBoundingClientRect().top) + 'px')
    .style('background', 'white')
    .style('border', '1px solid #ccc')
    .style('border-radius', '4px')
    .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)')
    .style('z-index', '1000')
    .style('padding', '4px 0')
  const isCollapsed = collapsedNodes.value.has(nodeId)
  const isHighlighted = cladeColors.value.has(nodeId)
  const menuItems: ({ label: string; action: () => void } | null)[] = [
    { label: isCollapsed ? '▶ Expand clade' : '▼ Collapse clade', action: () => {
      visualizationStore.toggleNodeCollapsed(nodeId)
    }},
    { label: '↺ Expand all clades', action: () => {
      visualizationStore.resetPhyloTreeState()
    }},
    null,
    { label: '📥 Export subtree (Newick)', action: () => {
      const newick = hierarchyToNewick(hnode)
      const filename = `subtree_${og.value}_${nodeId.replace(/[^a-zA-Z0-9]/g, '_').slice(0, 60)}.nwk`
      downloadTextFile(newick, filename)
    }},
    null,
    { label: isHighlighted ? '🎨 Remove highlight' : '🎨 Highlight clade', action: () => {
      if (isHighlighted) {
        cladeColors.value.delete(nodeId)
      } else {
        const c = highlightColorPalette[nextColorIndex % highlightColorPalette.length]
        nextColorIndex++
        cladeColors.value.set(nodeId, c)
      }
      void rerenderCurrentTree(metrics)
    }},
    { label: '🧹 Clear all highlights', action: () => {
      cladeColors.value.clear()
      nextColorIndex = 0
      void rerenderCurrentTree(metrics)
    }},
  ]
  menuItems.forEach(item => {
    if (item === null) {
      contextMenu.append('div')
        .style('height', '1px')
        .style('background', '#e5e7eb')
        .style('margin', '4px 0')
    } else {
      contextMenu.append('div')
        .style('padding', '6px 12px')
        .style('cursor', 'pointer')
        .style('font-size', '13px')
        .text(item.label)
        .on('mouseover', function () { d3.select(this).style('background', '#f0f0f0') })
        .on('mouseout', function () { d3.select(this).style('background', 'white') })
        .on('click', function () { item.action(); contextMenu.remove() })
    }
  })
  d3.select('body').on('click.contextmenu', function () {
    contextMenu.remove()
    d3.select('body').on('click.contextmenu', null)
  })
}

// Serialize a d3.hierarchy node back to a Newick string.
function hierarchyToNewick(node: d3.HierarchyNode<PhyloDatum>): string {
  function rec(n: d3.HierarchyNode<PhyloDatum>): string {
    const bl = n.data.branchLength ? `:${n.data.branchLength}` : ''
    const name = n.data.name || ''
    if (n.children && n.children.length > 0) {
      const inner = n.children.map(rec).join(',')
      return `(${inner})${name}${bl}`
    }
    return `${name}${bl}`
  }
  return rec(node) + ';'
}

// View-level actions (called via defineExpose)
function collapseAllClades() {
  if (!fullHierarchy.value) return
  const ids: string[] = []
  fullHierarchy.value.each((n) => {
    // Collapse every internal node except the root.
    if (n.children && n.children.length > 0 && n.depth > 0) {
      ids.push(n.data.nodeId)
    }
  })
  visualizationStore.setPhyloCollapsedNodes(ids)
}

function collapseToSpecies() {
  if (!fullHierarchy.value) return
  const ids = collapseToSpeciesIds(fullHierarchy.value, getPrefix)
  visualizationStore.setPhyloCollapsedNodes(ids)
}

async function rerenderCurrentTree(metrics: any = lastMetrics.value): Promise<boolean> {
  if (props.hashLoading) return false;
  if (loading.value) return false;
  if (typeof newickstr.value !== "string" || !newickstr.value.trim()) return false;
  if (!metrics) return false;
  const requestId = loadRequestSeq;
  await nextTick();
  return initPhylotree(newickstr.value, metrics, { requestId });
}



// Helper function to render tree for currently selected orthogroup
async function renderTreeForSelectedOG(origin = "unknown") {
  const renderSignature = currentRenderSignature();
  if (activeRenderSignature === renderSignature) {
    tracePhyloLoad("render-skip-active-duplicate", { origin });
    return;
  }
  if (!loading.value && lastCompletedRenderSignature === renderSignature) {
    tracePhyloLoad("render-skip-completed-duplicate", { origin });
    return;
  }

  const requestId = ++loadRequestSeq;
  activeRenderSignature = renderSignature;
  tracePhyloLoad("render-start", { origin, requestId });
  activeAbortController?.abort();
  const controller = new AbortController();
  activeAbortController = controller;
  const continuingLoad = loading.value && typeof loadingProgress.value === "number" && Number.isFinite(loadingProgress.value);
  const renderStartProgress = continuingLoad ? Math.max(loadingProgress.value ?? 0, 45) : 0;
  setLoadingProgressScope(renderStartProgress, 100);
  setLoadingPhaseHint("Preparing tree data...");
  await showLoadingFrame({ preserveProgress: continuingLoad });
  setLoadingProgress(0, 4);
  try {
    const ogKey = selectedOrthogroupKey();
    if (!selectedOrthogroup.value || !newicks.value[ogKey]) {
      // Fall back to the directly-loaded full Newick (button was clicked)
      if (fullNewick.value) {
        fullTreeAvailable.value = false;
        noNewickMessage.value = "";
        setLoadingPhaseHint("Fetching orthogroup expression values...");
        await Promise.all([
          fetchOrthogroupDataForAllSpecies(controller.signal),
          fetchHighlightedGenesForAllSpecies(controller.signal),
        ]);
        if (requestId !== loadRequestSeq || controller.signal.aborted) return;
        setLoadingProgress(2, 4);
        const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
        lastMetrics.value = metrics;
        newickstr.value = fullNewick.value;
        await nextTick();
        setLoadingPhaseHint("Rendering phylogenetic tree...");
        const rendered = await initPhylotree(newickstr.value, metrics, { requestId });
        if (!rendered) return;
        setLoadingProgress(4, 4);
        return;
      }

      const availableFullNewick = await fetchFullNewickForSelectedOG(controller.signal);
      if (requestId !== loadRequestSeq || controller.signal.aborted) return;
      setLoadingProgress(1, 4);
      if (availableFullNewick) {
        fullNewick.value = availableFullNewick;
        fullTreeAvailable.value = false;
        noNewickMessage.value = "";

          setLoadingPhaseHint("Fetching orthogroup expression values...");
        await Promise.all([
          fetchOrthogroupDataForAllSpecies(controller.signal),
          fetchHighlightedGenesForAllSpecies(controller.signal),
        ]);
        if (requestId !== loadRequestSeq || controller.signal.aborted) return;
        setLoadingProgress(2, 4);

        const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
        lastMetrics.value = metrics;
        newickstr.value = availableFullNewick;
        await nextTick();
        setLoadingPhaseHint("Rendering phylogenetic tree...");
        const rendered = await initPhylotree(newickstr.value, metrics, { requestId });
        if (!rendered) return;
        setLoadingProgress(4, 4);
        return;
      }

      fullTreeAvailable.value = false;
      noNewickMessage.value = "No phylogenetic tree is available for this orthogroup.";
      newickstr.value = null;
      noNewickResolved.value = true;
      loading.value = false;
      return;
    }

    fullTreeAvailable.value = false;
    noNewickMessage.value = "";

    setLoadingPhaseHint("Fetching orthogroup expression values...");
    await Promise.all([
      fetchOrthogroupDataForAllSpecies(controller.signal),
      fetchHighlightedGenesForAllSpecies(controller.signal),
    ]);
    if (requestId !== loadRequestSeq || controller.signal.aborted) return;
    setLoadingProgress(2, 4);
    
    const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
    lastMetrics.value = metrics;
    const nextNewick = newicks.value[ogKey];
    newickstr.value = typeof nextNewick === "string" && nextNewick.trim() ? nextNewick : null;
    if (newickstr.value !== null) {
      await nextTick();
      setLoadingPhaseHint("Rendering phylogenetic tree...");
      const rendered = await initPhylotree(newickstr.value, metrics, { requestId });
      if (!rendered) return;
      setLoadingProgress(4, 4);
    }
  } catch (error) {
    if (isCanceledRequest(error)) return;
    console.error("Error rendering phylogenetic tree:", error);
    loading.value = false;
  } finally {
    if (requestId === loadRequestSeq) {
      loading.value = false;
      loadingProgress.value = null;
      activeAbortController = null;
      lastCompletedRenderSignature = renderSignature;
      activeRenderSignature = null;
      tracePhyloLoad("render-finish", { origin, requestId });
    }
  }
}

// Load the full Newick for the selected OG directly from the API,
// bypassing the species filter (useful when the current species has
// no entry in the selected orthogroup).
async function loadFullNewickForOG() {
  if (!selectedOrthogroup.value) return;
  const requestId = ++loadRequestSeq;
  activeAbortController?.abort();
  const controller = new AbortController();
  activeAbortController = controller;
  await showLoadingFrame();
  try {
    const newick = await fetchFullNewickForSelectedOG(controller.signal);
    if (requestId !== loadRequestSeq || controller.signal.aborted) return;
    if (!newick) {
      noNewickResolved.value = true;
      loading.value = false;
      return;
    }

    fullNewick.value = newick;  // persist so watchers can't wipe it
    newickstr.value = newick;
    fullTreeAvailable.value = true;
    noNewickMessage.value = "";

    await Promise.all([
      fetchOrthogroupDataForAllSpecies(controller.signal),
      fetchHighlightedGenesForAllSpecies(controller.signal),
    ]);
    if (requestId !== loadRequestSeq || controller.signal.aborted) return;

    const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
    lastMetrics.value = metrics;
    await nextTick();
    const rendered = await initPhylotree(newickstr.value, metrics, { requestId });
    if (rendered && requestId === loadRequestSeq) loading.value = false;
  } catch (e) {
    if (isCanceledRequest(e)) return;
    console.error("Failed to load full gene tree:", e);
    loading.value = false;
  } finally {
    if (requestId === loadRequestSeq) {
      loading.value = false;
      activeAbortController = null;
      loadingProgress.value = null;
    }
  }
}


onMounted(async () => {
  // Parse URL state
  const rawOg = route.query.orthogroup;
  if (rawOg) {
    visualizationStore.setPhyloTreeState({ selectedOrthogroup: String(rawOg) });
  }

  const rawFilters = route.query.filters;
  if (rawFilters) {
    try {
      const parsed = JSON.parse(String(rawFilters));
      if (parsed && typeof parsed === "object") {
        filters.value = parsed;
      }
    } catch {
      // ignore parse errors
    }
  }

  // Mark URL parsing as complete
  initialUrlParsing.value = false;

  // Initial data fetch will be triggered by the watcher
})


// Watch for hashLoading to complete - then trigger initial fetch
watch(
  () => props.hashLoading,
  async (isLoading) => {
    // When hash loading completes (false), trigger initial data fetch
    if (isLoading === false) {
      const ok = await fetchAllSelected({ keepLoading: true });
      if (!ok) return; // superseded by a concurrent watcher trigger
      await renderTreeForSelectedOG("hash-loading-complete");
    }
  },
  { immediate: true }
)


watch(
  () => Object.keys(props.allTables).length,
  async (newCount, oldCount) => {
    if (props.hashLoading) return;
    if (newCount === 0 || newCount === oldCount) return;
    if (!selectedOrthogroup.value) return;

    await renderTreeForSelectedOG("all-tables-ready");
  }
)


// Watch for filter, per-dataset ID filter, and table changes - refetch data
watch(
  [tableNameOptions, filters, () => filtersStore.datasetIdFilters, () => filtersStore.filterChainVersion],
  async () => {
    // Don't fetch while hash is still loading
    if (props.hashLoading) return;
    const currentSig = computeFilterSignature();
    if (lastOgListFilterSig === currentSig) {
      tracePhyloLoad("catalog-filters-skip-current");
      await renderTreeForSelectedOG("catalog-filters-current");
      return;
    }
    const ok = await fetchAllSelected({ keepLoading: true });
    if (!ok) return; // superseded by a concurrent watcher trigger
    await renderTreeForSelectedOG("catalog-filters");
  },
  {deep: true}
)


// Watch for orthogroup selection changes
watch(
  selectedOrthogroup,
  async () => {
    if (suppressSelectedOrthogroupWatcher) return;
    if (initialUrlParsing.value) return;
    if (props.hashLoading) return;
    fullNewick.value = null;  // clear full-tree override when user picks a new OG
    updateUrlFromState();
    // Only re-render the tree/heatmap for the newly selected OG.  Do NOT call
    // fetchAllSelected() here: that rebuilds `commonOGs_array` (the dropdown
    // source) and would collapse the list to whatever the current view
    // contains, breaking dropdown persistence.  The catalog-level OG list is
    // refreshed only when sidebar filters / datasets actually change (see the
    // [tableNameOptions, filters, datasetIdFilters, filterChainVersion]
    // watcher below).
    await renderTreeForSelectedOG("orthogroup-dropdown");
  }
)


watch(
  () => visualizationStore.expressionDisplay,
  async () => {
    if (props.hashLoading) return;
    const ok = await fetchAllSelected({ keepLoading: true });
    if (!ok) return; // superseded by a concurrent watcher trigger
    await renderTreeForSelectedOG("expression-display");
  },
  { deep: true }
);


watch(
  () => visualizationStore.colorScale,
  async () => {
    console.log('[PhylogeneticTree] ColorScale changed:', visualizationStore.colorScale)
    await renderTreeForSelectedOG("color-scale");
  }
);


watch(
  () => visualizationStore.legend,
  async () => {
    console.log('[PhylogeneticTree] Legend toggle changed:', visualizationStore.legend)
    await renderTreeForSelectedOG("legend");
  }
);


// Watch for clustering settings changes (only clusterCols applies to PhyloTree)
watch(
  [
    () => visualizationStore.clustering.clusterCols,
    () => visualizationStore.clustering.method,
    () => visualizationStore.clustering.distance,
  ],
  async () => {
    console.log('[PhylogeneticTree] Clustering settings changed:', visualizationStore.clustering)
    await renderTreeForSelectedOG("clustering");
  },
  { deep: true }
);

watch(
  [
    () => visualizationStore.colOrder.name,
    () => visualizationStore.colOrder.order,
    () => visualizationStore.customColOrder.enabled,
    () => visualizationStore.customColOrder.mode,
    () => visualizationStore.customColOrder.metadataColumn,
    () => visualizationStore.customColOrder.metadataValues.join("\u0000"),
    () => visualizationStore.customColOrder.sampleNames.join("\u0000"),
  ],
  async () => {
    await rerenderCurrentTree(lastMetrics.value);
  },
);

watch(
  selectedGroupingColumn,
  async () => {
    if (props.hashLoading) return;
    if (!newickstr.value) return;
    const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
    lastMetrics.value = metrics;
    await rerenderCurrentTree(metrics);
  },
);


// Watch for phyloTree state changes (reset button, external collapse changes)
watch(
  () => visualizationStore.phyloTree.resetCounter,
  async (newCounter, oldCounter) => {
    if (newCounter !== oldCounter) {
      console.log('[PhylogeneticTree] Reset triggered, resetting zoom and re-rendering');
      
      // Reset the D3 zoom transform on the SVG
      if (phylotreeContainer.value && currentZoomBehavior) {
        const svgElement = phylotreeContainer.value.querySelector('svg');
        if (svgElement) {
          const svgSel = d3.select<SVGSVGElement, unknown>(svgElement);
          svgSel.call(currentZoomBehavior.transform, d3.zoomIdentity);
          console.log('[PhylogeneticTree] D3 zoom reset to identity');
        }
      }
      
      await renderTreeForSelectedOG("reset-counter");
    }
  }
);

// Re-render when collapse state or branch-length mode changes (cheap: no refetch)
watch(
  [
    () => visualizationStore.phyloTree.collapsedNodes,
    () => visualizationStore.phyloTree.branchLengthMode,
  ],
  async () => {
    await rerenderCurrentTree(lastMetrics.value);
  },
  { deep: true }
);

onUnmounted(() => {
  activeAbortController?.abort();
});


</script>

