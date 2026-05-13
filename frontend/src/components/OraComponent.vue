<template>
  <main>
    <!-- Top control bar -->
    <div class="flex justify-between px-2 items-center mb-2">
      <div class="text-gray-500 font-medium flex items-center space-x-2">
        <DropdownMenu
          :modelValue="localTableName"
          :options="tableNameOptions"
          @update:modelValue="(val) => onTableChange(val)"
        />
        <span class="pl-2 text-xs whitespace-nowrap"
          >({{ getEntityCountLabel() }}: {{ rowCount }})</span
        >
      </div>
      <div class="flex space-x-2">
        <button
          aria-label="Add another dot plot"
          @click="addDotplot"
          :disabled="
            props.existingTables.length === Object.keys(props.allTables).length
          "
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white disabled:opacity-50"
          v-tooltip="'Add another dot plot'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <path
              d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4"
            />
          </svg>
        </button>

        <button
          aria-label="Remove dot plot"
          @click="removeDotplot"
          :disabled="props.existingTables.length === 1"
          class="p-2 rounded-md text-accent1-500 border border-accent1-500 hover:bg-accent1-500 hover:text-white disabled:opacity-50"
          v-tooltip="'Remove dot plot'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <path
              d="M4 8a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7A.5.5 0 0 1 4 8"
            />
          </svg>
        </button>

        <button
          aria-label="Share the visualization"
          @click="showShareOverlay = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Share the visualization'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            fill="currentColor"
            viewBox="0 0 16 16"
          >
            <path
              d="M13.5 1a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3M11 2.5a2.5 2.5 0 1 1 .603 1.628l-6.718 3.12a2.5 2.5 0 0 1 0 1.504l6.718 3.12a2.5 2.5 0 1 1-.488.876l-6.718-3.12a2.5 2.5 0 1 1 0-3.256l6.718-3.12A2.5 2.5 0 0 1 11 2.5m-8.5 4a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3m11 5.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3"
            />
          </svg>
        </button>

        <button
          aria-label="Open settings"
          @click="openSettingsOverlay"
          class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900"
          v-tooltip="'Open settings'"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- Main dot plot container -->
    <div
      v-if="loading || !renderReady || (rowCount <= 5000 && rowCount > 0)"
      ref="plotShell"
      data-testid="ora-plot-shell"
      class="relative flex flex-col overflow-hidden"
      :style="plotShellStyle"
    >
      <LoadingOverlay v-if="loading || !renderReady" />

      <div
        class="h-full flex flex-col"
        :class="{ 'invisible pointer-events-none': loading || !renderReady || rowCount <= 0 || rowCount > 5000 }"
      >
        <!-- ORA Info Banner (collapsible, default collapsed) -->
        <div v-if="oraMetadata" class="mb-3 p-3 bg-blue-50 border border-blue-200 rounded-md text-sm flex-shrink-0">
        <div
          class="flex items-center justify-between cursor-pointer select-none"
          @click="oraInfoOpen = !oraInfoOpen"
        >
          <div class="font-semibold text-blue-900">
            Over-Representation Analysis (ORA)
          </div>
          <svg
            class="w-5 h-5 text-blue-700 transition-transform duration-300"
            :class="{ 'rotate-180': oraInfoOpen }"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fill-rule="evenodd"
              d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
              clip-rule="evenodd"
            />
          </svg>
        </div>
        <transition name="collapse">
          <div v-show="oraInfoOpen" class="text-blue-800 space-y-1 mt-1">
            <div>
              <strong>{{ getEntitySetLabel() }}:</strong>
              {{ oraMetadata.subset_size }} annotated {{ getEntityLabelPluralLower() }}
              <span v-if="oraMetadata.raw_subset_size !== undefined">
                of {{ oraMetadata.raw_subset_size }} filtered
              </span>
              vs {{ oraMetadata.background_size }} annotated {{ getEntityLabelPluralLower() }}
              <span v-if="oraMetadata.raw_background_size !== undefined">
                of {{ oraMetadata.raw_background_size }} in the {{ localTableName }} species background
              </span>
            </div>
            <div v-if="oraMetadata.unannotated_subset_count > 0 || oraMetadata.unannotated_background_count > 0" class="text-xs text-blue-700">
              Unannotated genes are excluded from the ORA universe for the selected metadata column.
            </div>
            <div>
              <strong>Enrichment Tests:</strong> {{ oraMetadata.total_tests }} total,
              <span class="font-semibold">{{ oraMetadata.significant_count }} significant</span>
              (FDR q-value &lt; {{ visualizationStore.significance }})
            </div>
            <div>
              <strong>Results Shown:</strong> Top {{ visualizationStore.oraTopN }} by combined score
              (minimum {{ visualizationStore.oraMinCount }} {{ getEntityLabelPluralLower() }} per term)
            </div>
            <!-- Topological filter info (GO terms only) -->
            <div v-if="oraMetadata.topological_filter_applied && oraMetadata.filtered_parent_count > 0" class="text-green-700 bg-green-50 rounded px-2 py-1 mt-1">
              <strong>🔬 Topological Filtering:</strong> 
              {{ oraMetadata.filtered_parent_count }} redundant parent GO terms removed
              <span v-if="oraMetadata.filtered_parents_sample?.length" class="block text-xs text-green-600 mt-0.5">
                Examples: {{ oraMetadata.filtered_parents_sample.slice(0, 5).join(', ') }}{{ oraMetadata.filtered_parents_sample.length > 5 ? '...' : '' }}
              </span>
            </div>
            <div class="text-xs text-blue-600 mt-2">
              💡 <strong>Combined Score</strong> = -log₁₀(q-value) × gene_ratio
              | Accounts for both statistical significance and effect size
            </div>
          </div>
        </transition>
        </div>

        <div
          ref="visualizationRoot"
          class="flex-1 min-h-0 bg-white border border-gray-300 rounded-md flex flex-row overflow-hidden"
        >
          <div class="flex-grow relative w-full overflow-hidden">
            <div ref="dotplotContainer" class="w-full h-full"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="rowCount > 5000">
      <div class="p-6 text-center text-gray-600 border border-gray-300 rounded-md">
        <p class="text-lg font-semibold">Too many {{ getEntityLabelPluralLower() }} for ORA visualization</p>
        <p class="mt-2">
          Your filter returned {{ rowCount }} {{ getEntityLabelPluralLower() }}. 
          Please refine your filters to reduce the {{ getEntityLabelPluralLower() }} set to ≤5000 {{ getEntityLabelPluralLower() }}.
        </p>
      </div>
    </div>

    <div v-else>
      <NoDataComponent :rowCount="rowCount" />
    </div>

    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(visualizationRoot)"
      @close="showShareOverlay = false"
    />
    
    <OraTooltipModal
      :show="showOraTooltipModal"
      :data="selectedTerm"
      :isGoTerm="isGoTermEnrichment"
      :visibleFields="visualizationStore.oraTooltipFields"
      @close="showOraTooltipModal = false"
      @filterByTerm="handleFilterByTerm"
    />
  </main>
</template>
<script setup lang="ts">
import axios from "axios";
import * as d3 from "d3";
import { storeToRefs } from "pinia";
import {
  computed,
  inject,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  type Ref,
  watch,
} from "vue";

import { API_BASE_URL, type Config } from "@/shared/Config";
import { COLORSCALES, getCategoricalColors } from "@/shared/Colorscales";
import DropdownMenu from "./DropdownMenu.vue";
import { useFiltersStore } from "@/stores/filters";
import LoadingOverlay from "./LoadingOverlay.vue";
import type { MetaFormat } from "@/shared/MetaFormat";
import NoDataComponent from "./NoDataComponent.vue";
import type { RowType } from "@/shared/RowType";
import ShareOverlay from "./ShareOverlay.vue";
import OraTooltipModal from "./OraTooltipModal.vue";
import { beautifyLabel, compareValues, exact_nc } from "@/shared/utils";
import { useVisualizationStore } from "@/stores/visualization";
import { useColumnsStore } from "@/stores/columns";
import { useAssistantStore } from "@/stores/assistant";
import { getEntityCountLabel, getEntitySetLabel, getEntityLabelPluralLower, getEntityLabelPlural } from "@/shared/dataTypeLabels";
import { createVisibleColorMapping, type ColorMapping, type SharedColorRegistry } from "@/shared/colorMapping";

// TODO: Numeric column values have not been tested as ORA input

const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const columnsStore = useColumnsStore();
const assistantStore = useAssistantStore();
const { filters } = storeToRefs(filtersStore);

// Per-dataset merged filters (includes per-dataset ID filter)
const mergedFilters = computed(() => filtersStore.getMergedFilters(props.tableName));

const sidebarOpen = inject("sidebarOpen") as Ref<boolean> | undefined; //Provided by App.vue
const sharedColorRegistry = inject<SharedColorRegistry>('sharedColorRegistry', undefined) as SharedColorRegistry | undefined;

const props = defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
  hashLoading?: boolean;
}>();

const localTableName = ref(props.tableName);
const tableNameOptions = computed(() => {
  return Object.fromEntries(
    Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) || key === props.tableName,
    ),
  );
});

const loading = ref(true);
const renderReady = ref(false);
const showShareOverlay = ref(false);
const showOraTooltipModal = ref(false);
const selectedTerm = ref<PValueEntry | null>(null);
const oraInfoOpen = ref(false);

const error = ref("");
const rowCount = ref(0);
const columnMeta = ref<MetaFormat>();
const subset = ref<string[]>([]);
const subsetFrequency = ref<Record<string, number>>({});
const subsetSize = ref<number>(0);
const data = ref<string[]>([]);
const dataFrequency = ref<Record<string, number>>({});
const dataSize = ref<number>(0);
const pValueEntries = ref<PValueEntry[]>([]);
const oraMetadata = ref<any>(null);

const dotplotContainer = ref<HTMLDivElement | null>(null);
const colorLegendContainer = ref<HTMLDivElement | null>(null);
const sizeLegendContainer = ref<HTMLDivElement | null>(null);
const plotShell = ref<HTMLDivElement | null>(null);

const visualizationRoot = ref<HTMLDivElement | null>(null);
let oraRequestSeq = 0;
const availablePlotHeight = ref(600);
const maxBubbleRadius = 15;
const minimumBubbleGap = 4;
const minimumOraRowHeight = maxBubbleRadius * 2 + minimumBubbleGap;
const plotVerticalChrome = 126;
const collapsedOraInfoHeight = 58;

function updateAvailablePlotHeight() {
  if (typeof window === "undefined") return;
  const shellTop = plotShell.value?.getBoundingClientRect().top ?? 160;
  const usableHeight = window.innerHeight - shellTop - 12;
  availablePlotHeight.value = Math.max(360, Math.floor(usableHeight));
}

const finalPlotHeight = computed(() => {
  const visibleRows = Math.max(pValueEntries.value.length, 1);
  const minimumHeight = visualizationStore.legend ? 360 : 300;
  const bubbleSafeHeight = visibleRows * minimumOraRowHeight + plotVerticalChrome + collapsedOraInfoHeight;
  return Math.max(minimumHeight, availablePlotHeight.value, bubbleSafeHeight);
});
const hasPreparedPlotData = computed(() => pValueEntries.value.length > 0 || oraMetadata.value !== null);
const activePlotHeight = computed(() => loading.value && !hasPreparedPlotData.value ? availablePlotHeight.value : finalPlotHeight.value);
const plotShellStyle = computed(() => ({
  height: `${activePlotHeight.value}px`,
  minHeight: `${activePlotHeight.value}px`,
}));

function log2FoldEnrichment(value: number): number {
  return Math.log2(Math.max(value, Number.EPSILON));
}

async function syncPlotHeightWithViewport() {
  updateAvailablePlotHeight();
  await nextTick();
}

// PValueEntry interface updated to match backend response
interface PValueEntry {
  attr: string;  // Frontend uses 'attr'
  attribute: string;  // Backend provides 'attribute'
  subset_count: number;
  background_count: number;
  gene_ratio: number;
  p_value: number;
  q_value: number;
  combined_score: number;
  odds_ratio?: number;
  expected_count: number;
  fold_enrichment: number;
  // GO term info (only for GO term enrichment)
  go_name?: string;
  go_namespace?: string;
  go_depth?: number;
}

// GO term info cache (includes name, namespace, and depth)
const goTermInfoCache = ref<Record<string, { name: string; namespace: string; depth: number }>>({});

// Check if we're enriching GO terms (check various possible column names)
const isGoTermEnrichment = computed(() => {
  const colName = visualizationStore.oraColumnName.toLowerCase();
  return colName.includes('go') || 
         colName === 'go_terms' ||
         colName === 'gene_ontology' ||
         colName.startsWith('go_');
});

/**
 * Fetch GO term details in batch for GO term enrichment.
 * Only called when oraColumnName is a GO term column.
 * Now includes depth information.
 */
async function fetchGoTermDetails(goIds: string[]): Promise<void> {
  if (!goIds.length) return;
  
  // Filter out already cached IDs
  const uncachedIds = goIds.filter(id => !goTermInfoCache.value[id]);
  if (!uncachedIds.length) return;
  
  try {
    const { data } = await axios.post(`${API_BASE_URL}/api/go/terms/batch`, {
      go_ids: uncachedIds,
      include_depth: true
    });
    
    if (data.available && data.terms) {
      for (const [goId, term] of Object.entries(data.terms)) {
        const termData = term as { name?: string; namespace?: string; depth?: number };
        goTermInfoCache.value[goId] = {
          name: termData.name || '',
          namespace: termData.namespace || '',
          depth: termData.depth ?? -1
        };
      }
    }
  } catch (error) {
    console.warn('Failed to fetch GO term details:', error);
  }
}

/**
 * Format GO depth for display with visual indicator.
 */
function formatGoDepth(depth: number): string {
  if (depth < 0) return 'N/A';
  if (depth === 0) return '0 (Root)';
  if (depth <= 2) return `${depth} (General)`;
  if (depth <= 5) return `${depth} (Intermediate)`;
  return `${depth} (Specific)`;
}

/**
 * Format GO namespace for display.
 */
function formatGoNamespace(namespace: string): string {
  const namespaceMap: Record<string, string> = {
    'biological_process': 'Biological Process',
    'molecular_function': 'Molecular Function',
    'cellular_component': 'Cellular Component'
  };
  return namespaceMap[namespace] || namespace;
}

/**
 * Fetch ORA data from backend endpoint.
 * 
 * The backend performs:
 * 1. Gene counting (unique genes, not occurrences) for array columns
 * 2. Species-specific background (all genes in same species)
 * 3. Fisher's Exact Test for each attribute
 * 4. Benjamini-Hochberg FDR correction
 * 5. Combined score calculation: -log10(q_value) * gene_ratio
 * 6. Filtering by significance and min_count
 * 7. Top-N selection by combined_score
 */
async function fetchAndPrepareData() {
  const requestId = ++oraRequestSeq;
  loading.value = true;
  renderReady.value = false;
  error.value = "";
  try {
    resetDotplot();
    // Prepare ORA request — max_subset_size replaces the separate /api/count call
    const oraRequest = {
      table_name: props.tableName,
      column_name: visualizationStore.oraColumnName,
      filters: mergedFilters.value,
      significance: visualizationStore.significance,
      top_n: visualizationStore.oraTopN,
      min_count: visualizationStore.oraMinCount,
      topological_filter: isGoTermEnrichment.value ? visualizationStore.oraTopologicalFilter : false,
      max_subset_size: 5000,
    };
    
    console.log('ORA Request:', oraRequest);
    
    // Call backend ORA endpoint (includes count check)
    const { data: oraResponse } = await axios.post(
      `${API_BASE_URL}/api/ora`,
      oraRequest,
    );
    if (requestId !== oraRequestSeq) return;
    
    console.log('ORA Response:', oraResponse);
    console.log('ORA Response type:', typeof oraResponse);
    
    // Parse response if it's a string (shouldn't happen with proper Content-Type)
    let parsedResponse = oraResponse;
    if (typeof oraResponse === 'string') {
      console.warn('ORA response is string, parsing JSON manually');
      parsedResponse = JSON.parse(oraResponse);
    }

    // Extract count from metadata (replaces separate /api/count call)
    rowCount.value = parsedResponse.metadata?.count ?? parsedResponse.metadata?.subset_size ?? 0;

    // Check for count-exceeded or empty subset
    if (parsedResponse.metadata?.message || !parsedResponse.results?.length) {
      pValueEntries.value = [];
      oraMetadata.value = parsedResponse.metadata;
      await nextTick();
      await syncPlotHeightWithViewport();
      await drawDotPlot();
      publishAnalysisContext();
      renderReady.value = true;
      return;
    }

    // Check for error response
    if (parsedResponse.error) {
      throw new Error(parsedResponse.error);
    }

      // Store results - map backend response to frontend interface
      // Fold enrichment and expected count are now calculated on backend
      pValueEntries.value = parsedResponse.results.map((r: any) => {
        return {
          attr: r.attribute,  // Map 'attribute' to 'attr' for compatibility
          attribute: r.attribute,  // Keep original for modal
          subset_count: r.subset_count,
          background_count: r.background_count,
          gene_ratio: r.gene_ratio,
          p_value: r.p_value,
          q_value: r.q_value,
          combined_score: r.combined_score,
          odds_ratio: r.odds_ratio,
          expected_count: r.expected_count,
          fold_enrichment: r.fold_enrichment,
        };
      });

      oraMetadata.value = parsedResponse.metadata;

      console.log(`ORA results: ${pValueEntries.value.length} significant terms`);
      console.log(`Metadata:`, oraMetadata.value);
      console.log(`ORA Column Name: "${visualizationStore.oraColumnName}"`);
      console.log(`Is GO Term Enrichment: ${isGoTermEnrichment.value}`);
      
      // Fetch GO term details if this is GO term enrichment
      if (isGoTermEnrichment.value && pValueEntries.value.length > 0) {
        // Use inline GO terms from ORA response if available, otherwise fetch separately
        if (parsedResponse.go_terms) {
          for (const [goId, term] of Object.entries(parsedResponse.go_terms)) {
            const termData = term as { name?: string; namespace?: string; depth?: number };
            goTermInfoCache.value[goId] = {
              name: termData.name || '',
              namespace: termData.namespace || '',
              depth: termData.depth ?? -1
            };
          }
        } else {
          const goIds = pValueEntries.value.map(e => e.attr);
          console.log(`Fetching GO term details for ${goIds.length} terms:`, goIds.slice(0, 5));
          await fetchGoTermDetails(goIds);
        }
        console.log(`GO Term Cache after fetch:`, goTermInfoCache.value);
        
        // Enrich entries with GO term info including depth
        pValueEntries.value = pValueEntries.value.map(entry => {
          const goInfo = goTermInfoCache.value[entry.attr];
          return {
            ...entry,
            go_name: goInfo?.name,
            go_namespace: goInfo?.namespace,
            go_depth: goInfo?.depth
          };
        });
        console.log(`Enriched entries sample:`, pValueEntries.value.slice(0, 2));
      }

      await nextTick();
      await syncPlotHeightWithViewport();
      await drawDotPlot();
      publishAnalysisContext();
      renderReady.value = true;
  } catch (e) {
    if (requestId !== oraRequestSeq) return;
    console.error("Error fetching ORA data:", e);
    error.value = "Failed to load ORA data.";
    renderReady.value = true;
  } finally {
    if (requestId === oraRequestSeq) {
      loading.value = false;
    }
  }
}

/**
 * Publish a compact digest of the current ORA result to the assistant store
 * so the AI can answer questions like "do you see a pattern?" about the
 * results the user is currently looking at. Stays small (top-N rows + meta)
 * to keep the prompt size bounded.
 */
function publishAnalysisContext() {
  try {
    const top = pValueEntries.value.slice(0, 25).map((e) => ({
      attribute: e.attr,
      name: e.go_name || undefined,
      namespace: e.go_namespace || undefined,
      depth: e.go_depth,
      subset_count: e.subset_count,
      background_count: e.background_count,
      expected_count: Number(e.expected_count?.toFixed?.(2) ?? e.expected_count),
      fold_enrichment: Number(e.fold_enrichment?.toFixed?.(2) ?? e.fold_enrichment),
      gene_ratio: Number(e.gene_ratio?.toFixed?.(4) ?? e.gene_ratio),
      p_value: e.p_value,
      q_value: e.q_value,
      combined_score: Number(e.combined_score?.toFixed?.(2) ?? e.combined_score),
    }));
    assistantStore.setAnalysisContext(`ora:${props.tableName}`, {
      kind: "ora",
      table: props.tableName,
      column: visualizationStore.oraColumnName,
      is_go_term: isGoTermEnrichment.value,
      significance: visualizationStore.significance,
      top_n_displayed: visualizationStore.oraTopN,
      min_count: visualizationStore.oraMinCount,
      metadata: oraMetadata.value || null,
      n_results: pValueEntries.value.length,
      top_terms: top,
    });
  } catch (e) {
    console.warn("Failed to publish ORA analysis context:", e);
  }
}

// Compute p-values for each attribute observed in either subset or background
// NOTE: This function is now DEPRECATED - ORA calculation moved to backend
// Kept for reference only
/*
function calculatePValues(
  subFreq: Record<string, number>,
  bgFreq: Record<string, number>,
  subSize: number,
  bgSize: number,
): PValueEntry[] {
  // ... old implementation removed ...
  // See backend: app/services.py -> calculate_ora()
  return [];
}
*/

// Local createVisibleColorMapping removed — now imported from @/shared/colorMapping

// Keep the old function for backwards compatibility with API-based lookup
async function createSideColorMapping(column_name: string, colType: string) {
  try {
    if (colType === "double precision" || colType === "bigint") {
      const { data } = await axios.get(
        `${API_BASE_URL}/api/column_bins`,
        {
          params: {
            table_names: props.tableName + "_meta",
            column_name: column_name,
            n_bins: 50, // Default histogram resolution
          },
        },
      );

      const bins = data; // Expect array of {bucket_lower, bucket_upper, frequency}

      if (!bins?.length) {
        // Fallback or empty mapping
        return {};
      }

      // Extract numeric domain for continuous scale
      const domainMin = bins[0].bucket_lower;
      const domainMax = bins[bins.length - 1].bucket_upper;

      // Use a sequential or diverging color scale suitable for numeric data
      // For example, use d3.interpolateViridis or your chosen scheme
      const colorScale = d3
        .scaleSequential(d3.interpolateBlues)
        .domain([domainMin, domainMax]);

      // Cache the bins and scale together, returning a function that maps value to color
      const mapping = {
        bins,
        colorScale,
        getColor: (value: number) => {
          // Find the bin where value falls (bucket_lower < value <= bucket_upper)
          const bin = bins.find(
            (b) => value >= b.bucket_lower && value <= b.bucket_upper,
          );
          return bin
            ? colorScale((bin.bucket_lower + bin.bucket_upper) / 2)
            : "#eeeeee";
        },
      };

      return mapping;
    } else if (colType === "boolean") {
      const terms = [true, false, null];
      const range = ["#36a2eb", "#e74c3c", "#ccc"];
      const scale = d3.scaleOrdinal().domain(terms).range(range);

      const mapping = {};
      terms.forEach((term) => {
        mapping[term] = scale(term);
      });

      return mapping;
    } else {
      const response = await axios.get(`${API_BASE_URL}/api/col`, {
        params: { column_name },
      });
      const terms = response.data.terms;
      const colors = getCategoricalColors(terms.length);
      const scale = d3.scaleOrdinal().domain(terms).range(colors);

      const mapping = {};
      terms.forEach((term) => {
        mapping[term] = scale(term);
      });

      return mapping;
    }
  } catch (error) {
    console.error(
      `Failed to fetch unique terms or buckets for column ${column_name}`,
      error,
    );
    return {};
  }
}

//Plot
function resetDotplot() {
  if (dotplotContainer.value) {
    d3.select(dotplotContainer.value).selectAll("*").remove();
  }
  if (colorLegendContainer.value) {
    d3.select(colorLegendContainer.value).selectAll("*").remove();
  }
  if (sizeLegendContainer.value) {
    d3.select(sizeLegendContainer.value).selectAll("*").remove();
  }
}

// Render row side colors for the dotplot using createVisibleColorMapping and data
async function renderDotplotRowSideColors({
  svg,
  margin,
  yLabels,
  attributeValues,
  column_name,
  colType,
  sideColorWidth = 20,
}: {
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  margin: { top: number; right: number; bottom: number; left: number };
  yLabels: string[];
  attributeValues: any[];
  column_name: string;
  colType: string;
  sideColorWidth?: number;
}) {
  // Register values with shared registry for cross-plot consistency, then get mapping
  if (sharedColorRegistry) {
    sharedColorRegistry.registerValues(column_name, colType, attributeValues);
  }
  const colorMap = (sharedColorRegistry && sharedColorRegistry.getMapping(column_name))
    ?? createVisibleColorMapping(column_name, colType, attributeValues);

  // Setup vertical band scale
  const scale = d3
    .scaleBand()
    .domain(yLabels)
    .range([0, +svg.attr("height") - margin.top - margin.bottom])
    .padding(0);

  // Append the group at the correct offset
  const containerGroup = svg
    .append("g")
    .attr(
      "transform",
      `translate(${margin.left - sideColorWidth},${margin.top})`,
    );

  // Draw color rectangles
  const rects = containerGroup
    .selectAll("rect")
    .data(attributeValues)
    .join("rect")
    .attr("x", 0)
    .attr("y", (d, i) => scale(yLabels[i]) ?? 0)
    .attr("width", sideColorWidth * 0.75)
    .attr("height", scale.bandwidth())
    .attr("fill", (d) => {
      // Numeric columns with binning and getColor method
      if (
        (colType === "double precision" || colType === "bigint") &&
        d !== null &&
        d !== undefined &&
        typeof colorMap.getColor === "function"
      ) {
        return colorMap.getColor(d) ?? "#eeeeee";
      }
      // Boolean/categorical mapping
      if (colorMap[d] !== undefined) return colorMap[d];
      return "#eeeeee";
    });

  // Tooltip setup, create div if it doesn't exist
  let tooltip = d3.select("#sideColorTooltip");

  tooltip = d3
    .select(svg.node().parentNode)
    .append("div")
    .attr("id", "sideColorTooltip")
    .style("position", "absolute")
    .style("z-index", "50")
    .style("visibility", "hidden")
    .style("background-color", "#f9fafb")
    .style("color", "#374151")
    .style("font-size", "0.75rem")
    .style("border-radius", "0.375rem")
    .style("padding", "0.25rem 0.5rem")
    .style("min-width", "6rem")
    .style("max-width", "20rem")
    .style("border", "1px solid #d1d5db")
    .style("box-shadow", "0 1px 2px rgba(0,0,0,0.05)")
    .style("pointer-events", "none");

  rects
    .on("mouseover", function (event, d) {
      d3.select(this).attr("stroke", "white").style("stroke-width", 2);

      let tooltipText = "";

      if (
        (colType === "double precision" || colType === "bigint") &&
        d !== null &&
        d !== undefined &&
        colorMap.bins
      ) {
        // Find the bin that includes d
        const bin = colorMap.bins.find(
          (b) => d >= b.bucket_lower && d <= b.bucket_upper,
        );
        if (bin) {
          tooltipText = `<strong>${column_name} bucket:</strong> [${bin.bucket_lower.toFixed(0)}, ${bin.bucket_upper.toFixed(0)}]`;
        } else {
          tooltipText = `<strong>${column_name}:</strong> ${d}`;
        }
      } else {
        tooltipText = `<strong>${column_name}:</strong> ${d}`;
      }
      tooltip.html(tooltipText);
      tooltip.style("visibility", "visible");
    })
    .on("mousemove", function (event) {
      if (!svg.node()?.parentNode) return;
      const containerRect = svg.node()!.parentNode!.getBoundingClientRect();
      const tooltipNode = tooltip.node();
      if (!tooltipNode) return;
      const tooltipRect = tooltipNode.getBoundingClientRect();

      const offsetX = 10;
      const offsetY = 10;
      let xPos = event.clientX - containerRect.left + offsetX;
      let yPos = event.clientY - containerRect.top + offsetY;

      // Adjust horizontal positioning if tooltip goes beyond container
      if (xPos + tooltipRect.width > containerRect.width) {
        xPos = event.clientX - containerRect.left - tooltipRect.width - offsetX;
      }
      // Adjust vertical positioning if tooltip goes beyond container
      if (yPos + tooltipRect.height > containerRect.height) {
        yPos = event.clientY - containerRect.top - tooltipRect.height - offsetY;
      }

      xPos = Math.max(0, xPos);
      yPos = Math.max(0, yPos);

      tooltip.style("left", xPos + "px").style("top", yPos + "px");
    })
    .on("mouseout", function () {
      d3.select(this).attr("stroke", "none");
      tooltip.style("visibility", "hidden");
    })
    .on("click", function (event, d) {
      if (
        (colType === "double precision" || colType === "bigint") &&
        d !== null &&
        d !== undefined &&
        colorMap.bins
      ) {
        // Find bin for clicked value to set filter range
        const bin = colorMap.bins.find(
          (b) => d >= b.bucket_lower && d <= b.bucket_upper,
        );
        if (bin) {
          filtersStore.setFilter(column_name, {
            value: [bin.bucket_lower, bin.bucket_upper],
          });
        } else {
          filtersStore.setFilter(column_name, { value: d });
        }
      } else {
        // For categorical or boolean, set exact filter
        filtersStore.setFilter(column_name, { value: d });
      }
    });
}

function createSizeLegend(
  svg: d3.Selection<SVGGElement, unknown, null, undefined>,
  sizeScale: d3.ScaleSqrt<number, number>,
  values: number[],
  circleSpacing = 50,
  leftMargin = 0,
  topMargin = 40,
  title = "Observed Count",
) {
  values = values.slice().sort((a, b) => a - b);
  const maxRadius = Math.max(...values.map(sizeScale));
  const labelOffset = 8;

  // Create a group inside parentG and position it according to margins
  const legendGroup = svg
    .append("g")
    .attr("transform", `translate(${leftMargin},${topMargin})`);

  // Title text
  legendGroup
    .append("text")
    .attr("x", 0)
    .attr("y", -topMargin / 2)
    .attr("font-size", 12)
    .attr("font-weight", "bold")
    .attr("text-anchor", "start")
    .text(title);

  // For each value, draw a circle and label
  values.forEach((value, i) => {
    const radius = sizeScale(value);
    const cy = i * circleSpacing;

    // Circle
    legendGroup
      .append("circle")
      .attr("cx", maxRadius)
      .attr("cy", cy)
      .attr("r", radius)
      .style("fill", "#bbb")
      .style("stroke", "#888");

    // Text label
    legendGroup
      .append("text")
      .attr("x", maxRadius * 2 + labelOffset)
      .attr("y", cy + 4) // vertically center text approx
      .text(value)
      .style("text-anchor", "start")
      .style("font-size", "11px");
  });
}

function createColorLegend(
  svg: d3.Selection<SVGGElement, unknown, null, undefined>,
  colorScale: d3.ScaleSequential<string>,
  minQValue: number,  // Most significant q-value (will be shown at TOP, yellow)
  maxQValue: number,  // Least significant q-value (will be shown at BOTTOM, dark)
  legendWidth = 20,
  legendHeight = 120,
  margin = { top: 40, right: 80, bottom: 10, left: 0 },
  title = "p-value",
) {
  // Create a group inside the provided parent selection and position it using margin
  const legend = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Define linearGradient with unique id to avoid conflicts
  const gradientId = `colorLegendGradient`;

  const defs = svg.append("defs");
  const gradient = defs
    .append("linearGradient")
    .attr("id", gradientId)
    .attr("x1", "0%")
    .attr("y1", "0%")
    .attr("x2", "0%")
    .attr("y2", "100%");

  // Legend orientation: TOP = most significant (low q-value, yellow), BOTTOM = least significant (high q-value, dark)
  // d=0 -> top (low q-value, yellow), d=1 -> bottom (high q-value, dark)
  const nStops = 10;
  const logMin = Math.log10(minQValue + 1e-300);
  const logMax = Math.log10(maxQValue + 1e-300);

  gradient
    .selectAll("stop")
    .data(d3.range(0, 1.01, 1 / nStops))
    .join("stop")
    .attr("offset", (d) => `${d * 100}%`)
    .attr("stop-color", (d) => {
      // d=0 -> top (low q-value), d=1 -> bottom (high q-value)
      const logValue = logMin + (logMax - logMin) * d;
      const value = Math.pow(10, logValue);
      return colorScale(value);
    });

  // Draw the rectangle filled with the gradient
  legend
    .append("rect")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .style("fill", `url(#${gradientId})`);

  // Create a logarithmic scale for the axis (low q-value at top, high at bottom)
  const legendScale = d3
    .scaleLog()
    .domain([minQValue, maxQValue])
    .range([0, legendHeight]);

  // Draw right-oriented axis on the rectangle side (no tick marks, only labels)
  const legendAxis = d3.axisRight(legendScale).ticks(5, ".1e").tickSize(0);

  legend
    .append("g")
    .attr("transform", `translate(${legendWidth}, 0)`)
    .call(legendAxis)
    .call((g) => g.select(".domain").remove());

  // Add title text above the legend - show the significance threshold used
  svg
    .append("text")
    .attr("x", margin.left)
    .attr("y", margin.top / 2)
    .attr("font-size", 12)
    .attr("font-weight", "bold")
    .attr("font-family", "sans-serif")
    .text(title + ` (< ${visualizationStore.significance})`);
}

// Draw dotplot based on pValueEntries in dotplotContainer ref
async function drawDotPlot() {
  if (!dotplotContainer.value) return;
  
  resetDotplot();
  
  // Handle case when there are no significant results
  if (!pValueEntries.value.length) {
    const container = dotplotContainer.value;
    const containerWidth = container.clientWidth || 800;
    const containerHeight = container.clientHeight || finalPlotHeight.value;
    
    const svg = d3
      .select(container)
      .append("svg")
      .attr("data-testid", "ora-dotplot-svg")
      .attr("width", containerWidth)
      .attr("height", containerHeight);
    
    // Show message for no significant results
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", containerHeight / 2 - 20)
      .attr("text-anchor", "middle")
      .attr("font-size", "16px")
      .attr("font-weight", "bold")
      .attr("fill", "#6b7280")
      .text("No Significant Results");
    
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", containerHeight / 2 + 10)
      .attr("text-anchor", "middle")
      .attr("font-size", "14px")
      .attr("fill", "#9ca3af")
      .text(`No terms with FDR q-value < ${visualizationStore.significance} found`);
    
    svg
      .append("text")
      .attr("x", containerWidth / 2)
      .attr("y", containerHeight / 2 + 35)
      .attr("text-anchor", "middle")
      .attr("font-size", "12px")
      .attr("fill", "#9ca3af")
      .text("Try adjusting the significance threshold or filters");
    
    return;
  }

  const container = dotplotContainer.value;

  const totalRowSideColorWidth = 20;

  const containerWidth = container.clientWidth || 800;
  const containerHeight = container.clientHeight || finalPlotHeight.value;

  const legendAreaWidth = 150; // width reserved for legend on right
  const legendSpacingVertical = 20; // vertical spacing between legends
  const legendHeight = 120;

  const margin = {
    top: 50,
    right: visualizationStore.legend ? legendAreaWidth + 40 : 40,
    bottom: 76,
    left: 120,
  };

  if (visualizationStore.oraRowSideColor) {
    margin.left += totalRowSideColorWidth;
  }

  const innerWidth = containerWidth - margin.left - margin.right;
  const innerHeight = containerHeight - margin.top - margin.bottom;

  const svg = d3
    .select(container)
    .append("svg")
    .attr("data-testid", "ora-dotplot-svg")
    .attr("width", containerWidth)
    .attr("height", containerHeight);

  svg
    .append("text")
    .attr("x", containerWidth / 2) // center horizontally
    .attr("y", 50 / 2) // position above the plot area, adjust as needed
    .attr("text-anchor", "middle") // center the text
    .attr("font-size", "16px")
    .attr("font-style", "italic")
    .text(beautifyLabel(localTableName.value));

  const plotGroup = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);

  // Only create legend groups if legend is enabled
  let legendGroup, colorLegendGroup, sizeLegendGroup;
  if (visualizationStore.legend) {
    legendGroup = svg
      .append("g")
      .attr(
        "transform",
        `translate(${margin.left + innerWidth + 40},${margin.top})`,
      );

    colorLegendGroup = legendGroup
      .append("g")
      .attr("transform", `translate(0,0)`);

    sizeLegendGroup = legendGroup
      .append("g")
      .attr("transform", `translate(0, ${legendHeight + legendSpacingVertical})`);
  }

  // Sort entries for plotting order
  const sortedEntries = pValueEntries.value
    .slice()
    .sort((a, b) =>
      compareValues(
        a[visualizationStore.oraOrder.name],
        b[visualizationStore.oraOrder.name],
        visualizationStore.oraOrder.order,
      ),
    );

  // Scales
  const maxLog2FoldEnrichment = d3.max(sortedEntries, (d) => log2FoldEnrichment(d.fold_enrichment)) ?? 0;
  const minLog2FoldEnrichment = d3.min(sortedEntries, (d) => log2FoldEnrichment(d.fold_enrichment)) ?? 0;
  const maxSubsetCount = d3.max(sortedEntries, (d) => d.subset_count) ?? 1;
  const minSubsetCount = d3.min(sortedEntries, (d) => d.subset_count) ?? 0;

  const xScale = d3
    .scaleLinear()
    .domain([Math.min(0, minLog2FoldEnrichment), maxLog2FoldEnrichment > 0 ? maxLog2FoldEnrichment : 1])
    .range([0, innerWidth]);

  const yScale = d3
    .scaleBand()
    .domain(sortedEntries.map((d) => d.attr))
    .range([0, innerHeight])
    .padding(0.1);

  const sizeScale = d3
    .scaleSqrt()
    .domain([minSubsetCount, maxSubsetCount])
    .range([6, maxBubbleRadius]);

  // Color scale by FDR-adjusted q-value (log scale)
  // For q-values: lower = more significant = should be brighter (yellow in VIRIDIS)
  // VIRIDIS interpolator: 0 = dark purple, 1 = yellow
  // So we INVERT the domain: [maxQValue, minQValue] so that low q-values map to high interpolator values (yellow)
  const minQValue = d3.min(sortedEntries, (d) => d.q_value) ?? parseFloat(visualizationStore.significance);
  const maxQValue = d3.max(sortedEntries, (d) => d.q_value) ?? 1;
  
  // Ensure we have a valid range for logarithmic scale (avoid values too close to 0)
  const minQValueSafe = Math.max(minQValue, 1e-300);
  // Ensure maxQValue is at least 10x larger than minQValue for visible color gradient
  const maxQValueSafe = Math.max(maxQValue, minQValueSafe * 100);
  
  // INVERTED domain: high q-values -> 0 (dark), low q-values -> 1 (yellow)
  const colorScale = d3
    .scaleSequentialLog(
      COLORSCALES[visualizationStore.colorScale] as (t: number) => string,
    )
    .domain([maxQValueSafe, minQValueSafe])  // INVERTED: max to min
    .clamp(true);

  // Create tooltip div (matching heatmap styling)
  const tooltip = d3
    .select(container)
    .append("div")
    .style("position", "absolute")
    .style("z-index", "1000")
    .style("visibility", "hidden")
    .style("background-color", "#f9fafb") // tailwind bg-gray-50
    .style("color", "#374151") // tailwind text-gray-700
    .style("font-size", "0.75rem") // tailwind text-xs
    .style("border-radius", "0.375rem") // tailwind rounded-md
    .style("padding", "0.5rem") // tailwind p-2
    .style("min-width", "10rem")
    .style("max-width", "20rem")
    .style("white-space", "normal")
    .style("word-wrap", "break-word")
    .style("border", "1px solid #d1d5db")
    .style("box-shadow", "0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)")
    .style("pointer-events", "none");

  // Draw points
  plotGroup
    .selectAll("circle")
    .data(sortedEntries)
    .enter()
    .append("circle")
    .attr("cx", (d) => xScale(log2FoldEnrichment(d.fold_enrichment)))
    .attr("cy", (d) => (yScale(d.attr) ?? 0) + yScale.bandwidth() / 2)
    .attr("r", (d) => sizeScale(d.subset_count))
    .style("fill", (d) => colorScale(d.q_value ?? 1))
    .style("opacity", 0.8)
    .on("mouseover", (event, d) => {
      tooltip.style("visibility", "visible");
      d3.select(event.currentTarget)
        .style("stroke", "white")
        .style("stroke-width", 3);
    })
    .on("mousemove", (event, d) => {
      // Build tooltip based on user-configured visible fields
      let tooltipContent = '';
      
      // Check if this is GO term enrichment AND we have GO info for this term
      const hasGoInfo = isGoTermEnrichment.value && (d.go_name || goTermInfoCache.value[d.attr]?.name);
      const goName = d.go_name || goTermInfoCache.value[d.attr]?.name || '';
      
      // Get configured fields from store
      const visibleFields = visualizationStore.oraTooltipFields;
      
      // Build content based on selected fields only
      let hasContent = false;
      
      // Show GO name if selected and available (GO enrichment only)
      if (visibleFields.includes('go_name') && isGoTermEnrichment.value && hasGoInfo) {
        tooltipContent += `<strong>${goName}</strong><br/>`;
        hasContent = true;
      }
      
      // Show attribute name if selected
      if (visibleFields.includes('attribute_name')) {
        if (isGoTermEnrichment.value && hasGoInfo && visibleFields.includes('go_name')) {
          tooltipContent += `<strong>GO ID:</strong> ${d.attr}<br/>`;
        } else {
          tooltipContent += `<strong>${d.attr}</strong><br/>`;
        }
        hasContent = true;
      }
      
      // Add separator if we have header content and will add metrics
      if (hasContent && visibleFields.some(f => !['attribute_name', 'go_name'].includes(f))) {
        tooltipContent += `<hr style="margin:4px 0; border-color:#888"/>`;
      }
      
      // Add core enrichment metrics
      if (visibleFields.includes('subset_count')) {
        tooltipContent += `<strong>Observed Count:</strong> ${d.subset_count}<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('expected_count')) {
        tooltipContent += `<strong>Expected Count:</strong> ${d.expected_count.toFixed(2)}<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('background_count')) {
        tooltipContent += `<strong>Background Count:</strong> ${d.background_count}<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('fold_enrichment')) {
        tooltipContent += `<strong>log<sub>2</sub>(Fold Enrichment):</strong> ${log2FoldEnrichment(d.fold_enrichment).toFixed(2)}<br/>`;
        hasContent = true;
      }
      
      // Add statistical details metrics
      if (visibleFields.includes('gene_ratio')) {
        tooltipContent += `<strong>Gene Ratio:</strong> ${(d.gene_ratio * 100).toFixed(1)}%<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('p_value')) {
        tooltipContent += `<strong>P-Value:</strong> ${d.p_value.toExponential(2)}<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('q_value')) {
        tooltipContent += `<strong>Q-Value:</strong> ${d.q_value.toExponential(2)}<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('combined_score')) {
        tooltipContent += `<strong>Combined Score:</strong> ${d.combined_score.toFixed(2)}<br/>`;
        hasContent = true;
      }
      if (visibleFields.includes('odds_ratio') && d.odds_ratio !== undefined) {
        tooltipContent += `<strong>Odds Ratio:</strong> ${d.odds_ratio.toFixed(2)}<br/>`;
        hasContent = true;
      }
      // GO-specific fields (only show for GO enrichment)
      if (isGoTermEnrichment.value) {
        if (visibleFields.includes('go_namespace') && d.go_namespace) {
          const namespaceLabel = d.go_namespace === 'biological_process' ? 'BP' : 
                                 d.go_namespace === 'molecular_function' ? 'MF' : 
                                 d.go_namespace === 'cellular_component' ? 'CC' : d.go_namespace;
          tooltipContent += `<strong>GO Category:</strong> ${namespaceLabel}<br/>`;
          hasContent = true;
        }
        if (visibleFields.includes('go_depth') && d.go_depth !== undefined) {
          tooltipContent += `<strong>GO Depth:</strong> ${d.go_depth}<br/>`;
          hasContent = true;
        }
      }
      
      // Add call-to-action
      if (hasContent) {
        tooltipContent += `<hr style="margin:4px 0; border-color:#888"/>`;
      }
      tooltipContent += `<div style="text-align:center; font-size:0.7rem; color:#6b7280;">Right-click for full details</div>`;
      

      const containerRect = container.getBoundingClientRect();
      const tooltipNode = tooltip.node();
      if (!tooltipNode) return;
      const tooltipRect = tooltipNode.getBoundingClientRect();

      const offsetX = 10; // horizontal offset from cursor
      const offsetY = 10; // vertical offset below cursor

      let xPosition = event.clientX - containerRect.left + offsetX;
      let yPosition = event.clientY - containerRect.top + offsetY;

      // Mirror horizontally if going out of right boundary
      if (xPosition + tooltipRect.width > containerRect.width) {
        xPosition =
          event.clientX - containerRect.left - tooltipRect.width - offsetX;
      }

      // Mirror vertically if going out of bottom boundary
      if (yPosition + tooltipRect.height > containerRect.height) {
        yPosition =
          event.clientY - containerRect.top - tooltipRect.height - offsetY;
      }

      // Clamp to minimum 0 to avoid negative positioning
      xPosition = Math.max(0, xPosition);
      yPosition = Math.max(0, yPosition);

      tooltip
        .html(tooltipContent)
        .style("left", `${xPosition}px`)
        .style("top", `${yPosition}px`)
        .style("pointer-events", "auto"); // Enable click on filter link
    })
    .on("mouseleave", (event) => {
      tooltip.style("visibility", "hidden");
      d3.select(event.currentTarget).style("stroke", "none");
    })
    .on("contextmenu", (event, d) => {
      // Right-click opens modal with full term details
      event.preventDefault();
      selectedTerm.value = d;
      showOraTooltipModal.value = true;
      tooltip.style("visibility", "hidden");
    });

  // Add mobile long-press support for touch devices
  const circleElements = plotGroup.selectAll("circle").nodes() as SVGCircleElement[];
  let longPressTimer: number | null = null;
  let longPressTriggered = false;
  
  circleElements.forEach((circle) => {
    if (!circle) return;
    
    circle.addEventListener("touchstart", function (event: TouchEvent) {
      longPressTriggered = false;
      const target = event.currentTarget as SVGCircleElement;
      const d = d3.select(target).datum() as any;
      
      longPressTimer = window.setTimeout(() => {
        longPressTriggered = true;
        selectedTerm.value = d;
        showOraTooltipModal.value = true;
        tooltip.style("visibility", "hidden");
      }, 500); // 500ms long press
    }, { passive: true });
    
    circle.addEventListener("touchend", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
    
    circle.addEventListener("touchmove", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
  });

  // X axis
  const xAxis = d3.axisBottom(xScale).ticks(6).tickFormat(d3.format(".2f"));
  plotGroup
    .append("g")
    .attr("transform", `translate(0,${innerHeight})`)
    .call(xAxis);

  // Y axis with label truncation
  const maxLabelWidth = 100; // Max width for labels
  
  const yAxisGroup = plotGroup
    .append("g")
    .attr("transform", `translate(${0 - totalRowSideColorWidth},${0})`)
    .call(d3.axisLeft(yScale).tickSizeOuter(0));
  
  const yAxisFontSize = Math.max(8, Math.min(10, yScale.bandwidth() * 0.75));
  const yAxisTexts = yAxisGroup.selectAll("text")
    .style("font-size", `${yAxisFontSize}px`);
  
  // Truncate long labels and add ellipsis
  yAxisTexts.each(function() {
    const textElement = d3.select(this);
    const originalText = textElement.text();
    const textLength = (this as SVGTextElement).getComputedTextLength();
    
    if (textLength > maxLabelWidth) {
      let truncatedText = originalText;
      
      // Iteratively truncate until it fits
      while ((this as SVGTextElement).getComputedTextLength() > maxLabelWidth && truncatedText.length > 0) {
        truncatedText = truncatedText.slice(0, -1);
        textElement.text(truncatedText + '...');
      }
      
      // Store original text as title for browser tooltip
      textElement.append("title").text(originalText);
    }
  });
  
  // Add custom tooltip for row labels
  const rowLabelTooltip = d3
    .select(container)
    .append("div")
    .attr("class", "row-label-tooltip")
    .style("position", "absolute")
    .style("z-index", "60")
    .style("visibility", "hidden")
    .style("background-color", "#1f2937")
    .style("color", "#f9fafb")
    .style("font-size", "0.75rem")
    .style("border-radius", "0.375rem")
    .style("padding", "0.25rem 0.5rem")
    .style("white-space", "nowrap")
    .style("pointer-events", "none");
  
  yAxisTexts
    .on("mouseover", function() {
      const currentText = d3.select(this).text();
      
      // Only show tooltip if text is truncated (contains "...")
      if (currentText.includes('...')) {
        const titleElement = d3.select(this).select("title");
        const fullText = !titleElement.empty() ? titleElement.text() : currentText.replace('...', '');
        
        rowLabelTooltip.html(fullText);
        rowLabelTooltip.style("visibility", "visible");
      }
    })
    .on("mousemove", function(event) {
      if (!dotplotContainer.value) return;
      const containerRect = dotplotContainer.value.getBoundingClientRect();
      
      const xPos = event.clientX - containerRect.left + 10;
      const yPos = event.clientY - containerRect.top - 10;
      
      rowLabelTooltip
        .style("left", xPos + "px")
        .style("top", yPos + "px");
    })
    .on("mouseout", function() {
      rowLabelTooltip.style("visibility", "hidden");
    });

  // Axis label
  svg
    .append("text")
    .attr("x", margin.left + innerWidth / 2)
    .attr("y", containerHeight - 42)
    .attr("text-anchor", "middle")
    .attr("font-weight", "bold")
    .call((text) => {
      text.append("tspan").text("log");
      text.append("tspan")
        .attr("baseline-shift", "sub")
        .attr("font-size", "70%")
        .text("2");
      text.append("tspan").text("(Fold Enrichment)");
    });

  // Create legends only if enabled
  if (visualizationStore.legend && colorLegendGroup && sizeLegendGroup) {
    // Use actual min/max q-values from data for legend (same as color scale domain - INVERTED)
    // Legend shows: top = most significant (low q-value, yellow), bottom = least significant (high q-value, dark)
    createColorLegend(
      colorLegendGroup, // pass the top legend group
      colorScale,
      minQValueSafe,  // Legend top: most significant (yellow)
      maxQValueSafe,  // Legend bottom: least significant (dark)
      20, // legendWidth
      120, // legendHeight
      { top: 20, right: 0, bottom: 0, left: 0 }, // no margin inside group
      "q-value (FDR)",
    );
    const sizeValues = [
      minSubsetCount,
      Math.round((minSubsetCount + maxSubsetCount) / 2),
      maxSubsetCount,
    ].filter((v) => v > 0);

    const sizeLegendHeight = 150; // approximate height to reserve; adjust as needed
    createSizeLegend(
      sizeLegendGroup, // pass the bottom legend group
      sizeScale,
      sizeValues,
      50,
      0, // leftMargin inside group
      50, // topMargin inside group
      "Observed Count",
    );
  }

  //RowSideColor
  const yLabels = sortedEntries.map((d) => d.attr);
  const attributeValues = sortedEntries.map((d) => d.attr);

  if (visualizationStore.oraRowSideColor) {
    await renderDotplotRowSideColors({
      svg,
      margin,
      yLabels,
      attributeValues,
      column_name: visualizationStore.oraColumnName,
      colType: columnMeta.value?.type.toLowerCase() ?? "text",
      sideColorWidth: totalRowSideColorWidth, // you have set to 20
    });
  }
}

//onTableChange
function onTableChange(value: string) {
  localTableName.value = value;
  emit("update:tableName", value);
}

// Handle filtering by ORA term from modal
function handleFilterByTerm(term: string) {
  filtersStore.setFilter(visualizationStore.oraColumnName, {
    value: term,
  });
}

//addDotplot
async function addDotplot() {
  if (props.existingTables.length !== Object.keys(props.allTables).length) {
    const nextTable = Object.entries(props.allTables).find(
      ([key]) => !props.existingTables.includes(key) && key !== props.tableName,
    )?.[0];
    if (nextTable) {
      emit("update:tableName", localTableName.value + "," + nextTable);
    }
  }
}

function removeDotplot() {
  if (props.existingTables.length > 1) {
    emit("update:tableName", "");
  }
}

function openSettingsOverlay() {
  emit("openSettingsOverlay");
}

const emit = defineEmits(["update:tableName", "openSettingsOverlay"]);

watch(
  [() => visualizationStore.oraColumnName],
  async () => {
    if (props.hashLoading) return;
    await fetchAndPrepareData();
  },
  { immediate: true },
);

watch(
  () => props.hashLoading,
  async (isLoading) => {
    if (isLoading === false) {
      await fetchAndPrepareData();
    }
  },
  { immediate: true },
);

watch(
  [
    () => visualizationStore.significance,
    () => visualizationStore.oraTopN,
    () => visualizationStore.oraMinCount,
    () => visualizationStore.oraTopologicalFilter,
  ],
  async () => {
    if (props.hashLoading) return;
    // Re-fetch data when significance, topN, minCount, or topological filter change
    // (these affect backend filtering)
    await fetchAndPrepareData();
  },
  { deep: true },
);

// Render-only settings — no re-fetch needed, just redraw the dot plot
watch(
  [
    () => visualizationStore.legend,
    () => visualizationStore.oraRowSideColor,
    () => visualizationStore.colorScale,
    () => visualizationStore.oraOrder,
  ],
  async () => {
    if (props.hashLoading) return;
    if (loading.value || !renderReady.value) return;
    loading.value = true;
    renderReady.value = false;
    await nextTick();
    await syncPlotHeightWithViewport();
    await drawDotPlot();
    renderReady.value = true;
    loading.value = false;
  },
  { deep: true },
);

// Watch for filter changes from sidebar and per-dataset ID filters
watch(
  [() => filters.value, () => filtersStore.datasetIdFilters],
  async () => {
    if (props.hashLoading) return;
    await fetchAndPrepareData();
  },
  { deep: true },
);

// Watch for color range changes (separate watch)
watch(
  () => visualizationStore.colorRange,
  async (colorRange) => {
    if (props.hashLoading) return;
    if (!colorRange) return; // guard against unset, undefined, or empty string
    if (loading.value || !renderReady.value) return;
    loading.value = true;
    renderReady.value = false;
    await nextTick();
    await syncPlotHeightWithViewport();
    await drawDotPlot();
    renderReady.value = true;
    loading.value = false;
  },
);

watch(
  [sidebarOpen, () => props.existingTables],
  async () => {
    if (props.hashLoading) return;
    if (loading.value || !renderReady.value) return;
    loading.value = true;
    renderReady.value = false;
    await nextTick();
    window.setTimeout(async () => {
      await syncPlotHeightWithViewport();
      await drawDotPlot();
      renderReady.value = true;
      loading.value = false;
    }, 300);
  },
  { deep: true },
);

// ResizeObserver for responsive sizing
let resizeObserver: ResizeObserver | null = null;
let resizeTimeout: ReturnType<typeof setTimeout> | null = null;
let lastContainerWidth = 0;

function handleWindowResize() {
  updateAvailablePlotHeight();
  if (!loading.value && renderReady.value && pValueEntries.value.length > 0) {
    if (resizeTimeout) clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
      drawDotPlot();
    }, 150);
  }
}

onMounted(async () => {
  await nextTick();
  updateAvailablePlotHeight();
  window.addEventListener("resize", handleWindowResize);

  // Set GO terms as default column if available and current is still default (ortho_id)
  if (visualizationStore.oraColumnName === 'ortho_id' && columnsStore.rowColumns.length > 0) {
    const goColumn = columnsStore.rowColumns.find(col => {
      const colName = col.column_name.toLowerCase();
      return colName.includes('go') || 
             colName === 'go_terms' ||
             colName === 'gene_ontology' ||
             colName.startsWith('go_');
    });
    
    if (goColumn) {
      console.log(`ORA: Setting default column to GO terms: ${goColumn.column_name}`);
      visualizationStore.oraColumnName = goColumn.column_name;
    }
  }
  
  // Setup resize observer for responsive plot sizing
  if (dotplotContainer.value) {
    resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      
      const newWidth = entry.contentRect.width;
      
      // Only redraw if width changed significantly (>5px) to avoid loops
      if (Math.abs(newWidth - lastContainerWidth) > 5) {
        lastContainerWidth = newWidth;
        
        // Debounce resize events
        if (resizeTimeout) clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
          if (!loading.value && renderReady.value && pValueEntries.value.length > 0) {
            drawDotPlot();
          }
        }, 150);
      }
    });
    resizeObserver.observe(dotplotContainer.value);
  }
});

onUnmounted(() => {
  window.removeEventListener("resize", handleWindowResize);
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (resizeTimeout) {
    clearTimeout(resizeTimeout);
    resizeTimeout = null;
  }
  // Drop our digest from the assistant context so stale results don't
  // leak into other views.
  assistantStore.setAnalysisContext(`ora:${props.tableName}`, null);
});
</script>
