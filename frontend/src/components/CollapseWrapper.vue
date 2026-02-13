<template>
  <div class="collapsible-wrapper">
    <div
      class="w-full text-lg font-medium flex items-center justify-between pb-1"
    >
      <div class="flex items-center">
        <span class="text-gray-700 cursor-default">
          {{ modelValue ? actualOpenText : actualClosedText }}
        </span>

        <!-- 🛈 Info Tooltip Icon -->
        <InfoTooltip
          :title="title"
          :description="description"
          :hidden="!description"
        />
      </div>
      <template v-if="deletable">
        <!-- Icon button for delete -->
        <button
          @click="remove"
          type="button"
          class="cursor-pointer p-1 rounded-full border-1 border-accent1-900 bg-accent1-100 hover:bg-accent1-900 text-accent1-900 hover:text-accent1-100"
          aria-label="Remove"
          v-tooltip="'Remove'"
        >
          <svg
            class="w-5 h-5"
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
      </template>
      <template v-else>
        <!-- ▼ Collapse/Expand Icon Button -->
        <button
          @click="toggle"
          :disabled="disabled"
          type="button"
          class="cursor-pointer p-1 rounded-full border-1 border-primary-900 bg-primary-100 hover:bg-primary-900 text-primary-900 hover:text-primary-100"
          aria-label="Toggle"
          v-tooltip="'Toggle'"
        >
          <svg
            class="w-5 h-5 transition-transform duration-300"
            :class="{
              'rotate-180': modelValue,
              'opacity-0': disabled,
            }"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </template>
    </div>
    <transition name="collapse">
      <div v-show="modelValue">
        <slot></slot>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";

import InfoTooltip from "./InfoTooltip.vue";

const props = defineProps<{
  modelValue: boolean;
  disabled: boolean;
  deletable: boolean;
  title?: string;
  description?: string;
}>();

const actualOpenText = computed(() =>
  props.title ? `Select ${props.title}:` : "Close",
);
const actualClosedText = computed(() => props.title ?? "Open");

const emit = defineEmits(["update:modelValue", "remove:filter"]);

const toggle = () => {
  emit("update:modelValue", !props.modelValue);
};

const remove = () => {
  emit("remove:filter");
};

const collapse = () => {
  emit("update:modelValue", false);
};

const uncollapse = () => {
  emit("update:modelValue", true);
};

defineExpose({
  collapse,
  uncollapse,
});
</script>
