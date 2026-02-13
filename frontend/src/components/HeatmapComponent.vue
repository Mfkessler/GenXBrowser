<template>
  <main class="flex flex-col h-full overflow-hidden">
    <div class="flex justify-between px-2 items-center mb-2 flex-shrink-0">
      <div class="text-gray-500 font-medium flex items-center space-x-2">
        <DropdownMenu
          :modelValue="localTableName"
          :options="tableNameOptions"
          @update:modelValue="
            (val) => {
              localTableName = val;
              emit('update:tableName', val); // emit to parent that selected table changed
            }
          "
        />
        <span class="pl-2 text-xs whitespace-nowrap"
        >({{ getEntityCountLabel() }}: {{ rowCount }})</span
        >
      </div>
      <div class="flex space-x-2">
        <span v-tooltip="props.existingTables.length === Object.keys(props.allTables).length ? 'All heatmaps already shown' : 'Add another heatmap'">
        <button
          aria-label="Add another heatmap"
          @click="addHeatmap"
          :disabled="
            props.existingTables.length === Object.keys(props.allTables).length
          "
          class="p-2 rounded-md text-primary-500 border border-primary-500"
          :class="{
            'disabled:opacity-50':
              props.existingTables.length ===
              Object.keys(props.allTables).length,
            'hover:bg-primary-500 hover:text-white':
              props.existingTables.length !==
              Object.keys(props.allTables).length,
          }"
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
        </span>

        <span v-tooltip="existingTables.length === 1 ? 'Cannot remove last heatmap' : 'Remove heatmap'">
        <button
          aria-label="Remove heatmap"
          @click="removeHeatmap"
          :disabled="existingTables.length === 1"
          class="p-2 rounded-md text-accent1-500 border border-accent1-500"
          :class="{
            'disabled:opacity-50': existingTables.length === 1,
            'hover:bg-accent1-500 hover:text-white': existingTables.length > 1,
          }"
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
        </span>

        <button
          aria-label="Share the heatmap"
          @click="showShareOverlay = true"
          class="p-2 rounded-md text-primary-500 border border-primary-500 hover:bg-primary-500 hover:text-white"
          v-tooltip="'Share the heatmap'"
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
          aria-label="Configure the visuals of the heatmap"
          @click="openSettingsOverlay"
          class="p-2 rounded-md text-white bg-accent1-900 border border-accent1-900 hover:bg-white hover:text-accent1-900"
          v-tooltip="'Configure the visuals of the heatmap'"
        >
          <!-- SVG icon as before -->
          <svg
            xmlns="http://www.w3.org/2000/svg"
            class="h-5 w-5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
          >
            <path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z" />
            <path
              d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1Z"
            />
          </svg>
        </button>
      </div>
    </div>
    <div
      v-if="rowCount <= 1000 && rowCount > 0"
      class="border border-gray-300 rounded-md bg-white flex-grow flex flex-col min-h-0 overflow-hidden"
    >
      <div class="flex-grow relative w-full min-h-0 overflow-hidden">
        <LoadingOverlay v-if="loading"/>
        <div ref="heatmapContainer" class="w-full h-full"></div>
      </div>
    </div>

    <!-- Show loading spinner when loading and rowCount is 0 or too high -->
    <div v-else-if="loading" class="flex-grow relative border border-gray-300 rounded-md bg-white min-h-[300px]">
      <LoadingOverlay size="md" />
    </div>

    <div v-else>
      <NoDataComponent :rowCount="rowCount"/>
    </div>

    <!-- Conditionally render the ShareOverlay -->
    <ShareOverlay
      v-if="showShareOverlay"
      :show="true"
      :showLink="true"
      :htmlContainer="ref(heatmapContainer)"
      @close="showShareOverlay = false"
    />
    
    <!-- Tooltip Modal for detailed metadata -->
    <TooltipModal
      :show="showTooltipModal"
      :rowData="selectedRowData"
      :tableName="props.tableName"
      :idColumn="idColumn"
      :heatmapCols="heatmapCols"
      :columnValue="selectedColumnValue"
      :cellValue="selectedCellValue"
      @close="closeTooltipModal"
    />
  </main>
</template>
<script setup lang="ts">
import axios from "axios";
import * as d3 from "d3";
import {lowerCase} from "lodash-es";
import {storeToRefs} from "pinia";
import {
  computed,
  inject,
  nextTick,
  onMounted,
  onBeforeUnmount,
  ref,
  type Ref,
  watch,
} from "vue";

import DropdownMenu from "./DropdownMenu.vue";
import {COLORSCALES, getCategoricalColors} from "@/shared/Colorscales";
import {useColumnsStore} from "@/stores/columns";
import {API_BASE_URL, type Config} from "@/shared/Config";
import {useFiltersStore} from "@/stores/filters";
import { useFilterSeparation } from "@/shared/useFilterSeparation";
import LoadingOverlay from "./LoadingOverlay.vue";
import type {MetaFormat} from "@/shared/MetaFormat";
import NoDataComponent from "./NoDataComponent.vue";
import type {RowType} from "@/shared/RowType";
import {beautifyLabel, compareValues} from "@/shared/utils";
import ShareOverlay from "./ShareOverlay.vue";
import {useVisualizationStore} from "@/stores/visualization";
import TooltipModal from "./TooltipModal.vue";
import { getDisplayName, sequenceFields, verboseFields } from "@/shared/metadataDisplayNames";
import { getEntityCountLabel } from "@/shared/dataTypeLabels";
import { useClustering } from "@/shared/useClustering";
import { createVisibleColorMapping, type SharedColorRegistry } from "@/shared/colorMapping";

// TODO: Add gene detail view

const config = inject("config") as Config;
const sharedColorRegistry = inject<SharedColorRegistry>('sharedColorRegistry', undefined);
const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const columnStore = useColumnsStore();
const { filters, geneFilters, sampleFilters, getMergedGeneFilters } = useFilterSeparation();
const { performClustering, isComputing: isClusteringComputing } = useClustering();

// Per-dataset merged gene filters (includes per-dataset ID filter)
const mergedGeneFilters = computed(() => getMergedGeneFilters(props.tableName).value);

const sidebarOpen = inject("sidebarOpen") as Ref<boolean> | undefined; //Provided by App.vue

const props = defineProps<{
  tableName: string;
  existingTables: string[];
  allTables: Record<string, string>;
}>();

const localTableName = ref(props.tableName);
const tableNameOptions = computed(() => {
  return Object.fromEntries(
    Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) || key === props.tableName,
    ),
  );
});

const loading = ref(false);
const showShareOverlay = ref(false);
const showTooltipModal = ref(false);
const selectedRowData = ref<RowType | null>(null);
const selectedColumnValue = ref("");
const selectedCellValue = ref<string | number>("");

const closeTooltipModal = () => {
  showTooltipModal.value = false;
  selectedRowData.value = null;
  selectedColumnValue.value = "";
  selectedCellValue.value = "";
};

const error = ref("");
const rowCount = ref(0);
const rows = ref<RowType[]>([]);
const processedRows = ref<RowType[]>([]);
const sortedRows = ref<RowType[]>([]);
const columnNames = ref<string[]>([]);
const dataColumnNames = ref<string[]>([]);
const columns = ref<RowType[]>([]);
const sortedColumns = ref<RowType[]>([]);
const sideColorCache: Record<string, Record<string, string>> = {};

const heatmapContainer = ref<HTMLDivElement | null>(null);

// geneFilters and sampleFilters are now provided by useFilterSeparation composable

const sortedColsKeys = computed(() =>
  sortedColumns.value.map((col) => col.column_name ?? "").filter(Boolean),
);

const visibleColumns = computed(() => {
  if (!visualizationStore.hideEmpty) return sortedColsKeys.value;
  const presentColumns = new Set<string>();
  for (const row of rows.value) {
    for (const col of sortedColsKeys.value) {
      if (row[col] !== undefined && row[col] !== "[BLOB]") {
        presentColumns.add(col);
      }
    }
  }
  return sortedColsKeys.value.filter((col) => presentColumns.has(col));
});

// Reactive references for TooltipModal
const idColumn = computed(() => config.visualization.id_column);
const heatmapCols = computed(() => visibleColumns.value);

// Helper
function getColumnKeys(dataRows: RowType[]): string[] {
  return [...new Set(dataRows.flatMap((row) => Object.keys(row)))];
}

// Fetch data
async function fetchAndPrepareData() {
  loading.value = true;
  error.value = "";
  try {
    //COUNT
    const {data: count} = await axios.post(
      `${API_BASE_URL}/api/count`,
      {
        table_name: props.tableName,
        filters: mergedGeneFilters.value,
      },
    );

    rowCount.value = count.count;

    //Process data fetching only when there is <= 1000 and > 0
    if (rowCount.value <= 1000 && rowCount.value > 0) {
      //DATA
      console.log('Heatmap - Fetching data with expression mode:', {
        optionId: visualizationStore.expressionDisplay.optionId,
        layer: visualizationStore.expressionDisplay.layer,
        transform: visualizationStore.expressionDisplay.transform
      });
      
      const {data: responseData} = await axios.post(
        `${API_BASE_URL}/api/data`,
        {
          table_name: props.tableName,
          filters: mergedGeneFilters.value,
          sample_filters: sampleFilters.value,
          layer: visualizationStore.expressionDisplay.layer,
          transform: visualizationStore.expressionDisplay.transform,
        },
      );

      // Extract data and layer metadata from response
      const data = responseData.data || responseData;
      const layerMetadata = responseData.layer_metadata;
      
      // Optional: Log layer info for debugging
      if (layerMetadata) {
        console.log('Expression Layer:', layerMetadata.layer_used);
        console.log('Transform:', layerMetadata.transform);
        console.log('Reasoning:', layerMetadata.layer_reasoning);
      }

      rows.value = Array.isArray(data)
        ? maskRows(data, config.visualization.hide_columns)
        : [];

      columnNames.value = getColumnKeys(rows.value);

      //DATA_COLUMNS
      const columnRes = await axios.get<MetaFormat[]>(
        `${API_BASE_URL}/api/columns`,
        {params: {table_name: props.tableName, meta: false}},
      );
      dataColumnNames.value = columnRes.data.map((c) => c.column_name);

      //METADATA
      const {data: metaResponseData} = await axios.post(
        `${API_BASE_URL}/api/data`,
        {
          table_name: props.tableName + "_meta",
          filters: {},
        },
      );

      const colData = metaResponseData.data || metaResponseData;
      columns.value = (Array.isArray(colData) ? colData : []).filter((meta: RowType) =>
        dataColumnNames.value.includes(meta.column_name as string),
      );

      sortedRows.value = calculateSortedRows(processedRows.value);
      sortedColumns.value = calculateSortedColumns(columns.value);

      processedRows.value = calculateProcessedRows();

      // Initialize tooltip fields with all available metadata fields except sequences and verbose fields
      if (visualizationStore.tooltipFields.length === 0 && rows.value.length > 0) {
        const firstRow = rows.value[0];
        const allFields = Object.keys(firstRow).filter(
          (key) => !dataColumnNames.value.includes(key) && key !== idColumn.value
        );
        
        // Exclude sequence fields and verbose fields by default
        const excludedFields = [...sequenceFields, ...verboseFields];
        const defaultFields = allFields.filter(
          (field) => !excludedFields.includes(field)
        );
        
        visualizationStore.setTooltipFields(defaultFields);
      }
      
      // Initialize default SideColors if not already set
      const rowColumnNames = columnNames.value.filter((c) => !dataColumnNames.value.includes(c));
      // Use columnsStore.colColumns which includes 'tissue_types'
      const colColumnNames = columnStore.colColumns.map((c) => c.column_name);
      visualizationStore.initializeDefaultSideColors(rowColumnNames, colColumnNames);

      recalculateData(); // recalc after new data
      
      // Trigger re-clustering if clustering is enabled (when data changes)
      const { clusterRows, clusterCols } = visualizationStore.clustering;
      if ((clusterRows || clusterCols) && processedRows.value.length > 0) {
        await performClustering(
          processedRows.value, 
          dataColumnNames.value,
          props.tableName,
          mergedGeneFilters.value,
          sampleFilters.value
        );
        recalculateData(); // recalc with new cluster order
      }

      await nextTick();
      // Wait for layout to stabilize — on first load with multiple heatmaps,
      // the flex container may not have final dimensions after nextTick alone.
      // Use multiple animation frames to ensure flex layout is complete.
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      await nextTick();
      renderHeatmap();
    }
  } catch (e) {
    console.error("Error fetching data:", e);
    error.value = "Failed to load data.";
  } finally {
    loading.value = false;
  }
}

// Preprocessing
function maskRow(
  row: RowType,
  hide: string[],
  placeholder = "[BLOB]",
): RowType {
  if (!hide.length) return row;
  const masked: RowType = {...row};
  for (const col of hide) {
    if (col in masked) masked[col] = placeholder;
  }
  return masked;
}

function maskRows(
  dataRows: RowType[],
  hideCols: string[],
  placeholder = "[BLOB]",
): RowType[] {
  if (!hideCols.length) return dataRows;
  return dataRows.map((row) => maskRow(row, hideCols, placeholder));
}

// Processing
function recalculateData() {
  sortedRows.value = calculateSortedRows(processedRows.value);
  sortedColumns.value = calculateSortedColumns(columns.value);

  // Sync rows with sorted data to reflect reorder in UI parts bound to rows
  rows.value = sortedRows.value;

  //Sync of the columns happens in visibleColumns
}

function calculateProcessedRows(): RowType[] {
  // With backend layer/transform support, no client-side processing needed
  // Backend now handles layer selection and transformations (log2, zscore)
  // This function can be simplified or removed entirely
  return rows.value;
}

function calculateSortedRows(processed: RowType[]): RowType[] {
  if (!processed || processed.length === 0) return [];
  
  // Check if clustering is enabled and we have cluster order
  const { clusterRows, rowOrder: clusterRowOrder } = visualizationStore.clustering;
  
  if (clusterRows && clusterRowOrder && clusterRowOrder.length === processed.length) {
    // Apply cluster ordering
    return clusterRowOrder.map(index => processed[index]);
  }
  
  // Fall back to standard sorting
  const primaryKey = visualizationStore.rowOrder.name;
  const primaryOrder = visualizationStore.rowOrder.order;

  const sorted = [...processed].sort((a, b) => {
    const compPrimary = compareValues(
      a[primaryKey],
      b[primaryKey],
      primaryOrder,
    );
    if (compPrimary !== 0) return compPrimary;
    return compareValues(a[idColumn.value], b[idColumn.value], "asc");
  });

  return sorted;
}

function calculateSortedColumns(metaData: RowType[]): RowType[] {
  if (!metaData || metaData.length === 0) return [];

  // Check if clustering is enabled and we have cluster order
  const { clusterCols, colOrder: clusterColOrder } = visualizationStore.clustering;
  
  if (clusterCols && clusterColOrder && clusterColOrder.length === metaData.length) {
    // Apply cluster ordering
    return clusterColOrder.map(index => metaData[index]);
  }
  
  // Fall back to standard sorting
  const primaryKey = visualizationStore.colOrder.name;
  const primaryOrder = visualizationStore.colOrder.order;

  const sorted = [...metaData].sort((a, b) => {
    // For tissue_types, use the tissue_col field
    const actualPrimaryKey = primaryKey === "tissue_types" ? "tissue_col" : primaryKey;
    const compPrimary = compareValues(
      a[actualPrimaryKey],
      b[actualPrimaryKey],
      primaryOrder,
    );
    if (compPrimary !== 0) return compPrimary;

    if (primaryKey !== "tissue_types") {
      const compTissue = compareValues(
        a.tissue_col ?? "",
        b.tissue_col ?? "",
        "asc",
      );
      if (compTissue !== 0) return compTissue;
    }

    // Fallback alphabetical by column_name ascending
    return ((a.column_name as string) ?? "").localeCompare(
      (b.column_name as string) ?? "",
    );
  });

  return sorted;
}

//Heatmap
function renderColorLegend(
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>,
  margin: { top: number; right: number; bottom: number; left: number },
  colorScale: d3.ScaleSequential<string>,
  legendWidth: number,
) {
  const svgWidth = +svg.attr("width");
  const svgHeight = +svg.attr("height");

  const legendHeight = svgHeight - margin.top - margin.bottom;

  // Create gradient definition
  const defs = svg.append("defs");
  const gradient = defs
    .append("linearGradient")
    .attr("id", "colorLegend")
    .attr("x1", "0%")
    .attr("y1", "100%") // from bottom to top
    .attr("x2", "0%")
    .attr("y2", "0%");

  // Stops from 0 to 1 with small step
  const domain = colorScale.domain();
  gradient
    .selectAll("stop")
    .data(d3.range(0, 1.01, 0.05))
    .enter()
    .append("stop")
    .attr("offset", (d) => `${d * 100}%`)
    .attr("stop-color", (d) =>
      colorScale(domain[0] + d * (domain[1] - domain[0])),
    );

  // Create legend group positioned at right side
  const legend = svg
    .append("g")
    .attr(
      "transform",
      `translate(${svgWidth - margin.right + 5}, ${margin.top})`,
    );

  // Add gradient rectangle
  legend
    .append("rect")
    .attr("width", legendWidth)
    .attr("height", legendHeight)
    .style("fill", "url(#colorLegend)");

  // Scale for the legend axis according to colorScale domain
  const legendScale = d3
    .scaleLinear()
    .domain([domain[0], domain[1]])
    .range([legendHeight, 0]);

  const legendAxis = d3.axisRight(legendScale).ticks(20).tickSize(6);

  // Add axis group
  legend
    .append("g")
    .attr("transform", `translate(${legendWidth}, 0)`)
    .call(legendAxis)
    .call((g) => g.select(".domain").remove());
}

// Local createVisibleColorMapping removed — now imported from @/shared/colorMapping

async function getOrCreateSideColorMapping(
  column_name: string,
  colType: string,
) {
  if (sideColorCache[column_name]) {
    return sideColorCache[column_name];
  }

  try {
    if (colType === "double precision" || colType === "bigint") {
      const {data} = await axios.get(
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

      sideColorCache[column_name] = mapping;
      return mapping;
    } else if (colType === "boolean") {
      const terms = [true, false, null];
      const range = ["#36a2eb", "#e74c3c", "#ccc"];
      const scale = d3.scaleOrdinal().domain(terms).range(range);

      const mapping = {};
      terms.forEach((term) => {
        mapping[term] = scale(term);
      });

      sideColorCache[column_name] = mapping;
      return mapping;
    } else if (column_name === "tissue_types") {
      // Get unique tissue values from column metadata
      const tissueValues = sortedColumns.value.map((meta) => meta.tissue_col ?? meta.column_name);
      const uniqueTissues = [...new Set(tissueValues)].filter(Boolean);
      
      // Use dynamic color palette that scales to any number of tissues
      const colors = getCategoricalColors(uniqueTissues.length);
      const scale = d3.scaleOrdinal().domain(uniqueTissues).range(colors);

      const mapping = {};
      uniqueTissues.forEach((term) => {
        mapping[term] = scale(term);
      });

      sideColorCache[column_name] = mapping;
      return mapping;
    } else {
      const response = await axios.get(`${API_BASE_URL}/api/col`, {
        params: {column_name},
      });
      const terms = response.data.terms;
      
      // Use dynamic color palette
      const colors = getCategoricalColors(terms.length);
      const scale = d3.scaleOrdinal().domain(terms).range(colors);

      const mapping = {};
      terms.forEach((term) => {
        mapping[term] = scale(term);
      });

      sideColorCache[column_name] = mapping;
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

function getSideColorAttributeValues(dataSource, colName, colType) {
  return dataSource.map((entry) => {
    const val = entry[colName];
    if (colType === "array") {
      if (Array.isArray(val) && val.length > 0) {
        // For array columns, return the first valid non-empty term
        // The backend already split these properly via get_unique_values()
        const validTerms = val.filter(v => v && String(v).trim());
        if (validTerms.length > 0) {
          // Return first term - it will match with the unique values from /api/col
          return String(validTerms[0]);
        }
      }
      return "";
    }
    if (colType === "boolean") {
      if (typeof val === "boolean") return val;
      return null;
    }
    if (colType === "double precision" || colType === "bigint") {
      return typeof val === "number" ? val : null;
    }
    // Fallback for other types
    return String(val ?? "");
  });
}

// Generalized function for both row and column side color rendering
async function renderSideColors({
                                  svg,
                                  margin,
                                  dimensionSize,
                                  labels,
                                  attributeValues,
                                  column_name,
                                  colType,
                                  xOffset = 0,
                                  yOffset = 0,
                                  orientation = "row", // 'row' or 'col'
                                  labelWidth = 40,
                                }) {
  if (
    (orientation === "row" && !visualizationStore.rowSideColors) ||
    (orientation === "col" && !visualizationStore.colSideColors)
  )
    return;

  loading.value = true;

  try {
    // Register values with shared registry for cross-plot consistency, then get mapping
    if (sharedColorRegistry) {
      sharedColorRegistry.registerValues(column_name, colType, attributeValues);
    }
    const colorMap = (sharedColorRegistry && sharedColorRegistry.getMapping(column_name))
      ?? createVisibleColorMapping(column_name, colType, attributeValues);

    // Dimension calculations
    const colorSize = dimensionSize * 0.75;

    const svgWidth = +svg.attr("width");
    const svgHeight = +svg.attr("height");

    // Scale for band positioning
    let scale;
    if (orientation === "row") {
      scale = d3
        .scaleBand()
        .domain(labels)
        .range([0, svgHeight - margin.top - margin.bottom])
        .padding(0);
    } else {
      scale = d3
        .scaleBand()
        .domain(labels)
        .range([0, svgWidth - margin.left - margin.right])
        .padding(0);
    }

    const containerGroup = svg
      .append("g")
      .attr("transform", `translate(${xOffset}, ${yOffset})`);

    // Draw rectangles
    const rects = containerGroup
      .selectAll("rect")
      .data(attributeValues)
      .join("rect");

    if (orientation === "row") {
      rects
        .attr("x", 0)
        .attr("y", (d, i) => scale(labels[i]))
        .attr("width", colorSize)
        .attr("height", scale.bandwidth())
        .attr("fill", (d) => {
          if (
            (colType === "double precision" || colType === "bigint") &&
            d !== null &&
            d !== undefined
          ) {
            return colorMap.getColor(d) ?? "#eeeeee";
          }
          return colorMap[d] ?? "#eeeeee";
        });
    } else {
      rects
        .attr("x", (d, i) => scale(labels[i]))
        .attr("y", 0)
        .attr("width", scale.bandwidth())
        .attr("height", colorSize)
        .attr("fill", (d) => {
          if (
            (colType === "double precision" || colType === "bigint") &&
            d !== null &&
            d !== undefined
          ) {
            return colorMap.getColor(d) ?? "#eeeeee";
          }
          return colorMap[d] ?? "#eeeeee";
        });
    }

    // Tooltip, unified for both
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
          // For numeric columns with buckets, show the actual value (not the bucket range)
          const formattedValue = Number.isInteger(d) ? d.toLocaleString() : d.toFixed(2);
          tooltipText = `<strong>${beautifyLabel(column_name)}:</strong> ${formattedValue}`;
        } else {
          tooltipText = `<strong>${beautifyLabel(column_name)}:</strong> ${d}`;
        }

        tooltip.html(tooltipText);
        tooltip.style("visibility", "visible");
      })
      .on("mousemove", function (event) {
        if (!svg.node().parentNode) return;
        const containerRect = svg.node().parentNode.getBoundingClientRect();
        const tooltipNode = tooltip.node();
        if (!tooltipNode) return;
        const tooltipRect = tooltipNode.getBoundingClientRect();

        const offsetX = 10;
        const offsetY = 10;
        let xPos = event.clientX - containerRect.left + offsetX;
        let yPos = event.clientY - containerRect.top + offsetY;

        if (orientation === "row") {
          if (xPos + tooltipRect.width > containerRect.width) {
            xPos =
              event.clientX - containerRect.left - tooltipRect.width - offsetX;
          }
          if (yPos + tooltipRect.height > containerRect.height) {
            yPos =
              event.clientY - containerRect.top - tooltipRect.height - offsetY;
          }
        } else {
          yPos = event.clientY - containerRect.top + colorSize + offsetY;
          if (xPos + tooltipRect.width > containerRect.width) {
            xPos =
              event.clientX - containerRect.left - tooltipRect.width - offsetX;
          }
          if (yPos + tooltipRect.height > containerRect.height) {
            yPos =
              event.clientY - containerRect.top - tooltipRect.height - offsetY;
          }
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
          // Find bin for clicked value
          const bin = colorMap.bins.find(
            (b) => d >= b.bucket_lower && d <= b.bucket_upper,
          );
          if (bin) {
            filtersStore.setFilter(column_name, {
              value: [bin.bucket_lower, bin.bucket_upper],
              strict: false,
            });
          } else {
            // Fallback if no bin found, set raw value
            filtersStore.setFilter(column_name, {value: d, strict: false});
          }
        } else {
          // For non-numeric or other types, keep existing behavior
          filtersStore.setFilter(column_name, {value: d, strict: false});
        }
      });

    // Label group
    const labelGroup = svg
      .append("g")
      .attr(
        "transform",
        orientation === "row"
          ? `translate(${xOffset}, ${yOffset + scale.bandwidth() * scale.domain().length + 5})`
          : `translate(${margin.left - labelWidth}, ${yOffset + colorSize / 2})`,
      );

    labelGroup
      .append("text")
      .text(getDisplayName(column_name))
      .attr("x", orientation === "row" ? 0 : labelWidth - 5)
      .attr("y", orientation === "row" ? colorSize / 2 : 0)
      .attr("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .attr("transform", orientation === "row" ? "rotate(270)" : "rotate(0)")
      .style("font-size", "0.75rem");
  } catch (err) {
    console.error(`Error rendering ${orientation} side colors:`, err);
  } finally {
    loading.value = false;
  }
}

function resetHeatmap() {
  if (!heatmapContainer.value) return;
  d3.select(heatmapContainer.value).selectAll("*").remove();
}

async function renderHeatmap() {
  if (
    !heatmapContainer.value ||
    !sortedRows.value.length ||
    !visibleColumns.value.length
  ) {
    return;
  }

  // Guard: if the container hasn't been laid out yet (zero dimensions),
  // defer rendering until the browser has completed layout.
  const container = heatmapContainer.value;
  if (container.clientWidth === 0 || container.clientHeight === 0) {
    // When multiple heatmaps load simultaneously, the flex layout may not have
    // stabilized yet. Retry with increasing delays to give the layout time to complete.
    await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
    await nextTick();
    if (!heatmapContainer.value || heatmapContainer.value.clientWidth === 0 || heatmapContainer.value.clientHeight === 0) {
      // Schedule a retry after a short delay to allow flex layout to stabilize
      setTimeout(() => {
        if (heatmapContainer.value && heatmapContainer.value.clientWidth > 0 && heatmapContainer.value.clientHeight > 0) {
          renderHeatmap();
        }
      }, 100);
      return;
    }
  }

  resetHeatmap();

  const width = container.clientWidth || 500;
  const height = container.clientHeight || 400;

  const legendWidth = 30;
  const sideColorWidth = 18;
  const sideColorGap = 2;

  let totalColSideColorHeight = 0;
  let totalRowSideColorWidth = 0;

  const margin = {top: 50, right: 20, bottom: 20, left: 20};

  if (visualizationStore.rowLabel) {
    margin.left += 100;
  }

  if (visualizationStore.colLabel) {
    margin.bottom += 70;
  }

  if (visualizationStore.rowSideColors.length > 0) {
    totalRowSideColorWidth =
      visualizationStore.rowSideColors.length * (sideColorWidth + sideColorGap);
    margin.left += totalRowSideColorWidth;
    margin.bottom = Math.max(100, margin.bottom);
  }

  if (visualizationStore.colSideColors.length > 0) {
    totalColSideColorHeight =
      visualizationStore.colSideColors.length * (sideColorWidth + sideColorGap);
    margin.top += totalColSideColorHeight
    margin.left = Math.max(100, margin.left);
  }

  if (visualizationStore.legend) {
    margin.right = legendWidth + 50;
  }

  const svgW = width - margin.left - margin.right;
  const svgH = height - margin.top - margin.bottom;
  
  const svg = d3
    .select(container)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  svg
    .append("text")
    .attr("x", width / 2) // center horizontally
    .attr("y", 50 / 2) // position above the plot area, adjust as needed
    .attr("text-anchor", "middle") // center the text
    .attr("font-size", "16px")
    .attr("font-style", "italic")
    .text(beautifyLabel(localTableName.value));

  const data = sortedRows.value;
  console.log(data)
  const heatmapCols = visibleColumns.value;
  const currentIdColumn = idColumn.value;
  
  // Determine if we should use deferred event binding for large datasets
  const totalCells = data.length * heatmapCols.length;
  const isLargeDataset = totalCells > 10000; // Defer events for > 10k cells

  //X/Y Labels
  const yLabels = data.map((row) =>
    row[currentIdColumn] !== undefined ? String(row[currentIdColumn]) : "",
  );
  const xLabels = heatmapCols;

  //console.log(xLabels);
  //console.log(yLabels);

  const x = d3.scaleBand().domain(xLabels).range([0, svgW]).padding(0);
  const y = d3.scaleBand().domain(yLabels).range([0, svgH]).padding(0);

  //Colorscaling
  const allCellVals = data
    .flatMap((row: RowType) =>
      heatmapCols.map((c) => {
        const val = row[c];
        return val === "[BLOB]" ? NaN : +val;
      }),
    )
    .filter((v) => !isNaN(v));

  const colorScale = d3
    .scaleSequential(
      COLORSCALES[visualizationStore.colorScale] as (t: number) => string,
    )
    .domain([d3.min(allCellVals) ?? 0, d3.max(allCellVals) ?? 1]);

  // Calculate label thinning for readability
  // Approximate height/width per label to determine skip interval
  const minLabelSpacing = 12; // minimum pixels between labels
  const cellWidth = x.bandwidth();
  const cellHeight = y.bandwidth();
  
  // Calculate skip intervals (show every nth label)
  const xLabelSkip = cellWidth < minLabelSpacing ? Math.ceil(minLabelSpacing / cellWidth) : 1;
  const yLabelSkip = cellHeight < minLabelSpacing ? Math.ceil(minLabelSpacing / cellHeight) : 1;

  // Conditionally render X-axis with label thinning
  if (visualizationStore.colLabel) {
    const xAxisGroup = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top + svgH})`)
      .call(d3.axisBottom(x).tickSize(0));
    
    // Apply label thinning - hide labels that would overlap
    xAxisGroup.selectAll("text")
      .attr("transform", "translate(-12,10) rotate(-90)")
      .style("text-anchor", "end")
      .attr("dominant-baseline", "middle")
      .style("font-size", "0.75rem")
      .style("visibility", (_d, i) => (i % xLabelSkip === 0) ? "visible" : "hidden");
  }

  // Conditionally render Y-axis (row labels) with label thinning
  if (visualizationStore.rowLabel) {
    const maxLabelWidth = 100; // Max width for labels
    
    const yAxisGroup = svg
      .append("g")
      .attr(
        "transform",
        `translate(${margin.left - totalRowSideColorWidth},${margin.top})`,
      )
      .call(d3.axisLeft(y));
    
    const yAxisTexts = yAxisGroup.selectAll("text")
      .style("font-size", "10px")
      // Apply label thinning - hide labels that would overlap
      .style("visibility", (_d, i) => (i % yLabelSkip === 0) ? "visible" : "hidden");

    // Truncate long labels and add ellipsis (only for visible labels)
    yAxisTexts.each(function(_d, i) {
      if (i % yLabelSkip !== 0) return; // Skip hidden labels
      
      const textElement = d3.select(this);
      const originalText = textElement.text();
      const textLength = (this as SVGTextElement).getComputedTextLength();
      
      if (textLength > maxLabelWidth) {
        let truncatedText = originalText;
        
        // Binary search for optimal length
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
      .on("mouseover", function(event) {
        const originalText = d3.select(this).text().replace('...', '');
        const fullText = d3.select(this).select("title").text() || originalText;
        
        // Only show tooltip if text is truncated
        if (fullText !== originalText || d3.select(this).text().includes('...')) {
          rowLabelTooltip.html(fullText);
          rowLabelTooltip.style("visibility", "visible");
        }
      })
      .on("mousemove", function(event) {
        if (!heatmapContainer.value) return;
        const containerRect = heatmapContainer.value.getBoundingClientRect();
        
        const xPos = event.clientX - containerRect.left + 10;
        const yPos = event.clientY - containerRect.top - 10;
        
        rowLabelTooltip
          .style("left", xPos + "px")
          .style("top", yPos + "px");
      })
      .on("mouseout", function() {
        rowLabelTooltip.style("visibility", "hidden");
      });
  }


  // Create a single tooltip div once, reuse in events
  const tooltip = d3
    .select(container)
    .append("div")
    .attr("class", "tooltip")
    .style("position", "absolute")
    .style("z-index", "50")
    .style("visibility", "hidden")
    .style("background-color", "#f9fafb") // bg-gray-50
    .style("color", "#374151") // text-gray-700
    .style("font-size", "0.75rem") // text-xs
    .style("border-radius", "0.375rem") // rounded-md
    .style("padding", "0.25rem 0.5rem") // px-2 py-1
    .style("min-width", "8rem")
    .style("white-space", "normal")
    .style("word-wrap", "break-word")
    .style("max-width", "24rem")
    .style("border", "1px solid #d1d5db")
    .style("box-shadow", "0 1px 2px rgba(0,0,0,0.05)")
    .style("pointer-events", "auto")
    .style("user-select", "text");

  let hideTimeout; // global merken

  // Pre-compute cell data for better performance
  const cellData = data.flatMap((row, rowIndex) =>
    heatmapCols.map((col) => ({
      rowIndex,
      col,
      value: row[col],
    }))
  );
  
  const cellGroup = svg
    .append("g")
    .attr("transform", `translate(${margin.left},${margin.top})`);
  
  // Render cells - for large datasets, skip initial event binding
  const rects = cellGroup
    .selectAll("rect")
    .data(cellData)
    .join("rect")
    .attr("x", (d) => x(d.col) ?? 0)
    .attr("y", (d) => y(yLabels[d.rowIndex]) ?? 0)
    .attr("width", x.bandwidth())
    .attr("height", y.bandwidth())
    .attr("fill", (d) => {
      if (d.value === "[BLOB]") return "#ccc";
      const n = +d.value;
      return isNaN(n) ? "#eee" : colorScale(n);
    })
    .attr("stroke", "none");
  
  // Add event handlers (deferred for large datasets to improve initial render)
  const addCellEventHandlers = () => {
    rects
    .on("mouseover", function (event, d) {
      d3.select(this).attr("stroke", "white").style("stroke-width", 2);

      const row = data[d.rowIndex];
      
      // Get metadata columns excluding heatmap columns and id column
      const allMetaCols = Object.keys(row).filter(
        (c) => !heatmapCols.includes(c) && c !== currentIdColumn
      );
      
      // Filter based on user's tooltip field preferences
      let visibleMetaCols = allMetaCols;
      if (visualizationStore.tooltipFields.length > 0) {
        visibleMetaCols = allMetaCols.filter(c => 
          visualizationStore.tooltipFields.includes(c)
        );
      }
      
      // Generate metadata HTML with display names
      const metaHtml = visibleMetaCols
        .map((c) => {
          let value = row[c] ?? "";
          
          // Handle sequences
          if (sequenceFields.includes(c)) {
            if (!visualizationStore.showSequencesInTooltip) {
              return null; // Skip sequences if disabled
            }
            
            const seq = String(value);
            if (seq.length > visualizationStore.sequencePreviewLength) {
              value = seq.substring(0, visualizationStore.sequencePreviewLength) + "... (truncated)";
            }
          }
          
          // Handle arrays - truncate long lists
          if (Array.isArray(value)) {
            if (value.length > 5) {
              value = value.slice(0, 5).join(", ") + ` ... (+${value.length - 5} more)`;
            } else {
              value = value.join(", ");
            }
          }
          
          return `<strong>${getDisplayName(c)}:</strong> ${value}`;
        })
        .filter(Boolean)
        .join("<br>");

      tooltip.html(`
      <b>${getDisplayName(currentIdColumn)}:</b> ${row[currentIdColumn]}<br>
      <b>Column:</b> ${d.col}<br>
      <b>Value:</b> ${d.value}<br>
      ${metaHtml ? `<hr style="margin:4px 0; border-color:#888"/><div>${metaHtml}</div>` : ''}
      <hr style="margin:4px 0; border-color:#888"/>
      <div style="text-align:center; font-size:0.7rem; color:#6b7280;">Right-click for full details</div>
    `);

      tooltip.style("visibility", "visible");

      if (hideTimeout) clearTimeout(hideTimeout); // falls noch aktiv
    })
    .on("mousemove", function (event) {
      if (!heatmapContainer.value) return;
      const containerRect = heatmapContainer.value.getBoundingClientRect();
      const tooltipNode = tooltip.node();
      if (!tooltipNode) return;
      const tooltipRect = tooltipNode.getBoundingClientRect();

      const offsetX = 12; // Abstand von der Maus nach rechts

      // Vertikal: Maus-Mitte
      let yPos = event.clientY - containerRect.top - tooltipRect.height / 2;

      // Horizontal: rechts neben der Maus
      let xPos = event.clientX - containerRect.left + offsetX;

      // Wenn rechts kein Platz → nach links spiegeln
      if (xPos + tooltipRect.width > containerRect.width) {
        xPos = event.clientX - containerRect.left - tooltipRect.width - offsetX;
      }

      // Begrenzung, damit Tooltip nicht außerhalb vom Container hängt
      xPos = Math.max(0, xPos);
      yPos = Math.max(0, Math.min(yPos, containerRect.height - tooltipRect.height));

      tooltip
        .style("left", xPos + "px")
        .style("top", yPos + "px");
    })

    .on("mouseout", function () {
      d3.select(this).attr("stroke", "none");

      // Tooltip nach 300ms schließen (falls Maus nicht in Tooltip wandert)
      hideTimeout = setTimeout(() => {
        tooltip.style("visibility", "hidden");
      }, 800);
    })
    .on("contextmenu", function (event, d) {
      event.preventDefault(); // Prevent browser context menu
      
      const row = data[d.rowIndex];
      
      // Open the tooltip modal with full data
      selectedRowData.value = row;
      selectedColumnValue.value = d.col;
      selectedCellValue.value = d.value;
      showTooltipModal.value = true;
      
      // Hide the hover tooltip
      tooltip.style("visibility", "hidden");
    });
  }; // End of addCellEventHandlers function
  
  // Defer event handler attachment for large datasets
  if (isLargeDataset) {
    // Use requestAnimationFrame to defer event binding
    requestAnimationFrame(() => {
      addCellEventHandlers();
    });
  } else {
    addCellEventHandlers();
  }

  // Add long-press support for touch devices
  let longPressTimer: number | null = null;
  let longPressTriggered = false;
  
  // Use passive event listeners for touch events to improve scroll performance
  const rectElements = cellGroup.selectAll("rect").nodes() as SVGRectElement[];
  rectElements.forEach((rect) => {
    if (!rect) return;
    
    rect.addEventListener("touchstart", function (event: TouchEvent) {
      longPressTriggered = false;
      const target = event.currentTarget as SVGRectElement;
      const d = d3.select(target).datum() as any;
      
      longPressTimer = window.setTimeout(() => {
        longPressTriggered = true;
        
        const row = data[d.rowIndex];
        selectedRowData.value = row;
        selectedColumnValue.value = d.col;
        selectedCellValue.value = d.value;
        showTooltipModal.value = true;
      }, 500); // 500ms long press
    }, { passive: true });
    
    rect.addEventListener("touchend", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
    
    rect.addEventListener("touchmove", function () {
      if (longPressTimer) {
        clearTimeout(longPressTimer);
        longPressTimer = null;
      }
    }, { passive: true });
  });

// --- Tooltip-Events ---
  tooltip
    .on("mouseenter", () => {
      if (hideTimeout) clearTimeout(hideTimeout); // bleibt offen
    })
    .on("mouseleave", () => {
      tooltip.style("visibility", "hidden"); // endgültig schließen
    });


  // Render the color legend on the right
  if (visualizationStore.legend) {
    renderColorLegend(svg, margin, colorScale, legendWidth);
  }

  // Row side colors
  if (visualizationStore.rowSideColors) {
    const sortedRowSideColors = visualizationStore.rowSideColors
      ? [...visualizationStore.rowSideColors].sort((a, b) => a.localeCompare(b))
      : [];
    for (let i = 0; i < sortedRowSideColors.length; i++) {
      const col = sortedRowSideColors[i];
      const colMeta = columnStore.rowColumns.find((c) => c.column_name === col);
      const colType = lowerCase(colMeta?.type) ?? "text";

      // Use helper for values:
      const attributeValues = getSideColorAttributeValues(data, col, colType);

      await renderSideColors({
        svg,
        margin,
        dimensionSize: sideColorWidth,
        labels: yLabels,
        attributeValues,
        column_name: col,
        colType,
        xOffset:
          margin.left -
          totalRowSideColorWidth +
          i * (sideColorWidth + sideColorGap),
        yOffset: margin.top,
        orientation: "row",
      });
    }
  }

  // Column side colors
  if (visualizationStore.colSideColors) {
    const sortedColSideColors = visualizationStore.colSideColors
      ? [...visualizationStore.colSideColors].sort((a, b) => a.localeCompare(b))
      : [];
    for (let i = 0; i < sortedColSideColors.length; i++) {
      const col = sortedColSideColors[i];
      let xLabelsForColoring, attributeValues, colType;
      if (col === "tissue_types") {
        // Filter to only the visible columns
        xLabelsForColoring = dataColumnNames.value.filter((name) =>
          visibleColumns.value.includes(name),
        );
        // Get actual tissue values from column metadata (tissue_col)
        const filteredColMeta = sortedColumns.value.filter((meta) =>
          visibleColumns.value.includes(meta.column_name),
        );
        attributeValues = filteredColMeta.map((meta) => meta.tissue_col ?? meta.column_name);
      } else {
        xLabelsForColoring = heatmapCols; // already filtered by visibleColumns
        // Filter metadata to only visible columns
        const filteredColMeta = sortedColumns.value.filter((meta) =>
          visibleColumns.value.includes(meta.column_name),
        );
        const colMeta = columnStore.colColumns.find(
          (c) => c.column_name === col,
        );
        colType = lowerCase(colMeta?.type) ?? "text";
        // Now attributeValues comes from filtered set!
        attributeValues = getSideColorAttributeValues(
          filteredColMeta,
          col,
          colType,
        );
      }
      await renderSideColors({
        svg,
        margin,
        dimensionSize: sideColorWidth,
        labels: xLabelsForColoring,
        attributeValues,
        column_name: col,
        colType,
        xOffset: margin.left,
        yOffset:
          margin.top -
          totalColSideColorHeight +
          i * (sideColorWidth + sideColorGap),
        orientation: "col",
        labelWidth: 40,
      });
    }
  }
}

//Settings
function openSettingsOverlay() {
  emit("openSettingsOverlay");
}

//AddHeatmap
async function addHeatmap() {
  if (props.existingTables.length !== Object.keys(props.allTables).length) {
    const nextPlausibleTable = Object.entries(props.allTables).filter(
      ([key]) => !props.existingTables.includes(key) && key !== props.tableName,
    )[0][0];

    emit("update:tableName", localTableName.value + "," + nextPlausibleTable);
  }
}

async function removeHeatmap() {
  emit("update:tableName", "");
}

const emit = defineEmits(["openSettingsOverlay", "update:tableName"]);

watch(
  [() => visualizationStore.expressionDisplay, () => filters.value, () => filtersStore.datasetIdFilters],
  async ([expressionDisplay]) => {
    if (!expressionDisplay) return; // guard against unset
    await fetchAndPrepareData();
    await nextTick();
    renderHeatmap();
  },
  {immediate: true, deep: true},
);

watch(
  [
    () => visualizationStore.hideEmpty,
    () => visualizationStore.legend,
    () => visualizationStore.rowOrder.name,
    () => visualizationStore.rowOrder.order,
    () => visualizationStore.colOrder.name,
    () => visualizationStore.colOrder.order,
    () => visualizationStore.colorScale,
    () => visualizationStore.rowLabel,
    () => visualizationStore.colLabel,
    () => visualizationStore.rowSideColors,
    () => visualizationStore.colSideColors,
  ],
  async () => {
    recalculateData();
    await nextTick();
    renderHeatmap();
  },
  {deep: true},
);

watch(
  [sidebarOpen, () => props.existingTables],
  async () => {
    await nextTick();
    setTimeout(() => {
      renderHeatmap();
    }, 300);
  },
  {deep: true},
);

// Watch for clustering settings changes
watch(
  [
    () => visualizationStore.clustering.clusterRows,
    () => visualizationStore.clustering.clusterCols,
    () => visualizationStore.clustering.method,
    () => visualizationStore.clustering.distance,
  ],
  async () => {
    // Trigger clustering when settings change
    if (processedRows.value.length > 0 && dataColumnNames.value.length > 0) {
      await performClustering(
        processedRows.value, 
        dataColumnNames.value,
        props.tableName,
        mergedGeneFilters.value,
        sampleFilters.value
      );
      recalculateData();
      await nextTick();
      renderHeatmap();
    }
  },
  { deep: true }
);

// Watch for cluster order changes (from worker)
watch(
  [
    () => visualizationStore.clustering.rowOrder,
    () => visualizationStore.clustering.colOrder,
  ],
  async () => {
    recalculateData();
    await nextTick();
    renderHeatmap();
  },
  { deep: true }
);

function handleWindowResize() {
  renderHeatmap();
}

onMounted(() => {
  window.addEventListener("resize", handleWindowResize);
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", handleWindowResize);
});
</script>
