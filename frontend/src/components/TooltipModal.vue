<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { getDisplayName, sequenceFields } from "@/shared/metadataDisplayNames";
import { useColumnsStore } from "@/stores/columns";
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { getEntityMetadataLabel } from "@/shared/dataTypeLabels";
import { openBlast as openBlastUtil, isBlastableSequence } from "@/shared/blast";
import type { BlastDatabase } from "@/shared/blast";
import { buildPhyloRouteTarget } from "@/shared/phyloNavigation";
import BlastWarningModal from "./BlastWarningModal.vue";
import InfoTooltip from "./InfoTooltip.vue";

export interface TooltipModalProps {
  show: boolean;
  rowData: Record<string, unknown> | null;
  tableName: string;
  idColumn: string;
  heatmapCols: string[];
  columnValue: string;
  cellValue: string | number;
}

const props = defineProps<TooltipModalProps>();
const route = useRoute();
const router = useRouter();
const columnsStore = useColumnsStore();
const emit = defineEmits<{
  close: [];
}>();

const copiedField = ref<string | null>(null);
const loadedSequences = ref<Record<string, string>>({});
const loadingSequences = ref<Set<string>>(new Set());
const showBlastWarning = ref(false);
const pendingBlastParams = ref<{ fieldType: string; sequence: string } | null>(null);

const metadataFields = computed(() => {
  if (!props.rowData) return [];
  
  return Object.keys(props.rowData).filter(
    (key) => !props.heatmapCols.includes(key) && key !== props.idColumn
  );
});

const visibleSequenceFields = computed(() => new Set(
  columnsStore.rowColumns
    .map((column) => column.column_name)
    .filter((columnName) => sequenceFields.includes(columnName))
));

const identificationFields = computed(() => {
  return metadataFields.value.filter((key) =>
    ["gene_id", "genename", "ortho_id", "hog"].includes(key)
  );
});

// Helper to check if a field looks like a sample value (numeric expression data)
const isSampleValueField = (key: string, value: unknown): boolean => {
  // If it's a number (expression value), it's likely a sample column
  if (typeof value === 'number') return true;
  // If it starts with tissue_type_, it's metadata for samples
  if (key.startsWith('tissue_type_')) return true;
  return false;
};

const annotationFields = computed(() => {
  if (!props.rowData) return [];
  
  return metadataFields.value.filter((key) => {
    // Skip sequence fields and identification fields
    if (sequenceFields.includes(key) || identificationFields.value.includes(key)) {
      return false;
    }
    
    // Skip fields with empty values
    const value = props.rowData?.[key];
    if (value === "" || value === null || value === undefined) {
      return false;
    }
    
    // Skip sample value columns (numeric expression data) and tissue_type metadata
    if (isSampleValueField(key, value)) {
      return false;
    }
    
    return true;
  });
});

const sequences = computed(() => {
  return metadataFields.value.filter(
    (key) => sequenceFields.includes(key) && visibleSequenceFields.value.has(key)
  );
});

const selectedOrthogroup = computed(() => {
  if (!props.rowData) return '';
  const orthoId = props.rowData.ortho_id;
  return typeof orthoId === 'string' ? orthoId.trim() : '';
});

const closeOverlay = () => {
  emit("close");
};

const isNewickField = (key: string): boolean => key === 'newick_str';

const canOpenPhyloTree = (key: string): boolean => {
  return isNewickField(key) && selectedOrthogroup.value.length > 0;
};

const openPhyloTree = () => {
  if (!selectedOrthogroup.value) return;

  router.push(
    buildPhyloRouteTarget(
      route.params.table_names,
      props.tableName,
      selectedOrthogroup.value,
      route.query as Record<string, unknown>,
    )
  );
  closeOverlay();
};

const getFieldValue = (key: string): string => {
  if (!props.rowData) return "";
  
  const value = props.rowData[key];
  
  // Check if it's a sequence field and if we have loaded data
  if (sequenceFields.includes(key) && loadedSequences.value[key]) {
    return loadedSequences.value[key];
  }
  
  return formatValue(value);
};

const loadSequenceIfNeeded = async (key: string) => {
  if (!props.rowData || !sequenceFields.includes(key)) return;
  
  const value = props.rowData[key];
  
  // If value is [BLOB], load the actual sequence
  if (value === "[BLOB]") {
    if (loadingSequences.value.has(key)) return; // Already loading
    
    loadingSequences.value.add(key);
    
    try {
      // Fetch the full row data with sequences
      const response = await axios.post(`${API_BASE_URL}/api/data`, {
        table_name: props.tableName,
        filters: {
          [props.idColumn]: props.rowData[props.idColumn]
        }
      });
      
      const data = response.data.data || response.data;
      if (Array.isArray(data) && data.length > 0) {
        const fullRow = data[0] as Record<string, unknown>;
        
        if (fullRow[key] && fullRow[key] !== "[BLOB]") {
          loadedSequences.value[key] = String(fullRow[key]);
        } else {
          console.warn(`${key} is still [BLOB] or empty in backend response`);
        }
      }
    } catch (error) {
      console.error(`Failed to load sequence for ${key}:`, error);
    } finally {
      loadingSequences.value.delete(key);
    }
  } else if (value && value !== "[BLOB]") {
    // Already have the data
    loadedSequences.value[key] = String(value);
  }
};

const copyToClipboard = async (text: string, fieldName: string) => {
  try {
    await navigator.clipboard.writeText(text);
    copiedField.value = fieldName;
    setTimeout(() => {
      copiedField.value = null;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy:", err);
  }
};

const openBlast = (fieldType: string, sequence: string) => {
  pendingBlastParams.value = { fieldType, sequence };
  showBlastWarning.value = true;
};

const proceedWithBlast = (database: BlastDatabase) => {
  if (pendingBlastParams.value) {
    openBlastUtil(pendingBlastParams.value.fieldType, pendingBlastParams.value.sequence, database);
  }
  showBlastWarning.value = false;
  pendingBlastParams.value = null;
};

const cancelBlast = () => {
  showBlastWarning.value = false;
  pendingBlastParams.value = null;
};

const formatValue = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (value === "[BLOB]") return "[Loading...]";
  if (Array.isArray(value)) {
    return value.join(", ");
  }
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
};

// Load sequences when modal opens
watch(() => props.show, (isShown) => {
  if (isShown && props.rowData) {
    // Reset loaded sequences for new data
    loadedSequences.value = {};
    
    // Load all sequence fields
    sequences.value.forEach(key => {
      loadSequenceIfNeeded(key);
    });
  }
}, { immediate: true });
</script>

<template>
  <div
    v-if="show && rowData"
    class="fixed inset-0 flex justify-center items-center z-50"
    style="background-color: rgba(0, 0, 0, 0.5)"
    @click.self="closeOverlay"
  >
    <div
      class="bg-white p-6 rounded-lg shadow-lg w-[50%] max-h-[90vh] flex flex-col"
    >
      <!-- Header -->
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-xl font-bold cursor-default">{{ getEntityMetadataLabel() }}</h1>
        <button
          @click="closeOverlay"
          class="text-gray-700 rounded-full p-2 hover:bg-gray-100"
          aria-label="Close overlay"
        >
          <svg
            class="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            ></path>
          </svg>
        </button>
      </div>

      <!-- Scrollable Content -->
      <div class="flex-grow overflow-y-auto space-y-6 pr-2">
        <!-- Cell Context -->
        <div class="bg-gray-50 p-4 rounded-md border border-gray-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">
            Expression Data
          </h2>
          <div class="space-y-2">
            <!-- Gene ID -->
            <div class="flex flex-col">
              <div class="flex justify-between items-center mb-1">
                <span class="font-medium text-gray-600 text-sm">{{
                  getDisplayName(idColumn)
                }}</span>
                <button
                  @click="copyToClipboard(String(rowData[idColumn]), idColumn)"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === idColumn ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm break-all">
                {{ rowData[idColumn] }}
              </div>
            </div>

            <!-- Column -->
            <div class="flex flex-col">
              <div class="flex justify-between items-center mb-1">
                <span class="font-medium text-gray-600 text-sm">Column</span>
                <button
                  @click="copyToClipboard(columnValue, 'column')"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === 'column' ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm break-all">
                {{ columnValue }}
              </div>
            </div>

            <!-- Value -->
            <div class="flex flex-col">
              <div class="flex justify-between items-center mb-1">
                <span class="font-medium text-gray-600 text-sm">Value</span>
                <button
                  @click="copyToClipboard(String(cellValue), 'value')"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === 'value' ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm">
                {{ cellValue }}
              </div>
            </div>
          </div>
        </div>

        <!-- Identification Section -->
        <div v-if="identificationFields.length > 0" class="bg-gray-50 p-4 rounded-md border border-gray-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">
            Identification
          </h2>
          <div class="space-y-2">
            <div
              v-for="key in identificationFields"
              :key="key"
              class="flex flex-col"
            >
              <div class="flex justify-between items-center mb-1">
                <span class="font-medium text-gray-600 text-sm">{{
                  getDisplayName(key)
                }}</span>
                <button
                  @click="copyToClipboard(getFieldValue(key), key)"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === key ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm break-all">
                {{ getFieldValue(key) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Annotations Section -->
        <div v-if="annotationFields.length > 0" class="bg-gray-50 p-4 rounded-md border border-gray-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">Annotations</h2>
          <div class="space-y-2">
            <div v-for="key in annotationFields" :key="key" class="flex flex-col">
              <div class="flex justify-between items-center mb-1">
                <span class="font-medium text-gray-600 text-sm">{{
                  getDisplayName(key)
                }}</span>
                <div class="flex items-center gap-1">
                  <button
                    v-if="canOpenPhyloTree(key)"
                    @click="openPhyloTree()"
                    class="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                  >
                    View
                  </button>
                  <button
                    @click="copyToClipboard(getFieldValue(key), key)"
                    class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                  >
                    {{ copiedField === key ? "✓ Copied!" : "📋 Copy" }}
                  </button>
                </div>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm break-all">
                {{ getFieldValue(key) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Sequences Section -->
        <div v-if="sequences.length > 0" class="bg-gray-50 p-4 rounded-md border border-gray-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">Sequences</h2>
          <div class="space-y-3">
            <div v-for="key in sequences" :key="key" class="flex flex-col">
              <div class="flex justify-between items-center mb-1">
                <div class="flex items-center">
                  <span class="font-medium text-gray-600 text-sm">{{
                    getDisplayName(key)
                  }}</span>
                  <InfoTooltip
                    v-if="key === 'rna_seq'"
                    title="cDNA Sequence"
                    description="Complementary DNA derived from mRNA. Lowercase letters indicate repetitive sequences (soft-masked regions)."
                  />
                </div>
                <div 
                  v-if="getFieldValue(key) && getFieldValue(key) !== '[Loading...]' && getFieldValue(key) !== '—'"
                  class="flex gap-1 items-center"
                >
                  <button
                    v-if="canOpenPhyloTree(key)"
                    @click="openPhyloTree()"
                    class="px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
                  >
                    View
                  </button>
                  <!-- BLAST Button -->
                  <button
                    v-if="isBlastableSequence(key)"
                    @click="openBlast(key, getFieldValue(key))"
                    class="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex items-center gap-1"
                    :disabled="loadingSequences.has(key)"
                    aria-label="Search sequence on NCBI BLAST"
                    v-tooltip="'Search sequence on NCBI BLAST'"
                  >
                    🧬 BLAST
                  </button>
                  <!-- Copy Button -->
                  <button
                    @click="copyToClipboard(getFieldValue(key), key)"
                    class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                    :disabled="loadingSequences.has(key)"
                  >
                    {{ 
                      loadingSequences.has(key) ? "Loading..." :
                      copiedField === key ? "✓ Copied!" : "📋 Copy" 
                    }}
                  </button>
                </div>
              </div>
              <div
                v-if="getFieldValue(key) && getFieldValue(key) !== '—'"
                class="bg-white p-3 rounded border border-gray-300 font-mono text-xs break-all max-h-32 overflow-y-auto"
                style="word-break: break-all; overflow-x: hidden;"
              >
                {{ getFieldValue(key) }}
              </div>
              <div v-else class="text-gray-400 text-sm italic">
                No sequence available
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="mt-4 flex justify-end">
        <button
          @click="closeOverlay"
          class="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  </div>
  
  <!-- BLAST Warning Modal (teleported to body to avoid parent constraints) -->
  <Teleport to="body">
    <BlastWarningModal
      :show="showBlastWarning"
      :field-type="pendingBlastParams?.fieldType"
      @proceed="proceedWithBlast"
      @cancel="cancelBlast"
    />
  </Teleport>
</template>

<style scoped>
/* Custom scrollbar for better aesthetics */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Prevent horizontal scrollbar on all content boxes */
.break-all {
  word-break: break-all;
  overflow-wrap: break-word;
  overflow-x: hidden;
}
</style>
