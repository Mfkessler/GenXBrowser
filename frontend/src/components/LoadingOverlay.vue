<template>
  <div
    class="absolute inset-0 flex justify-center items-center bg-white bg-opacity-80 z-50"
  >
    <div
      :class="containerClasses"
    >
      <img
        :src="loadingGif"
        alt="Loading..."
        :class="imageClasses"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import loadingGif from "@/assets/loading_dna.gif";

const props = withDefaults(
  defineProps<{
    size?: 'sm' | 'md' | 'lg';
  }>(),
  {
    size: 'lg'
  }
);

const containerClasses = computed(() => {
  const base = 'relative flex flex-col justify-center items-center';
  switch (props.size) {
    case 'sm':
      return `${base} w-24 h-24`;
    case 'md':
      return `${base} w-40 h-40`;
    case 'lg':
    default:
      return `${base} w-full h-full p-4`;
  }
});

const imageClasses = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'w-20 h-20 object-contain';
    case 'md':
      return 'w-32 h-32 object-contain';
    case 'lg':
    default:
      return 'max-w-full max-h-full object-contain';
  }
});
</script>
