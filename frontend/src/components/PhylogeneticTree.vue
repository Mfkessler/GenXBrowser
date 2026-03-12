<template>
  <main>

    <div v-if="loading" class="flex-grow relative h-[90vh] w-full">
      <LoadingOverlay v-if="loading"/>
    </div>

    <div v-if="!loading && newickstr !== null" class="flex-grow relative h-[90vh] w-full">
      <!-- Phylogenetic Tree Title + Buttons in same row -->
      <div v-if="commonOGs_array.length > 0" class="flex flex-wrap items-center gap-3 mb-1 p-3 bg-gray-50 rounded-lg border border-gray-200">
        <!-- Orthogroup Selector - same styling as Compare view -->
        <div class="flex-grow min-w-48">
          <DropdownMenu
            placeholder="Select orthogroup"
            v-model="selectedOrthogroup"
            :options="commonOGs_options"
          />
        </div>

        <!-- Action Buttons -->
        <div class="flex gap-2 ml-auto">
          <button
            aria-label="Share the phylogenetic tree"
            @click="showShareOverlay = true"
            class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white transition"
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
            class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900 transition"
            @click="emit('openSettingsOverlay')"
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
              <circle cx="12" cy="12" r="3"/>
              <path
                d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"
              />
            </svg>
          </button>
        </div>
      </div>
      <div
        ref="phylotreeContainer"
        id="phylotreeContainer"
        class="border border-gray-300 rounded-2xl bg-white p-1 pb-32 w-full shadow-sm min-w-0 overflow-y-auto h-[calc(100dvh-3rem)]"
      ></div>
    </div>

    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(phylotreeContainer)"
      @close="showShareOverlay = false"
    />

    <!-- Tooltip Modal for detailed cell info -->
    <TooltipModal
      v-if="selectedRowData"
      :show="showTooltipModal"
      :row-data="selectedRowData"
      :table-name="selectedTableName"
      :column-value="selectedColumnValue"
      :cell-value="selectedCellValue"
      :id-column="config.visualization.id_column"
      :heatmap-cols="heatmapCols"
      @close="closeTooltipModal"
    />

    <div v-if="newickstr===null" class="flex-grow relative h-[90vh] w-full">
      <NoNewickComponent :og="og" :show-full-tree="true" @show-full-tree="loadFullNewickForOG" />
    </div>


  </main>
</template>

<script setup lang="ts">

// Imports
import axios from "axios";
import {storeToRefs} from "pinia";
import {onMounted, ref, computed, toRaw, watch, unref, inject, nextTick} from 'vue'
import {phylotree} from 'phylotree'
import '../assets/phylotree.css' // CSS from phylotree GitHub page https://github.com/veg/phylotree.js/blob/master/phylotree.css (modified)
import * as d3 from "d3";
import {API_BASE_URL} from "@/shared/Config.ts";
import {COLORSCALES} from "@/shared/Colorscales.ts";
import type {MetaFormat} from "@/shared/MetaFormat.ts";
import type {RowType} from "@/shared/RowType.ts";
import {assign} from "lodash-es";
import {useFiltersStore} from "@/stores/filters.ts";
import {useVisualizationStore} from "@/stores/visualization.ts";
import {getExpressionOption} from "@/shared/ExpressionDisplay.ts";
import ShareOverlay from "@/components/ShareOverlay.vue";
import LoadingOverlay from "@/components/LoadingOverlay.vue";
import NoNewickComponent from "@/components/NoNewickComponent.vue";
import TooltipModal from "@/components/TooltipModal.vue";
import DropdownMenu from "@/components/DropdownMenu.vue";
import { getDisplayName, sequenceFields, verboseFields } from "@/shared/metadataDisplayNames";
import { getEntityIdLabel } from "@/shared/dataTypeLabels";
import { buildOrthogroupScopedFilters } from "@/shared/orthogroupFilters";
import { buildPhyloMetricKeys, matchLeafToDataset, resolvePhyloLeafMatch } from "@/shared/phyloLeafMatching";
import type { Config } from "@/shared/Config";
import { hierarchicalCluster } from "@/shared/clustering";
import { useRoute, useRouter } from 'vue-router';

const config = inject("config") as Config;
const phylotreeContainer = ref<HTMLDivElement | null>(null);
const showShareOverlay = ref(false);
const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const {filters} = storeToRefs(filtersStore);
const tableData = ref<Record<string, any[]>>({});

// Router for URL state management
const route = useRoute();
const router = useRouter();
const initialUrlParsing = ref(true);

// Available orthogroups (extracted from newick data)
const commonOGs_array = ref<string[]>([]);

// Tooltip modal state
const showTooltipModal = ref(false);
const selectedRowData = ref<RowType | null>(null);
const selectedTableName = ref("");
const selectedColumnValue = ref("");
const selectedCellValue = ref<string | number>("");
const heatmapCols = ref<string[]>([]);

// Hidden nodes/species tracking - now managed via visualizationStore.phyloTree
// Local refs for species hiding (not persisted, but could be in future)
const hiddenSpecies = ref<Set<string>>(new Set());
// Use store for collapsed nodes (persisted)
const collapsedNodes = computed(() => new Set(visualizationStore.phyloTree.collapsedNodes));

// Zoom behavior reference
let currentZoomBehavior: d3.ZoomBehavior<SVGSVGElement, unknown> | null = null;

const closeTooltipModal = () => {
  showTooltipModal.value = false;
  selectedRowData.value = null;
  selectedTableName.value = "";
  selectedColumnValue.value = "";
  selectedCellValue.value = "";
};

const emit = defineEmits(['openSettingsOverlay', 'update:tableName', 'update:orthogroupOptions']);

const rows = ref<RowType[]>([]);
const columnNames = ref<string[]>([]);
const dataColumnNames = ref<string[]>([]);
const columns = ref<RowType[]>([]);
const newicks = ref<Record<string, string>>({});
const orthogroupCaseMap = ref<Record<string, string>>({});
const newickstr = ref("");
const loading = ref(false);
// Holds the full (unfiltered) Newick loaded via the "Show full tree" button.
// Acts as fallback in renderTreeForSelectedOG so watchers don't wipe it out.
const fullNewick = ref<string | null>(null);

// Selected orthogroup - computed property linked to store
const selectedOrthogroup = computed({
  get: () => visualizationStore.phyloTree.selectedOrthogroup,
  set: (v: string) => visualizationStore.setPhyloTreeState({ selectedOrthogroup: v })
});

// Alias for template compatibility
const og = computed(() => selectedOrthogroup.value);

// Convert array to Record for DropdownMenu compatibility
const commonOGs_options = computed(() => {
  const record: Record<string, string> = {};
  commonOGs_array.value.forEach((ogItem) => {
    record[ogItem] = ogItem.toUpperCase();
  });
  return record;
});

// Expose orthogroupOptions to parent
defineExpose({
  orthogroupOptions: commonOGs_options
});

// URL state management
function updateUrlFromState() {
  const newQuery: Record<string, string> = { ...route.query } as Record<string, string>;

  if (selectedOrthogroup.value) {
    newQuery.orthogroup = selectedOrthogroup.value;
  } else {
    delete newQuery.orthogroup;
  }

  const plainFilters = filters.value;
  if (plainFilters && Object.keys(plainFilters).length > 0) {
    newQuery.filters = JSON.stringify(plainFilters);
  } else {
    delete newQuery.filters;
  }

  router.replace({
    name: route.name ?? undefined,
    query: newQuery,
  });
}


function getColumnKeys(dataRows: RowType[]): string[] {
  return [...new Set(dataRows.flatMap((row) => Object.keys(row)))];
}


const props = defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
  speciesCodeMap?: Record<string, string>; // table_name -> species_code (e.g., "arabidopsis_thaliana" -> "AT")
  hashLoading?: boolean; // True while parent is loading hash data
  initialOrthogroup?: string | null; // OG from hash load
}>();

const colorSchemes: Record<string, string[]> = {
  set1: [...d3.schemeSet1],
  set2: [...d3.schemeSet2],
  set3: [...d3.schemeSet3],
  paired: [...d3.schemePaired],
  dark2: [...d3.schemeDark2],
  accent: [...d3.schemeAccent],
  category10: [...d3.schemeCategory10],
  observable10: [...d3.schemeObservable10]
};


const selectedCount = ref(0);
selectedCount.value = Object.keys(props.tableName[0]).length;

const tableNameOptions = computed(() => {
  return Object.fromEntries(
    Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) || key === props.tableName,
    ),
  );
});


async function fetchData(
  tableName: string,
  rowCount: number,
  requestFilters: Record<string, any> = filtersStore.getMergedFilters(tableName),
) {
  try {

    if (rowCount <= 1000 && rowCount > 0) {

      console.log('Phylogenetic Tree - Fetching data with expression mode:', {
        optionId: visualizationStore.expressionDisplay.optionId,
        layer: visualizationStore.expressionDisplay.layer,
        transform: visualizationStore.expressionDisplay.transform
      });

      // Parallelize the 3 independent API calls
      const [exprRes, columnRes, metaRes] = await Promise.all([
        axios.post(
          `${API_BASE_URL}/api/data`,
          {
            table_name: tableName,
            filters: requestFilters,
            layer: visualizationStore.expressionDisplay.layer,
            transform: visualizationStore.expressionDisplay.transform,
          },
        ),
        axios.get<MetaFormat[]>(
          `${API_BASE_URL}/api/columns`,
          {params: {table_name: tableName, meta: false}},
        ),
        axios.post(
          `${API_BASE_URL}/api/data`,
          {
            table_name: tableName + "_meta",
            filters: {},
          },
        ),
      ]);

      const data = exprRes.data.data || exprRes.data;
      columnNames.value = getColumnKeys(rows.value);

      //DATA_COLUMNS
      dataColumnNames.value = columnRes.data.map((c) => c.column_name);

      //METADATA
      const colData = metaRes.data.data || metaRes.data;
      columns.value = (Array.isArray(colData) ? colData : []).filter((meta: RowType) =>
        dataColumnNames.value.includes(meta.column_name as string),
      );

      Object.entries(data).map(([_, v]) => {
        // Store newick with lowercase OG key to match getAllOGs() filtering
        const ogKey = String(v["ortho_id"]).trim().toLowerCase();
        orthogroupCaseMap.value[ogKey] = String(v["ortho_id"]).trim();
        newicks.value[ogKey] = v["newick_str"];
      })

      const filteredColumns = Object.values(columns.value).reduce((acc, item) => {
        if ('column_name' in item) {
          // Use tissue column directly from h5ad
          const tissue_type = item.tissue ?? "Unknown";
          if (tissue_type && tissue_type !== "") {
            acc['tissue_type_' + item.column_name] = tissue_type;
          } else {
            acc['tissue_type_' + item.column_name] = "Unknown";
          }
        }

        return acc
      }, {})

      const data_full = ref({items: []});
      Object.keys(data).forEach((key) => {
        const concat_array = assign({}, data[key], filteredColumns);
        data_full.value.items.push(concat_array);

      })

      return toRaw(data_full.value);
    }
    return false;
  } catch (e) {
    console.error("Error fetching data:", e);
  } finally {
  }

}

// Get orthogroups based on selected dataset count:
// - Single dataset: return ALL orthogroups from that dataset (union)
// - Multiple datasets: return ONLY orthogroups present in ALL datasets (intersection)
// Additionally filters to only include orthogroups that have Newick tree data
function getAllOGs(dataRef: Record<string, any>, newicksRef: Record<string, string>): Set<string> {
  const raw = toRaw(unref(dataRef));

  const sets = Object.entries(raw)
    .map(([_, plant]) => {
      if (!plant) return new Set<string>();
      
      const items = plant?.items ?? [];
      const arr = Array.isArray(items) ? items : Object.values(toRaw(items));

      const ogs = arr
        .map((o: any) => o?.ortho_id)
        .filter((v: any) => v != null && String(v).trim() !== "")
        .map((v: any) => String(v).trim().toLowerCase());

      return new Set(ogs);
    })
    .filter((s) => s.size > 0);

  if (sets.length === 0) return new Set();

  let resultSet: Set<string>;

  // Single dataset: return union (all OGs from that dataset)
  if (sets.length === 1) {
    resultSet = sets[0];
  } else {
    // Multiple datasets: return intersection (only OGs in ALL datasets)
    resultSet = sets.reduce((acc, s) => new Set([...acc].filter((og) => s.has(og))));
  }

  // Filter to only include OGs that have Newick tree data
  return new Set([...resultSet].filter(og => {
    const newickExists = newicksRef[og] && newicksRef[og].trim() !== '';
    return newickExists;
  }));
}


async function fetchAllSelected() {
  loading.value = true
  
  // Use catalog-selected datasets from existingTables prop
  const selectedDatasets = props.existingTables && props.existingTables.length > 0 
    ? [...props.existingTables] 
    : [props.tableName];
  
  const results: Record<string, any> = {}

  // Clear newicks before fetching to avoid stale data
  newicks.value = {};

  // Parallelize multi-species fetch instead of sequential for-loop
  const entries = await Promise.all(
    selectedDatasets.map(async (tableName) => {
      const { data: count } = await axios.post(
        `${API_BASE_URL}/api/count`,
        {
          table_name: tableName,
          filters: filtersStore.getMergedFilters(tableName),
        },
      );
      const rowCount = count.count;
      if (rowCount === 0) return null;
      const data = await fetchData(tableName, rowCount);
      return data ? { tableName, data } : null;
    })
  );

  for (const entry of entries) {
    if (entry) results[entry.tableName] = entry.data;
  }
  tableData.value = results

  // Apply union (single dataset) or intersection (multiple datasets) logic
  // Filter to only include OGs that have Newick tree data
  const filteredOGs = getAllOGs(results, newicks.value);
  commonOGs_array.value = [...filteredOGs].sort();

  // Handle OG selection with persistence and fallback
  // Priority: 1) initialOrthogroup from hash, 2) current store value, 3) first available
  const hashOG = props.initialOrthogroup;
  const currentSelection = hashOG || selectedOrthogroup.value;
  
  if (commonOGs_array.value.length > 0) {
    // If current selection is still valid (case-insensitive), keep it; otherwise select first
    const matchingOG = commonOGs_array.value.find(og => og.toLowerCase() === currentSelection?.toLowerCase());
    if (matchingOG) {
      // Use the exact case from commonOGs_array for consistency
      selectedOrthogroup.value = matchingOG;
    } else {
      selectedOrthogroup.value = commonOGs_array.value[0];
    }
  } else {
    // Keep the current selection when the species filter yields no matching OGs,
    // so the "Show full tree" button can still call loadFullNewickForOG with the
    // correct OG id. Only clear if there was truly nothing selected to begin with.
    if (!currentSelection) {
      selectedOrthogroup.value = '';
    }
    // else: leave selectedOrthogroup as-is so NoNewickComponent shows the right OG
    // and loadFullNewickForOG doesn't bail out on the empty-string guard.
  }

  loading.value = false
}

function computeMetrics(dataRef: any, calcOption: string, codeMap?: Record<string, string>) {

  return Object.fromEntries(
    Object.entries(dataRef.value).map(([groupName, groupVal]) => {
      const genes = Array.isArray(groupVal)
        ? groupVal
        : Array.isArray(groupVal?.items)
          ? groupVal.items
          : Object.values(groupVal?.items ?? {});

      // Look up species code for this group (e.g., "AT" for "arabidopsis_thaliana")
      const speciesCode = codeMap?.[groupName] ?? null

      const perGene = Object.fromEntries(genes.flatMap((gene) => {
          const tissueExpression = {}
          const normalizationTissue = {}

          const sampleKeys = Object.keys(gene).filter(
            k => /\d+$/.test(k) && typeof gene[k] === "number"
          )

          for (const k of sampleKeys) {
            const tissueKey = `tissue_type_${k}`
            const tissue = gene[tissueKey] || "Unknown"
            const value = gene[k]

            if (!tissueExpression[tissue]) tissueExpression[tissue] = []
            tissueExpression[tissue].push(value)
          }

          Object.entries(tissueExpression).map(([key, value]) => {
              if (calcOption === "mean") {
                const v = mean(value)
                if (!normalizationTissue[key]) normalizationTissue[key] = []
                normalizationTissue[key].push(v)
              } else {
                const v = median(value)
                if (!normalizationTissue[key]) normalizationTissue[key] = []
                normalizationTissue[key].push(v)
              }
            }
          )
          const data = { tissueExpression, normalizationTissue }

          const entries = buildPhyloMetricKeys(groupName, String(gene.gene_id), speciesCode)
            .map((key): [string, typeof data] => [key, data])
          return entries
        })
      )
      return [groupName, perGene]
    })
  )
}

async function fetchOrthogroupDataForAllSpecies() {
  if (!selectedOrthogroup.value) return false;

  const allDatasets = Object.keys(props.allTables);
  if (allDatasets.length === 0) return false;
  const originalCaseOrthogroup = orthogroupCaseMap.value[selectedOrthogroup.value] || selectedOrthogroup.value;

  const entries = await Promise.all(
    allDatasets.map(async (tableName) => {
      const scopedFilters = buildOrthogroupScopedFilters(
        filtersStore.getMergedFilters(tableName),
        originalCaseOrthogroup,
      );

      const { data: count } = await axios.post(`${API_BASE_URL}/api/count`, {
        table_name: tableName,
        filters: scopedFilters,
      });

      const rowCount = count.count;
      if (rowCount === 0) return null;

      const data = await fetchData(tableName, rowCount, scopedFilters);
      return data ? { tableName, data } : null;
    })
  );

  const results: Record<string, any> = {};
  for (const entry of entries) {
    if (entry) results[entry.tableName] = entry.data;
  }

  if (Object.keys(results).length === 0) {
    return false;
  }

  tableData.value = results;
  return true;
}

function mean(arr: number[]): number {
  if (arr.length > 2) {
    const sum = arr.reduce((acc, val) => acc + val, 0);
    return sum / arr.length;
  } else {
    return arr[0];
  }
}

function median(values: number[]): number {
  values = [...values].sort((a, b) => a - b);
  const half = Math.floor(values.length / 2);
  return (values.length % 2
      ? values[half]
      : (values[half - 1] + values[half]) / 2
  );
}


function resetContainer() {
  if (!phylotreeContainer.value) return;
  d3.select(phylotreeContainer.value).selectAll("*").remove();
}

function getPrefix(name: string): string {
  const m = name.match(/^([^_]+)/)
  return m ? m[1] : name
}

/**
 * Extract subtree as Newick string from a node using phylotree's getNewick
 * @param node - The phylotree node to export
 * @returns Newick string representation of the subtree
 */
function getSubtreeNewick(node: any): string {
  // Recursive function to build Newick from node structure
  function buildNewick(n: any): string {
    if (!n) return '';
    
    const name = n.data?.name || n.name || '';
    const branchLength = n.data?.attribute !== undefined ? `:${n.data.attribute}` : '';
    
    // If node has children, recursively process them
    if (n.children && n.children.length > 0) {
      const childStrings = n.children.map((child: any) => buildNewick(child));
      return `(${childStrings.join(',')})${name}${branchLength}`;
    }
    
    // Leaf node
    return `${name}${branchLength}`;
  }
  
  return buildNewick(node) + ';';
}

/**
 * Download text content as a file
 */
function downloadTextFile(content: string, filename: string, mimeType: string = 'text/plain') {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Store for clade highlighting colors
const cladeColors = ref<Map<string, string>>(new Map());
const highlightColorPalette = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#14b8a6', '#3b82f6', '#8b5cf6', '#ec4899'];
let nextColorIndex = 0;

async function initPhylotree(newick_str: string, metrics: any) {
  loading.value = true

  resetContainer()

  const tree = new phylotree(newick_str)
  const container = phylotreeContainer.value

  const renderedTree = tree.render({
    width: container?.clientWidth || window.innerWidth * 0.8,
    height: window.innerHeight,
    'top-bottom-spacing': 'fit-to-size',
    selectable: false,
    collapsible: true,   // Enable phylotree's built-in collapse on node click
    'show-scale': false,  // Scale bar disabled
    zoom: false,  // We implement our own zoom
    brush: false,
    reroot: false,  // Disable default reroot behavior on branch click
    hide: false,    // Disable default hide behavior
    container: '#phylotreeContainer'
  })

  const svgElement = renderedTree.show()

  if (!container || !(svgElement instanceof SVGSVGElement)) {
    return
  }

  renderedTree.layout(true)

  container.innerHTML = ''
  container.appendChild(svgElement)

  const svgSel = d3.select<SVGSVGElement, unknown>(svgElement)

  const mainGroup = svgSel.select<SVGGElement>('g')
  if (!mainGroup.node()) return

  // === ZOOM IMPLEMENTATION ===
  // Create a wrapper group for zoom transforms
  const zoomGroup = svgSel.insert('g', ':first-child')
    .attr('class', 'zoom-container');
  
  // Move the main group into the zoom container
  mainGroup.remove();
  zoomGroup.append(() => mainGroup.node());
  
  // Create zoom behavior
  const zoomBehavior = d3.zoom<SVGSVGElement, unknown>()
    .scaleExtent([0.1, 10])  // Allow 10% to 1000% zoom
    .filter((event) => {
      // Don't zoom when clicking on nodes (let node click handlers work)
      const target = event.target as Element;
      const isNode = target.closest('g.node') !== null;
      // Allow zoom for scroll wheel, but not for click on nodes
      if (event.type === 'wheel') return true;
      if (event.type === 'mousedown' && isNode) return false;
      if (event.type === 'dblclick' && isNode) return false;
      return true;
    })
    .on('zoom', (event) => {
      zoomGroup.attr('transform', event.transform.toString());
      // Persist zoom state to store (throttled to avoid excessive updates)
      visualizationStore.setPhyloTreeZoom({
        k: event.transform.k,
        x: event.transform.x,
        y: event.transform.y
      });
    });
  
  // Apply zoom behavior to SVG
  svgSel.call(zoomBehavior);
  currentZoomBehavior = zoomBehavior;
  
  // Restore saved zoom transform from store
  const savedTransform = visualizationStore.phyloTree.zoomTransform;
  if (savedTransform.k !== 1 || savedTransform.x !== 0 || savedTransform.y !== 0) {
    const transform = d3.zoomIdentity
      .translate(savedTransform.x, savedTransform.y)
      .scale(savedTransform.k);
    svgSel.call(zoomBehavior.transform, transform);
  }
  // === END ZOOM IMPLEMENTATION ===

  // Note: Title is now rendered in the Vue template, not in SVG

  const bbox = mainGroup.node()!.getBBox()
  const leaves: { name: string; y: number }[] = []

  svgSel.selectAll<SVGGElement, any>('g.node').each(function (d: any) {
    const g = d3.select(this)
    const datum = d || g.datum()
    const name: string | undefined =
      datum?.name || datum?.data?.name || datum?.data?.id

    if (!name) return

    const transform = g.attr('transform') || ''
    const m = /translate\(([^,]+),\s*([^)]+)\)/.exec(transform)
    if (!m) return

    const y = +m[2]
    leaves.push({name, y})
  })

  const prefixes = Array.from(new Set(leaves.map(l => getPrefix(l.name))))

  const selectedScheme = colorSchemes[visualizationStore.colorScale] || d3.schemeSet1;

  const prefixColor = d3.scaleOrdinal()
    .domain(prefixes)
    .range(selectedScheme)

  svgSel.selectAll<SVGGElement, any>('g.node').each(function (d: any) {
    const g = d3.select(this)
    const datum = d || g.datum()

    const name: string | undefined =
      datum?.name || datum?.data?.name || datum?.data?.id

    if (!name) return

    const prefix = getPrefix(name)
    const color = prefixColor(prefix)

    g.select('circle').attr('fill', color)
    g.select('text').attr('fill', color)
  })

  // === BOOTSTRAP VALUES DISPLAY ===
  // Display bootstrap/support values on internal nodes if available in node name or attribute
  svgSel.selectAll<SVGGElement, any>('g.internal-node').each(function (d: any) {
    const g = d3.select(this);
    const datum = d || g.datum();
    
    // Bootstrap values can be in node name (e.g., "100" or "0.95") or in attribute
    const nodeName = datum?.data?.name || datum?.name || '';
    const nodeAttr = datum?.data?.annotation || datum?.annotation || '';
    
    // Try to parse as bootstrap value (numeric between 0-100 or 0-1)
    let bootstrapValue: number | null = null;
    const numericName = parseFloat(nodeName);
    const numericAttr = parseFloat(nodeAttr);
    
    if (!isNaN(numericName) && numericName >= 0) {
      bootstrapValue = numericName;
    } else if (!isNaN(numericAttr) && numericAttr >= 0) {
      bootstrapValue = numericAttr;
    }
    
    // Display bootstrap value if found and significant (>= 50% or >= 0.5)
    if (bootstrapValue !== null) {
      // Normalize to 0-100 range if needed
      const displayValue = bootstrapValue <= 1 ? Math.round(bootstrapValue * 100) : Math.round(bootstrapValue);
      
      if (displayValue >= 50) {
        const circle = g.select('circle, ellipse, rect');
        const cx = parseFloat(circle.attr('cx') || '0');
        const cy = parseFloat(circle.attr('cy') || '0');
        
        g.append('text')
          .attr('class', 'bootstrap-value')
          .attr('x', cx - 5)
          .attr('y', cy - 8)
          .attr('font-size', '9px')
          .attr('fill', displayValue >= 90 ? '#059669' : displayValue >= 70 ? '#d97706' : '#dc2626')
          .attr('font-weight', displayValue >= 90 ? 'bold' : 'normal')
          .text(displayValue.toString());
      }
    }
  });

  // === CLADE HIGHLIGHTING ===
  // Apply stored clade colors to branches
  function getDescendantNodeIds(node: any): string[] {
    const ids: string[] = [];
    function traverse(n: any) {
      if (!n) return;
      const nodeId = n.data?.name || n.name || '';
      if (nodeId) ids.push(nodeId);
      if (n.children) {
        n.children.forEach((child: any) => traverse(child));
      }
    }
    traverse(node);
    return ids;
  }
  
  // Simple nodeId generator for clade highlighting (defined before main getNodeId)
  function getSimpleNodeId(g: d3.Selection<SVGGElement, any, any, any>, datum: any): string {
    if (datum?.data?.name) return datum.data.name;
    if (datum?.name) return datum.name;
    const transform = g.attr('transform') || '';
    const m = /translate\\(([^,]+),\\s*([^)]+)\\)/.exec(transform);
    if (m) return `internal_${Math.round(+m[1])}_${Math.round(+m[2])}`;
    return '';
  }
  
  // Color branches for highlighted clades — pre-build node-ID-to-element map for O(1) lookup
  const nodeElementMap = new Map<string, { g: d3.Selection<SVGGElement, any, any, any>; datum: any }>();
  svgSel.selectAll<SVGGElement, any>('g.node, g.internal-node').each(function (d: any) {
    const g = d3.select(this);
    const datum = d || g.datum();
    const nodeId = getSimpleNodeId(g, datum);
    if (nodeId) {
      nodeElementMap.set(nodeId, { g, datum });
    }
  });

  cladeColors.value.forEach((color, nodeId) => {
    const entry = nodeElementMap.get(nodeId);
    if (!entry) return;

    // Color the subtree branches
    const descendantIds = getDescendantNodeIds(entry.datum);

    // Color nodes in subtree using map lookup instead of full scan
    for (const descId of descendantIds) {
      const descEntry = nodeElementMap.get(descId);
      if (descEntry) {
        descEntry.g.select('circle, ellipse, rect').attr('fill', color);
        descEntry.g.select('text').attr('fill', color);
      }
    }

    // Also color the clicked node itself
    entry.g.select('circle, ellipse, rect')
      .attr('fill', color)
      .attr('stroke', color)
      .attr('stroke-width', 2);
  });


  const groupNames = Object.keys(metrics)
  const tissueSet = new Set<string>()
  for (const group of Object.values(metrics)) {
    for (const gene of Object.values(group)) {
      const norm = gene.normalizationTissue ?? {}
      for (const t of Object.keys(norm)) {
        tissueSet.add(t)
      }
    }
  }

  let tissues = Array.from(tissueSet)
  
  // Apply column clustering if enabled
  if (visualizationStore.clustering.clusterCols && tissues.length > 2) {
    try {
      // Build a data matrix for clustering: rows = genes, cols = tissues
      const allGenes: { geneId: string; values: number[] }[] = [];
      
      for (const [_, genesObj] of Object.entries(metrics)) {
        for (const [geneId, geneData] of Object.entries(genesObj as Record<string, any>)) {
          const tn = geneData?.normalizationTissue ?? {};
          const values = tissues.map(t => {
            let v = tn[t];
            if (Array.isArray(v)) v = v[0];
            return typeof v === 'number' && Number.isFinite(v) ? v : 0;
          });
          allGenes.push({ geneId, values });
        }
      }
      
      if (allGenes.length > 0) {
        // Transpose for column clustering: each row is a tissue profile across all genes
        const colProfiles: number[][] = tissues.map((_, colIdx) =>
          allGenes.map(g => g.values[colIdx])
        );
        
        // Perform hierarchical clustering on columns (returns order directly)
        const clusterResult = hierarchicalCluster(
          colProfiles,
          visualizationStore.clustering.method,
          visualizationStore.clustering.distance
        );
        
        // Reorder tissues based on clustering
        tissues = clusterResult.order.map(idx => tissues[idx]);
      }
    } catch (error) {
      console.warn('Column clustering failed, using original order:', error);
    }
  }

  const columns: { tissue: string; colIndex: number }[] =
    tissues.map((tissue, idx) => ({tissue, colIndex: idx}))


  const allValues: number[] = []

  for (const [_, genesObj] of Object.entries(metrics)) {
    const geneIds = Object.keys(genesObj)
    geneIds.forEach(geneId => {
      const tn = genesObj[geneId]?.normalizationTissue ?? {}
      tissues.forEach(t => {
        let v = tn[t]
        if (Array.isArray(v)) v = v[0]
        if (typeof v === 'number' && Number.isFinite(v)) {
          allValues.push(v)
        }
      })
    })
  }

  const minVal = d3.min(allValues) ?? 0
  const maxVal = d3.max(allValues) ?? 1

  const color = d3
    .scaleSequential(
      COLORSCALES[visualizationStore.colorScale] as (t: number) => string,
    )
    .domain([minVal, maxVal])

  const treeRight = bbox.x + bbox.width

  const cellSize = 14
  const cellPad = 6
  const heatmapX = treeRight

  const heatmapGroup = mainGroup.append('g')
    .attr('class', 'tree-heatmap')
    .attr('transform', `translate(${heatmapX})`)

  // Build map: species prefix -> lowercase table name
  // Supports both full species name prefixes (e.g., "Capnoides_sempervirens" -> "capnoides_sempervirens")
  // and short species code prefixes (e.g., "AT" -> "arabidopsis_thaliana")
  const speciesNameToTable: Record<string, string> = {}
  groupNames.forEach(tableName => {
    // Full species name: "capnoides_sempervirens" -> "Capnoides_sempervirens"
    const sentenceCase = tableName.charAt(0).toUpperCase() + tableName.slice(1)
    speciesNameToTable[sentenceCase] = tableName
    // Also add short species code mapping if available (e.g., "AT" -> "arabidopsis_thaliana")
    const code = props.speciesCodeMap?.[tableName]
    if (code && !(code in speciesNameToTable)) {
      speciesNameToTable[code] = tableName
    }
  })
  
  // === NODE INTERACTIVITY WITH COLLAPSE SUPPORT ===

  // Helper to generate a unique node ID for internal nodes based on position
  function getNodeId(g: d3.Selection<SVGGElement, any, any, any>, datum: any): string {
    // Try to get name first
    if (datum?.data?.name) return datum.data.name;
    if (datum?.name) return datum.name;
    // Use transform position as unique identifier for unnamed internal nodes
    const transform = g.attr('transform') || '';
    const m = /translate\(([^,]+),\s*([^)]+)\)/.exec(transform);
    if (m) {
      return `internal_${Math.round(+m[1])}_${Math.round(+m[2])}`;
    }
    return `internal_${Math.random().toString(36).substr(2, 9)}`;
  }
  
  // Count internal nodes for debugging
  let internalNodeCount = 0;
  let leafNodeCount = 0;
  
  // Debug: Log element counts
  const allNodes = svgSel.selectAll<SVGGElement, any>('g.node');
  const branches = svgSel.selectAll<SVGPathElement, any>('path.branch');
  console.log(`[PhyloTree] Elements - Nodes: ${allNodes.size()}, Branches: ${branches.size()}`);
  
  // Add hover effects to branches for better UX
  branches.each(function() {
    const path = d3.select(this);
    const originalStroke = path.attr('stroke') || '#aaa';
    const originalWidth = path.attr('stroke-width') || '1.5';
    
    path.style('cursor', 'pointer')
      .on('mouseenter', function() {
        d3.select(this)
          .attr('stroke-width', 3)
          .attr('stroke', '#3b82f6');
      })
      .on('mouseleave', function() {
        d3.select(this)
          .attr('stroke-width', originalWidth)
          .attr('stroke', originalStroke);
      });
  });
  
  svgSel.selectAll<SVGGElement, any>('g.node').each(function (d: any) {
    const g = d3.select(this)
    const datum = d || g.datum()
    
    // Get node name - leaves have names, internal nodes typically don't
    const nodeName: string | undefined =
      datum?.data?.name || datum?.name || datum?.data?.id
    
    // Check for circle element - internal nodes typically have circles
    const circleEl = g.select('circle');
    const hasCircle = circleEl.node() !== null;
    
    // Determine if this is a leaf node by checking the text element
    // Leaf nodes have visible species/gene name labels, internal nodes have no text or empty text
    const textEl = g.select('text');
    const textContent = textEl.node() ? textEl.text().trim() : '';
    const hasVisibleLabel = textContent.length > 0;
    
    // A node is INTERNAL if it has a circle but no visible text label
    // OR if it explicitly has no name
    const isInternalNode = (hasCircle && !hasVisibleLabel) || (!nodeName && hasCircle);
    
    const nodeId = getNodeId(g, datum);
    
    if (isInternalNode) internalNodeCount++;
    else leafNodeCount++;
    
    // For LEAF nodes only - add context menu for species operations
    // (phylotree.js handles internal node collapse via collapsible: true)
    if (!isInternalNode && nodeName) {
      // For leaf nodes - species hide/show behavior via context menu
      const speciesTableName = matchLeafToDataset(nodeName, groupNames, props.speciesCodeMap ?? {})?.tableName;
      if (!speciesTableName) return;
      
      g.on('contextmenu', function(event: MouseEvent) {
          event.preventDefault();
          event.stopPropagation();
          showNodeContextMenu(event, container, speciesTableName, metrics);
        });
    }
  });
  
  console.log(`[PhyloTree] Node counts - Internal: ${internalNodeCount}, Leaf: ${leafNodeCount}`);
  
  // Context menu for leaf nodes
  function showNodeContextMenu(event: MouseEvent, container: HTMLElement, speciesTableName: string, metrics: any) {
    // Remove any existing context menus
    d3.selectAll('.node-context-menu').remove();
    
    const contextMenu = d3.select(container)
      .append('div')
      .attr('class', 'node-context-menu')
      .style('position', 'absolute')
      .style('left', (event.clientX - container.getBoundingClientRect().left) + 'px')
      .style('top', (event.clientY - container.getBoundingClientRect().top) + 'px')
      .style('background', 'white')
      .style('border', '1px solid #ccc')
      .style('border-radius', '4px')
      .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)')
      .style('z-index', '1000')
      .style('padding', '4px 0');
    
    const isHidden = hiddenSpecies.value.has(speciesTableName);
    
    const menuItems = [
      { label: isHidden ? 'Show species' : 'Hide species', action: () => {
        if (isHidden) {
          hiddenSpecies.value.delete(speciesTableName);
        } else {
          hiddenSpecies.value.add(speciesTableName);
        }
        initPhylotree(newickstr.value, metrics);
      }},
      { label: 'Show all species', action: () => {
        hiddenSpecies.value.clear();
        initPhylotree(newickstr.value, metrics);
      }}
    ];
    
    menuItems.forEach(item => {
      contextMenu.append('div')
        .style('padding', '6px 12px')
        .style('cursor', 'pointer')
        .style('font-size', '13px')
        .text(item.label)
        .on('mouseover', function() { d3.select(this).style('background', '#f0f0f0'); })
        .on('mouseout', function() { d3.select(this).style('background', 'white'); })
        .on('click', function() { item.action(); contextMenu.remove(); });
    });
    
    d3.select('body').on('click.contextmenu', function() {
      contextMenu.remove();
      d3.select('body').on('click.contextmenu', null);
    });
  }
  
  // Context menu for internal nodes (collapse/expand, export, highlight)
  function showInternalNodeContextMenu(event: MouseEvent, container: HTMLElement, nodeId: string, datum: any, metrics: any) {
    d3.selectAll('.node-context-menu').remove();
    
    const contextMenu = d3.select(container)
      .append('div')
      .attr('class', 'node-context-menu')
      .style('position', 'absolute')
      .style('left', (event.clientX - container.getBoundingClientRect().left) + 'px')
      .style('top', (event.clientY - container.getBoundingClientRect().top) + 'px')
      .style('background', 'white')
      .style('border', '1px solid #ccc')
      .style('border-radius', '4px')
      .style('box-shadow', '0 2px 8px rgba(0,0,0,0.15)')
      .style('z-index', '1000')
      .style('padding', '4px 0');
    
    const isCollapsed = collapsedNodes.value.has(nodeId);
    const isHighlighted = cladeColors.value.has(nodeId);
    
    // Menu items with separators (null = separator)
    const menuItems: ({ label: string; action: () => void; icon?: string } | null)[] = [
      { label: isCollapsed ? '▶ Expand clade' : '▼ Collapse clade', action: () => {
        visualizationStore.toggleNodeCollapsed(nodeId);
        initPhylotree(newickstr.value, metrics);
      }},
      { label: '↺ Expand all clades', action: () => {
        visualizationStore.resetPhyloTreeState();
        initPhylotree(newickstr.value, metrics);
      }},
      null, // Separator
      { label: '📥 Export subtree (Newick)', action: () => {
        const newick = getSubtreeNewick(datum);
        const filename = `subtree_${og.value}_${nodeId.replace(/[^a-zA-Z0-9]/g, '_')}.nwk`;
        downloadTextFile(newick, filename);
      }},
      null, // Separator
      { label: isHighlighted ? '🎨 Remove highlight' : '🎨 Highlight clade', action: () => {
        if (isHighlighted) {
          cladeColors.value.delete(nodeId);
        } else {
          // Assign next color from palette
          const color = highlightColorPalette[nextColorIndex % highlightColorPalette.length];
          nextColorIndex++;
          cladeColors.value.set(nodeId, color);
        }
        initPhylotree(newickstr.value, metrics);
      }},
      { label: '🧹 Clear all highlights', action: () => {
        cladeColors.value.clear();
        nextColorIndex = 0;
        initPhylotree(newickstr.value, metrics);
      }}
    ];
    
    menuItems.forEach(item => {
      if (item === null) {
        // Render separator
        contextMenu.append('div')
          .style('height', '1px')
          .style('background', '#e5e7eb')
          .style('margin', '4px 0');
      } else {
        contextMenu.append('div')
          .style('padding', '6px 12px')
          .style('cursor', 'pointer')
          .style('font-size', '13px')
          .text(item.label)
          .on('mouseover', function() { d3.select(this).style('background', '#f0f0f0'); })
          .on('mouseout', function() { d3.select(this).style('background', 'white'); })
          .on('click', function() { item.action(); contextMenu.remove(); });
      }
    });
    
    d3.select('body').on('click.contextmenu', function() {
      contextMenu.remove();
      d3.select('body').on('click.contextmenu', null);
    });
  }
  // === END NODE INTERACTIVITY ===

  // Create tooltip div
  const tooltip = d3.select(container)
    .append("div")
    .attr("class", "phylo-tooltip")
    .style("position", "absolute")
    .style("visibility", "hidden")
    .style("background-color", "white")
    .style("color", "#333")
    .style("font-size", "0.75rem")
    .style("border-radius", "0.375rem")
    .style("padding", "0.25rem 0.5rem")
    .style("min-width", "8rem")
    .style("white-space", "normal")
    .style("word-wrap", "break-word")
    .style("max-width", "24rem")
    .style("border", "1px solid #d1d5db")
    .style("box-shadow", "0 1px 2px rgba(0,0,0,0.05)")
    .style("pointer-events", "auto")
    .style("user-select", "text")
    .style("z-index", "1000");

  // Store tissue columns for TooltipModal
  heatmapCols.value = tissues;

  leaves.forEach(leaf => {
    const leafName = leaf.name  // e.g., "Staphisagria_picta_evm.model.ptg000098l.1147"

    const resolvedLeaf = resolvePhyloLeafMatch(leafName, metrics, props.speciesCodeMap ?? {})
    if (!resolvedLeaf) return

    const matchedTable = resolvedLeaf.tableName

    // Skip hidden species
    if (hiddenSpecies.value.has(matchedTable)) return;

    columns.forEach(({tissue, colIndex}) => {
      const genesObj = metrics[matchedTable]
      if (!genesObj) return

      const geneObj = genesObj[resolvedLeaf.matchedKey]
      if (!geneObj) return

      let v: any = geneObj.normalizationTissue?.[tissue]
      if (Array.isArray(v)) v = v[0]
      if (typeof v === 'number' && Number.isFinite(v)) {
        // Get the original row data for this gene from tableData
        const originalRowData = tableData.value[matchedTable]?.items?.find(
          (item: any) => String(item[config.visualization.id_column]) === resolvedLeaf.geneId
        );
        
        // Store references for tooltip/modal access
        const cellData = {
          geneId: resolvedLeaf.geneId,
          tissue: tissue,
          value: v,
          species: matchedTable,
          tableName: matchedTable,
          geneObj: geneObj,
          rowData: originalRowData || null // Store full row data for modal
        };

        heatmapGroup.append('rect')
          .attr('x', colIndex * (cellSize + cellPad))
          .attr('y', leaf.y - cellSize / 2 + (-3))
          .attr('width', cellSize)
          .attr('height', cellSize)
          .attr('fill', color(v))
          .attr('class', 'heatmap-cell')
          .style('cursor', 'pointer')
          .datum(cellData)
          .on('mouseover', function(event, d) {
            d3.select(this).attr('stroke', 'white').style('stroke-width', 2);
            
            // Build tooltip content with dynamic entity label and selected fields
            const entityLabel = getEntityIdLabel();
            const selectedFields = visualizationStore.tooltipFields;
            
            // Start with base fields
            let tooltipHtml = `
              <b>${entityLabel}:</b> ${d.geneId}<br>
              <b>Tissue:</b> ${d.tissue}<br>
              <b>Value:</b> ${typeof d.value === 'number' ? d.value.toFixed(3) : d.value}<br>
              <b>Species:</b> ${d.species}<br>
            `;
            
            // Add selected metadata fields if row data is available
            if (d.rowData && selectedFields !== null && selectedFields.length > 0) {
              const metaLines = selectedFields
                .filter(field => field !== config.visualization.id_column && d.rowData[field] !== undefined)
                .map(field => {
                  let value = d.rowData[field];
                  if (Array.isArray(value)) {
                    value = value.length > 3 ? value.slice(0, 3).join(', ') + '...' : value.join(', ');
                  }
                  return `<b>${getDisplayName(field)}:</b> ${value}`;
                })
                .join('<br>');
              
              if (metaLines) {
                tooltipHtml += `<hr style="margin:4px 0; border-color:#888"/>${metaLines}`;
              }
            }
            
            tooltipHtml += `
              <hr style="margin:4px 0; border-color:#888"/>
              <div style="text-align:center; font-size:0.7rem; color:#6b7280;">Right-click for more details</div>
            `;
            
            tooltip.html(tooltipHtml).style('visibility', 'visible');
          })
          .on('mousemove', function(event) {
            if (!container) return;
            const containerRect = container.getBoundingClientRect();
            const tooltipNode = tooltip.node();
            if (!tooltipNode) return;
            const tooltipRect = tooltipNode.getBoundingClientRect();
            
            const offsetX = 12;
            let xPos = event.clientX - containerRect.left + offsetX;
            let yPos = event.clientY - containerRect.top - tooltipRect.height / 2;
            
            if (xPos + tooltipRect.width > containerRect.width) {
              xPos = event.clientX - containerRect.left - tooltipRect.width - offsetX;
            }
            
            xPos = Math.max(0, xPos);
            yPos = Math.max(0, Math.min(yPos, containerRect.height - tooltipRect.height));
            
            tooltip
              .style('left', xPos + 'px')
              .style('top', yPos + 'px');
          })
          .on('mouseout', function() {
            d3.select(this).attr('stroke', 'none');
            tooltip.style('visibility', 'hidden');
          })
          .on('contextmenu', function(event, d) {
            event.preventDefault();
            
            // Use the stored rowData directly
            if (d.rowData) {
              selectedRowData.value = d.rowData;
              selectedTableName.value = d.tableName;
              selectedColumnValue.value = d.tissue;
              selectedCellValue.value = d.value;
              // Update heatmapCols with available tissue columns
              heatmapCols.value = Array.from(tissueSet);
              showTooltipModal.value = true;
            } else {
              console.warn('No row data available for this cell');
            }
          });
      }
    })
  })

  const firstLeafY = d3.min(leaves, d => d.y) ?? 0

  const topCellY = firstLeafY - cellSize

  const labelY = topCellY - 10

  columns.forEach(({tissue, colIndex}) => {
    const x = colIndex * (cellSize + cellPad) + cellSize / 2

    heatmapGroup.append('text')
      .attr('x', x)
      .attr('y', labelY)
      .attr('text-anchor', 'left')
      .attr('font-size', 17)
      .attr('transform', `rotate(-90, ${x}, ${labelY})`)
      .text(tissue.charAt(0).toUpperCase() + tissue.slice(1))
  })

  const heatmapWidth = columns.length * (cellSize + cellPad)

  const legendWidth = 26
  const legendHeight = 230
  const legendSteps = 40

  const legendX = heatmapX + heatmapWidth + 200

  const legendY = firstLeafY - legendHeight + 200

  // Only render legend if visualizationStore.legend is true
  if (visualizationStore.legend) {
    const legendGroup = mainGroup.append('g')
      .attr('class', 'heatmap-legend')
      .attr('transform', `translate(${legendX}, ${legendY})`)


  const legendValueScale = d3.scaleLinear()
    .domain([minVal, maxVal])
    .range([legendHeight, 0])

  const stepHeight = legendHeight / legendSteps

  const legendData = d3.range(legendSteps).map(i => {
    const t0 = i / legendSteps
    const v = minVal + t0 * (maxVal - minVal)
    return {index: i, value: v}
  })

  legendGroup.selectAll('rect')
    .data(legendData)
    .enter()
    .append('rect')
    .attr('x', 0)
    .attr('y', d => legendValueScale(d.value))
    .attr('width', legendWidth)
    .attr('height', stepHeight + 10)
    .attr('fill', d => color(d.value))


  legendGroup.append('g')
    .attr('transform', `translate(${legendWidth + 4}, 0)`)
    .call(
      d3.axisRight(legendValueScale)
        .ticks(5)
        .tickSize(4)
    )
    .selectAll('text')
    .style('font-size', '18')


  legendGroup.append('text')
    .attr('x', legendWidth / 2)
    .attr('y', -10)
    .attr('text-anchor', 'middle')
    .style('font-size', '14px')
    .text(getExpressionOption(visualizationStore.expressionDisplay.optionId)?.label || 'Expression values')
  }


  const finalBBox = mainGroup.node()!.getBBox()

  const padding = 10
  const viewWidth = finalBBox.width + padding * 2
  const viewHeight = finalBBox.height + padding * 2

  const shiftY = padding - finalBBox.y

  mainGroup.attr('transform', `translate(0, ${shiftY})`)

  svgElement.setAttribute('viewBox', `0 0 ${viewWidth} ${viewHeight}`)
  svgElement.removeAttribute('width')
  svgElement.removeAttribute('height')
  svgElement.style.width = '100%'
  svgElement.style.height = 'auto'
  svgElement.setAttribute('preserveAspectRatio', 'xMinYMin meet')

  loading.value = false
}


// Helper function to render tree for currently selected orthogroup
async function renderTreeForSelectedOG() {
  if (!selectedOrthogroup.value || !newicks.value[selectedOrthogroup.value]) {
    // Fall back to the directly-loaded full Newick (button was clicked)
    if (fullNewick.value) {
      const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
      newickstr.value = fullNewick.value;
      await nextTick();
      initPhylotree(newickstr.value, metrics);
      return;
    }
    newickstr.value = null as any;
    return;
  }

  await fetchOrthogroupDataForAllSpecies();
  
  const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
  newickstr.value = newicks.value[selectedOrthogroup.value];
  if (newickstr.value !== null) {
    await nextTick();
    initPhylotree(newickstr.value, metrics);
  }
}

// Load the full Newick for the selected OG directly from the API,
// bypassing the species filter (useful when the current species has
// no entry in the selected orthogroup).
async function loadFullNewickForOG() {
  if (!selectedOrthogroup.value) return;
  try {
    const response = await axios.get<{ og_id: string; newick: string }>(
      `${API_BASE_URL}/api/gene_tree/${orthogroupCaseMap.value[selectedOrthogroup.value] || selectedOrthogroup.value}`
    );
    const newick = response.data.newick;
    if (!newick) return;

    fullNewick.value = newick;  // persist so watchers can't wipe it
    newickstr.value = newick;

    // Re-fetch all available datasets with the SAME merged filters (which already
    // include the orthogroup filter from the sidebar), but for ALL species — not
    // just the catalog-selected ones.  Per-species row count for a single OG is
    // always small (<1000), so the rowCount guard inside fetchData is never hit.
    await fetchOrthogroupDataForAllSpecies();

    const metrics = computeMetrics(tableData, "mean", props.speciesCodeMap);
    await nextTick();
    initPhylotree(newickstr.value, metrics);
  } catch (e) {
    console.error("Failed to load full gene tree:", e);
  }
}


onMounted(async () => {
  // Parse URL state
  const rawOg = route.query.orthogroup;
  if (rawOg) {
    visualizationStore.setPhyloTreeState({ selectedOrthogroup: String(rawOg) });
  }

  const rawFilters = route.query.filters;
  if (rawFilters) {
    try {
      const parsed = JSON.parse(String(rawFilters));
      if (parsed && typeof parsed === "object") {
        filters.value = parsed;
      }
    } catch {
      // ignore parse errors
    }
  }

  // Mark URL parsing as complete
  initialUrlParsing.value = false;

  // Initial data fetch will be triggered by the watcher
})


// Watch for hashLoading to complete - then trigger initial fetch
watch(
  () => props.hashLoading,
  async (isLoading) => {
    // When hash loading completes (false), trigger initial data fetch
    if (isLoading === false) {
      await fetchAllSelected();
      await renderTreeForSelectedOG();
    }
  },
  { immediate: true }
)


watch(
  () => Object.keys(props.allTables).length,
  async (newCount, oldCount) => {
    if (props.hashLoading) return;
    if (newCount === 0 || newCount === oldCount) return;
    if (!selectedOrthogroup.value) return;

    await renderTreeForSelectedOG();
  }
)


// Watch for filter, per-dataset ID filter, and table changes - refetch data
watch(
  [tableNameOptions, filters, () => filtersStore.datasetIdFilters],
  async () => {
    // Don't fetch while hash is still loading
    if (props.hashLoading) return;
    await fetchAllSelected();
    await renderTreeForSelectedOG();
  },
  {deep: true}
)


// Watch for orthogroup selection changes
watch(
  selectedOrthogroup,
  async () => {
    if (initialUrlParsing.value) return;
    if (props.hashLoading) return;
    fullNewick.value = null;  // clear full-tree override when user picks a new OG
    updateUrlFromState();
    await renderTreeForSelectedOG();
  }
)


watch(
  () => visualizationStore.expressionDisplay,
  async () => {
    if (props.hashLoading) return;
    console.log('[PhylogeneticTree] Expression display changed:', visualizationStore.expressionDisplay)
    // Fetch new data with updated layer/transform parameters
    await fetchAllSelected();
    await renderTreeForSelectedOG();
  },
  { deep: true }
);


watch(
  () => visualizationStore.colorScale,
  async () => {
    console.log('[PhylogeneticTree] ColorScale changed:', visualizationStore.colorScale)
    await renderTreeForSelectedOG();
  }
);


watch(
  () => visualizationStore.legend,
  async () => {
    console.log('[PhylogeneticTree] Legend toggle changed:', visualizationStore.legend)
    await renderTreeForSelectedOG();
  }
);


// Watch for clustering settings changes (only clusterCols applies to PhyloTree)
watch(
  [
    () => visualizationStore.clustering.clusterCols,
    () => visualizationStore.clustering.method,
    () => visualizationStore.clustering.distance,
  ],
  async () => {
    console.log('[PhylogeneticTree] Clustering settings changed:', visualizationStore.clustering)
    await renderTreeForSelectedOG();
  },
  { deep: true }
);


// Watch for phyloTree state changes (reset button, external collapse changes)
watch(
  () => visualizationStore.phyloTree.resetCounter,
  async (newCounter, oldCounter) => {
    if (newCounter !== oldCounter) {
      console.log('[PhylogeneticTree] Reset triggered, resetting zoom and re-rendering');
      
      // Reset the D3 zoom transform on the SVG
      if (phylotreeContainer.value && currentZoomBehavior) {
        const svgElement = phylotreeContainer.value.querySelector('svg');
        if (svgElement) {
          const svgSel = d3.select<SVGSVGElement, unknown>(svgElement);
          svgSel.call(currentZoomBehavior.transform, d3.zoomIdentity);
          console.log('[PhylogeneticTree] D3 zoom reset to identity');
        }
      }
      
      await renderTreeForSelectedOG();
    }
  }
);


</script>

