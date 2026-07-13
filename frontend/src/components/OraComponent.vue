<template>
  <main class="min-w-0">
    <!-- Top control bar -->
    <div
      class="flex justify-between gap-2 px-2 items-start mb-2 flex-wrap"
      data-export-ignore="true"
    >
      <div class="text-gray-500 font-medium flex items-center gap-2 min-w-0 flex-wrap">
        <DropdownMenu
          :modelValue="localTableName"
          :options="tableNameOptions"
          @update:modelValue="(val) => onTableChange(val)"
        />
        <span class="pl-2 text-xs whitespace-nowrap"
          >({{ getEntityCountLabel() }}: {{ rowCount }})</span
        >
      </div>
      <div class="flex gap-2 flex-wrap justify-end">
        <button
          aria-label="Add another dot plot"
          @click="addDotplot"
          :disabled="
            props.existingTables.length === Object.keys(props.allTables).length
          "
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white disabled:opacity-50"
          v-tooltip="'Add another dot plot'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <path
              d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4"
            />
          </svg>
        </button>

        <button
          aria-label="Remove dot plot"
          @click="removeDotplot"
          :disabled="props.existingTables.length === 1"
          class="p-2 rounded-md text-accent1-500 border border-accent1-500 hover:bg-accent1-500 hover:text-white disabled:opacity-50"
          v-tooltip="'Remove dot plot'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <path
              d="M4 8a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7A.5.5 0 0 1 4 8"
            />
          </svg>
        </button>

        <button
          v-if="showSharedActions"
          aria-label="Share the visualization"
          @click="showShareOverlay = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Share the visualization'"
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
          v-if="showSharedActions"
          aria-label="Export data"
          @click="showExportModal = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Export data'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1m-4-4-4 4m0 0-4-4m4 4V4" />
          </svg>
        </button>

        <button
          v-if="showSharedActions"
          aria-label="Open settings"
          @click="openSettingsOverlay"
          class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900"
          v-tooltip="'Open settings'"
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
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
            />
          </svg>
        </button>
      </div>
    </div>

    <template v-if="loading || !renderReady || (rowCount <= 5000 && rowCount > 0)">
      <!-- ORA Info Banner (collapsible, default collapsed) -->
      <div
        v-if="oraMetadata && renderReady && rowCount > 0 && rowCount <= 5000"
        class="mb-2 p-3 bg-blue-50 border border-blue-200 rounded-md text-sm"
      >
        <div
          class="flex items-center justify-between cursor-pointer select-none"
          @click="toggleOraInfo"
        >
          <div class="font-semibold text-blue-900">
            Over-Representation Analysis (ORA)
          </div>
          <svg
            class="w-5 h-5 text-blue-700 transition-transform duration-300"
            :class="{ 'rotate-180': oraInfoOpen }"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </div>
        <transition name="collapse">
          <div v-show="oraInfoOpen" class="text-blue-800 space-y-1 mt-1">
            <div>
              <strong>{{ getEntitySetLabel() }}:</strong>
              {{ oraMetadata.subset_size }} annotated {{ getEntityLabelPluralLower() }}
              <span v-if="oraMetadata.raw_subset_size !== undefined">
                of {{ oraMetadata.raw_subset_size }} filtered
              </span>
              vs {{ oraMetadata.background_size }} annotated {{ getEntityLabelPluralLower() }}
              <span v-if="oraMetadata.raw_background_size !== undefined">
                of {{ oraMetadata.raw_background_size }} in the {{ localTableName }} species background
              </span>
            </div>
            <div v-if="oraMetadata.unannotated_subset_count > 0 || oraMetadata.unannotated_background_count > 0" class="text-xs text-blue-700">
              Unannotated transcripts are excluded from the ORA universe for the selected metadata column.
            </div>
            <div>
              <strong>Enrichment Tests:</strong> {{ oraMetadata.total_tests }} total,
              <span class="font-semibold">{{ currentSignificantCount }} significant</span>
              (FDR q-value &lt; {{ visualizationStore.significance }})
            </div>
            <div>
              <strong>Results Shown:</strong>
              {{ pValueEntries.length }} of {{ currentCriteriaCount }} passing terms after significance,
              minimum {{ visualizationStore.oraMinCount }} {{ getEntityLabelPluralLower() }} per term,
              GO depth filtering, and Top {{ visualizationStore.oraTopN }} selection.
            </div>
            <div v-if="goDepthFilterStatus" class="text-blue-700 bg-blue-100 rounded px-2 py-1 mt-1">
              <strong>GO Depth Filtering:</strong>
              Displaying only terms with GO depth at least {{ goDepthFilterStatus.depth }}.
              {{ goDepthFilterStatus.hiddenCount }} terms at shallower depths were filtered before Top N was selected.
            </div>
            <div v-if="minCountFilterStatus" class="text-blue-700 bg-blue-100 rounded px-2 py-1 mt-1">
              <strong>Minimum {{ getEntityCountLabel() }}:</strong>
              Displaying only terms with at least {{ minCountFilterStatus.threshold }} {{ getEntityLabelPluralLower() }}.
              {{ minCountFilterStatus.hiddenCount }} significant terms below this threshold were filtered before GO depth filtering and Top N was selected.
            </div>
            <div class="text-xs text-blue-600 mt-2">
              <strong>Combined Score</strong> = -log10(q-value) x gene_ratio
              | Accounts for both statistical significance and effect size
            </div>
          </div>
        </transition>
      </div>

      <!-- Main dot plot container -->
      <div
        ref="plotShell"
        data-testid="ora-plot-shell"
        class="relative flex flex-col overflow-hidden border border-gray-300 rounded-md bg-white"
        :style="plotShellStyle"
      >
        <LoadingOverlay
          v-if="(loading || !renderReady) && !props.deferLoadingOverlay"
          primaryStatus="Analyzing transcriptomic data..."
          :currentPhaseHint="loadingPhaseHint"
          cancellable
          @cancel="cancelActiveLoad"
        />

        <div
          class="h-full flex flex-col"
          :class="{ 'invisible pointer-events-none': loading || !renderReady || rowCount <= 0 || rowCount > 5000 }"
        >
          <div
            ref="visualizationRoot"
            class="flex-1 min-h-0 bg-white flex flex-row overflow-hidden"
          >
            <div class="flex-grow relative w-full overflow-hidden">
              <div ref="dotplotContainer" class="w-full h-full"></div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <div v-else-if="rowCount > 5000">
      <div class="p-6 text-center text-gray-600 border border-gray-300 rounded-md">
        <p class="text-lg font-semibold">Too many {{ getEntityLabelPluralLower() }} for ORA visualization</p>
        <p class="mt-2">
          Your filter returned {{ rowCount }} {{ getEntityLabelPluralLower() }}. 
          Please refine your filters to reduce the {{ getEntityLabelPluralLower() }} set to ≤5000 {{ getEntityLabelPluralLower() }}.
        </p>
      </div>
    </div>

    <div v-else>
      <NoDataComponent :rowCount="rowCount" />
    </div>

    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(visualizationRoot)"
      @close="showShareOverlay = false"
    />

    <ExportModal
      v-if="showExportModal"
      :data="oraExportPayload.data"
      :columns="oraExportPayload.columns"
      :columnDisplayNames="oraExportColumnDisplayNames"
      :metaColumns="oraExportPayload.metaColumns"
      :sampleColumns="oraExportPayload.sampleColumns"
      :filename="oraExportPayload.filename"
      :hasFilters="oraExportPayload.hasFilters"
      :totalCount="oraExportPayload.data.length"
      dataColumnLabel="metrics"
      @close="showExportModal = false"
    />
    
    <OraTooltipModal
      :show="showOraTooltipModal"
      :data="selectedTerm"
      :isGoTerm="isGoTermEnrichment"
      :visibleFields="visualizationStore.oraTooltipFields"
      @close="showOraTooltipModal = false"
      @filterByTerm="handleFilterByTerm"
    />
  </main>
</template>
<script setup lang="ts">
import axios from "axios";
import * as d3 from "d3";
import { storeToRefs } from "pinia";
import {
  computed,
  inject,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  type Ref,
  watch,
} from "vue";

import { API_BASE_URL } from "@/shared/Config";
import { COLORSCALES } from "@/shared/Colorscales";
import DropdownMenu from "./DropdownMenu.vue";
import { useFiltersStore } from "@/stores/filters";
import LoadingOverlay from "./LoadingOverlay.vue";
import type { MetaFormat } from "@/shared/MetaFormat";
import NoDataComponent from "./NoDataComponent.vue";
import type { RowType } from "@/shared/RowType";
import ShareOverlay from "./ShareOverlay.vue";
import ExportModal from "./ExportModal.vue";
import OraTooltipModal from "./OraTooltipModal.vue";
import { beautifyLabel, compareValues } from "@/shared/utils";
import { getDisplayName } from "@/shared/metadataFields";
import { useVisualizationStore } from "@/stores/visualization";
import { useColumnsStore } from "@/stores/columns";
import { useAssistantStore } from "@/stores/assistant";
import { getEntityCountLabel, getEntitySetLabel, getEntityLabelPluralLower } from "@/shared/dataTypeLabels";
import { createVisibleColorMapping, type SharedColorRegistry } from "@/shared/colorMapping";

// TODO: Numeric column values have not been tested as ORA input

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const columnsStore = useColumnsStore();
const assistantStore = useAssistantStore();
const { filters } = storeToRefs(filtersStore);
const filterChainVersion = computed(() => filtersStore.filterChainVersion);

// Per-dataset merged filters (includes per-dataset ID filter)
const mergedFilters = computed(() => filtersStore.getMergedFilters(props.tableName));

const sidebarOpen = inject("sidebarOpen") as Ref<boolean> | undefined; //Provided by App.vue
const sharedColorRegistry = inject<SharedColorRegistry>('sharedColorRegistry', undefined) as SharedColorRegistry | undefined;

const props = withDefaults(defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
  hashLoading?: boolean;
  showSharedActions?: boolean;
  deferLoadingOverlay?: boolean;
}>(), {
  hashLoading: false,
  showSharedActions: true,
  deferLoadingOverlay: false,
});

const localTableName = ref(props.tableName);
const tableNameOptions = computed(() => {
  return Object.fromEntries(
    Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) || key === props.tableName,
    ),
  );
});

const loading = ref(true);
const loadingProgress = ref<number | null>(null);
const loadingPhaseHint = ref("Preparing ORA request...");
const renderReady = ref(false);
const showShareOverlay = ref(false);
const showExportModal = ref(false);
const showOraTooltipModal = ref(false);
const selectedTerm = ref<PValueEntry | null>(null);
const oraInfoOpen = ref(false);

const error = ref("");
const rowCount = ref(0);
const columnMeta = ref<MetaFormat>();
const rawPValueEntries = ref<PValueEntry[]>([]);
const oraMetadata = ref<OraMetadata | null>(null);

const dotplotContainer = ref<HTMLDivElement | null>(null);
const colorLegendContainer = ref<HTMLDivElement | null>(null);
const sizeLegendContainer = ref<HTMLDivElement | null>(null);
const plotShell = ref<HTMLDivElement | null>(null);

const visualizationRoot = ref<HTMLDivElement | null>(null);
let oraRequestSeq = 0;
let activeAbortController: AbortController | null = null;
let softProgressTimer: ReturnType<typeof setInterval> | null = null;
let phaseHintTimer: ReturnType<typeof setInterval> | null = null;
const availablePlotHeight = ref(600);
const maxBubbleRadius = 15;
const minimumBubbleGap = 4;
const plotVerticalChrome = 126;
const oraLegendAreaWidth = 150;
const oraLegendSpacingVertical = 20;
const oraColorLegendHeight = 120;
const oraSizeLegendTopMargin = 50;
const oraSizeLegendCircleSpacing = 50;
const oraLegendBottomPadding = 16;

function getLargestBubbleDiameter(entries: PValueEntry[]): number {
  if (!entries.length) return maxBubbleRadius * 2;
  const counts = entries.map((entry) => entry.subset_count);
  const minSubsetCount = d3.min(counts) ?? 0;
  const maxSubsetCount = d3.max(counts) ?? 1;
  const sizeScale = d3
    .scaleSqrt()
    .domain([minSubsetCount, maxSubsetCount])
    .range([6, maxBubbleRadius]);
  return Math.ceil((d3.max(entries, (entry) => sizeScale(entry.subset_count)) ?? maxBubbleRadius) * 2);
}

function getSizeLegendValues(entries: PValueEntry[]): number[] {
  const counts = entries.map((entry) => entry.subset_count);
  const minSubsetCount = d3.min(counts) ?? 0;
  const maxSubsetCount = d3.max(counts) ?? 0;
  return [
    minSubsetCount,
    Math.round((minSubsetCount + maxSubsetCount) / 2),
    maxSubsetCount,
  ].filter((value, index, values) => value > 0 && values.indexOf(value) === index);
}

function getLegendRequiredHeight(entries: PValueEntry[]): number {
  if (!visualizationStore.legend) return 240;
  const sizeLegendValues = getSizeLegendValues(entries);
  const sizeLegendContentHeight =
    oraSizeLegendTopMargin
    + Math.max(0, sizeLegendValues.length - 1) * oraSizeLegendCircleSpacing
    + maxBubbleRadius;

  return Math.ceil(
    50
      + oraColorLegendHeight
      + oraLegendSpacingVertical
      + sizeLegendContentHeight
      + oraLegendBottomPadding,
  );
}

function updateAvailablePlotHeight() {
  if (typeof window === "undefined") return;
  const shellTop = plotShell.value?.getBoundingClientRect().top ?? 160;
  const usableHeight = window.innerHeight - shellTop - 12;
  availablePlotHeight.value = Math.max(360, Math.floor(usableHeight));
}

function waitForPaint(): Promise<void> {
  if (typeof requestAnimationFrame === "undefined") return Promise.resolve();
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function setLoadingProgress(value: number | null) {
  if (value === null) {
    loadingProgress.value = null;
    return;
  }
  loadingProgress.value = Math.min(100, Math.max(0, value));
}

function setLoadingPhaseHint(phaseHint: string) {
  loadingPhaseHint.value = phaseHint;
}

function stopSoftProgress() {
  if (softProgressTimer !== null) {
    clearInterval(softProgressTimer);
    softProgressTimer = null;
  }
}

function stopPhaseHintCycle() {
  if (phaseHintTimer !== null) {
    clearInterval(phaseHintTimer);
    phaseHintTimer = null;
  }
}

function stopLoadingTimers() {
  stopSoftProgress();
  stopPhaseHintCycle();
}

function startSoftProgress(ceiling = 82) {
  stopSoftProgress();
  softProgressTimer = setInterval(() => {
    const current = loadingProgress.value ?? 0;
    if (current >= ceiling) return;
    const increment = Math.max(0.35, (ceiling - current) * 0.08);
    setLoadingProgress(Math.min(ceiling, current + increment));
  }, 450);
}

function startPhaseHintCycle(phaseHints: string[], intervalMs = 1800) {
  stopPhaseHintCycle();
  if (!phaseHints.length) return;
  let phaseIndex = 0;
  setLoadingPhaseHint(phaseHints[phaseIndex]);
  phaseHintTimer = setInterval(() => {
    phaseIndex = (phaseIndex + 1) % phaseHints.length;
    setLoadingPhaseHint(phaseHints[phaseIndex]);
  }, intervalMs);
}

async function showLoadingFrame(initialProgress = 5) {
  loading.value = true;
  renderReady.value = false;
  error.value = "";
  setLoadingPhaseHint("Preparing ORA request...");
  setLoadingProgress(initialProgress);
  await nextTick();
  await waitForPaint();
}

function isCanceledRequest(error: unknown) {
  return axios.isCancel(error) || (axios.isAxiosError(error) && error.code === "ERR_CANCELED");
}

function cancelActiveLoad(emitCancel = true) {
  oraRequestSeq += 1;
  activeAbortController?.abort();
  activeAbortController = null;
  stopLoadingTimers();
  resetDotplot();
  loading.value = false;
  renderReady.value = true;
  setLoadingProgress(null);
  setLoadingPhaseHint("Load canceled");
  if (emitCancel) emit("load-cancel");
}

const finalPlotHeight = computed(() => {
  const visibleRows = Math.max(pValueEntries.value.length, 1);
  const rowHeight = getLargestBubbleDiameter(pValueEntries.value) + minimumBubbleGap;
  const minimumHeight = getLegendRequiredHeight(pValueEntries.value);
  const bubbleSafeHeight = visibleRows * rowHeight + plotVerticalChrome;
  return Math.max(minimumHeight, bubbleSafeHeight);
});

const hasPreparedPlotData = computed(() => pValueEntries.value.length > 0 || oraMetadata.value !== null);
const activePlotHeight = computed(() => loading.value && !hasPreparedPlotData.value ? availablePlotHeight.value : finalPlotHeight.value);
const plotShellStyle = computed(() => ({
  height: `${activePlotHeight.value}px`,
  minHeight: `${activePlotHeight.value}px`,
}));

function log2FoldEnrichment(value: number): number {
  return Math.log2(Math.max(value, Number.EPSILON));
}

async function syncPlotHeightWithViewport() {
  updateAvailablePlotHeight();
  await nextTick();
}

// PValueEntry interface updated to match backend response
interface PValueEntry {
  attr: string;  // Frontend uses 'attr'
  attribute: string;  // Backend provides 'attribute'
  subset_count: number;
  background_count: number;
  gene_ratio: number;
  p_value: number;
  q_value: number;
  combined_score: number;
  odds_ratio?: number;
  expected_count: number;
  fold_enrichment: number;
  // GO term info (only for GO term enrichment)
  go_name?: string;
  go_namespace?: string;
  go_depth?: number;
}

interface OraResult {
  attribute: string;
  subset_count: number;
  background_count: number;
  gene_ratio: number;
  p_value: number;
  q_value: number;
  combined_score: number;
  odds_ratio?: number;
  expected_count: number;
  fold_enrichment: number;
  go_name?: string;
  go_namespace?: string;
  go_depth?: number;
}

interface OraMetadata {
  count?: number;
  subset_size?: number;
  background_size?: number;
  unannotated_subset_count?: number;
  unannotated_background_count?: number;
  filtered_count?: number;
  available_go_depths?: number[];
  max_go_depth?: number;
  message?: string;
  [key: string]: unknown;
}

interface OraResponse {
  results?: OraResult[];
  metadata?: OraMetadata;
  error?: string;
  go_terms?: Record<string, { name?: string; namespace?: string; depth?: number }>;
}

const oraExportMetaColumns = computed(() => {
  const columns = ['attribute'];
  if (isGoTermEnrichment.value) {
    columns.push('go_name', 'go_namespace', 'go_depth');
  }
  return columns;
});

const oraExportMetricColumns = [
  'subset_count',
  'background_count',
  'expected_count',
  'fold_enrichment',
  'gene_ratio',
  'p_value',
  'q_value',
  'combined_score',
  'odds_ratio',
];

const oraExportColumnDisplayNames = computed(() => {
  const selectedColumnDisplayName = getDisplayName(visualizationStore.oraColumnName);
  const mapping: Record<string, string> = {
    attribute: selectedColumnDisplayName,
  };

  for (const column of oraExportMetaColumns.value) {
    if (column === 'attribute') continue;
    mapping[column] = getDisplayName(column, beautifyLabel(column));
  }

  for (const column of oraExportMetricColumns) {
    mapping[column] = beautifyLabel(column);
  }

  return mapping;
});

const oraExportPayload = computed(() => {
  const metaColumns = oraExportMetaColumns.value;
  const sampleColumns = oraExportMetricColumns;
  const columns = [...metaColumns, ...sampleColumns];
  const data = pValueEntries.value.map((entry) => {
    const row: RowType = {
      attribute: entry.attr,
      subset_count: entry.subset_count,
      background_count: entry.background_count,
      expected_count: entry.expected_count,
      fold_enrichment: entry.fold_enrichment,
      gene_ratio: entry.gene_ratio,
      p_value: entry.p_value,
      q_value: entry.q_value,
      combined_score: entry.combined_score,
      odds_ratio: entry.odds_ratio ?? null,
    };
    if (isGoTermEnrichment.value) {
      row.go_name = entry.go_name ?? null;
      row.go_namespace = entry.go_namespace ?? null;
      row.go_depth = entry.go_depth ?? null;
    }
    return row;
  });

  return {
    data,
    columns,
    metaColumns,
    sampleColumns,
    filename: `ora_${props.tableName}_${visualizationStore.oraColumnName}`,
    hasFilters: Object.keys(mergedFilters.value).length > 0,
    dataset: props.tableName,
  };
});

defineExpose({
  getExportPayload: () => oraExportPayload.value,
  cancelActiveLoad,
});

// GO term info cache (includes name, namespace, and depth)
const goTermInfoCache = ref<Record<string, { name: string; namespace: string; depth?: number }>>({});

// Check if we're enriching GO terms (check various possible column names)
const isGoTermEnrichment = computed(() => {
  const colName = visualizationStore.oraColumnName.toLowerCase();
  return colName.includes('go') || 
         colName === 'go_terms' ||
         colName === 'gene_ontology' ||
         colName.startsWith('go_');
});

const activeGoDepthFilter = computed(() => {
  const selectedDepth = visualizationStore.oraGoDepthFilter;
  if (!isGoTermEnrichment.value || selectedDepth === "") return null;

  const depth = Number(visualizationStore.oraGoDepthFilter);
  return Number.isInteger(depth) && depth > 0 ? depth : null;
});

const significanceFilteredEntries = computed(() => {
  const threshold = Number(visualizationStore.significance);
  const significance = Number.isFinite(threshold) ? threshold : 1;
  return rawPValueEntries.value.filter((entry) => entry.q_value < significance);
});

const criteriaFilteredEntries = computed(() => {
  const selectedDepth = activeGoDepthFilter.value;
  return significanceFilteredEntries.value.filter((entry) => {
    if (entry.subset_count < visualizationStore.oraMinCount) return false;
    if (selectedDepth === null) return true;
    return typeof entry.go_depth === 'number' && entry.go_depth >= selectedDepth;
  });
});

const pValueEntries = computed(() => {
  return criteriaFilteredEntries.value
    .slice()
    .sort((a, b) => b.combined_score - a.combined_score)
    .slice(0, visualizationStore.oraTopN);
});
const currentSignificantCount = computed(() => significanceFilteredEntries.value.length);
const currentCriteriaCount = computed(() => criteriaFilteredEntries.value.length);

const minCountHiddenCount = computed(() => {
  const threshold = visualizationStore.oraMinCount;
  if (threshold <= 1) return 0;
  return significanceFilteredEntries.value.filter((entry) => entry.subset_count < threshold).length;
});

const minCountFilterStatus = computed(() => {
  const threshold = visualizationStore.oraMinCount;
  if (threshold <= 1 || minCountHiddenCount.value <= 0) return null;
  return { threshold, hiddenCount: minCountHiddenCount.value };
});

const goDepthHiddenCount = computed(() => {
  if (activeGoDepthFilter.value !== null) {
    return significanceFilteredEntries.value.filter((entry) => {
      if (entry.subset_count < visualizationStore.oraMinCount) return false;
      return !(typeof entry.go_depth === 'number' && entry.go_depth >= activeGoDepthFilter.value!);
    }).length;
  }
  return rawPValueEntries.value.length - pValueEntries.value.length;
});
const goDepthFilterStatus = computed(() => {
  const depth = activeGoDepthFilter.value;
  if (depth === null || goDepthHiddenCount.value <= 0) return null;
  return { depth, hiddenCount: goDepthHiddenCount.value };
});

function syncAvailableGoDepths() {
  if (!isGoTermEnrichment.value) {
    visualizationStore.setOraAvailableGoDepths([]);
    return;
  }
  const metadataDepths = Array.isArray(oraMetadata.value?.available_go_depths)
    ? oraMetadata.value.available_go_depths
    : null;
  if (metadataDepths) {
    visualizationStore.setOraAvailableGoDepths([0, ...metadataDepths]);
    return;
  }
  visualizationStore.setOraAvailableGoDepths(
    [0, ...rawPValueEntries.value
      .map((entry) => entry.go_depth)
      .filter((depth): depth is number => typeof depth === 'number' && Number.isInteger(depth) && depth > 0)],
  );
}

function toggleOraInfo() {
  oraInfoOpen.value = !oraInfoOpen.value;
}

/**
 * Fetch GO term details in batch for GO term enrichment.
 * Only called when oraColumnName is a GO term column.
 * Now includes depth information.
 */
async function fetchGoTermDetails(goIds: string[], signal?: AbortSignal): Promise<void> {
  if (!goIds.length) return;
  
  // Filter out already cached IDs
  const uncachedIds = goIds.filter(id => !goTermInfoCache.value[id]);
  if (!uncachedIds.length) return;
  
  try {
    const { data } = await axios.post(`${API_BASE_URL}/api/go/terms/batch`, {
      go_ids: uncachedIds,
      include_depth: true
    }, { signal });
    
    if (data.available && data.terms) {
      for (const [goId, term] of Object.entries(data.terms)) {
        const termData = term as { name?: string; namespace?: string; depth?: number };
        goTermInfoCache.value[goId] = {
          name: termData.name || '',
          namespace: termData.namespace || '',
          depth: typeof termData.depth === 'number' && termData.depth >= 0 ? termData.depth : undefined
        };
      }
    }
  } catch (error) {
    if (isCanceledRequest(error)) return;
    console.warn('Failed to fetch GO term details:', error);
  }
}

/**
 * Fetch ORA data from backend endpoint.
 * 
 * The backend performs:
 * 1. Gene counting (unique genes, not occurrences) for array columns
 * 2. Species-specific background (all genes in same species)
 * 3. Fisher's Exact Test for each attribute
 * 4. Benjamini-Hochberg FDR correction
 * 5. Combined score calculation: -log10(q_value) * gene_ratio
 * 6. Filtering by significance and min_count
 * 7. Top-N selection by combined_score
 */
async function fetchAndPrepareData() {
  const requestId = ++oraRequestSeq;
  activeAbortController?.abort();
  const controller = new AbortController();
  activeAbortController = controller;
  await showLoadingFrame();
  if (requestId !== oraRequestSeq) return;
  try {
    resetDotplot();
    setLoadingProgress(10);
    setLoadingPhaseHint("Building enrichment request...");
    // Prepare ORA request — max_subset_size replaces the separate /api/count call
    const oraRequest = {
      table_name: props.tableName,
      column_name: visualizationStore.oraColumnName,
      filters: mergedFilters.value,
      filter_chain: filtersStore.buildFilterChainPayload(mergedFilters.value, props.tableName),
      significance: 1.000001,
      top_n: 0,
      min_count: 1,
      go_depth_min: 0,
      max_subset_size: 5000,
    };
    
    // Call backend ORA endpoint (includes count check)
    startPhaseHintCycle([
      "Counting filtered transcripts...",
      "Building the background universe...",
      "Running enrichment tests...",
      "Adjusting FDR q-values...",
    ]);
    startSoftProgress(82);
    const { data: oraResponse } = await axios.post(
      `${API_BASE_URL}/api/ora`,
      oraRequest,
      { signal: controller.signal },
    );
    stopLoadingTimers();
    if (requestId !== oraRequestSeq || controller.signal.aborted) return;
    setLoadingProgress(85);
    setLoadingPhaseHint("Processing enrichment results...");
    
    // Parse response if it's a string (shouldn't happen with proper Content-Type)
    let parsedResponse = oraResponse as OraResponse;
    if (typeof oraResponse === 'string') {
      console.warn('ORA response is string, parsing JSON manually');
      parsedResponse = JSON.parse(oraResponse) as OraResponse;
    }
    setLoadingProgress(88);

    // Extract count from metadata (replaces separate /api/count call)
    rowCount.value = parsedResponse.metadata?.count ?? parsedResponse.metadata?.subset_size ?? 0;

    // Check for count-exceeded or empty subset
    if (parsedResponse.metadata?.message || !parsedResponse.results?.length) {
      rawPValueEntries.value = [];
      oraMetadata.value = parsedResponse.metadata;
      syncAvailableGoDepths();
      setLoadingProgress(92);
      setLoadingPhaseHint("Preparing empty result view...");
      await nextTick();
      await syncPlotHeightWithViewport();
      setLoadingProgress(96);
      setLoadingPhaseHint("Rendering ORA dot plot...");
      await drawDotPlot();
      publishAnalysisContext();
      setLoadingProgress(100);
      renderReady.value = true;
      return;
    }

    // Check for error response
    if (parsedResponse.error) {
      throw new Error(parsedResponse.error);
    }

      // Store results - map backend response to frontend interface
      // Fold enrichment and expected count are now calculated on backend
      rawPValueEntries.value = parsedResponse.results.map((r) => {
        return {
          attr: r.attribute,  // Map 'attribute' to 'attr' for compatibility
          attribute: r.attribute,  // Keep original for modal
          subset_count: r.subset_count,
          background_count: r.background_count,
          gene_ratio: r.gene_ratio,
          p_value: r.p_value,
          q_value: r.q_value,
          combined_score: r.combined_score,
          odds_ratio: r.odds_ratio,
          expected_count: r.expected_count,
          fold_enrichment: r.fold_enrichment,
          go_name: r.go_name,
          go_namespace: r.go_namespace,
          go_depth: typeof r.go_depth === 'number' && r.go_depth >= 0 ? r.go_depth : undefined,
        };
      });

        oraMetadata.value = parsedResponse.metadata;
        setLoadingProgress(90);
      // Fetch GO term details if this is GO term enrichment
      if (isGoTermEnrichment.value && rawPValueEntries.value.length > 0) {
        // Use inline GO terms from ORA response if available, otherwise fetch separately
        if (parsedResponse.go_terms) {
          setLoadingPhaseHint("Applying GO term metadata...");
          for (const [goId, term] of Object.entries(parsedResponse.go_terms)) {
            const termData = term as { name?: string; namespace?: string; depth?: number };
            goTermInfoCache.value[goId] = {
              name: termData.name || '',
              namespace: termData.namespace || '',
              depth: typeof termData.depth === 'number' && termData.depth >= 0 ? termData.depth : undefined
            };
          }
        } else {
          const goIds = rawPValueEntries.value.map(e => e.attr);
          startPhaseHintCycle([
            "Fetching GO term details...",
            "Resolving GO names and namespaces...",
            "Applying GO depth metadata...",
          ], 1600);
          startSoftProgress(94);
          await fetchGoTermDetails(goIds, controller.signal);
          stopLoadingTimers();
        }
        if (requestId !== oraRequestSeq || controller.signal.aborted) return;
        setLoadingProgress(94);
        
        // Enrich entries with GO term info including depth
        rawPValueEntries.value = rawPValueEntries.value.map(entry => {
          const goInfo = goTermInfoCache.value[entry.attr];
          return {
            ...entry,
            go_name: entry.go_name ?? goInfo?.name,
            go_namespace: entry.go_namespace ?? goInfo?.namespace,
            go_depth: entry.go_depth ?? goInfo?.depth
          };
        });
      }
      syncAvailableGoDepths();
      setLoadingProgress(96);

      await nextTick();
      await syncPlotHeightWithViewport();
      setLoadingProgress(98);
      setLoadingPhaseHint("Rendering ORA dot plot...");
      await drawDotPlot();
      publishAnalysisContext();
      setLoadingProgress(100);
      renderReady.value = true;
  } catch (e) {
    stopLoadingTimers();
    if (isCanceledRequest(e)) return;
    if (requestId !== oraRequestSeq) return;
    console.error("Error fetching ORA data:", e);
    error.value = "Failed to load ORA data.";
    renderReady.value = true;
  } finally {
    if (requestId === oraRequestSeq) {
      stopLoadingTimers();
      activeAbortController = null;
      loading.value = false;
      loadingProgress.value = null;
    }
  }
}

/**
 * Publish a compact digest of the current ORA result to the assistant store
 * so the AI can answer questions like "do you see a pattern?" about the
 * results the user is currently looking at. Stays small (top-N rows + meta)
 * to keep the prompt size bounded.
 */
function publishAnalysisContext() {
  try {
    const top = pValueEntries.value.slice(0, 25).map((e) => ({
      attribute: e.attr,
      name: e.go_name || undefined,
      namespace: e.go_namespace || undefined,
      depth: e.go_depth,
      subset_count: e.subset_count,
      background_count: e.background_count,
      expected_count: Number(e.expected_count?.toFixed?.(2) ?? e.expected_count),
      fold_enrichment: Number(e.fold_enrichment?.toFixed?.(2) ?? e.fold_enrichment),
      gene_ratio: Number(e.gene_ratio?.toFixed?.(4) ?? e.gene_ratio),
      p_value: e.p_value,
      q_value: e.q_value,
      combined_score: Number(e.combined_score?.toFixed?.(2) ?? e.combined_score),
    }));
    assistantStore.setAnalysisContext(`ora:${props.tableName}`, {
      kind: "ora",
      table: props.tableName,
      column: visualizationStore.oraColumnName,
      is_go_term: isGoTermEnrichment.value,
      significance: visualizationStore.significance,
      top_n_displayed: visualizationStore.oraTopN,
      min_count: visualizationStore.oraMinCount,
      metadata: {
        ...(oraMetadata.value || {}),
        significant_count: significanceFilteredEntries.value.length,
        filtered_count: criteriaFilteredEntries.value.length,
      },
      n_results: pValueEntries.value.length,
      top_terms: top,
    });
  } catch (e) {
    console.warn("Failed to publish ORA analysis context:", e);
  }
}

//Plot
function resetDotplot() {
  if (dotplotContainer.value) {
    d3.select(dotplotContainer.value).selectAll("*").remove();
  }
  if (colorLegendContainer.value) {
    d3.select(colorLegendContainer.value).selectAll("*").remove();
  }
  if (sizeLegendContainer.value) {
    d3.select(sizeLegendContainer.value).selectAll("*").remove();
  }
}

// Render row side colors for the dotplot using createVisibleColorMapping and data
async function renderDotplotRowSideColors({
  svg,
  margin,
  yLabels,
  attributeValues,
  column_name,
  colType,
  sideColorWidth = 20,
}: {
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  margin: { top: number; right: number; bottom: number; left: number };
  yLabels: string[];
  attributeValues: string[];
  column_name: string;
  colType: string;
  sideColorWidth?: number;
}) {
  // Register values with shared registry for cross-plot consistency, then get mapping
  if (sharedColorRegistry) {
    sharedColorRegistry.registerValues(column_name, colType, attributeValues);
  }
  const colorMap = (sharedColorRegistry && sharedColorRegistry.getMapping(column_name))
    ?? createVisibleColorMapping(column_name, colType, attributeValues);

  // Setup vertical band scale
  const scale = d3
    .scaleBand()
    .domain(yLabels)
    .range([0, +svg.attr("height") - margin.top - margin.bottom])
    .padding(0);

  // Append the group at the correct offset
  const containerGroup = svg
    .append("g")
    .attr(
      "transform",
      `translate(${margin.left - sideColorWidth},${margin.top})`,
    );

  // Draw color rectangles
  const rects = containerGroup
    .selectAll("rect")
    .data(attributeValues)
    .join("rect")
    .attr("x", 0)
    .attr("y", (d, i) => scale(yLabels[i]) ?? 0)
    .attr("width", sideColorWidth * 0.75)
    .attr("height", scale.bandwidth())
    .attr("fill", (d) => {
      const numericValue = Number(d);
      // Numeric columns with binning and getColor method
      if (
        (colType === "double precision" || colType === "bigint") &&
        Number.isFinite(numericValue) &&
        typeof colorMap.getColor === "function"
      ) {
        return colorMap.getColor(numericValue) ?? "#eeeeee";
      }
      // Boolean/categorical mapping
      const mappedColor = colorMap[d];
      if (typeof mappedColor === "string") return mappedColor;
      return "#eeeeee";
    });

  // Tooltip setup for the row-side rectangles.
  const svgParent = svg.node()?.parentNode as HTMLElement | null;
  if (!svgParent) return;
  const tooltip = d3
    .select(svgParent)
    .append("div")
    .attr("id", "sideColorTooltip")
    .style("position", "absolute")
    .style("z-index", "50")
    .style("visibility", "hidden")
    .style("background-color", "#f9fafb")
    .style("color", "#374151")
    .style("font-size", "0.75rem")
    .style("border-radius", "0.375rem")
    .style("padding", "0.25rem 0.5rem")
    .style("min-width", "6rem")
    .style("max-width", "20rem")
    .style("border", "1px solid #d1d5db")
    .style("box-shadow", "0 1px 2px rgba(0,0,0,0.05)")
    .style("pointer-events", "none");

  rects
    .on("mouseover", function (event, d) {
      d3.select(this).attr("stroke", "white").style("stroke-width", 2);
      const entry = pValueEntries.value.find((item) => item.attr === d);
      tooltip.html(entry ? buildOraTooltipContent(entry) : String(d ?? ""));
      tooltip.style("visibility", "visible");
    })
    .on("mousemove", function (event) {
      const containerRect = svgParent.getBoundingClientRect();
      const tooltipNode = tooltip.node() as HTMLDivElement | null;
      if (!tooltipNode) return;
      const tooltipRect = tooltipNode.getBoundingClientRect();

      const offsetX = 10;
      const offsetY = 10;
      let xPos = event.clientX - containerRect.left + offsetX;
      let yPos = event.clientY - containerRect.top + offsetY;

      // Adjust horizontal positioning if tooltip goes beyond container
      if (xPos + tooltipRect.width > containerRect.width) {
        xPos = event.clientX - containerRect.left - tooltipRect.width - offsetX;
      }
      // Adjust vertical positioning if tooltip goes beyond container
      if (yPos + tooltipRect.height > containerRect.height) {
        yPos = event.clientY - containerRect.top - tooltipRect.height - offsetY;
      }

      xPos = Math.max(0, xPos);
      yPos = Math.max(0, yPos);

      tooltip.style("left", xPos + "px").style("top", yPos + "px");
    })
    .on("mouseout", function () {
      d3.select(this).attr("stroke", "none");
      tooltip.style("visibility", "hidden");
    })
    .on("contextmenu", function (event, d) {
      const entry = pValueEntries.value.find((item) => item.attr === d);
      if (!entry) return;
      event.preventDefault();
      selectedTerm.value = entry;
      showOraTooltipModal.value = true;
      tooltip.style("visibility", "hidden");
    })
    .on("click", function (event, d) {
      const numericValue = Number(d);
      if (
        (colType === "double precision" || colType === "bigint") &&
        Number.isFinite(numericValue) &&
        colorMap.bins
      ) {
        // Find bin for clicked value to set filter range
        const bin = colorMap.bins.find(
          (b) => numericValue >= b.bucket_lower && numericValue <= b.bucket_upper,
        );
        if (bin) {
          filtersStore.setFilter(column_name, {
            value: [bin.bucket_lower, bin.bucket_upper] as unknown as string,
          });
        } else {
          filtersStore.setFilter(column_name, { value: d });
        }
      } else {
        // For categorical or boolean, set exact filter
        filtersStore.setFilter(column_name, { value: d });
      }
    });
}

function buildOraTooltipContent(d: PValueEntry): string {
  let tooltipContent = '';

  const hasGoInfo = isGoTermEnrichment.value && (d.go_name || goTermInfoCache.value[d.attr]?.name);
  const goName = d.go_name || goTermInfoCache.value[d.attr]?.name || '';
  const visibleFields = visualizationStore.oraTooltipFields;
  let hasContent = false;

  if (visibleFields.includes('go_name') && isGoTermEnrichment.value && hasGoInfo) {
    tooltipContent += `<strong>${goName}</strong><br/>`;
    hasContent = true;
  }

  if (visibleFields.includes('attribute_name')) {
    if (isGoTermEnrichment.value && hasGoInfo && visibleFields.includes('go_name')) {
      tooltipContent += `<strong>GO ID:</strong> ${d.attr}<br/>`;
    } else {
      tooltipContent += `<strong>${d.attr}</strong><br/>`;
    }
    hasContent = true;
  }

  if (hasContent && visibleFields.some(f => !['attribute_name', 'go_name'].includes(f))) {
    tooltipContent += `<hr style="margin:4px 0; border-color:#888"/>`;
  }

  if (visibleFields.includes('subset_count')) {
    tooltipContent += `<strong>Observed Count:</strong> ${d.subset_count}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('expected_count')) {
    tooltipContent += `<strong>Expected Count:</strong> ${d.expected_count.toFixed(2)}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('background_count')) {
    tooltipContent += `<strong>Background Count:</strong> ${d.background_count}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('fold_enrichment')) {
    tooltipContent += `<strong>log<sub>2</sub>(Fold Enrichment):</strong> ${log2FoldEnrichment(d.fold_enrichment).toFixed(2)}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('gene_ratio')) {
    tooltipContent += `<strong>Gene Ratio:</strong> ${(d.gene_ratio * 100).toFixed(1)}%<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('p_value')) {
    tooltipContent += `<strong>P-Value:</strong> ${d.p_value.toExponential(2)}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('q_value')) {
    tooltipContent += `<strong>Q-Value:</strong> ${d.q_value.toExponential(2)}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('combined_score')) {
    tooltipContent += `<strong>Combined Score:</strong> ${d.combined_score.toFixed(2)}<br/>`;
    hasContent = true;
  }
  if (visibleFields.includes('odds_ratio') && d.odds_ratio !== undefined) {
    tooltipContent += `<strong>Odds Ratio:</strong> ${d.odds_ratio.toFixed(2)}<br/>`;
    hasContent = true;
  }
  if (isGoTermEnrichment.value) {
    if (visibleFields.includes('go_namespace') && d.go_namespace) {
      const namespaceLabel = d.go_namespace === 'biological_process' ? 'BP' : 
                             d.go_namespace === 'molecular_function' ? 'MF' : 
                             d.go_namespace === 'cellular_component' ? 'CC' : d.go_namespace;
      tooltipContent += `<strong>GO Category:</strong> ${namespaceLabel}<br/>`;
      hasContent = true;
    }
    if (visibleFields.includes('go_depth') && d.go_depth !== undefined) {
      tooltipContent += `<strong>GO Depth:</strong> ${d.go_depth}<br/>`;
      hasContent = true;
    }
  }

  if (hasContent) {
    tooltipContent += `<hr style="margin:4px 0; border-color:#888"/>`;
  }
  tooltipContent += `<div style="text-align:center; font-size:0.7rem; color:#6b7280;">Right-click for full details</div>`;
  return tooltipContent;
}

function createSizeLegend(
  svg: d3.Selection<SVGGElement, unknown, null, undefined>,
  sizeScale: d3.ScalePower<number, number>,
  values: number[],
  circleSpacing = 50,
  leftMargin = 0,
  topMargin = 40,
  title = "Observed Count",
) {
  values = values.slice().sort((a, b) => a - b);
  const maxRadius = Math.max(...values.map((value) => sizeScale(value)));
  const labelOffset = 8;

  // Create a group inside parentG and position it according to margins
  const legendGroup = svg
    .append("g")
    .attr("transform", `translate(${leftMargin},${topMargin})`);

  // Title text
  legendGroup
    .append("text")
    .attr("x", 0)
    .attr("y", -topMargin / 2)
    .attr("font-size", 12)
    .attr("font-weight", "bold")
    .attr("text-anchor", "start")
    .text(title);

  // For each value, draw a circle and label
  values.forEach((value, i) => {
    const radius = sizeScale(value);
    const cy = i * circleSpacing;

    // Circle
    legendGroup
      .append("circle")
      .attr("cx", maxRadius)
      .attr("cy", cy)
      .attr("r", radius)
      .style("fill", "#bbb")
      .style("stroke", "#888");

    // Text label
    legendGroup
      .append("text")
      .attr("x", maxRadius * 2 + labelOffset)
      .attr("y", cy + 4) // vertically center text approx
      .text(value)
      .style("text-anchor", "start")
      .style("font-size", "11px");
  });
}

function createColorLegend(
  svg: d3.Selection<SVGGElement, unknown, null, undefined>,
  colorScale: d3.ScaleSequential<string>,
  minQValue: number,  // Most significant q-value (will be shown at TOP, yellow)
  maxQValue: number,  // Least significant q-value (will be shown at BOTTOM, dark)
  legendWidth = 20,
  legendHeight = 120,
  margin = { top: 40, right: 80, bottom: 10, left: 0 },
  title = "p-value",
) {
  // Create a group inside the provided parent selection and position it using margin
  const legend = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Define linearGradient with unique id to avoid conflicts
  const gradientId = `colorLegendGradient`;

  const defs = svg.append("defs");
  const gradient = defs
    .append("linearGradient")
    .attr("id", gradientId)
    .attr("x1", "0%")
    .attr("y1", "0%")
    .attr("x2", "0%")
    .attr("y2", "100%");

  // Legend orientation: TOP = most significant (low q-value, yellow), BOTTOM = least significant (high q-value, dark)
  // d=0 -> top (low q-value, yellow), d=1 -> bottom (high q-value, dark)
  const nStops = 10;
  const logMin = Math.log10(minQValue + 1e-300);
  const logMax = Math.log10(maxQValue + 1e-300);

  gradient
    .selectAll("stop")
    .data(d3.range(0, 1.01, 1 / nStops))
    .join("stop")
    .attr("offset", (d) => `${d * 100}%`)
    .attr("stop-color", (d) => {
      // d=0 -> top (low q-value), d=1 -> bottom (high q-value)
      const logValue = logMin + (logMax - logMin) * d;
      const value = Math.pow(10, logValue);
      return colorScale(value);
    });

  // Draw the rectangle filled with the gradient
  legend
    .append("rect")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .style("fill", `url(#${gradientId})`);

  // Create a logarithmic scale for the axis (low q-value at top, high at bottom)
  const legendScale = d3
    .scaleLog()
    .domain([minQValue, maxQValue])
    .range([0, legendHeight]);

  // Draw right-oriented axis on the rectangle side (no tick marks, only labels)
  const legendAxis = d3.axisRight(legendScale).ticks(5, ".1e").tickSize(0);

  legend
    .append("g")
    .attr("transform", `translate(${legendWidth}, 0)`)
    .call(legendAxis)
    .call((g) => g.select(".domain").remove());

  // Add title text above the legend - show the significance threshold used
  svg
    .append("text")
    .attr("x", margin.left)
    .attr("y", margin.top / 2)
    .attr("font-size", 12)
    .attr("font-weight", "bold")
    .attr("font-family", "sans-serif")
    .text(title + ` (< ${visualizationStore.significance})`);
}

// Draw dotplot based on pValueEntries in dotplotContainer ref
async function drawDotPlot() {
  if (!dotplotContainer.value) return;
  
  resetDotplot();
  
  // Handle case when there are no significant results
  if (!pValueEntries.value.length) {
    const container = dotplotContainer.value;
    const containerWidth = container.clientWidth || 800;
    const containerHeight = container.clientHeight || finalPlotHeight.value;
    
    const svg = d3
      .select(container)
      .append("svg")
      .attr("data-testid", "ora-dotplot-svg")
      .attr("width", containerWidth)
      .attr("height", containerHeight);
    
    // Show message for no significant results
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", containerHeight / 2 - 20)
      .attr("text-anchor", "middle")
      .attr("font-size", "16px")
      .attr("font-weight", "bold")
      .attr("fill", "#6b7280")
      .text("No Significant Results");
    
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", containerHeight / 2 + 10)
      .attr("text-anchor", "middle")
      .attr("font-size", "14px")
      .attr("fill", "#9ca3af")
      .text(`No terms with FDR q-value < ${visualizationStore.significance} found`);
    
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", containerHeight / 2 + 35)
      .attr("text-anchor", "middle")
      .attr("font-size", "12px")
      .attr("fill", "#9ca3af")
      .text("Try adjusting the significance threshold or filters");
    
    return;
  }

  const container = dotplotContainer.value;

  const totalRowSideColorWidth = 20;

  const containerWidth = container.clientWidth || 800;
  const containerHeight = container.clientHeight || finalPlotHeight.value;

  const margin = {
    top: 50,
    right: visualizationStore.legend ? oraLegendAreaWidth + 40 : 40,
    bottom: 76,
    left: 120,
  };

  if (visualizationStore.oraRowSideColor) {
    margin.left += totalRowSideColorWidth;
  }

  const innerWidth = containerWidth - margin.left - margin.right;
  const innerHeight = containerHeight - margin.top - margin.bottom;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("data-testid", "ora-dotplot-svg")
    .attr("width", containerWidth)
    .attr("height", containerHeight);

  svg
    .append("text")
    .attr("x", containerWidth / 2) // center horizontally
    .attr("y", 50 / 2) // position above the plot area, adjust as needed
    .attr("text-anchor", "middle") // center the text
    .attr("font-size", "16px")
    .attr("font-style", "italic")
    .text(beautifyLabel(localTableName.value));

  const plotGroup = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Only create legend groups if legend is enabled
  let legendGroup, colorLegendGroup, sizeLegendGroup;
  if (visualizationStore.legend) {
    legendGroup = svg
      .append("g")
      .attr(
        "transform",
        `translate(${margin.left + innerWidth + 40},${margin.top})`,
      );

    colorLegendGroup = legendGroup
      .append("g")
      .attr("transform", `translate(0,0)`);

    sizeLegendGroup = legendGroup
      .append("g")
      .attr("transform", `translate(0, ${oraColorLegendHeight + oraLegendSpacingVertical})`);
  }

  // Sort entries for plotting order
  const sortedEntries = pValueEntries.value
    .slice()
    .sort((a, b) =>
      compareValues(
        a[visualizationStore.oraOrder.name],
        b[visualizationStore.oraOrder.name],
        visualizationStore.oraOrder.order,
      ),
    );

  // Scales
  const maxLog2FoldEnrichment = d3.max(sortedEntries, (d) => log2FoldEnrichment(d.fold_enrichment)) ?? 0;
  const minLog2FoldEnrichment = d3.min(sortedEntries, (d) => log2FoldEnrichment(d.fold_enrichment)) ?? 0;
  const maxSubsetCount = d3.max(sortedEntries, (d) => d.subset_count) ?? 1;
  const minSubsetCount = d3.min(sortedEntries, (d) => d.subset_count) ?? 0;

  const xScale = d3
    .scaleLinear()
    .domain([Math.min(0, minLog2FoldEnrichment), maxLog2FoldEnrichment > 0 ? maxLog2FoldEnrichment : 1])
    .range([0, innerWidth]);

  const yScale = d3
    .scaleBand()
    .domain(sortedEntries.map((d) => d.attr))
    .range([0, innerHeight])
    .padding(0.1);

  const sizeScale = d3
    .scaleSqrt()
    .domain([minSubsetCount, maxSubsetCount])
    .range([6, maxBubbleRadius]);

  // Color scale by FDR-adjusted q-value (log scale)
  // For q-values: lower = more significant = should be brighter (yellow in VIRIDIS)
  // VIRIDIS interpolator: 0 = dark purple, 1 = yellow
  // So we INVERT the domain: [maxQValue, minQValue] so that low q-values map to high interpolator values (yellow)
  const minQValue = d3.min(sortedEntries, (d) => d.q_value) ?? parseFloat(visualizationStore.significance);
  const maxQValue = d3.max(sortedEntries, (d) => d.q_value) ?? 1;
  
  // Ensure we have a valid range for logarithmic scale (avoid values too close to 0)
  const minQValueSafe = Math.max(minQValue, 1e-300);
  // Ensure maxQValue is at least 10x larger than minQValue for visible color gradient
  const maxQValueSafe = Math.max(maxQValue, minQValueSafe * 100);
  
  // INVERTED domain: high q-values -> 0 (dark), low q-values -> 1 (yellow)
  const colorScale = d3
    .scaleSequentialLog(
      COLORSCALES[visualizationStore.oraColorScale] as (t: number) => string,
    )
    .domain([maxQValueSafe, minQValueSafe])  // INVERTED: max to min
    .clamp(true);

  // Create tooltip div (matching heatmap styling)
  const tooltip = d3
    .select(container)
    .append("div")
    .style("position", "absolute")
    .style("z-index", "1000")
    .style("visibility", "hidden")
    .style("background-color", "#f9fafb") // tailwind bg-gray-50
    .style("color", "#374151") // tailwind text-gray-700
    .style("font-size", "0.75rem") // tailwind text-xs
    .style("border-radius", "0.375rem") // tailwind rounded-md
    .style("padding", "0.5rem") // tailwind p-2
    .style("min-width", "10rem")
    .style("max-width", "20rem")
    .style("white-space", "normal")
    .style("word-wrap", "break-word")
    .style("border", "1px solid #d1d5db")
    .style("box-shadow", "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)")
    .style("pointer-events", "none");

  // Draw points
  plotGroup
    .selectAll("circle")
    .data(sortedEntries)
    .enter()
    .append("circle")
    .attr("cx", (d) => xScale(log2FoldEnrichment(d.fold_enrichment)))
    .attr("cy", (d) => (yScale(d.attr) ?? 0) + yScale.bandwidth() / 2)
    .attr("r", (d) => sizeScale(d.subset_count))
    .style("fill", (d) => colorScale(d.q_value ?? 1))
    .style("opacity", 0.8)
    .on("mouseover", (event) => {
      tooltip.style("visibility", "visible");
      d3.select(event.currentTarget)
        .style("stroke", "white")
        .style("stroke-width", 3);
    })
    .on("mousemove", (event, d) => {
      const tooltipContent = buildOraTooltipContent(d);

      const containerRect = container.getBoundingClientRect();
      const tooltipNode = tooltip.node();
      if (!tooltipNode) return;
      const tooltipRect = tooltipNode.getBoundingClientRect();

      const offsetX = 10; // horizontal offset from cursor
      const offsetY = 10; // vertical offset below cursor

      let xPosition = event.clientX - containerRect.left + offsetX;
      let yPosition = event.clientY - containerRect.top + offsetY;

      // Mirror horizontally if going out of right boundary
      if (xPosition + tooltipRect.width > containerRect.width) {
        xPosition =
          event.clientX - containerRect.left - tooltipRect.width - offsetX;
      }

      // Mirror vertically if going out of bottom boundary
      if (yPosition + tooltipRect.height > containerRect.height) {
        yPosition =
          event.clientY - containerRect.top - tooltipRect.height - offsetY;
      }

      // Clamp to minimum 0 to avoid negative positioning
      xPosition = Math.max(0, xPosition);
      yPosition = Math.max(0, yPosition);

      tooltip
        .html(tooltipContent)
        .style("left", `${xPosition}px`)
        .style("top", `${yPosition}px`)
        .style("pointer-events", "auto"); // Enable click on filter link
    })
    .on("mouseleave", (event) => {
      tooltip.style("visibility", "hidden");
      d3.select(event.currentTarget).style("stroke", "none");
    })
    .on("contextmenu", (event, d) => {
      // Right-click opens modal with full term details
      event.preventDefault();
      selectedTerm.value = d;
      showOraTooltipModal.value = true;
      tooltip.style("visibility", "hidden");
    });

  // Add mobile long-press support for touch devices
  const circleElements = plotGroup.selectAll("circle").nodes() as SVGCircleElement[];
  let longPressTimer: number | null = null;
  
  circleElements.forEach((circle) => {
    if (!circle) return;
    
    circle.addEventListener("touchstart", function (event: TouchEvent) {
      const target = event.currentTarget as SVGCircleElement;
      const d = d3.select(target).datum() as PValueEntry;
      
      longPressTimer = window.setTimeout(() => {
        selectedTerm.value = d;
        showOraTooltipModal.value = true;
        tooltip.style("visibility", "hidden");
      }, 500); // 500ms long press
    }, { passive: true });
    
    circle.addEventListener("touchend", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
    
    circle.addEventListener("touchmove", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
  });

  // X axis
  const xAxis = d3.axisBottom(xScale).ticks(6).tickFormat(d3.format(".2f"));
  plotGroup
    .append("g")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(xAxis);

  // Y axis with label truncation
  const maxLabelWidth = 100; // Max width for labels
  
  const yAxisGroup = plotGroup
    .append("g")
    .attr("transform", `translate(${0 - totalRowSideColorWidth},${0})`)
    .call(d3.axisLeft(yScale).tickSizeOuter(0));
  
  const yAxisFontSize = Math.max(8, Math.min(10, yScale.bandwidth() * 0.75));
  const yAxisTexts = yAxisGroup.selectAll("text")
    .style("font-size", `${yAxisFontSize}px`);
  
  // Truncate long labels and add ellipsis
  yAxisTexts.each(function() {
    const textElement = d3.select(this);
    const originalText = textElement.text();
    const textLength = (this as SVGTextElement).getComputedTextLength();
    
    if (textLength > maxLabelWidth) {
      let truncatedText = originalText;
      
      // Iteratively truncate until it fits
      while ((this as SVGTextElement).getComputedTextLength() > maxLabelWidth && truncatedText.length > 0) {
        truncatedText = truncatedText.slice(0, -1);
        textElement.text(truncatedText + '...');
      }
      
      // Store original text as title for browser tooltip
      textElement.append("title").text(originalText);
    }
  });
  
  // Add custom tooltip for row labels
  const rowLabelTooltip = d3
    .select(container)
    .append("div")
    .attr("class", "row-label-tooltip")
    .style("position", "absolute")
    .style("z-index", "60")
    .style("visibility", "hidden")
    .style("background-color", "#1f2937")
    .style("color", "#f9fafb")
    .style("font-size", "0.75rem")
    .style("border-radius", "0.375rem")
    .style("padding", "0.25rem 0.5rem")
    .style("white-space", "nowrap")
    .style("pointer-events", "none");
  
  yAxisTexts
    .on("mouseover", function() {
      const currentText = d3.select(this).text();
      
      // Only show tooltip if text is truncated (contains "...")
      if (currentText.includes('...')) {
        const titleElement = d3.select(this).select("title");
        const fullText = !titleElement.empty() ? titleElement.text() : currentText.replace('...', '');
        
        rowLabelTooltip.html(fullText);
        rowLabelTooltip.style("visibility", "visible");
      }
    })
    .on("mousemove", function(event) {
      if (!dotplotContainer.value) return;
      const containerRect = dotplotContainer.value.getBoundingClientRect();
      
      const xPos = event.clientX - containerRect.left + 10;
      const yPos = event.clientY - containerRect.top - 10;
      
      rowLabelTooltip
        .style("left", xPos + "px")
        .style("top", yPos + "px");
    })
    .on("mouseout", function() {
      rowLabelTooltip.style("visibility", "hidden");
    });

  // Axis label
  svg
    .append("text")
    .attr("x", margin.left + innerWidth / 2)
    .attr("y", containerHeight - 42)
    .attr("text-anchor", "middle")
    .attr("font-weight", "bold")
    .call((text) => {
      text.append("tspan").text("log");
      text.append("tspan")
        .attr("baseline-shift", "sub")
        .attr("font-size", "70%")
        .text("2");
      text.append("tspan").text("(Fold Enrichment)");
    });

  // Create legends only if enabled
  if (visualizationStore.legend && colorLegendGroup && sizeLegendGroup) {
    // Use actual min/max q-values from data for legend (same as color scale domain - INVERTED)
    // Legend shows: top = most significant (low q-value, yellow), bottom = least significant (high q-value, dark)
    createColorLegend(
      colorLegendGroup, // pass the top legend group
      colorScale,
      minQValueSafe,  // Legend top: most significant (yellow)
      maxQValueSafe,  // Legend bottom: least significant (dark)
      20, // legendWidth
      120, // legendHeight
      { top: 20, right: 0, bottom: 0, left: 0 }, // no margin inside group
      "q-value (FDR)",
    );
    const sizeValues = getSizeLegendValues(sortedEntries);

    createSizeLegend(
      sizeLegendGroup, // pass the bottom legend group
      sizeScale,
      sizeValues,
      oraSizeLegendCircleSpacing,
      0, // leftMargin inside group
      oraSizeLegendTopMargin,
      "Observed Count",
    );
  }

  //RowSideColor
  const yLabels = sortedEntries.map((d) => d.attr);
  const attributeValues = sortedEntries.map((d) => d.attr);

  if (visualizationStore.oraRowSideColor) {
    await renderDotplotRowSideColors({
      svg,
      margin,
      yLabels,
      attributeValues,
      column_name: visualizationStore.oraColumnName,
      colType: columnMeta.value?.type.toLowerCase() ?? "text",
      sideColorWidth: totalRowSideColorWidth, // you have set to 20
    });
  }
}

//onTableChange
function onTableChange(value: string) {
  localTableName.value = value;
  emit("update:tableName", value);
}

// Handle filtering by ORA term from modal
function handleFilterByTerm(term: string) {
  filtersStore.setFilter(visualizationStore.oraColumnName, {
    value: term,
  });
}

//addDotplot
async function addDotplot() {
  if (props.existingTables.length !== Object.keys(props.allTables).length) {
    const nextTable = Object.entries(props.allTables).find(
      ([key]) => !props.existingTables.includes(key) && key !== props.tableName,
    )?.[0];
    if (nextTable) {
      emit("update:tableName", localTableName.value + "," + nextTable);
    }
  }
}

function removeDotplot() {
  if (props.existingTables.length > 1) {
    emit("update:tableName", "");
  }
}

function openSettingsOverlay() {
  emit("openSettingsOverlay");
}

const emit = defineEmits(["update:tableName", "openSettingsOverlay", "loading-change", "load-cancel"]);

watch(
  [loading, loadingProgress],
  () => {
    emit("loading-change", {
      tableName: props.tableName,
      loading: loading.value,
      progress: loadingProgress.value,
      phaseHint: loadingPhaseHint.value,
    });
  },
  { immediate: true },
);

watch(
  [() => visualizationStore.oraColumnName],
  async () => {
    if (props.hashLoading) return;
    visualizationStore.setOraAvailableGoDepths([]);
    visualizationStore.setOraGoDepthFilter(0);
    await fetchAndPrepareData();
  },
  { immediate: true },
);

watch(
  () => props.hashLoading,
  async (isLoading) => {
    if (isLoading === false) {
      await fetchAndPrepareData();
    }
  },
  { immediate: true },
);

watch(
  [
    () => visualizationStore.significance,
    () => visualizationStore.oraTopN,
    () => visualizationStore.oraMinCount,
    () => visualizationStore.oraGoDepthFilter,
  ],
  async () => {
    if (props.hashLoading) return;
    if (loading.value || !renderReady.value) return;
    await showLoadingFrame();
    await syncPlotHeightWithViewport();
    setLoadingProgress(65);
    setLoadingPhaseHint("Applying ORA filters...");
    await drawDotPlot();
    publishAnalysisContext();
    setLoadingProgress(100);
    renderReady.value = true;
    loading.value = false;
    loadingProgress.value = null;
  },
  { deep: true },
);

// Render-only settings — no re-fetch needed, just redraw the dot plot
watch(
  [
    () => visualizationStore.legend,
    () => visualizationStore.oraRowSideColor,
    () => visualizationStore.oraColorScale,
    () => visualizationStore.oraOrder,
  ],
  async () => {
    if (props.hashLoading) return;
    if (loading.value || !renderReady.value) return;
    await showLoadingFrame();
    await syncPlotHeightWithViewport();
    setLoadingProgress(65);
    setLoadingPhaseHint("Redrawing ORA visualization...");
    await drawDotPlot();
    setLoadingProgress(100);
    renderReady.value = true;
    loading.value = false;
    loadingProgress.value = null;
  },
  { deep: true },
);

// Watch for filter changes from sidebar and per-dataset ID filters
watch(
  [() => filters.value, () => filtersStore.datasetIdFilters, filterChainVersion],
  async () => {
    if (props.hashLoading) return;
    await fetchAndPrepareData();
  },
  { deep: true },
);

watch(
  [sidebarOpen, () => props.existingTables],
  async () => {
    if (props.hashLoading) return;
    if (loading.value || !renderReady.value) return;
    await showLoadingFrame();
    window.setTimeout(async () => {
      await syncPlotHeightWithViewport();
      setLoadingProgress(65);
      setLoadingPhaseHint("Resizing ORA visualization...");
      await drawDotPlot();
      setLoadingProgress(100);
      renderReady.value = true;
      loading.value = false;
      loadingProgress.value = null;
    }, 300);
  },
  { deep: true },
);

// ResizeObserver for responsive sizing
let resizeObserver: ResizeObserver | null = null;
let resizeTimeout: ReturnType<typeof setTimeout> | null = null;
let lastContainerWidth = 0;

function handleWindowResize() {
  updateAvailablePlotHeight();
  if (!loading.value && renderReady.value && hasPreparedPlotData.value) {
    if (resizeTimeout) clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      drawDotPlot();
    }, 150);
  }
}

onMounted(async () => {
  await nextTick();
  updateAvailablePlotHeight();
  window.addEventListener("resize", handleWindowResize);

  // Set GO terms as default column if available and current is still default (ortho_id)
  if (visualizationStore.oraColumnName === 'ortho_id' && columnsStore.rowColumns.length > 0) {
    const goColumn = columnsStore.rowColumns.find(col => {
      const colName = col.column_name.toLowerCase();
      return colName.includes('go') || 
             colName === 'go_terms' ||
             colName === 'gene_ontology' ||
             colName.startsWith('go_');
    });
    
    if (goColumn) {
      visualizationStore.oraColumnName = goColumn.column_name;
    }
  }
  
  // Setup resize observer for responsive plot sizing
  if (dotplotContainer.value) {
    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      
      const newWidth = entry.contentRect.width;
      
      // Width changes require a redraw; height-only changes from the info banner
      // should not rescale the dot plot internals.
      if (
        Math.abs(newWidth - lastContainerWidth) > 5
      ) {
        lastContainerWidth = newWidth;
        
        // Debounce resize events
        if (resizeTimeout) clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
          if (!loading.value && renderReady.value && hasPreparedPlotData.value) {
            drawDotPlot();
          }
        }, 150);
      }
    });
    resizeObserver.observe(dotplotContainer.value);
  }
});

onUnmounted(() => {
  activeAbortController?.abort();
  stopSoftProgress();
  window.removeEventListener("resize", handleWindowResize);
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
    resizeTimeout = null;
  }
  // Drop our digest from the assistant context so stale results don't
  // leak into other views.
  assistantStore.setAnalysisContext(`ora:${props.tableName}`, null);
});
</script>
