<template>
  <div
    data-card-role="analysis"
    :class="[
      'relative rounded-xl border-1 p-5 transition-all duration-200 flex flex-col h-full min-w-0 overflow-hidden [container-type:inline-size]',
      enabled
        ? `${colorClasses.border} ${colorClasses.bg} cursor-pointer hover:shadow-lg hover:scale-[1.02] active:scale-[0.98]`
        : 'border-gray-200 bg-gray-50 cursor-not-allowed',
    ]"
    :role="'button'"
    :aria-disabled="!enabled"
    :tabindex="enabled ? 0 : -1"
    @click="handleClick"
    @keydown.enter.prevent="handleClick"
    @keydown.space.prevent="handleClick"
    v-tooltip="tooltipText"
  >
    <div class="analysis-card-header w-full">
      <!-- Icon -->
      <div
        :class="[
          'analysis-card-icon-shell rounded-full flex items-center justify-center transition-colors',
          enabled
            ? `${colorClasses.iconBg} ${colorClasses.iconText}`
            : 'bg-gray-200 text-gray-400',
        ]"
      >
        <!-- Heatmap Icon -->
        <svg
          v-if="type === 'heatmap'"
          class="analysis-card-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <rect x="3" y="3" width="5" height="5" opacity="0.3" fill="currentColor"/>
          <rect x="10" y="3" width="5" height="5" opacity="0.8" fill="currentColor"/>
          <rect x="17" y="3" width="5" height="5" opacity="0.1" fill="currentColor"/>
          <rect x="3" y="10" width="5" height="5" opacity="0.6" fill="currentColor"/>
          <rect x="10" y="10" width="5" height="5" opacity="0.4" fill="currentColor"/>
          <rect x="17" y="10" width="5" height="5" opacity="0.9" fill="currentColor"/>
          <rect x="3" y="17" width="5" height="5" opacity="0.1" fill="currentColor"/>
          <rect x="10" y="17" width="5" height="5" opacity="0.7" fill="currentColor"/>
          <rect x="17" y="17" width="5" height="5" opacity="0.5" fill="currentColor"/>
        </svg>

        <!-- Compare Expression Icon -->
        <svg
          v-else-if="type === 'compare'"
          class="analysis-card-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M3 17c4-1 6-12 10-12s6 8 8 10" opacity="0.4" />
          <path d="M3 12c3 0 7 10 11 10s5-15 7-15" />
        </svg>

        <!-- Phylogenetic Tree Icon -->
        <svg
          v-else-if="type === 'phylo'"
          class="analysis-card-icon"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          viewBox="0 0 24 24"
        >
          <line x1="6" y1="4" x2="6" y2="20" />
          <line x1="6" y1="9" x2="12" y2="9" />
          <line x1="12" y1="6" x2="12" y2="12" />
          <line x1="12" y1="6" x2="20" y2="6" />
          <line x1="12" y1="12" x2="20" y2="12" />
          <line x1="6" y1="16" x2="14" y2="16" />
          <line x1="14" y1="14" x2="14" y2="18" />
          <line x1="14" y1="18" x2="20" y2="18" />
          <circle cx="20" cy="6" r="1" />
          <circle cx="20" cy="12" r="1" />
          <circle cx="20" cy="18" r="1" />
        </svg>

        <!-- ORA Icon -->
        <svg
          v-else-if="type === 'ora'"
          class="analysis-card-icon"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          viewBox="0 0 24 24"
        >
          <circle cx="6" cy="20" r="1" />
          <circle cx="12" cy="14" r="2" />
          <circle cx="18" cy="4" r="1.5" />
        </svg>
      </div>

      <div class="analysis-card-copy">
        <h3
          :class="[
            'analysis-card-title text-lg font-semibold mb-1 max-w-full',
            enabled ? colorClasses.title : 'text-gray-400',
          ]"
        >
          {{ title }}
        </h3>

        <p
          :class="[
            'analysis-card-description text-sm leading-relaxed max-w-full',
            enabled ? 'text-gray-500' : 'text-gray-300',
          ]"
        >
          {{ description }}
        </p>
      </div>
    </div>

    <!-- Selection badge -->
    <div
      v-if="enabled && selectedCount > 0"
      :class="[
        'mt-auto self-center inline-flex items-center text-xs font-medium px-2 py-0.5 rounded-full',
        colorClasses.badge,
      ]"
    >
      {{ selectedCount }} {{ selectedCount === 1 ? 'dataset' : 'datasets' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import { useVisualizationStore } from "@/stores/visualization";

const props = defineProps<{
  type: "heatmap" | "compare" | "ora" | "phylo";
  enabled: boolean;
  disabledReason: string | null;
  selectedCount: number;
  selectedTableNames: string[];
}>();

const router = useRouter();
const visualizationStore = useVisualizationStore();

const ANALYSIS_META: Record<
  string,
  {
    title: string;
    description: string;
    routePrefix: string;
    border: string;
    bg: string;
    iconBg: string;
    iconText: string;
    title_color: string;
    badge: string;
  }
> = {
  heatmap: {
    title: "Heatmap",
    description:
      "Visualize gene expression levels as a color-coded heatmap with clustering, side colors, and multiple expression transforms.",
    routePrefix: "/h/",
    border: "border-purple-400",
    bg: "bg-purple-50",
    iconBg: "bg-purple-100",
    iconText: "text-purple-600",
    title_color: "text-purple-700",
    badge: "bg-purple-100 text-purple-700",
  },
  compare: {
    title: "Compare Expression",
    description:
      "Compare expression values across species for individual orthogroups using line, box, or violin plots.",
    routePrefix: "/c/",
    border: "border-blue-400",
    bg: "bg-blue-50",
    iconBg: "bg-blue-100",
    iconText: "text-blue-600",
    title_color: "text-blue-700",
    badge: "bg-blue-100 text-blue-700",
  },
  phylo: {
    title: "Phylogenetic Tree",
    description:
      "Display a phylogenetic tree with expression heatmap overlay for orthogroups across species.",
    routePrefix: "/p/",
    border: "border-orange-300",
    bg: "bg-orange-50",
    iconBg: "bg-orange-100",
    iconText: "text-orange-500",
    title_color: "text-orange-600",
    badge: "bg-orange-100 text-orange-700",
  },
  ora: {
    title: "ORA Analysis",
    description:
      "Over-Representation Analysis identifies enriched GO terms among filtered transcripts using a dot plot.",
    routePrefix: "/o/",
    border: "border-red-400",
    bg: "bg-red-50",
    iconBg: "bg-red-100",
    iconText: "text-red-600",
    title_color: "text-red-700",
    badge: "bg-red-100 text-red-700",
  },
};

const meta = computed(() => ANALYSIS_META[props.type]);

const title = computed(() => meta.value.title);
const description = computed(() => meta.value.description);

const colorClasses = computed(() => ({
  border: meta.value.border,
  bg: meta.value.bg,
  iconBg: meta.value.iconBg,
  iconText: meta.value.iconText,
  title: meta.value.title_color,
  badge: meta.value.badge,
}));

const tooltipText = computed(() => {
  if (!props.enabled && props.disabledReason) {
    return props.disabledReason;
  }
  return null;
});

function handleClick() {
  if (!props.enabled) return;

  // Pre-set species in visualization store for Compare
  if (props.type === "compare") {
    visualizationStore.setCompareState({
      selectedSpecies: props.selectedTableNames,
    });
  }

  const route = meta.value.routePrefix + props.selectedTableNames.join(",");
  router.push(route);
}
</script>

<style scoped>
.analysis-card-header {
  display: grid;
  grid-template-columns: minmax(4.75rem, clamp(4.75rem, 28cqi, 7.5rem)) minmax(0, 1fr);
  align-items: center;
  gap: 0.875rem;
  min-width: 0;
}

.analysis-card-icon-shell {
  width: min(100%, clamp(4.75rem, 28cqi, 7.5rem));
  aspect-ratio: 1 / 1;
  justify-self: center;
}

.analysis-card-icon {
  width: clamp(2.5rem, 14cqi, 4.5rem);
  height: clamp(2.5rem, 14cqi, 4.5rem);
}

.analysis-card-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.analysis-card-description {
  display: -webkit-box;
  overflow: hidden;
  text-overflow: ellipsis;
  line-clamp: 4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}

@container (max-width: 22rem) {
  .analysis-card-header {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .analysis-card-icon-shell {
    width: clamp(4.5rem, 34cqi, 6.25rem);
  }
}
</style>
