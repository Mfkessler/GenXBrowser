<template>
  <div class="h-[100vh] flex flex-col">
    <!-- Optional: Your header or controls here -->

    <!-- Gallery container: flex wrap and gap for nice grid layout -->
    <div
      class="flex gap-4 flex-grow p-2 overflow-x-auto overflow-y-hidden whitespace-nowrap"
    >
      <!-- Only render Compare after hash data is loaded (if hash-based) -->
      <!-- For non-hash loads (hashLoadedSpecies stays null), render immediately when isDataLoaded is true -->
      <!-- For hash loads, wait until isDataLoaded is true AND hashLoadedSpecies has been populated -->
      <template v-if="isDataLoaded">
        <div
          v-for="tableName in effectiveTableNames"
          :key="tableName"
          class="flex-grow min-w-[42rem] h-[90vh] flex flex-col"
        >
          <Compare
            :table-name="tableName"
            :existing-tables="tableNamesFromRoute"
            :all-tables="allTables"
            :initial-species="hashLoadedSpecies"
            :initial-orthogroup="hashLoadedOrthogroup"
            @update:tableName="onUpdateTableName(tableName, $event)"
          />
        </div>
      </template>
    </div>
    <!-- SettingsOverlay -->

  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { type CatalogMeta } from "@/shared/CatalogMeta";
import Compare from "@/components/Compare.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import { beautifyLabel } from "@/shared/utils";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const allTables = ref<Record<string, string>>({});
const hashLoadedSpecies = ref<string[] | null>(null);  // null = not a hash load
const hashLoadedOrthogroup = ref<string | null>(null);  // For hash-based loads
const isDataLoaded = ref(false);  // Wait for hash data to load before rendering Compare

// Get table names from route params
const tableNamesFromRoute = computed(() => {
  const param = route.params.table_names;
  return typeof param === "string" && param.length > 0 ? param.split(",") : [];
});

// Always render a single Compare component (using first species as "main table").
// The Compare component fetches data for ALL species via allTables and uses the
// store's selectedSpecies / selectedOrthogroup for display.
const effectiveTableNames = computed(() => {
  if (hashLoadedSpecies.value !== null && hashLoadedSpecies.value.length > 0) {
    return [hashLoadedSpecies.value[0]];
  }
  // Catalog navigation with multiple species → single panel
  if (tableNamesFromRoute.value.length > 1) {
    return [tableNamesFromRoute.value[0]];
  }
  return tableNamesFromRoute.value;
});

function onUpdateTableName(oldTableName: string, newTableName: string) {
  if (oldTableName === newTableName) return;

  const currentTableNames = [...effectiveTableNames.value];

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

  // Update local state if we're in hash-loaded mode
  if (hashLoadedSpecies.value !== null) {
    hashLoadedSpecies.value = updatedTableNames;
  }

  // Update store
  visualizationStore.setCompareState({ selectedSpecies: updatedTableNames });

  router.replace({
    name: route.name,
    params: {
      ...route.params,
      table_names: updatedTableNames.join(","),
    },
    query: { ...route.query },
  });
}

// Re-load filter / visualization state whenever `?id=` changes. Triggers
// on initial mount and on assistant-driven re-navigations to the same
// /c/<tables> path with a fresh hash.
async function loadStateFromIdParam(idParam: unknown) {
  if (typeof idParam !== "string" || idParam.length !== 16) return;
  try {
    const response = await axios.post(`${API_BASE_URL}/api/id`, { id: idParam });
    const data = response.data;
    if (data.filters && data.visualizations) {
      visualizationStore.replaceState(data.visualizations);
      filtersStore.replaceState(data.filters);
      if (data.visualizations.compare?.selectedSpecies?.length > 0) {
        hashLoadedSpecies.value = data.visualizations.compare.selectedSpecies;
      }
      if (data.visualizations.compare?.selectedOrthogroup) {
        hashLoadedOrthogroup.value = data.visualizations.compare.selectedOrthogroup;
      }
    } else {
      console.warn("Invalid data received from backend for ID", idParam);
    }
  } catch (error) {
    console.error("Error fetching filter data by ID", idParam, error);
  }
}

watch(
  () => route.query.id,
  async (idParam) => {
    if (typeof idParam !== "string" || idParam.length !== 16) return;
    isDataLoaded.value = false;
    await loadStateFromIdParam(idParam);
    isDataLoaded.value = allTables.value && Object.keys(allTables.value).length > 0;
  },
);

watch(
  tableNamesFromRoute,
  (routeTableNames) => {
    if (routeTableNames.length === 0) return;
    if (hashLoadedSpecies.value === null) return;
    const current = hashLoadedSpecies.value.join(",");
    const next = routeTableNames.join(",");
    if (current === next) return;
    hashLoadedSpecies.value = [...routeTableNames];
    visualizationStore.setCompareState({ selectedSpecies: routeTableNames });
  },
);

onMounted(async () => {
  await loadStateFromIdParam(route.query.id);

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

  // For non-hash navigation with multiple species from catalog,
  // pre-set selectedSpecies so the Compare component shows them all
  if (hashLoadedSpecies.value === null && tableNamesFromRoute.value.length > 1) {
    visualizationStore.setCompareState({ selectedSpecies: tableNamesFromRoute.value });
  }
  
  // Mark data as loaded AFTER allTables is populated - now Compare components can render
  isDataLoaded.value = true;
});
</script>
