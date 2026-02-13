<template>
  <div class="h-[100vh] flex flex-col">
    <!-- PhyloTree Controls Bar -->
    <div class="flex items-center gap-2 p-2 bg-gray-50 border-b border-gray-200">
      <!-- Reset View Button -->
      <button
        @click="resetPhyloTreeView"
        class="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-100 transition-colors"
        title="Reset zoom and expand all collapsed nodes"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
        </svg>
        Reset View
      </button>
      
      <!-- Zoom level indicator -->
      <span class="text-sm text-gray-500 ml-2">
        Zoom: {{ Math.round(zoomLevel * 100) }}%
      </span>
      
      <!-- Collapsed nodes count -->
      <span v-if="collapsedNodesCount > 0" class="text-sm text-amber-600 ml-2">
        {{ collapsedNodesCount }} node(s) collapsed
      </span>
      
      <div class="flex-grow"></div>
      
      <!-- Hint -->
      <span class="text-xs text-gray-400">
        Scroll to zoom • Drag to pan • Click nodes to collapse
      </span>
    </div>

    <!-- Gallery container: flex wrap and gap for nice grid layout -->
    <div
      class="flex gap-4 flex-grow p-2 overflow-x-auto overflow-y-hidden whitespace-nowrap"
    >
      <div
        v-for="tableName in tableNames"
        :key="tableName"
        class="flex-grow min-w-[42rem] h-[90vh] flex flex-col"
      >
        <PhylogeneticTree
          ref="phyloTreeRefs"
          :table-name="tableName"
          :existing-tables="allTableNamesFromRoute"
          :all-tables="allTables"
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
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { type CatalogMeta } from "@/shared/CatalogMeta";
import PhylogeneticTree from "@/components/PhylogeneticTree.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import { beautifyLabel } from "@/shared/utils";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const allTables = ref<Record<string, string>>({});
const showSettingsOverlay = ref(false);
const phyloTreeRefs = ref<InstanceType<typeof PhylogeneticTree>[] | null>(null);
const hashLoading = ref(true); // Prevent child from fetching until hash is loaded
const initialOrthogroup = ref<string | null>(null); // OG from hash load

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

onMounted(async () => {
  // Check for `id` query parameter
  const idParam = route.query.id;
  if (typeof idParam === "string" && idParam.length === 16) {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/id`, {
        id: idParam,
      });

      const data = response.data;

      // Expecting: data = { filters: {...}, visualizations: {...} }
      if (data.filters && data.visualizations) {
        // IMPORTANT: Restore visualization state FIRST (includes selectedOrthogroup),
        // then filters. This prevents the filters watcher from overwriting the OG selection.
        visualizationStore.replaceState(data.visualizations);
        filtersStore.replaceState(data.filters);
        
        // Set initial orthogroup from hash for child component
        if (data.visualizations.phyloTree?.selectedOrthogroup) {
          initialOrthogroup.value = data.visualizations.phyloTree.selectedOrthogroup;
        }
      } else {
        console.warn("Invalid data received from backend for ID", idParam);
      }
    } catch (error) {
      console.error("Error fetching filter data by ID", idParam, error);
    }
  }
  
  // Mark hash loading as complete - child can now fetch data
  hashLoading.value = false;

  // Fetch all possible table names for dropdown options:
  const tagsParam = [...filtersStore.tags].join(",");
  const response = await axios.get<CatalogMeta[]>(
    `${API_BASE_URL}/api/tables`,
    {
      params: {
        tags: tagsParam,
      },
    },
  );

  response.data.forEach((t) => {
    allTables.value[t.table_name] = beautifyLabel(t.table_name);
  });
});
</script>
