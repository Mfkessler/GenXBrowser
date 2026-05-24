<template>
  <footer class="border-t border-slate-200/80 bg-gradient-to-b from-slate-100 via-slate-100 to-slate-200/70 text-slate-500 shadow-[0_-10px_30px_rgba(148,163,184,0.08)]">
    <div class="mx-auto grid gap-4 px-4 py-4 text-center sm:grid-cols-[1fr_auto_1fr] sm:items-center sm:text-left">
      <div class="flex justify-center sm:justify-self-start">
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
      </div>

      <div class="flex justify-center sm:justify-self-center">
        <div class="rounded-full border border-white/80 bg-white/75 px-4 py-2 text-xs font-medium text-slate-600 shadow-sm backdrop-blur">
          Last update <span class="ml-1 font-mono text-slate-700">{{ lastUpdate }}</span>
        </div>
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
</template>
<script setup lang="ts">
const baseUrl = import.meta.env.BASE_URL || "/";
const licenseText = "MIT License";
const licenseLink = `${baseUrl}LICENSE.txt`;

const startedAt = new Date();
const pad = (n: number) => n.toString().padStart(2, "0");
const lastUpdate = `${startedAt.getFullYear()}-${pad(startedAt.getMonth() + 1)}-${pad(startedAt.getDate())}`;
</script>
