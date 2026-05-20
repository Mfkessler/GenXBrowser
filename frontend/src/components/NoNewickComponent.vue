<template>
  <div
    class="min-h-[28rem] h-full flex flex-grow items-center justify-center bg-white px-4 py-12"
  >
    <div class="text-center max-w-3xl">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        class="h-12 w-12 mx-auto mb-4 text-gray-700"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"
        />
      </svg>
      <p class="text-lg font-semibold text-gray-700">
        {{ title || `No Newick string provided within the data base for the selected orthogroup ${og}` }}
      </p>
      <p class="text-gray-500">{{ message || "The selected species has no entry in this orthogroup." }}</p>
      <p v-if="!showFullTree && hint" class="mt-1 text-sm text-gray-400">{{ hint }}</p>
      <button
        v-if="showFullTree"
        class="mt-4 px-4 py-2 rounded-md text-sm font-medium text-white bg-[#8fbc45] hover:bg-[#7aaa30] transition-colors"
        @click="emit('show-full-tree')"
      >
        Show full tree (all species)
      </button>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{
  og: string;
  showFullTree?: boolean;
  title?: string;
  message?: string;
  hint?: string;
}>();

const emit = defineEmits<{
  (e: 'show-full-tree'): void;
}>();
</script>
