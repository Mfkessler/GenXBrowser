<template>
  <main class="flex flex-col flex-1 min-w-0 w-full">
    <div class="border border-gray-300 rounded-lg sm:rounded-2xl bg-white p-2 sm:p-3 w-full shadow-sm min-w-0">
      <!-- Loading States -->
      <div v-if="loading || loadingMount" class="flex-grow relative h-[90vh] w-full">
        <LoadingOverlay
          primaryStatus="Comparing expression profiles..."
          :currentPhaseHint="loadingPhaseHint"
          cancellable
          @cancel="cancelActiveLoad"
        />
      </div>

      <!-- Note: rowCount > 1000 check removed for Compare view.
           Compare only displays ONE orthogroup at a time, so the data volume
           is inherently limited. The filtering happens client-side after fetching. -->

      <!-- Main Compare View -->
      <div v-if="selectedTables.length >= 1 && commonOGs_array.length > 0 && !loading && !loadingMount">
        <!-- Control Bar - Compact version with settings in modal -->
        <div class="flex flex-wrap items-center gap-3 mb-4 p-3 bg-gray-50 rounded-lg border border-gray-200 min-w-0">
          <!-- Orthogroup Selector -->
          <div class="flex-grow min-w-0 sm:min-w-48">
            <DropdownMenu
              placeholder="Select orthogroup"
              v-model="selectedOrthogroup"
              :options="commonOGs_options"
            />
          </div>

          <!-- Summary Info -->
          <div class="text-sm text-gray-500 whitespace-nowrap">
            (Transcript Count: {{ processedData?.transcripts.length || 0 }})
          </div>

          <!-- Action Buttons -->
          <div class="flex gap-2 ml-auto flex-shrink-0">
            <button
              aria-label="Share visualization"
              @click="openShareOverlay"
              class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white transition"
              v-tooltip="'Share visualization'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="currentColor" viewBox="0 0 16 16">
                <path d="M13.5 1a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3M11 2.5a2.5 2.5 0 1 1 .603 1.628l-6.718 3.12a2.5 2.5 0 0 1 0 1.504l6.718 3.12a2.5 2.5 0 1 1-.488.876l-6.718-3.12a2.5 2.5 0 1 1 0-3.256l6.718-3.12A2.5 2.5 0 0 1 11 2.5m-8.5 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3m11 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3" />
              </svg>
            </button>
            <button
              aria-label="Export data"
              @click="showExportModal = true"
              class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white transition"
              v-tooltip="'Export data'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
            </button>
            <button
              aria-label="Configure visualization settings"
              @click="showSettingsModal = true"
              class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900 transition"
              v-tooltip="'Configure visualization settings'"
            >
              <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="3"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
              </svg>
            </button>
          </div>
        </div>

        <h2 class="px-2 pb-2 text-sm sm:text-base font-semibold text-gray-700 leading-snug break-words">
          {{ plotTitle }}
        </h2>

        <!-- Plotly Chart Container -->
        <div ref="cardWrapper" class="w-full overflow-hidden">
          <div ref="plotContainer" class="w-full min-h-[30rem] bg-white rounded-lg border border-gray-200"></div>
        </div>

        <!-- Legend (only show for line plots) -->
        <div v-if="plotType === 'line'" class="mt-4 px-3 py-2 text-sm text-gray-600 border-t border-gray-200 flex flex-wrap gap-x-2 gap-y-1">
          <span class="font-medium">Legend:</span>
          <span>thin lines = individual transcripts,</span>
          <span>thick bold lines = species mean of all transcripts</span>
          <span v-if="visualizationStore.compare.showAllTranscripts">| dotted lines (30% opacity) = unfiltered transcripts from same orthogroup</span>
        </div>
        <div v-else class="mt-4 px-3 py-2 text-sm text-gray-600 border-t border-gray-200 flex flex-wrap gap-x-2 gap-y-1">
          <span class="font-medium">Legend:</span>
          <span>{{ plotType === 'box' ? 'Box plots' : 'Violin plots' }} grouped by {{ groupingColumnLabel }}, colored by species</span>
          <span v-if="visualizationStore.compare.showAllTranscripts">| 30% opacity = unfiltered transcripts from same orthogroup</span>
        </div>
      </div>

      <!-- No Intersection -->
      <div v-if="!loadingMount && !loading && selectedTables.length >= 1 && commonOGs_array.length === 0" class="flex-grow relative h-[10vh] w-full">
        <NoIntersectOverlay :nIntersect="0" />
      </div>
    </div>

    <!-- Overlays -->
    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="plotContainerRef"
      :multiPlot="false"
      @close="showShareOverlay = false"
    />

    <!-- Export Modal -->
    <ExportModal
      v-if="showExportModal"
      :data="exportData"
      :columns="exportColumns"
      :metaColumns="exportMetaColumns"
      :sampleColumns="exportSampleColumns"
      :filename="exportFilename"
      :hasFilters="hasActiveFilters"
      :totalCount="exportData.length"
      @close="showExportModal = false"
    />

    <!-- Visualization Settings Modal (unified with other views) -->
    <VisualizationSettings
      :showSettingsOverlay="showSettingsModal"
      context="compare"
      :orthogroupOptions="commonOGs_options"
      @update:show-overlay="showSettingsModal = false"
    />
  </main>
</template>

<!-- eslint-disable vue/multi-word-component-names, @typescript-eslint/no-explicit-any -->
<script setup lang="ts">
defineOptions({ name: "CompareComponent" });

import axios from "axios";
import {
  computed,
  ref,
  unref,
  watch,
  onMounted,
  onUnmounted,
  toRaw,
  nextTick,
} from "vue";
import * as Plotly from "plotly.js-dist-min";

import { API_BASE_URL } from "@/shared/Config";
import { getCategoricalColors } from "@/shared/Colorscales";
import { getExpressionOption } from "@/shared/ExpressionDisplay";
import { useFiltersStore } from "@/stores/filters";
import { useColumnsStore } from "@/stores/columns";
import { useVisualizationStore } from "@/stores/visualization";
import { useFilterSeparation } from "@/shared/useFilterSeparation";
import { beautifyLabel } from "@/shared/utils";
import { hierarchicalCluster } from "@/shared/clustering";
import type { RowType } from "@/shared/RowType";
import type { MetaFormat } from "@/shared/MetaFormat";

import LoadingOverlay from "@/components/LoadingOverlay.vue";
import NoIntersectOverlay from "@/components/NoIntersectOverlay.vue";
import ShareOverlay from "@/components/ShareOverlay.vue";
import ExportModal from "@/components/ExportModal.vue";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import DropdownMenu from "@/components/DropdownMenu.vue";

import { useRoute, useRouter } from "vue-router";

// ============================================================================
// Types
// ============================================================================
interface SampleValue {
  value: number;
  sampleName: string;
}

interface TranscriptData {
  geneId: string;
  species: string;
  values: Record<string, SampleValue[]>;
  filterMatched: boolean; // true if transcript passed the active filter
}

interface ProcessedData {
  transcripts: TranscriptData[];
  groups: string[];
  species: string[];
}

// ============================================================================
// Props & Emits
// ============================================================================
const props = defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
  initialSpecies?: string[] | null;  // For hash-based loads: all species to load
  initialOrthogroup?: string | null;  // For hash-based loads: pre-selected orthogroup
}>();

const emit = defineEmits(["load-cancel"]);

// ============================================================================
// Stores & Router
// ============================================================================
const route = useRoute();
const router = useRouter();
const filtersStore = useFiltersStore();
const columnsStore = useColumnsStore();
const visualizationStore = useVisualizationStore();
const { filters, sampleFilters, filterChainVersion, getMergedGeneFilters, getFilterChainPayload } = useFilterSeparation();

// ============================================================================
// Reactive State
// ============================================================================
const loading = ref(false);
const loadingMount = ref(true);
const loadingProgress = ref<number | null>(null);
const loadingPhaseHint = ref("Preparing comparison request...");
const initialUrlParsing = ref(true); // Guard against watchers during URL parsing
const showShareOverlay = ref(false);
const showExportModal = ref(false);
const showSettingsModal = ref(false);

// Plot type dropdown UI state
const showPlotTypeDropdown = ref(false);
const plotTypeDropdownRef = ref<HTMLDivElement | null>(null);

// Selection state
// Initialize with all species - we need to load all data to know which species have which OGs
const selectedTables = ref<string[]>([]);

// Data state
const tableData = ref<Record<string, any>>({});
const unfilteredTableData = ref<Record<string, any>>({});
const commonOGs_array = ref<string[]>([]);

// Plot state
const cardWrapper = ref<HTMLDivElement | null>(null);
const plotContainer = ref<HTMLDivElement | null>(null);
const plotContainerRef = computed(() => ref(plotContainer.value));

// No filter dropdowns needed - Plotly legend handles species visibility

// Processed data for plotting
const processedData = ref<ProcessedData | null>(null);
let loadRequestSeq = 0;
let activeAbortController: AbortController | null = null;

function setLoadingProgress(step: number, totalSteps: number) {
  loadingProgress.value = totalSteps > 0 ? (step / totalSteps) * 100 : null;
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
  loading.value = false;
  loadingMount.value = false;
  loadingProgress.value = null;
  setLoadingPhaseHint("Load canceled");
  if (emitCancel) emit("load-cancel");
}

defineExpose({ cancelActiveLoad });

// ============================================================================
// Store-backed Computed Properties (Single Source of Truth)
// ============================================================================
const plotType = computed({
  get: () => visualizationStore.compare.plotType,
  set: (v: 'line' | 'box' | 'violin') => visualizationStore.setCompareState({ plotType: v })
});

const plotHeight = computed({
  get: () => visualizationStore.compare.plotHeight,
  set: (v: number) => visualizationStore.setCompareState({ plotHeight: v })
});

const selectedOrthogroup = computed({
  get: () => visualizationStore.compare.selectedOrthogroup,
  set: (v: string) => visualizationStore.setCompareState({ selectedOrthogroup: v })
});

const expressionDisplayOption = computed({
  get: () => visualizationStore.compare.expression,
  set: (v: string) => visualizationStore.setCompareState({ expression: v })
});

const selectedGroupingColumn = computed(() => {
  const configured = visualizationStore.compare.groupingColumn;
  if (configured && columnsStore.filterableColColumns.some((col) => col.column_name === configured)) {
    return configured;
  }
  return columnsStore.tissueColumnName || columnsStore.filterableColColumns[0]?.column_name || 'tissue';
});

const groupingColumnLabel = computed(() => {
  const column = columnsStore.filterableColColumns.find((col) => col.column_name === selectedGroupingColumn.value);
  return (column?.display_name || selectedGroupingColumn.value || 'sample group').toString();
});

// Species visibility is controlled by Plotly's built-in legend click functionality
  // Sample groups are filtered via sampleFilters (Samples tab in sidebar)

// ============================================================================
// Computed Properties
// ============================================================================
const selectedOrthogroupLabel = computed(() => {
  return commonOGs_array.value.includes(selectedOrthogroup.value)
    ? selectedOrthogroup.value
    : "";
});

const plotTypeLabels: Record<string, string> = {
  line: "Line Plot",
  box: "Box Plot",
  violin: "Violin Plot",
};

const plotTitle = computed(() => {
  const orthogroup = selectedOrthogroupLabel.value
    ? selectedOrthogroupLabel.value.toUpperCase()
    : "";
  return `Orthogroup Expression: ${orthogroup} (${plotTypeLabels[plotType.value]})`;
});

// Convert array to Record for DropdownMenu compatibility
const commonOGs_options = computed(() => {
  const record: Record<string, string> = {};
  commonOGs_array.value.forEach((og) => {
    record[og] = og.toUpperCase();
  });
  return record;
});

// Removed totalTranscripts - using processedData.transcripts.length directly

// Species colors (consistent across renders)
const speciesColors = computed(() => {
  // Use all available species from props
  const allSpeciesKeys = Object.keys(props.allTables).sort();
  const colors = getCategoricalColors(allSpeciesKeys.length);
  const colorMap: Record<string, string> = {};
  allSpeciesKeys.forEach((sp, i) => {
    colorMap[sp] = colors[i];
  });
  return colorMap;
});

// Export modal computed properties
const hasActiveFilters = computed(() => Object.keys(filters.value).length > 0);

const exportFilename = computed(() => {
  return `compare_${selectedOrthogroupLabel.value}_${expressionDisplayOption.value}`;
});

const exportMetaColumns = computed(() => ['species', filtersStore.idColumnName]);

const exportSampleColumns = computed(() => {
  if (!processedData.value) return [];
  return processedData.value.groups;
});

const exportColumns = computed(() => {
  return [...exportMetaColumns.value, ...exportSampleColumns.value];
});

const exportData = computed<RowType[]>(() => {
  if (!processedData.value) return [];
  
  // Export all transcripts from all species - no filter
  const filteredTranscripts = processedData.value.transcripts;
  const filteredTissues = processedData.value.groups;
  
  return filteredTranscripts.map((t) => {
    const row: RowType = {
      species: beautifyLabel(t.species),
      [filtersStore.idColumnName]: t.geneId,
    };
    filteredTissues.forEach((tissue) => {
      const vals = t.values[tissue];
      if (vals && vals.length > 0) {
        const mean = vals.reduce((sum, sample) => sum + sample.value, 0) / vals.length;
        row[tissue] = parseFloat(mean.toFixed(4));
      } else {
        row[tissue] = null;
      }
    });
    return row;
  });
});

// Share overlay - no sync needed since store is now Single Source of Truth
function openShareOverlay() {
  showShareOverlay.value = true;
}

// ============================================================================
// Expression Display Helpers
// ============================================================================
function getExpressionParams(optionId: string): { layer: string | null; transform: 'raw' | 'log2' | 'zscore' } {
  // Use shared ExpressionDisplay configuration for consistency with Heatmap
  const option = getExpressionOption(optionId);
  if (option) {
    return { layer: option.layer, transform: option.transform };
  }
  // Fallback defaults
  return { layer: "tpm", transform: "raw" };
}

// ============================================================================
// URL State Management
// ============================================================================
function updateUrlFromState() {
  const newQuery: Record<string, string> = { ...route.query } as Record<string, string>;
  delete newQuery.tables;

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

  // Save compare-specific settings
  newQuery.expression = expressionDisplayOption.value;
  newQuery.plotType = plotType.value;
  newQuery.plotHeight = String(plotHeight.value);
  
  // Species visibility is controlled by Plotly legend - no need to save to URL

  router.replace({
    name: route.name ?? undefined,
    query: newQuery,
  });
}

// ============================================================================
// Data Fetching
// ============================================================================
async function fetchData(tableName: string, signal?: AbortSignal) {
  try {
    // Note: We don't check row count limit for Compare view because:
    // 1. Compare only displays ONE orthogroup at a time (selected via dropdown)
    // 2. The orthogroup filtering happens client-side after fetching
    // 3. Even with many genes, only the selected orthogroup's data is rendered
    const params = getExpressionParams(expressionDisplayOption.value);
    const tableLabel = beautifyLabel(tableName);

    setLoadingPhaseHint(`Fetching ${tableLabel} expression values...`);
    const { data: responseData } = await axios.post(`${API_BASE_URL}/api/data`, {
      table_name: tableName,
      filters: getMergedGeneFilters(tableName).value,
      filter_chain: getFilterChainPayload(getMergedGeneFilters(tableName).value),
      sample_filters: sampleFilters.value,
      layer: params.layer,
      transform: params.transform,
    }, { signal });

    const data = responseData.data || responseData;
    
    // Return null if no data
    if (!data || Object.keys(data).length === 0) {
      return null;
    }

    // Get data columns
    setLoadingPhaseHint(`Loading ${tableLabel} sample columns...`);
    const columnRes = await axios.get<MetaFormat[]>(`${API_BASE_URL}/api/columns`, {
      params: { table_name: tableName, meta: false },
      signal,
    });
    const dataColumnNames = columnRes.data.map((c) => c.column_name);

    // Get metadata
    setLoadingPhaseHint(`Loading ${tableLabel} sample metadata...`);
    const { data: metaResponseData } = await axios.post(`${API_BASE_URL}/api/data`, {
      table_name: tableName + "_meta",
      filters: {},
    }, { signal });

    const colData = metaResponseData.data || metaResponseData;
    const columns = (Array.isArray(colData) ? colData : []).filter((meta: RowType) =>
      dataColumnNames.includes(meta.column_name as string)
    );
    columnsStore.setSampleMetadata(columns as Record<string, unknown>[], tableName);

    setLoadingPhaseHint(`Preparing ${tableLabel} orthogroup data...`);
    const enrichedData = Object.keys(data).map((key) => ({ ...data[key] }));

    return { items: enrichedData, sampleMetadata: columns, tableName };
  } catch (e) {
    if (isCanceledRequest(e)) return null;
    console.error("Error fetching data:", e);
  }
  return null;
}

async function fetchAllSelected() {
  const requestId = ++loadRequestSeq;
  activeAbortController?.abort();
  const controller = new AbortController();
  activeAbortController = controller;
  loading.value = true;
  loadingProgress.value = 0;
  setLoadingPhaseHint("Loading selected datasets...");

  console.log('[Compare] fetchAllSelected - selectedTables:', selectedTables.value);

  try {
    const results: Record<string, any> = {};
    const unfilteredCount = visualizationStore.compare.showAllTranscripts && selectedOrthogroup.value
      ? selectedTables.value.length
      : 0;
    const totalSteps = Math.max(1, selectedTables.value.length + unfilteredCount + 2);
    let completedSteps = 0;
    for (const tableName of selectedTables.value) {
      console.log('[Compare] Fetching data for table:', tableName);
      const result = await fetchData(tableName, controller.signal);
      if (requestId !== loadRequestSeq || controller.signal.aborted) return;
      console.log('[Compare] Fetched result for', tableName, ':', result ? 'success' : 'null');
      results[tableName] = result;
      setLoadingProgress(++completedSteps, totalSteps);
    }

    console.log('[Compare] All results keys:', Object.keys(results));
    console.log('[Compare] Results with data:', Object.entries(results).filter((entry) => entry[1] !== null).map(([k]) => k));
    
    tableData.value = results;
    setLoadingPhaseHint("Finding shared orthogroups...");
    const allOGs = getAllOGs(results);
    commonOGs_array.value = [...allOGs].sort();

    // If showAllTranscripts is enabled, fetch unfiltered data for the SELECTED orthogroup
    console.log('[FetchAllSelected] showAllTranscripts:', visualizationStore.compare.showAllTranscripts);
    console.log('[FetchAllSelected] selectedOrthogroup:', selectedOrthogroup.value);
    console.log('[FetchAllSelected] commonOGs length:', commonOGs_array.value.length);
    
    // BUGFIX: Only fetch unfiltered data for the selected orthogroup, not all common orthogroups
    // This ensures "All Transcripts" works regardless of whether there's an orthogroup filter in the sidebar
    if (visualizationStore.compare.showAllTranscripts && selectedOrthogroup.value) {
      console.log('[FetchAllSelected] Fetching unfiltered data for selected OG:', selectedOrthogroup.value);
      const unfilteredResults: Record<string, any> = {};
      for (const tableName of selectedTables.value) {
        setLoadingPhaseHint(`Fetching unfiltered ${beautifyLabel(tableName)} transcripts...`);
        const result = await fetchUnfilteredData(tableName, [selectedOrthogroup.value], controller.signal);
        if (requestId !== loadRequestSeq || controller.signal.aborted) return;
        unfilteredResults[tableName] = result;
        setLoadingProgress(++completedSteps, totalSteps);
        if (result) {
          console.log('[FetchAllSelected] Got unfiltered data for', tableName, ':', result.items?.length || 0, 'items');
        } else {
          console.warn('[FetchAllSelected] No unfiltered data for', tableName);
        }
      }
      const totalUnfilteredItems = Object.values(unfilteredResults).reduce((sum, r: any) => sum + (r?.items?.length || 0), 0);
      console.log('[FetchAllSelected] Total unfiltered items:', totalUnfilteredItems);
      unfilteredTableData.value = unfilteredResults;
    } else {
      console.log('[FetchAllSelected] Clearing unfiltered data (showAllTranscripts:', visualizationStore.compare.showAllTranscripts, ', selectedOG:', !!selectedOrthogroup.value, ')');
      unfilteredTableData.value = {};
    }

    // Handle OG selection with persistence and fallback
    // Keep current selection if still valid (case-insensitive), otherwise select first
    const currentSelection = selectedOrthogroup.value;
    if (commonOGs_array.value.length > 0) {
      const matchingOG = commonOGs_array.value.find(
        og => og.toLowerCase() === currentSelection?.toLowerCase()
      );
      if (matchingOG) {
        selectedOrthogroup.value = matchingOG;
      } else {
        selectedOrthogroup.value = commonOGs_array.value[0];
      }
    } else {
      selectedOrthogroup.value = '';
    }
    setLoadingProgress(totalSteps - 1, totalSteps);
    setLoadingPhaseHint("Rendering comparison plot...");
    await nextTick();
    await renderPlot();
    setLoadingProgress(totalSteps, totalSteps);
  } catch (e) {
    if (isCanceledRequest(e)) return;
    console.error("Error loading comparison data:", e);
  } finally {
    if (requestId === loadRequestSeq) {
      activeAbortController = null;
      loading.value = false;
      loadingProgress.value = null;
    }
  }
}

// Get orthogroups based on selected dataset count:
// - Single dataset: return ALL orthogroups from that dataset (union)
// - Multiple datasets: return ONLY orthogroups present in ALL datasets (intersection)
function getAllOGs(dataRef: Record<string, any>): Set<string> {
  const raw = toRaw(unref(dataRef));

  const sets = Object.values(raw)
    .map((plant) => {
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

  // Single dataset: return union (all OGs from that dataset)
  if (sets.length === 1) {
    return sets[0];
  }

  // Multiple datasets: return intersection (only OGs in ALL datasets)
  return sets.reduce((acc, s) => new Set([...acc].filter((og) => s.has(og))));
}

/**
 * Fetch unfiltered data for specific orthogroups.
 * Used by "All Transcripts" mode to get transcripts not passing the current filter
 * but belonging to matched orthogroups.
 */
async function fetchUnfilteredData(tableName: string, ogIds: string[], signal?: AbortSignal) {
  console.log('[FetchUnfiltered] Starting fetch for', tableName, 'with', ogIds.length, 'OGs');
  console.log('[FetchUnfiltered] OG IDs:', ogIds);
  try {
    const params = getExpressionParams(expressionDisplayOption.value);

    // Get current active filters to understand the structure
    const currentGeneFilters = getMergedGeneFilters(tableName).value;
    console.log('[FetchUnfiltered] Current active gene filters:', JSON.stringify(currentGeneFilters, null, 2));

    // Determine the correct OG column name — h5ad standard is 'ortho_id'
    let ogFilterKey = 'ortho_id'; // default
    const existingData = tableData.value[tableName];
    if (existingData?.items) {
      const items = Array.isArray(existingData.items) 
        ? existingData.items 
        : Object.values(existingData.items);
      if (items.length > 0) {
        const firstItem = items[0];
        // Check which column exists in the data
        if (firstItem.hasOwnProperty('ortho_id')) {
          ogFilterKey = 'ortho_id';
        }
      }
    }

    // Check if the current filter has a specific structure we need to match
    const existingOgFilter = currentGeneFilters[ogFilterKey];
    console.log('[FetchUnfiltered] Existing OG filter structure:', typeof existingOgFilter, existingOgFilter);

    // IMPORTANT: Get the original case OG value
    // 1. Try to get from active filter (preserves case)
    // 2. If no filter exists, extract from the loaded data (critical for case-sensitive API)
    let ogValue = ogIds.join(',');
    if (existingOgFilter && typeof existingOgFilter === 'object' && existingOgFilter.value) {
      ogValue = existingOgFilter.value;
      console.log('[FetchUnfiltered] Using OG value from active filter (preserves case):', ogValue);
    } else {
      // BUGFIX: Extract original case from loaded data
      // ogIds are lowercase, but API is case-sensitive
      const originalCaseOGs: string[] = [];
      const existingData = tableData.value[tableName];
      if (existingData?.items) {
        const items = Array.isArray(existingData.items) 
          ? existingData.items 
          : Object.values(existingData.items);
        const lowerToOriginalMap = new Map<string, string>();
        items.forEach((item: any) => {
          const ogVal = item?.ortho_id;
          if (ogVal) {
            const lower = String(ogVal).trim().toLowerCase();
            if (!lowerToOriginalMap.has(lower)) {
              lowerToOriginalMap.set(lower, String(ogVal).trim());
            }
          }
        });
        
        ogIds.forEach(lowercaseOg => {
          const originalCase = lowerToOriginalMap.get(lowercaseOg);
          if (originalCase) {
            originalCaseOGs.push(originalCase);
          } else {
            console.warn('[FetchUnfiltered] Could not find original case for:', lowercaseOg);
            originalCaseOGs.push(lowercaseOg);
          }
        });
      } else {
        originalCaseOGs.push(...ogIds);
      }
      
      ogValue = originalCaseOGs.join(',');
      console.log('[FetchUnfiltered] No existing OG filter, extracted original case from data:', ogValue);
    }

    // Fetch data with orthogroup filter only (no gene filters)
    // IMPORTANT: Match the filter structure from the active filters
    // Filters are objects with a `value` property, not plain strings
    const ogOnlyFilter = {
      [ogFilterKey]: {
        value: ogValue,
      }
    };

    console.log('[FetchUnfiltered] Active gene filters being ignored:', Object.keys(currentGeneFilters).filter(k => k !== ogFilterKey));
    console.log('[FetchUnfiltered] Request params:', { 
      tableName, 
      ogFilterKey,
      ogFilterValue: ogOnlyFilter[ogFilterKey],
      ogFilterValueType: typeof ogOnlyFilter[ogFilterKey],
      filterKeys: Object.keys(ogOnlyFilter),
      layer: params.layer, 
      transform: params.transform 
    });

    const { data: responseData } = await axios.post(`${API_BASE_URL}/api/data`, {
      table_name: tableName,
      filters: ogOnlyFilter,  // Send ONLY the OG filter
      sample_filters: {},     // Empty sample filters
      layer: params.layer,
      transform: params.transform,
    }, { signal });

    console.log('[FetchUnfiltered] Response received for', tableName);
    const data = responseData.data || responseData;
    const dataKeys = data ? Object.keys(data).length : 0;
    console.log('[FetchUnfiltered] Data keys count:', dataKeys);
    
    // Check what OGs are actually in the returned data
    if (data && dataKeys > 0) {
      const ogSet = new Set<string>();
      Object.values(data).forEach((item: any) => {
        const ogVal = item?.ortho_id;
        if (ogVal) ogSet.add(String(ogVal));
      });
      console.log('[FetchUnfiltered] Unique OGs in response:', Array.from(ogSet).sort());
      console.log('[FetchUnfiltered] OGs match requested?', ogIds.some(id => ogSet.has(id)));
    }
    
    if (!data || Object.keys(data).length === 0) {
      console.warn('[FetchUnfiltered] Empty data for', tableName);
      return null;
    }

    // Reuse sample metadata from filtered data
    const existingResult = tableData.value[tableName];
    const sampleMetadata = existingResult?.sampleMetadata || [];
    console.log('[FetchUnfiltered] Sample metadata rows:', sampleMetadata.length);

    const enrichedData = Object.keys(data).map((key) => ({ ...data[key] }));

    console.log('[FetchUnfiltered] Returning', enrichedData.length, 'enriched items for', tableName);
    return { items: enrichedData, sampleMetadata, tableName };
  } catch (e) {
    if (isCanceledRequest(e)) return null;
    console.error('[FetchUnfiltered] Error fetching unfiltered data for', tableName, ':', e);
  }
  return null;
}

// ============================================================================
// Data Processing for Plotting
// ============================================================================
function processDataForPlotting(og: string): ProcessedData | null {
  console.log('[ProcessData] Processing OG:', og);
  const raw = toRaw(tableData.value);
  const rawUnfiltered = toRaw(unfilteredTableData.value);
  const needle = String(og).trim().toLowerCase();
  const showAll = visualizationStore.compare.showAllTranscripts;

  console.log('[ProcessData] showAll:', showAll);
  console.log('[ProcessData] rawUnfiltered keys:', Object.keys(rawUnfiltered).length);
  console.log('[ProcessData] raw keys:', Object.keys(raw).length);

  const transcripts: TranscriptData[] = [];
  const groupSet = new Set<string>();
  const speciesSet = new Set<string>();

  // Track gene IDs from filtered data to identify unfiltered-only transcripts
  const filteredGeneIds = new Set<string>();

  Object.entries(raw).forEach(([tableName, tableInfo]) => {
    if (!tableInfo?.items) return;

    const items = Array.isArray(tableInfo.items)
      ? tableInfo.items
      : Object.values(tableInfo.items);
    const groupMap = buildSampleGroupMap(tableInfo.sampleMetadata || []);

    // Filter by orthogroup
    const matchingItems = items.filter((item: any) => {
      const ogVal = item?.ortho_id;
      return ogVal != null && String(ogVal).trim().toLowerCase() === needle;
    });

    matchingItems.forEach((item: any) => {
      const geneId = item[filtersStore.idColumnName] || item.gene_id || "unknown";
      filteredGeneIds.add(`${tableName}::${geneId}`);
      const values: Record<string, SampleValue[]> = {};

      Object.entries(item).forEach(([key, value]) => {
        if (typeof value === "number" && groupMap[key]) {
          const group = groupMap[key];
          if (!values[group]) values[group] = [];
          values[group].push({
            value: value,
            sampleName: key
          });
          groupSet.add(group);
        }
      });

      transcripts.push({
        geneId,
        species: tableName,
        values,
        filterMatched: true,
      });

      speciesSet.add(tableName);
    });
  });

  // Add unfiltered transcripts (from "All Transcripts" mode)
  console.log('[ProcessData] Filtered transcripts so far:', transcripts.length);
  console.log('[ProcessData] Filtered gene IDs:', filteredGeneIds.size);
  
  if (showAll && Object.keys(rawUnfiltered).length > 0) {
    console.log('[ProcessData] Adding unfiltered transcripts...');
    let unfilteredAdded = 0;
    let unfilteredSkipped = 0;
    
    Object.entries(rawUnfiltered).forEach(([tableName, tableInfo]) => {
      if (!tableInfo?.items) {
        console.warn('[ProcessData] No items for', tableName, 'in unfiltered data');
        return;
      }

      const items = Array.isArray(tableInfo.items)
        ? tableInfo.items
        : Object.values(tableInfo.items);
      const groupMap = buildSampleGroupMap(tableInfo.sampleMetadata || []);
      
      console.log('[ProcessData] Table', tableName, '- items:', items.length, 'groupMap keys:', Object.keys(groupMap).length);

      const matchingItems = items.filter((item: any) => {
        const ogVal = item?.ortho_id;
        return ogVal != null && String(ogVal).trim().toLowerCase() === needle;
      });
      
      console.log('[ProcessData] Table', tableName, '- matching items for OG:', matchingItems.length);
      
      // Debug: Show some OG values that ARE in the data
      if (matchingItems.length === 0 && items.length > 0) {
        const sampleOGs = items.slice(0, 5).map((item: any) => item?.ortho_id);
        console.warn('[ProcessData] No matches! Sample OG values in data:', sampleOGs);
        console.warn('[ProcessData] Looking for (needle):', needle);
      }

      matchingItems.forEach((item: any) => {
        const geneId = item[filtersStore.idColumnName] || item.gene_id || "unknown";
        const key = `${tableName}::${geneId}`;

        // Skip transcripts already in filtered data
        if (filteredGeneIds.has(key)) {
          unfilteredSkipped++;
          return;
        }

        const values: Record<string, SampleValue[]> = {};
        Object.entries(item).forEach(([k, value]) => {
          if (typeof value === "number" && groupMap[k]) {
            const group = groupMap[k];
            if (!values[group]) values[group] = [];
            values[group].push({
              value: value as number,
              sampleName: k,
            });
            groupSet.add(group);
          }
        });

        transcripts.push({
          geneId,
          species: tableName,
          values,
          filterMatched: false,
        });
        unfilteredAdded++;

        speciesSet.add(tableName);
      });
    });
    
    console.log('[ProcessData] Unfiltered transcripts added:', unfilteredAdded, 'skipped (already in filtered):', unfilteredSkipped);
  } else if (showAll) {
    console.warn('[ProcessData] showAll is true but rawUnfiltered is empty!');
  }

  console.log('[ProcessData] Final transcript count:', transcripts.length, '(filtered:', transcripts.filter(t => t.filterMatched).length, 'unfiltered:', transcripts.filter(t => !t.filterMatched).length, ')');

  return {
    transcripts,
    groups: orderGroupCategories([...groupSet], transcripts),
    species: [...speciesSet].sort(),
  };
}

function buildSampleGroupMap(sampleMetadata: RowType[]): Record<string, string> {
  const groupMap: Record<string, string> = {};
  const groupColumn = selectedGroupingColumn.value;
  sampleMetadata.forEach((item: RowType) => {
    if (!("column_name" in item)) return;
    const rawValue = (item as any)[groupColumn];
    groupMap[item.column_name as string] = rawValue !== null && rawValue !== undefined && String(rawValue) !== ""
      ? String(rawValue)
      : "Unknown";
  });
  return groupMap;
}

function orderGroupCategories(groups: string[], transcripts: TranscriptData[]): string[] {
  const customOrder = visualizationStore.customColOrder;
  if (customOrder.enabled && customOrder.metadataValues.length > 0) {
    const groupRank = getGroupRankFromAxis(customOrder.metadataValues);
    return [...groups].sort((a, b) => {
      const aRank = groupRank.get(a.toLowerCase()) ?? Number.MAX_SAFE_INTEGER;
      const bRank = groupRank.get(b.toLowerCase()) ?? Number.MAX_SAFE_INTEGER;
      if (aRank !== bRank) return aRank - bRank;
      return a.localeCompare(b);
    });
  }
  if (visualizationStore.colOrder.name && visualizationStore.colOrder.name !== "OLO") {
    return orderAxisCategories(groups, visualizationStore.colOrder.order);
  }
  const sortedGroups = orderAxisCategories(groups, "asc");
  if (visualizationStore.clustering.clusterCols && sortedGroups.length > 2) {
    try {
      const groupProfiles = sortedGroups.map((group) => transcripts.map((transcript) => {
        const values = transcript.values[group] ?? [];
        if (values.length === 0) return 0;
        return values.reduce((sum, item) => sum + item.value, 0) / values.length;
      }));
      const clusterResult = hierarchicalCluster(
        groupProfiles,
        visualizationStore.clustering.method,
        visualizationStore.clustering.distance,
      );
      return clusterResult.order.map((index) => sortedGroups[index]);
    } catch (error) {
      console.warn('Compare column clustering failed, using alphabetical order:', error);
    }
  }
  return sortedGroups;
}

function getGroupRankFromAxis(orderedValues: string[]): Map<string, number> {
  return new Map(orderedValues.map((value, index) => [value.toLowerCase(), index]));
}

function orderAxisCategories(groups: string[], direction: "asc" | "desc"): string[] {
  return [...groups].sort((a, b) => {
    const comparison = a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });
    return direction === "desc" ? -comparison : comparison;
  });
}

// ============================================================================
// Plotly Rendering
// ============================================================================
async function renderPlot() {
  console.log('[RenderPlot] Starting render...');
  if (!plotContainer.value || !selectedOrthogroupLabel.value) {
    console.log('[RenderPlot] Missing container or orthogroup');
    return;
  }

  const data = processDataForPlotting(selectedOrthogroupLabel.value);
  if (!data || data.transcripts.length === 0) {
    console.log('[RenderPlot] No data or transcripts to plot');
    Plotly.purge(plotContainer.value);
    return;
  }

  processedData.value = data;
  console.log('[RenderPlot] processedData.value set. Transcript count:', data.transcripts.length);

  // Always render ALL species - Plotly legend handles visibility
  const filteredTranscripts = data.transcripts;
  // Use all available groups from the data (already filtered by sampleFilters)
  const filteredTissues = data.groups;

  if (filteredTranscripts.length === 0 || filteredTissues.length === 0) {
    Plotly.purge(plotContainer.value);
    return;
  }

  const traces: Plotly.Data[] = [];
  const colors = speciesColors.value;

  // Group transcripts by species
  const bySpecies: Record<string, TranscriptData[]> = {};
  filteredTranscripts.forEach((t) => {
    if (!bySpecies[t.species]) bySpecies[t.species] = [];
    bySpecies[t.species].push(t);
  });

  const showAll = visualizationStore.compare.showAllTranscripts;

  // Create traces for each species
  Object.entries(bySpecies).forEach(([species, speciesTranscripts]) => {
    const color = colors[species] || "#888";
    const speciesLabel = beautifyLabel(species);
    const speciesLabelItalic = `<i>${speciesLabel}</i>`;

    // Separate filtered and unfiltered transcripts
    const matchedTranscripts = speciesTranscripts.filter(t => t.filterMatched);
    const unmatchedTranscripts = speciesTranscripts.filter(t => !t.filterMatched);

    if (plotType.value === 'line') {
      // LINE PLOT: Individual transcript traces (thin lines) — filtered transcripts
      matchedTranscripts.forEach((transcript, idx) => {
        // Build customdata with sample details for each tissue
        const customData = filteredTissues.map((tissue) => {
          const vals = transcript.values[tissue];
          if (!vals || vals.length === 0) return { samples: [], nSamples: 0 };
          return {
            samples: vals.map((sv) => ({ name: sv.sampleName, value: sv.value })),
            nSamples: vals.length,
          };
        });

        const yValues = filteredTissues.map((tissue) => {
          const vals = transcript.values[tissue];
          if (!vals || vals.length === 0) return null;
          return vals.reduce((a, b) => a + b.value, 0) / vals.length; // Mean across samples
        });

        // Build hover text with sample details (showing real sample names)
        const hoverText = filteredTissues.map((tissue, tissueIdx) => {
          const data = customData[tissueIdx];
          const mean = yValues[tissueIdx];
          let text = `<b>${transcript.geneId}</b><br>` +
            `Species: ${speciesLabelItalic}<br>` +
            `${groupingColumnLabel.value}: ${tissue}<br>` +
            `Mean: ${mean !== null ? mean.toFixed(3) : 'N/A'}<br>`;
          if (data.nSamples > 0) {
            text += `<br><b>Samples (n=${data.nSamples}):</b><br>`;
            data.samples.forEach((s: { name: string; value: number }) => {
              text += `  ${s.name}: ${s.value.toFixed(3)}<br>`;
            });
          }
          return text;
        });

        traces.push({
          x: filteredTissues,
          y: yValues,
          type: "scatter",
          mode: "lines+markers",
          name: speciesLabelItalic,
          legendgroup: species,
          showlegend: idx === 0, // Only show one legend entry per species group
          line: {
            color: color,
            width: 1.5,
            dash: "solid",
          },
          marker: {
            size: 5,
            color: color,
          },
          opacity: 0.6,
          hovertemplate: '%{text}<extra></extra>',
          text: hoverText,
        } as unknown as Plotly.Data);
      });

      // Species mean trace (thick bold line) — uses only filtered transcripts
      // Build hover text with sample count for each tissue
      const meanHoverText = filteredTissues.map((tissue) => {
        const allVals: number[] = [];
        matchedTranscripts.forEach((t) => {
          const vals = t.values[tissue];
          if (vals) {
            vals.forEach((sv) => allVals.push(sv.value));
          }
        });
        const mean = allVals.length > 0 
          ? allVals.reduce((a, b) => a + b, 0) / allVals.length 
          : null;
        return `<b>${speciesLabelItalic} Mean</b><br>` +
          `${groupingColumnLabel.value}: ${tissue}<br>` +
          `Mean: ${mean !== null ? mean.toFixed(3) : 'N/A'}<br>` +
          `Transcripts: ${matchedTranscripts.length}<br>` +
          `Samples: ${allVals.length}`;
      });

      const meanYValues = filteredTissues.map((tissue) => {
        const allVals: number[] = [];
        matchedTranscripts.forEach((t) => {
          const vals = t.values[tissue];
          if (vals) {
            vals.forEach((sv) => allVals.push(sv.value));
          }
        });
        if (allVals.length === 0) return null;
        return allVals.reduce((a, b) => a + b, 0) / allVals.length;
      });

      traces.push({
        x: filteredTissues,
        y: meanYValues,
        type: "scatter",
        mode: "lines",
        name: `${speciesLabelItalic} (mean)`,
        legendgroup: species,
        showlegend: true,
        line: {
          color: color,
          width: 4,
        },
        hovertemplate: '%{text}<extra></extra>',
        text: meanHoverText,
      } as unknown as Plotly.Data);

      // Unfiltered transcript traces (dashed, reduced opacity)
      if (showAll && unmatchedTranscripts.length > 0) {
        const unfilteredLegendGroup = `${species}_unfiltered`;

        unmatchedTranscripts.forEach((transcript, idx) => {
          const yValues = filteredTissues.map((tissue) => {
            const vals = transcript.values[tissue];
            if (!vals || vals.length === 0) return null;
            return vals.reduce((a, b) => a + b.value, 0) / vals.length;
          });

          const hoverText = filteredTissues.map((tissue) => {
            const vals = transcript.values[tissue];
            const mean = vals && vals.length > 0
              ? vals.reduce((a, b) => a + b.value, 0) / vals.length
              : null;
            let text = `<b>${transcript.geneId}</b> (unfiltered)<br>` +
              `Species: ${speciesLabelItalic}<br>` +
              `${groupingColumnLabel.value}: ${tissue}<br>` +
              `Mean: ${mean !== null ? mean.toFixed(3) : 'N/A'}<br>`;
            if (vals && vals.length > 0) {
              text += `<br><b>Samples (n=${vals.length}):</b><br>`;
              vals.forEach((s) => {
                text += `  ${s.sampleName}: ${s.value.toFixed(3)}<br>`;
              });
            }
            return text;
          });

          traces.push({
            x: filteredTissues,
            y: yValues,
            type: "scatter",
            mode: "lines+markers",
            name: `${speciesLabelItalic} (unfiltered)`,
            legendgroup: unfilteredLegendGroup,
            showlegend: idx === 0,
            line: {
              color: color,
              width: 1,
              dash: "dot",
            },
            marker: {
              size: 4,
              color: color,
            },
            opacity: 0.3,
            hovertemplate: '%{text}<extra></extra>',
            text: hoverText,
          } as unknown as Plotly.Data);
        });
      }
    } else if (plotType.value === 'box' || plotType.value === 'violin') {
      // BOX/VIOLIN PLOT: One trace per species, grouped by selected sample metadata
      // Collect values from filtered transcripts
      const xValues: string[] = [];
      const yValues: number[] = [];
      const hoverTexts: string[] = [];
      
      filteredTissues.forEach((tissue) => {
        matchedTranscripts.forEach((transcript) => {
          const vals = transcript.values[tissue];
          if (vals && vals.length > 0) {
            vals.forEach((sv) => {
              xValues.push(tissue);
              yValues.push(sv.value);
              hoverTexts.push(
                `<b>${transcript.geneId}</b><br>` +
                `Species: ${speciesLabelItalic}<br>` +
                `${groupingColumnLabel.value}: ${tissue}<br>` +
                `${sv.sampleName}: ${sv.value.toFixed(3)}`
              );
            });
          }
        });
      });

      if (plotType.value === 'box') {
        traces.push({
          x: xValues,
          y: yValues,
          type: "box",
          name: speciesLabelItalic,
          legendgroup: species,
          marker: { color: color },
          line: { color: color },
          fillcolor: color,
          opacity: 0.7,
          boxpoints: "outliers",
          jitter: 0.3,
          pointpos: 0,
          hovertemplate: '%{text}<extra></extra>',
          text: hoverTexts,
        } as unknown as Plotly.Data);
      } else {
        // Violin plot
        traces.push({
          x: xValues,
          y: yValues,
          type: "violin",
          name: speciesLabelItalic,
          legendgroup: species,
          line: { color: color },
          fillcolor: color,
          opacity: 0.7,
          box: { visible: true },
          meanline: { visible: true },
          points: "outliers",
          jitter: 0.3,
          scalemode: "width",
          hovertemplate: '%{text}<extra></extra>',
          text: hoverTexts,
        } as unknown as Plotly.Data);
      }

      // Unfiltered transcripts as separate overlay traces (box/violin)
      if (showAll && unmatchedTranscripts.length > 0) {
        const uxValues: string[] = [];
        const uyValues: number[] = [];
        const uHoverTexts: string[] = [];

        filteredTissues.forEach((tissue) => {
          unmatchedTranscripts.forEach((transcript) => {
            const vals = transcript.values[tissue];
            if (vals && vals.length > 0) {
              vals.forEach((sv) => {
                uxValues.push(tissue);
                uyValues.push(sv.value);
                uHoverTexts.push(
                  `<b>${transcript.geneId}</b> (unfiltered)<br>` +
                  `Species: ${speciesLabelItalic}<br>` +
                  `${groupingColumnLabel.value}: ${tissue}<br>` +
                  `${sv.sampleName}: ${sv.value.toFixed(3)}`
                );
              });
            }
          });
        });

        if (plotType.value === 'box') {
          traces.push({
            x: uxValues,
            y: uyValues,
            type: "box",
            name: `${speciesLabelItalic} (unfiltered)`,
            legendgroup: `${species}_unfiltered`,
            marker: { color: color },
            line: { color: color },
            fillcolor: color,
            opacity: 0.3,
            boxpoints: "outliers",
            jitter: 0.3,
            pointpos: 0,
            hovertemplate: '%{text}<extra></extra>',
            text: uHoverTexts,
          } as unknown as Plotly.Data);
        } else {
          traces.push({
            x: uxValues,
            y: uyValues,
            type: "violin",
            name: `${speciesLabelItalic} (unfiltered)`,
            legendgroup: `${species}_unfiltered`,
            line: { color: color },
            fillcolor: color,
            opacity: 0.3,
            box: { visible: true },
            meanline: { visible: true },
            points: "outliers",
            jitter: 0.3,
            scalemode: "width",
            hovertemplate: '%{text}<extra></extra>',
            text: uHoverTexts,
          } as unknown as Plotly.Data);
        }
      }
    }
  });

  // Y-axis title based on expression display
  const yAxisTitles: Record<string, string> = {
    tpm: "TPM Value",
    tmm: "TMM Value",
    getmm: "GeTMM Value",
    log2: "Log₂(TPM + 1)",
    zscore: "Z-Score (on GeTMM)",
    "zscore-tpm": "Z-Score (on TPM)",
    raw: "Raw Counts",
  };

  const containerWidth = plotContainer.value.clientWidth || cardWrapper.value?.clientWidth || 800;
  const isMobilePlot = containerWidth < 520;
  const responsiveHeight = isMobilePlot
    ? Math.max(520, Math.min(680, plotHeight.value + 80))
    : plotHeight.value;
  const topMargin = isMobilePlot ? 180 : 90;
  const bottomMargin = isMobilePlot ? 150 : 120;

  const layout: Partial<Plotly.Layout> = {
    autosize: true,
    height: responsiveHeight,
    margin: {
      l: isMobilePlot ? 58 : 70,
      r: isMobilePlot ? 12 : 30,
      t: topMargin,
      b: bottomMargin,
    },
    xaxis: {
      title: { text: groupingColumnLabel.value, standoff: 15 },
      type: "category",
      tickangle: -45,
      tickfont: { size: isMobilePlot ? 10 : 11 },
      categoryorder: "array",
      categoryarray: filteredTissues,
      automargin: true,
    } as any,
    yaxis: {
      title: {
        text: yAxisTitles[expressionDisplayOption.value] || "Expression Value",
        standoff: isMobilePlot ? 6 : 12,
      },
      automargin: true,
      zeroline: true,
      zerolinecolor: "#e0e0e0",
      gridcolor: "#f0f0f0",
    } as any,
    legend: {
      orientation: "h",
      yanchor: "bottom",
      y: 1.02,
      xanchor: "left",
      x: 0,
      bgcolor: "rgba(255,255,255,0.9)",
      bordercolor: "#e0e0e0",
      borderwidth: 1,
      tracegroupgap: isMobilePlot ? 8 : 20,
      font: { size: isMobilePlot ? 10 : 12 },
    },
    hovermode: "closest",
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#fafafa",
    // Box/Violin grouping mode
    boxmode: plotType.value === 'box' ? 'group' : undefined,
    violinmode: plotType.value === 'violin' ? 'group' : undefined,
  } as any;

  const config: Partial<Plotly.Config> = {
    responsive: true,
    displayModeBar: "hover",
    displaylogo: false,
    modeBarButtonsToRemove: ["lasso2d", "select2d"],
    toImageButtonOptions: {
      format: "svg",
      filename: `orthogroup_expression_${selectedOrthogroupLabel.value}`,
    },
  };

  await Plotly.react(plotContainer.value, traces, layout, config);
}

// ============================================================================
// Filter Controls
// ============================================================================
// Species filtering removed - Plotly legend handles visibility

// Close dropdowns on outside click
function handleClickOutside(event: MouseEvent) {
  if (
    plotTypeDropdownRef.value &&
    !plotTypeDropdownRef.value.contains(event.target as Node)
  ) {
    showPlotTypeDropdown.value = false;
  }
}

// ============================================================================
// Watchers
// ============================================================================
watch([filters, () => filtersStore.datasetIdFilters, filterChainVersion], () => {
  if (initialUrlParsing.value) return;
  updateUrlFromState();
  fetchAllSelected();
}, { deep: true });

// Watch sampleFilters to refetch data when sample filters change
watch(sampleFilters, async () => {
  if (initialUrlParsing.value) return;
  await fetchAllSelected();
  await nextTick();
  renderPlot();
}, { deep: true });

watch(selectedOrthogroup, async () => {
  if (initialUrlParsing.value) return;
  updateUrlFromState();
  
  // BUGFIX: When "All Transcripts" is enabled, refetch unfiltered data for the newly selected orthogroup
  // This ensures the feature works even when there's no orthogroup filter in the sidebar
  if (visualizationStore.compare.showAllTranscripts && selectedOrthogroup.value) {
    console.log('[Orthogroup Changed] Refetching unfiltered data for:', selectedOrthogroup.value);
    const unfilteredResults: Record<string, any> = {};
    for (const tableName of selectedTables.value) {
      const result = await fetchUnfilteredData(tableName, [selectedOrthogroup.value]);
      unfilteredResults[tableName] = result;
    }
    unfilteredTableData.value = unfilteredResults;
    await nextTick();
    renderPlot();
  }
});

// Watch for plot rendering changes (orthogroup, plotHeight, plotType, grouping column)
watch(
  [selectedOrthogroupLabel, plotHeight, plotType, selectedGroupingColumn],
  async () => {
    if (initialUrlParsing.value) return;
    updateUrlFromState();
    await nextTick();
    renderPlot();
  },
  { deep: true }
);

// Watch for expression changes - need to refetch data with new expression params
watch(
  () => visualizationStore.compare.expression,
  async (newVal, oldVal) => {
    if (initialUrlParsing.value) return;
    if (newVal !== oldVal) {
      updateUrlFromState();
      await fetchAllSelected();
      await nextTick();
      renderPlot();
    }
  }
);

// Watch for showAllTranscripts toggle — re-fetch unfiltered data and re-render
watch(
  () => visualizationStore.compare.showAllTranscripts,
  async () => {
    console.log('[AllTranscripts Toggle] Changed to:', visualizationStore.compare.showAllTranscripts);
    console.log('[AllTranscripts Toggle] initialUrlParsing:', initialUrlParsing.value);
    console.log('[AllTranscripts Toggle] commonOGs length:', commonOGs_array.value.length);
    console.log('[AllTranscripts Toggle] selectedOrthogroup:', selectedOrthogroup.value);
    if (initialUrlParsing.value) {
      console.log('[AllTranscripts Toggle] Blocked by initialUrlParsing');
      return;
    }
    await fetchAllSelected();
    await nextTick();
    await renderPlot();
    console.log('[AllTranscripts Toggle] Render complete. Transcript count:', processedData.value?.transcripts.length || 0);
  }
);

watch(
  [
    () => visualizationStore.clustering.clusterCols,
    () => visualizationStore.clustering.method,
    () => visualizationStore.clustering.distance,
    () => visualizationStore.colOrder.name,
    () => visualizationStore.colOrder.order,
    () => visualizationStore.customColOrder.enabled,
    () => visualizationStore.customColOrder.mode,
    () => visualizationStore.customColOrder.metadataColumn,
    () => visualizationStore.customColOrder.metadataValues.join("\u0000"),
    () => visualizationStore.customColOrder.sampleNames.join("\u0000"),
  ],
  async () => {
    if (initialUrlParsing.value) return;
    await nextTick();
    await renderPlot();
  },
);

// Watch for window resize
let resizeObserver: ResizeObserver | null = null;
let resizeTimeout: ReturnType<typeof setTimeout> | null = null;

// Debounced resize handler (200ms debounce)
function handleResize() {
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
  }
  resizeTimeout = setTimeout(() => {
    if (plotContainer.value) {
      // Full re-render ensures proper scaling of all elements
      renderPlot();
    }
  }, 200);
}

// ============================================================================
// Lifecycle
// ============================================================================
onMounted(async () => {
  loadingMount.value = true;

  // Load ONLY selected datasets from catalog (via existingTables prop)
  // This determines whether we show union (single dataset) or intersection (multiple datasets) of OGs
  const catalogSelectedTables = props.existingTables && props.existingTables.length > 0 
    ? [...props.existingTables] 
    : [props.tableName];
  selectedTables.value = catalogSelectedTables;

  // Check if this is a hash-based load (initialSpecies prop is set)
  const isHashBasedLoad = props.initialSpecies !== null && props.initialSpecies !== undefined && props.initialSpecies.length > 0;

  if (isHashBasedLoad) {
    // Hash-based load: use all species from prop for initial selection
    const speciesFromProps = props.initialSpecies!;
    const speciesFromStore = visualizationStore.compare.selectedSpecies;
    
    // Use whichever has more species (in case of timing issues)
    const initialSelectedSpecies = speciesFromProps.length >= speciesFromStore.length 
      ? [...speciesFromProps] 
      : [...speciesFromStore];
    
    console.log('[Compare] Hash-based load - speciesFromProps:', speciesFromProps);
    console.log('[Compare] Hash-based load - speciesFromStore:', speciesFromStore);
    console.log('[Compare] Hash-based load - initial selection:', initialSelectedSpecies);
    
    // Ensure store matches
    visualizationStore.setCompareState({ 
      selectedSpecies: initialSelectedSpecies,
      // Also set orthogroup if provided
      ...(props.initialOrthogroup ? { selectedOrthogroup: props.initialOrthogroup } : {})
    });
  } else {
    // Normal navigation (not hash-based)
    // Check if the store already has multi-species selection pre-set from catalog
    const storeSpecies = visualizationStore.compare.selectedSpecies;

    if (storeSpecies.length > 1) {
      // Coming from catalog with pre-selected species — keep them
      console.log('[Compare] Catalog navigation - preserving store species:', storeSpecies);
    } else {
      // Single-species or fresh navigation — set defaults
      visualizationStore.setCompareState({ 
        selectedSpecies: [props.tableName],
        selectedOrthogroup: ''  // Will be set after data loads
      });
    }
    
    // Parse URL state (legacy support for old direct URLs without route tables).
    const rawTables = route.query.tables;
    if (rawTables && props.existingTables.length === 0) {
      try {
        const parsed = JSON.parse(String(rawTables));
        if (Array.isArray(parsed)) {
          selectedTables.value = parsed;
          visualizationStore.setCompareState({ selectedSpecies: parsed });
        }
      } catch {
        // ignore parse errors
      }
    }

    const rawOg = route.query.orthogroup;
    if (rawOg) {
      selectedOrthogroup.value = String(rawOg);
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

    // Parse compare-specific settings from URL
    const rawExpression = route.query.expression;
    if (rawExpression && typeof rawExpression === 'string') {
      expressionDisplayOption.value = rawExpression;
    }

    const rawPlotType = route.query.plotType;
    if (rawPlotType && ['line', 'box', 'violin'].includes(String(rawPlotType))) {
      plotType.value = rawPlotType as 'line' | 'box' | 'violin';
    }

    const rawPlotHeight = route.query.plotHeight;
    if (rawPlotHeight) {
      const height = parseInt(String(rawPlotHeight), 10);
      if (!isNaN(height) && height >= 300 && height <= 800) {
        plotHeight.value = height;
      }
    }

    // Species selection from URL removed - Plotly legend controls visibility
  } // End of else block for non-hash-based load

  // Mark URL parsing as complete to allow watchers to run
  initialUrlParsing.value = false;

  // Setup click outside handler
  document.addEventListener("click", handleClickOutside);

  // Setup resize observer for card wrapper to handle sidebar toggle
  // Observe the wrapper so when sidebar changes, we detect the width change
  const elementToObserve = cardWrapper.value || plotContainer.value;
  if (elementToObserve) {
    resizeObserver = new ResizeObserver(() => {
      handleResize();
    });
    resizeObserver.observe(elementToObserve);
  }

  try {
    await fetchAllSelected();
  } finally {
    loadingMount.value = false;
  }

  // Render plot after initial data load
  await nextTick();
  renderPlot();
});

watch(
  () => props.existingTables,
  async (nextTables) => {
    if (initialUrlParsing.value) return;
    const nextSelection = nextTables && nextTables.length > 0
      ? [...nextTables]
      : [props.tableName];
    if (selectedTables.value.join(",") === nextSelection.join(",")) return;

    selectedTables.value = nextSelection;
    visualizationStore.setCompareState({ selectedSpecies: nextSelection });
    await fetchAllSelected();
    await nextTick();
    renderPlot();
  },
  { deep: true },
);

onUnmounted(() => {
  activeAbortController?.abort();
  document.removeEventListener("click", handleClickOutside);
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
  }
  if (resizeObserver) {
    resizeObserver.disconnect();
  }
  if (plotContainer.value) {
    Plotly.purge(plotContainer.value);
  }
});
</script>

<style scoped>
/* Custom scrollbar for dropdowns */
.max-h-48::-webkit-scrollbar,
.max-h-64::-webkit-scrollbar {
  width: 6px;
}

.max-h-48::-webkit-scrollbar-track,
.max-h-64::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.max-h-48::-webkit-scrollbar-thumb,
.max-h-64::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.max-h-48::-webkit-scrollbar-thumb:hover,
.max-h-64::-webkit-scrollbar-thumb:hover {
  background: #a1a1a1;
}
</style>
