<template>
  <main class="flex flex-col h-full min-h-0 overflow-hidden">
    <div
      class="flex justify-between gap-2 px-2 items-start mb-2 flex-shrink-0 flex-wrap"
      data-export-ignore="true"
    >
      <div class="text-gray-500 font-medium flex items-center gap-2 min-w-0 flex-wrap">
        <DropdownMenu
          :modelValue="localTableName"
          :options="tableNameOptions"
          @update:modelValue="
            (val) => {
              localTableName = val;
              emit('update:tableName', val); // emit to parent that selected table changed
            }
          "
        />
        <span class="pl-2 text-xs whitespace-nowrap"
        >({{ getEntityCountLabel() }}: {{ rowCount }})</span
        >
      </div>
      <div class="flex gap-2 flex-wrap justify-end">
        <button
          v-if="rowCount <= 1000 && rowCount > 0"
          aria-label="Toggle zoom mode"
          @click="toggleZoomMode"
          class="p-2 rounded-md border"
          :class="zoomMode
            ? 'text-white bg-primary-500 border-primary-500'
            : 'text-primary-500 border-primary-500 hover:bg-primary-500 hover:text-white'"
          v-tooltip="zoomMode ? 'Zoom mode active' : 'Rectangle zoom mode'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10.5 18a7.5 7.5 0 1 1 5.3-12.8A7.5 7.5 0 0 1 10.5 18Z" />
            <path stroke-linecap="round" stroke-linejoin="round" d="m16 16 5 5M8 10.5h5M10.5 8v5" />
          </svg>
        </button>

        <button
          v-if="rowCount <= 1000 && rowCount > 0"
          aria-label="Toggle pan mode"
          @click="togglePanMode"
          :disabled="!isHeatmapZoomed"
          class="p-2 rounded-md border"
          :class="panMode
            ? 'text-white bg-primary-500 border-primary-500'
            : 'text-primary-500 border-primary-500 disabled:opacity-50 hover:bg-primary-500 hover:text-white'"
          v-tooltip="!isHeatmapZoomed ? 'Zoom in before panning' : panMode ? 'Pan mode active' : 'Pan mode'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M7 11.5V9a2 2 0 1 1 4 0v2.5M11 11V8a2 2 0 1 1 4 0v4m0-1V9.5a2 2 0 1 1 4 0V15a6 6 0 0 1-6 6h-1.5a6 6 0 0 1-4.8-2.4L4 15v-1a2 2 0 0 1 3.2-1.6L9 14" />
          </svg>
        </button>

        <button
          v-if="rowCount <= 1000 && rowCount > 0"
          aria-label="Reset heatmap zoom"
          @click="resetZoom"
          :disabled="!isHeatmapZoomed"
          class="p-2 rounded-md text-primary-500 border border-primary-500 disabled:opacity-50"
          :class="{'hover:bg-primary-500 hover:text-white': isHeatmapZoomed}"
          v-tooltip="isHeatmapZoomed ? 'Reset zoom' : 'No zoom active'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 12a9 9 0 1 0 3-6.7M3 4v5h5" />
          </svg>
        </button>

        <span v-tooltip="props.existingTables.length === Object.keys(props.allTables).length ? 'All heatmaps already shown' : 'Add another heatmap'">
        <button
          aria-label="Add another heatmap"
          @click="addHeatmap"
          :disabled="
            props.existingTables.length === Object.keys(props.allTables).length
          "
          class="p-2 rounded-md text-primary-500 border border-primary-500"
          :class="{
            'disabled:opacity-50':
              props.existingTables.length ===
              Object.keys(props.allTables).length,
            'hover:bg-primary-500 hover:text-white':
              props.existingTables.length !==
              Object.keys(props.allTables).length,
          }"
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
        </span>

        <span v-tooltip="existingTables.length === 1 ? 'Cannot remove last heatmap' : 'Remove heatmap'">
        <button
          aria-label="Remove heatmap"
          @click="removeHeatmap"
          :disabled="existingTables.length === 1"
          class="p-2 rounded-md text-accent1-500 border border-accent1-500"
          :class="{
            'disabled:opacity-50': existingTables.length === 1,
            'hover:bg-accent1-500 hover:text-white': existingTables.length > 1,
          }"
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
        </span>

        <button
          v-if="showSharedActions"
          aria-label="Share the heatmap"
          @click="showShareOverlay = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Share the heatmap'"
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
          aria-label="Configure the visuals of the heatmap"
          @click="openSettingsOverlay"
          class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900"
          v-tooltip="'Configure the visuals of the heatmap'"
        >
          <!-- SVG icon as before -->
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
            />
          </svg>
        </button>
      </div>
    </div>
    <div
      v-if="rowCount <= 1000 && rowCount > 0"
      class="border border-gray-300 rounded-md bg-white flex-grow flex flex-col min-h-0 overflow-hidden"
    >
      <div class="flex-grow relative w-full min-h-0 overflow-hidden">
        <LoadingOverlay
          v-if="loading && !deferLoadingOverlay"
          primaryStatus="Generating expression heatmap..."
          :currentPhaseHint="loadingPhaseHint"
          cancellable
          @cancel="cancelActiveLoad"
        />
        <div ref="heatmapContainer" class="w-full h-full"></div>
      </div>
    </div>

    <!-- Show loading spinner when loading and rowCount is 0 or too high -->
    <div v-else-if="loading" class="flex-grow relative border border-gray-300 rounded-md bg-white min-h-[300px]">
      <LoadingOverlay
        v-if="!deferLoadingOverlay"
        size="md"
        primaryStatus="Generating expression heatmap..."
        :currentPhaseHint="loadingPhaseHint"
        cancellable
        @cancel="cancelActiveLoad"
      />
    </div>

    <div v-else class="flex-grow min-h-0">
      <NoDataComponent :rowCount="rowCount"/>
    </div>

    <!-- Conditionally render the ShareOverlay -->
    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(heatmapContainer)"
      @close="showShareOverlay = false"
    />

    <ExportModal
      v-if="showExportModal"
      :data="heatmapExportPayload.data"
      :columns="heatmapExportPayload.columns"
      :columnDisplayNames="heatmapExportColumnDisplayNames"
      :metaColumns="heatmapExportPayload.metaColumns"
      :sampleColumns="heatmapExportPayload.sampleColumns"
      :filename="heatmapExportPayload.filename"
      :hasFilters="heatmapExportPayload.hasFilters"
      :totalCount="heatmapExportPayload.data.length"
      @close="showExportModal = false"
    />
    
    <!-- Tooltip Modal for detailed metadata -->
    <TooltipModal
      :show="showTooltipModal"
      :rowData="selectedRowData"
      :tableName="props.tableName"
      :idColumn="idColumn"
      :heatmapCols="heatmapCols"
      :columnValue="selectedColumnValue"
      :cellValue="selectedCellValue"
      @close="closeTooltipModal"
    />
  </main>
</template>
<script setup lang="ts">
import axios from "axios";
import * as d3 from "d3";
import {lowerCase} from "lodash-es";
import {
  computed,
  inject,
  nextTick,
  onBeforeUnmount,
  ref,
  type Ref,
  watch,
} from "vue";

import DropdownMenu from "./DropdownMenu.vue";
import {COLORSCALES} from "@/shared/Colorscales";
import {useColumnsStore} from "@/stores/columns";
import {API_BASE_URL, type Config} from "@/shared/Config";
import {useFiltersStore} from "@/stores/filters";
import { useFilterSeparation } from "@/shared/useFilterSeparation";
import LoadingOverlay from "./LoadingOverlay.vue";
import type {MetaFormat} from "@/shared/MetaFormat";
import NoDataComponent from "./NoDataComponent.vue";
import type {RowType} from "@/shared/RowType";
import {beautifyLabel, compareValues} from "@/shared/utils";
import ShareOverlay from "./ShareOverlay.vue";
import ExportModal from "./ExportModal.vue";
import {useVisualizationStore} from "@/stores/visualization";
import { getExpressionOption } from "@/shared/ExpressionDisplay";
import TooltipModal from "./TooltipModal.vue";
import { getDisplayName, sequenceFields, verboseFields } from "@/shared/metadataDisplayNames";
import { getEntityCountLabel } from "@/shared/dataTypeLabels";
import { useClustering } from "@/shared/useClustering";
import {
  createVisibleColorMapping,
  getListMetadataKey,
  normalizeMetadataList,
  type SharedColorRegistry,
  type SideColorValue,
} from "@/shared/colorMapping";

// TODO: Add gene detail view

const config = inject("config") as Config;
const sharedColorRegistry = inject<SharedColorRegistry>('sharedColorRegistry', undefined);
const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const columnStore = useColumnsStore();
const { filters, sampleFilters, filterChainVersion, getMergedGeneFilters, getFilterChainPayload } = useFilterSeparation();
const { performClustering } = useClustering();

// Per-dataset merged gene filters (includes per-dataset ID filter)
const mergedGeneFilters = computed(() => getMergedGeneFilters(props.tableName).value);

const sidebarOpen = inject("sidebarOpen") as Ref<boolean> | undefined; //Provided by App.vue

const props = withDefaults(defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
  showSharedActions?: boolean;
  deferLoadingOverlay?: boolean;
}>(), {
  showSharedActions: true,
  deferLoadingOverlay: false,
});

const emit = defineEmits(["openSettingsOverlay", "update:tableName", "loading-change", "load-cancel"]);

const localTableName = ref(props.tableName);
const tableNameOptions = computed(() => {
  return Object.fromEntries(
    Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) || key === props.tableName,
    ),
  );
});

const loading = ref(false);
const loadingProgress = ref<number | null>(null);
const loadingPhaseHint = ref("Preparing heatmap request...");
const showShareOverlay = ref(false);
const showExportModal = ref(false);
const showTooltipModal = ref(false);
const selectedRowData = ref<RowType | null>(null);
const selectedColumnValue = ref("");
const selectedCellValue = ref<string | number>("");

const closeTooltipModal = () => {
  showTooltipModal.value = false;
  selectedRowData.value = null;
  selectedColumnValue.value = "";
  selectedCellValue.value = "";
};

const error = ref("");
const rowCount = ref(0);
const rows = ref<RowType[]>([]);
const processedRows = ref<RowType[]>([]);
const sortedRows = ref<RowType[]>([]);
const columnNames = ref<string[]>([]);
const dataColumnNames = ref<string[]>([]);
const columns = ref<RowType[]>([]);
const sortedColumns = ref<RowType[]>([]);

const heatmapContainer = ref<HTMLDivElement | null>(null);
const heatmapInstanceId = `heatmap-${Math.random().toString(36).slice(2, 10)}`;
const colorLegendId = `${heatmapInstanceId}-color-legend`;
const sideColorTooltipId = `${heatmapInstanceId}-side-color-tooltip`;

interface HeatmapZoomWindow {
  xStart: number;
  xEnd: number;
  yStart: number;
  yEnd: number;
}

const zoomWindow = ref<HeatmapZoomWindow | null>(null);
const zoomMode = ref(false);
const panMode = ref(false);

// Guards against concurrent renders: if a second render is requested while
// one is already in progress, it will be queued and run immediately after.
let isRendering = false;
let renderPending = false;
let renderFrame: number | null = null;
let renderTimer: ReturnType<typeof setTimeout> | null = null;
let isUnmounting = false;
let loadRequestSeq = 0;
let activeAbortController: AbortController | null = null;

const LEGEND_WIDTH = 18;
const LEGEND_GAP = 5;
const LEGEND_RIGHT_PADDING = 12;
const LEGEND_AXIS_SPACE = 34;
const LEGEND_LABEL_FONT = "11px sans-serif";
const LEGEND_LABEL_LINE_HEIGHT = 12;
const SIDE_COLOR_WIDTH = 18;
const SIDE_COLOR_GAP = 2;
const MAX_RENDER_RETRIES = 18;

// geneFilters and sampleFilters are now provided by useFilterSeparation composable

const sortedColsKeys = computed(() =>
  sortedColumns.value.map((col) => String(col.column_name ?? "")).filter(Boolean),
);

const visibleColumns = computed(() => {
  const presentColumns = new Set<string>();
  for (const row of rows.value) {
    for (const col of sortedColsKeys.value) {
      if (row[col] !== undefined && row[col] !== "[BLOB]") {
        presentColumns.add(col);
      }
    }
  }
  return sortedColsKeys.value.filter((col) => presentColumns.has(col));
});

// Reactive references for TooltipModal
const idColumn = computed(() => config.visualization.id_column);
const heatmapCols = computed(() => visibleColumns.value);
const isHeatmapZoomed = computed(() => zoomWindow.value !== null);

const heatmapExportMetaColumns = computed(() =>
  columnNames.value.includes(idColumn.value) ? [idColumn.value] : [],
);

const heatmapExportColumnDisplayNames = computed(() => {
  const mapping: Record<string, string> = {};
  for (const column of heatmapExportMetaColumns.value) {
    mapping[column] = getDisplayName(column);
  }
  for (const column of visibleColumns.value) {
    mapping[column] = column;
  }
  return mapping;
});

const heatmapExportPayload = computed(() => {
  const metaColumns = heatmapExportMetaColumns.value;
  const sampleColumns = visibleColumns.value;
  const columnsForExport = [...metaColumns, ...sampleColumns];
  const data = sortedRows.value.map((row) => {
    const exportRow: RowType = {};
    for (const column of columnsForExport) {
      exportRow[column] = row[column];
    }
    return exportRow;
  });

  return {
    data,
    columns: columnsForExport,
    metaColumns,
    sampleColumns,
    filename: `heatmap_${props.tableName}_${visualizationStore.expressionDisplay.optionId}`,
    hasFilters: Object.keys(filters.value).length > 0,
    dataset: props.tableName,
  };
});

defineExpose({
  getExportPayload: () => heatmapExportPayload.value,
  cancelActiveLoad,
});

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
  clearScheduledRender();
  loading.value = false;
  loadingProgress.value = null;
  setLoadingPhaseHint("Load canceled");
  if (emitCancel) emit("load-cancel");
}

function getCurrentZoomWindow(rowTotal: number, colTotal: number): HeatmapZoomWindow {
  const current = zoomWindow.value;
  if (!current) {
    return {xStart: 0, xEnd: colTotal, yStart: 0, yEnd: rowTotal};
  }
  return clampZoomWindow(current, rowTotal, colTotal);
}

function clampZoomWindow(window: HeatmapZoomWindow, rowTotal: number, colTotal: number): HeatmapZoomWindow {
  const visibleCols = Math.max(1, Math.min(colTotal, window.xEnd - window.xStart));
  const visibleRows = Math.max(1, Math.min(rowTotal, window.yEnd - window.yStart));
  const xStart = Math.max(0, Math.min(window.xStart, Math.max(0, colTotal - visibleCols)));
  const yStart = Math.max(0, Math.min(window.yStart, Math.max(0, rowTotal - visibleRows)));
  return {
    xStart,
    xEnd: Math.min(colTotal, xStart + visibleCols),
    yStart,
    yEnd: Math.min(rowTotal, yStart + visibleRows),
  };
}

function setZoomWindow(nextWindow: HeatmapZoomWindow | null) {
  if (!nextWindow) {
    zoomWindow.value = null;
    panMode.value = false;
    scheduleHeatmapRender();
    return;
  }

  const clamped = clampZoomWindow(nextWindow, sortedRows.value.length, visibleColumns.value.length);
  if (
    clamped.xStart <= 0 &&
    clamped.yStart <= 0 &&
    clamped.xEnd >= visibleColumns.value.length &&
    clamped.yEnd >= sortedRows.value.length
  ) {
    zoomWindow.value = null;
    panMode.value = false;
  } else {
    zoomWindow.value = clamped;
  }
  scheduleHeatmapRender();
}

function resetZoom() {
  zoomMode.value = false;
  panMode.value = false;
  setZoomWindow(null);
}

function toggleZoomMode() {
  zoomMode.value = !zoomMode.value;
  if (zoomMode.value) {
    panMode.value = false;
  }
  scheduleHeatmapRender();
}

function togglePanMode() {
  if (!isHeatmapZoomed.value) {
    panMode.value = false;
    return;
  }
  panMode.value = !panMode.value;
  if (panMode.value) {
    zoomMode.value = false;
  }
  scheduleHeatmapRender();
}

// Helper
function getColumnKeys(dataRows: RowType[]): string[] {
  return [...new Set(dataRows.flatMap((row) => Object.keys(row)))];
}

// Fetch data
async function fetchAndPrepareData() {
  const requestId = ++loadRequestSeq;
  activeAbortController?.abort();
  const controller = new AbortController();
  activeAbortController = controller;
  loading.value = true;
  loadingProgress.value = 0;
  setLoadingPhaseHint("Counting filtered transcripts...");
  error.value = "";
  const totalSteps = 7;
  try {
    //COUNT
    const {data: count} = await axios.post(
      `${API_BASE_URL}/api/count`,
      {
        table_name: props.tableName,
        filters: mergedGeneFilters.value,
        filter_chain: getFilterChainPayload(mergedGeneFilters.value),
      },
      { signal: controller.signal },
    );
    if (requestId !== loadRequestSeq || controller.signal.aborted) return;
    setLoadingProgress(1, totalSteps);
    setLoadingPhaseHint("Fetching expression values...");

    rowCount.value = count.count;

    //Process data fetching only when there is <= 1000 and > 0
    if (rowCount.value <= 1000 && rowCount.value > 0) {
      //DATA
      console.log('Heatmap - Fetching data with expression mode:', {
        optionId: visualizationStore.expressionDisplay.optionId,
        layer: visualizationStore.expressionDisplay.layer,
        transform: visualizationStore.expressionDisplay.transform
      });
      
      const {data: responseData} = await axios.post(
        `${API_BASE_URL}/api/data`,
        {
          table_name: props.tableName,
          filters: mergedGeneFilters.value,
          filter_chain: getFilterChainPayload(mergedGeneFilters.value),
          sample_filters: sampleFilters.value,
          layer: visualizationStore.expressionDisplay.layer,
          transform: visualizationStore.expressionDisplay.transform,
        },
        { signal: controller.signal },
      );
      if (requestId !== loadRequestSeq || controller.signal.aborted) return;
      setLoadingProgress(2, totalSteps);
      setLoadingPhaseHint("Loading sample columns...");

      // Extract data and layer metadata from response
      const data = responseData.data || responseData;
      const layerMetadata = responseData.layer_metadata;
      
      // Optional: Log layer info for debugging
      if (layerMetadata) {
        console.log('Expression Layer:', layerMetadata.layer_used);
        console.log('Transform:', layerMetadata.transform);
        console.log('Reasoning:', layerMetadata.layer_reasoning);
      }

      rows.value = Array.isArray(data)
        ? maskRows(data, config.visualization.hide_columns)
        : [];

      columnNames.value = getColumnKeys(rows.value);

      //DATA_COLUMNS
      const columnRes = await axios.get<MetaFormat[]>(
        `${API_BASE_URL}/api/columns`,
        {params: {table_name: props.tableName, meta: false}, signal: controller.signal},
      );
      if (requestId !== loadRequestSeq || controller.signal.aborted) return;
      setLoadingProgress(3, totalSteps);
      setLoadingPhaseHint("Loading sample metadata...");
      dataColumnNames.value = columnRes.data.map((c) => c.column_name);

      //METADATA
      const {data: metaResponseData} = await axios.post(
        `${API_BASE_URL}/api/data`,
        {
          table_name: props.tableName + "_meta",
          filters: {},
        },
        { signal: controller.signal },
      );
      if (requestId !== loadRequestSeq || controller.signal.aborted) return;
      setLoadingProgress(4, totalSteps);
      setLoadingPhaseHint("Preparing normalized matrix...");

      const colData = metaResponseData.data || metaResponseData;
      columns.value = (Array.isArray(colData) ? colData : []).filter((meta: RowType) =>
        dataColumnNames.value.includes(meta.column_name as string),
      );
      columnStore.setSampleMetadata(columns.value as Record<string, unknown>[], props.tableName);

      processedRows.value = calculateProcessedRows();
      setLoadingProgress(5, totalSteps);

      // Initialize tooltip fields with all available metadata fields except sequences and verbose fields
      if (visualizationStore.tooltipFields === null && rows.value.length > 0) {
        const firstRow = rows.value[0];
        const allFields = Object.keys(firstRow).filter(
          (key) => !dataColumnNames.value.includes(key) && key !== idColumn.value
        );
        
        // Exclude sequence fields and verbose fields by default
        const excludedFields = [...sequenceFields, ...verboseFields];
        const defaultFields = allFields.filter(
          (field) => !excludedFields.includes(field)
        );
        
        visualizationStore.setTooltipFields(defaultFields);
      }
      
      // Initialize default SideColors if not already set
      const rowColumnNames = columnNames.value.filter((c) => !dataColumnNames.value.includes(c));
      // Use columnsStore.colColumns which includes 'tissue_types'
      const colColumnNames = columnStore.colColumns.map((c) => c.column_name);
      visualizationStore.initializeDefaultSideColors(rowColumnNames, colColumnNames);

      recalculateData(); // recalc after new data
      setLoadingPhaseHint("Applying heatmap ordering...");
      
      // Trigger re-clustering if clustering is enabled (when data changes)
      const { clusterRows, clusterCols } = visualizationStore.clustering;
      if ((clusterRows || clusterCols) && processedRows.value.length > 0) {
        setLoadingPhaseHint("Applying configured hierarchical clustering...");
        await performClustering(
          processedRows.value, 
          dataColumnNames.value,
          props.tableName,
          mergedGeneFilters.value,
          sampleFilters.value
        );
        recalculateData(); // recalc with new cluster order
      }
      setLoadingProgress(6, totalSteps);
      setLoadingPhaseHint("Rendering heatmap tiles...");

      await nextTick();
      await renderHeatmap();
      setLoadingProgress(7, totalSteps);
    }
  } catch (e) {
    if (isCanceledRequest(e)) return;
    console.error("Error fetching data:", e);
    error.value = "Failed to load data.";
  } finally {
    if (requestId === loadRequestSeq) {
      activeAbortController = null;
      loading.value = false;
      loadingProgress.value = null;
    }
  }
}

// Preprocessing
function maskRow(
  row: RowType,
  hide: string[],
  placeholder = "[BLOB]",
): RowType {
  if (!hide.length) return row;
  const masked: RowType = {...row};
  for (const col of hide) {
    if (col in masked) masked[col] = placeholder;
  }
  return masked;
}

function maskRows(
  dataRows: RowType[],
  hideCols: string[],
  placeholder = "[BLOB]",
): RowType[] {
  if (!hideCols.length) return dataRows;
  return dataRows.map((row) => maskRow(row, hideCols, placeholder));
}

// Processing
function recalculateData() {
  sortedRows.value = calculateSortedRows(processedRows.value);
  sortedColumns.value = calculateSortedColumns(columns.value);
  if (zoomWindow.value) {
    zoomWindow.value = clampZoomWindow(zoomWindow.value, sortedRows.value.length, visibleColumns.value.length);
  }
}

function calculateProcessedRows(): RowType[] {
  // With backend layer/transform support, no client-side processing needed
  // Backend now handles layer selection and transformations (log2, zscore)
  // This function can be simplified or removed entirely
  return rows.value;
}

function calculateSortedRows(processed: RowType[]): RowType[] {
  if (!processed || processed.length === 0) return [];
  
  // Check if clustering is enabled and we have cluster order
  const { clusterRows } = visualizationStore.clustering;
  const clusterRowOrder = visualizationStore.getClusterRowOrder(props.tableName);
  
  if (clusterRows && clusterRowOrder && clusterRowOrder.length === processed.length) {
    // Apply cluster ordering
    return clusterRowOrder.map(index => processed[index]);
  }
  
  // Fall back to standard sorting
  const primaryKey = visualizationStore.rowOrder.name;
  const primaryOrder = visualizationStore.rowOrder.order;

  const sorted = [...processed].sort((a, b) => {
    const compPrimary = compareValues(
      a[primaryKey],
      b[primaryKey],
      primaryOrder,
    );
    if (compPrimary !== 0) return compPrimary;
    return compareValues(a[idColumn.value], b[idColumn.value], "asc");
  });

  return sorted;
}

function calculateSortedColumns(metaData: RowType[]): RowType[] {
  if (!metaData || metaData.length === 0) return [];

  // Check if clustering is enabled and we have cluster order
  const { clusterCols } = visualizationStore.clustering;
  const clusterColOrder = visualizationStore.getClusterColOrder(props.tableName);
  
  if (clusterCols && clusterColOrder && clusterColOrder.length === metaData.length) {
    // Apply cluster ordering
    return clusterColOrder.map(index => metaData[index]);
  }

  const customOrder = visualizationStore.customColOrder;
  if (customOrder.enabled) {
    const tissueKey = columnStore.tissueColumnName ?? 'tissue';
    if (customOrder.mode === "samples" && customOrder.sampleNames.length > 0) {
      const sampleRank = new Map(customOrder.sampleNames.map((sampleName, index) => [sampleName, index]));
      return [...metaData].sort((a, b) => {
        const aName = String(a.column_name ?? "");
        const bName = String(b.column_name ?? "");
        const aRank = sampleRank.get(aName) ?? Number.MAX_SAFE_INTEGER;
        const bRank = sampleRank.get(bName) ?? Number.MAX_SAFE_INTEGER;
        if (aRank !== bRank) return aRank - bRank;
        return aName.localeCompare(bName);
      });
    }

    if (customOrder.mode === "metadata" && customOrder.metadataValues.length > 0) {
      const metadataKey = customOrder.metadataColumn === "tissue_types" ? tissueKey : customOrder.metadataColumn;
      const valueRank = new Map(customOrder.metadataValues.map((value, index) => [value, index]));
      return [...metaData].sort((a, b) => {
        const aValue = String(a[metadataKey] ?? "");
        const bValue = String(b[metadataKey] ?? "");
        const aRank = valueRank.get(aValue) ?? Number.MAX_SAFE_INTEGER;
        const bRank = valueRank.get(bValue) ?? Number.MAX_SAFE_INTEGER;
        if (aRank !== bRank) return aRank - bRank;
        const valueComparison = compareValues(aValue, bValue, "asc");
        if (valueComparison !== 0) return valueComparison;
        return String(a.column_name ?? "").localeCompare(String(b.column_name ?? ""));
      });
    }
  }
  
  // Fall back to standard sorting
  const primaryKey = visualizationStore.colOrder.name;
  const primaryOrder = visualizationStore.colOrder.order;

  const sorted = [...metaData].sort((a, b) => {
    // For tissue_types, use the configured tissue column
    const tissueKey = columnStore.tissueColumnName ?? 'tissue';
    const actualPrimaryKey = primaryKey === "tissue_types" ? tissueKey : primaryKey;
    const compPrimary = compareValues(
      a[actualPrimaryKey],
      b[actualPrimaryKey],
      primaryOrder,
    );
    if (compPrimary !== 0) return compPrimary;

    if (primaryKey !== "tissue_types") {
      const compTissue = compareValues(
        a[tissueKey] ?? "",
        b[tissueKey] ?? "",
        "asc",
      );
      if (compTissue !== 0) return compTissue;
    }

    // Fallback alphabetical by column_name ascending
    return ((a.column_name as string) ?? "").localeCompare(
      (b.column_name as string) ?? "",
    );
  });

  return sorted;
}

//Heatmap
function getHeatmapLegendLabel(): string {
  return getExpressionOption(visualizationStore.expressionDisplay.optionId)?.label || "Expression values";
}

function getLegendLabelLines(label: string): string[] {
  const match = label.match(/^(.+?)\s*(\(.+\))$/);
  return match ? [match[1].trim(), match[2].trim()] : [label];
}

function measureLegendLabelWidth(labelLines: string[]): number {
  if (typeof document === "undefined") return Math.max(...labelLines.map((line) => line.length * 6.5));
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return Math.max(...labelLines.map((line) => line.length * 6.5));
  context.font = LEGEND_LABEL_FONT;
  return Math.max(...labelLines.map((line) => context.measureText(line).width));
}

function getColorLegendReservedWidth(): number {
  const labelWidth = measureLegendLabelWidth(getLegendLabelLines(getHeatmapLegendLabel()));
  const legendContentWidth = Math.max(LEGEND_WIDTH + LEGEND_AXIS_SPACE, labelWidth);
  return Math.ceil(LEGEND_GAP + legendContentWidth + LEGEND_RIGHT_PADDING);
}

function getLegendTickValues(minValue: number, maxValue: number): number[] {
  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) return [];
  if (minValue === maxValue) return [minValue];
  const step = (maxValue - minValue) / 4;
  return [minValue, minValue + step, minValue + step * 2, minValue + step * 3, maxValue];
}

function renderColorLegend(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  margin: { top: number; right: number; bottom: number; left: number },
  colorScale: d3.ScaleSequential<string>,
  legendWidth: number,
  gradientId: string,
) {
  const svgWidth = +svg.attr("width");
  const svgHeight = +svg.attr("height");

  const plotHeight = svgHeight - margin.top - margin.bottom;
  const legendHeight = plotHeight / 2;
  const legendTop = margin.top + (plotHeight - legendHeight) / 2;

  // Create gradient definition
  const defs = svg.append("defs");
  const gradient = defs
    .append("linearGradient")
    .attr("id", gradientId)
    .attr("x1", "0%")
    .attr("y1", "100%") // from bottom to top
    .attr("x2", "0%")
    .attr("y2", "0%");

  // Stops from 0 to 1 with small step
  const domain = colorScale.domain();
  gradient
    .selectAll("stop")
    .data(d3.range(0, 1.01, 0.05))
    .enter()
    .append("stop")
    .attr("offset", (d) => `${d * 100}%`)
    .attr("stop-color", (d) =>
      colorScale(domain[0] + d * (domain[1] - domain[0])),
    );

  // Create legend group positioned at right side
  const legend = svg
    .append("g")
    .attr("transform", `translate(0, ${margin.top})`);

  // Add gradient rectangle
  legend
    .append("rect")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .style("fill", `url(#${gradientId})`);

  // Scale for the legend axis according to colorScale domain
  const legendScale = d3
    .scaleLinear()
    .domain([domain[0], domain[1]])
    .range([legendHeight, 0]);

  const legendAxis = d3
    .axisRight(legendScale)
    .tickValues(getLegendTickValues(domain[0], domain[1]))
    .tickSize(4);

  // Add axis group
  legend
    .append("g")
    .attr("transform", `translate(${legendWidth}, 0)`)
    .call(legendAxis)
    .call((g) => g.select(".domain").remove());

  const legendLabelLines = getLegendLabelLines(getHeatmapLegendLabel());
  const legendLabel = legend
    .append("text")
    .attr("x", legendWidth / 2)
    .attr("y", legendLabelLines.length > 1 ? -24 : -10)
    .attr("text-anchor", "middle")
    .style("font", LEGEND_LABEL_FONT);

  legendLabel
    .selectAll("tspan")
    .data(legendLabelLines)
    .enter()
    .append("tspan")
    .attr("x", legendWidth / 2)
    .attr("dy", (_line, index) => (index === 0 ? 0 : LEGEND_LABEL_LINE_HEIGHT))
    .text((line) => line);

  const legendBBox = legend.node()?.getBBox();
  const legendMinX = legendBBox ? legendBBox.x : 0;
  const plotRight = svgWidth - margin.right;
  legend.attr(
    "transform",
    `translate(${plotRight + LEGEND_GAP - legendMinX}, ${legendTop})`,
  );
}

function getSideColorAttributeValues(dataSource: Record<string, unknown>[], colName: string, colType: string): SideColorValue[] {
  return dataSource.map((entry) => {
    const val = entry[colName];
    if (colType === "array") {
      return getListMetadataKey(val);
    }
    if (colType === "boolean") {
      if (typeof val === "boolean") return val;
      return null;
    }
    if (colType === "double precision" || colType === "bigint") {
      return typeof val === "number" ? val : null;
    }
    // Fallback for other types
    return String(val ?? "");
  });
}

function getSideColorDisplayValue(value: SideColorValue, colType: string): string {
  if (colType === "array") {
    const terms = normalizeMetadataList(value)
      .map((term) => term.trimEnd())
      .filter((term) => term.trim().length > 0);
    return terms.length > 0 ? terms.join("<br>") : "None";
  }

  const normalizedValue = String(value ?? "").trimEnd();
  return normalizedValue.trim().length > 0 ? normalizedValue : "";
}

function getSideColorTooltipValue(value: SideColorValue, colType: string): string | null {
  const tooltipValue = getSideColorDisplayValue(value, colType);
  return tooltipValue.trim().length > 0 ? tooltipValue : null;
}

function getSideColorDataValue(value: SideColorValue, colType: string): string {
  return colType === "array" ? getListMetadataKey(value) : String(value ?? "");
}

function cssAttributeValue(value: string): string {
  return value.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
}

function flashMatchingSideColorRects(columnName: string, dataValue: string, sourceNode: SVGRectElement) {
  const selector =
    `rect[data-color-col="${cssAttributeValue(columnName)}"]` +
    `[data-color-val="${cssAttributeValue(dataValue)}"]`;
  const nodes = [...document.querySelectorAll<SVGRectElement>(selector)]
    .filter((node) => node !== sourceNode);

  nodes.forEach((node) => {
    const sel = d3.select(node);
    const originalStroke = node.getAttribute("stroke") ?? "none";
    const originalStrokeWidth = node.getAttribute("stroke-width") ?? "0";

    sel.interrupt("metadata-flash");
    sel
      .transition("metadata-flash")
      .duration(160)
      .attr("stroke", "#111827")
      .attr("stroke-width", 2.5)
      .transition()
      .duration(160)
      .attr("stroke", originalStroke === "none" ? null : originalStroke)
      .attr("stroke-width", originalStrokeWidth)
      .transition()
      .duration(160)
      .attr("stroke", "#111827")
      .attr("stroke-width", 2.5)
      .transition()
      .duration(160)
      .attr("stroke", originalStroke === "none" ? null : originalStroke)
      .attr("stroke-width", originalStrokeWidth)
      .transition()
      .duration(160)
      .attr("stroke", "#111827")
      .attr("stroke-width", 2.5)
      .transition()
      .duration(200)
      .attr("stroke", originalStroke === "none" ? null : originalStroke)
      .attr("stroke-width", originalStrokeWidth);
  });
}

// Generalized function for both row and column side color rendering
async function renderSideColors({
                                  svg,
                                  margin,
                                  dimensionSize,
                                  labels,
                                  attributeValues,
                                  colorDomainValues,
                                  column_name,
                                  colType,
                                  xOffset = 0,
                                  yOffset = 0,
                                  orientation = "row", // 'row' or 'col'
                                  labelWidth = 40,
                                }) {
  if (
    (orientation === "row" && !visualizationStore.rowSideColors) ||
    (orientation === "col" && !visualizationStore.colSideColors)
  )
    return;

  try {
    const isNumericSideColor = colType === "double precision" || colType === "bigint";
    const useSharedMapping = !(orientation === "col" && isNumericSideColor);
    const mappingValues = colorDomainValues ?? attributeValues;

    // Categorical/list side colors share a registry for stable colors across plots.
    // Numeric column side colors intentionally use a local domain per heatmap and
    // per metadata column, but the domain is still based on the full loaded
    // heatmap, not the current zoom window.
    if (sharedColorRegistry && useSharedMapping) {
      sharedColorRegistry.registerValues(column_name, colType, mappingValues);
    }
    const sharedColorMap = sharedColorRegistry && useSharedMapping
      ? sharedColorRegistry.getMapping(column_name)
      : null;
    const colorMap = sharedColorMap ?? createVisibleColorMapping(column_name, colType, mappingValues);

    // Dimension calculations
    const colorSize = dimensionSize * 0.75;

    const svgWidth = +svg.attr("width");
    const svgHeight = +svg.attr("height");

    // Scale for band positioning
    let scale;
    if (orientation === "row") {
      scale = d3
        .scaleBand()
        .domain(labels)
        .range([0, svgHeight - margin.top - margin.bottom])
        .padding(0);
    } else {
      scale = d3
        .scaleBand()
        .domain(labels)
        .range([0, svgWidth - margin.left - margin.right])
        .padding(0);
    }

    const containerGroup = svg
      .append("g")
      .attr("transform", `translate(${xOffset}, ${yOffset})`);

    // Draw rectangles
    const rects = containerGroup
      .selectAll("rect")
      .data(attributeValues)
      .join("rect");

    if (orientation === "row") {
      rects
        .attr("x", 0)
        .attr("y", (d, i) => scale(labels[i]))
        .attr("width", colorSize)
        .attr("height", scale.bandwidth())
        .attr("data-color-col", column_name)
        .attr("data-color-val", (d) => getSideColorDataValue(d, colType))
        .attr("fill", (d) => {
          if (
            (colType === "double precision" || colType === "bigint") &&
            d !== null &&
            d !== undefined
          ) {
            return typeof colorMap.getColor === "function" ? colorMap.getColor(d) ?? "#eeeeee" : "#eeeeee";
          }
          return colorMap[getSideColorDataValue(d, colType)] ?? "#eeeeee";
        });
    } else {
      rects
        .attr("x", (d, i) => scale(labels[i]))
        .attr("y", 0)
        .attr("width", scale.bandwidth())
        .attr("height", colorSize)
        .attr("data-color-col", column_name)
        .attr("data-color-val", (d) => getSideColorDataValue(d, colType))
        .attr("fill", (d) => {
          if (
            (colType === "double precision" || colType === "bigint") &&
            d !== null &&
            d !== undefined
          ) {
            return typeof colorMap.getColor === "function" ? colorMap.getColor(d) ?? "#eeeeee" : "#eeeeee";
          }
          return colorMap[getSideColorDataValue(d, colType)] ?? "#eeeeee";
        });
    }

    // Tooltip, unified for both
    const containerNode = svg.node()?.parentNode as HTMLElement | null;
    if (!containerNode) return;

    let tooltip = d3.select(containerNode).select<HTMLDivElement>(`#${sideColorTooltipId}`);

    if (tooltip.empty()) {
      tooltip = d3
        .select(containerNode)
        .append("div")
        .attr("id", sideColorTooltipId)
        .style("position", "absolute")
        .style("z-index", "50")
        .style("visibility", "hidden")
        .style("background-color", "#f9fafb")
        .style("color", "#374151")
        .style("font-size", "0.75rem")
        .style("border-radius", "0.375rem")
        .style("padding", "0.25rem 0.5rem")
        .style("display", "inline-block")
        .style("width", "max-content")
        .style("min-width", "0")
        .style("max-width", "20rem")
        .style("border", "1px solid #d1d5db")
        .style("box-shadow", "0 1px 2px rgba(0,0,0,0.05)")
        .style("pointer-events", "none");
    }

    rects
      .on("mouseover", function (this: SVGRectElement, event, d) {
        d3.select(this).attr("stroke", "white").style("stroke-width", 2);

        let tooltipValue: string | null = null;

        if (
          (colType === "double precision" || colType === "bigint") &&
          d !== null &&
          d !== undefined &&
          colorMap.bins
        ) {
          // For numeric columns with buckets, show the actual value (not the bucket range)
          const formattedValue = Number.isInteger(d) ? d.toLocaleString() : d.toFixed(2);
          const normalizedValue = String(formattedValue).trimEnd();
          tooltipValue = normalizedValue.trim().length > 0 ? normalizedValue : null;
        } else {
          tooltipValue = getSideColorTooltipValue(d, colType);
        }

        if (!tooltipValue) {
          tooltip.style("visibility", "hidden");
          return;
        }

        tooltip.html(tooltipValue);
        tooltip.style("visibility", "visible");
      })
      .on("mousemove", function (event) {
        if (!svg.node().parentNode) return;
        const containerRect = svg.node().parentNode.getBoundingClientRect();
        const tooltipNode = tooltip.node();
        if (!tooltipNode) return;
        const tooltipRect = tooltipNode.getBoundingClientRect();

        const offsetX = 10;
        const offsetY = 10;
        let xPos = event.clientX - containerRect.left + offsetX;
        let yPos = event.clientY - containerRect.top + offsetY;

        if (orientation === "row") {
          if (xPos + tooltipRect.width > containerRect.width) {
            xPos =
              event.clientX - containerRect.left - tooltipRect.width - offsetX;
          }
          if (yPos + tooltipRect.height > containerRect.height) {
            yPos =
              event.clientY - containerRect.top - tooltipRect.height - offsetY;
          }
        } else {
          yPos = event.clientY - containerRect.top + colorSize + offsetY;
          if (xPos + tooltipRect.width > containerRect.width) {
            xPos =
              event.clientX - containerRect.left - tooltipRect.width - offsetX;
          }
          if (yPos + tooltipRect.height > containerRect.height) {
            yPos =
              event.clientY - containerRect.top - tooltipRect.height - offsetY;
          }
        }

        xPos = Math.max(0, xPos);
        yPos = Math.max(0, yPos);
        tooltip.style("left", xPos + "px").style("top", yPos + "px");
      })
      .on("mouseout", function (this: SVGRectElement) {
        d3.select(this).attr("stroke", "none");
        tooltip.style("visibility", "hidden");
      })
      .on("contextmenu", function (this: SVGRectElement, event, d) {
        event.preventDefault();
        event.stopPropagation();
        tooltip.style("visibility", "hidden");
        flashMatchingSideColorRects(column_name, getSideColorDataValue(d, colType), this);
      })
      .on("click", function (_event, d) {
        if (
          (colType === "double precision" || colType === "bigint") &&
          d !== null &&
          d !== undefined &&
          colorMap.bins
        ) {
          // Find bin for clicked value
          const bin = colorMap.bins.find(
            (b) => d >= b.bucket_lower && d <= b.bucket_upper,
          );
          if (bin) {
            filtersStore.setFilter(column_name, {
              value: [bin.bucket_lower, bin.bucket_upper] as unknown as string,
            });
          } else {
            // Fallback if no bin found, set raw value
            filtersStore.setFilter(column_name, {value: d as unknown as string});
          }
        } else {
          // For non-numeric or other types, keep existing behavior
          const filterValue = colType === "array" ? normalizeMetadataList(d).join("|") : d;
          if (filterValue !== undefined && filterValue !== null && filterValue !== "") {
            filtersStore.setFilter(column_name, {
              value: filterValue as string,
              match_mode: "or",
              exact: true,
            });
          }
        }
      });

    // Label group
    const labelGroup = svg
      .append("g")
      .attr(
        "transform",
        orientation === "row"
          ? `translate(${xOffset}, ${yOffset + scale.bandwidth() * scale.domain().length + 5})`
          : `translate(${margin.left - labelWidth}, ${yOffset + colorSize / 2})`,
      );

    labelGroup
      .append("text")
      .text(getDisplayName(column_name))
      .attr("x", orientation === "row" ? 0 : labelWidth - 5)
      .attr("y", orientation === "row" ? colorSize / 2 : 0)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("transform", orientation === "row" ? "rotate(270)" : "rotate(0)")
      .style("font-size", "0.75rem");
  } catch (err) {
    console.error(`Error rendering ${orientation} side colors:`, err);
  }
}

function resetHeatmap() {
  if (!heatmapContainer.value) return;
  d3.select(heatmapContainer.value).selectAll("*").remove();
}

function clearScheduledRender() {
  if (renderFrame !== null) {
    cancelAnimationFrame(renderFrame);
    renderFrame = null;
  }
  if (renderTimer !== null) {
    clearTimeout(renderTimer);
    renderTimer = null;
  }
}

function scheduleHeatmapRender(delay = 0, retries = MAX_RENDER_RETRIES) {
  if (isUnmounting) return;

  const runRender = async () => {
    renderFrame = null;
    const didRender = await renderHeatmap();
    if (!didRender && retries > 0 && !isUnmounting) {
      scheduleHeatmapRender(0, retries - 1);
    }
  };

  if (delay > 0) {
    clearScheduledRender();
    renderTimer = setTimeout(() => {
      renderTimer = null;
      renderFrame = requestAnimationFrame(() => {
        void runRender();
      });
    }, delay);
    return;
  }

  if (renderFrame !== null) return;
  if (renderTimer !== null) {
    clearTimeout(renderTimer);
    renderTimer = null;
  }

  renderFrame = requestAnimationFrame(() => {
    void runRender();
  });
}

function getHeatmapLayout(width: number, height: number) {
  let totalColSideColorHeight = 0;
  let totalRowSideColorWidth = 0;

  const margin = {top: 50, right: 20, bottom: 20, left: 20};

  if (visualizationStore.rowLabel) {
    margin.left += 100;
  }

  if (visualizationStore.colLabel) {
    margin.bottom += 70;
  }

  if (visualizationStore.rowSideColors.length > 0) {
    totalRowSideColorWidth =
      visualizationStore.rowSideColors.length * (SIDE_COLOR_WIDTH + SIDE_COLOR_GAP);
    margin.left += totalRowSideColorWidth;
    margin.bottom = Math.max(100, margin.bottom);
  }

  if (visualizationStore.colSideColors.length > 0) {
    totalColSideColorHeight =
      visualizationStore.colSideColors.length * (SIDE_COLOR_WIDTH + SIDE_COLOR_GAP);
    margin.top += totalColSideColorHeight;
    margin.left = Math.max(100, margin.left);
  }

  if (visualizationStore.legend) {
    margin.right = getColorLegendReservedWidth();
  }

  const svgW = width - margin.left - margin.right;
  const svgH = height - margin.top - margin.bottom;

  return {
    margin,
    svgW,
    svgH,
    totalColSideColorHeight,
    totalRowSideColorWidth,
  };
}

async function renderHeatmap(): Promise<boolean> {
  if (isRendering) {
    renderPending = true;
    return true;
  }
  isRendering = true;
  renderPending = false;
  try {
    if (
      !heatmapContainer.value ||
      !sortedRows.value.length ||
      !visibleColumns.value.length
    ) {
      return false;
    }

    const container = heatmapContainer.value;
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width <= 0 || height <= 0) {
      return false;
    }

    const {
      margin,
      svgW,
      svgH,
      totalColSideColorHeight,
      totalRowSideColorWidth,
    } = getHeatmapLayout(width, height);

    // In the multi-heatmap gallery the card width changes while siblings mount.
    // Skip drawing until the drawable SVG area is actually positive.
    if (svgW <= 0 || svgH <= 0) {
      return false;
    }

    resetHeatmap();
  
    const svg = d3
      .select(container)
      .append("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("data-zoomed", zoomWindow.value !== null ? "true" : "false")
      .attr("data-pan-mode", panMode.value ? "true" : "false")
      .attr("data-zoom-mode", zoomMode.value ? "true" : "false")
      .style("touch-action", "none");

  svg
    .append("text")
    .attr("x", width / 2) // center horizontally
    .attr("y", 50 / 2) // position above the plot area, adjust as needed
    .attr("text-anchor", "middle") // center the text
    .attr("font-size", "16px")
    .attr("font-style", "italic")
    .text(beautifyLabel(localTableName.value));

    const allData = sortedRows.value;
    const allHeatmapCols = visibleColumns.value;
    const activeWindow = getCurrentZoomWindow(allData.length, allHeatmapCols.length);
    const data = allData.slice(activeWindow.yStart, activeWindow.yEnd);
    const heatmapCols = allHeatmapCols.slice(activeWindow.xStart, activeWindow.xEnd);
    const currentIdColumn = idColumn.value;
  
  // Determine if we should use deferred event binding for large datasets
    const totalCells = data.length * heatmapCols.length;
    const isLargeDataset = totalCells > 10000; // Defer events for > 10k cells

  //X/Y Labels
    const yLabels = data.map((row) =>
      row[currentIdColumn] !== undefined ? String(row[currentIdColumn]) : "",
    );
    const xLabels = heatmapCols;

  //console.log(xLabels);
  //console.log(yLabels);

    const x = d3.scaleBand().domain(xLabels).range([0, svgW]).padding(0);
    const y = d3.scaleBand().domain(yLabels).range([0, svgH]).padding(0);

  //Colorscaling
    const allCellVals = allData
      .flatMap((row: RowType) =>
        allHeatmapCols.map((c) => {
          const val = row[c];
          return val === "[BLOB]" ? NaN : +val;
        }),
      )
      .filter((v) => !isNaN(v));

    const colorScale = d3
      .scaleSequential(
        COLORSCALES[visualizationStore.colorScale] as (t: number) => string,
      )
      .domain([d3.min(allCellVals) ?? 0, d3.max(allCellVals) ?? 1]);

  // Calculate label thinning for readability
  // Approximate height/width per label to determine skip interval
    const minLabelSpacing = 12; // minimum pixels between labels
    const cellWidth = x.bandwidth();
    const cellHeight = y.bandwidth();
  
  // Calculate skip intervals (show every nth label)
    const xLabelSkip = cellWidth < minLabelSpacing ? Math.ceil(minLabelSpacing / cellWidth) : 1;
    const yLabelSkip = cellHeight < minLabelSpacing ? Math.ceil(minLabelSpacing / cellHeight) : 1;

  // Conditionally render X-axis with label thinning
  if (visualizationStore.colLabel) {
    const xAxisGroup = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top + svgH})`)
      .call(d3.axisBottom(x).tickSize(0));
    
    // Apply label thinning - hide labels that would overlap
    xAxisGroup.selectAll("text")
      .attr("transform", "translate(-12,10) rotate(-90)")
      .style("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .style("font-size", "0.75rem")
      .style("visibility", (_d, i) => (i % xLabelSkip === 0) ? "visible" : "hidden");
  }

  // Conditionally render Y-axis (row labels) with label thinning
  if (visualizationStore.rowLabel) {
    const maxLabelWidth = 100; // Max width for labels
    
    const yAxisGroup = svg
      .append("g")
      .attr(
        "transform",
        `translate(${margin.left - totalRowSideColorWidth},${margin.top})`,
      )
      .call(d3.axisLeft(y).tickSize(0));
    
    const yAxisTexts = yAxisGroup.selectAll("text")
      .style("font-size", "10px")
      // Apply label thinning - hide labels that would overlap
      .style("visibility", (_d, i) => (i % yLabelSkip === 0) ? "visible" : "hidden");

    // Truncate long labels and add ellipsis (only for visible labels)
    yAxisTexts.each(function(_d, i) {
      if (i % yLabelSkip !== 0) return; // Skip hidden labels
      
      const textElement = d3.select(this);
      const originalText = textElement.text();
      const textLength = (this as SVGTextElement).getComputedTextLength();
      
      if (textLength > maxLabelWidth) {
        let truncatedText = originalText;
        
        // Binary search for optimal length
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
        const originalText = d3.select(this).text().replace('...', '');
        const fullText = d3.select(this).select("title").text() || originalText;
        
        // Only show tooltip if text is truncated
        if (fullText !== originalText || d3.select(this).text().includes('...')) {
          rowLabelTooltip.html(fullText);
          rowLabelTooltip.style("visibility", "visible");
        }
      })
      .on("mousemove", function(event) {
        if (!heatmapContainer.value) return;
        const containerRect = heatmapContainer.value.getBoundingClientRect();
        
        const xPos = event.clientX - containerRect.left + 10;
        const yPos = event.clientY - containerRect.top - 10;
        
        rowLabelTooltip
          .style("left", xPos + "px")
          .style("top", yPos + "px");
      })
      .on("mouseout", function() {
        rowLabelTooltip.style("visibility", "hidden");
      });
  }


  // Create a single tooltip div once, reuse in events
    const tooltip = d3
      .select(container)
      .append("div")
      .attr("class", "tooltip")
      .style("position", "absolute")
      .style("z-index", "50")
      .style("visibility", "hidden")
      .style("background-color", "#f9fafb") // bg-gray-50
      .style("color", "#374151") // text-gray-700
      .style("font-size", "0.75rem") // text-xs
      .style("border-radius", "0.375rem") // rounded-md
      .style("padding", "0.25rem 0.5rem") // px-2 py-1
      .style("min-width", "8rem")
      .style("white-space", "normal")
      .style("word-wrap", "break-word")
      .style("max-width", "24rem")
      .style("border", "1px solid #d1d5db")
      .style("box-shadow", "0 1px 2px rgba(0,0,0,0.05)")
      .style("pointer-events", "none")
      .style("user-select", "text");

  let hideTimeout; // global merken

  // Pre-compute cell data for better performance
  const cellData = data.flatMap((row, rowIndex) =>
    heatmapCols.map((col) => ({
      rowIndex,
      col,
      value: row[col],
    }))
  );
  
  const cellGroup = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`)
    .style("cursor", panMode.value ? "grab" : zoomMode.value ? "crosshair" : "default");

  const plotHitbox = cellGroup
    .append("rect")
    .attr("class", "heatmap-plot-hitbox")
    .attr("width", svgW)
    .attr("height", svgH)
    .attr("fill", "transparent")
    .attr("pointer-events", "all")
    .style("touch-action", "none");

  const zoomSelectionRect = cellGroup
    .append("rect")
    .attr("class", "heatmap-zoom-selection")
    .attr("fill", "rgba(166, 197, 80, 0.24)")
    .attr("stroke", "#ffffff")
    .attr("stroke-width", 2)
    .attr("pointer-events", "none")
    .style("filter", "drop-shadow(0 0 2px rgba(98, 128, 16, 0.45))")
    .style("display", "none");

  const clampPointer = (clientX: number, clientY: number): [number, number] => {
    const containerRect = container.getBoundingClientRect();
    const rawX = clientX - containerRect.left - margin.left;
    const rawY = clientY - containerRect.top - margin.top;
    return [
      Math.max(0, Math.min(svgW, rawX)),
      Math.max(0, Math.min(svgH, rawY)),
    ];
  };

  // Shared drag controller. Returned by beginPlotDrag and driven by either
  // mouse or touch listeners — there is no event synthesis between the two.
  type DragController = {
    onMove: (clientX: number, clientY: number) => void;
    onEnd: (clientX: number, clientY: number) => void;
    cancel: () => void;
  };

  const beginPlotDrag = (startClientX: number, startClientY: number): DragController | null => {
    if (!zoomMode.value && !panMode.value) return null;
    const startZoomed = zoomWindow.value !== null;
    if (panMode.value && !startZoomed) return null;

    const start = clampPointer(startClientX, startClientY);
    const startWindow = {...activeWindow};
    tooltip.style("visibility", "hidden");

    let pendingPanWindow: HeatmapZoomWindow | null = null;
    let panWindow = {...startWindow};
    let lastPanPoint = start;
    let accumulatedPanDx = 0;
    let accumulatedPanDy = 0;
    let livePanFrame: number | null = null;
    let didMove = false;
    let finished = false;

    const zoomWindowsEqual = (left: HeatmapZoomWindow, right: HeatmapZoomWindow) => (
      left.xStart === right.xStart &&
      left.xEnd === right.xEnd &&
      left.yStart === right.yStart &&
      left.yEnd === right.yEnd
    );

    const scheduleLivePan = () => {
      if (livePanFrame !== null) return;
      livePanFrame = requestAnimationFrame(() => {
        livePanFrame = null;
        if (pendingPanWindow) {
          setZoomWindow(pendingPanWindow);
        }
      });
    };

    const teardown = () => {
      if (livePanFrame !== null) {
        cancelAnimationFrame(livePanFrame);
        livePanFrame = null;
      }
      cellGroup.style("cursor", panMode.value ? "grab" : zoomMode.value ? "crosshair" : "default");
      zoomSelectionRect.style("display", "none");
    };

    const onMove = (clientX: number, clientY: number) => {
      if (finished) return;
      const current = clampPointer(clientX, clientY);
      const dx = current[0] - start[0];
      const dy = current[1] - start[1];
      didMove = didMove || Math.abs(dx) > 3 || Math.abs(dy) > 3;

      if (panMode.value && startZoomed) {
        cellGroup.style("cursor", "grabbing");
        accumulatedPanDx += current[0] - lastPanPoint[0];
        accumulatedPanDy += current[1] - lastPanPoint[1];
        lastPanPoint = current;

        const colWidth = Math.max(1, x.bandwidth());
        const rowHeight = Math.max(1, y.bandwidth());
        const colShift = Math.trunc(-accumulatedPanDx / colWidth);
        const rowShift = Math.trunc(-accumulatedPanDy / rowHeight);
        if (colShift !== 0 || rowShift !== 0) {
          accumulatedPanDx += colShift * colWidth;
          accumulatedPanDy += rowShift * rowHeight;

          const nextPanWindow = clampZoomWindow({
            xStart: panWindow.xStart + colShift,
            xEnd: panWindow.xEnd + colShift,
            yStart: panWindow.yStart + rowShift,
            yEnd: panWindow.yEnd + rowShift,
          }, allData.length, allHeatmapCols.length);
          if (!zoomWindowsEqual(nextPanWindow, panWindow)) {
            panWindow = nextPanWindow;
            pendingPanWindow = nextPanWindow;
            scheduleLivePan();
          }
        }
        return;
      }

      const x0 = Math.min(start[0], current[0]);
      const y0 = Math.min(start[1], current[1]);
      const x1 = Math.max(start[0], current[0]);
      const y1 = Math.max(start[1], current[1]);
      zoomSelectionRect
        .raise()
        .style("display", null)
        .attr("x", x0)
        .attr("y", y0)
        .attr("width", x1 - x0)
        .attr("height", y1 - y0);
    };

    const onEnd = (clientX: number, clientY: number) => {
      if (finished) return;
      finished = true;
      teardown();
      if (panMode.value && startZoomed) {
        if (didMove && pendingPanWindow) setZoomWindow(pendingPanWindow);
        return;
      }
      if (!didMove) return;

      const end = clampPointer(clientX, clientY);
      const x0 = Math.min(start[0], end[0]);
      const y0 = Math.min(start[1], end[1]);
      const x1 = Math.max(start[0], end[0]);
      const y1 = Math.max(start[1], end[1]);
      if (x1 - x0 < 8 || y1 - y0 < 8) return;

      const nextWindow = {
        xStart: activeWindow.xStart + Math.floor(x0 / Math.max(1, x.bandwidth())),
        xEnd: activeWindow.xStart + Math.ceil(x1 / Math.max(1, x.bandwidth())),
        yStart: activeWindow.yStart + Math.floor(y0 / Math.max(1, y.bandwidth())),
        yEnd: activeWindow.yStart + Math.ceil(y1 / Math.max(1, y.bandwidth())),
      };
      setZoomWindow(nextWindow);
    };

    const cancel = () => {
      if (finished) return;
      finished = true;
      teardown();
    };

    return {onMove, onEnd, cancel};
  };

  const handlePlotPointerDown = (event: PointerEvent) => {
    // For mouse: only react to the primary (left) button. Touch and pen
    // pointers always report button 0, so they fall through.
    if (event.pointerType === "mouse" && event.button !== 0) return;
    if (event.altKey || event.ctrlKey || event.metaKey) return;

    const controller = beginPlotDrag(event.clientX, event.clientY);
    if (!controller) return;

    event.preventDefault();
    event.stopPropagation();

    const pointerId = event.pointerId;

    // CRITICAL: capture the pointer on the persistent container <div>.
    // The SVG (and the touched cell) gets rebuilt by setZoomWindow during a
    // pan, which would otherwise cause the browser to fire `touchcancel` and
    // kill the gesture after a single increment. Capturing on a node that
    // survives re-renders keeps pointermove/pointerup flowing to us.
    try {
      container.setPointerCapture(pointerId);
    } catch {
      // setPointerCapture can throw if the pointer is already released or
      // the element isn't connected; we degrade gracefully by relying on
      // bubbling.
    }

    let cleanedUp = false;
    const cleanup = () => {
      if (cleanedUp) return;
      cleanedUp = true;
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerup", onPointerUp);
      container.removeEventListener("pointercancel", onPointerCancel);
      container.removeEventListener("lostpointercapture", onLostCapture);
      try {
        if (container.hasPointerCapture?.(pointerId)) {
          container.releasePointerCapture(pointerId);
        }
      } catch {
        // ignore
      }
    };

    const onPointerMove = (moveEvent: PointerEvent) => {
      if (moveEvent.pointerId !== pointerId) return;
      // preventDefault on the captured pointermove is what keeps the browser
      // from interpreting the gesture as a native scroll on touch devices.
      moveEvent.preventDefault();
      controller.onMove(moveEvent.clientX, moveEvent.clientY);
    };

    const onPointerUp = (upEvent: PointerEvent) => {
      if (upEvent.pointerId !== pointerId) return;
      cleanup();
      controller.onEnd(upEvent.clientX, upEvent.clientY);
    };

    const onPointerCancel = (cancelEvent: PointerEvent) => {
      if (cancelEvent.pointerId !== pointerId) return;
      cleanup();
      controller.cancel();
    };

    // If capture is lost for any reason (e.g. the OS taking over the touch),
    // tear down cleanly so the next gesture starts with a fresh slate.
    const onLostCapture = (lostEvent: PointerEvent) => {
      if (lostEvent.pointerId !== pointerId) return;
      cleanup();
      controller.cancel();
    };

    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerUp);
    container.addEventListener("pointercancel", onPointerCancel);
    container.addEventListener("lostpointercapture", onLostCapture);
  };

  // Bind to cellGroup so pointerdown bubbles up from either the hitbox or any
  // cell rect. One listener is enough — we no longer attach separate mouse and
  // touch listeners (Pointer Events unify them).
  cellGroup.on("pointerdown.zoom-pan", function (event) {
    handlePlotPointerDown(event as PointerEvent);
  });
  
  // Render cells - for large datasets, skip initial event binding
  const rects = cellGroup
    .selectAll<SVGRectElement, (typeof cellData)[number]>("rect.heatmap-cell")
    .data(cellData)
    .join("rect")
    .attr("class", "heatmap-cell")
    .attr("x", (d) => x(d.col) ?? 0)
    .attr("y", (d) => y(yLabels[d.rowIndex]) ?? 0)
    .attr("width", x.bandwidth())
    .attr("height", y.bandwidth())
    .attr("fill", (d) => {
      if (d.value === "[BLOB]") return "#ccc";
      const n = +d.value;
      return isNaN(n) ? "#eee" : colorScale(n);
    })
    .attr("stroke", "none")
    .style("touch-action", "none");
  
  // Add event handlers (deferred for large datasets to improve initial render)
  const addCellEventHandlers = () => {
    rects
    .on("mouseover", function (event, d) {
      if (zoomMode.value || panMode.value) return;
      d3.select(this).attr("stroke", "white").style("stroke-width", 2);

      const row = data[d.rowIndex];
      
      // Get metadata columns excluding heatmap columns and id column
      const allMetaCols = Object.keys(row).filter(
        (c) => !heatmapCols.includes(c) && c !== currentIdColumn
      );
      
      // Filter based on user's tooltip field preferences
      // null = uninitialized / show all; [] = user deselected all / show none
      let visibleMetaCols = allMetaCols;
      if (visualizationStore.tooltipFields !== null) {
        visibleMetaCols = allMetaCols.filter(c => 
          visualizationStore.tooltipFields!.includes(c)
        );
      }
      
      // Generate metadata HTML with display names
      const metaHtml = visibleMetaCols
        .map((c) => {
          let value = row[c] ?? "";
          
          // Handle sequences
          if (sequenceFields.includes(c)) {
            if (!visualizationStore.showSequencesInTooltip) {
              return null; // Skip sequences if disabled
            }
            
            const seq = String(value);
            if (seq.length > visualizationStore.sequencePreviewLength) {
              value = seq.substring(0, visualizationStore.sequencePreviewLength) + "... (truncated)";
            }
          }
          
          // Handle arrays - truncate long lists
          if (Array.isArray(value)) {
            if (value.length > 5) {
              value = value.slice(0, 5).join(", ") + ` ... (+${value.length - 5} more)`;
            } else {
              value = value.join(", ");
            }
          }
          
          return `<strong>${getDisplayName(c)}:</strong> ${value}`;
        })
        .filter(Boolean)
        .join("<br>");

      tooltip.html(`
      <b>${getDisplayName(currentIdColumn)}:</b> ${row[currentIdColumn]}<br>
      <b>Column:</b> ${d.col}<br>
      <b>Value:</b> ${d.value}<br>
      ${metaHtml ? `<hr style="margin:4px 0; border-color:#888"/><div>${metaHtml}</div>` : ''}
      <hr style="margin:4px 0; border-color:#888"/>
      <div style="text-align:center; font-size:0.7rem; color:#6b7280;">Right-click for full details</div>
    `);

      tooltip.style("visibility", "visible");

      if (hideTimeout) clearTimeout(hideTimeout); // falls noch aktiv
    })
    .on("mousemove", function (event) {
      if (zoomMode.value || panMode.value) return;
      if (!heatmapContainer.value) return;
      const containerRect = heatmapContainer.value.getBoundingClientRect();
      const tooltipNode = tooltip.node();
      if (!tooltipNode) return;
      const tooltipRect = tooltipNode.getBoundingClientRect();

      const offsetX = 12; // Abstand von der Maus nach rechts

      // Vertikal: Maus-Mitte
      let yPos = event.clientY - containerRect.top - tooltipRect.height / 2;

      // Horizontal: rechts neben der Maus
      let xPos = event.clientX - containerRect.left + offsetX;

      // Wenn rechts kein Platz → nach links spiegeln
      if (xPos + tooltipRect.width > containerRect.width) {
        xPos = event.clientX - containerRect.left - tooltipRect.width - offsetX;
      }

      // Begrenzung, damit Tooltip nicht außerhalb vom Container hängt
      xPos = Math.max(0, xPos);
      yPos = Math.max(0, Math.min(yPos, containerRect.height - tooltipRect.height));

      tooltip
        .style("left", xPos + "px")
        .style("top", yPos + "px");
    })

    .on("mouseout", function () {
      if (zoomMode.value || panMode.value) return;
      d3.select(this).attr("stroke", "none");

      // Tooltip nach 300ms schließen (falls Maus nicht in Tooltip wandert)
      hideTimeout = setTimeout(() => {
        tooltip.style("visibility", "hidden");
      }, 800);
    })
    .on("contextmenu", function (event, d) {
      event.preventDefault(); // Prevent browser context menu
      
      const row = data[d.rowIndex];
      
      // Open the tooltip modal with full data
      selectedRowData.value = row;
      selectedColumnValue.value = d.col;
      selectedCellValue.value = typeof d.value === "number" || typeof d.value === "string" ? d.value : String(d.value ?? "");
      showTooltipModal.value = true;
      
      // Hide the hover tooltip
      tooltip.style("visibility", "hidden");
    });
  }; // End of addCellEventHandlers function
  
  // Defer event handler attachment for large datasets
  if (isLargeDataset) {
    // Use requestAnimationFrame to defer event binding
    requestAnimationFrame(() => {
      addCellEventHandlers();
    });
  } else {
    addCellEventHandlers();
  }

  // Add long-press support for touch devices
  let longPressTimer: number | null = null;
  
  // Use passive event listeners for touch events to improve scroll performance
  const rectElements = cellGroup.selectAll("rect").nodes() as SVGRectElement[];
  rectElements.forEach((rect) => {
    if (!rect) return;
    
    rect.addEventListener("touchstart", function (event: TouchEvent) {
      if (zoomMode.value || panMode.value) return;
      const target = event.currentTarget as SVGRectElement;
      const d = d3.select(target).datum() as { rowIndex: number; col: string; value: string | number };
      
      longPressTimer = window.setTimeout(() => {
        const row = data[d.rowIndex];
        selectedRowData.value = row;
        selectedColumnValue.value = d.col;
        selectedCellValue.value = d.value;
        showTooltipModal.value = true;
      }, 500); // 500ms long press
    }, { passive: true });
    
    rect.addEventListener("touchend", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
    
    rect.addEventListener("touchmove", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
  });

// --- Tooltip-Events ---
  tooltip
    .on("mouseenter", () => {
      if (hideTimeout) clearTimeout(hideTimeout); // bleibt offen
    })
    .on("mouseleave", () => {
      tooltip.style("visibility", "hidden"); // endgültig schließen
    });


  // Render the color legend on the right
    if (visualizationStore.legend) {
      renderColorLegend(svg, margin, colorScale, LEGEND_WIDTH, colorLegendId);
    }

  // Row side colors
  if (visualizationStore.rowSideColors) {
    const sortedRowSideColors = visualizationStore.rowSideColors
      ? [...visualizationStore.rowSideColors].sort((a, b) => a.localeCompare(b))
      : [];
    for (let i = 0; i < sortedRowSideColors.length; i++) {
      const col = sortedRowSideColors[i];
      const colMeta = columnStore.rowColumns.find((c) => c.column_name === col);
      const colType = lowerCase(colMeta?.type) ?? "text";

      // Use helper for values:
      const attributeValues = getSideColorAttributeValues(data, col, colType);
      const colorDomainValues = getSideColorAttributeValues(allData, col, colType);

      await renderSideColors({
        svg,
        margin,
        dimensionSize: SIDE_COLOR_WIDTH,
        labels: yLabels,
        attributeValues,
        colorDomainValues,
        column_name: col,
        colType,
        xOffset:
          margin.left -
          totalRowSideColorWidth +
          i * (SIDE_COLOR_WIDTH + SIDE_COLOR_GAP),
        yOffset: margin.top,
        orientation: "row",
      });
    }
  }

  // Column side colors
  if (visualizationStore.colSideColors) {
    const sortedColSideColors = visualizationStore.colSideColors
      ? [...visualizationStore.colSideColors].sort((a, b) => a.localeCompare(b))
      : [];
    for (let i = 0; i < sortedColSideColors.length; i++) {
      const col = sortedColSideColors[i];
      let xLabelsForColoring, attributeValues, colorDomainValues, colType;
      const allColMeta = sortedColumns.value.filter((meta) =>
        allHeatmapCols.includes(String(meta.column_name ?? "")),
      );
      if (col === "tissue_types") {
        xLabelsForColoring = heatmapCols;
        // Get actual tissue values from column metadata using configured tissue column
        const tissueKey = columnStore.tissueColumnName ?? 'tissue';
        const filteredColMeta = sortedColumns.value.filter((meta) =>
          heatmapCols.includes(String(meta.column_name ?? "")),
        );
        attributeValues = filteredColMeta.map((meta) => meta[tissueKey] ?? meta.column_name);
        colorDomainValues = allColMeta.map((meta) => meta[tissueKey] ?? meta.column_name);
      } else {
        xLabelsForColoring = heatmapCols; // already filtered by visibleColumns
        // Filter metadata to only visible columns
        const filteredColMeta = sortedColumns.value.filter((meta) =>
          heatmapCols.includes(String(meta.column_name ?? "")),
        );
        const colMeta = columnStore.colColumns.find(
          (c) => c.column_name === col,
        );
        colType = lowerCase(colMeta?.type) ?? "text";
        // Now attributeValues comes from filtered set!
        attributeValues = getSideColorAttributeValues(
          filteredColMeta,
          col,
          colType,
        );
        colorDomainValues = getSideColorAttributeValues(
          allColMeta,
          col,
          colType,
        );
      }
      await renderSideColors({
        svg,
        margin,
        dimensionSize: SIDE_COLOR_WIDTH,
        labels: xLabelsForColoring,
        attributeValues,
        colorDomainValues,
        column_name: col,
        colType,
        xOffset: margin.left,
        yOffset:
          margin.top -
          totalColSideColorHeight +
          i * (SIDE_COLOR_WIDTH + SIDE_COLOR_GAP),
        orientation: "col",
        labelWidth: 40,
      });
    }
    }
    return true;
  } finally {
    isRendering = false;
    if (renderPending) {
      renderPending = false;
      scheduleHeatmapRender();
    }
  }
}

//Settings
function openSettingsOverlay() {
  emit("openSettingsOverlay");
}

//AddHeatmap
async function addHeatmap() {
  if (props.existingTables.length !== Object.keys(props.allTables).length) {
    const nextPlausibleTable = Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) && key !== props.tableName,
    )[0][0];

    emit("update:tableName", localTableName.value + "," + nextPlausibleTable);
  }
}

async function removeHeatmap() {
  emit("update:tableName", "");
}

watch(
  () => props.tableName,
  async (newTableName) => {
    localTableName.value = newTableName;
    await nextTick();
    scheduleHeatmapRender();
  },
);

watch(
  [() => visualizationStore.expressionDisplay, () => filters.value, () => filtersStore.datasetIdFilters, filterChainVersion],
  async ([expressionDisplay]) => {
    if (!expressionDisplay) return; // guard against unset
    await fetchAndPrepareData();
    await nextTick();
    scheduleHeatmapRender();
  },
  {immediate: true, deep: true},
);

watch(
  [
    () => visualizationStore.legend,
    () => visualizationStore.rowOrder.name,
    () => visualizationStore.rowOrder.order,
    () => visualizationStore.colOrder.name,
    () => visualizationStore.colOrder.order,
    () => visualizationStore.customColOrder.enabled,
    () => visualizationStore.customColOrder.mode,
    () => visualizationStore.customColOrder.metadataColumn,
    () => visualizationStore.customColOrder.metadataValues.join("\u0000"),
    () => visualizationStore.customColOrder.sampleNames.join("\u0000"),
    () => visualizationStore.colorScale,
    () => visualizationStore.rowLabel,
    () => visualizationStore.colLabel,
    () => visualizationStore.rowSideColors,
    () => visualizationStore.colSideColors,
  ],
  async () => {
    recalculateData();
    await nextTick();
    scheduleHeatmapRender();
  },
  {deep: true},
);

watch(
  [sidebarOpen, () => props.existingTables],
  async () => {
    await nextTick();
    scheduleHeatmapRender(300);
  },
  {deep: true},
);

// Watch for clustering settings changes
watch(
  [
    () => visualizationStore.clustering.clusterRows,
    () => visualizationStore.clustering.clusterCols,
    () => visualizationStore.clustering.method,
    () => visualizationStore.clustering.distance,
  ],
  async () => {
    // Trigger clustering when settings change
    if (processedRows.value.length > 0 && dataColumnNames.value.length > 0) {
      await performClustering(
        processedRows.value, 
        dataColumnNames.value,
        props.tableName,
        mergedGeneFilters.value,
        sampleFilters.value
      );
      recalculateData();
      await nextTick();
      scheduleHeatmapRender();
    }
  },
  { deep: true }
);

// Watch for cluster order changes (from worker)
watch(
  [
    () => visualizationStore.clustering.rowOrder,
    () => visualizationStore.clustering.colOrder,
    () => visualizationStore.clustering.rowOrdersByDataset[props.tableName],
    () => visualizationStore.clustering.colOrdersByDataset[props.tableName],
  ],
  async () => {
    recalculateData();
    await nextTick();
    scheduleHeatmapRender();
  },
  { deep: true }
);

// ResizeObserver re-renders the heatmap when the container gets its final size.
// This is the primary fix for multi-heatmap rendering: when multiple heatmaps
// share a flex layout, each container's width is not final until all siblings
// have mounted. The observer fires as soon as dimensions stabilise.
let resizeObserver: ResizeObserver | null = null;
let resizeDebounceTimer: ReturnType<typeof setTimeout> | null = null;

// flush: 'post' is required for template refs in Vue 3 — the ref is only
// populated after the DOM update, so a 'pre' flush would see null.
watch(heatmapContainer, (newContainer) => {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (newContainer) {
    resizeObserver = new ResizeObserver(() => {
      if (resizeDebounceTimer) clearTimeout(resizeDebounceTimer);
      resizeDebounceTimer = setTimeout(() => {
        scheduleHeatmapRender();
      }, 100);
    });
    resizeObserver.observe(newContainer);
  }
}, { flush: 'post' });

onBeforeUnmount(() => {
  isUnmounting = true;
  activeAbortController?.abort();
  clearScheduledRender();
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (resizeDebounceTimer) {
    clearTimeout(resizeDebounceTimer);
    resizeDebounceTimer = null;
  }
});
</script>
