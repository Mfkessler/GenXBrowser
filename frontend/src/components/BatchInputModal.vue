<template>
  <div v-if="isOpen" class="fixed inset-0 z-[60] flex items-center justify-center p-6">
    <!-- Background overlay -->
    <div class="absolute inset-0 bg-black opacity-50" @click="$emit('close')"></div>

    <!-- Modal content -->
    <div class="relative bg-white rounded-lg border border-gray-300 w-full max-w-lg p-6 z-10">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold text-gray-700">
          Batch Input: {{ beautifiedLabel }}
          <span v-if="speciesName" class="block text-sm font-normal text-gray-500 italic">{{ speciesName }}</span>
        </h3>
        <button
          @click="$emit('close')"
          class="cursor-pointer text-gray-500 hover:text-red-600 text-xl font-bold"
          aria-label="Close"
        >
          &times;
        </button>
      </div>

      <!-- Multi-select mode (when availableOptions provided) -->
      <div v-if="hasAvailableOptions">
        <p class="text-sm text-gray-600 mb-3">
          Select one or more values from the list below:
        </p>
        
        <!-- Search filter -->
        <div class="mb-3">
          <input
            v-model="optionSearch"
            type="text"
            placeholder="Search options..."
            class="w-full px-3 py-2 border border-gray-300 rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
          />
        </div>
        
        <!-- Select All / Clear buttons -->
        <div class="flex gap-2 mb-3">
          <button
            @click="selectAllOptions"
            class="cursor-pointer px-3 py-1 text-xs bg-primary-100 text-primary-700 rounded hover:bg-primary-200"
          >
            Select All
          </button>
          <button
            @click="clearSelectedOptions"
            class="cursor-pointer px-3 py-1 text-xs bg-gray-100 text-gray-700 rounded hover:bg-gray-200"
          >
            Clear
          </button>
        </div>
        
        <!-- Options list -->
        <div class="mb-4 max-h-64 overflow-y-auto border border-gray-200 rounded-md">
          <label
            v-for="option in filteredOptions"
            :key="option"
            class="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-b-0"
          >
            <input
              type="checkbox"
              :value="option"
              v-model="selectedOptions"
              class="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <span class="text-sm text-gray-700">{{ option }}</span>
          </label>
          <div v-if="filteredOptions.length === 0" class="px-3 py-4 text-sm text-gray-500 text-center">
            No matching options found
          </div>
        </div>
        
        <!-- Selection summary -->
        <div v-if="selectedOptions.length > 0" class="mb-4 p-3 bg-green-50 rounded-md border border-green-200">
          <div class="text-sm font-medium text-green-700 mb-1">
            Selected ({{ selectedOptions.length }}):
          </div>
          <div class="flex flex-wrap gap-1 max-h-20 overflow-y-auto">
            <span
              v-for="val in selectedOptions.slice(0, 20)"
              :key="val"
              class="text-xs bg-green-200 text-green-800 px-2 py-0.5 rounded-full"
            >
              {{ val }}
            </span>
            <span v-if="selectedOptions.length > 20" class="text-xs text-green-600 italic">
              +{{ selectedOptions.length - 20 }} more...
            </span>
          </div>
        </div>
      </div>

      <!-- Text input mode (original behavior) -->
      <div v-else>
        <!-- Instructions -->
        <p class="text-sm text-gray-600 mb-3">
          Paste multiple values below. Supported separators: comma, newline, semicolon, pipe, or space.
          The dominant separator will be auto-detected.
        </p>

        <!-- Textarea -->
        <div class="mb-4">
          <textarea
            v-model="inputText"
            placeholder="Paste your values here (e.g., ID1, ID2, ID3 or one per line)"
            class="w-full h-40 p-3 border border-gray-300 rounded-md bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 resize-y text-sm font-mono"
          ></textarea>
        </div>

        <!-- Validate Button -->
        <div class="mb-4">
          <button
            @click="validateInput"
            :disabled="!inputText.trim() || isValidating"
            class="cursor-pointer w-full px-4 py-2 bg-primary-500 text-white rounded-md hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            <svg v-if="isValidating" class="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"></path>
            </svg>
            {{ isValidating ? 'Validating...' : 'Validate' }}
          </button>
        </div>

        <!-- Metrics Display (only shown after validation) -->
        <div v-if="hasValidated" class="mb-4 p-4 bg-gray-50 rounded-md border border-gray-200">
          <h4 class="font-semibold text-gray-700 mb-2">Validation Results</h4>
          
          <!-- Detected Separator -->
          <div class="text-sm text-gray-600 mb-2">
            <span class="font-medium">Detected Separator:</span> 
            <span class="font-mono bg-gray-200 px-1.5 py-0.5 rounded">{{ detectedSeparatorLabel }}</span>
          </div>

          <!-- Metrics -->
          <div class="grid grid-cols-3 gap-3 mb-3">
            <div class="text-center p-2 bg-white rounded border">
              <div class="text-lg font-bold text-gray-700">{{ parsedTokens.length }}</div>
              <div class="text-xs text-gray-500">Tokens Parsed</div>
            </div>
            <div class="text-center p-2 bg-green-50 rounded border border-green-200">
              <div class="text-lg font-bold text-green-600">{{ matchedValues.length }}</div>
              <div class="text-xs text-green-600">Valid Matches</div>
            </div>
            <div class="text-center p-2 bg-red-50 rounded border border-red-200">
              <div class="text-lg font-bold text-red-600">{{ discardedValues.length }}</div>
              <div class="text-xs text-red-600">Not Found</div>
            </div>
          </div>

          <!-- Matched Values Preview -->
          <div v-if="matchedValues.length > 0" class="mb-3">
            <div class="text-sm font-medium text-green-700 mb-1">
              Will be added ({{ matchedValues.length }}):
            </div>
            <div class="max-h-24 overflow-y-auto bg-green-50 p-2 rounded border border-green-200">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="val in matchedValues.slice(0, 50)"
                  :key="val"
                  class="text-xs bg-green-200 text-green-800 px-2 py-0.5 rounded-full"
                >
                  {{ val }}
                </span>
                <span v-if="matchedValues.length > 50" class="text-xs text-green-600 italic">
                  +{{ matchedValues.length - 50 }} more...
                </span>
              </div>
            </div>
          </div>

          <!-- Discarded Values -->
          <div v-if="discardedValues.length > 0">
            <div class="text-sm font-medium text-red-700 mb-1">
              Not found in data ({{ discardedValues.length }}):
            </div>
            <div class="max-h-24 overflow-y-auto bg-red-50 p-2 rounded border border-red-200">
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="val in discardedValues.slice(0, 30)"
                  :key="val"
                  class="text-xs bg-red-200 text-red-800 px-2 py-0.5 rounded-full"
                >
                  {{ val }}
                </span>
                <span v-if="discardedValues.length > 30" class="text-xs text-red-600 italic">
                  +{{ discardedValues.length - 30 }} more...
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex gap-3">
        <button
          @click="$emit('close')"
          class="cursor-pointer flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-md hover:bg-gray-100"
        >
          Cancel
        </button>
        <button
          @click="applyFilters"
          class="cursor-pointer flex-1 px-4 py-2 bg-accent1-500 text-white rounded-md hover:bg-accent1-700"
        >
          Apply{{ hasAvailableOptions ? ` (${effectiveMatchedValues.length} selected)` : effectiveMatchedValues.length > 0 ? ` ${effectiveMatchedValues.length} filter${effectiveMatchedValues.length !== 1 ? 's' : ''}` : '' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { beautifyLabel } from "@/shared/utils";
import { useColumnsStore } from "@/stores/columns";

const props = defineProps<{
  isOpen: boolean;
  columnName: string;
  columnLabel: string;
  availableOptions?: string[];
  currentValues?: string[];
  tableName?: string;
  speciesName?: string;
}>();

const emit = defineEmits<{
  (e: "close"): void;
  (e: "apply-filters", values: string[]): void;
}>();

// Multi-select mode state
const selectedOptions = ref<string[]>([]);
const optionSearch = ref("");

// Text input mode state
const inputText = ref("");
const isValidating = ref(false);
const hasValidated = ref(false);
const parsedTokens = ref<string[]>([]);
const matchedValues = ref<string[]>([]);
const discardedValues = ref<string[]>([]);
const detectedSeparator = ref<string>("comma");

const columnsStore = useColumnsStore();

const beautifiedLabel = computed(() => {
  const colName = props.columnName || props.columnLabel;
  const allCols = [...columnsStore.rowColumns, ...columnsStore.filterableColColumns];
  const found = allCols.find(c => c.column_name === colName);
  if (found?.display_name) return found.display_name;
  return beautifyLabel(props.columnLabel) ?? "Filter";
});

// Check if we have predefined options (multi-select mode)
const hasAvailableOptions = computed(() => {
  return props.availableOptions && props.availableOptions.length > 0;
});

// Filtered options based on search
const filteredOptions = computed(() => {
  if (!props.availableOptions) return [];
  if (!optionSearch.value.trim()) return props.availableOptions;
  const search = optionSearch.value.toLowerCase();
  return props.availableOptions.filter(opt => 
    opt.toLowerCase().includes(search)
  );
});

// Effective matched values (for button label and add action)
const effectiveMatchedValues = computed(() => {
  if (hasAvailableOptions.value) {
    return selectedOptions.value;
  }
  return matchedValues.value;
});

// Multi-select helper functions
function selectAllOptions() {
  selectedOptions.value = [...(props.availableOptions || [])];
}

function clearSelectedOptions() {
  selectedOptions.value = [];
}

// Check if this filter is for GO terms
const isGoTermFilter = computed(() => {
  const label = (props.columnName || props.columnLabel).toLowerCase();
  return label === 'go_term' || label === 'go term' || label === 'goterm';
});

const detectedSeparatorLabel = computed(() => {
  const labels: Record<string, string> = {
    newline: "Newline (\\n)",
    comma: "Comma (,)",
    semicolon: "Semicolon (;)",
    pipe: "Pipe (|)",
    space: "Space/Tab",
  };
  return labels[detectedSeparator.value] || detectedSeparator.value;
});

// Reset/Initialize state when modal opens
watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      // Multi-select mode: Initialize with current filter values (synchronization!)
      if (hasAvailableOptions.value) {
        selectedOptions.value = props.currentValues ? [...props.currentValues] : [];
        optionSearch.value = "";
      } else {
        // Text input mode: reset state
        selectedOptions.value = [];
        optionSearch.value = "";
      }
      // Don't reset inputText to allow re-validation
      hasValidated.value = false;
      matchedValues.value = [];
      discardedValues.value = [];
      parsedTokens.value = [];
    }
  }
);

/**
 * Detect the dominant separator in the input text.
 * Returns the separator with the highest count.
 */
function detectDominantSeparator(text: string): string {
  const separators = {
    newline: (text.match(/\n/g) || []).length,
    comma: (text.match(/,/g) || []).length,
    semicolon: (text.match(/;/g) || []).length,
    pipe: (text.match(/\|/g) || []).length,
    space: (text.match(/[\t ]+/g) || []).length,
  };

  // Find the separator with the highest count
  let dominant: string = "comma";
  let maxCount = 0;

  for (const [sep, count] of Object.entries(separators)) {
    if (count > maxCount) {
      maxCount = count;
      dominant = sep;
    }
  }

  // If no separators found, default to comma (handles single-value input)
  return dominant;
}

/**
 * Parse the input text using the detected dominant separator.
 */
function parseInputText(text: string, separator: string): string[] {
  let regex: RegExp;

  switch (separator) {
    case "newline":
      regex = /\n/;
      break;
    case "comma":
      regex = /,/;
      break;
    case "semicolon":
      regex = /;/;
      break;
    case "pipe":
      regex = /\|/;
      break;
    case "space":
      regex = /[\t ]+/;
      break;
    default:
      regex = /,/;
  }

  return text
    .split(regex)
    .map((item) => item.trim().replace(/['"]/g, ""))
    .filter(Boolean);
}

/**
 * Validate the parsed tokens against the database.
 */
async function validateInput() {
  if (!inputText.value.trim()) return;

  isValidating.value = true;
  hasValidated.value = false;

  try {
    // Detect separator
    detectedSeparator.value = detectDominantSeparator(inputText.value);
    
    // Parse tokens
    parsedTokens.value = parseInputText(inputText.value, detectedSeparator.value);
    
    // Remove duplicates
    const uniqueTokens = [...new Set(parsedTokens.value)];
    parsedTokens.value = uniqueTokens;

    if (uniqueTokens.length === 0) {
      matchedValues.value = [];
      discardedValues.value = [];
      hasValidated.value = true;
      return;
    }

    // Validate against database
    if (isGoTermFilter.value) {
      // For GO terms, validate each token individually using the GO search API
      const matched: string[] = [];
      const discarded: string[] = [];

      // Batch validate - check if each GO term exists
      for (const token of uniqueTokens) {
        try {
          // GO terms should start with "GO:" - accept both with and without prefix
          const goId = token.startsWith("GO:") ? token : `GO:${token}`;
          const response = await axios.get(`${API_BASE_URL}/api/go/search`, {
            params: { q: goId, limit: 1 },
          });
          
          if (response.data.available && response.data.results?.length > 0) {
            // Use the exact GO ID from the result
            matched.push(response.data.results[0].id);
          } else {
            discarded.push(token);
          }
        } catch {
          discarded.push(token);
        }
      }

      matchedValues.value = [...new Set(matched)];
      discardedValues.value = discarded;
    } else {
      // For regular columns, use the distinct values endpoint to validate
      try {
        const response = await axios.post(`${API_BASE_URL}/api/data/distinct`, {
          column: props.columnName,
          values: uniqueTokens,
          ...(props.tableName ? { table_name: props.tableName } : {}),
        });

        if (response.data.matched) {
          matchedValues.value = response.data.matched;
          discardedValues.value = response.data.unmatched || 
            uniqueTokens.filter(t => !response.data.matched.includes(t));
        } else {
          // Fallback: if endpoint doesn't support batch validation, assume all are valid
          matchedValues.value = uniqueTokens;
          discardedValues.value = [];
        }
      } catch {
        // If the distinct endpoint fails, assume all tokens are valid
        // (validation will happen when filter is applied)
        matchedValues.value = uniqueTokens;
        discardedValues.value = [];
      }
    }

    hasValidated.value = true;
  } catch (error) {
    console.error("Error validating batch input:", error);
    // On error, show all as parsed but unvalidated
    matchedValues.value = parsedTokens.value;
    discardedValues.value = [];
    hasValidated.value = true;
  } finally {
    isValidating.value = false;
  }
}

/**
 * Apply the selected values as filters (replaces existing).
 */
function applyFilters() {
  const valuesToApply = effectiveMatchedValues.value;
  
  emit("apply-filters", valuesToApply);
  // Reset state
  inputText.value = "";
  hasValidated.value = false;
  matchedValues.value = [];
  discardedValues.value = [];
  parsedTokens.value = [];
  selectedOptions.value = [];
  optionSearch.value = "";
  emit("close");
}
</script>
