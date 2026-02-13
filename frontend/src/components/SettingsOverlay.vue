<template>
  <div
    v-if="show"
    class="fixed inset-0 flex justify-center items-center z-50"
    style="background-color: rgba(0, 0, 0, 0.5)"
  >
    <div
      class="bg-white p-6 rounded-lg shadow-lg w-[30%] max-h-[90vh] flex flex-col"
    >
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-xl font-bold cursor-default">Visualization Settings</h1>
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

      <div class="flex items-center gap-2 mb-2">
        <p class="block text-sm font-semibold text-gray-700">Expression</p>
        <InfoTooltip
          title="Expression Display"
          description="Choose how expression data is normalized and transformed. Normalized Values: TPM (within-sample) or TMM (between-sample). Transformations: Log2 or Z-Score for visualization. Raw Data: Unprocessed counts."
        />
      </div>
      <select
        v-model="selectedExpressionOption"
        @change="onExpressionChange"
        class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 mb-4"
      >
        <optgroup
          v-for="section in EXPRESSION_SECTIONS"
          :key="section.label"
          :label="section.label"
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

      <p v-if="showColorSchema" class="block mb-2 text-sm font-semibold text-gray-700"> Select color schema: </p>
      <select
        v-if="showColorSchema"
        v-model="colorSchema"
        class="border rounded px-2 py-1 h-9"
      >
        <option disabled value="">Color schema</option>
        <option v-for="opt in colorOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>

      <button
        @click="closeOverlay"
        class="mt-2 border border-accent1-900 bg-accent1-100 text-accent1-900 hover:text-accent1-100 hover:bg-accent1-900 py-2 rounded-md w-full"
      >
        Close
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  defineProps,
  defineEmits,
  ref,
} from "vue";
import { useVisualizationStore } from "@/stores/visualization";
import InfoTooltip from "@/components/InfoTooltip.vue";
import {
  EXPRESSION_SECTIONS,
  getExpressionOption,
} from "@/shared/ExpressionDisplay";


// Props
const props = defineProps<{
  show: boolean;
  showColorSchema: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:colorSchema', value: string): void;
  (e: 'close'): void;
}>();

const visualizationStore = useVisualizationStore();
const selectedExpressionOption = ref(visualizationStore.expressionDisplay.optionId);
const colorSchema = ref('');

const onExpressionChange = () => {
  const option = getExpressionOption(selectedExpressionOption.value);
  if (option) {
    visualizationStore.setExpressionDisplay(option.id, option.layer, option.transform);
  }
};

function closeOverlay() {
  emit('update:colorSchema', colorSchema.value);
  emit('close');
}

const colorOptions = [
  {value: 'observable10', label: 'Observable10'},
  {value: 'category10', label: 'Category10'},
  {value: 'dark2', label: 'Dark2'},
  {value: 'set1', label: 'Set1'},
  {value: 'set2', label: 'Set2'},
  {value: 'set3', label: 'Set3'},
  {value: 'accent', label: 'Accent'},
  {value: 'paired', label: 'Paired'},
];

</script>
