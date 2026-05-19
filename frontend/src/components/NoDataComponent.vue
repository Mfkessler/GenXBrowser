<template>
  <div
    class="flex h-full min-h-[18rem] w-full flex-grow items-center justify-center rounded-md border border-gray-300 bg-white p-4"
  >
    <div class="text-center max-w-full">
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
      <p class="text-base sm:text-lg font-semibold text-gray-700 leading-snug break-words">
        {{
          rowCount === 0
            ? "No Data Found"
            : `Too many data points (${rowCount} > 1000)`
        }}
      </p>
      <p class="text-sm text-gray-700 leading-snug">Please try different search criteria</p>
    </div>
  </div>
</template>
<script setup lang="ts">
defineProps<{
  rowCount: number;
}>();
</script>
