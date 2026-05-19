<template>
  <div class="flex flex-col w-full gap-3" ref="viewContentRoot">
    <div
      v-if="visibleTableNames.length >= 2"
      class="flex justify-end px-2"
    >
      <div class="inline-flex items-center gap-2 rounded-md border border-gray-200 bg-white px-2 py-1 shadow-sm">
        <span class="text-xs font-semibold text-gray-500 px-1">All datasets</span>
        <button
          aria-label="Share all ORA results"
          @click="showShareOverlay = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Share all ORA results'"
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
          aria-label="Configure all ORA results"
          @click="openSettingsOverlay"
          class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900"
          v-tooltip="'Configure all ORA results'"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </div>
    </div>
    <div
      ref="visualizationExportRoot"
      class="relative grid gap-4 p-2 overflow-visible [container-type:inline-size]"
      :style="oraGridStyle"
    >
      <LoadingOverlay
        v-if="showBatchLoadingOverlay"
        label="Loading ORA"
        cancellable
        @cancel="cancelLoadingAndReturnToCatalog"
      />
      <div
        v-for="tableName in visibleTableNames"
        :key="tableName"
        class="min-w-0 flex flex-col"
      >
        <OraComponent
          ref="oraRefs"
          :table-name="tableName"
          :existing-tables="visibleTableNames"
          :all-tables="allTables"
          :hash-loading="hashLoading"
          :show-shared-actions="visibleTableNames.length <= 1"
          :defer-loading-overlay="visibleTableNames.length > 1"
          @openSettingsOverlay="openSettingsOverlay"
          @update:tableName="onUpdateTableName(tableName, $event)"
          @loading-change="onOraLoadingChange"
          @load-cancel="cancelLoadingAndReturnToCatalog"
        />
      </div>
    </div>
    <div
      v-if="hiddenTableNames.length > 0"
      class="px-3 py-1.5 text-[11px] text-gray-500 bg-gray-50 border-t border-gray-200"
    >
      Hidden by current filter:
      <span v-for="(h, i) in hiddenTableNames" :key="h.table" class="ml-1">
        <span class="font-medium text-gray-700">{{ h.table }}</span>
        <span class="text-gray-400"> ({{ h.reason }})</span><span v-if="i < hiddenTableNames.length - 1">,</span>
      </span>
    </div>
    <!-- SettingsOverlay -->
    <VisualizationSettings
      :showSettingsOverlay="showSettingsOverlay"
      context="ora"
      @update:show-overlay="closeSettingsOverlay"
    />
    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(visualizationExportRoot)"
      @close="showShareOverlay = false"
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
      dataColumnLabel="metrics"
      @close="showExportModal = false"
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
import OraComponent from "@/components/OraComponent.vue";
import LoadingOverlay from "@/components/LoadingOverlay.vue";
import ShareOverlay from "@/components/ShareOverlay.vue";
import ExportModal from "@/components/ExportModal.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import { useDatasetEmptinessFilter } from "@/shared/useDatasetEmptinessFilter";
import { beautifyLabel } from "@/shared/utils";
import type { RowType } from "@/shared/RowType";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const showSettingsOverlay = ref(false);
const showShareOverlay = ref(false);
const showExportModal = ref(false);
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

interface OraLoadingState {
  tableName: string;
  loading: boolean;
  progress: number | null;
}

const oraRefs = ref<ExportPayloadProvider[]>([]);
const allTables = ref<Record<string, string>>({});
const hashLoading = ref(true);
const oraLoadingStates = ref<Record<string, OraLoadingState>>({});
let activeHashAbortController: AbortController | null = null;
let activeTablesAbortController: AbortController | null = null;

// Shared color registry for consistent side-color mapping across multiple ORA plots
const sharedColorRegistry = new SharedColorRegistry();
provide('sharedColorRegistry', sharedColorRegistry);

const tableNames = computed(() => {
  const param = route.params.table_names;
  return typeof param === "string" ? param.split(",") : [];
});

// Hide datasets that have no transcripts / no samples after the current
// filter set so the user never sees an unfiltered panel sitting next to
// filtered ones.
const { visibleTableNames, hiddenTableNames, cancelProbes } = useDatasetEmptinessFilter(tableNames);

const oraGridStyle = computed(() => ({
  gridTemplateColumns: visibleTableNames.value.length <= 1
    ? "minmax(0, 1fr)"
    : "repeat(auto-fit, minmax(min(100%, 38rem), 1fr))",
}));

const activeOraLoadingStates = computed(() =>
  Object.values(oraLoadingStates.value).filter((state) => state.loading),
);

const showBatchLoadingOverlay = computed(() =>
  visibleTableNames.value.length > 1 && activeOraLoadingStates.value.length > 0,
);

const globalExportPayload = computed(() => {
  const payloads = (oraRefs.value || [])
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
    filename: `ora_${visibleTableNames.value.join('_')}_${visualizationStore.oraColumnName}`,
    hasFilters: Object.keys(filtersStore.filters).length > 0,
  };
});

function uniqueColumns(columns: string[]): string[] {
  return [...new Set(columns.filter(Boolean))];
}

function onOraLoadingChange(state: OraLoadingState) {
  oraLoadingStates.value = {
    ...oraLoadingStates.value,
    [state.tableName]: state,
  };
}

function cancelBatchLoading() {
  for (const component of oraRefs.value || []) {
    component?.cancelActiveLoad?.(false);
  }
}

function isCanceledRequest(error: unknown) {
  return axios.isCancel(error) || (axios.isAxiosError(error) && error.code === "ERR_CANCELED");
}

function cancelLoadingAndReturnToCatalog() {
  activeHashAbortController?.abort();
  activeHashAbortController = null;
  activeTablesAbortController?.abort();
  activeTablesAbortController = null;
  cancelProbes();
  cancelBatchLoading();
  oraLoadingStates.value = {};
  hashLoading.value = false;
  router.replace({ name: "catalog" });
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

// Re-load filter / visualization state whenever `?id=` changes — including
// the initial mount. This is what makes assistant-driven re-navigations
// (e.g. ORA orthogroup -> GO terms on the same /o/CS path) actually take
// effect; without it the component would be reused and stale state kept.
async function loadStateFromIdParam(idParam: unknown, signal?: AbortSignal) {
  hashLoading.value = true;
  if (typeof idParam !== "string" || idParam.length !== 16) {
    hashLoading.value = false;
    return;
  }
  try {
    const response = await axios.post(`${API_BASE_URL}/api/id`, { id: idParam }, { signal });
    const data = response.data;
    if (data.filters && data.visualizations) {
      // Visualization state first, then filters — watchers on filters
      // would otherwise overwrite restored selections.
      visualizationStore.replaceState(data.visualizations);
      filtersStore.replaceState(
        data.filters.filters !== undefined ? data.filters : { filters: data.filters },
      );
    } else {
      console.warn("Invalid data received from backend for ID", idParam);
    }
  } catch (error) {
    if (isCanceledRequest(error)) return;
    console.error("Error fetching filter data by ID", idParam, error);
  } finally {
    if (!signal?.aborted) hashLoading.value = false;
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
