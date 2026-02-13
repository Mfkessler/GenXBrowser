<template>
  <div class="h-[calc(100vh-7rem)] flex flex-col overflow-hidden">
    <div
      class="flex gap-4 flex-grow p-2 overflow-x-hidden overflow-y-auto"
    >
      <div
        v-for="tableName in tableNames"
        :key="tableName"
        class="flex-grow min-w-[42rem] flex flex-col"
      >
        <OraComponent
          :table-name="tableName"
          :existing-tables="tableNames"
          :all-tables="allTables"
          @openSettingsOverlay="openSettingsOverlay"
          @update:tableName="onUpdateTableName(tableName, $event)"
        />
      </div>
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
import { computed, onMounted, provide, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { type CatalogMeta } from "@/shared/CatalogMeta";
import { SharedColorRegistry } from "@/shared/colorMapping";
import OraComponent from "@/components/OraComponent.vue";
import { useFiltersStore } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import VisualizationSettings from "@/components/VisualizationSettings.vue";
import { beautifyLabel } from "@/shared/utils";

const route = useRoute();
const router = useRouter();

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();

const showSettingsOverlay = ref(false);
const allTables = ref<Record<string, string>>({});

// Shared color registry for consistent side-color mapping across multiple ORA plots
const sharedColorRegistry = new SharedColorRegistry();
provide('sharedColorRegistry', sharedColorRegistry);

const tableNames = computed(() => {
  const param = route.params.table_names;
  return typeof param === "string" ? param.split(",") : [];
});

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
        // IMPORTANT: Restore visualization state FIRST,
        // then filters. This prevents watchers from overwriting selections.
        visualizationStore.replaceState(data.visualizations);
        filtersStore.replaceState(data.filters);
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
});
</script>
