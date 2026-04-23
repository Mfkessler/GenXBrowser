<template>
  <div class="w-full max-w-7xl mx-auto p-2 md:p-4">
    <header class="mb-6">
      <div class="flex items-start justify-between flex-wrap gap-4">
        <div>
          <h1 class="text-3xl md:text-4xl font-bold text-gray-800">
            {{ overview?.project.name || "GenXBrowser" }}
          </h1>
          <p v-if="overview?.project.description" class="mt-1 text-gray-600">
            {{ overview.project.description }}
          </p>
          <p v-if="overview?.project.version" class="mt-1 text-xs text-gray-400">
            Version {{ overview.project.version }}
          </p>
        </div>
        <div class="flex gap-2 flex-wrap">
          <button
            v-if="assistantStore.enabled"
            class="bg-gradient-to-r from-accent1-500 to-accent2-500 hover:from-accent1-700 hover:to-accent2-700 text-white font-semibold px-4 py-2 rounded-lg text-sm cursor-pointer inline-flex items-center gap-2 shadow-sm"
            @click="assistantStore.open = true"
          >
            <AiSparkleIcon class="w-4 h-4" />
            Ask {{ assistantStore.displayName }}
          </button>
        </div>
      </div>
    </header>

    <div v-if="loading" class="text-gray-500 py-12 text-center">Loading overview…</div>
    <div v-else-if="error" class="bg-red-50 border border-red-200 text-red-700 rounded-lg p-4">
      {{ error }}
    </div>

    <template v-else-if="overview">
      <div v-if="!overview.species.length" class="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-4">
        No datasets loaded. Visit
        <RouterLink to="/admin" class="underline font-semibold">Admin → Data Paths</RouterLink>
        to configure <code>H5AD_DATA_DIR</code>.
      </div>

      <template v-else>
        <section class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          <KpiCard label="Species" :value="overview.global.n_species" />
          <KpiCard label="Samples" :value="overview.global.n_samples" />
          <KpiCard label="Genes" :value="overview.global.n_genes" />
          <KpiCard
            v-if="overview.global.has_orthogroups"
            label="Orthogroups"
            :value="overview.global.orthogroup_count"
          />
          <KpiCard
            v-if="overview.global.gene_tree_count > 0"
            label="Gene Trees"
            :value="overview.global.gene_tree_count"
          />
          <KpiCard
            v-if="overview.global.tf_total > 0"
            label="Transcription Factors"
            :value="overview.global.tf_total"
          />
        </section>

        <Section title="Loaded Datasets" subtitle="Per-species summary of the currently loaded H5ADs.">
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div
              v-for="sp in overview.species"
              :key="sp.code"
              class="bg-white border border-gray-200 rounded-xl p-4 flex flex-col gap-2"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-xs text-gray-500 font-mono">{{ sp.code }}</span>
                <div class="flex flex-wrap gap-1 justify-end">
                  <span
                    v-for="t in (sp.tags || []).slice(0, 3)"
                    :key="t"
                    class="text-[10px] uppercase tracking-wide bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full"
                  >{{ t }}</span>
                </div>
              </div>
              <h3 class="font-semibold text-gray-800 italic text-base" :title="sp.full_name">
                {{ sp.full_name }}
              </h3>
              <dl class="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <dt class="text-gray-500 text-xs">Samples</dt>
                  <dd class="font-semibold">{{ fmt(sp.n_samples) }}</dd>
                </div>
                <div>
                  <dt class="text-gray-500 text-xs">Genes</dt>
                  <dd class="font-semibold">{{ fmt(sp.n_genes) }}</dd>
                </div>
              </dl>
              <div class="flex flex-wrap gap-1">
                <span
                  v-for="layer in sp.layers"
                  :key="layer"
                  class="text-[10px] font-mono bg-primary-100 text-primary-900 border border-primary-300 px-1.5 py-0.5 rounded"
                >{{ layer }}</span>
              </div>
            </div>
          </div>
        </Section>

        <Section
          v-if="tissueChartData"
          title="Tissue distribution"
          subtitle="Sample counts per tissue across loaded species."
        >
          <PlotlyChart :data="tissueChartData.data" :layout="tissueChartData.layout" :height="440" />
        </Section>

        <Section
          v-if="coverageMatrix"
          title="Annotation coverage"
          subtitle="Fraction of entries with non-null values for known annotation fields."
        >
          <PlotlyChart
            :data="coverageMatrix.data"
            :layout="coverageMatrix.layout"
            :height="Math.max(260, 70 + overview.species.length * 50)"
          />
        </Section>

        <Section title="Expression layers" subtitle="Available normalisations per dataset.">
          <div class="overflow-x-auto">
            <table class="min-w-full text-sm border-collapse">
              <thead>
                <tr class="text-left text-gray-500">
                  <th class="px-3 py-2 border-b border-gray-200">Species</th>
                  <th
                    v-for="layer in allLayers"
                    :key="layer"
                    class="px-3 py-2 border-b border-gray-200 text-center font-mono text-xs"
                  >{{ layer }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="sp in overview.species" :key="sp.code" class="hover:bg-gray-50">
                  <td class="px-3 py-2 border-b border-gray-100 font-semibold italic">{{ sp.full_name }}</td>
                  <td
                    v-for="layer in allLayers"
                    :key="layer"
                    class="px-3 py-2 border-b border-gray-100 text-center"
                  >
                    <span v-if="sp.layers.includes(layer)" class="text-primary-700">✓</span>
                    <span v-else class="text-gray-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <Section
          v-if="qcRows.length > 0"
          title="QC metrics"
          subtitle="Sample-level quality control metrics extracted from the loaded H5ADs."
        >
          <div class="overflow-x-auto">
            <table class="min-w-full text-sm border-collapse">
              <thead>
                <tr class="text-left text-gray-500">
                  <th class="px-3 py-2 border-b border-gray-200">Species</th>
                  <th class="px-3 py-2 border-b border-gray-200">Metric</th>
                  <th class="px-3 py-2 border-b border-gray-200 text-right">Min</th>
                  <th class="px-3 py-2 border-b border-gray-200 text-right">Median</th>
                  <th class="px-3 py-2 border-b border-gray-200 text-right">Mean</th>
                  <th class="px-3 py-2 border-b border-gray-200 text-right">Max</th>
                  <th class="px-3 py-2 border-b border-gray-200 text-right">n</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in qcRows" :key="row.key" class="hover:bg-gray-50">
                  <td class="px-3 py-2 border-b border-gray-100 italic">{{ row.fullName }}</td>
                  <td class="px-3 py-2 border-b border-gray-100">{{ row.metric }}</td>
                  <td class="px-3 py-2 border-b border-gray-100 text-right">{{ fmtNum(row.stat.min) }}</td>
                  <td class="px-3 py-2 border-b border-gray-100 text-right">{{ fmtNum(row.stat.median) }}</td>
                  <td class="px-3 py-2 border-b border-gray-100 text-right">{{ fmtNum(row.stat.mean) }}</td>
                  <td class="px-3 py-2 border-b border-gray-100 text-right">{{ fmtNum(row.stat.max) }}</td>
                  <td class="px-3 py-2 border-b border-gray-100 text-right">{{ row.stat.count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Section>

        <Section
          v-if="tfChartData"
          title="Transcription factor families"
          subtitle="Top TF families across species where a TF annotation is present."
        >
          <PlotlyChart :data="tfChartData.data" :layout="tfChartData.layout" :height="440" />
        </Section>

        <Section
          v-if="overview.global.has_orthogroups"
          title="Orthogroups"
          subtitle="Cross-species orthology assignments discovered in the loaded data."
        >
          <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <KpiCard label="Total orthogroups" :value="overview.global.orthogroup_count" />
            <KpiCard
              v-for="sp in speciesWithOrtho"
              :key="sp.code"
              :label="`${sp.full_name} — genes with OG`"
              :value="sp.derived.genes_with_orthogroup ?? 0"
            />
          </div>
        </Section>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, h, defineComponent, onBeforeUnmount, watch } from "vue";
import { RouterLink } from "vue-router";
import { fetchOverview, fetchOverviewMtime, type OverviewPayload } from "@/shared/landingApi";
import { useAssistantStore } from "@/stores/assistant";
import AiSparkleIcon from "@/components/icons/AiSparkleIcon.vue";

const assistantStore = useAssistantStore();

const loading = ref(true);
const error = ref("");
const overview = ref<OverviewPayload | null>(null);

const CACHE_KEY = "genx.overview.v2";

const KpiCard = defineComponent({
  props: { label: { type: String, required: true }, value: { type: [Number, String], required: true } },
  setup(props) {
    return () =>
      h("div", { class: "bg-white border border-gray-200 rounded-xl p-4" }, [
        h("div", { class: "text-xs uppercase tracking-wide text-gray-400" }, props.label),
        h(
          "div",
          { class: "mt-1 text-2xl font-bold text-gray-800" },
          typeof props.value === "number" ? fmt(props.value) : String(props.value),
        ),
      ]);
  },
});

const Section = defineComponent({
  props: { title: String, subtitle: String },
  setup(props, { slots }) {
    return () =>
      h("section", { class: "mb-8" }, [
        h("div", { class: "mb-3" }, [
          h("h2", { class: "text-lg font-semibold text-gray-800" }, props.title),
          props.subtitle ? h("p", { class: "text-sm text-gray-500" }, props.subtitle) : null,
        ]),
        slots.default ? slots.default() : null,
      ]);
  },
});

const PlotlyChart = defineComponent({
  name: "PlotlyChart",
  props: {
    data: { type: Array, required: true },
    layout: { type: Object, default: () => ({}) },
    height: { type: Number, default: 360 },
  },
  setup(props) {
    const el = ref<HTMLDivElement | null>(null);
    let plotlyRef: typeof import("plotly.js-dist-min") | null = null;

    async function draw() {
      if (!el.value) return;
      if (!plotlyRef) plotlyRef = await import("plotly.js-dist-min");
      const base = {
        autosize: true,
        margin: { l: 70, r: 30, t: 60, b: 140 },
        legend: {
          orientation: "h" as const,
          yanchor: "bottom" as const,
          y: 1.02,
          xanchor: "right" as const,
          x: 1,
          bgcolor: "rgba(255,255,255,0)",
        },
        hoverlabel: { namelength: -1 },
      };
      const userLayout = props.layout as Record<string, unknown>;
      const merged = {
        ...base,
        ...userLayout,
        legend: { ...base.legend, ...((userLayout.legend as object) || {}) },
        margin: { ...base.margin, ...((userLayout.margin as object) || {}) },
      };
      await plotlyRef.react(
        el.value,
        props.data as unknown as Parameters<typeof plotlyRef.react>[1],
        merged as unknown as Parameters<typeof plotlyRef.react>[2],
        { responsive: true, displaylogo: false },
      );
    }

    watch(() => [props.data, props.layout], draw, { deep: true });
    onMounted(draw);
    onBeforeUnmount(async () => {
      if (plotlyRef && el.value) plotlyRef.purge(el.value);
    });
    return () => h("div", { ref: el, style: { width: "100%", height: `${props.height}px` } });
  },
});

async function loadOverview(): Promise<void> {
  try {
    const { mtime } = await fetchOverviewMtime();
    const cachedRaw = sessionStorage.getItem(CACHE_KEY);
    if (cachedRaw) {
      try {
        const cached = JSON.parse(cachedRaw) as OverviewPayload & { _cachedMtime?: number };
        if (cached && cached._cachedMtime === mtime) {
          overview.value = cached;
          return;
        }
      } catch { /* ignore */ }
    }
    const fresh = await fetchOverview();
    try {
      sessionStorage.setItem(CACHE_KEY, JSON.stringify({ ...fresh, _cachedMtime: mtime }));
    } catch { /* quota */ }
    overview.value = fresh;
  } catch {
    overview.value = await fetchOverview();
  }
}

onMounted(async () => {
  await assistantStore.loadFeatures();
  try {
    await loadOverview();
  } catch (e) {
    error.value = (e as Error).message || "Failed to load overview";
  } finally {
    loading.value = false;
  }
});

function fmt(n: number): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return n.toLocaleString();
}
function fmtNum(n: number): string {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1000) return n.toFixed(0);
  if (abs >= 1) return n.toFixed(2);
  return n.toFixed(3);
}

const allLayers = computed(() => {
  if (!overview.value) return [] as string[];
  const s = new Set<string>();
  for (const sp of overview.value.species) sp.layers.forEach((l) => s.add(l));
  return Array.from(s);
});

const speciesWithOrtho = computed(() =>
  (overview.value?.species || []).filter((s) => (s.derived.orthogroup_count ?? 0) > 0),
);

const tissueChartData = computed(() => {
  if (!overview.value) return null;
  const union = overview.value.global.tissue_union;
  if (!union.length) return null;
  const tissues = union.map((u) => u.tissue);
  const codeToName: Record<string, string> = {};
  for (const sp of overview.value.species) codeToName[sp.code] = sp.full_name || sp.code;
  const codes = overview.value.species.map((s) => s.code);
  const traces = codes.map((code) => ({
    type: "bar" as const,
    name: codeToName[code],
    x: tissues,
    y: union.map((u) => u.counts[code] || 0),
  }));
  return {
    data: traces,
    layout: {
      barmode: "stack" as const,
      xaxis: { title: "Tissue", tickangle: -35, automargin: true },
      yaxis: { title: "Sample count", automargin: true },
    },
  };
});

const coverageMatrix = computed(() => {
  if (!overview.value) return null;
  const species = overview.value.species;
  if (!species.length) return null;
  const fields = new Set<string>();
  species.forEach((s) => {
    Object.keys(s.annotation_coverage.var || {}).forEach((k) => fields.add(`var.${k}`));
    Object.keys(s.annotation_coverage.obs || {}).forEach((k) => fields.add(`obs.${k}`));
  });
  const fieldArr = Array.from(fields).sort();
  if (!fieldArr.length) return null;
  const z = species.map((s) =>
    fieldArr.map((f) => {
      const [ns, name] = f.split(".");
      const bucket = ns === "var" ? s.annotation_coverage.var : s.annotation_coverage.obs;
      return bucket?.[name] ?? 0;
    }),
  );
  return {
    data: [
      {
        type: "heatmap" as const,
        x: fieldArr,
        y: species.map((s) => s.full_name || s.code),
        z,
        zmin: 0,
        zmax: 1,
        colorscale: "Viridis" as const,
        colorbar: { title: "non-null" },
      },
    ],
    layout: {
      xaxis: { title: "Annotation field", tickangle: -35, automargin: true },
      yaxis: { title: "Species", automargin: true },
      margin: { l: 220, r: 30, t: 40, b: 160 },
    },
  };
});

const qcRows = computed(() => {
  if (!overview.value) return [] as Array<{ key: string; code: string; fullName: string; metric: string; stat: { min: number; max: number; mean: number; median: number; count: number } }>;
  const rows: Array<{ key: string; code: string; fullName: string; metric: string; stat: { min: number; max: number; mean: number; median: number; count: number } }> = [];
  for (const sp of overview.value.species) {
    const qc = sp.derived.qc_metrics;
    if (!qc) continue;
    for (const [metric, stat] of Object.entries(qc)) {
      rows.push({ key: `${sp.code}:${metric}`, code: sp.code, fullName: sp.full_name || sp.code, metric, stat });
    }
  }
  return rows;
});

const tfChartData = computed(() => {
  if (!overview.value) return null;
  const families = new Map<string, Record<string, number>>();
  let any = false;
  for (const sp of overview.value.species) {
    const fams = sp.derived.tf_families;
    if (!fams || !fams.length) continue;
    any = true;
    for (const f of fams) {
      const row = families.get(f.value) || {};
      row[sp.code] = (row[sp.code] || 0) + f.count;
      families.set(f.value, row);
    }
  }
  if (!any) return null;
  const famArr = Array.from(families.entries())
    .map(([name, counts]) => ({ name, counts, total: Object.values(counts).reduce((a, b) => a + b, 0) }))
    .sort((a, b) => b.total - a.total)
    .slice(0, 15);
  const codeToName: Record<string, string> = {};
  for (const sp of overview.value.species) codeToName[sp.code] = sp.full_name || sp.code;
  const codes = overview.value.species.map((s) => s.code);
  const traces = codes.map((code) => ({
    type: "bar" as const,
    name: codeToName[code],
    x: famArr.map((f) => f.name),
    y: famArr.map((f) => f.counts[code] || 0),
  }));
  return {
    data: traces,
    layout: {
      barmode: "stack" as const,
      xaxis: { title: "TF family", tickangle: -30, automargin: true },
      yaxis: { title: "Gene count", automargin: true },
    },
  };
});
</script>
