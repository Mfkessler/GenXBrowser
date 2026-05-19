<template>
  <div
    :class="[
      'relative rounded-xl p-5 w-full mx-auto transition-all duration-200 flex flex-col cursor-pointer select-none h-full [container-type:inline-size]',
      props.selected
        ? 'border-2 border-primary-500 shadow-md bg-primary-50/30'
        : 'border-1 border-gray-300 bg-white hover:border-gray-400 hover:shadow-sm',
    ]"
    role="checkbox"
    :aria-checked="props.selected"
    :tabindex="0"
    @click="$emit('toggle-select', tableName)"
    @keydown.enter.prevent="$emit('toggle-select', tableName)"
    @keydown.space.prevent="$emit('toggle-select', tableName)"
  >
    <!-- Selection indicator (top-right) -->
    <div class="absolute top-3 right-3">
      <div
        :class="[
          'w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors',
          props.selected
            ? 'border-primary-500 bg-primary-500'
            : 'border-gray-300 bg-white',
        ]"
      >
        <svg
          v-if="props.selected"
          class="w-3.5 h-3.5 text-white"
          fill="none"
          stroke="currentColor"
          stroke-width="3"
          viewBox="0 0 24 24"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
        </svg>
      </div>
    </div>

    <div class="flex-1">
      <!-- Species Photo + Title (Circular Mode) -->
      <div v-if="photoDisplayMode === 'circular'" class="catalog-entry-header mb-2">
        <!-- Photo stays in normal flow so it cannot cover the dataset text. -->
        <img 
          :src="displayPhotoUrl" 
          :alt="tableName"
          class="catalog-entry-photo rounded-full object-contain bg-black border-2 border-primary-900 flex-shrink-0 cursor-pointer hover:border-primary-700 transition-colors"
          :class="{ 'opacity-50': photoLoading }"
          @click.stop="openPhotoModal"
        />
        <div class="catalog-entry-copy">
          <h2 class="text-lg italic font-semibold text-gray-700 text-center mb-1 break-words min-w-0">
            {{ beautifyLabel(tableName) }}
          </h2>
          <p :class="['text-gray-400 text-sm transition-colors duration-500 text-center break-words', countFlash ? 'count-flash' : '']"><b>Count: </b>{{ displayCount }} {{ entityLabelPlural }}</p>
          <div class="flex items-center justify-center min-w-0 max-w-full">
            <p :class="['text-gray-400 text-sm transition-colors duration-500 break-words min-w-0', tissueFlash ? 'count-flash' : '']">
              <b>{{ defaultSampleColumnLabel }}: </b>{{ tissues }}
            </p>
            <!-- Help Icon -->
            <div
              class="relative inline-block ml-1.5"
              v-tooltip:bottom="defaultSampleColumnTooltip"
            >
              <div
                class="w-3.5 h-3.5 rounded-full bg-gray-400 text-white font-bold text-[10px] flex items-center justify-center cursor-pointer"
              >
                ?
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Title Only (Watermark Mode) -->
      <div v-else>
        <h2 class="text-lg italic font-semibold text-gray-700 w-full flex items-center mb-1">
          {{ beautifyLabel(tableName) }}
        </h2>
        <p :class="['text-gray-400 text-sm transition-colors duration-500', countFlash ? 'count-flash' : '']"><b>Count: </b>{{ displayCount }} {{ entityLabelPlural }}</p>
        <div class="flex items-center">
          <p :class="['text-gray-400 text-sm transition-colors duration-500', tissueFlash ? 'count-flash' : '']">
            <b>{{ defaultSampleColumnLabel }}: </b>{{ tissues }}
          </p>

          <!-- Help Icon -->
          <div
            class="relative inline-block ml-1.5"
            v-tooltip:bottom="defaultSampleColumnTooltip"
          >
            <div
              class="w-3.5 h-3.5 rounded-full bg-gray-400 text-white font-bold text-[10px] flex items-center justify-center cursor-pointer"
            >
              ?
            </div>
          </div>
        </div>
      </div>
      
      <!-- Watermark Photo (positioned absolutely in top-right) -->
      <img 
        v-if="photoDisplayMode === 'watermark'"
        :src="displayPhotoUrl" 
        :alt="tableName"
        class="absolute top-3 right-12 w-24 h-24 object-contain opacity-20 grayscale pointer-events-none"
        :class="{ 'opacity-10': photoLoading }"
      />
      
      <!-- Data action buttons -->
      <div class="flex justify-center gap-2 mt-3">
        <!-- Filter Transcript IDs Button (Purple) -->
        <button
          class="cursor-pointer rounded-full border-1 border-purple-600 bg-purple-100 hover:bg-purple-600 text-purple-600 hover:text-purple-100 p-2 min-w-10 min-h-10 flex items-center justify-center"
          aria-label="Filter Transcript IDs"
          @click.stop="openIdFilterModal"
          v-tooltip="'Filter Transcript IDs'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="w-4.5 h-4.5"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M8 4a4 4 0 100 8 4 4 0 000-8zM2 8a6 6 0 1110.89 3.476l4.817 4.817a1 1 0 01-1.414 1.414l-4.816-4.816A6 6 0 012 8z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
        <!-- Inspect Metadata Button -->
        <button
          class="cursor-pointer rounded-full border-1 border-blue-600 bg-blue-100 hover:bg-blue-600 text-blue-600 hover:text-blue-100 p-2 min-w-10 min-h-10 flex items-center justify-center"
          aria-label="Inspect Metadata"
          @click.stop="$emit('inspect-metadata')"
          v-tooltip="'Inspect Metadata'"
        >
          <svg
            class="w-4.5 h-4.5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <circle cx="12" cy="12" r="10" stroke="currentColor"/>
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 16v-4m0-4h.01"
            />
          </svg>
        </button>
        <!-- Inspect Data Button -->
        <span v-tooltip="config.access.data ? 'Inspect Data' : 'Data access not available'">
        <button
          :disabled="!config.access.data"
          class="rounded-full border-1 border-green-600 bg-green-100 text-green-600 p-2 min-w-10 min-h-10 flex items-center justify-center"
          :class="{
            'cursor-pointer hover:bg-green-600 hover:text-green-100':
              config.access.data,
            'cursor-not-allowed opacity-50': !config.access.data,
          }"
          aria-label="Inspect Data"
          @click.stop="$emit('inspect-data')"
        >
          <svg
            class="w-4.5 h-4.5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <rect
              x="4"
              y="6"
              width="16"
              height="12"
              rx="2"
              stroke="currentColor"
            />
            <path d="M4 10h16M10 6v12" stroke="currentColor"/>
          </svg>
        </button>
        </span>
        <!-- Download Data Button -->
        <span v-tooltip="config.access.download ? 'Download Data' : 'Download not available'">
        <button
          class="rounded-full border-1 border-yellow-600 bg-yellow-100 text-yellow-600 p-2 min-w-10 min-h-10 flex items-center justify-center"
          :class="{
            'cursor-pointer hover:bg-yellow-600 hover:text-yellow-100':
              config.access.download,
            'cursor-not-allowed opacity-50': !config.access.download,
          }"
          aria-label="Download Data"
          @click.stop="$emit('download-data')"
        >
          <svg
            class="w-4.5 h-4.5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            viewBox="0 0 24 24"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M12 4v12m0 0l-4-4m4 4l4-4"
            />
            <rect
              x="4"
              y="18"
              width="16"
              height="2"
              rx="1"
              stroke="currentColor"
            />
          </svg>
        </button>
        </span>
      </div>
      
      <div v-if="tagItems.length > 0" class="flex flex-wrap gap-1.5 mt-2 overflow-hidden max-h-7 items-center justify-center">
        <template v-for="tag in visibleTags" :key="tag">
          <div
            :class="[
              'flex items-center border-1 text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 cursor-pointer transition-all duration-300',
              props.highlightedTag === tag
                ? 'border-primary-500 bg-primary-500 text-white shadow-lg scale-110 tag-pulse'
                : 'border-primary-900 bg-primary-100 text-primary-900 hover:bg-primary-200'
            ]"
            @click.stop="highlightTag(tag)"
          >
            {{ tag }}
          </div>
        </template>
        <div
          v-if="hiddenTags.length > 0"
          class="flex items-center border-1 border-gray-400 bg-gray-100 text-gray-500 text-xs font-medium px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 cursor-default"
          v-tooltip="hiddenTags.join(', ')"
          @click.stop
        >
          +{{ hiddenTags.length }} more
        </div>
      </div>

      <!-- Per-dataset ID filter chips -->
      <div v-if="datasetIdPills.length > 0" class="flex flex-wrap gap-1 mt-2 items-center" @click.stop>
        <!-- First chip shown in full -->
        <span
          class="inline-flex items-center gap-0.5 bg-purple-50 text-purple-700 border border-purple-200 text-xs rounded-full px-2 py-0.5"
        >
          {{ datasetIdPills[0] }}
          <button
            class="cursor-pointer ml-0.5 text-purple-400 hover:text-purple-700"
            aria-label="Remove filter"
            @click.stop="removeIdPill(datasetIdPills[0])"
          >&times;</button>
        </span>
        <!-- Overflow chip showing remaining count -->
        <span
          v-if="datasetIdPills.length > 1"
          class="inline-flex items-center bg-purple-50 text-purple-500 border border-purple-200 text-xs rounded-full px-2 py-0.5 cursor-default"
          v-tooltip="datasetIdPills.slice(1).join(', ')"
        >
          +{{ datasetIdPills.length - 1 }} more
        </span>
        <!-- Clear all chip -->
        <button
          class="cursor-pointer inline-flex items-center text-purple-400 hover:text-red-500 text-xs ml-0.5"
          aria-label="Clear all ID filters"
          @click.stop="clearDatasetIdFilter"
          v-tooltip="'Clear all ID filters'"
        >
          <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>

      <!-- Batch Input Modal for per-dataset ID filtering -->
      <BatchInputModal
        :is-open="showBatchModal"
        :column-name="config.visualization.id_column"
        :column-label="idColumnLabel"
        :table-name="props.tableName"
        :species-name="beautifyLabel(props.tableName)"
        :current-values="datasetIdPills"
        @close="showBatchModal = false"
        @apply-filters="onBatchIdFiltersApplied"
      />
      
      <!-- Photo Modal -->
      <div
        v-if="showPhotoModal"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-75"
        @click="closePhotoModal"
      >
        <div class="relative max-w-4xl max-h-[90vh] bg-white rounded-2xl shadow-2xl overflow-hidden" @click.stop>
          <!-- Close Button -->
          <button
            class="absolute top-4 right-4 z-10 w-10 h-10 flex items-center justify-center rounded-full bg-white/90 hover:bg-white text-gray-600 hover:text-gray-900 shadow-lg transition-all"
            @click="closePhotoModal"
            aria-label="Close"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
            </svg>
          </button>
          
          <!-- Photo -->
          <div class="p-8">
            <img 
              :src="displayPhotoUrl" 
              :alt="beautifyLabel(tableName)"
              class="max-w-full max-h-[calc(90vh-8rem)] mx-auto rounded-xl shadow-xl"
            />
            <!-- Caption -->
            <div class="mt-4 text-center">
              <h3 class="text-xl font-semibold text-gray-800 italic">
                {{ beautifyLabel(tableName) }}
              </h3>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
import axios from "axios";
import {computed, inject, onMounted, ref, watch} from "vue";

import {API_BASE_URL, type Config} from "@/shared/Config";
import { getEntityLabelPlural } from "@/shared/dataTypeLabels";
import {useFiltersStore} from "@/stores/filters";
import {useColumnsStore} from "@/stores/columns";
import {beautifyLabel} from "@/shared/utils";
import BatchInputModal from "./BatchInputModal.vue";
import { getProcessedPhoto, generateInitialsPlaceholder } from "@/utils/imageProcessor";
import { filterMetadataRows, uniqueMetadataValues, type MetadataFilterValue, type MetadataRow } from "@/shared/sampleMetadataFilters";

const filtersStore = useFiltersStore();
const columnsStore = useColumnsStore();

const config = inject("config") as Config;

// Photo display mode from environment variable
const photoDisplayMode = import.meta.env.VITE_PHOTO_DISPLAY_MODE || 'circular';

const props = defineProps<{
  tableName: string;
  dataPoints: number;
  description: string;
  tags: string[];
  photo?: string;  // Photo filename from API
  tissueCount?: number;
  selected: boolean;
  highlightedTag?: string | null;
}>();

const emit = defineEmits(["inspect-metadata", "inspect-data", "download-data", "toggle-select", "update:filtered-count", "highlight-tag"]);

const filteredCount = ref<number | null>(null);
const loadingCount = ref(false);
const isOG = ref(false);
const n_tissues = ref<number | null>(null);
const tissueTypes = ref<string[] | null>(null);
const hasCalculatedTissues = ref(false);
const showBatchModal = ref(false);
const countFlash = ref(false);
const tissueFlash = ref(false);

// Species photo state
const photoUrl = ref<string | null>(null);
const photoLoading = ref(false);
const photoError = ref(false);
const showPhotoModal = ref(false);

// Track "last settled" values so we only flash on real changes, not on
// initial mount, loading transitions, or route-back re-renders.
let lastSettledCount: number | null = null;
let lastSettledTissues: number | null = null;
// True once the initial onMounted load has finished; prevents false flash.
let initialLoadDone = false;
// Serialised snapshot of the filter object at last settle — used to detect
// whether a filter actually changed versus a re-evaluation from navigation.
let lastFilterSnapshot = '';

const tagItems = computed(
  () => props.tags?.map((t) => t.trim()).filter(Boolean) ?? [],
);

const MAX_VISIBLE_TAGS = 4;

const visibleTags = computed(() => tagItems.value.slice(0, MAX_VISIBLE_TAGS));
const hiddenTags = computed(() => tagItems.value.slice(MAX_VISIBLE_TAGS));
const entityLabelPlural = getEntityLabelPlural();

const displayCount = computed(() => {
  if (loadingCount.value) return "...";
  if (filteredCount.value !== null) return filteredCount.value;
  return props.dataPoints;
});

const tissues = computed(() => {
  if (loadingCount.value) return "...";
  // Prioritize calculated value when we have actively calculated tissues
  if (hasCalculatedTissues.value && n_tissues.value !== null) return n_tissues.value;
  // Fall back to prop only if we haven't calculated yet
  if (props.tissueCount !== undefined) return props.tissueCount;
  if (n_tissues.value !== null) return n_tissues.value;
  return 0;
});

const defaultSampleColumn = computed(() => (
  columnsStore.filterableColColumns.find((column) => column.is_tissue) ?? null
));

const defaultSampleColumnLabel = computed(() => (
  defaultSampleColumn.value?.display_name
  || (defaultSampleColumn.value?.column_name ? beautifyLabel(defaultSampleColumn.value.column_name) : 'Sample Metadata')
));

const defaultSampleColumnTooltip = computed(() => {
  const label = defaultSampleColumnLabel.value;
  if (tissueTypes.value && tissueTypes.value.length > 0) {
    return `${label}: ${tissueTypes.value.join(', ')}`;
  }
  if (tissueTypes.value && tissueTypes.value.length === 0) {
    return `No ${label} values match current filters`;
  }
  return 'Loading...';
});

// Photo URL: processed photo or initials placeholder
const displayPhotoUrl = computed(() => {
  if (photoError.value || !props.photo) {
    // Generate initials placeholder
    return generateInitialsPlaceholder(props.tableName, 64);
  }
  return photoUrl.value || generateInitialsPlaceholder(props.tableName, 64);
});

// Load and process photo on mount
watch(() => props.photo, async (newPhoto) => {
  if (!newPhoto) {
    photoUrl.value = null;
    return;
  }
  
  photoLoading.value = true;
  photoError.value = false;
  
  try {
    const processed = await getProcessedPhoto(newPhoto, API_BASE_URL);
    photoUrl.value = processed;
  } catch (error) {
    console.error(`Failed to load photo for ${props.tableName}:`, error);
    photoError.value = true;
  } finally {
    photoLoading.value = false;
  }
}, { immediate: true });

function highlightTag(tag: string) {
  emit("highlight-tag", tag);
}

// Per-dataset ID filter: computed list of pills from the store
const datasetIdPills = computed(() => {
  const dsFilter = filtersStore.datasetIdFilters[props.tableName];
  if (!dsFilter || !dsFilter.value) return [];
  return dsFilter.value.split(",").filter(Boolean);
});

// Effective filters for this dataset: global filters merged with per-dataset ID filter
const effectiveFilters = computed(() => filtersStore.getMergedFilters(props.tableName));

function openIdFilterModal() {
  showBatchModal.value = true;
}

// Display label for the ID column — use display_name from store if available,
// otherwise fall back to beautifyLabel
const idColumnLabel = computed(() => {
  const colName = config.visualization.id_column;
  const found = columnsStore.rowColumns.find(c => c.column_name === colName);
  if (found?.display_name) return found.display_name;
  return beautifyLabel(colName);
});

function onBatchIdFiltersApplied(values: string[]) {
  if (values.length === 0) {
    filtersStore.removeDatasetIdFilter(props.tableName);
  } else {
    filtersStore.setDatasetIdFilter(props.tableName, {
      value: values.join(","),
    });
  }
}

function removeIdPill(pill: string) {
  const remaining = datasetIdPills.value.filter((p) => p !== pill);
  if (remaining.length === 0) {
    filtersStore.removeDatasetIdFilter(props.tableName);
  } else {
    filtersStore.setDatasetIdFilter(props.tableName, {
      value: remaining.join(","),
    });
  }
}

function clearDatasetIdFilter() {
  filtersStore.removeDatasetIdFilter(props.tableName);
}

function openPhotoModal() {
  if (!photoError.value && props.photo) {
    showPhotoModal.value = true;
  }
}

function closePhotoModal() {
  showPhotoModal.value = false;
}

async function calculate_tissues(tableName: string, filters: Record<string, unknown>): Promise<string[]> {
  try {
    const tissueColumnName = defaultSampleColumn.value?.column_name;
    if (!tissueColumnName) return [];
    const sampleMetadataColumns = new Set(columnsStore.filterableColColumns.map((column) => column.column_name));
    
    // Backend doesn't properly filter _meta tables, so we always fetch all data
    // and filter client-side
    const response_data = await axios.post(
      `${API_BASE_URL}/api/data`,
      {
        table_name: tableName + "_meta",
        filters: {}, // Always empty - we filter client-side
      },
    );
    
    // Backend returns {data: [...records...]}, axios wraps in .data
    const data = response_data.data?.data || response_data.data || [];
    
    if (!Array.isArray(data) && typeof data !== 'object') {
      console.warn('Invalid data structure for calculate_tissues:', data);
      return [];
    }
    
    const dataArray = (Array.isArray(data) ? data : Object.values(data)) as MetadataRow[];
    const filteredRows = filterMetadataRows(dataArray, filters as Record<string, MetadataFilterValue>, sampleMetadataColumns);
    return uniqueMetadataValues(filteredRows, tissueColumnName);
  } catch (error) {
    console.error("Error calculating tissues:", error);
    return [];
  }
}

/**
 * Trigger flash animations.  Called after every data-fetch settles.
 * Only flashes the metric(s) that actually changed since the last settle,
 * and only after the initial mount has completed (so navigating back
 * to home doesn't cause a spurious flash).
 */
function settleAndFlash(newCount: number | null, newTissueCount: number | null, filterSnapshot: string) {
  // On first mount we just record the baseline — no flash.
  if (!initialLoadDone) {
    lastSettledCount = newCount;
    lastSettledTissues = newTissueCount;
    lastFilterSnapshot = filterSnapshot;
    initialLoadDone = true;
    return;
  }
  // If the filter snapshot hasn't changed (e.g. navigating back to Home
  // with the same filters), skip flashing entirely.
  if (filterSnapshot === lastFilterSnapshot) {
    lastSettledCount = newCount;
    lastSettledTissues = newTissueCount;
    return;
  }
  // Flash count only when it actually changed
  if (newCount !== lastSettledCount) {
    countFlash.value = true;
    setTimeout(() => { countFlash.value = false; }, 600);
  }
  // Flash tissue count only when it actually changed
  if (newTissueCount !== lastSettledTissues) {
    tissueFlash.value = true;
    setTimeout(() => { tissueFlash.value = false; }, 600);
  }
  lastSettledCount = newCount;
  lastSettledTissues = newTissueCount;
  lastFilterSnapshot = filterSnapshot;
}

// Emit effective count whenever it changes so the parent can track it per-dataset
watch(
  () => filteredCount.value,
  (count) => {
    emit("update:filtered-count", props.tableName, count);
  },
);

onMounted(() => {
  // Emit initial count (total) so the catalog store has a baseline.
  // The effectiveFilters watcher ({immediate: true}) handles the actual
  // tissue + count fetch — including any already-active filters.
  emit("update:filtered-count", props.tableName, null);
});


watch(
  [effectiveFilters, () => filtersStore.filterChainVersion],
  async ([newFilters]) => {
    console.log(`[CatalogEntry watcher] Filter change detected for ${props.tableName}:`, newFilters);
    
    if (!props.tableName) return;

    // Check for orthogroup filter
    isOG.value = Object.keys(newFilters).includes("ortho_id");
    const isEmpty = Object.keys(newFilters).length === 0;

    console.log(`[CatalogEntry watcher] isEmpty:`, isEmpty, 'filter keys:', Object.keys(newFilters));

    const snapshot = JSON.stringify(newFilters);

    if (isEmpty) {
      filteredCount.value = null;
      // Reset tissues to show all when filters are cleared
      loadingCount.value = true;
      try {
        const tissues = await calculate_tissues(props.tableName, {});
        n_tissues.value = tissues.length;
        tissueTypes.value = tissues;
        hasCalculatedTissues.value = true;
      } catch (error) {
        console.error("Error occurred fetching tissues: ", error);
        hasCalculatedTissues.value = false;
      } finally {
        loadingCount.value = false;
        settleAndFlash(props.dataPoints, n_tissues.value, snapshot);
      }
      return;
    }

    loadingCount.value = true;
    try {
      // Recalculate tissues with current filters
      const tissues = await calculate_tissues(props.tableName, newFilters);
      n_tissues.value = tissues.length;
      tissueTypes.value = tissues;
      hasCalculatedTissues.value = true;

      // Get filtered count
      const response = await axios.post(
        `${API_BASE_URL}/api/count`,
        {
          table_name: props.tableName,
          filters: newFilters,
          filter_chain: filtersStore.buildFilterChainPayload(newFilters),
        },
      );
      filteredCount.value = response.data.count;
    } catch (error) {
      console.error("Error occurred fetching count: ", error);
      filteredCount.value = null;
      hasCalculatedTissues.value = false;
    } finally {
      loadingCount.value = false;
      settleAndFlash(filteredCount.value ?? props.dataPoints, n_tissues.value, snapshot);
    }
  },
  {immediate: true, deep: true},
);
</script>

<style scoped>
@keyframes count-flash-anim {
  0% { color: inherit; }
  30% { color: #7c3aed; font-weight: 800; }
  100% { color: inherit; }
}
.count-flash {
  animation: count-flash-anim 0.6s ease-in-out;
}

@keyframes tag-pulse-anim {
  0%, 100% {
    transform: scale(1.1);
    box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.7);
  }
  50% {
    transform: scale(1.15);
    box-shadow: 0 0 0 8px rgba(59, 130, 246, 0);
  }
}
.tag-pulse {
  animation: tag-pulse-anim 0.6s ease-in-out;
}

.catalog-entry-header {
  display: grid;
  grid-template-columns: minmax(4.75rem, clamp(4.75rem, 28cqi, 7.5rem)) minmax(0, 1fr);
  align-items: center;
  gap: 0.875rem;
  min-width: 0;
}

.catalog-entry-photo {
  width: min(100%, clamp(4.75rem, 28cqi, 7.5rem));
  aspect-ratio: 1 / 1;
  justify-self: center;
}

.catalog-entry-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
}

@container (max-width: 22rem) {
  .catalog-entry-header {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .catalog-entry-photo {
    width: clamp(4.5rem, 34cqi, 6.25rem);
  }
}
</style>
