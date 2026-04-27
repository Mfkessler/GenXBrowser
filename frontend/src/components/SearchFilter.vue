<template>
  <div class="relative py-1 border-b border-gray-300">
    <CollapseWrapper
      v-if="label !== 'tissue_types'"
      ref="collapseWrapperRef"
      v-model="collapseWrapperIsOpen"
      :disabled="!pillItemsActive"
      :deletable="pillItemsPresent"
      :title="beautifiedLabel"
      :description="description"
      @remove:filter="handleRemoveAllPills"
    >
      <div class="py-2">
        <!-- Note: array-type columns are rendered as text filters -->
        <TextFilter
          v-if="
            props.type?.toLowerCase() === 'text' ||
            props.type?.toLowerCase() === 'array'
          "
          :key="id"
          v-model="modVal"
          :label="label"
          :id="id"
          :type="props.type"
          ref="instanceRef"
        />
        <BooleanFilter
          v-if="props.type?.toLowerCase() === 'boolean'"
          :key="id"
          v-model="modVal"
          :label="label"
          :id="id"
          ref="instanceRef"
        />
        <NumericFilter
          v-if="
            props.type?.toLowerCase() === 'bigint' ||
            props.type?.toLowerCase() === 'double precision'
          "
          :key="id"
          v-model="modVal"
          :label="label"
          :id="id"
          ref="instanceRef"
        />
      </div>
      <slot name="label-suffix" />
    </CollapseWrapper>
  </div>
</template>
<script setup lang="ts">
import { isEqual } from "lodash-es";
import { computed, ref, watch } from "vue";

import CollapseWrapper from "./CollapseWrapper.vue";
import BooleanFilter from "./BooleanFilter.vue";
import NumericFilter from "./NumericFilter.vue";
import TextFilter from "./TextFilter.vue";
import { beautifyLabel } from "@/shared/utils";

export interface ModelValue {
  value: string | boolean | [number, number] | null;
  /** How multiple values combine ("or" default, "and" for AND). */
  match_mode?: "or" | "and";
  /** Exact match (true, default) vs substring match (false). */
  exact?: boolean;
}

const props = defineProps<{
  modelValue?: ModelValue | null;
  label: string;
  description?: string;
  type?: string;
  id?: string;
}>();

const modVal = ref<ModelValue | null>(props.modelValue ?? null);

const beautifiedLabel = computed(() => beautifyLabel(props.label) ?? "Filter");

const collapseWrapperIsOpen = ref(modVal.value !== null);

const collapseWrapperRef = ref<InstanceType<typeof CollapseWrapper> | null>(
  null,
);
const instanceRef = ref<InstanceType<typeof TextFilter> | null>(null);

const collapse = () => {
  collapseWrapperRef.value?.collapse();
};

const uncollapse = () => {
  collapseWrapperRef.value?.uncollapse();
};

const handleRemoveAllPills = () => {
  instanceRef.value?.reset();
};

const pillItemsPresent = computed(() => {
  return modVal.value !== null;
});

const pillItemsActive = computed(() => {
  return pillItemsPresent.value || modVal.value === null;
});

const emit = defineEmits(["update:modelValue"]);
defineExpose({ collapse, uncollapse });

// Update local modVal when prop changes
watch(
  () => props.modelValue,
  (newVal) => {
    if (!isEqual(newVal, modVal.value)) {
      modVal.value = newVal ? { ...newVal } : null; // create new object reference
    }
  },
  { deep: true, immediate: true },
);

// Emit changes when modVal changes
watch(
  modVal,
  (newVal) => {
    if (!isEqual(newVal, props.modelValue)) {
      emit("update:modelValue", newVal);
    }
  },
  { deep: true },
);
</script>
