<template>
  <div>
    <div class="relative">
      <div ref="suggestionAnchorRef" class="flex rounded-md">
        <!-- Input Field -->
        <div
          class="flex-grow px-3 py-2 border-1 rounded-md bg-gray-50 focus:outline-none focus-within:ring-2 focus-within:ring-primary-500"
          :class="[isDragging ? 'border-primary-500' : 'border-gray-300']"
          @dragover.prevent="handleDragOver"
          @dragleave.prevent="handleDragLeave"
          @drop.prevent="onFileDrop"
        >
          <input
            v-if="!uploadedFile"
            :id="id"
            v-model="localInput"
            @keyup.enter="addPills"
            @focus="onSearchFocus"
            @blur="onSearchBlur"
            :placeholder="`Enter ${beautifiedLabel} or drag file`"
            type="text"
            class="w-full text-gray-700 outline-none bg-transparent"
            autocomplete="off"
          />
          <div v-else class="flex items-center">
            <svg
              class="w-5 h-5 mr-2 text-gray-700"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z"
              />
            </svg>
            <span class="text-sm text-blue-700">{{ uploadedFile.name }}</span>
            <button
              @click="removeUploadedFile"
              class="cursor-pointer ml-2 w-6 h-6 rounded-full flex items-center justify-center hover:bg-red-100"
              aria-label="Remove file"
              v-tooltip="'Remove file'"
            >
              <svg
                class="w-5 h-5 text-red-700"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fill-rule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clip-rule="evenodd"
                />
              </svg>
            </button>
          </div>
        </div>
        <!-- Add Button -->
        <div class="relative flex items-center" v-if="!uploadedFile">
            <button
              aria-label="Add filter term"
              @click="addPills"
              :disabled="!localInput"
              :class="[
                'cursor-pointer w-6 h-6 absolute inset-y-0 right-2 top-1/2 transform -translate-y-1/2 bg-gray-50 hover:bg-primary-900 text-primary-900 hover:text-gray-50 border rounded-full flex items-center justify-center',
                {
                  'opacity-50 cursor-not-allowed': !localInput,
                },
              ]"
              v-tooltip="localInput ? 'Add filter term' : ''"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                class="h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="3"
              >
                <path d="M12 6v12m6-6H6" />
              </svg>
            </button>
        </div>
      </div>
    </div>
    <!-- Suggestion dropdown – teleported to body so it escapes any scroll/overflow container -->
    <Teleport to="body">
      <div
        v-if="showDropdown"
        ref="suggestionFloatRef"
        :style="[suggestionFloatStyles, { minWidth: suggestionAnchorRef ? suggestionAnchorRef.offsetWidth + 'px' : '220px', maxWidth: '400px' }]"
        class="z-[9999] bg-white border border-gray-300 rounded-md shadow-lg"
      >
        <ul class="max-h-60 overflow-y-auto">
          <li
            v-for="item in searchResults"
            :key="item.term"
            @mousedown.prevent="addSuggestion(item.term)"
            class="cursor-pointer p-2 hover:bg-accent2-100 hover:shadow-md text-base text-gray-700 hover:text-white rounded-md"
          >
            <div class="flex flex-col">
              <span class="text-base">{{ item.term }}</span>
              <span class="text-xs text-gray-400">{{ item.description }}</span>
            </div>
          </li>
        </ul>
      </div>
    </Teleport>
    <!-- Error Message -->
    <p v-if="errorMessage" class="text-red-500 text-sm mt-1">
      {{ errorMessage }}
    </p>
    <!-- Pills (compact display) -->
    <div v-if="pillItems.length > 0" class="flex items-center gap-2 mt-2 max-w-full overflow-hidden">
      <!-- First pill (abbreviated if too long) -->
      <div
        class="flex items-center bg-primary-100 text-primary-900 border-1 text-sm font-medium px-2.5 py-0.5 rounded-full max-w-[200px]"
      >
        <span class="truncate">{{ pillItems[0] }}</span>
        <button
          @click="removePill(pillItems[0])"
          class="cursor-pointer ml-0.5 p-0.5 rounded-full bg-primary-100 hover:bg-primary-900 text-primary-900 hover:text-primary-100 focus:outline-none flex-shrink-0"
        >
          <svg
            class="w-4 h-4"
            fill="currentColor"
            viewBox="0 0 20 20"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              fill-rule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>
      <!-- Additional pills indicator with tooltip -->
      <div v-if="pillItems.length > 1" class="relative">
        <span
          ref="moreChipRef"
          :aria-label="hiddenPillsTooltip"
          @mouseenter="showMoreTooltip = true"
          @mouseleave="showMoreTooltip = false"
          @touchstart="handleTouchStart"
          @touchend="handleTouchEnd"
          @touchcancel="handleTouchCancel"
          class="flex items-center bg-gray-200 text-gray-700 border border-gray-300 text-xs font-medium px-2 py-0.5 rounded-full cursor-help"
        >
          +{{ pillItems.length - 1 }} more
        </span>
      </div>
      
      <!-- Tooltip with up to 10 additional filters (Teleport outside conditional) -->
      <Teleport to="body">
        <div
          v-if="showMoreTooltip && pillItems.length > 1"
          ref="floatingRef"
          :style="floatingStyles"
          class="z-[99999] bg-blue-600 text-white text-xs rounded-md px-3 py-2 shadow-lg pointer-events-none max-w-xs"
          role="tooltip"
        >
          <div class="space-y-1">
            <div v-for="(item, index) in hiddenPillsForTooltip" :key="index" class="whitespace-nowrap">
              {{ item }}
            </div>
            <div v-if="remainingPillsCount > 0" class="text-gray-300 italic">
              ... and {{ remainingPillsCount }} more
            </div>
          </div>
          <div
            ref="arrowRef"
            :style="arrowStyles"
            class="absolute w-2 h-2 bg-blue-600 rotate-45"
          ></div>
        </div>
      </Teleport>
      <!-- Clear all button -->
      <button
        v-if="pillItems.length > 1"
        @click="clearAllPills"
        class="cursor-pointer text-xs text-red-500 hover:text-red-700 hover:underline"
      >
        Clear all
      </button>
    </div>
    <!-- Match-mode toggle (OR/AND) + Exact / Empty checkboxes + Bulk button -->
    <div class="flex items-center justify-between mt-1">
      <div class="flex items-center space-x-3">
        <!-- OR/AND toggle: only visible when 2+ values are selected -->
        <button
          v-if="pillItems.length >= 2"
          type="button"
          @click="toggleMatchMode"
          :aria-label="matchMode === 'or' ? 'Switch to AND (all values must match)' : 'Switch to OR (any value must match)'"
          v-tooltip="matchMode === 'or'
            ? 'OR: at least one of the selected values must match (click for AND)'
            : 'AND: every selected value must match (click for OR)'"
          :class="[
            'cursor-pointer text-xs font-bold uppercase tracking-wide px-2 py-1 rounded-md border transition-colors',
            matchMode === 'and'
              ? 'bg-accent1-700 text-white border-accent1-700 hover:bg-accent1-900'
              : 'bg-primary-100 text-primary-900 border-primary-300 hover:bg-primary-200',
          ]"
        >
          {{ matchMode === 'and' ? 'AND' : 'OR' }}
        </button>
        <label class="flex items-center">
          <input
            type="checkbox"
            v-model="exact"
            class="cursor-pointer form-checkbox h-4 w-4 accent-primary-700 mr-2"
          />
          <span class="text-sm text-gray-700">Exact</span>
        </label>
        <label class="flex items-center">
          <input
            type="checkbox"
            v-model="empty"
            :disabled="!!uploadedFile"
            class="cursor-pointer form-checkbox h-4 w-4 accent-primary-700 mr-2"
          />
          <span
            class="text-sm text-gray-700"
            :class="{ 'opacity-50': uploadedFile }"
            >Empty</span
          >
        </label>
      </div>
      <!-- Batch Input Button -->
        <button
          aria-label="Add multiple values at once"
          @click="handleOpenBatchModal"
          class="cursor-pointer px-2 py-1 text-xs bg-gray-50 hover:bg-accent1-100 text-accent1-700 hover:text-accent1-900 border border-gray-300 hover:border-accent1-500 rounded-md flex items-center gap-1 transition-colors"
          v-tooltip="'Add multiple values at once'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="8" y1="6" x2="21" y2="6"></line>
            <line x1="8" y1="12" x2="21" y2="12"></line>
            <line x1="8" y1="18" x2="21" y2="18"></line>
            <line x1="3" y1="6" x2="3.01" y2="6"></line>
            <line x1="3" y1="12" x2="3.01" y2="12"></line>
            <line x1="3" y1="18" x2="3.01" y2="18"></line>
          </svg>
          Bulk
        </button>
    </div>

    <!-- Batch Input Modal -->
    <BatchInputModal
      :is-open="showBatchModal"
      :column-name="id || label"
      :column-label="label"
      :available-options="availableOptionsForBatch"
      :current-values="pillItems"
      @close="handleBatchModalClose"
      @apply-filters="onBatchFiltersApplied"
    />
  </div>
</template>
<script setup lang="ts">
import axios from "axios";
import { debounce, isEqual } from "lodash-es";
import { computed, onMounted, ref, watch } from "vue";
import { useFloating, offset, flip, shift, arrow, autoUpdate } from "@floating-ui/vue";

import BatchInputModal from "./BatchInputModal.vue";
import { API_BASE_URL } from "@/shared/Config";
import { type ModelValue } from "./SearchFilter.vue";
import { beautifyLabel } from "@/shared/utils";
import { useColumnsStore } from "@/stores/columns";

const props = defineProps<{
  modelValue?: ModelValue | null;
  label: string;
  id?: string;
}>();

const columnsStore = useColumnsStore();

const isDragging = ref(false);
const empty = ref(false);
// Match mode for multiple selected values: "or" (default) or "and".
// Replaces the legacy boolean `strict` flag (strict == match_mode === 'and').
const matchMode = ref<'or' | 'and'>('or');
// Whether to require exact value matches. Default true. When false,
// substring matching is used in the backend.
const exact = ref(true);
const showDropdown = ref(false);
const showBatchModal = ref(false);

const localInput = ref("");
const uploadedFile = ref<File | null>(null);
const errorMessage = ref("");
const pillItems = ref<string[]>([]);

// Tooltip state
const showMoreTooltip = ref(false);
const longPressTimer = ref<number | null>(null);
const moreChipRef = ref<HTMLElement | null>(null);
const floatingRef = ref<HTMLElement | null>(null);
const arrowRef = ref<HTMLElement | null>(null);

const beautifiedLabel = computed(() => beautifyLabel(props.label) ?? "Filter");

// Get available options for batch modal (e.g., tissue types)
const availableOptionsForBatch = computed(() => {
  const columnName = props.id || props.label;
  // Check if this is a tissue column with pre-cached values
  if (columnsStore.tissueColumnName === columnName) {
    return columnsStore.tissueValues;
  }
  // Return undefined for regular text input mode
  return undefined;
});

// Tooltip text for hidden pills (shows first 10) - used for aria-label
const hiddenPillsTooltip = computed(() => {
  const hidden = pillItems.value.slice(1);
  if (hidden.length <= 10) {
    return hidden.join(", ");
  }
  return hidden.slice(0, 10).join(", ") + `, ... and ${hidden.length - 10} more`;
});

// Pills to display in tooltip (up to 10)
const hiddenPillsForTooltip = computed(() => {
  const hidden = pillItems.value.slice(1);
  return hidden.slice(0, 10);
});

// Remaining pills not shown in tooltip
const remainingPillsCount = computed(() => {
  const hidden = pillItems.value.slice(1);
  return Math.max(0, hidden.length - 10);
});

// Floating UI setup for tooltip positioning
const { floatingStyles, middlewareData, placement } = useFloating(moreChipRef, floatingRef, {
  placement: 'top',
  middleware: [
    offset(8),
    flip(),
    shift({ padding: 8 }),
    arrow({ element: arrowRef })
  ],
  whileElementsMounted: autoUpdate
});

// Floating UI setup for suggestions dropdown
const suggestionAnchorRef = ref<HTMLElement | null>(null);
const suggestionFloatRef = ref<HTMLElement | null>(null);
const {
  floatingStyles: suggestionFloatStyles,
  update: updateSuggestionPosition,
} = useFloating(suggestionAnchorRef, suggestionFloatRef, {
  placement: 'bottom-start',
  middleware: [offset(4), flip(), shift({ padding: 8 })],
  whileElementsMounted: autoUpdate,
});

// Arrow positioning for tooltip
const arrowStyles = computed(() => {
  const arrowData = middlewareData.value.arrow;
  if (!arrowData) return {};
  
  const { x, y } = arrowData;
  const side = placement.value.split('-')[0];
  
  const staticSide = {
    top: 'bottom',
    right: 'left',
    bottom: 'top',
    left: 'right'
  }[side] as string;
  
  return {
    left: x != null ? `${x}px` : '',
    top: y != null ? `${y}px` : '',
    [staticSide]: '-4px'
  };
});

const searchResults = ref<
  { term: string; description: string; similarity: number }[]
>([]);

// Check if this filter is for GO terms
const isGoTermFilter = computed(() => {
  const label = (props.id || props.label).toLowerCase();
  return label === 'go_terms' || label === 'go_term' || label === 'go term' || label === 'goterm';
});

//Handle suggestions
function addSuggestion(term: string) {
  pillItems.value = [...new Set([...pillItems.value, term])].sort();
  localInput.value = "";
  showDropdown.value = false;
}

const fetchSuggestions = debounce(async (val: string) => {
  if (val && val.length >= 2 && !uploadedFile.value) {
    try {
      // Use GO API for GO term filters
      if (isGoTermFilter.value) {
        const response = await axios.get(`${API_BASE_URL}/api/go/search`, {
          params: { q: val, limit: 10 },
        });
        
        if (response.data.available && response.data.results) {
          searchResults.value = response.data.results.map((result: any) => ({
            term: result.id,  // Store the GO ID
            description: `${result.name}${result.definition ? ' - ' + result.definition.substring(0, 100) + (result.definition.length > 100 ? '...' : '') : ''}`,
            similarity: 1.0,
          }));
          showDropdown.value = searchResults.value.length > 0;
        } else {
          searchResults.value = [];
          showDropdown.value = false;
        }
      } else {
        // Use regular fuzzy search for other filters
        const response = await axios.get(`${API_BASE_URL}/api/find`, {
          params: { column: props.id || props.label, search_term: val },
        });
        searchResults.value = response.data;
        showDropdown.value = response.data.length > 0;
      }
    } catch (e) {
      console.error("Error occured finding similar descriptions: ", e);
      searchResults.value = [];
      showDropdown.value = false;
    }
  } else {
    searchResults.value = [];
    showDropdown.value = false;
  }
}, 100);

//Handle pills
function parsePills(input: string): string[] {
  return input
    .replace(/['"]/g, "")
    .split(/[\n;|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function addPills() {
  if (!localInput.value) return;
  const term = localInput.value.trim();
  if (!term) return;
  empty.value = false;
  pillItems.value = [...new Set([...pillItems.value, term])].sort();
  localInput.value = "";
  errorMessage.value = "";
}

function removePill(pill: string) {
  pillItems.value = pillItems.value.filter((item) => item !== pill);
}

/**
 * Clear all pills at once.
 */
function clearAllPills() {
  pillItems.value = [];
}

/**
 * Handle touch start for long press on mobile
 */
function handleTouchStart() {
  longPressTimer.value = window.setTimeout(() => {
    showMoreTooltip.value = true;
  }, 500); // 500ms for long press
}

/**
 * Handle touch end - clear timer and hide tooltip after delay
 */
function handleTouchEnd() {
  if (longPressTimer.value !== null) {
    clearTimeout(longPressTimer.value);
    longPressTimer.value = null;
  }
  // Keep tooltip visible briefly after long press
  if (showMoreTooltip.value) {
    setTimeout(() => {
      showMoreTooltip.value = false;
    }, 2000); // Hide after 2 seconds
  }
}

/**
 * Handle touch cancel - clear timer and hide tooltip
 */
function handleTouchCancel() {
  if (longPressTimer.value !== null) {
    clearTimeout(longPressTimer.value);
    longPressTimer.value = null;
  }
  showMoreTooltip.value = false;
}

/**
 * Handle batch filters applied from the BatchInputModal.
 * Replaces pill items with the selected values (1:1 sync).
 */
function onBatchFiltersApplied(values: string[]) {
  // Replace pills entirely with the new selection
  pillItems.value = values.sort();
  // Set empty flag if no values selected
  empty.value = values.length === 0;
}

/**
 * Ensure tissue values are loaded before opening the batch modal.
 * This is critical for the HOME page where the sidebar watch may not have triggered yet.
 */
async function ensureTissueValuesLoaded() {
  const columnName = props.id || props.label;
  
  // Only load if this is the tissue column and values are not yet cached
  if (columnsStore.tissueColumnName === columnName && columnsStore.tissueValues.length === 0) {
    try {
      // Fetch from all tables (same logic as SidebarComponent)
      const tablesResponse = await axios.get(`${API_BASE_URL}/api/tables`);
      const tables = tablesResponse.data;
      
      const allTissues = new Set<string>();
      
      // Fetch tissues from each table's metadata
      for (const table of tables) {
        try {
          const response = await axios.post(`${API_BASE_URL}/api/data`, {
            table_name: table.table_name + "_meta",
            filters: {},
          });
          
          const data = response.data.data || response.data;
          if (data && typeof data === 'object') {
            // Extract tissue values from the metadata
            const values = Object.values(data) as any[];
            values.forEach((item: any) => {
              const tissueValue = item[columnName];
              if (tissueValue) {
                allTissues.add(tissueValue);
              }
            });
          }
        } catch (err) {
          console.warn(`Could not fetch tissues for ${table.table_name}:`, err);
        }
      }
      
      const tissueArray = Array.from(allTissues).sort();
      
      if (tissueArray.length > 0) {
        columnsStore.setDistinctValues(columnName, tissueArray);
      }
    } catch (err) {
      console.warn("Could not load tissue values on demand:", err);
    }
  }
}

async function handleOpenBatchModal() {
  // Ensure tissue values are loaded before opening modal
  await ensureTissueValuesLoaded();
  showBatchModal.value = true;
}

function handleBatchModalClose() {
  showBatchModal.value = false;
}

function reset() {
  pillItems.value = [];
  matchMode.value = 'or';
  exact.value = true;
  empty.value = false;
}

//Handle file dragging
function handleDragOver() {
  isDragging.value = true;
}

function handleDragLeave() {
  isDragging.value = false;
}

function onFileDrop(e: DragEvent) {
  isDragging.value = false;
  const files = e.dataTransfer?.files;
  if (files && files.length > 0) {
    handleFile(files[0]);
  }
}

async function handleFile(file: File) {
  if (file.type !== "text/plain") {
    errorMessage.value = "Please upload a .txt file";
    return;
  }
  uploadedFile.value = file;
  errorMessage.value = "";

  try {
    // Use the modern File API if available
    const content = await file.text();

    // Replace newlines, semicolons, and commas with a single comma, remove quotes
    const pills = parsePills(content);

    // Merge with existing pills, remove duplicates, and sort
    pillItems.value = Array.from(
      new Set([...pillItems.value, ...pills]),
    ).sort();
  } catch {
    errorMessage.value = "Error reading file";
    uploadedFile.value = null;
    pillItems.value = [];
  }
}

function removeUploadedFile() {
  uploadedFile.value = null;
}

function onSearchFocus() {
  if (searchResults.value.length > 0) showDropdown.value = true;
}

function onSearchBlur() {
  setTimeout(() => (showDropdown.value = false), 100);
}

function toggleMatchMode() {
  matchMode.value = matchMode.value === 'or' ? 'and' : 'or';
}

watch(localInput, fetchSuggestions);

watch(
  [pillItems, matchMode, exact, empty],
  () => {
    // Auto-reset match mode when fewer than 2 pills (toggle is hidden)
    if (pillItems.value.length < 2 && matchMode.value === 'and') {
      matchMode.value = 'or';
    }
    // If the filter is truly empty, emit null so parent can delete the key
    if (!empty.value && pillItems.value.length === 0) {
      emit("update:modelValue", null);
    } else {
      emit("update:modelValue", {
        value: empty.value ? null : pillItems.value.join("|"),
        // Legacy alias for backward compatibility (true == AND)
        strict: matchMode.value === 'and',
        match_mode: matchMode.value,
        exact: exact.value,
        empty: empty.value,
      });
    }
  },
  { deep: true },
);

watch(
  () => props.modelValue,
  (newVal, oldVal) => {
    if (!isEqual(newVal, oldVal)) {
      if (newVal) {
        pillItems.value = newVal.value
          ? newVal.value.toString().split("|").filter(Boolean)
          : [];
        // Prefer match_mode if present, else fall back to legacy `strict`
        const mv = newVal as unknown as { match_mode?: 'or' | 'and'; strict?: boolean; exact?: boolean };
        matchMode.value = mv.match_mode ?? (mv.strict ? 'and' : 'or');
        exact.value = mv.exact ?? true;
        empty.value = newVal.value === null;
      } else {
        // Clear pills if no modelValue
        pillItems.value = [];
        matchMode.value = 'or';
        exact.value = true;
        empty.value = false;
      }
    }
  },
  { immediate: true, deep: true },
);

// Watcher: reset filter when parent signals empty state
watch(
  () => empty.value,
  (val) => {
    if (val) {
      pillItems.value = [];
      localInput.value = "";
      matchMode.value = 'or';
    }
  },
);

const emit = defineEmits(["update:modelValue"]);
defineExpose({ reset });

onMounted(() => {
  if (props.modelValue) {
    pillItems.value = props.modelValue.value
      ? props.modelValue.value.toString().split("|").filter(Boolean)
      : [];
    const mv = props.modelValue as unknown as { match_mode?: 'or' | 'and'; strict?: boolean; exact?: boolean };
    matchMode.value = mv.match_mode ?? (mv.strict ? 'and' : 'or');
    exact.value = mv.exact ?? true;
    empty.value = props.modelValue.value === null;
  }
});
</script>
