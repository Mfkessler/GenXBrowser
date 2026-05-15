<template>
  <div class="relative ml-2 flex items-center">
    <button
      ref="triggerRef"
      @mouseenter="showTooltip = true"
      @mouseleave="showTooltip = false"
      @focus="showTooltip = true"
      @blur="showTooltip = false"
      class="rounded-full text-gray-700 w-4 h-4 flex items-center justify-center text-xs focus:outline-none hover:text-primary-600"
    >
      ?
    </button>

    <Teleport to="body">
      <div
        v-if="showTooltip && (title || description)"
        ref="floatingRef"
        :style="floatingStyles"
        class="z-[99999] bg-blue-600 text-white text-xs rounded-md px-3 py-2 max-w-xs shadow-lg pointer-events-none"
        role="tooltip"
      >
        <template v-if="title">
          <strong>{{ title }}</strong><span v-if="description">: </span>
        </template>
        <span>{{ description }}</span>
        <div
          ref="arrowRef"
          :style="arrowStyles"
          class="absolute w-2 h-2 bg-blue-600 rotate-45"
        ></div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { useFloating, offset, flip, shift, arrow, autoUpdate } from "@floating-ui/vue";

// Props for title + description
defineProps<{
  title?: string;
  description?: string;
}>();

// Tooltip visibility
const showTooltip = ref(false);

// Floating UI refs
const triggerRef = ref<HTMLElement | null>(null);
const floatingRef = ref<HTMLElement | null>(null);
const arrowRef = ref<HTMLElement | null>(null);

// Floating UI setup
const { floatingStyles, middlewareData, placement } = useFloating(triggerRef, floatingRef, {
  placement: 'top',
  middleware: [
    offset(8),
    flip(),
    shift({ padding: 8 }),
    arrow({ element: arrowRef })
  ],
  whileElementsMounted: autoUpdate
});

// Arrow positioning
const arrowStyles = computed(() => {
  const arrowData = middlewareData.value.arrow;
  if (!arrowData) return {};
  
  const { x, y } = arrowData;
  const side = placement.value.split('-')[0];
  
  const staticSide = {
    top: 'bottom',
    right: 'left',
    bottom: 'top',
    left: 'right'
  }[side] as string;
  
  return {
    left: x != null ? `${x}px` : '',
    top: y != null ? `${y}px` : '',
    [staticSide]: '-4px'
  };
});
</script>
