<template>
  <div
    v-if="show"
    class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]"
    @click.self="handleCancel"
  >
    <div class="bg-white rounded-lg shadow-xl max-w-md w-full mx-4 p-6">
      <!-- Step 1: Warning -->
      <div v-if="currentStep === 'warning'">
        <div class="flex items-center gap-3 mb-4">
          <div class="text-3xl">⚠️</div>
          <h2 class="text-xl font-bold text-gray-900">Data Upload Warning</h2>
        </div>
        
        <div class="space-y-3 text-gray-700 mb-6">
          <p>
            You are about to upload sequence data to the <strong>NCBI BLAST server</strong>, 
            which is a public external service.
          </p>
          
          <p class="bg-yellow-50 border border-yellow-200 rounded p-3">
            <strong class="text-yellow-800">Important:</strong> If you are working with 
            unpublished or confidential data, please be aware that this information will 
            be transmitted to and processed on NCBI's public servers. Once uploaded, the 
            data will no longer be under your exclusive control.
          </p>
          
          <p>
            Do you want to proceed with the BLAST search?
          </p>
        </div>
        
        <div class="flex gap-3 justify-end">
          <button
            @click="handleCancel"
            class="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            @click="proceedToDatabase"
            class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
          >
            Proceed to BLAST
          </button>
        </div>
      </div>

      <!-- Step 2: Database Selection -->
      <div v-else-if="currentStep === 'database'">
        <div class="flex items-center gap-3 mb-4">
          <div class="text-3xl">🔬</div>
          <h2 class="text-xl font-bold text-gray-900">Select Database</h2>
        </div>
        
        <div class="mb-6">
          <p class="text-gray-700 mb-4">
            Choose the database for your {{ blastTypeLabel }} BLAST search:
          </p>
          
          <div class="space-y-3">
            <label
              v-for="option in databaseOptions"
              :key="option.value"
              class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
              :class="{ 'border-blue-500 bg-blue-50': selectedDatabase === option.value }"
            >
              <input
                type="radio"
                :value="option.value"
                v-model="selectedDatabase"
                class="mt-1 w-4 h-4 text-blue-600 focus:ring-blue-500"
              />
              <div class="flex-1">
                <div class="font-medium text-gray-900">{{ option.label }}</div>
                <div class="text-sm text-gray-600 mt-1">{{ option.description }}</div>
              </div>
            </label>
          </div>
        </div>
        
        <div class="flex gap-3 justify-end">
          <button
            @click="handleCancel"
            class="px-4 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300 transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            @click="submitBlast"
            class="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors font-medium"
          >
            Start BLAST
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { 
  getBlastType, 
  getAvailableDatabases, 
  getDefaultDatabase,
  type BlastDatabase 
} from '@/shared/blast';

const props = defineProps<{
  show: boolean;
  fieldType?: string;
}>();

const emit = defineEmits<{
  proceed: [database: BlastDatabase];
  cancel: [];
}>();

type Step = 'warning' | 'database';

const currentStep = ref<Step>('warning');
const selectedDatabase = ref<BlastDatabase | null>(null);

const blastTypeLabel = computed(() => {
  if (!props.fieldType) return '';
  const type = getBlastType(props.fieldType);
  return type === 'protein' ? 'Protein' : 'RNA';
});

const databaseOptions = computed(() => {
  if (!props.fieldType) return [];
  const type = getBlastType(props.fieldType);
  return getAvailableDatabases(type);
});

// Reset state when modal is opened
watch(() => props.show, (newShow) => {
  if (newShow) {
    currentStep.value = 'warning';
    if (props.fieldType) {
      const type = getBlastType(props.fieldType);
      selectedDatabase.value = getDefaultDatabase(type);
    }
  }
});

function proceedToDatabase() {
  currentStep.value = 'database';
}

function submitBlast() {
  if (selectedDatabase.value) {
    emit('proceed', selectedDatabase.value);
  }
}

function handleCancel() {
  currentStep.value = 'warning';
  emit('cancel');
}
</script>
