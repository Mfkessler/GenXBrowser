<template>
  <div class="px-2">
    <div class="mb-4 mt-1 text-center">
      <h1 class="text-xl font-bold tracking-tight text-gray-800">Gen<span class="text-primary-500">X</span>Browser</h1>
    </div>
    
    <div class="prose prose-sm max-w-5xl mx-auto mt-6">
      <div v-html="htmlContent"></div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { marked } from "marked";
import { inject, ref, computed, onMounted } from "vue";

import { type Config } from "@/shared/Config";

const config = inject("config") as Config;
const markdown = ref("");

// Convert Markdown to HTML
const htmlContent = computed(() => marked.parse(markdown.value));

onMounted(async () => {
  // Use import.meta.env.BASE_URL to get the correct base path in production
  // about.md is in public folder, so it's served at the base URL directly
  const baseUrl = import.meta.env.BASE_URL || '/';
  const aboutPath = `${baseUrl}${config.corporate_identity.about}`;
  const response = await fetch(aboutPath);
  markdown.value = await response.text();
});
</script>
