<template>
  <div class="min-h-screen flex flex-col bg-gray-50">
    <main class="flex flex-1 overflow-hidden relative">
      <!-- Open Sidebar Button (appears when sidebar is closed) -->
      <button
        v-show="!sidebarOpen"
        class="fixed left-2 top-1/2 -translate-y-1/2 z-40 cursor-pointer bg-gray-200 hover:bg-gray-300 text-gray-600 hover:text-gray-800 p-2 rounded-full shadow-md transition-all duration-200"
        :class="{ 'pointer-events-none': disableControls, 'sidebar-hint-pulse': showSidebarHint }"
        @click="sidebarOpen = true"
        aria-label="Open sidebar"
        v-tooltip:right="'Open sidebar'"
      >
        <svg
          class="h-4 w-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="M9 5l7 7-7 7"
          />
        </svg>
      </button>
      <!-- Sidebar -->
      <div
        class="transition-all duration-300 relative"
        :class="sidebarOpen ? 'w-auto' : 'w-0'"
        :style="{
          minWidth: sidebarOpen ? '320px' : 0,
          maxWidth: sidebarOpen ? '540px' : 0,
          overflow: 'visible'
        }"
      >
        <div class="flex-1 h-full" style="overflow-y: auto; overflow-x: visible;">
          <SidebarComponent
            v-show="sidebarOpen"
            :disable-controls="disableControls"
            @toggle-sidebar="sidebarOpen = false"
            @navigate-home="$router.push('/')"
          />
        </div>
      </div>
      <!-- Main content area -->
      <div
        ref="mainScroll"
        class="transition-all duration-300 flex-1 overflow-auto"
      >
        <div class="p-4 min-h-full flex items-center flex-col">
          <RouterView class="mx-auto w-full" />
        </div>
      </div>
    </main>

    <FooterComponent :hidden="footerHidden" />
  </div>
</template>
<script setup lang="ts">
import { onMounted, provide, ref } from "vue";

import FooterComponent from "./components/FooterComponent.vue";
import SidebarComponent from "./components/SidebarComponent.vue";

// TODO: Optimize heatmap rendering performance for large datasets

const disableControls = ref(false);
const sidebarOpen = ref(true);
const footerHidden = ref(false);
const showSidebarHint = ref(false);

provide("sidebarOpen", sidebarOpen);

onMounted(() => {
  // Check if user has seen the sidebar hint before
  const hasSeenHint = localStorage.getItem('sidebar-hint-seen');
  if (!hasSeenHint) {
    showSidebarHint.value = true;
    // Stop the animation after 5 seconds and mark as seen
    setTimeout(() => {
      showSidebarHint.value = false;
      localStorage.setItem('sidebar-hint-seen', 'true');
    }, 5000);
  }
});
</script>

<style scoped>
@keyframes sidebar-hint {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
  }
  50% {
    box-shadow: 0 0 0 10px rgba(34, 197, 94, 0);
  }
}

.sidebar-hint-pulse {
  animation: sidebar-hint 1.5s ease-out infinite;
}
</style>
