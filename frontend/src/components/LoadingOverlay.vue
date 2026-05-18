<template>
  <div
    class="loading-overlay fixed inset-0 z-50 grid place-items-center bg-white/85 backdrop-blur-[1px]"
    :style="overlayStyle"
    role="status"
    aria-live="polite"
  >
    <div :class="containerClasses">
      <div v-if="hasProgress" class="w-full space-y-2">
        <div class="flex items-center justify-between gap-4 text-xs font-medium text-gray-600">
          <span>{{ label }}</span>
          <span>{{ normalizedProgress }}%</span>
        </div>
        <div class="h-2 w-full overflow-hidden rounded-full bg-gray-200" aria-hidden="true">
          <div
            class="h-full rounded-full bg-primary-500 transition-[width] duration-200 ease-out"
            :style="{ width: `${normalizedProgress}%` }"
          ></div>
        </div>
      </div>

      <div v-else class="flex flex-col items-center gap-3">
        <div class="h-9 w-9 rounded-full border-2 border-gray-200 border-t-primary-500 animate-spin"></div>
        <div class="text-xs font-medium text-gray-600">{{ label }}</div>
      </div>

      <button
        v-if="cancellable"
        type="button"
        class="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
        @click="emit('cancel')"
      >
        Cancel
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, onMounted, onUnmounted, ref, type Ref } from "vue";

const props = withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg';
    progress?: number | null;
    label?: string;
    cancellable?: boolean;
  }>(),
  {
    size: 'lg',
    progress: null,
    label: 'Loading',
    cancellable: false,
  }
);

const emit = defineEmits<{
  cancel: [];
}>();

const sidebarOpen = inject<Ref<boolean> | undefined>("sidebarOpen", undefined);
const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1024);

function updateViewportWidth() {
  if (typeof window === "undefined") return;
  viewportWidth.value = window.innerWidth;
}

onMounted(() => {
  updateViewportWidth();
  window.addEventListener("resize", updateViewportWidth);
});

onUnmounted(() => {
  window.removeEventListener("resize", updateViewportWidth);
});

const overlayStyle = computed(() => {
  const sidebarWidth = sidebarOpen?.value && viewportWidth.value >= 768 ? 320 : 0;
  return { left: `${sidebarWidth}px` };
});

const hasProgress = computed(() => typeof props.progress === 'number' && Number.isFinite(props.progress));

const normalizedProgress = computed(() => {
  if (!hasProgress.value) return 0;
  return Math.min(100, Math.max(0, Math.round(props.progress ?? 0)));
});

const containerClasses = computed(() => {
  const base = 'flex w-[min(22rem,calc(100%-2rem))] flex-col items-center justify-center gap-4 rounded-md border border-gray-200 bg-white/95 px-5 py-4 text-center shadow-lg';
  switch (props.size) {
    case 'sm':
      return `${base} max-w-56 px-4 py-3`;
    case 'md':
      return `${base} max-w-72`;
    case 'lg':
    default:
      return base;
  }
});
</script>
