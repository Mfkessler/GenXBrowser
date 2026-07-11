<template>
  <main class="px-2">
    <!-- Page title -->
    <div class="mb-4 mt-1 text-center relative">
      <h1 class="text-xl font-bold tracking-tight text-gray-800">Gen<span class="text-primary-500">X</span>Browser</h1>
    </div>

    <!-- Catalog Label -->
    <div class="mt-6 mb-4 max-w-5xl mx-auto" v-if="catalog.length > 0">
      <h2 class="text-gray-600 font-semibold text-base mb-3">
        Datasets
      </h2>
    </div>

    <!-- Catalog Header -->
    <div class="flex justify-between items-center mb-3 max-w-5xl mx-auto">
      <div class="text-sm font-medium">
        <span v-if="catalogStore.selectedCount > 0" class="text-primary-700">
          {{ catalogStore.selectedCount }} of {{ catalog.length }} dataset{{ catalog.length !== 1 ? 's' : '' }} selected
        </span>
        <span v-else class="text-gray-400 italic">
          Select one or more datasets, then choose an analysis below.
        </span>
      </div>

      <div class="flex items-center gap-2">
        <button
          v-if="catalog.length > 0"
          class="text-xs font-medium px-3 py-1.5 rounded-md border-1 border-primary-500 text-primary-500 hover:bg-primary-50 cursor-pointer transition-colors"
          @click="toggleSelectAll"
        >
          {{ allSelected ? 'Deselect All' : 'Select All' }}
        </button>
      </div>
    </div>

    <!-- Dataset Grid -->
    <div ref="datasetGridRef" class="dashboard-card-grid">
      <CatalogEntry
        v-for="entry in catalog"
        :key="entry.table_name"
        :tableName="entry.table_name"
        :data-points="entry.count"
        :description="entry.description"
        :tags="entry.tags"
        :photo="entry.photo"
        :default-trait-count="entry._default_trait_count"
        :selected="catalogStore.isSelected(entry.table_name)"
        @toggle-select="catalogStore.toggleSelection($event)"
        @update:filtered-count="onFilteredCountUpdate"
        @inspect-metadata="openOverlay('metadata', entry)"
        @inspect-data="openOverlay('data', entry)"
      />
    </div>

    <!-- ─── Analysis Section ─────────────────────────────────────── -->
    <div class="mt-6 mb-4 max-w-5xl mx-auto" v-if="catalog.length > 0">
      <h2 class="text-gray-600 font-semibold text-base mb-3">
        Analysis
      </h2>

      <div class="dashboard-card-grid">
        <AnalysisCard
          :style="analysisCardStyle"
          type="heatmap"
          :enabled="heatmapState.enabled"
          :disabled-reason="heatmapState.reason"
          :selected-count="heatmapState.eligibleCount"
          :selected-table-names="heatmapState.eligibleTableNames"
        />
        <AnalysisCard
          :style="analysisCardStyle"
          type="ora"
          :enabled="oraState.enabled"
          :disabled-reason="oraState.reason"
          :selected-count="oraState.eligibleCount"
          :selected-table-names="oraState.eligibleTableNames"
        />
        <AnalysisCard
          :style="analysisCardStyle"
          type="compare"
          :enabled="compareState.enabled"
          :disabled-reason="compareState.reason"
          :selected-count="compareState.eligibleCount"
          :selected-table-names="compareState.eligibleTableNames"
        />
        <AnalysisCard
          :style="analysisCardStyle"
          type="phylo"
          :enabled="phyloState.enabled"
          :disabled-reason="phyloState.reason"
          :selected-count="phyloState.eligibleCount"
          :selected-table-names="phyloState.eligibleTableNames"
        />
      </div>
    </div>

    <!-- Empty state -->
    <div
      v-if="catalog.length === 0 && !isLoading"
      class="flex flex-col items-center justify-center py-16 text-gray-400"
    >
      <svg class="w-16 h-16 mb-4" fill="none" stroke="currentColor" stroke-width="1" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round"
          d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p class="text-lg font-medium mb-1">No datasets found</p>
      <p class="text-sm">No datasets match your current filters.</p>
      <button
        v-if="[...filtersStore.tags].length > 0"
        class="mt-3 text-sm text-primary-500 hover:text-primary-700 underline cursor-pointer"
        @click="filtersStore.tags.clear()"
      >
        Clear tag filters
      </button>
    </div>

    <!-- Overlays (unchanged) -->
    <OverlayTable
      v-if="showOverlay && overlayType === 'metadata'"
      :title="overlayTitle"
      :endpoint="overlayEndpoint"
      :filters="overlayFilters"
      :type="overlayType"
      @close="showOverlay = false"
    />
    <DataManagerModal
      v-if="showOverlay && overlayType === 'data'"
      :tableName="currentTableName"
      :title="overlayTitle"
      @close="showOverlay = false"
    />
  </main>
</template>
<script setup lang="ts">
import axios from "axios";
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import AnalysisCard from "@/components/AnalysisCard.vue";
import CatalogEntry from "@/components/CatalogEntry.vue";
import DataManagerModal from "@/components/DataManagerModal.vue";
import { type CatalogMeta } from "@/shared/CatalogMeta";
import { API_BASE_URL } from "@/shared/Config";
import { useFiltersStore } from "@/stores/filters";
import { useCatalogStore } from "@/stores/catalog";
import { type OverlayConfig } from "@/shared/OverlayConfig";
import OverlayTable from "@/components/OverlayTable.vue";
import { jsonToTsv, beautifyLabel } from "@/shared/utils";
import { fetchAnalysisLimits } from "@/shared/landingApi";
import { getMirroredCardStyle, readCardBoxSize, type CardBoxSize } from "@/shared/dashboardCardSizing";

type AnalysisLimitView = "heatmap" | "phylo" | "ora" | "compare";

const OVERLAY_CONFIG: Record<"metadata" | "data", OverlayConfig> = {
  metadata: {
    title: (entry) => `${entry.table_name} Metadata`,
    endpoint: `${API_BASE_URL}/api/data`,
    filters: (entry) => ({
      table_name: entry.table_name + "_meta",
      columns: [],
    }),
  },
  data: {
    title: (entry) => `${entry.table_name} Data`,
    endpoint: `${API_BASE_URL}/api/data`,
    filters: (entry) => ({ table_name: entry.table_name, columns: [] }),
  },
};

const filtersStore = useFiltersStore();
const catalogStore = useCatalogStore();

const catalog = ref<Array<CatalogMeta>>([]);
const isLoading = ref(false);
const analysisLimits = ref<Record<string, { max_rows: number | null }>>({});
const datasetGridRef = ref<HTMLDivElement | null>(null);
const datasetCardSize = ref<CardBoxSize | null>(null);

const showOverlay = ref(false);
const overlayTitle = ref("");
const overlayEndpoint = ref("");
const overlayFilters = ref<Record<string, string | string[]>>({});
const overlayType = ref<"data" | "metadata">("data");
const currentTableName = ref("");
let datasetCardResizeObserver: ResizeObserver | null = null;

const analysisCardStyle = computed(() => getMirroredCardStyle(datasetCardSize.value));

function disconnectDatasetCardObserver() {
  datasetCardResizeObserver?.disconnect();
  datasetCardResizeObserver = null;
}

function updateDatasetCardSize() {
  const datasetCard = datasetGridRef.value?.querySelector<HTMLElement>('[data-card-role="dataset"]');
  if (!datasetCard) {
    datasetCardSize.value = null;
    return;
  }

  datasetCardSize.value = readCardBoxSize(datasetCard.getBoundingClientRect());
}

function observeDatasetCard() {
  disconnectDatasetCardObserver();
  updateDatasetCardSize();

  const datasetCard = datasetGridRef.value?.querySelector<HTMLElement>('[data-card-role="dataset"]');
  if (!datasetCard || typeof ResizeObserver === "undefined") {
    return;
  }

  datasetCardResizeObserver = new ResizeObserver(() => {
    updateDatasetCardSize();
  });
  datasetCardResizeObserver.observe(datasetCard);
}

// ── Select All / Deselect All ─────────────────────────────────────
const allSelected = computed(
  () =>
    catalog.value.length > 0 &&
    catalog.value.every((e) => catalogStore.isSelected(e.table_name)),
);

function toggleSelectAll() {
  if (allSelected.value) {
    catalogStore.deselectAll();
  } else {
    catalogStore.selectAll(catalog.value.map((e) => e.table_name));
  }
}

// ── Filtered-count callback from CatalogEntry ─────────────────────
function onFilteredCountUpdate(tableName: string, count: number | null) {
  catalogStore.setFilteredCount(tableName, count);
}

// ── Analysis enable/disable logic (independent limits) ────────────

/** Get the effective count for a table, falling back to the catalog total */
function effectiveCount(tableName: string): number {
  const entry = catalog.value.find((e) => e.table_name === tableName);
  return catalogStore.getEffectiveCount(
    tableName,
    entry?.count ?? 0,
  );
}

function computeAnalysisState(limit: number | null): { enabled: boolean; reason: string | null; eligibleCount: number; eligibleTableNames: string[] } {
  const selected = catalogStore.selectedTableNamesArray;
  if (selected.length === 0) {
    return { enabled: false, reason: "Select at least one dataset to start this analysis.", eligibleCount: 0, eligibleTableNames: [] };
  }

  // Filter out datasets with count = 0
  const nonEmpty = selected.filter((t) => effectiveCount(t) > 0);

  // Filter out datasets exceeding the limit
  const eligible = limit !== null
    ? nonEmpty.filter((t) => effectiveCount(t) <= limit)
    : nonEmpty;

  if (eligible.length === 0) {
    const reasons: string[] = [];
    const zeroCount = selected.filter((t) => effectiveCount(t) === 0);
    if (zeroCount.length > 0) {
      reasons.push(`${zeroCount.map((t) => beautifyLabel(t)).join(", ")} ${zeroCount.length === 1 ? 'has' : 'have'} 0 matching transcripts`);
    }
    if (limit !== null) {
      const overLimit = nonEmpty.filter((t) => effectiveCount(t) > limit);
      if (overLimit.length > 0) {
        reasons.push(`${overLimit.map((t) => beautifyLabel(t)).join(", ")} ${overLimit.length === 1 ? 'exceeds' : 'exceed'} the ${limit.toLocaleString()} transcript limit`);
      }
    }
    return {
      enabled: false,
      reason: reasons.join(". ") + ". Apply sidebar filters to adjust.",
      eligibleCount: 0,
      eligibleTableNames: [],
    };
  }

  return { enabled: true, reason: null, eligibleCount: eligible.length, eligibleTableNames: eligible };
}

function analysisLimit(view: AnalysisLimitView): number | null {
  return analysisLimits.value[view]?.max_rows ?? null;
}

const heatmapState = computed(() => computeAnalysisState(analysisLimit("heatmap")));
const phyloState = computed(() => computeAnalysisState(analysisLimit("phylo")));
const oraState = computed(() => computeAnalysisState(analysisLimit("ora")));
const compareState = computed(() => computeAnalysisState(analysisLimit("compare")));

// ── Shared orthogroup fetching for Compare & Phylo ────────────────
// ── Overlay / download (unchanged logic) ──────────────────────────

function openOverlay(type: "metadata" | "data", entry: CatalogMeta) {
  const config = OVERLAY_CONFIG[type];
  showOverlay.value = true;
  overlayTitle.value = config.title(entry);
  overlayEndpoint.value = config.endpoint;
  overlayFilters.value = config.filters(entry);
  overlayType.value = type;
  currentTableName.value = entry.table_name;
}

const fetchTables = async () => {
  isLoading.value = true;
  try {
    const tagsParam = [...filtersStore.tags].join(",");
    const response = await axios.get<CatalogMeta[]>(
      `${API_BASE_URL}/api/tables`,
      { params: { tags: tagsParam } },
    );

    catalog.value = response.data.map((entry: CatalogMeta) => ({
      ...entry,
      table_name: entry.table_name.replace(/^.*"\s*([^"]+)\s*".*$/, "$1"),
    }));

    // Update filterStore
    filtersStore.setTableNames(
      response.data.map((entry: CatalogMeta) => entry.table_name),
    );

    // Prune selection to only tables that still exist
    const validNames = new Set(catalog.value.map((e) => e.table_name));
    const currentSelection = catalogStore.selectedTableNamesArray;
    const pruned = currentSelection.filter((n) => validNames.has(n));
    if (pruned.length !== currentSelection.length) {
      catalogStore.selectAll(pruned);
    }
  } catch (e) {
    console.error("Error occurred fetching tables: ", e);
  } finally {
    isLoading.value = false;
  }
};

function downloadTsvFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/tab-separated-values" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => {
    URL.revokeObjectURL(url);
    a.remove();
  }, 0);
}

async function downloadCatalogEntry(entry: CatalogMeta) {
  try {
    const entryFilters = filtersStore.getMergedFilters(entry.table_name);
    const dataResp = await axios.post(`${API_BASE_URL}/api/data`, {
      table_name: entry.table_name,
      filters: entryFilters,
      filter_chain: filtersStore.buildFilterChainPayload(entryFilters, entry.table_name),
    });
    const data = Array.isArray(dataResp.data) ? dataResp.data : (dataResp.data?.data ?? []);

    const metaResp = await axios.post(`${API_BASE_URL}/api/data`, {
      table_name: entry.table_name + "_meta",
    });
    const meta = Array.isArray(metaResp.data) ? metaResp.data : (metaResp.data?.data ?? []);

    const prefix = entry.table_name.replace(/[^a-zA-Z0-9_\-]/g, "_");
    const dataTsv = jsonToTsv(data);
    const metaTsv = jsonToTsv(meta);

    downloadTsvFile(`${prefix}_data.tsv`, dataTsv);
    setTimeout(() => {
      downloadTsvFile(`${prefix}_metadata.tsv`, metaTsv);
    }, 400);
  } catch (err) {
    console.error("Error downloading data or metadata:", err);
  }
}

watch(
  () => filtersStore.tags,
  () => { fetchTables(); },
  { deep: true },
);

watch(
  () => catalog.value.map((entry) => entry.table_name).join("|"),
  async () => {
    await nextTick();
    observeDatasetCard();
  },
  { flush: "post" },
);

onMounted(() => {
  fetchAnalysisLimits()
    .then((limits) => {
      analysisLimits.value = limits || {};
    })
    .catch(() => {
      analysisLimits.value = {};
    });
  fetchTables();
  nextTick(() => {
    observeDatasetCard();
  });
});

onBeforeUnmount(() => {
  disconnectDatasetCardObserver();
});
</script>

<style scoped>
.dashboard-card-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 1rem;
  max-width: 64rem;
  margin-left: auto;
  margin-right: auto;
  align-items: stretch;
}

@media (min-width: 640px) {
  .dashboard-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
