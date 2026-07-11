/**
 * Composable that probes each loaded dataset for matching samples / rows
 * after the current sample- and gene-filters and exposes the subset of
 * tables that still have data.
 *
 * Used by the visualization views (Heatmap, Compare, ORA, Phylo) to hide
 * datasets that completely fall through a sample filter — e.g. setting
 * `tissue = flower` should hide a dataset that has zero `flower` samples
 * instead of leaving it as an unfiltered, misleading panel.
 */
import { computed, onUnmounted, ref, watch, type Ref } from "vue";
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { useFilterSeparation } from "@/shared/useFilterSeparation";
import { useFiltersStore } from "@/stores/filters";

export interface EmptyProbeOptions {
  /** When true (default), tables with `count == 0` (no var-row match) are
   *  also hidden, mirroring the behaviour of the backend's empty-table
   *  guard for assistant-built deeplinks. */
  hideOnEmptyVar?: boolean;
}

export function useDatasetEmptinessFilter(
  tableNames: Ref<string[]>,
  options: EmptyProbeOptions = {},
) {
  const { sampleFilters, geneFilters, filterChainVersion, getFilterChainPayload } = useFilterSeparation();
  const filtersStore = useFiltersStore();
  const hideOnEmptyVar = options.hideOnEmptyVar ?? true;

  // Per-table probe results. `null` = pending / unknown (treat as visible
  // until the probe answers, to avoid flicker on first paint).
  const sampleCounts = ref<Record<string, number | null>>({});
  const varCounts = ref<Record<string, number | null>>({});
  const probing = ref(false);
  let activeProbeController: AbortController | null = null;

  /** Tables that should remain rendered: have `sample_count > 0` (or no
   *  sample filter) AND, if `hideOnEmptyVar` is set, `count > 0` too. */
  const visibleTableNames = computed<string[]>(() => {
    return tableNames.value.filter((tn) => {
      const sc = sampleCounts.value[tn];
      if (sc !== null && sc !== undefined && sc <= 0) return false;
      if (hideOnEmptyVar) {
        const vc = varCounts.value[tn];
        if (vc !== null && vc !== undefined && vc <= 0) return false;
      }
      return true;
    });
  });

  /** Tables that were hidden by the current filter set, with the reason. */
  const hiddenTableNames = computed<Array<{ table: string; reason: string }>>(() => {
    const out: Array<{ table: string; reason: string }> = [];
    for (const tn of tableNames.value) {
      const sc = sampleCounts.value[tn];
      const vc = varCounts.value[tn];
      if (sc !== null && sc !== undefined && sc <= 0) {
        out.push({ table: tn, reason: "no samples match the current filter" });
      } else if (hideOnEmptyVar && vc !== null && vc !== undefined && vc <= 0) {
        out.push({ table: tn, reason: "no transcripts match the current filter" });
      }
    }
    return out;
  });

  let probeId = 0;
  function cancelProbes() {
    probeId += 1;
    activeProbeController?.abort();
    activeProbeController = null;
    probing.value = false;
  }

  async function refreshProbes() {
    const myId = ++probeId;
    activeProbeController?.abort();
    const controller = new AbortController();
    activeProbeController = controller;
    probing.value = true;
    const tables = [...tableNames.value];
    const sampleFilterPayload = { ...sampleFilters.value };
    const geneFilterPayload = { ...geneFilters.value };

    const results = await Promise.all(
      tables.map(async (tn) => {
        try {
          const disabled = filtersStore.getDisabledColumnsForDataset(tn);
          const scopedGeneFilters = Object.fromEntries(
            Object.entries(geneFilterPayload).filter(([key]) => !disabled[key]),
          );
          for (const [key, custom] of Object.entries(filtersStore.getCustomFiltersForDataset(tn))) {
            if (!disabled[key]) scopedGeneFilters[key] = custom.filter;
          }
          const { data } = await axios.post<{
            count: number;
            sample_count: number;
            total_samples: number;
          }>(`${API_BASE_URL}/api/count`, {
            table_name: tn,
            filters: scopedGeneFilters,
            filter_chain: getFilterChainPayload(scopedGeneFilters, tn),
            sample_filters: sampleFilterPayload,
          }, { signal: controller.signal });
          return { tn, count: data.count ?? 0, sample_count: data.sample_count ?? 0 };
        } catch (error) {
          if (axios.isCancel(error) || (axios.isAxiosError(error) && error.code === "ERR_CANCELED")) {
            return { tn, count: null as number | null, sample_count: null as number | null };
          }
          // On error we keep the dataset visible (treat probe as unknown).
          return { tn, count: null as number | null, sample_count: null as number | null };
        }
      }),
    );

    // Drop stale results when filters / tables change mid-flight.
    if (myId !== probeId || controller.signal.aborted) return;

    const nextSamples: Record<string, number | null> = {};
    const nextVars: Record<string, number | null> = {};
    for (const r of results) {
      nextSamples[r.tn] = r.sample_count;
      nextVars[r.tn] = r.count;
    }
    sampleCounts.value = nextSamples;
    varCounts.value = nextVars;
    probing.value = false;
    if (activeProbeController === controller) {
      activeProbeController = null;
    }
  }

  watch(
    [tableNames, sampleFilters, geneFilters, filterChainVersion],
    () => {
      refreshProbes();
    },
    { deep: true, immediate: true },
  );

  onUnmounted(cancelProbes);

  return {
    visibleTableNames,
    hiddenTableNames,
    sampleCounts,
    varCounts,
    probing,
    refreshProbes,
    cancelProbes,
  };
}
