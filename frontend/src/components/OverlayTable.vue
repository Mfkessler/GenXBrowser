<template>
  <Teleport to="body">
    <div class="fixed inset-0 z-[60] items-center align-top p-6">
    <!-- Background overlay -->
    <div class="absolute inset-0 bg-black opacity-50" @click="$emit('close')"></div>

    <!-- Modal content -->
    <div
      class="relative bg-white rounded-md border-1 border-gray-300 w-full max-h-[90vh] overflow-hidden p-6 z-10 flex flex-col"
    >
      <!-- Header Row: Title + Close Button -->
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-xl font-bold text-gray-700">
          <span v-html="formattedTitle"></span>
        </h2>
        <button
          @click="$emit('close')"
          class="cursor-pointer text-gray-500 hover:text-red-600 text-2xl font-bold focus:outline-none"
          aria-label="Close"
        >
          &times;
        </button>
      </div>

      <!-- Filter Status Bar -->
      <div v-if="hasActiveSampleFilters" class="mb-4 p-3 bg-primary-50 border border-primary-200 rounded-md flex items-center justify-between">
        <div class="flex items-center gap-2 text-sm text-primary-700">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          <span>
            <strong>{{ activeSampleFilterCount }}</strong> Sample filter(s) applied
          </span>
          <span class="text-primary-500">
            → {{ filteredSampleCount }} of {{ totalSampleCount }} samples visible
          </span>
        </div>
        <button
          @click="clearSampleFilters"
          class="cursor-pointer text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded hover:bg-primary-200"
        >
          Clear Filters
        </button>
      </div>

      <!-- Control Bar -->
      <div class="flex flex-wrap items-start gap-4 mb-4 pb-4 border-b border-gray-200">
        <!-- Column Selection -->
        <div class="flex flex-col gap-1 min-w-[200px]">
          <label class="text-sm font-semibold text-gray-700">Sample Metadata</label>
          <div class="relative">
            <button
              @click="showColumnDropdown = !showColumnDropdown"
              class="cursor-pointer w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-left flex justify-between items-center"
            >
              <span class="truncate">{{ visibleColumns.length }} of {{ availableColumns.length }} selected</span>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            <div
              v-if="showColumnDropdown"
              class="absolute z-20 mt-1 w-72 max-h-60 overflow-y-auto bg-white border border-gray-300 rounded-md shadow-lg"
            >
              <div class="p-2 border-b border-gray-200 flex gap-2">
                <button
                  @click="selectAllColumns"
                  class="cursor-pointer text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded hover:bg-primary-200"
                >
                  Select All
                </button>
                <button
                  @click="clearColumns"
                  class="cursor-pointer text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  Clear
                </button>
              </div>
              <label
                v-for="col in selectableColumns"
                :key="col"
                class="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :value="col"
                  v-model="selectedColumns"
                  class="rounded text-primary-600"
                />
                <span class="text-sm truncate">{{ getColumnDisplayName(col) }}</span>
              </label>
            </div>
          </div>
        </div>

        <!-- Sample ID Search -->
        <div class="flex flex-col gap-1 flex-1 min-w-[300px]">
          <label class="text-sm font-semibold text-gray-700">Search Sample IDs (comma, space, or newline separated)</label>
          <div class="flex gap-2">
            <textarea
              v-model="searchInput"
              @input="onSearchInput"
              placeholder="Enter sample IDs or paste list..."
              class="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500 resize-none"
              rows="2"
            ></textarea>
            <template v-if="searchInput">
              <button
                @click="clearSearch"
                class="cursor-pointer px-3 py-2 border border-gray-300 rounded-md hover:bg-gray-100"
                aria-label="Clear Search"
                v-tooltip="'Clear Search'"
              >
                <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </template>
          </div>
          <span v-if="parsedSampleIds.length > 0" class="text-xs text-gray-500">
            {{ parsedSampleIds.length }} sample IDs parsed
          </span>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-col gap-1 justify-end">
          <label class="text-sm font-semibold text-gray-700">&nbsp;</label>
          <div class="flex gap-2">
            <button
              @click="handleExport"
              :disabled="filteredRows.length === 0 || exporting"
              class="cursor-pointer px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 flex items-center gap-2"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              Export
            </button>
            <button
              @click="resetSettings"
              class="cursor-pointer px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-100"
              aria-label="Reset settings"
              v-tooltip="'Reset settings'"
            >
              Reset
            </button>
          </div>
        </div>
      </div>

      <!-- Info Bar with Pagination -->
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm text-gray-600">
          <template v-if="loading">
            Loading data...
          </template>
          <template v-else-if="filteredRows.length > 0">
            Showing {{ paginatedRows.length }} of {{ filteredRows.length }} samples
            <span v-if="parsedSampleIds.length > 0 || hasActiveSampleFilters" class="text-primary-600">(filtered)</span>
          </template>
          <template v-else>
            No data available
          </template>
        </span>

        <!-- Pagination Controls -->
        <div
          v-if="showPagination"
          class="flex items-center gap-2"
        >
          <!-- Left Arrow -->
          <span v-tooltip="page === 1 ? 'Already on first page' : 'Previous Page'">
            <button
              :disabled="page === 1"
              @click="goToPage(page - 1)"
              class="cursor-pointer px-2 py-2 rounded-full text-primary-700 hover:bg-primary-100 border-1 border-primary-300 disabled:opacity-50"
              aria-label="Previous Page"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
          </span>

          <!-- Previous Page Number -->
          <button
            v-if="page > 1"
            @click="goToPage(page - 1)"
            class="cursor-pointer px-3 py-2 rounded-md text-primary-700 hover:bg-primary-100 font-semibold"
          >
            {{ page - 1 }}
          </button>

          <!-- Current Page Number -->
          <span
            class="px-3 py-2 rounded-md text-primary-700 bg-primary-100 border-1 border-primary-300 font-bold"
          >{{ page }}</span>

          <!-- Next Page Number -->
          <button
            v-if="hasNextPage"
            @click="goToPage(page + 1)"
            class="cursor-pointer px-3 py-2 rounded-md text-primary-700 hover:bg-primary-100 font-semibold"
          >
            {{ page + 1 }}
          </button>

          <!-- Right Arrow -->
          <span v-tooltip="!hasNextPage ? 'Already on last page' : 'Next Page'">
            <button
              :disabled="!hasNextPage"
              @click="goToPage(page + 1)"
              class="cursor-pointer px-2 py-2 rounded-full text-primary-700 hover:bg-primary-100 border-1 border-primary-300 disabled:opacity-50"
              aria-label="Next Page"
            >
              <svg
                class="w-5 h-5"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M9 5l7 7-7 7"
                />
              </svg>
            </button>
          </span>
        </div>
      </div>

      <!-- Data Table -->
      <div class="overflow-auto max-h-[55vh] border border-gray-300 rounded-md">
        <LoadingOverlay v-if="loading" size="md" />
        <table v-else-if="paginatedRows.length > 0" class="text-sm text-left text-gray-700 table-fixed w-full">
          <thead class="text-xs text-gray-700 uppercase bg-gray-50 sticky top-0">
            <tr>
              <th
                v-for="col in visibleColumns"
                :key="col"
                scope="col"
                class="px-3 py-2 whitespace-nowrap text-left min-w-[120px] max-w-[250px]"
              >
                {{ getColumnDisplayName(col) }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in paginatedRows"
              :key="idx"
              class="border-b hover:bg-gray-100 bg-white"
            >
              <td
                v-for="col in visibleColumns"
                :key="col"
                class="px-3 py-2 text-left min-w-[120px] max-w-[250px] truncate"
                :title="formatCellValue(row[col])"
                v-html="formatCellDisplay(row[col])"
              >
              </td>
            </tr>
          </tbody>
        </table>
        <div v-else class="h-[50vh] flex items-center justify-center bg-white">
          <div class="text-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              class="h-12 w-12 mx-auto mb-4 text-gray-700"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
              />
            </svg>
            <p class="text-lg font-semibold text-gray-700">No Data Found</p>
            <p class="text-sm text-gray-700">
              Please try different search criteria
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Export Modal -->
      <ExportModal
        v-if="showExportModal"
        :data="exportData"
        :columns="exportColumns"
        :columnDisplayNames="exportColumnDisplayNames"
        :metaColumns="visibleColumns"
        :sampleColumns="[]"
        :filename="`${tableName}_metadata`"
        :hasFilters="parsedSampleIds.length > 0 || hasActiveSampleFilters"
        :totalCount="filteredRows.length"
        row-label="samples"
        @close="showExportModal = false"
      />
    </div>
  </Teleport>
</template>
<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, onUnmounted, ref, watch, nextTick } from "vue";
import type { RowType } from "@/shared/RowType";
import { beautifyLabel, formatSpeciesValue, isCellEmpty } from "@/shared/utils";
import { useFiltersStore } from "@/stores/filters";
import { useColumnsStore } from "@/stores/columns";
import ExportModal from "./ExportModal.vue";
import LoadingOverlay from "./LoadingOverlay.vue";

const props = defineProps<{
  endpoint: string;
  type: "data" | "metadata";
  filters?: Record<string, unknown>;
  title?: string;
}>();

defineEmits(["close"]);

const filtersStore = useFiltersStore();
const columnsStore = useColumnsStore();

// Extract table name from title (e.g., "capnoides_sempervirens Metadata" -> "capnoides_sempervirens")
const tableName = computed(() => {
  if (!props.title) return 'metadata';
  return props.title.replace(/\s+Metadata$/i, '').toLowerCase();
});

// Format species name for display with italics and green text
function formatSpeciesName(name: string): string {
  // Remove underscores and capitalize properly
  const parts = name.split('_');
  if (parts.length >= 2) {
    const genus = parts[0].charAt(0).toUpperCase() + parts[0].slice(1).toLowerCase();
    const species = parts[1].toLowerCase();
    return `<span class="text-green-600 italic font-semibold">${genus} ${species}</span>`;
  }
  return name;
}

// Formatted title for display
const formattedTitle = computed(() => {
  if (!props.title) return '';
  const speciesName = tableName.value;
  return `${formatSpeciesName(speciesName)} <span class="text-gray-700">- Sample Manager</span>`;
});

const storageKey = computed(() => `metadataModal_${tableName.value}`);

// State
const allRows = ref<RowType[]>([]);
const allColumns = ref<string[]>([]);
const selectedColumns = ref<string[]>([]);
const searchInput = ref("");
const parsedSampleIds = ref<string[]>([]);
const loading = ref(false);
const showColumnDropdown = ref(false);
const showExportModal = ref(false);
const exporting = ref(false);
const resetting = ref(false);
const totalSamplesWithoutFilters = ref<number>(0); // Track total before filtering

// Compute sample filters (sample metadata columns only)
// For metadata tables (_meta), samples are ROWS and we filter them using sample_filters
const sampleFilters = computed(() => {
  const sampleColNames = new Set(columnsStore.filterableColColumns.map(c => c.column_name));
  return Object.fromEntries(
    Object.entries(filtersStore.filters).filter(([key]) => sampleColNames.has(key))
  );
});

// Filter status
const activeSampleFilterCount = computed(() => Object.keys(sampleFilters.value).length);
const hasActiveSampleFilters = computed(() => activeSampleFilterCount.value > 0);

// Sample counts for filter display
const totalSampleCount = computed(() => totalSamplesWithoutFilters.value || allRows.value.length);
const filteredSampleCount = computed(() => {
  // Backend returns filtered data, so allRows is already filtered
  return allRows.value.length;
});

// No need for client-side filtering - backend returns filtered data
const filteredByFilters = computed(() => allRows.value);

// Pagination state - 20 rows per page
const limit = 20;
const page = ref(1);

// Column name mappings
// Columns to hide
const HIDDEN_COLUMNS = new Set<string>(['type', 'ismeta']);

// RNA metrics columns
const RNA_METRICS = ['assigned', 'pct_unmapped', 'pct_no_feature', 'pct_trimmed'];

// Get available columns (non-empty, non-hidden)
const availableColumns = computed(() => {
  return allColumns.value.filter(col => {
    if (col === sampleIdColumn.value) return true;
    // Don't hide if it's one of our important columns
    if (HIDDEN_COLUMNS.has(col.toLowerCase())) return false;
    
    // Check if column is completely empty
    const allEmpty = allRows.value.every(row => isCellEmpty(row[col]));
    return !allEmpty;
  });
});

// Get first column name (sample ID column)
const sampleIdColumn = computed(() => allColumns.value[0] || 'sample_id');

// Visible columns for display
const visibleColumns = computed(() => {
  const visible = selectedColumns.value.filter(col => availableColumns.value.includes(col));
  if (!visible.includes(sampleIdColumn.value) && availableColumns.value.includes(sampleIdColumn.value)) {
    return [sampleIdColumn.value, ...visible];
  }
  return visible;
});

const selectableColumns = computed(() => availableColumns.value.filter(col => col !== sampleIdColumn.value));

// Filter rows based on search
const filteredRows = computed(() => {
  // First apply sample filters from sidebar
  const rows = filteredByFilters.value;
  
  // Then apply search filter
  if (parsedSampleIds.value.length === 0) {
    return rows;
  }
  
  const searchSet = new Set(parsedSampleIds.value.map(id => id.toLowerCase()));
  return rows.filter(row => {
    const sampleId = String(row[sampleIdColumn.value] || '').toLowerCase();
    return searchSet.has(sampleId);
  });
});

// Paginated rows
const paginatedRows = computed(() => {
  const start = (page.value - 1) * limit;
  const end = start + limit;
  return filteredRows.value.slice(start, end);
});

// Pagination logic
const hasNextPage = computed(() => {
  return filteredRows.value.length > page.value * limit;
});

const showPagination = computed(() => {
  return filteredRows.value.length > limit;
});

function goToPage(newPage: number) {
  if (newPage < 1) return;
  if (newPage > Math.ceil(filteredRows.value.length / limit)) return;
  page.value = newPage;
}

// Export data
const exportData = computed(() => filteredRows.value);
const exportColumns = computed(() => visibleColumns.value);

// Export column display names mapping
const exportColumnDisplayNames = computed(() => {
  const mapping: Record<string, string> = {};
  for (const col of visibleColumns.value) {
    mapping[col] = getColumnDisplayName(col);
  }
  return mapping;
});

// Column display helpers
function getColumnDisplayName(col: string): string {
  // Special handling for first column (Sample ID)
  if (col === sampleIdColumn.value) {
    return 'SAMPLE ID';
  }

  const configuredColumn = columnsStore.filterableColColumns.find(c => c.column_name === col)
    ?? columnsStore.colColumns.find(c => c.column_name === col);
  if (configuredColumn?.display_name) {
    return beautifyLabel(configuredColumn.display_name);
  }
  
  // Use beautifyLabel for other columns
  return beautifyLabel(col);
}

// Format cell value for tooltip (full value)
function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

// Format cell value for display (truncated if needed, with species formatting)
function formatCellDisplay(value: unknown): string {
  if (value === null || value === undefined) return '';
  
  // Format species names if present
  const formatted = formatSpeciesValue(value);
  
  // Truncate if too long
  if (formatted.length > 40) {
    // If it contains HTML tags, don't truncate in the middle of a tag
    if (formatted.includes('<em>')) {
      return formatted; // Keep full formatting for species names
    }
    return formatted.substring(0, 37) + '...';
  }
  
  return formatted;
}

// Search handling
function onSearchInput() {
  const input = searchInput.value.trim();
  if (!input) {
    parsedSampleIds.value = [];
    return;
  }
  parsedSampleIds.value = input
    .split(/[,\s\n\t]+/)
    .map((id) => id.trim())
    .filter((id) => id.length > 0);
  
  // Reset to first page when search changes
  page.value = 1;
}

function clearSearch() {
  searchInput.value = "";
  parsedSampleIds.value = [];
  page.value = 1;
}

// Clear sample filters
function clearSampleFilters() {
  // Only clear sample filters, not transcript filters
  const sampleColNames = new Set(columnsStore.filterableColColumns.map(c => c.column_name));
  for (const key of Object.keys(filtersStore.filters)) {
    if (sampleColNames.has(key)) {
      filtersStore.removeFilter(key);
    }
  }
  page.value = 1;
}

// Column selection
function selectAllColumns() {
  selectedColumns.value = [...selectableColumns.value];
  saveSettings();
}

function clearColumns() {
  selectedColumns.value = [];
  saveSettings();
}

// Export handling
async function handleExport() {
  exporting.value = true;
  // Small delay to show loading state
  await new Promise(resolve => setTimeout(resolve, 100));
  showExportModal.value = true;
  exporting.value = false;
}

// Reset to defaults
async function resetSettings() {
  resetting.value = true;
  localStorage.removeItem(storageKey.value);
  searchInput.value = "";
  parsedSampleIds.value = [];
  page.value = 1;
  setDefaultColumns();
  // Wait for Vue to finish reactive updates
  await nextTick();
  resetting.value = false;
}

// Settings persistence
function saveSettings() {
  const settings = {
    selectedColumns: selectedColumns.value,
  };
  localStorage.setItem(storageKey.value, JSON.stringify(settings));
}

function loadSettings() {
  resetting.value = true;
  const saved = localStorage.getItem(storageKey.value);
  if (saved) {
    try {
      const settings = JSON.parse(saved);
      // Validate columns still exist
      const validCols = new Set(selectableColumns.value);
      selectedColumns.value = (settings.selectedColumns || []).filter(
        (col: string) => validCols.has(col)
      );
      
      // If no valid columns, use defaults
      if (selectedColumns.value.length === 0) {
        setDefaultColumns();
      }
    } catch {
      setDefaultColumns();
    }
  } else {
    setDefaultColumns();
  }
  resetting.value = false;
}

function setDefaultColumns() {
  // Default: configured sample metadata + RNA metrics. Sample ID is always visible.
  const primarySampleColumn = columnsStore.tissueColumnName || 'tissue';
  const defaults = [
    primarySampleColumn,
    ...RNA_METRICS
  ];
  
  selectedColumns.value = defaults.filter(col => availableColumns.value.includes(col));
  
  // If we don't have enough columns, add more up to 6 columns
  if (selectedColumns.value.length < 6) {
    for (const col of selectableColumns.value) {
      if (!selectedColumns.value.includes(col) && selectedColumns.value.length < 6) {
        selectedColumns.value.push(col);
      }
    }
  }
  
  // Save settings after setting defaults (unless resetting)
  if (!resetting.value) {
    saveSettings();
  }
}

// Fetch total count without filters
async function fetchTotalCount() {
  try {
    // Fetch without sample filters to get total count
    const requestBody: Record<string, unknown> = {
      table_name: props.filters?.table_name,
      columns: props.filters?.columns || [],
      // No sample_filters here to get total unfiltered count
    };
    
    const response = await axios.post(props.endpoint, requestBody);
    const responseData = response.data;
    const rowData = Array.isArray(responseData) ? responseData : (responseData?.data ?? []);
    totalSamplesWithoutFilters.value = rowData.length;
  } catch (e) {
    console.error("Error fetching total count:", e);
  }
}

// Fetch data
async function fetchData() {
  loading.value = true;
  
  try {
    // Build request body with sample filters from sidebar
    // For metadata tables, use sample_filters like Data Manager does
    const requestBody: Record<string, unknown> = {
      table_name: props.filters?.table_name,
      columns: props.filters?.columns || [],
      sample_filters: sampleFilters.value,  // Sample filters for metadata table rows
    };
    
    const response = await axios.post(props.endpoint, requestBody);
    const responseData = response.data;
    const rowData = Array.isArray(responseData) ? responseData : (responseData?.data ?? []);
    
    allRows.value = rowData.map((row: RowType) => {
      const cleaned: RowType = {};
      for (const [key, value] of Object.entries(row)) {
        if (!HIDDEN_COLUMNS.has(key.toLowerCase())) cleaned[key] = value;
      }
      return cleaned;
    });
    
    // Extract columns from first row
    if (allRows.value.length > 0) {
      const newColumns = Object.keys(allRows.value[0]).filter(col => !HIDDEN_COLUMNS.has(col.toLowerCase()));
      // Only load settings on first load or when columns change
      if (allColumns.value.length === 0 || JSON.stringify(allColumns.value) !== JSON.stringify(newColumns)) {
        allColumns.value = newColumns;
        loadSettings();
      }
    }
    
    // Fetch total count on first load (when we have no filters yet)
    if (totalSamplesWithoutFilters.value === 0 && Object.keys(sampleFilters.value).length === 0) {
      totalSamplesWithoutFilters.value = allRows.value.length;
    } else if (totalSamplesWithoutFilters.value === 0) {
      // If filters are active on first load, fetch total separately
      fetchTotalCount();
    }
  } catch (e) {
    console.error("Error fetching metadata:", e);
    allRows.value = [];
    allColumns.value = [];
  } finally {
    loading.value = false;
  }
}

// Close dropdown when clicking outside
function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (!target.closest(".relative")) {
    showColumnDropdown.value = false;
  }
}

// Watch for column selection changes
watch(selectedColumns, () => {
  if (!resetting.value) {
    saveSettings();
  }
}, { deep: true });

// Watch for search changes to reset pagination
watch(parsedSampleIds, () => {
  page.value = 1;
});

// Watch for filter changes to refetch
watch(
  () => props.filters,
  () => {
    page.value = 1;
    fetchData();
  },
  { deep: true }
);

// Watch for sample filter changes to refetch
watch(
  sampleFilters,
  () => {
    page.value = 1;
    fetchData();
  },
  { deep: true }
);

onMounted(() => {
  document.addEventListener("click", handleClickOutside);
  fetchData();
});

onUnmounted(() => {
  document.removeEventListener("click", handleClickOutside);
});
</script>
