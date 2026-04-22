<template>
  <footer class="border-t border-gray-400 bg-gray-50 text-gray-400 py-4">
    <div class="mx-auto flex items-center justify-between gap-8">
      <!-- Left: Logo -->
      <div class="flex items-center pl-4">
        <img v-if="config.corporate_identity.logo" :src="logoUrl" alt="Logo" class="h-8 mr-2 object-contain" />
        <span class="text-lg">{{ companyName }}</span>
      </div>

      <!-- Center: Compliance Link -->
      <div>
          <a
            :aria-label="`Open link to ${ccByText}`"
            :href="ccByLink"
            target="_blank"
            rel="noopener"
            class="hover:text-gray-600 underline transition"
            v-tooltip="`Open link to ${ccByText}`"
          >
            {{ ccByText }} ({{ ccByShortform }})
          </a>
      </div>

      <!-- About Link -->
      <div>
          <RouterLink
            to="/about"
            aria-label="Navigate to About"
            class="hover:text-gray-600 underline transition"
            v-tooltip="'Navigate to About'"
          >
            About
          </RouterLink>
      </div>

      <!-- Right: Last Update -->
      <div class="text-sm pr-4">
        Last update: <span class="font-mono">{{ lastUpdate }}</span>
      </div>
    </div>
  </footer>
</template>
<script setup lang="ts">
import { inject } from "vue";

import { type Config } from "@/shared/Config";
import { getCcByMappings } from "@/shared/ccByMappings";

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

// Dynamically resolve the CC-BY
const [ccByShortform, ccByText, ccByLink] = getCcByMappings(
  String(config.corporate_identity.cc_by),
);

const startedAt = new Date();
const pad = (n: number) => n.toString().padStart(2, "0");
const lastUpdate = `${startedAt.getFullYear()}-${pad(startedAt.getMonth() + 1)}-${pad(startedAt.getDate())}`;
</script>
