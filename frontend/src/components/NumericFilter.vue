<template>
  <div class="w-full max-w-lg select-none">
    <!-- Histogram above slider -->
    <div class="flex w-full h-12 items-end mb-1 px-3 space-x-[1px]">
      <div
        v-for="bin in histogramBins"
        :key="bin.bucket_id"
        class="flex-1 relative rounded-md"
        :style="{
          height:
            bin.frequency > 0
              ? `${(bin.frequency / maxFrequency) * 100 || 0}%`
              : '2px',
          backgroundColor: bin.frequency > 0 ? '#C65060' : '#E5E7EB', // accent1-500 from theme
          opacity:
            bin.bucket_upper <= localLower || bin.bucket_lower >= localUpper
              ? 0.5
              : 1,
        }"
        :aria-label="`[${bin.bucket_lower}, ${bin.bucket_upper}]: ${bin.frequency} value(s)`"
      ></div>
    </div>

    <!-- Slider container -->
    <div ref="sliderRef" class="relative ml-3 mr-3 h-6" @touchstart.prevent>
      <!-- Track background -->
      <div
        class="absolute w-full bg-gray-300 rounded-md"
        style="height: 4px; top: 50%; transform: translateY(-50%)"
      ></div>

      <!-- Highlight between thumbs -->
      <div
        class="absolute h-6 rounded-md bg-accent2-100"
        style="height: 4px; top: 50%; transform: translateY(-50%)"
        :style="highlightStyle"
      ></div>

      <!-- Lower thumb -->
      <div
        class="absolute w-6 h-6 bg-primary-900 rounded-full cursor-pointer touch-none flex items-center justify-center"
        :style="lowerThumbStyle"
        @mousedown.prevent="startDrag('lower')"
        aria-label="Lower bound"
        role="slider"
      >
        <!-- Inner circle to create hole -->
        <div class="w-4 h-4 rounded-full bg-white"></div>
      </div>

      <!-- Upper thumb -->
      <div
        class="absolute w-6 h-6 bg-primary-900 rounded-full cursor-pointer touch-none flex items-center justify-center"
        :style="upperThumbStyle"
        @mousedown.prevent="startDrag('upper')"
        aria-label="Upper bound"
        role="slider"
      >
        <!-- Inner circle to create hole -->
        <div class="w-4 h-4 rounded-full bg-white"></div>
      </div>
    </div>

    <!-- Numeric inputs under thumbs -->
    <div class="flex justify-between mt-3">
      <input
        type="number"
        v-model.number="localLower"
        @change="onManualInput"
        :min="actualMin"
        :max="localUpper"
        class="w-1/2 m-1 py-1 border-1 rounded-md text-center text-gray-700"
        aria-label="Lower bound input"
      />
      <input
        type="number"
        v-model.number="localUpper"
        @change="onManualInput"
        :min="localLower"
        :max="actualMax"
        class="w-1/2 m-1 py-1 border-1 rounded-md text-center text-gray-700"
        aria-label="Upper bound input"
      />
    </div>

    <p v-if="errorMessage" class="text-red-500 text-sm mt-2">
      {{ errorMessage }}
    </p>
    <div class="ml-1 mt-2 mb-1">
      <input
        type="checkbox"
        v-model="empty"
        class="cursor-pointer form-checkbox h-4 w-4 accent-primary-700 mr-2"
      />
      <span class="text-sm text-gray-700">Empty</span>
    </div>
  </div>
</template>
<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref, watch } from "vue";

import { API_BASE_URL } from "@/shared/Config";
import { useFiltersStore } from "@/stores/filters";
import type { ModelValue } from "./SearchFilter.vue";

const props = defineProps<{
  modelValue?: ModelValue | null;
  label?: string;
  id?: string;
  step?: number;
}>();

const empty = ref(false);

// Histogram
const histogramBins = ref<
  {
    bucket_id: number;
    bucket_lower: number;
    bucket_upper: number;
    frequency: number;
  }[]
>([]);

// Local state
const errorMessage = ref("");

const step = props.step ?? 1;

const binEdges = computed(() =>
  Array.from(
    histogramBins.value.reduce((acc, bin) => {
      acc.add(bin.bucket_lower);
      acc.add(bin.bucket_upper);
      return acc;
    }, new Set<number>()),
  ).sort((a, b) => a - b),
);

const actualMin = computed(() => binEdges.value[0] ?? 0);
const actualMax = computed(() => {
  const arr = binEdges.value;
  return arr.length > 0 ? arr[arr.length - 1] : 100;
});

const localLower = ref<number>(actualMin.value);
const localUpper = ref<number>(actualMax.value);

const maxFrequency = computed(() =>
  Math.max(...histogramBins.value.map((b) => b.frequency), 1),
);

// Drag logic
const sliderRef = ref<HTMLElement | null>(null);
const sliderWidth = ref(0);
const sliderLeft = ref(0);
const dragging = ref<"lower" | "upper" | null>(null);

// Compute percent positions of thumbs for styling
const percentLower = computed(
  () =>
    ((localLower.value! - actualMin.value) /
      (actualMax.value - actualMin.value)) *
    100,
);
const percentUpper = computed(
  () =>
    ((localUpper.value! - actualMin.value) /
      (actualMax.value - actualMin.value)) *
    100,
);

const lowerThumbStyle = computed(() => ({
  left: `calc(${percentLower.value}% - 0.75rem)`,
}));
const upperThumbStyle = computed(() => ({
  left: `calc(${percentUpper.value}% - 0.75rem)`,
}));

const highlightStyle = computed(() => {
  const [start, end] = [percentLower.value, percentUpper.value].sort(
    (a, b) => a - b,
  );
  return { left: `${start}%`, width: `${end - start}%` };
});

// Slider functions
function snapToClosestEdge(val: number): number {
  return binEdges.value.reduce((closest, edge) =>
    Math.abs(edge - val) < Math.abs(closest - val) ? edge : closest,
  );
}

function clamp(val: number): number {
  return Math.min(
    actualMax.value,
    Math.max(actualMin.value, Math.round(val / step) * step),
  );
}

function validateBounds(lower: number, upper: number): boolean {
  if (lower > upper) {
    errorMessage.value = "Lower bound cannot be greater than upper bound.";
    return false;
  }
  if (lower < actualMin.value || upper > actualMax.value) {
    errorMessage.value = `Bounds must be between ${actualMin.value} and ${actualMax.value}.`;
    return false;
  }
  errorMessage.value = "";
  return true;
}

// Convert pixel position to value
function pixelToValue(clientX: number): number {
  if (!sliderRef.value) return actualMin.value;
  const offset = clientX - sliderLeft.value;
  const percent = Math.min(1, Math.max(0, offset / sliderWidth.value));
  return clamp(actualMin.value + percent * (actualMax.value - actualMin.value));
}

// Update position while dragging
function onDrag(event: MouseEvent | TouchEvent) {
  if (!dragging.value) return;
  const clientX = "touches" in event ? event.touches[0].clientX : event.clientX;
  const newVal = snapToClosestEdge(pixelToValue(clientX));

  if (dragging.value === "lower") {
    localLower.value = Math.min(newVal, localUpper.value! - 1);
  } else {
    localUpper.value = Math.max(newVal, localLower.value! + 1);
  }
}

function stopDrag() {
  empty.value = false;
  dragging.value = null;
  localLower.value = clamp(localLower.value!);
  localUpper.value = clamp(localUpper.value!);

  if (validateBounds(localLower.value!, localUpper.value!)) {
    const isFullRange =
      localLower.value === actualMin.value &&
      localUpper.value === actualMax.value;

    emit(
      "update:modelValue",
      isFullRange
        ? null
        : { value: [localLower.value!, localUpper.value!], strict: false },
    );
  }

  window.removeEventListener("mousemove", onDrag);
  window.removeEventListener("touchmove", onDrag);
  window.removeEventListener("mouseup", stopDrag);
  window.removeEventListener("touchend", stopDrag);
  window.removeEventListener("touchcancel", stopDrag);
}

function startDrag(thumb: "lower" | "upper") {
  dragging.value = thumb;

  if (sliderRef.value) {
    const rect = sliderRef.value.getBoundingClientRect();
    sliderWidth.value = rect.width;
    sliderLeft.value = rect.left;
  }

  window.addEventListener("mousemove", onDrag);
  window.addEventListener("touchmove", onDrag, { passive: false });
  window.addEventListener("mouseup", stopDrag);
  window.addEventListener("touchend", stopDrag);
  window.addEventListener("touchcancel", stopDrag);
}

//Handle manual input
function onManualInput() {
  if (localLower.value === null || localUpper.value === null) return;

  // Clamp to min/max ranges
  //localLower.value = clamp(localLower.value);
  //localUpper.value = clamp(localUpper.value);

  if (!validateBounds(localLower.value, localUpper.value)) {
    return;
  }

  const isFullRange =
    localLower.value === actualMin.value &&
    localUpper.value === actualMax.value;

  emit(
    "update:modelValue",
    isFullRange
      ? null
      : { value: [localLower.value, localUpper.value], strict: false },
  );
}

function reset() {
  localLower.value = actualMin.value;
  localUpper.value = actualMax.value;
  empty.value = false;
  emit("update:modelValue", null);
}

const emit = defineEmits(["update:modelValue"]);
defineExpose({ reset });

watch(
  () => props.modelValue,
  (val) => {
    if (!val || val.value === null) {
      localLower.value = actualMin.value;
      localUpper.value = actualMax.value;
    } else if (
      Array.isArray(val.value) &&
      val.value.length === 2 &&
      typeof val.value[0] === "number" &&
      typeof val.value[1] === "number"
    ) {
      localLower.value = val.value[0];
      localUpper.value = val.value[1];
    }
  },
  { immediate: true },
);

// Watcher: reset filter when parent signals empty state
watch(
  () => empty.value,
  (val) => {
    if (val) {
      localLower.value = actualMin.value;
      localUpper.value = actualMax.value;

      emit("update:modelValue", {
        value: null,
        strict: false,
      });
    } else {
      const isFullRange =
        localLower.value === actualMin.value &&
        localUpper.value === actualMax.value;

      emit(
        "update:modelValue",
        isFullRange
          ? null
          : { value: [localLower.value!, localUpper.value!], strict: false },
      );
    }
  },
);

onMounted(async () => {
  try {
    const filtersStore = useFiltersStore();
    const table_names = [...filtersStore.table_names]
      .map((t) => t + "_meta")
      .join(","); // Appends _meta suffix for sample metadata queries

    const { data } = await axios.get(
      `${API_BASE_URL}/api/column_bins`,
      {
        params: {
          table_names: table_names,
          column_name: props.id || props.label,
          n_bins: 50, // Default histogram resolution
        },
      },
    );

    histogramBins.value = data;

    if (data.length) {
      localLower.value = data[0].bucket_lower;
      localUpper.value = data[data.length - 1].bucket_upper;
    }
  } catch (e) {
    console.error("Failed to fetch histogram bins", e);
  }
});
</script>
