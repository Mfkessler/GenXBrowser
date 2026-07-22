<template>
  <div class="flex flex-col w-full gap-3" ref="viewContentRoot">
    <div
      v-if="visibleTableNames.length >= 2"
      class="flex justify-end px-2"
    >
      <div class="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-2 py-1 shadow-sm">
        <span class="text-xs font-semibold text-gray-500 px-1">All datasets</span>
        <button
          aria-label="Share all heatmaps"
          @click="showShareOverlay = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Share all heatmaps'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="currentColor" viewBox="0 0 16 16">
            <path d="M13.5 1a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3M11 2.5a2.5 2.5 0 1 1 .603 1.628l-6.718 3.12a2.5 2.5 0 0 1 0 1.504l6.718 3.12a2.5 2.5 0 1 1-.488.876l-6.718-3.12a2.5 2.5 0 1 1 0-3.256l6.718-3.12A2.5 2.5 0 0 1 11 2.5m-8.5 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3m11 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3" />
          </svg>
        </button>
        <button
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
          aria-label="Configure all heatmaps"
          @click="openSettingsOverlay"
          class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900"
          v-tooltip="'Configure all heatmaps'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z" />
          </svg>
        </button>
      </div>
    </div>
    <div
      ref="visualizationExportRoot"
      class="relative grid gap-4 p-2 overflow-visible items-stretch [container-type:inline-size]"
      :style="heatmapGridStyle"
    >
      <LoadingOverlay
        v-if="showBatchLoadingOverlay"
        primaryStatus="Generating expression heatmaps..."
        :currentPhaseHint="batchLoadingPhaseHint"
        cancellable
        @cancel="cancelLoadingAndReturnToCatalog"
      />
      <template v-if="hashStateLoaded">
        <div
          v-for="tableName in visibleTableNames"
          :key="tableName"
          class="min-w-0 flex flex-col"
          :style="heatmapCardStyle"
        >
          <HeatmapComponent
            ref="heatmapRefs"
            :table-name="tableName"
            :existing-tables="visibleTableNames"
            :all-tables="allTables"
            :show-shared-actions="visibleTableNames.length <= 1"
            :defer-loading-overlay="visibleTableNames.length > 1"
            @openSettingsOverlay="openSettingsOverlay"
            @update:tableName="onUpdateTableName(tableName, $event)"
            @loading-change="onHeatmapLoadingChange"
            @load-cancel="cancelLoadingAndReturnToCatalog"
          />
        </div>
      </template>
    </div>
    <div
      v-if="hiddenTableNames.length > 0"
      class="px-3 py-1.5 text-[11px] text-gray-500 bg-gray-50 border-t border-gray-200"
    >
      Hidden by current filter:
      <span
        v-for="(h, i) in hiddenTableNames"
        :key="h.table"
        class="ml-1"
      >
        <span class="font-medium text-gray-700">{{ h.table }}</span>
        <span class="text-gray-400"> ({{ h.reason }})</span><span v-if="i < hiddenTableNames.length - 1">,</span>
      </span>
    </div>
    <!-- SettingsOverlay -->
    <VisualizationSettings
      :showSettingsOverlay="showSettingsOverlay"
      context="heatmap"
      @update:show-overlay="closeSettingsOverlay"
    />
    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(visualizationExportRoot)"
      :initialDownload="assistantVisualizationExport ?? undefined"
      @close="closeShareOverlay"
    />
    <ExportModal
      v-if="showExportModal"
      :data="globalExportPayload.data"
      :columns="globalExportPayload.columns"
      :metaColumns="globalExportPayload.metaColumns"
      :sampleColumns="globalExportPayload.sampleColumns"
      :filename="globalExportPayload.filename"
      :hasFilters="globalExportPayload.hasFilters"
      :totalCount="globalExportPayload.data.length"
      :initialFormat="assistantDataExport ?? undefined"
      :autoExport="assistantDataExport !== null"
      @close="closeExportModal"
    />
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { computed, onMounted, onUnmounted, provide, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { type CatalogMeta } from "@/shared/CatalogMeta";
import { SharedColorRegistry } from "@/shared/colorMapping";
import { getHeatmapCardMinHeight, getHeatmapGridTemplate } from "@/shared/heatmapLayout";
import HeatmapComponent from "@/components/HeatmapComponent.vue";
import LoadingOverlay from "@/components/LoadingOverlay.vue";
import ShareOverlay from "@/components/ShareOverlay.vue";
import ExportModal from "@/components/ExportModal.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import { useDatasetEmptinessFilter } from "@/shared/useDatasetEmptinessFilter";
import { beautifyLabel } from "@/shared/utils";
import type { RowType } from "@/shared/RowType";
import {
  useAssistantExportTriggers,
  type DataExportFormat,
  type VisualizationExportFormat,
} from "@/shared/useAssistantExportTriggers";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const showSettingsOverlay = ref(false);
const showShareOverlay = ref(false);
const showExportModal = ref(false);
const assistantVisualizationExport = ref<VisualizationExportFormat | null>(null);
const assistantDataExport = ref<DataExportFormat | null>(null);

function closeShareOverlay() {
  showShareOverlay.value = false;
  assistantVisualizationExport.value = null;
}

function closeExportModal() {
  showExportModal.value = false;
  assistantDataExport.value = null;
}

useAssistantExportTriggers({
  openVisualizationExport(format) {
    assistantVisualizationExport.value = format;
    showShareOverlay.value = true;
  },
  openDataExport(format) {
    assistantDataExport.value = format ?? null;
    showExportModal.value = true;
  },
});
const viewContentRoot = ref<HTMLDivElement | null>(null);
const visualizationExportRoot = ref<HTMLDivElement | null>(null);
interface ExportPayload {
  dataset: string;
  columns: string[];
  metaColumns: string[];
  sampleColumns: string[];
  data: RowType[];
}

interface ExportPayloadProvider {
  getExportPayload?: () => ExportPayload | null;
  cancelActiveLoad?: (emitCancel?: boolean) => void;
}

interface HeatmapLoadingState {
  tableName: string;
  loading: boolean;
  progress: number | null;
  phaseHint?: string;
}

const heatmapRefs = ref<ExportPayloadProvider[]>([]);
const allTables = ref<Record<string, string>>({});
const hashStateLoaded = ref(false);
const heatmapLoadingStates = ref<Record<string, HeatmapLoadingState>>({});
let activeHashAbortController: AbortController | null = null;
let activeTablesAbortController: AbortController | null = null;

// Shared color registry for consistent side-color mapping across multiple Heatmap plots
const sharedColorRegistry = new SharedColorRegistry();
provide('sharedColorRegistry', sharedColorRegistry);

const tableNames = computed(() => {
  const param = route.params.table_names;
  return typeof param === "string" ? param.split(",") : [];
});

// Auto-hide datasets whose `.var` rows or `.obs` samples fall completely
// through the active gene/sample filters — keeps panels meaningful instead
// of showing unfiltered placeholders next to filtered ones.
const { visibleTableNames, hiddenTableNames, cancelProbes } = useDatasetEmptinessFilter(tableNames);

const heatmapGridStyle = computed(() => ({
  gridTemplateColumns: getHeatmapGridTemplate(visibleTableNames.value.length),
}));

const heatmapCardStyle = computed(() => ({
  minHeight: getHeatmapCardMinHeight(visibleTableNames.value.length),
  height: getHeatmapCardMinHeight(visibleTableNames.value.length),
}));

const activeHeatmapLoadingStates = computed(() =>
  Object.values(heatmapLoadingStates.value).filter((state) => state.loading),
);

const showBatchLoadingOverlay = computed(() =>
  visibleTableNames.value.length > 1 && activeHeatmapLoadingStates.value.length > 0,
);

const batchLoadingPhaseHint = computed(() => {
  const state = activeHeatmapLoadingStates.value.find((state) => state.phaseHint);
  return state?.phaseHint || "Preparing heatmaps across selected datasets...";
});

const globalExportPayload = computed(() => {
  const payloads = (heatmapRefs.value || [])
    .map((component) => component?.getExportPayload?.())
    .filter(Boolean);
  const columns = uniqueColumns(['dataset', ...payloads.flatMap((payload) => payload.columns)]);
  const metaColumns = uniqueColumns(['dataset', ...payloads.flatMap((payload) => payload.metaColumns)]);
  const sampleColumns = uniqueColumns(payloads.flatMap((payload) => payload.sampleColumns));
  const data = payloads.flatMap((payload) =>
    payload.data.map((row: RowType) => ({ dataset: beautifyLabel(payload.dataset), ...row })),
  );

  return {
    data,
    columns,
    metaColumns,
    sampleColumns,
    filename: `heatmaps_${visibleTableNames.value.join('_')}_${visualizationStore.expressionDisplay.optionId}`,
    hasFilters: Object.keys(filtersStore.filters).length > 0,
  };
});

function uniqueColumns(columns: string[]): string[] {
  return [...new Set(columns.filter(Boolean))];
}

const openSettingsOverlay = () => {
  showSettingsOverlay.value = true;
};

const closeSettingsOverlay = () => {
  showSettingsOverlay.value = false;
};

function onUpdateTableName(oldTableName: string, newTableName: string) {
  if (oldTableName === newTableName) return;

  const currentTableNames =
    typeof route.params.table_names === "string"
      ? route.params.table_names.split(",")
      : [];

  let updatedTableNames: string[];

  if (newTableName === "") {
    // Remove oldTableName entirely
    updatedTableNames = currentTableNames.filter(
      (name) => name !== oldTableName,
    );
  } else {
    // Replace oldTableName with newTableName
    updatedTableNames = currentTableNames.map((name) =>
      name === oldTableName ? newTableName : name,
    );
  }

  router.replace({
    name: route.name,
    params: {
      ...route.params,
      table_names: updatedTableNames.join(","),
    },
    query: { ...route.query },
  });
}

function onHeatmapLoadingChange(state: HeatmapLoadingState) {
  heatmapLoadingStates.value = {
    ...heatmapLoadingStates.value,
    [state.tableName]: state,
  };
}

function isCanceledRequest(error: unknown) {
  return axios.isCancel(error) || (axios.isAxiosError(error) && error.code === "ERR_CANCELED");
}

function cancelBatchLoading() {
  for (const component of heatmapRefs.value || []) {
    component?.cancelActiveLoad?.(false);
  }
}

function cancelLoadingAndReturnToCatalog() {
  activeHashAbortController?.abort();
  activeHashAbortController = null;
  activeTablesAbortController?.abort();
  activeTablesAbortController = null;
  cancelProbes();
  cancelBatchLoading();
  heatmapLoadingStates.value = {};
  hashStateLoaded.value = true;
  router.replace({ name: "catalog" });
}

// Re-load filter / visualization state whenever `?id=` changes. This
// allows assistant-driven re-navigations within the same heatmap path
// (different filter/viz hash) to refresh the view automatically.
async function loadStateFromIdParam(idParam: unknown, signal?: AbortSignal) {
  if (typeof idParam !== "string" || idParam.length !== 16) {
    hashStateLoaded.value = true;
    return;
  }
  hashStateLoaded.value = false;
  try {
    const response = await axios.post(`${API_BASE_URL}/api/id`, { id: idParam }, { signal });
    const data = response.data;
    if (data.filters && data.visualizations) {
      visualizationStore.replaceState(data.visualizations);
      filtersStore.replaceState(data.filters);
    } else {
      console.warn("Invalid data received from backend for ID", idParam);
    }
  } catch (error) {
    if (isCanceledRequest(error)) return;
    console.error("Error fetching filter data by ID", idParam, error);
  } finally {
    if (!signal?.aborted) hashStateLoaded.value = true;
  }
}

watch(
  () => route.query.id,
  (idParam) => {
    activeHashAbortController?.abort();
    const controller = new AbortController();
    activeHashAbortController = controller;
    loadStateFromIdParam(idParam, controller.signal).finally(() => {
      if (activeHashAbortController === controller) activeHashAbortController = null;
    });
  },
  { immediate: true },
);

onMounted(async () => {
  activeTablesAbortController?.abort();
  const controller = new AbortController();
  activeTablesAbortController = controller;
  // Fetch all possible table names for dropdown options:
  const tagsParam = [...filtersStore.tags].join(",");
  try {
    const response = await axios.get<CatalogMeta[]>(
      `${API_BASE_URL}/api/tables`,
      {
        params: {
          tags: tagsParam,
        },
        signal: controller.signal,
      },
    );

    if (controller.signal.aborted) return;
    response.data.forEach((t) => {
      allTables.value[t.table_name] = beautifyLabel(t.table_name);
    });
  } catch (error) {
    if (!isCanceledRequest(error)) throw error;
  } finally {
    if (activeTablesAbortController === controller) activeTablesAbortController = null;
  }
});

onUnmounted(() => {
  activeHashAbortController?.abort();
  activeTablesAbortController?.abort();
});
</script>
