<template>
  <div
    class="loading-overlay fixed inset-0 z-50 grid place-items-center bg-white/85 backdrop-blur-[1px]"
    :style="overlayStyle"
    role="status"
    aria-live="polite"
  >
    <div :class="containerClasses">
      <div class="flex flex-col items-center gap-3">
        <svg
          class="h-10 w-10 animate-spin text-primary-500"
          viewBox="0 0 48 48"
          aria-hidden="true"
        >
          <circle
            class="text-gray-200"
            cx="24"
            cy="24"
            r="18"
            fill="none"
            stroke="currentColor"
            stroke-width="4"
          />
          <circle
            cx="24"
            cy="24"
            r="18"
            fill="none"
            stroke="currentColor"
            stroke-width="4"
            stroke-linecap="round"
            stroke-dasharray="76 38"
          />
        </svg>
        <div class="space-y-1">
          <div class="text-sm font-semibold text-gray-800">{{ statusTitle }}</div>
          <div v-if="statusHint" class="text-xs font-medium text-gray-500">{{ statusHint }}</div>
        </div>
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
    label?: string;
    primaryStatus?: string;
    currentPhaseHint?: string;
    cancellable?: boolean;
    /**
     * When true, the overlay always spans the full viewport width and
     * ignores the app sidebar offset. Use this for overlays rendered inside
     * modals that are teleported to <body> and already cover the sidebar
     * (e.g. DataManagerModal, OverlayTable), otherwise a stripe to the left
     * of the sidebar boundary is left uncovered, letting background content
     * flash through underneath.
     */
    fullViewport?: boolean;
  }>(),
  {
    size: 'lg',
    label: 'Loading',
    primaryStatus: undefined,
    currentPhaseHint: undefined,
    cancellable: false,
    fullViewport: false,
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
  if (props.fullViewport) return { left: '0px' };
  const sidebarWidth = sidebarOpen?.value && viewportWidth.value >= 768 ? 320 : 0;
  return { left: `${sidebarWidth}px` };
});

const statusTitle = computed(() => props.primaryStatus || props.label);
const statusHint = computed(() => props.currentPhaseHint?.trim() || 'Working on the analysis');

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
