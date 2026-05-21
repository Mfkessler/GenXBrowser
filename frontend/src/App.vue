<template>
  <div class="min-h-screen flex flex-col bg-gray-50">
    <main class="flex flex-1 overflow-visible relative items-stretch">
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
        class="app-sidebar transition-all duration-300 relative z-50 flex-shrink-0 bg-gray-50"
        :style="{
          width: sidebarOpen ? '320px' : '0',
          overflow: 'hidden'
        }"
      >
          <div class="app-sidebar-inner w-[320px]">
          <SidebarComponent
            v-show="sidebarOpen"
            :disable-controls="disableControls"
            @toggle-sidebar="sidebarOpen = false"
            @navigate-home="$router.push('/catalog')"
          />
        </div>
      </div>
      <!-- Main content area -->
      <div
        ref="mainScroll"
        class="transition-all duration-300 flex-1 min-w-0 overflow-visible relative z-0"
      >
        <div class="p-4 min-h-full flex items-center flex-col overflow-visible">
          <RouterView class="mx-auto w-full" />
        </div>
      </div>
    </main>

    <FooterComponent :hidden="footerHidden" />

    <!-- Global AI assistant (always visible when enabled) -->
    <template v-if="assistantStore.enabled">
      <AssistantPanel />
      <button
        v-show="!assistantStore.open"
        class="fixed bottom-6 right-6 z-40 cursor-pointer rounded-full bg-blue-600/70 hover:bg-blue-600 text-white shadow-xl p-4 flex items-center justify-center transition-colors"
        :aria-label="`Open ${assistantStore.displayName}`"
        v-tooltip:left="`Ask ${assistantStore.displayName}`"
        @click="assistantStore.open = true"
      >
        <AiSparkleIcon class="w-6 h-6 drop-shadow" />
      </button>
    </template>
  </div>
</template>
<script setup lang="ts">
import { onMounted, provide, ref } from "vue";

import FooterComponent from "./components/FooterComponent.vue";
import SidebarComponent from "./components/SidebarComponent.vue";
import AssistantPanel from "./components/AssistantPanel.vue";
import AiSparkleIcon from "./components/icons/AiSparkleIcon.vue";
import { useAssistantStore } from "./stores/assistant";

// TODO: Optimize heatmap rendering performance for large datasets

const disableControls = ref(false);
const sidebarOpen = ref(true);
const footerHidden = ref(false);
const showSidebarHint = ref(false);
const assistantStore = useAssistantStore();

provide("sidebarOpen", sidebarOpen);

onMounted(() => {
  assistantStore.loadFeatures();
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

@media (max-width: 767px) {
  .app-sidebar {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 45;
    height: 100dvh;
    max-height: 100dvh;
    max-width: min(320px, 88vw);
    box-shadow: 8px 0 24px rgba(15, 23, 42, 0.18);
  }

  .app-sidebar-inner {
    height: 100dvh;
    overflow-y: auto;
    overscroll-behavior: contain;
    -webkit-overflow-scrolling: touch;
    width: min(320px, 88vw);
  }
}
</style>
