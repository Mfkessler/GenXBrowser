<template>
  <div class="min-h-[100vh] flex flex-col relative">
    <div v-if="visibleCombinedLoading" class="absolute inset-0 z-50">
      <LoadingOverlay
        primaryStatus="Generating phylogenetic tree..."
        :currentPhaseHint="combinedLoadingPhaseHint"
        cancellable
        @cancel="cancelUnifiedLoading"
      />
    </div>

    <!-- PhyloTree Controls Bar -->
    <div class="flex flex-wrap items-center gap-2 p-2 bg-gray-50 border-b border-gray-200">
      <!-- Reset View Button -->
      <button
        @click="resetPhyloTreeView"
        class="flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition-colors min-h-11"
        aria-label="Reset zoom and expand all collapsed nodes"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Reset View
      </button>

      <!-- Quick-collapse actions -->
      <button
        @click="callOnAllTrees('expandAll')"
        class="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition-colors min-h-11"
        aria-label="Expand every collapsed clade"
      >Expand all</button>
      <button
        @click="callOnAllTrees('collapseAll')"
        class="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition-colors min-h-11"
        aria-label="Collapse every internal clade"
      >Collapse all</button>
      <button
        @click="callOnAllTrees('collapseToSpecies')"
        class="px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition-colors min-h-11"
        aria-label="Collapse every monophyletic species clade"
      >Collapse to species</button>

      <!-- Zoom level indicator -->
      <span class="text-sm text-gray-500 ml-0 sm:ml-2 whitespace-nowrap">
        Zoom: {{ Math.round(zoomLevel * 100) }}%
      </span>
      
      <!-- Collapsed nodes count -->
      <span v-if="collapsedNodesCount > 0" class="text-sm text-amber-600 ml-2">
        {{ collapsedNodesCount }} node(s) collapsed
      </span>
      
      <div class="hidden sm:block flex-grow"></div>
      
      <!-- Hint -->
      <span class="hidden lg:inline text-xs text-gray-400">
        Scroll to zoom • Drag to pan • Click internal nodes to collapse • Right-click for more
      </span>

    </div>

    <!-- Gallery container: flex wrap and gap for nice grid layout -->
    <div class="flex gap-4 flex-grow p-2 overflow-visible min-w-0">
      <div
        v-for="tableName in tableNames"
        :key="phyloInstanceKey(tableName)"
        class="flex-grow min-w-0 min-h-[34rem] sm:min-h-[calc(100vh-5rem)] flex flex-col"
      >
        <PhylogeneticTree
          ref="phyloTreeRefs"
          :table-name="tableName"
          :existing-tables="allTableNamesFromRoute"
          :all-tables="allTables"
          :species-code-map="speciesCodeMap"
          :hash-loading="hashLoading"
          external-loading-overlay
          :initial-orthogroup="initialOrthogroup"
          @openSettingsOverlay="openSettingsOverlay"
          @update:loading-state="onChildLoadingState"
          @update:tableName="onUpdateTableName(tableName, $event)"
          @load-cancel="cancelUnifiedLoading"
        />
      </div>
    </div>
    <!-- SettingsOverlay -->
    <VisualizationSettings
      :showSettingsOverlay="showSettingsOverlay"
      context="phylogeneticTree"
      :phyloTreeOrthogroupOptions="phyloTreeOrthogroupOptions"
      @update:show-overlay="closeSettingsOverlay"
    />
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { type CatalogMeta } from "@/shared/CatalogMeta";
import PhylogeneticTree from "@/components/PhylogeneticTree.vue";
import LoadingOverlay from "@/components/LoadingOverlay.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import { beautifyLabel } from "@/shared/utils";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const allTables = ref<Record<string, string>>({});
const speciesCodeMap = ref<Record<string, string>>({});
const showSettingsOverlay = ref(false);
type PhylogeneticTreeExpose = InstanceType<typeof PhylogeneticTree> & {
  orthogroupOptions?: Record<string, string>;
  cancelActiveLoad?: (emitCancel?: boolean) => void;
  expandAll?: () => void;
  collapseAll?: () => void;
  collapseToSpecies?: () => void;
};
const phyloTreeRefs = ref<PhylogeneticTreeExpose[] | null>(null);
const hashLoading = ref(true); // Prevent child from fetching until hash is loaded
const childLoading = ref(true);
const childLoadingProgress = ref<number | null>(null);
const childLoadingPhaseHint = ref("Preparing tree request...");
const combinedLoadingProgress = ref<number | null>(5);
const combinedLoadingPhaseHint = computed(() => {
  if (hashLoading.value) return "Restoring saved tree state...";
  return childLoadingPhaseHint.value || "Preparing tree request...";
});
const visibleCombinedLoading = ref(true);
const initialOrthogroup = ref<string | null>(null); // OG from hash load
let activeHashAbortController: AbortController | null = null;
let hideCombinedLoadingTimer: ReturnType<typeof setTimeout> | null = null;

const combinedLoading = computed(() => hashLoading.value || childLoading.value);

watch(
  [hashLoading, childLoading, childLoadingProgress],
  () => {
    if (combinedLoading.value) {
      if (hideCombinedLoadingTimer !== null) {
        clearTimeout(hideCombinedLoadingTimer);
        hideCombinedLoadingTimer = null;
      }
      visibleCombinedLoading.value = true;
    }

    if (!combinedLoading.value) {
      if (hideCombinedLoadingTimer === null) {
        hideCombinedLoadingTimer = setTimeout(() => {
          hideCombinedLoadingTimer = null;
          if (!combinedLoading.value) {
            visibleCombinedLoading.value = false;
            combinedLoadingProgress.value = null;
          }
        }, 180);
      }
      return;
    }

    const current = combinedLoadingProgress.value ?? 0;
    const next = typeof childLoadingProgress.value === "number" && Number.isFinite(childLoadingProgress.value)
      ? childLoadingProgress.value
      : 5;
    combinedLoadingProgress.value = Math.min(100, Math.max(current, next));
  },
  { immediate: true },
);

// Get orthogroup options from the first PhyloTree instance
const phyloTreeOrthogroupOptions = computed(() => {
  if (phyloTreeRefs.value && phyloTreeRefs.value.length > 0) {
    return phyloTreeRefs.value[0]?.orthogroupOptions || {};
  }
  return {};
});

function openSettingsOverlay() {
  showSettingsOverlay.value = true;
}

function closeSettingsOverlay() {
  showSettingsOverlay.value = false;
}

function resetPhyloTreeView() {
  visualizationStore.resetPhyloTreeState();
}

function callOnAllTrees(method: 'expandAll' | 'collapseAll' | 'collapseToSpecies') {
  const refs = phyloTreeRefs.value;
  if (!refs) return;
  for (const r of refs) {
    r[method]?.();
  }
}

// GAIA state-token toolbar commands are delivered through a CustomEvent and
// fanned out to every mounted tree instance.
const PHYLO_COMMAND_DISPATCH: Record<string, () => void> = {
  reset_view: () => resetPhyloTreeView(),
  expand_all: () => callOnAllTrees('expandAll'),
  collapse_all: () => callOnAllTrees('collapseAll'),
  collapse_to_species: () => callOnAllTrees('collapseToSpecies'),
};

function onAssistantPhyloCommand(event: Event) {
  const detail = (event as CustomEvent<{ command?: string }>).detail;
  const command = String(detail?.command || '').trim().toLowerCase();
  const handler = PHYLO_COMMAND_DISPATCH[command];
  if (handler) handler();
}

function cancelUnifiedLoading() {
  activeHashAbortController?.abort();
  activeHashAbortController = null;
  hashLoading.value = false;
  childLoading.value = false;
  childLoadingProgress.value = null;
  childLoadingPhaseHint.value = "Load canceled";
  combinedLoadingProgress.value = null;
  visibleCombinedLoading.value = false;
  phyloTreeRefs.value?.forEach((tree) => tree.cancelActiveLoad?.(false));
  router.replace({ name: "catalog" });
}

function onChildLoadingState(state: { loading: boolean; progress: number | null; phaseHint?: string }) {
  childLoading.value = state.loading;
  childLoadingProgress.value = state.progress;
  childLoadingPhaseHint.value = state.phaseHint || childLoadingPhaseHint.value;
}

const zoomLevel = computed(() => visualizationStore.phyloTree.zoomTransform.k);
const collapsedNodesCount = computed(() => visualizationStore.phyloTree.collapsedNodes.length);

// All table names from route (for passing to child as existing-tables)
const allTableNamesFromRoute = computed(() => {
  const param = route.params.table_names;
  return typeof param === "string" ? param.split(",") : [];
});

// Always render a single PhylogeneticTree component.
// The component fetches data for all available species internally.
const tableNames = computed(() => {
  const all = allTableNamesFromRoute.value;
  // For multi-species catalog navigation, render single panel with first species
  if (all.length > 1) {
    return [all[0]];
  }
  return all;
});

const analysisInstanceKey = computed(() => {
  const tables = typeof route.params.table_names === "string" ? route.params.table_names : "";
  const id = typeof route.query.id === "string" ? route.query.id : "";
  const filters = typeof route.query.filters === "string" ? route.query.filters : "";
  return `${tables}|${id}|${filters}`;
});

function phyloInstanceKey(tableName: string) {
  return `${tableName}|${analysisInstanceKey.value}`;
}

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

// Re-load filter / visualization state whenever `?id=` changes — covers
// both initial mount and assistant-driven re-navigations to the same
// /p/<tables> path with a fresh hash.
async function loadStateFromIdParam(idParam: unknown, signal?: AbortSignal) {
  if (typeof idParam !== "string" || idParam.length !== 16) return;
  try {
    const response = await axios.post(`${API_BASE_URL}/api/id`, { id: idParam }, { signal });
    const data = response.data;
    if (data.filters && data.visualizations) {
      visualizationStore.replaceState(data.visualizations);
      filtersStore.replaceState(data.filters);
      if (data.visualizations.phyloTree?.selectedOrthogroup) {
        initialOrthogroup.value = data.visualizations.phyloTree.selectedOrthogroup;
      }
    } else {
      console.warn("Invalid data received from backend for ID", idParam);
    }
  } catch (error) {
    if (axios.isCancel(error) || (axios.isAxiosError(error) && error.code === "ERR_CANCELED")) return;
    console.error("Error fetching filter data by ID", idParam, error);
  }
}

watch(
  // Use a primitive string signature so Vue can dedupe by value.  A raw
  // `() => [...]` getter returns a new array on every dependency tick,
  // which makes the watcher fire on every router.replace (e.g. when the
  // child writes `?orthogroup=` back into the URL).  That in turn
  // bounces `hashLoading` and re-triggers downstream fetches that have
  // nothing to do with the user's action.
  () => {
    const id = typeof route.query.id === "string" ? route.query.id : "";
    const filters = typeof route.query.filters === "string" ? route.query.filters : "";
    const tables = typeof route.params.table_names === "string" ? route.params.table_names : "";
    return `${id}|${filters}|${tables}`;
  },
  async (_sig, _oldSig) => {
    activeHashAbortController?.abort();
    const controller = new AbortController();
    activeHashAbortController = controller;
    hashLoading.value = true;
    const idParam = typeof route.query.id === "string" ? route.query.id : "";
    await loadStateFromIdParam(idParam, controller.signal);
    if (!controller.signal.aborted) {
      hashLoading.value = false;
      activeHashAbortController = null;
    }
  },
  { flush: "sync" },
);

onMounted(async () => {
  if (typeof window !== "undefined") {
    window.addEventListener('genx:phylo-command', onAssistantPhyloCommand);
  }
  activeHashAbortController?.abort();
  const controller = new AbortController();
  activeHashAbortController = controller;
  // Fetch all possible table names for dropdown options:
  const tagsParam = [...filtersStore.tags].join(",");
  try {
    await loadStateFromIdParam(route.query.id, controller.signal);

    const response = await axios.get<CatalogMeta[]>(
      `${API_BASE_URL}/api/tables`,
      {
        params: {
          tags: tagsParam,
        },
        signal: controller.signal,
      },
    );

    const nextAllTables: Record<string, string> = {};
    const nextSpeciesCodeMap: Record<string, string> = {};

    const capabilities = new Map(response.data.map((table) => [table.table_name, table.has_orthogroups !== false]));
    if (allTableNamesFromRoute.value.some((tableName) => capabilities.get(tableName) !== true)) {
      await router.replace({ name: "catalog" });
      return;
    }

    response.data.filter((t) => t.has_orthogroups !== false).forEach((t) => {
      nextAllTables[t.table_name] = beautifyLabel(t.table_name);
      if (t._species_code) {
        nextSpeciesCodeMap[t.table_name] = t._species_code;
      }
    });

    allTables.value = nextAllTables;
    speciesCodeMap.value = nextSpeciesCodeMap;
  } finally {
    // Child fetch/render starts only after hash state and species metadata are ready.
    if (!controller.signal.aborted) {
      hashLoading.value = false;
      activeHashAbortController = null;
    }
  }
});

onUnmounted(() => {
  if (typeof window !== "undefined") {
    window.removeEventListener('genx:phylo-command', onAssistantPhyloCommand);
  }
  if (hideCombinedLoadingTimer !== null) {
    clearTimeout(hideCombinedLoadingTimer);
    hideCombinedLoadingTimer = null;
  }
  activeHashAbortController?.abort();
});
</script>
