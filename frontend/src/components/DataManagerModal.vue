<template>
  <div class="fixed inset-0 z-50 items-center align-top p-6" :style="managerOverlayStyle">
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
      <div v-if="hasActiveFilters" class="mb-4 p-3 bg-primary-50 border border-primary-200 rounded-md flex items-center justify-between">
        <div class="flex items-center gap-2 text-sm text-primary-700">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
          </svg>
          <span>
            <strong>{{ activeGeneFilterCount }}</strong> {{ entityLabel }} filter(s), 
            <strong>{{ activeSampleFilterCount }}</strong> Sample filter(s) applied
          </span>
          <span class="text-primary-500">
            → {{ filteredSampleColumns.length }} of {{ allSampleColumns.length }} samples visible
          </span>
        </div>
        <button
          @click="clearAllFilters"
          class="cursor-pointer text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded hover:bg-primary-200"
        >
          Clear Filters
        </button>
      </div>

      <!-- Control Bar -->
      <div class="flex flex-wrap items-start gap-4 mb-4 pb-4 border-b border-gray-200">
        <!-- Metadata Column Selection -->
        <div class="flex flex-col gap-1 min-w-[200px]">
          <label class="text-sm font-semibold text-gray-700">{{ entityLabel }} Metadata</label>
          <div class="relative">
            <button
              @click="showColumnDropdown = !showColumnDropdown"
              class="cursor-pointer w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-left flex justify-between items-center"
            >
              <span class="truncate">{{ selectedMetaColumns.length }} of {{ availableMetaColumns.length }} selected</span>
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
                  @click="selectAllMetaColumns"
                  class="cursor-pointer text-xs px-2 py-1 bg-primary-100 text-primary-700 rounded hover:bg-primary-200"
                >
                  Select All
                </button>
                <button
                  @click="clearMetaColumns"
                  class="cursor-pointer text-xs px-2 py-1 bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
                >
                  Clear
                </button>
              </div>
              <label
                v-for="col in availableMetaColumns"
                :key="col.column_name"
                class="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer"
              >
                <input
                  type="checkbox"
                  :value="col.column_name"
                  v-model="selectedMetaColumns"
                  class="rounded text-primary-600"
                />
                <span class="text-sm truncate">{{ col.display_name || formatColumnName(col.column_name) }}</span>
              </label>
            </div>
          </div>
        </div>

        <!-- Count Matrix Toggle -->
        <div class="flex flex-col gap-1 min-w-[150px]">
          <label class="text-sm font-semibold text-gray-700">Data Display</label>
          <label class="flex items-center gap-2 px-3 py-2 border border-gray-300 rounded-md bg-white cursor-pointer hover:bg-gray-50">
            <input
              type="checkbox"
              v-model="showCountMatrix"
              class="rounded text-primary-600"
            />
            <span class="text-sm">Count Matrix</span>
          </label>
        </div>

        <!-- Layer Selection -->
        <div v-if="showCountMatrix" class="flex flex-col gap-1 min-w-[200px]">
          <label class="text-sm font-semibold text-gray-700">Expression Layer</label>
          <select
            v-model="selectedLayer"
            class="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-primary-500 focus:border-primary-500"
          >
            <optgroup
              v-for="section in EXPRESSION_SECTIONS"
              :key="section.label"
              :label="section.label.replace(/—/g, '').trim()"
            >
              <option
                v-for="optId in section.optionIds"
                :key="optId"
                :value="optId"
              >
                {{ getExpressionOption(optId)?.label }}
              </option>
            </optgroup>
          </select>
        </div>

        <!-- Gene ID Search -->
        <div class="flex flex-col gap-1 flex-1 min-w-[300px]">
          <label class="text-sm font-semibold text-gray-700">Search {{ entityLabel }} IDs (comma, space, or newline separated)</label>
          <div class="flex gap-2">
            <textarea
              v-model="searchInput"
              @input="onSearchInput"
              :placeholder="`Enter ${entityLabelLower} IDs or paste list...`"
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
          <span v-if="parsedGeneIds.length > 0" class="text-xs text-gray-500">
            {{ parsedGeneIds.length }} {{ entityLabelLower }} IDs parsed
          </span>
        </div>

        <!-- Action Buttons -->
        <div class="flex flex-col gap-1 justify-end">
          <label class="text-sm font-semibold text-gray-700">&nbsp;</label>
          <div class="flex gap-2">
            <button
              @click="handleExport"
              :disabled="totalCount === 0 || loading || exporting"
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
                aria-label="Reset settings and clear filters"
                v-tooltip="'Reset settings and clear filters'"
              >
                Reset
              </button>
          </div>
        </div>
      </div>

      <!-- Info Bar -->
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm text-gray-600">
          <template v-if="totalCount > 0">
            Showing {{ Math.min(rows.length, totalCount) }} of {{ totalCount }} {{ entityLabelPlural.toLowerCase() }}
            <span v-if="hasActiveFilters || parsedGeneIds.length > 0" class="text-primary-600">(filtered)</span>
          </template>
          <template v-else-if="loading">
            Loading data...
          </template>
          <template v-else>
            No data available
          </template>
        </span>
        
        <!-- Lazy load indicator -->
        <span v-if="hasMoreData && !loading" class="text-xs text-gray-400">
          Scroll down to load more...
        </span>
      </div>

      <!-- Data Table with Virtual Scrolling -->
      <div 
        ref="tableContainer"
        class="flex-1 overflow-auto border border-gray-300 rounded-md"
        @scroll="onScroll"
      >
        <table v-if="rows.length > 0" class="text-sm text-left text-gray-700 w-full">
          <thead class="text-xs text-gray-700 uppercase bg-gray-50 sticky top-0 z-10">
            <tr>
              <!-- Entity ID Column (always first) -->
              <th class="px-3 py-2 whitespace-nowrap min-w-[150px] max-w-[250px] bg-gray-50">
                <div class="flex items-center gap-1">
                  <span>{{ entityIdLabel }}</span>
                  <button
                    @click="copyColumnValues('gene_id')"
                    :disabled="copyLoading === 'gene_id'"
                    :class="[
                      'cursor-pointer p-1 rounded transition-colors',
                      copyFeedback === 'gene_id' 
                        ? 'text-green-600 bg-green-50' 
                        : copyLoading === 'gene_id'
                          ? 'text-gray-300'
                          : 'text-gray-400 hover:text-primary-600 hover:bg-primary-50'
                    ]"
                    aria-label="Copy column values"
                    v-tooltip="!copyLoading && !copyFeedback ? `Copy all ${entityIdLabel} values (${totalCount})` : ''"
                  >
                    <!-- Loading spinner -->
                    <svg v-if="copyLoading === 'gene_id'" class="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                    </svg>
                    <!-- Checkmark icon when copied -->
                    <svg v-else-if="copyFeedback === 'gene_id'" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <!-- Copy icon -->
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                  </button>
                </div>
              </th>
              <!-- Selected Metadata Columns -->
              <th
                v-for="col in selectedMetaColumns"
                :key="col"
                class="px-3 py-2 whitespace-nowrap min-w-[100px] max-w-[200px] bg-gray-50"
              >
                <div class="flex items-center gap-1">
                  <span>{{ getMetaColumnDisplayName(col) }}</span>
                  <InfoTooltip
                    v-if="col === 'rna_seq'"
                    title="cDNA Sequence"
                    description="Complementary DNA derived from mRNA. Lowercase letters indicate repetitive sequences (soft-masked regions)."
                  />
                  <button
                    @click="copyColumnValues(col)"
                    :disabled="copyLoading === col"
                    :class="[
                      'cursor-pointer p-1 rounded transition-colors',
                      copyFeedback === col 
                        ? 'text-green-600 bg-green-50' 
                        : copyLoading === col
                          ? 'text-gray-300'
                          : 'text-gray-400 hover:text-primary-600 hover:bg-primary-50'
                    ]"
                    aria-label="Copy column values"
                    v-tooltip="!copyLoading && !copyFeedback ? `Copy all ${getMetaColumnDisplayName(col)} values (${totalCount})` : ''"
                  >
                    <!-- Loading spinner -->
                    <svg v-if="copyLoading === col" class="animate-spin h-3.5 w-3.5" fill="none" viewBox="0 0 24 24">
                      <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                      <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
                    </svg>
                    <!-- Checkmark icon when copied -->
                    <svg v-else-if="copyFeedback === col" xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <polyline points="20 6 9 17 4 12"></polyline>
                    </svg>
                    <!-- Copy icon -->
                    <svg v-else xmlns="http://www.w3.org/2000/svg" class="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                    </svg>
                  </button>
                </div>
              </th>
              <!-- Sample Expression Columns (filtered) -->
              <th
                v-for="sample in filteredSampleColumns"
                :key="sample"
                class="px-3 py-2 whitespace-nowrap min-w-[80px] max-w-[120px] bg-gray-100"
              >
                {{ sample }}
              </th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="(row, idx) in rows"
              :key="idx"
              class="border-b hover:bg-gray-100 bg-white"
            >
              <!-- Entity ID -->
              <td class="px-3 py-2 min-w-[150px] max-w-[250px] truncate font-mono text-xs" :title="String(row.gene_id)">
                {{ row.gene_id }}
              </td>
              <!-- Metadata Columns -->
              <td
                v-for="col in selectedMetaColumns"
                :key="col"
                class="px-3 py-2 min-w-[100px] max-w-[200px] truncate"
                :title="formatCellValue(row[col])"
              >
                <!-- BLAST-able sequence columns -->
                <span
                  v-if="isBlastableSequence(col) && row[col] && row[col] !== '[BLOB]'"
                  @click="openBlast(col, formatCellValue(row[col]))"
                  class="cursor-pointer text-blue-600 hover:text-blue-800 hover:underline flex items-center gap-1"
                  role="button"
                  tabindex="0"
                  aria-label="Click to BLAST sequence"
                  v-tooltip="'Click to BLAST this sequence'"
                >
                  <span class="text-xs">🧬</span>
                  <span class="truncate">{{ formatCellDisplay(row[col]) }}</span>
                </span>
                <!-- Regular columns with species formatting -->
                <span v-else v-html="formatCellDisplay(row[col])"></span>
              </td>
              <!-- Sample Expression Values (filtered) -->
              <td
                v-for="sample in filteredSampleColumns"
                :key="sample"
                class="px-3 py-2 min-w-[80px] max-w-[120px] text-right font-mono text-xs bg-gray-50"
                :title="formatCellValue(row[sample])"
              >
                {{ formatNumber(row[sample]) }}
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Initial loading space; the single modal-level overlay is rendered below. -->
        <div v-if="loading && rows.length === 0" class="h-[300px]"></div>

        <!-- Loading more indicator -->
        <div v-if="loading && currentOffset > 0" class="py-4 flex items-center justify-center bg-gray-50">
          <svg class="animate-spin h-5 w-5 text-primary-500 mr-2" fill="none" viewBox="0 0 24 24">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
          </svg>
          <span class="text-sm text-gray-500">Loading more...</span>
        </div>

        <!-- Error State -->
        <div v-if="error && rows.length === 0" class="h-[300px] flex items-center justify-center text-red-500">
          <div class="text-center">
            <svg class="h-12 w-12 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <p class="font-medium">{{ error }}</p>
          </div>
        </div>
      </div>

      <LoadingOverlay
        v-if="initialLoading || (loading && currentOffset === 0)"
        size="md"
        primaryStatus="Loading data..."
        currentPhaseHint="Preparing Data Manager"
      />

      <LoadingOverlay
        v-if="exporting"
        size="md"
        primaryStatus="Loading export data..."
        currentPhaseHint="Fetching all matching rows for export"
        cancellable
        @cancel="cancelExportFetch"
      />
    </div>

    <!-- Export Modal -->
    <ExportModal
      v-if="showExportModal"
      :data="allExportData"
      :columns="exportColumns"
      :columnDisplayNames="exportColumnDisplayNames"
      :metaColumns="selectedMetaColumns"
      :sampleColumns="filteredSampleColumns"
      :filename="props.tableName + '_export'"
      :hasFilters="hasActiveFilters || parsedGeneIds.length > 0"
      :totalCount="totalCount"
      @close="showExportModal = false"
    />
  </div>
  
  <!-- BLAST Warning Modal (teleported to body for proper positioning) -->
  <Teleport to="body">
    <BlastWarningModal
      :show="showBlastWarning"
      :field-type="pendingBlastParams?.fieldType"
      @proceed="proceedWithBlast"
      @cancel="cancelBlast"
    />
  </Teleport>
</template>

<script setup lang="ts">
import axios from "axios";
import { ref, computed, watch, onMounted, onUnmounted, inject, nextTick, type Ref } from "vue";

import { API_BASE_URL } from "@/shared/Config";
import {
  EXPRESSION_SECTIONS,
  getExpressionOption,
} from "@/shared/ExpressionDisplay";
import { 
  getEntityLabel, 
  getEntityLabelPlural, 
  getEntityLabelLower, 
  getEntityIdLabel 
} from "@/shared/dataTypeLabels";
import { beautifyLabel, formatSpeciesValue } from "@/shared/utils";
import { useFiltersStore } from "@/stores/filters";
import { useColumnsStore } from "@/stores/columns";
import type { RowType } from "@/shared/RowType";
import { isBlastableSequence, openBlast as openBlastUtil } from "@/shared/blast";
import type { BlastDatabase } from "@/shared/blast";
import ExportModal from "./ExportModal.vue";
import LoadingOverlay from "./LoadingOverlay.vue";
import BlastWarningModal from "./BlastWarningModal.vue";
import InfoTooltip from "./InfoTooltip.vue";

const props = defineProps<{
  tableName: string;
  title: string;
}>();

defineEmits(["close"]);

const filtersStore = useFiltersStore();
const columnsStore = useColumnsStore();

// Dynamic labels based on VITE_DATA_TYPE
const entityLabel = getEntityLabel();
const entityLabelPlural = getEntityLabelPlural();
const entityLabelLower = getEntityLabelLower();
const entityIdLabel = getEntityIdLabel();

// Storage key for persistence
const storageKey = computed(() => `dataManager_${props.tableName}`);

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
  const speciesName = props.title.replace(/\s+Data$/i, '').toLowerCase();
  return `${formatSpeciesName(speciesName)} <span class="text-gray-700">- Data Manager</span>`;
});

// Column types from API
interface ColumnInfo {
  column_name: string;
  display_name?: string;
  type: string;
  isMeta: boolean;
}

// State
const availableMetaColumns = ref<ColumnInfo[]>([]);
const allSampleColumns = ref<string[]>([]);
const selectedMetaColumns = ref<string[]>([]);
const selectedLayer = ref("tpm");
const searchInput = ref("");
const parsedGeneIds = ref<string[]>([]);
const showCountMatrix = ref(true);

const rows = ref<RowType[]>([]);
const totalCount = ref(0);
const loading = ref(false);
const initialLoading = ref(true);
const error = ref("");
const showColumnDropdown = ref(false);
const showExportModal = ref(false);
const exporting = ref(false);
const exportAbortController = ref<AbortController | null>(null);
const allExportData = ref<RowType[]>([]);
const showBlastWarning = ref(false);
const pendingBlastParams = ref<{ fieldType: string; sequence: string } | null>(null);
const suppressAutoReload = ref(true);

// Lazy loading state
const pageSize = 100;
const currentOffset = ref(0);
const hasMoreData = computed(() => rows.value.length < totalCount.value);

// Refs
const tableContainer = ref<HTMLElement | null>(null);
const sidebarOpen = inject<Ref<boolean> | undefined>("sidebarOpen", undefined);
const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1024);

function updateViewportWidth() {
  if (typeof window === "undefined") return;
  viewportWidth.value = window.innerWidth;
}

const managerOverlayStyle = computed(() => {
  const sidebarWidth = sidebarOpen?.value && viewportWidth.value >= 768 ? 320 : 0;
  return { left: `${sidebarWidth}px` };
});

// Compute gene filters (transcript/gene metadata columns)
const geneFilters = computed(() => {
  const geneColNames = new Set(columnsStore.rowColumns.map(c => c.column_name));
  return Object.fromEntries(
    Object.entries(filtersStore.filters).filter(([key]) => geneColNames.has(key))
  );
});

// Compute sample filters (sample metadata columns)
const sampleFilters = computed(() => {
  const sampleColNames = new Set(columnsStore.filterableColColumns.map(c => c.column_name));
  return Object.fromEntries(
    Object.entries(filtersStore.filters).filter(([key]) => sampleColNames.has(key))
  );
});

// Filter status
const activeGeneFilterCount = computed(() => Object.keys(geneFilters.value).length);
const activeSampleFilterCount = computed(() => Object.keys(sampleFilters.value).length);
const hasActiveFilters = computed(() => activeGeneFilterCount.value > 0 || activeSampleFilterCount.value > 0);

// Filtered sample columns based on sample filters and Count Matrix toggle
const filteredSampleColumns = computed(() => {
  // If Count Matrix is disabled, return empty array
  if (!showCountMatrix.value) {
    return [];
  }
  
  // If no sample filters, show all samples
  if (Object.keys(sampleFilters.value).length === 0) {
    return allSampleColumns.value;
  }
  
  // The backend will return only the filtered samples in the data
  // We extract the sample columns from the first row of data
  if (rows.value.length > 0) {
    const rowKeys = Object.keys(rows.value[0]);
    const metaCols = new Set(['gene_id', ...selectedMetaColumns.value]);
    return rowKeys.filter(key => !metaCols.has(key) && allSampleColumns.value.includes(key));
  }
  
  return allSampleColumns.value;
});

// Export data
const exportColumns = computed(() => [
  'gene_id',
  ...selectedMetaColumns.value,
  ...filteredSampleColumns.value
]);

// Export column display names mapping
const exportColumnDisplayNames = computed(() => {
  const mapping: Record<string, string> = {};
  
  // Add gene_id
  mapping['gene_id'] = entityIdLabel;
  
  // Add metadata columns
  for (const col of selectedMetaColumns.value) {
    mapping[col] = getMetaColumnDisplayName(col);
  }
  
  // Add sample columns (use as-is, they are sample IDs)
  for (const col of filteredSampleColumns.value) {
    mapping[col] = col;
  }
  
  return mapping;
});

// Format helpers
function formatColumnName(col: string): string {
  return col.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

function getMetaColumnDisplayName(colName: string): string {
  const col = availableMetaColumns.value.find(c => c.column_name === colName);
  const displayName = col?.display_name || formatColumnName(colName);
  return beautifyLabel(displayName);
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

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

function formatNumber(value: unknown): string {
  if (value === null || value === undefined) return "-";
  const num = Number(value);
  if (isNaN(num)) return String(value);
  if (Number.isInteger(num)) return num.toLocaleString();
  return num.toFixed(3);
}

// Copy column values to clipboard
const copyFeedback = ref<string | null>(null);
const copyLoading = ref<string | null>(null);

async function copyColumnValues(columnName: string) {
  if (totalCount.value === 0) return;
  
  copyLoading.value = columnName;
  
  try {
    // Fetch ALL data for the column (not just visible rows)
    const expressionOption = getExpressionOption(selectedLayer.value);
    
    const requestBody: Record<string, unknown> = {
      table_name: props.tableName,
      columns: [columnName], // Only fetch the column we need
      filters: geneFilters.value,
      filter_chain: filtersStore.buildFilterChainPayload(geneFilters.value),
      sample_filters: sampleFilters.value,
      limit: 100000, // Get all data
      offset: 0,
    };
    
    if (expressionOption) {
      if (expressionOption.layer) {
        requestBody.layer = expressionOption.layer;
      }
      if (expressionOption.transform !== "raw") {
        requestBody.transform = expressionOption.transform;
      }
    }
    
    if (parsedGeneIds.value.length > 0) {
      requestBody.gene_ids = parsedGeneIds.value;
    }
    
    const response = await axios.post(`${API_BASE_URL}/api/data`, requestBody);
    const responseData = response.data;
    const allRows = Array.isArray(responseData) ? responseData : (responseData?.data ?? []);
    
    // Get all values from the column
    const values = allRows
      .map((row: RowType) => {
        const val = row[columnName];
        if (val === null || val === undefined) return "";
        if (Array.isArray(val)) return val.join(", ");
        return String(val);
      })
      .filter((val: string) => val !== "");
    
    // Join with newlines
    const text = values.join("\n");
    
    await navigator.clipboard.writeText(text);
    copyFeedback.value = columnName;
    setTimeout(() => {
      copyFeedback.value = null;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy to clipboard:", err);
  } finally {
    copyLoading.value = null;
  }
}

// Parse search input into gene IDs
function onSearchInput() {
  const input = searchInput.value.trim();
  if (!input) {
    parsedGeneIds.value = [];
    return;
  }
  parsedGeneIds.value = input
    .split(/[,\s\n\t]+/)
    .map((id) => id.trim())
    .filter((id) => id.length > 0);
}

function clearSearch() {
  searchInput.value = "";
  parsedGeneIds.value = [];
}

// Column selection
function selectAllMetaColumns() {
  selectedMetaColumns.value = availableMetaColumns.value.map(c => c.column_name);
}

function clearMetaColumns() {
  selectedMetaColumns.value = [];
}

// Clear all filters
function clearAllFilters() {
  filtersStore.clearFilters();
  searchInput.value = "";
  parsedGeneIds.value = [];
  reloadData();
}

// BLAST functionality
function openBlast(fieldType: string, sequence: string) {
  pendingBlastParams.value = { fieldType, sequence };
  showBlastWarning.value = true;
}

function proceedWithBlast(database: BlastDatabase) {
  if (pendingBlastParams.value) {
    openBlastUtil(pendingBlastParams.value.fieldType, pendingBlastParams.value.sequence, database);
  }
  showBlastWarning.value = false;
  pendingBlastParams.value = null;
}

function cancelBlast() {
  showBlastWarning.value = false;
  pendingBlastParams.value = null;
}

// Scroll handler for lazy loading
function onScroll() {
  if (!tableContainer.value || loading.value || !hasMoreData.value) return;
  
  const { scrollTop, scrollHeight, clientHeight } = tableContainer.value;
  // Load more when user scrolls to bottom 200px
  if (scrollHeight - scrollTop - clientHeight < 200) {
    loadMore();
  }
}

// Fetch column metadata
async function fetchColumnInfo() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/columns`, {
      params: { table_name: props.tableName }
    });
    
    const columns: ColumnInfo[] = response.data || [];
    
    // Separate meta columns and sample columns
    // Exclude gene_id from meta columns since it's always shown as first column
    availableMetaColumns.value = columns.filter(c => c.isMeta === true && c.column_name !== 'gene_id');
    allSampleColumns.value = columns
      .filter(c => c.isMeta === false)
      .map(c => c.column_name);
    
    // Load saved settings or use defaults
    loadSettings();
  } catch (e) {
    console.error("Error fetching columns:", e);
    availableMetaColumns.value = [];
    allSampleColumns.value = [];
  }
}

// Reload data from scratch
async function reloadData() {
  rows.value = [];
  currentOffset.value = 0;
  totalCount.value = 0;
  await fetchData();
}

// Fetch total count for current filters
async function fetchTotalCount() {
  try {
    const requestBody: Record<string, unknown> = {
      table_name: props.tableName,
      filters: geneFilters.value,
      filter_chain: filtersStore.buildFilterChainPayload(geneFilters.value),
    };
    
    // Add gene ID filter if search is active
    if (parsedGeneIds.value.length > 0) {
      requestBody.gene_ids = parsedGeneIds.value;
    }
    
    const response = await axios.post(`${API_BASE_URL}/api/count`, requestBody);
    totalCount.value = response.data?.count ?? 0;
  } catch (e) {
    console.error("Error fetching count:", e);
  }
}

// Handle export: fetch ALL data first, then show modal
async function handleExport() {
  exporting.value = true;
  const controller = new AbortController();
  exportAbortController.value = controller;
  
  try {
    const expressionOption = getExpressionOption(selectedLayer.value);
    
    // Build columns list
    const columns = [
      'gene_id',
      ...selectedMetaColumns.value,
      ...allSampleColumns.value
    ];
    
    const requestBody: Record<string, unknown> = {
      table_name: props.tableName,
      columns: columns,
      filters: geneFilters.value,
      filter_chain: filtersStore.buildFilterChainPayload(geneFilters.value),
      sample_filters: sampleFilters.value,
      limit: 100000, // Get all data (high limit)
      offset: 0,
    };
    
    if (expressionOption) {
      if (expressionOption.layer) {
        requestBody.layer = expressionOption.layer;
      }
      if (expressionOption.transform !== "raw") {
        requestBody.transform = expressionOption.transform;
      }
    }
    
    if (parsedGeneIds.value.length > 0) {
      requestBody.gene_ids = parsedGeneIds.value;
    }
    
    const response = await axios.post(`${API_BASE_URL}/api/data`, requestBody, { signal: controller.signal });
    const responseData = response.data;
    allExportData.value = Array.isArray(responseData) ? responseData : (responseData?.data ?? []);
    
    showExportModal.value = true;
  } catch (e: unknown) {
    if (axios.isCancel(e) || (axios.isAxiosError(e) && e.code === "ERR_CANCELED")) {
      return;
    }
    console.error("Error fetching export data:", e);
    error.value = "Failed to load data for export";
  } finally {
    exportAbortController.value = null;
    exporting.value = false;
  }
}

function cancelExportFetch() {
  exportAbortController.value?.abort();
}

// Fetch data with current settings (for viewer, paginated)
async function fetchData() {
  if (loading.value) return;
  
  loading.value = true;
  error.value = "";
  
  try {
    const expressionOption = getExpressionOption(selectedLayer.value);
    
    // Build columns list: gene_id + selected meta + all samples
    // (backend will filter samples based on sample_filters)
    const columns = [
      'gene_id',
      ...selectedMetaColumns.value,
      ...allSampleColumns.value
    ];
    
    const requestBody: Record<string, unknown> = {
      table_name: props.tableName,
      columns: columns,
      filters: geneFilters.value,  // Gene/transcript filters
      sample_filters: sampleFilters.value,  // Sample filters
      limit: pageSize,
      offset: currentOffset.value,
    };

    // Add layer/transform if available
    if (expressionOption) {
      if (expressionOption.layer) {
        requestBody.layer = expressionOption.layer;
      }
      if (expressionOption.transform !== "raw") {
        requestBody.transform = expressionOption.transform;
      }
    }

    // Add gene ID filter if search is active
    if (parsedGeneIds.value.length > 0) {
      requestBody.gene_ids = parsedGeneIds.value;
    }

    const response = await axios.post(`${API_BASE_URL}/api/data`, requestBody);
    
    const responseData = response.data;
    const rowData = Array.isArray(responseData) ? responseData : (responseData?.data ?? []);
    
    if (currentOffset.value === 0) {
      rows.value = rowData;
      // Fetch actual total count on first load before dismissing the loading overlay.
      await fetchTotalCount();
    } else {
      rows.value = [...rows.value, ...rowData];
    }

    // Save settings after successful fetch
    saveSettings();
  } catch (e: unknown) {
    console.error("Error fetching data:", e);
    error.value = axios.isAxiosError<{ error?: string }>(e)
      ? e.response?.data?.error || "Failed to load data"
      : "Failed to load data";
  } finally {
    loading.value = false;
  }
}

// Load more data (lazy loading)
async function loadMore() {
  if (loading.value || !hasMoreData.value) return;
  currentOffset.value = rows.value.length;
  await fetchData();
}

// Settings persistence
function saveSettings() {
  const settings = {
    selectedMetaColumns: selectedMetaColumns.value,
    selectedLayer: selectedLayer.value,
    searchInput: searchInput.value,
    showCountMatrix: showCountMatrix.value,
  };
  localStorage.setItem(storageKey.value, JSON.stringify(settings));
}

function loadSettings() {
  const saved = localStorage.getItem(storageKey.value);
  if (saved) {
    try {
      const settings = JSON.parse(saved);
      // Validate columns still exist
      const validCols = new Set(availableMetaColumns.value.map(c => c.column_name));
      selectedMetaColumns.value = (settings.selectedMetaColumns || []).filter(
        (col: string) => validCols.has(col)
      );
      selectedLayer.value = settings.selectedLayer || "tpm";
      searchInput.value = settings.searchInput || "";
      showCountMatrix.value = settings.showCountMatrix !== undefined ? settings.showCountMatrix : true;
      onSearchInput();
    } catch {
      resetToDefaults();
    }
  } else {
    resetToDefaults();
  }
}

function resetToDefaults() {
  // Select first few metadata columns by default
  selectedMetaColumns.value = availableMetaColumns.value
    .slice(0, 5)
    .map(c => c.column_name);
  selectedLayer.value = "tpm";
  searchInput.value = "";
  parsedGeneIds.value = [];
  showCountMatrix.value = true;
}

function resetSettings() {
  localStorage.removeItem(storageKey.value);
  // Also clear filters
  filtersStore.clearFilters();
  resetToDefaults();
  reloadData();
}

// Close dropdown when clicking outside
function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement;
  if (!target.closest(".relative")) {
    showColumnDropdown.value = false;
  }
}

// Debounced reload on settings change
let reloadTimeout: ReturnType<typeof setTimeout> | null = null;
function debouncedReload() {
  if (suppressAutoReload.value || initialLoading.value) return;
  if (reloadTimeout) clearTimeout(reloadTimeout);
  reloadTimeout = setTimeout(() => {
    reloadData();
  }, 300);
}

// Watch for layer changes to reload
watch(selectedLayer, () => {
  if (rows.value.length > 0 || currentOffset.value > 0) {
    debouncedReload();
  }
});

// Watch for Count Matrix toggle
watch(showCountMatrix, () => {
  saveSettings();
});

// Watch for meta column changes to reload
watch(selectedMetaColumns, () => {
  if (rows.value.length > 0 || currentOffset.value > 0) {
    debouncedReload();
  }
}, { deep: true });

// Watch for search changes
watch(parsedGeneIds, () => {
  debouncedReload();
}, { deep: true });

// Watch for filter changes
watch([geneFilters, sampleFilters], () => {
  debouncedReload();
}, { deep: true });

onMounted(async () => {
  initialLoading.value = true;
  suppressAutoReload.value = true;
  updateViewportWidth();
  window.addEventListener("resize", updateViewportWidth);
  document.addEventListener("click", handleClickOutside);
  try {
    await fetchColumnInfo();
    // Auto-load data when modal opens. Keep the initial overlay active until
    // columns, settings, first page, and count have all settled.
    await fetchData();
  } finally {
    await nextTick();
    suppressAutoReload.value = false;
    initialLoading.value = false;
  }
});

onUnmounted(() => {
  window.removeEventListener("resize", updateViewportWidth);
  exportAbortController.value?.abort();
  document.removeEventListener("click", handleClickOutside);
  if (reloadTimeout) clearTimeout(reloadTimeout);
});
</script>
