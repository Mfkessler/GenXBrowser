<template>
  <div
    :class="[
      'relative rounded-xl border-1 p-5 transition-all duration-200 flex flex-col items-center text-center h-full',
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
    <!-- Icon -->
    <div
      :class="[
        'w-12 h-12 rounded-full flex items-center justify-center mb-3 transition-colors',
        enabled
          ? `${colorClasses.iconBg} ${colorClasses.iconText}`
          : 'bg-gray-200 text-gray-400',
      ]"
    >
      <!-- Heatmap Icon -->
      <svg
        v-if="type === 'heatmap'"
        class="w-6 h-6"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        viewBox="0 0 24 24"
      >
        <rect x="3" y="12" width="4" height="8" rx="1" stroke="currentColor" />
        <rect x="10" y="8" width="4" height="12" rx="1" stroke="currentColor" />
        <rect x="17" y="4" width="4" height="16" rx="1" stroke="currentColor" />
      </svg>

      <!-- Compare Expression Icon -->
      <svg
        v-else-if="type === 'compare'"
        class="w-6 h-6"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        viewBox="0 0 24 24"
      >
        <line x1="4" y1="4" x2="4" y2="20" />
        <line x1="4" y1="20" x2="20" y2="20" />
        <polyline points="6,16 10,10 14,13 18,7" />
        <circle cx="6" cy="16" r="0.8" />
        <circle cx="10" cy="10" r="0.8" />
        <circle cx="14" cy="13" r="0.8" />
        <circle cx="18" cy="7" r="0.8" />
      </svg>

      <!-- Phylogenetic Tree Icon -->
      <svg
        v-else-if="type === 'phylo'"
        class="w-6 h-6"
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
        class="w-6 h-6"
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

    <!-- Title -->
    <h3
      :class="[
        'text-sm font-semibold mb-1',
        enabled ? colorClasses.title : 'text-gray-400',
      ]"
    >
      {{ title }}
    </h3>

    <!-- Description -->
    <p
      :class="[
        'text-xs leading-relaxed',
        enabled ? 'text-gray-500' : 'text-gray-300',
      ]"
    >
      {{ description }}
    </p>

    <!-- Selection badge -->
    <div
      v-if="enabled && selectedCount > 0"
      :class="[
        'mt-auto pt-3 text-xs font-medium px-2 py-0.5 rounded-full',
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
