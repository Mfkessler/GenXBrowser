<template>
  <footer class="bg-gray-50 text-gray-400 py-4">
    <div class="mx-auto flex flex-wrap items-center justify-center sm:justify-between gap-x-8 gap-y-3 px-4 text-center sm:text-left">
      <!-- Left: Logo -->
      <div class="flex items-center min-w-0">
        <img v-if="config.corporate_identity.logo" :src="logoUrl" alt="Logo" class="h-8 mr-2 object-contain" />
        <span class="text-lg">{{ companyName }}</span>
      </div>

      <!-- Center: Compliance Link -->
      <div>
          <a
            :aria-label="`Open link to ${licenseText}`"
            :href="licenseLink"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center justify-center text-gray-400 hover:text-gray-600 transition"
            v-tooltip="`Open link to ${licenseText}`"
          >
            <svg
              class="h-8 w-8"
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

      <!-- About Link -->
      <div>
          <RouterLink
            to="/about"
            aria-label="Navigate to About"
            class="inline-flex items-center justify-center text-gray-400 hover:text-gray-600 transition"
            v-tooltip="'Navigate to About'"
          >
            <svg
              class="h-8 w-8"
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

      <!-- Right: Last Update -->
      <div class="text-sm">
        Last update: <span class="font-mono">{{ lastUpdate }}</span>
      </div>
    </div>
  </footer>
</template>
<script setup lang="ts">
import { inject } from "vue";

import { type Config } from "@/shared/Config";

const config = inject("config") as Config;

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

const logoUrl = resolveLogoUrl(config.corporate_identity.logo);
const companyName = config.corporate_identity.company_name;
const baseUrl = import.meta.env.BASE_URL || "/";
const licenseText = "MIT License";
const licenseLink = `${baseUrl}LICENSE.txt`;

const startedAt = new Date();
const pad = (n: number) => n.toString().padStart(2, "0");
const lastUpdate = `${startedAt.getFullYear()}-${pad(startedAt.getMonth() + 1)}-${pad(startedAt.getDate())}`;
</script>
