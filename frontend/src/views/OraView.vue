<template>
  <div class="flex flex-col">
    <div
      class="flex gap-4 p-2 overflow-x-auto overflow-y-hidden"
    >
      <div
        v-for="tableName in visibleTableNames"
        :key="tableName"
        class="flex-grow min-w-[42rem] flex flex-col"
      >
        <OraComponent
          :table-name="tableName"
          :existing-tables="visibleTableNames"
          :all-tables="allTables"
          :hash-loading="hashLoading"
          @openSettingsOverlay="openSettingsOverlay"
          @update:tableName="onUpdateTableName(tableName, $event)"
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
  </div>
</template>

<script setup lang="ts">
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { computed, onMounted, provide, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

import { type CatalogMeta } from "@/shared/CatalogMeta";
import { SharedColorRegistry } from "@/shared/colorMapping";
import OraComponent from "@/components/OraComponent.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import { useDatasetEmptinessFilter } from "@/shared/useDatasetEmptinessFilter";
import { beautifyLabel } from "@/shared/utils";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const showSettingsOverlay = ref(false);
const allTables = ref<Record<string, string>>({});
const hashLoading = ref(true);

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
const { visibleTableNames, hiddenTableNames } = useDatasetEmptinessFilter(tableNames);

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
async function loadStateFromIdParam(idParam: unknown) {
  hashLoading.value = true;
  if (typeof idParam !== "string" || idParam.length !== 16) {
    hashLoading.value = false;
    return;
  }
  try {
    const response = await axios.post(`${API_BASE_URL}/api/id`, { id: idParam });
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
    console.error("Error fetching filter data by ID", idParam, error);
  } finally {
    hashLoading.value = false;
  }
}

watch(
  () => route.query.id,
  (idParam) => { loadStateFromIdParam(idParam); },
  { immediate: true },
);

onMounted(async () => {
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
