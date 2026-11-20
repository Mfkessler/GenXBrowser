<template>
  <footer class="border-t border-slate-200/80 bg-gradient-to-b from-slate-100 via-slate-100 to-slate-200/70 text-slate-500 shadow-[0_-10px_30px_rgba(148,163,184,0.08)]">
    <div class="mx-auto grid gap-4 px-4 py-4 text-center sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:text-left">
      <div class="flex items-center gap-2 justify-center sm:justify-self-start">
        <RouterLink
          to="/about"
          aria-label="Navigate to About"
          class="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-white/80 bg-white/70 text-slate-500 shadow-sm transition hover:-translate-y-0.5 hover:text-slate-700"
          v-tooltip="'Navigate to About'"
        >
          <svg
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" stroke-width="1.8" />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M12 10v5"
            />
            <circle cx="12" cy="7.25" r=".75" fill="currentColor" stroke="none" />
          </svg>
        </RouterLink>

        <!-- Hidden screenshot trigger — visible only on hover -->
        <button
          @click="screenshotModal?.captureAndOpen()"
          class="screenshot-trigger inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-white/80 bg-white/70 text-slate-500 shadow-sm transition hover:-translate-y-0.5 hover:text-slate-700"
          aria-label="Export figure"
          v-tooltip="'Export figure  (Ctrl+Shift+P)'"
          data-html2canvas-ignore="true"
        >
          <svg
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316Z"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0ZM18.75 10.5h.008v.008h-.008V10.5Z"
            />
          </svg>
        </button>
      </div>

      <div class="flex flex-col items-center gap-2 sm:justify-self-center">
        <div class="rounded-full border border-white/80 bg-white/75 px-4 py-2 text-xs font-medium text-slate-600 shadow-sm backdrop-blur">
          Last update <span class="ml-1 font-mono text-slate-700">{{ lastUpdate }}</span>
        </div>
        <nav v-if="showLegalLinks" aria-label="Legal" class="flex flex-wrap items-center justify-center gap-x-2 text-xs text-slate-600">
          <a :href="`${legalBase}imprint.html`" class="hover:underline focus-visible:underline">Imprint &amp; Privacy</a>
          <span aria-hidden="true" class="text-slate-400">|</span>
          <a :href="`${legalBase}terms.html`" class="hover:underline focus-visible:underline">Terms of Service</a>
        </nav>
      </div>

      <div class="flex justify-center sm:justify-self-end">
        <a
          :aria-label="`Open link to ${licenseText}`"
          :href="licenseLink"
          target="_blank"
          rel="noopener"
          class="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-white/80 bg-white/70 text-slate-500 shadow-sm transition hover:-translate-y-0.5 hover:text-slate-700"
          v-tooltip="`Open link to ${licenseText}`"
        >
          <svg
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M9 12.75 11.25 15 15 9.75"
            />
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="1.8"
              d="M3.75 6.75A2.25 2.25 0 0 1 6 4.5h12a2.25 2.25 0 0 1 2.25 2.25v5.379a2.25 2.25 0 0 1-.659 1.591l-5.25 5.25a2.25 2.25 0 0 1-1.591.659H6A2.25 2.25 0 0 1 3.75 17.25V6.75Z"
            />
          </svg>
        </a>
      </div>
    </div>
  </footer>

  <!-- Screenshot / figure export modal (always mounted for Ctrl+Shift+P) -->
  <ScreenshotModal ref="screenshotModal" />
</template>
<script setup lang="ts">
import { onMounted, ref } from 'vue'

import ScreenshotModal from './ScreenshotModal.vue'

const baseUrl = import.meta.env.BASE_URL || "/";
const licenseText = "MIT License";
const licenseLink = `${baseUrl}LICENSE.txt`;

const lastUpdate = import.meta.env.VITE_BUILD_DATE || "unknown";

const legalBase = `${baseUrl}instance-legal/`;
const showLegalLinks = ref(false);

onMounted(async () => {
  try {
    const response = await fetch(`${legalBase}index.json`, { cache: "no-cache" });
    if (response.status === 404) return;
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    // Some SPA hosts return index.html for missing files.
    if (!response.headers.get("content-type")?.includes("application/json")) return;
    const manifest: unknown = await response.json();
    if (typeof manifest !== "object" || manifest === null || !("enabled" in manifest) || typeof manifest.enabled !== "boolean") {
      throw new Error("Expected an instance legal manifest with a boolean enabled field");
    }
    showLegalLinks.value = manifest.enabled;
  } catch (error) {
    console.warn("Could not load instance legal links", error);
  }
});

const screenshotModal = ref<InstanceType<typeof ScreenshotModal> | null>(null)
</script>

<style scoped>
.screenshot-trigger {
  opacity: 0;
  transition: opacity 0.2s ease-in-out, transform 0.2s ease;
}

.screenshot-trigger:hover {
  opacity: 1;
}
</style>
