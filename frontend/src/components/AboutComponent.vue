<template>
  <div class="px-2 pb-6">
    <div class="mb-4 mt-1 text-center">
      <h1 class="text-xl font-bold tracking-tight text-gray-800">Gen<span class="text-primary-500">X</span>Browser</h1>
    </div>

    <section class="mx-auto mt-6 max-w-5xl rounded-[28px] border border-slate-200 bg-white/85 shadow-[0_22px_70px_rgba(15,23,42,0.08)] backdrop-blur">
      <div class="px-5 py-6 sm:px-8 sm:py-8">
        <div class="about-copy prose prose-sm max-w-none text-slate-700 sm:prose-base prose-headings:text-slate-800 prose-a:text-primary-700 hover:prose-a:text-primary-900">
          <div v-html="htmlContent"></div>
        </div>

        <div v-if="showProjectBranding" class="mt-8">
          <div class="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
            <img
              v-if="logoUrl"
              :src="logoUrl"
              :alt="companyName || 'Project logo'"
              class="max-h-20 w-auto max-w-full object-contain mix-blend-multiply"
            />
            <p v-if="companyName" class="max-w-xl text-sm leading-6 text-slate-600">{{ companyName }}</p>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
<script setup lang="ts">
import { marked } from "marked";
import { computed, inject, onMounted, ref } from "vue";

import { type Config } from "@/shared/Config";

const config = inject("config") as Config;
const markdown = ref("");

function resolveLogoUrl(logo: string): string {
  if (!logo) {
    return "";
  }

  if (/^(?:https?:)?\/\//.test(logo) || logo.startsWith("/")) {
    return logo;
  }

  const baseUrl = import.meta.env.BASE_URL || "/";
  return `${baseUrl}${logo}`;
}

// Convert Markdown to HTML
const htmlContent = computed(() => marked.parse(markdown.value) as string);
const companyName = computed(() => config.corporate_identity.company_name?.trim() || "");
const logoUrl = computed(() => resolveLogoUrl(config.corporate_identity.logo));
const showProjectBranding = computed(() => Boolean(companyName.value || logoUrl.value));

onMounted(async () => {
  // Use import.meta.env.BASE_URL to get the correct base path in production
  // about.md is in public folder, so it's served at the base URL directly
  const baseUrl = import.meta.env.BASE_URL || "/";
  const aboutPath = `${baseUrl}${config.corporate_identity.about}`;
  const response = await fetch(aboutPath);
  markdown.value = await response.text();
});
</script>
<style scoped>
.about-copy :deep(img) {
  display: block;
  max-width: min(100%, 240px);
  margin: 2rem auto 0;
  mix-blend-mode: multiply;
}
</style>
