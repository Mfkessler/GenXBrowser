<script setup lang="ts">
import { ref, computed } from "vue";
import InfoTooltip from "./InfoTooltip.vue";

export interface OraTooltipModalProps {
  show: boolean;
  data: {
    attr: string;
    subset_count: number;
    background_count: number;
    gene_ratio: number;
    p_value: number;
    q_value: number;
    combined_score: number;
    odds_ratio?: number;
    expected_count: number;
    fold_enrichment: number;
    go_name?: string;
    go_namespace?: string;
    go_depth?: number;
  } | null;
  isGoTerm: boolean;
  visibleFields: string[];
}

const props = defineProps<OraTooltipModalProps>();
const emit = defineEmits<{
  close: [];
  filterByTerm: [term: string];
}>();

const copiedField = ref<string | null>(null);

// Metric definitions with descriptions for InfoTooltip
const metricDefinitions = {
  attr: { 
    label: "Attribute ID", 
    description: "The identifier for this enriched term (e.g., GO term ID, orthogroup ID)"
  },
  go_name: { 
    label: "GO Term Name", 
    description: "Human-readable name of the Gene Ontology term"
  },
  go_namespace: { 
    label: "GO Category", 
    description: "Biological Process (BP), Molecular Function (MF), or Cellular Component (CC)"
  },
  go_depth: { 
    label: "GO Depth", 
    description: "Position in GO hierarchy. Higher depth = more specific term"
  },
  subset_count: { 
    label: "Observed Count", 
    description: "Number of genes in your filtered set that have this attribute. This is what you actually observe in your data."
  },
  expected_count: { 
    label: "Expected Count", 
    description: "Expected number of genes with this attribute under the null hypothesis (random distribution). Formula: (background_count / background_size) × subset_size"
  },
  background_count: { 
    label: "Background Count", 
    description: "Total number of genes in the species (background) that have this attribute"
  },
  fold_enrichment: { 
    label: "Fold Enrichment", 
    description: "How many times more enriched this term is compared to random expectation. Formula: (observed_count / subset_size) / (background_count / background_size). Values >1 indicate enrichment, <1 indicate depletion."
  },
  gene_ratio: { 
    label: "Gene Ratio", 
    description: "Proportion of all genes with this attribute that are in your subset. Formula: subset_count / background_count. High values mean the term is highly specific to your gene set."
  },
  p_value: { 
    label: "P-Value", 
    description: "Statistical significance from Fisher's Exact Test (one-tailed, testing for enrichment). Lower values indicate stronger evidence against random chance."
  },
  q_value: { 
    label: "Q-Value (FDR)", 
    description: "False Discovery Rate-adjusted p-value using Benjamini-Hochberg correction. Controls the expected proportion of false positives. Threshold typically: 0.01 or 0.05"
  },
  combined_score: { 
    label: "Combined Score", 
    description: "Composite ranking metric balancing significance and effect size. Formula: -log₁₀(q_value) × gene_ratio. Higher scores indicate both statistically significant AND biologically relevant terms."
  },
  odds_ratio: { 
    label: "Odds Ratio", 
    description: "Odds ratio from Fisher's Exact Test. Measures the strength of association between your gene set and this attribute. Values >1 indicate positive association."
  }
};

const closeOverlay = () => {
  emit("close");
};

const filterByThisTerm = () => {
  if (props.data) {
    emit("filterByTerm", props.data.attr);
    closeOverlay();
  }
};

const copyToClipboard = async (text: string, fieldName: string) => {
  try {
    await navigator.clipboard.writeText(String(text));
    copiedField.value = fieldName;
    setTimeout(() => {
      copiedField.value = null;
    }, 2000);
  } catch (err) {
    console.error("Failed to copy:", err);
  }
};

const formatValue = (key: string, value: unknown): string => {
  if (value === null || value === undefined) return "—";
  
  // Format based on metric type
  switch (key) {
    case 'expected_count':
    case 'fold_enrichment':
    case 'gene_ratio':
      return typeof value === 'number' ? value.toFixed(3) : String(value);
    case 'p_value':
    case 'q_value':
      return typeof value === 'number' ? value.toExponential(2) : String(value);
    case 'combined_score':
      return typeof value === 'number' ? value.toFixed(2) : String(value);
    case 'subset_count':
    case 'background_count':
    case 'go_depth':
      return String(value);
    case 'go_namespace':
      // Format namespace
      if (value === 'biological_process') return 'Biological Process';
      if (value === 'molecular_function') return 'Molecular Function';
      if (value === 'cellular_component') return 'Cellular Component';
      return String(value);
    default:
      return String(value);
  }
};

const formatGoDepth = (depth: number): string => {
  if (depth < 0) return 'N/A';
  return `Level ${depth}`;
};

// Core metrics (always shown)
const coreMetrics = computed(() => {
  const metrics: Array<{key: string, value: unknown}> = [];
  if (!props.data) return metrics;
  
  // Always show these
  metrics.push({ key: 'subset_count', value: props.data.subset_count });
  metrics.push({ key: 'expected_count', value: props.data.expected_count });
  metrics.push({ key: 'background_count', value: props.data.background_count });
  metrics.push({ key: 'fold_enrichment', value: props.data.fold_enrichment });
  
  return metrics;
});

// Additional metrics (configurable via visibleFields)
const additionalMetrics = computed(() => {
  const metrics: Array<{key: string, value: unknown}> = [];
  if (!props.data) return metrics;
  
  const availableMetrics = ['gene_ratio', 'p_value', 'q_value', 'combined_score', 'odds_ratio'];
  
  for (const key of availableMetrics) {
    if (props.visibleFields.includes(key) && props.data[key as keyof typeof props.data] !== undefined) {
      metrics.push({ key, value: props.data[key as keyof typeof props.data] });
    }
  }
  
  return metrics;
});

</script>

<template>
  <Teleport to="body">
    <div
      v-if="show && data"
      class="fixed inset-0 flex justify-center items-center z-[60]"
      style="background-color: rgba(0, 0, 0, 0.5)"
      @click.self="closeOverlay"
    >
      <div
        class="bg-white p-6 rounded-lg shadow-lg w-[50%] max-h-[90vh] flex flex-col"
      >
      <!-- Header -->
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-xl font-bold cursor-default">ORA Term Details</h1>
        <button
          @click="closeOverlay"
          class="text-gray-700 rounded-full p-2 hover:bg-gray-100"
          aria-label="Close overlay"
        >
          <svg
            class="w-6 h-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
              d="M6 18L18 6M6 6l12 12"
            ></path>
          </svg>
        </button>
      </div>

      <!-- Scrollable Content -->
      <div class="flex-grow overflow-y-auto space-y-6 pr-2">
        <!-- Attribute Information -->
        <div class="bg-gray-50 p-4 rounded-md border border-gray-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">
            Attribute Information
          </h2>
          <div class="space-y-2">
            <!-- Attribute ID -->
            <div class="flex flex-col">
              <div class="flex justify-between items-center mb-1">
                <div class="flex items-center">
                  <span class="font-medium text-gray-600 text-sm">{{
                    metricDefinitions.attr.label
                  }}</span>
                  <InfoTooltip 
                    :description="metricDefinitions.attr.description"
                  />
                </div>
                <button
                  @click="copyToClipboard(data.attr, 'attr')"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === 'attr' ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm break-all font-mono">
                {{ data.attr }}
              </div>
            </div>

            <!-- GO Term Specific Fields -->
            <template v-if="isGoTerm && data.go_name">
              <!-- GO Name -->
              <div class="flex flex-col">
                <div class="flex justify-between items-center mb-1">
                  <div class="flex items-center">
                    <span class="font-medium text-gray-600 text-sm">{{
                      metricDefinitions.go_name.label
                    }}</span>
                    <InfoTooltip 
                      :description="metricDefinitions.go_name.description"
                    />
                  </div>
                  <button
                    @click="copyToClipboard(data.go_name, 'go_name')"
                    class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                  >
                    {{ copiedField === 'go_name' ? "✓ Copied!" : "📋 Copy" }}
                  </button>
                </div>
                <div class="bg-white p-2 rounded border border-gray-300 text-sm break-all">
                  {{ data.go_name }}
                </div>
              </div>

              <!-- GO Namespace -->
              <div v-if="data.go_namespace" class="flex flex-col">
                <div class="flex items-center mb-1">
                  <span class="font-medium text-gray-600 text-sm">{{
                    metricDefinitions.go_namespace.label
                  }}</span>
                  <InfoTooltip 
                    :description="metricDefinitions.go_namespace.description"
                  />
                </div>
                <div class="bg-white p-2 rounded border border-gray-300 text-sm">
                  {{ formatValue('go_namespace', data.go_namespace) }}
                </div>
              </div>

              <!-- GO Depth -->
              <div v-if="data.go_depth !== undefined" class="flex flex-col">
                <div class="flex items-center mb-1">
                  <span class="font-medium text-gray-600 text-sm">{{
                    metricDefinitions.go_depth.label
                  }}</span>
                  <InfoTooltip 
                    :description="metricDefinitions.go_depth.description"
                  />
                </div>
                <div class="bg-white p-2 rounded border border-gray-300 text-sm">
                  {{ formatGoDepth(data.go_depth) }}
                </div>
              </div>
            </template>
          </div>
        </div>

        <!-- Core Enrichment Metrics -->
        <div class="bg-blue-50 p-4 rounded-md border border-blue-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">
            Enrichment Metrics
          </h2>
          <div class="space-y-2">
            <div 
              v-for="metric in coreMetrics" 
              :key="metric.key"
              class="flex flex-col"
            >
              <div class="flex justify-between items-center mb-1">
                <div class="flex items-center">
                  <span class="font-medium text-gray-600 text-sm">{{
                    metricDefinitions[metric.key as keyof typeof metricDefinitions].label
                  }}</span>
                  <InfoTooltip 
                    :description="metricDefinitions[metric.key as keyof typeof metricDefinitions].description"
                  />
                </div>
                <button
                  @click="copyToClipboard(formatValue(metric.key, metric.value), metric.key)"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === metric.key ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm font-mono">
                {{ formatValue(metric.key, metric.value) }}
                <span v-if="metric.key === 'fold_enrichment'" class="ml-1">×</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Statistical Metrics -->
        <div v-if="additionalMetrics.length > 0" class="bg-gray-50 p-4 rounded-md border border-gray-200">
          <h2 class="text-lg font-semibold mb-3 text-gray-800">
            Statistical Details
          </h2>
          <div class="space-y-2">
            <div 
              v-for="metric in additionalMetrics" 
              :key="metric.key"
              class="flex flex-col"
            >
              <div class="flex justify-between items-center mb-1">
                <div class="flex items-center">
                  <span class="font-medium text-gray-600 text-sm">{{
                    metricDefinitions[metric.key as keyof typeof metricDefinitions].label
                  }}</span>
                  <InfoTooltip 
                    :description="metricDefinitions[metric.key as keyof typeof metricDefinitions].description"
                  />
                </div>
                <button
                  @click="copyToClipboard(formatValue(metric.key, metric.value), metric.key)"
                  class="px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                >
                  {{ copiedField === metric.key ? "✓ Copied!" : "📋 Copy" }}
                </button>
              </div>
              <div class="bg-white p-2 rounded border border-gray-300 text-sm font-mono">
                {{ formatValue(metric.key, metric.value) }}
              </div>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="mt-4">
          <button
            @click="filterByThisTerm"
            class="w-full px-4 py-2 bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors font-semibold"
            style="background-color: #2563eb; color: white;"
          >
            Filter Data by This Term
          </button>
        </div>
      </div>

        <!-- Footer -->
        <div class="mt-4 flex justify-end">
          <button
            @click="closeOverlay"
            class="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* Custom scrollbar for better aesthetics */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* Prevent horizontal scrollbar on all content boxes */
.break-all {
  word-break: break-all;
  overflow-wrap: break-word;
  overflow-x: hidden;
}
</style>
