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
import { computed, onMounted, ref } from "vue";
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

onMounted(async () => {
  // Check for `id` query parameter (hash-based share link)
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
        // then filters. This prevents watchers from overwriting the OG selection.
        visualizationStore.replaceState(data.visualizations);
        filtersStore.replaceState(data.filters);
        
        console.log('[CompareExpression] Hash load - data.visualizations.compare:', data.visualizations.compare);
        
        // Use species from the loaded state
        if (data.visualizations.compare?.selectedSpecies?.length > 0) {
          hashLoadedSpecies.value = data.visualizations.compare.selectedSpecies;
          console.log('[CompareExpression] hashLoadedSpecies set to:', hashLoadedSpecies.value);
        }
        // Use orthogroup from the loaded state
        if (data.visualizations.compare?.selectedOrthogroup) {
          hashLoadedOrthogroup.value = data.visualizations.compare.selectedOrthogroup;
          console.log('[CompareExpression] hashLoadedOrthogroup set to:', hashLoadedOrthogroup.value);
        }
      } else {
        console.warn("Invalid data received from backend for ID", idParam);
      }
    } catch (error) {
      console.error("Error fetching filter data by ID", idParam, error);
    }
  }

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
