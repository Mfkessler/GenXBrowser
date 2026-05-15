<template>
  <div class="checkbox-selector">
    <div class="grid grid-cols-2 gap-2">
      <div v-for="option in options" :key="option" class="flex items-center">
        <input
          type="checkbox"
          :id="option"
          :value="option"
          v-model="selectedOptions"
          class="mr-2 cursor-pointer accent-primary-700"
        />
        <label class="text-sm text-gray-700" :for="option">{{
          displayNames?.[option] || getDisplayName(option)
        }}</label>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
//IMPORT
import { computed } from "vue";

import { getDisplayName } from "@/shared/metadataDisplayNames";

//VARIABLES
const props = defineProps<{
  options: string[];
  modelValue: string[];
  displayNames?: Record<string, string>;
}>();

//EMITS
const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const selectedOptions = computed({
  get: () => props.modelValue,
  set: (value) => emit("update:modelValue", value),
});

</script>
