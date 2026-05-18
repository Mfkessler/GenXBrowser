<template>
  <div class="min-h-[100vh] flex flex-col relative">
    <div v-if="hashLoading" class="absolute inset-0 z-50">
      <LoadingOverlay label="Loading tree" cancellable @cancel="cancelHashLoading" />
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

      <button
        @click="openSettingsOverlay"
        class="flex items-center justify-center p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900 transition-colors min-h-11"
        aria-label="Configure phylogenetic tree settings"
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
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>
    </div>

    <!-- Gallery container: flex wrap and gap for nice grid layout -->
    <div
      v-if="!hashLoading"
      class="flex gap-4 flex-grow p-2 overflow-visible min-w-0"
    >
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
          :initial-orthogroup="initialOrthogroup"
          @openSettingsOverlay="openSettingsOverlay"
          @update:tableName="onUpdateTableName(tableName, $event)"
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
  expandAll?: () => void;
  collapseAll?: () => void;
  collapseToSpecies?: () => void;
};
const phyloTreeRefs = ref<PhylogeneticTreeExpose[] | null>(null);
const hashLoading = ref(true); // Prevent child from fetching until hash is loaded
const initialOrthogroup = ref<string | null>(null); // OG from hash load
let activeHashAbortController: AbortController | null = null;

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

function cancelHashLoading() {
  activeHashAbortController?.abort();
  activeHashAbortController = null;
  hashLoading.value = false;
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
  () => [route.query.id, route.query.filters, route.params.table_names],
  async (idParam) => {
    activeHashAbortController?.abort();
    const controller = new AbortController();
    activeHashAbortController = controller;
    hashLoading.value = true;
    await loadStateFromIdParam(Array.isArray(idParam) ? idParam[0] : idParam, controller.signal);
    if (!controller.signal.aborted) {
      hashLoading.value = false;
      activeHashAbortController = null;
    }
  },
  { flush: "sync" },
);

onMounted(async () => {
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

    response.data.forEach((t) => {
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
  activeHashAbortController?.abort();
});
</script>
