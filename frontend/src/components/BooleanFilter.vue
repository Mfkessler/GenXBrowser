<template>
  <div class="flex items-center select-none">
    <!-- Left label -->
    <span
      class="text-gray-700 text-md ml-3 mr-3 cursor-pointer"
      @click="setValue(false)"
      :aria-pressed="localValue === false"
      role="button"
      tabindex="0"
      @keydown.enter.prevent="setValue(false)"
      @keydown.space.prevent="setValue(false)"
    >
      False
    </span>

    <!-- Toggle control -->
    <div
      class="relative w-[60px] h-[30px] rounded-full cursor-pointer transition-colors"
      :class="{
        'bg-gray-300': localValue === null,
        'bg-green-500': localValue === true,
        'bg-red-500': localValue === false,
      }"
      role="checkbox"
      :aria-checked="ariaChecked"
    >
      <!-- Sliding highlight -->
      <div
        class="absolute top-[2px] left-[2px] w-[26px] h-[26px] bg-white rounded-full transition-transform duration-300 ease-in-out"
        :class="{
          'translate-x-0': localValue === false,
          'translate-x-[15px]': localValue === null,
          'translate-x-[30px]': localValue === true,
        }"
      ></div>

      <!-- Invisible clickable areas to select state -->
      <button
        type="button"
        @click="setValue(false)"
        class="absolute left-0 top-0 w-[30px] h-[30px] rounded-l-full focus:outline-none"
        :aria-pressed="localValue === false"
        tabindex="-1"
        aria-label="False"
      ></button>
      <button
        type="button"
        @click="setValue(null)"
        class="absolute left-[20px] top-0 w-[20px] h-[30px] focus:outline-none"
        :aria-pressed="localValue === null"
        tabindex="-1"
        aria-label="Disabled"
      ></button>
      <button
        type="button"
        @click="setValue(true)"
        class="absolute right-0 top-0 w-[20px] h-[30px] rounded-r-full focus:outline-none"
        :aria-pressed="localValue === true"
        tabindex="-1"
        aria-label="True"
      ></button>
    </div>

    <!-- Right label -->
    <span
      class="text-gray-700 text-md ml-3 mr-3 cursor-pointer"
      @click="setValue(true)"
      :aria-pressed="localValue === true"
      role="button"
      tabindex="0"
      @keydown.enter.prevent="setValue(true)"
      @keydown.space.prevent="setValue(true)"
    >
      True
    </span>
    <input
      type="checkbox"
      v-model="empty"
      class="cursor-pointer form-checkbox h-4 w-4 accent-primary-700 mr-2"
    />
    <span class="text-sm text-gray-700">Empty</span>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from "vue";

import { type ModelValue } from "./SearchFilter.vue";
import { parseBoolean } from "@/shared/utils";

const props = defineProps<{
  modelValue?: ModelValue | null;
}>();

const localValue = ref<boolean | null>(
  parseBoolean(props.modelValue?.value) ?? null,
);
const empty = ref(false);

function setValue(val: boolean | null) {
  if (localValue.value !== val) {
    localValue.value = val;
    empty.value = false; // uncheck empty when toggled
  }
}

const ariaChecked = computed(() => {
  if (localValue.value === true) return "true";
  if (localValue.value === false) return "false";
  return "mixed"; // For null/disabled
});

function reset() {
  localValue.value = null;
  empty.value = false;
}

const emit = defineEmits(["update:modelValue"]);
defineExpose({ reset });

// Update localValue when prop changes
watch(
  () => props.modelValue,
  (newVal) => {
    localValue.value = parseBoolean(newVal?.value) ?? null;
  },
  { deep: true },
);

watch(
  [localValue, empty],
  () => {
    if (!empty.value && localValue.value === null) {
      emit("update:modelValue", null);
    } else {
      emit("update:modelValue", {
        value: localValue.value,
        strict: false,
      });
    }
  },
  { deep: true },
);

// Watcher: reset filter when parent signals empty state
watch(
  () => empty.value,
  () => {
    localValue.value = null;
  },
);
</script>
