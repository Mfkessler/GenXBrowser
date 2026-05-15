<template>
  <div class="w-full min-h-full bg-white border-r-1 border-gray-300">
    <!-- Action Buttons Row -->
    <div class="relative flex items-center justify-center px-4 py-3 border-b-1 border-gray-300">
      <!-- Close Sidebar Button (Left side, absolute positioned).
           Classic "X" close icon. -->
      <button
        aria-label="Close sidebar"
        :disabled="disableControls"
        class="absolute left-4 cursor-pointer font-semibold bg-transparent text-gray-700 hover:text-primary-900 disabled:opacity-50 inline-flex justify-center items-center px-2 py-1"
        @click="$emit('toggle-sidebar')"
        v-tooltip:right="'Close sidebar'"
      >
        <svg
          class="h-5 w-5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M6 6l12 12M18 6L6 18"
          />
        </svg>
      </button>

      <div class="inline-flex items-center gap-2">
        <button
          v-if="showFilterChainButton"
          aria-label="Configure filter chain"
          :disabled="disableControls"
          class="cursor-pointer rounded-md bg-transparent p-1.5 text-gray-600 hover:bg-gray-100 hover:text-gray-900 disabled:opacity-50"
          @click="filterChainOpen = true"
          v-tooltip:right="'Configure filter chain'"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 13a5 5 0 0 0 7.54.54l2-2a5 5 0 0 0-7.07-7.07l-1.15 1.15" />
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 11a5 5 0 0 0-7.54-.54l-2 2a5 5 0 0 0 7.07 7.07l1.15-1.15" />
          </svg>
        </button>

        <!-- Catalog Button (Centered) — text-only pseudo-button (icon + label, no border). -->
        <button
          aria-label="Navigate to Catalog"
          :disabled="disableControls"
          class="cursor-pointer font-semibold bg-transparent text-blue-600 hover:text-blue-800 disabled:opacity-50 inline-flex justify-center items-center gap-1 px-2 py-1 text-sm"
          @click="$emit('navigate-home')"
          v-tooltip:right="'Navigate to Catalog'"
        >
          <svg
            class="h-4 w-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M4 6h16M4 10h16M4 14h16M4 18h10"
            />
          </svg>
          <span>Catalog</span>
        </button>
      </div>
    </div>

    <GlobalFilterChainModal
      :open="filterChainOpen"
      :columns="activeRowFilterKeys"
      :filters="activeRowFilters"
      :labels="rowFilterLabels"
      @close="filterChainOpen = false"
    />

    <!-- Tabs -->
    <div class="flex whitespace-nowrap">
      <button
        :class="[
          'flex-1 px-4 py-2 bg-white cursor-pointer',
          selectedTab === 'meta'
            ? 'text-gray-700 font-bold'
            : 'border-b-1 border-r-1 border-gray-300 text-gray-400 shadow-inner',
        ]"
        :style="
          selectedTab === 'meta'
            ? ''
            : 'box-shadow: inset 1px 1px 5px 0 rgba(0,0,0,0.20)'
        "
        @click="selectedTab = 'meta'"
      >
        {{ getEntityLabelPlural() }}
      </button>
      <button
        :class="[
          'flex-1 px-4 py-2 bg-white cursor-pointer',
          selectedTab === 'columnMeta'
            ? 'text-gray-700 font-bold'
            : 'border-b-1 border-l-1 border-gray-300 text-gray-400 shadow-inner',
        ]"
        :style="
          selectedTab === 'columnMeta'
            ? ''
            : 'box-shadow: inset 1px 1px 5px 0 rgba(0,0,0,0.20)'
        "
        @click="selectedTab = 'columnMeta'"
      >
        Samples
      </button>
    </div>
    <div class="p-4 overflow-x-hidden">
      <div v-if="loading" class="text-gray-500">Loading filters...</div>
      <div v-else>
        <SearchFilter
          v-for="col in selectedTab === 'meta'
            ? filteredRowColumns
            : columnsStore.filterableColColumns"
          :key="col.column_name"
          v-model="filters[col.column_name]"
          :label="getDisplayName(col.column_name, col.display_name)"
          :description="col.description"
          :type="col.type"
          :id="col.column_name"
          :ref="
            (el) => {
              setSearchFilterRef(col.column_name, el);
            }
          "
        ></SearchFilter>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import axios from "axios";
import { debounce } from "lodash-es";
import { inject, nextTick, onMounted, ref, watch, computed } from "vue";
import { useRoute } from "vue-router";

import { useColumnsStore } from "@/stores/columns";
import { API_BASE_URL, type Config } from "@/shared/Config";
import { useFiltersStore, type FilterValue } from "@/stores/filters";
import SearchFilter from "./SearchFilter.vue";
import GlobalFilterChainModal from "./GlobalFilterChainModal.vue";
import { getEntityLabelPlural } from "@/shared/dataTypeLabels";
import { getDisplayName } from "@/shared/metadataDisplayNames";

const config = inject("config") as Config;

defineProps<{
  disableControls?: boolean;
}>();

defineEmits<{
  'toggle-sidebar': [];
  'navigate-home': [];
}>();

const route = useRoute();
const filtersStore = useFiltersStore();
const columnsStore = useColumnsStore();

// Get current table name from route
const currentTableName = computed(() => {
  const param = route.params.table_names;
  if (typeof param === "string") {
    // Take first table if multiple are selected
    return param.split(",")[0];
  }
  return null;
});

const selectedTab = ref<"meta" | "columnMeta">("meta");
const loading = ref(true);
const filters = ref<Record<string, FilterValue>>({ ...filtersStore.filters });
const filterChainOpen = ref(false);

// Columns filtered to exclude the transcript/gene ID column (handled per-dataset in cards)
const filteredRowColumns = computed(() =>
  columnsStore.rowColumns.filter((col) => col.column_name !== config.visualization.id_column)
);

const rowFilterColumnNames = computed(() => new Set(filteredRowColumns.value.map((col) => col.column_name)));

const activeRowFilters = computed(() => Object.fromEntries(
  Object.entries(filtersStore.filters).filter(([key, filter]) => (
    rowFilterColumnNames.value.has(key) && filter && String(filter.value ?? "").trim() !== ""
  )),
));

const activeRowFilterKeys = computed(() => Object.keys(activeRowFilters.value));
const showFilterChainButton = computed(() => activeRowFilterKeys.value.length >= 2);
const rowFilterLabels = computed(() => Object.fromEntries(
  filteredRowColumns.value.map((col) => [col.column_name, col.display_name]),
));

interface SearchFilterExpose {
  collapse?: () => void;
  uncollapse?: () => void;
  reset?: () => void;
}

const searchFilterRefs = ref<Record<string, SearchFilterExpose>>({});

function setSearchFilterRef(columnName: string, refInstance: unknown) {
  if (refInstance && typeof refInstance === "object") {
    searchFilterRefs.value[columnName] = refInstance as SearchFilterExpose;
  }
}

// Guard to prevent infinite loop between store sync and auto-apply watchers
let syncingFromStore = false;

function cleanFilters(
  filters: Record<string, FilterValue>,
): Record<string, FilterValue> {
  return Object.fromEntries(
    Object.entries(filters).filter(([, v]) => v && v.value !== ""),
  );
}

function isFilterEmpty(filter?: FilterValue): boolean {
  return !filter || filter.value === "";
}

// Auto-apply: push local filter changes to the store with a debounce
const autoApplyFilters = debounce(() => {
  const cleaned = cleanFilters(filters.value);
  filtersStore.setFilters(cleaned);

  // Collapse all SearchFilters where the filter is not set
  for (const col of columnsStore.allColumns) {
    const filterVal = filters.value[col.column_name];
    const refInstance = searchFilterRefs.value[col.column_name];
    if (refInstance && isFilterEmpty(filterVal)) {
      refInstance.collapse();
    }
  }
}, 500);

async function fetchColumns() {
  try {
    const metaResponse = await axios.get(
      `${API_BASE_URL}/api/columns`,
      {
        params: {
          meta: true,
          columns: false,
        },
      },
    );

    const columnMetaResponse = await axios.get(
      `${API_BASE_URL}/api/columns`,
      {
        params: {
          columns: true,
        },
      },
    );

    columnsStore.setRowColumns(metaResponse.data);
    columnsStore.setColColumns(columnMetaResponse.data);
    
    // fetchTissueValues will be called by the watch on currentTableName
  } catch {
    columnsStore.setRowColumns([]);
    columnsStore.setColColumns([]);
  } finally {
    loading.value = false;
  }
}

// Helper function to extract unique tissue values from metadata
function extractTissueValues(data: Record<string, unknown>[], tissueColName: string): string[] {
  const values = data
    .map(item => item[tissueColName])
    .filter(Boolean);
  return [...new Set(values.map(String))].sort();
}

async function fetchTissueValuesForAllTables() {
  const tissueColName = columnsStore.tissueColumnName;
  if (!tissueColName) return;
  
  try {
    // Get all available tables
    const tablesResponse = await axios.get(`${API_BASE_URL}/api/tables`);
    const tables = tablesResponse.data;
    
    const allTissues = new Set<string>();
    
    // Fetch tissues from each table
    for (const table of tables) {
      try {
        const response = await axios.post(`${API_BASE_URL}/api/data`, {
          table_name: table.table_name + "_meta",
          filters: {},
        });
        
        const data = response.data.data || response.data;
        if (data && typeof data === 'object') {
          const tissues = extractTissueValues(Object.values(data) as Record<string, unknown>[], tissueColName);
          tissues.forEach(t => allTissues.add(t));
        }
      } catch (err) {
        console.warn(`Could not fetch tissues for ${table.table_name}:`, err);
      }
    }
    
    const tissueArray = Array.from(allTissues).sort();
    
    if (tissueArray.length > 0) {
      columnsStore.setDistinctValues(tissueColName, tissueArray);
    }
  } catch (err) {
    console.warn("Could not fetch tissue values for all tables:", err);
  }
}

async function fetchTissueValues() {
  const tissueColName = columnsStore.tissueColumnName;
  const tableName = currentTableName.value;
  
  if (!tissueColName) return;
  
  // If no specific table, fetch from all tables (catalog page)
  if (!tableName) {
    await fetchTissueValuesForAllTables();
    return;
  }
  
  try {
    // Fetch from _meta table like CatalogEntry does
    const response = await axios.post(`${API_BASE_URL}/api/data`, {
      table_name: tableName + "_meta",
      filters: {},
    });
    
    const data = response.data.data || response.data;
    if (data && typeof data === 'object') {
      const tissues = extractTissueValues(Object.values(data) as Record<string, unknown>[], tissueColName);
      if (tissues.length > 0) {
        columnsStore.setDistinctValues(tissueColName, tissues);
      }
    }
  } catch (err) {
    console.warn("Could not fetch distinct tissue values:", err);
  }
}

// Fetch tissue values when table is available or changes
watch(currentTableName, async () => {
  if (columnsStore.tissueColumnName) {
    await fetchTissueValues();
  }
}, { immediate: true });

watch(
  () => filtersStore.filters,
  (newFilters) => {
    syncingFromStore = true;
    filters.value = { ...newFilters };

    // Uncollapse all SearchFilters which have a non-empty filter value
    for (const col of columnsStore.allColumns) {
      const filterVal = filters.value[col.column_name];
      const refInstance = searchFilterRefs.value[col.column_name];
      if (refInstance && filterVal && filterVal.value !== "") {
        refInstance.uncollapse();
      }
    }
    // Reset guard after this tick so the auto-apply watcher skips this change
    nextTick(() => { syncingFromStore = false; });
  },
  { deep: true },
);

// Auto-apply: whenever local filters change (user adds/removes pills), push to the store
watch(
  filters,
  () => {
    if (syncingFromStore) return;
    autoApplyFilters();
  },
  { deep: true },
);

onMounted(async () => {
  fetchColumns();
});
</script>
