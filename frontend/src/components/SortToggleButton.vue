<template>
    <button
      aria-label="Toggle the order of the elements between ascending and descending"
      @click="toggleState"
      class="px-4 py-2 text-sm font-medium justify-center rounded-md transition-colors duration-200 ease-in-out border-1 flex items-center whitespace-nowrap border-primary-900"
      :disabled="disabled"
      v-tooltip="'Toggle sort order'"
      :class="[
        {
          'cursor-not-allowed': disabled,
          'hover:bg-primary-100': !disabled,
        },
      ]"
    >
      <span
        class="asc"
        :class="{
          'text-primary-900': modelValue === 'asc',
          'text-gray-300': modelValue === 'desc' || disabled,
        }"
        >ASC</span
      >
      <span class="mx-1">|</span>
      <span
        class="desc"
        :class="{
          'text-primary-900': modelValue === 'desc',
          'text-gray-300': modelValue === 'asc' || disabled,
        }"
        >DESC</span
      >
    </button>
</template>

<script setup lang="ts">
//IMPORT
import { onUnmounted, watch } from "vue";

//VARIABLES
const props = defineProps<{
  modelValue: string | undefined;
  disabled?: boolean;
}>();

//FUNCTIONS
const toggleState = () => {
  if (props.modelValue === "asc") {
    emit("update:modelValue", "desc");
  } else {
    emit("update:modelValue", "asc");
  }
};

//EMIT
const emit = defineEmits(["update:modelValue"]);

//WATCHERS
const propsWatcher = watch(
  () => props,
  () => {
    if (props.disabled) {
      emit("update:modelValue", undefined);
    } else if (!props.disabled && props.modelValue === undefined) {
      emit("update:modelValue", "asc");
    }
  },
  { deep: true },
);

onUnmounted(() => {
  propsWatcher();
});
</script>
