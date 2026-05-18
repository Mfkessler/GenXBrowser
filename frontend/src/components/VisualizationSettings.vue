<template>
  <div
    v-if="showSettingsOverlay"
    class="fixed inset-0 flex justify-center items-center z-50"
    style="background-color: rgba(0, 0, 0, 0.5)"
  >
    <div
      class="bg-white p-4 sm:p-6 rounded-lg shadow-lg w-[94vw] sm:w-[90vw] md:w-[70vw] xl:w-[36rem] max-w-[96vw] h-[90vh] flex flex-col"
    >
      <!-- Title -->
      <div class="flex justify-between items-center mb-4">
        <h1 class="text-xl font-bold cursor-default">Visualization Settings</h1>
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
      <div class="flex-grow overflow-y-auto">
        <CollapseWrapper
          v-model="generalIsOpen"
          :disabled="false"
          :deletable="false"
          title="General"
          class="mb-2"
        >
          <!-- Compare: Orthogroup Selection -->
          <div
            v-if="context === 'compare'"
            class="mb-4"
          >
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Orthogroup
              </h3>
              <InfoTooltip
                title="Orthogroup Selection"
                description="Select the orthogroup to compare expression patterns across species."
              />
            </div>
            <DropdownMenu
              :modelValue="store.compare.selectedOrthogroup"
              @update:modelValue="(v: string) => store.setCompareState({ selectedOrthogroup: v })"
              :options="orthogroupOptions || {}"
              placeholder="Select orthogroup"
              class="w-full"
            />
          </div>

          <!-- PhyloTree: Orthogroup Selection -->
          <div
            v-if="context === 'phylogeneticTree'"
            class="mb-4"
          >
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Orthogroup
              </h3>
              <InfoTooltip
                title="Orthogroup Selection"
                description="Select the orthogroup to display the phylogenetic tree for."
              />
            </div>
            <DropdownMenu
              :modelValue="store.phyloTree.selectedOrthogroup"
              @update:modelValue="(v: string) => store.setPhyloTreeState({ selectedOrthogroup: v })"
              :options="phyloTreeOrthogroupOptions || {}"
              placeholder="Select orthogroup"
              class="w-full"
            />
          </div>

          <!-- PhyloTree: Tree-X-Axis (cladogram / phylogram) -->
          <div
            v-if="context === 'phylogeneticTree'"
            class="mb-4"
          >
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Tree axis
              </h3>
              <InfoTooltip
                title="Tree X-axis"
                description="Cladogram ignores branch lengths and aligns all leaves at the right edge (easier to read for skewed trees). Phylogram scales the x-axis by branch length (preserves evolutionary distances)."
              />
            </div>
            <div class="flex gap-2">
              <button
                type="button"
                class="px-3 py-1 text-sm rounded border"
                :class="store.phyloTree.branchLengthMode === 'cladogram' ? 'bg-primary-500 text-white border-primary-500' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
                @click="store.setBranchLengthMode('cladogram')"
              >Cladogram</button>
              <button
                type="button"
                class="px-3 py-1 text-sm rounded border"
                :class="store.phyloTree.branchLengthMode === 'phylogram' ? 'bg-primary-500 text-white border-primary-500' : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'"
                @click="store.setBranchLengthMode('phylogram')"
              >Phylogram</button>
            </div>
          </div>

          <!-- PhyloTree/Compare: Sample grouping column -->
          <div v-if="context === 'phylogeneticTree' || context === 'compare'" class="mb-4">
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Group Samples By
              </h3>
              <InfoTooltip
                title="Sample Grouping"
                description="Select one sample metadata column used to aggregate and label expression values."
              />
            </div>
            <div class="max-h-48 overflow-y-auto border border-gray-200 rounded-md p-2 bg-gray-50 space-y-1">
              <label
                v-for="(label, columnName) in groupingColumnOptions"
                :key="columnName"
                class="flex items-center gap-2 px-2 py-1 text-sm rounded cursor-pointer hover:bg-white"
              >
                <input
                  type="radio"
                  name="sample-grouping-column"
                  :value="columnName"
                  :checked="selectedGroupingColumn === columnName"
                  @change="setGroupingColumn(String(columnName))"
                  class="h-4 w-4 text-primary-600 border-gray-300 focus:ring-primary-500"
                />
                <span class="truncate">{{ label }}</span>
              </label>
              <div v-if="Object.keys(groupingColumnOptions).length === 0" class="text-sm text-gray-500 italic text-center py-3">
                No sample metadata columns available
              </div>
            </div>
          </div>

          <!-- Expression (for Heatmap/PhyloTree - uses expressionDisplay in store) -->
          <div v-if="context !== 'compare' && context !== 'ora'">
            <div class="flex items-center gap-2 mb-2">
              <h3
                class="text-md font-semibold cursor-default text-primary-900"
              >
                Expression
              </h3>
              <InfoTooltip
                title="Expression Display"
                description="Choose how expression data is normalized and transformed. Normalized Values: TPM (within-sample) or TMM (between-sample). Transformations: Log2 or Z-Score for visualization. Raw Data: Unprocessed counts."
              />
            </div>
            <select
              v-model="selectedExpressionOption"
              @change="onExpressionChange"
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 mb-4"
            >
              <optgroup
                v-for="section in EXPRESSION_SECTIONS"
                :key="section.label"
                :label="section.label"
              >
                <option
                  v-for="optId in section.optionIds"
                  :key="optId"
                  :value="optId"
                >
                  {{ getExpressionOption(optId)?.label }}
                </option>
              </optgroup>
            </select>
          </div>

          <!-- Expression (for Compare - uses compare.expression in store) -->
          <div v-if="context === 'compare'">
            <div class="flex items-center gap-2 mb-2">
              <h3
                class="text-md font-semibold cursor-default text-primary-900"
              >
                Expression
              </h3>
              <InfoTooltip
                title="Expression Display"
                description="Choose how expression data is normalized and transformed. Normalized Values: TPM (within-sample) or TMM (between-sample). Transformations: Log2 or Z-Score for visualization. Raw Data: Unprocessed counts."
              />
            </div>
            <select
              :value="store.compare.expression"
              @change="onCompareExpressionChange"
              class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 mb-4"
            >
              <optgroup
                v-for="section in EXPRESSION_SECTIONS"
                :key="section.label"
                :label="section.label"
              >
                <option
                  v-for="optId in section.optionIds"
                  :key="optId"
                  :value="optId"
                >
                  {{ getExpressionOption(optId)?.label }}
                </option>
              </optgroup>
            </select>
          </div>

          <!-- Compare: Plot Type -->
          <div v-if="context === 'compare'" class="mb-4">
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Plot Type
              </h3>
              <InfoTooltip
                title="Plot Type"
                description="Line Plot: Shows individual transcripts and species mean. Box Plot: Shows distribution with quartiles. Violin Plot: Shows full distribution shape."
              />
            </div>
            <DropdownMenu
              :modelValue="store.compare.plotType"
              @update:modelValue="(v: 'line' | 'box' | 'violin') => store.setCompareState({ plotType: v })"
              :options="plotTypeOptions"
              class="w-full"
            />
          </div>

          <!-- Compare: Plot Height -->
          <div v-if="context === 'compare'" class="mb-4">
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Plot Height
              </h3>
            </div>
            <div class="flex items-center gap-3">
              <input
                type="range"
                :value="store.compare.plotHeight"
                @input="(e) => store.setCompareState({ plotHeight: Number((e.target as HTMLInputElement).value) })"
                min="300"
                max="800"
                step="50"
                class="flex-grow h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-primary-600"
              />
              <span class="text-sm font-semibold text-primary-900 min-w-[4rem] text-right">{{ store.compare.plotHeight }}px</span>
            </div>
          </div>

          <!-- Compare: All Transcripts toggle -->
          <div v-if="context === 'compare'" class="mb-4">
            <div class="flex items-center gap-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                All Transcripts
              </h3>
              <InfoTooltip
                title="All Transcripts"
                description="Show all transcripts belonging to matched orthogroups, even if they do not pass the current filter. Example: Filtering by 'MIKC TF Family' finds orthogroups containing MIKC transcripts. Enabling this option shows ALL transcripts within those orthogroups — not just the MIKC members. Additional transcripts are displayed at reduced opacity."
              />
              <div class="ml-auto">
                <ToggleSwitch
                  :modelValue="store.compare.showAllTranscripts"
                  @update:modelValue="(v: boolean) => store.setCompareState({ showAllTranscripts: v })"
                />
              </div>
            </div>
          </div>

          <!-- Heatmap: ColorScale (not for Compare) -->
          <div v-if="context !== 'compare'">
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              ColorScale
            </h3>
            <DropdownMenu
              v-model="store.colorScale"
              :options="colorScaleDropdownOptions"
              class="items-center mb-4"
            />
          </div>

          <!-- Heatmap: Show Legend (not for Compare) -->
          <div v-if="context !== 'compare'" class="flex items-center gap-2 mb-2">
            <h3 class="text-md font-semibold cursor-default text-primary-900">
              Show Legend
            </h3>
            <ToggleSwitch v-model="store.legend" />
          </div>

        </CollapseWrapper>

        <!-- Clustering -->
        <CollapseWrapper
          v-if="context === null || context === 'heatmap' || context === 'phylogeneticTree'"
          v-model="clusteringIsOpen"
          :disabled="false"
          :deletable="false"
          title="Clustering"
          class="mb-2"
        >
          <div class="space-y-4">
            <!-- Cluster Rows Toggle (not for phylogeneticTree - tree defines row order) -->
            <div v-if="context !== 'phylogeneticTree'" class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <h3 class="text-md font-semibold cursor-default text-primary-900">
                  Cluster Rows
                </h3>
                <InfoTooltip
                  title="Row Clustering"
                  description="Group similar genes/transcripts together using hierarchical clustering based on expression patterns across samples."
                />
              </div>
              <ToggleSwitch
                :modelValue="store.clustering.clusterRows"
                @update:modelValue="store.setClusterRows"
              />
            </div>

            <!-- Info for phylogeneticTree about row order -->
            <div v-if="context === 'phylogeneticTree'" class="text-sm text-gray-600 italic">
              Row order is defined by the phylogenetic tree topology.
            </div>

            <!-- Cluster Columns Toggle -->
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <h3 class="text-md font-semibold cursor-default text-primary-900">
                  Cluster {{ context === 'phylogeneticTree' ? 'Sample Groups' : 'Columns' }}
                </h3>
                <InfoTooltip
                  title="Column Clustering"
                  :description="context === 'phylogeneticTree' 
                    ? 'Group similar sample metadata values together based on their expression profiles across species.'
                    : 'Group similar samples together based on their expression profiles.'"
                />
              </div>
              <ToggleSwitch
                :modelValue="store.clustering.clusterCols"
                @update:modelValue="store.setClusterCols"
              />
            </div>

            <!-- Clustering Options (only show if at least one clustering is enabled) -->
            <div v-if="(context !== 'phylogeneticTree' && (store.clustering.clusterRows || store.clustering.clusterCols)) || (context === 'phylogeneticTree' && store.clustering.clusterCols)" class="border-t border-gray-200 pt-4 space-y-4">
              <!-- Linkage Method -->
              <div>
                <div class="flex items-center gap-2 mb-2">
                  <h3 class="text-md font-semibold cursor-default text-primary-900">
                    Linkage Method
                  </h3>
                  <InfoTooltip
                    title="Clustering Linkage"
                    description="Average (UPGMA): Recommended for gene expression. Complete: Produces compact clusters. Ward: Minimizes variance within clusters."
                  />
                </div>
                <DropdownMenu
                  :modelValue="store.clustering.method"
                  @update:modelValue="store.setClusterMethod"
                  :options="clusterMethodOptions"
                  class="w-full"
                />
              </div>

              <!-- Distance Metric -->
              <div>
                <div class="flex items-center gap-2 mb-2">
                  <h3 class="text-md font-semibold cursor-default text-primary-900">
                    Distance Metric
                  </h3>
                  <InfoTooltip
                    title="Distance Metric"
                    description="Correlation (1-r): Best for expression data, captures pattern similarity. Euclidean: Standard distance, sensitive to magnitude differences."
                  />
                </div>
                <DropdownMenu
                  :modelValue="store.clustering.distance"
                  @update:modelValue="store.setClusterDistance"
                  :options="clusterDistanceOptions"
                  class="w-full"
                />
              </div>

              <!-- Computing indicator -->
              <div v-if="store.clustering.isComputing" class="flex items-center gap-2 text-sm text-gray-600">
                <svg class="animate-spin h-4 w-4 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                  <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Computing clusters...</span>
              </div>
            </div>
          </div>
        </CollapseWrapper>

        <!-- Rows -->
        <CollapseWrapper
          v-if="context === null || context === 'heatmap'"
          v-model="rowIsOpen"
          :disabled="false"
          :deletable="false"
          :title="getEntityLabelPlural()"
          class="mb-2"
        >
          <div class="flex items-center gap-2 mb-2">
            <h3 class="text-md font-semibold cursor-default text-primary-900">
              Row Labels
            </h3>
            <ToggleSwitch v-model="store.rowLabel" />
          </div>
          <div>
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              Row Order
            </h3>
            <div class="flex items-center mb-4">
              <DropdownMenu
                :key="Object.keys(rowOrderOptions).length"
                :modelValue="rowOrderName"
                @update:modelValue="selectRowOrder"
                :options="rowOrderOptions"
                placeholder="No metadata sorting"
                class="mr-2"
              />
              <SortToggleButton
                v-model="store.rowOrder.order"
                :disabled="store.clustering.clusterRows || store.rowOrder.name === 'OLO' || !store.rowOrder.name"
              />
            </div>
            <p v-if="orderFeedback.axis === 'row'" class="-mt-2 mb-3 text-xs text-primary-700">
              {{ orderFeedback.message }}
            </p>
          </div>

          <div>
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              RowSideColors
            </h3>
            <div class="flex items-center mb-4">
              <CheckboxSelector
                v-model="store.rowSideColors"
                @update:modelValue="store.setRowSideColors"
                :options="rowSideColorOptions"
                :displayNames="rowSideColorDisplayNames"
              />
            </div>
          </div>
        </CollapseWrapper>
        <!-- Cols -->
        <CollapseWrapper
          v-if="context !== 'ora'"
          v-model="colIsOpen"
          :disabled="false"
          :deletable="false"
          title="Samples"
          class="mb-2"
        >
          <div v-if="context === null || context === 'heatmap'" class="flex items-center gap-2 mb-2">
            <h3 class="text-md font-semibold cursor-default text-primary-900">
              Column Labels
            </h3>
            <ToggleSwitch v-model="store.colLabel" />
          </div>
          <div>
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              Column Order
            </h3>
            <div class="flex items-center mb-4">
              <DropdownMenu
                :modelValue="colOrderName"
                @update:modelValue="selectColOrder"
                :options="colOrderOptions"
                placeholder="No metadata sorting"
                class="mr-2"
              />
              <SortToggleButton
                v-model="store.colOrder.order"
                :disabled="store.clustering.clusterCols || store.colOrder.name === 'OLO' || !store.colOrder.name"
              />
            </div>
            <p v-if="orderFeedback.axis === 'col'" class="-mt-2 mb-3 text-xs text-primary-700">
              {{ orderFeedback.message }}
            </p>
          </div>

          <div class="mb-4">
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              {{ axisOnlyCustomOrder ? 'Custom X-Axis Order' : 'Custom Order' }}
            </h3>
            <div class="border border-gray-200 rounded-md p-3 bg-gray-50 space-y-3">
              <div class="flex items-center justify-between">
                <span class="text-sm font-medium text-gray-700">Enable custom order</span>
                <ToggleSwitch v-model="customOrderEnabled" />
              </div>
              <template v-if="store.customColOrder.enabled">
                <div v-if="!axisOnlyCustomOrder" class="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    class="px-2 py-1 text-xs rounded border"
                    :class="store.customColOrder.mode === 'metadata' ? 'bg-primary-500 text-white border-primary-500' : 'bg-white text-gray-700 border-gray-300'"
                    @click="setCustomOrderMode('metadata')"
                  >By metadata</button>
                  <button
                    type="button"
                    class="px-2 py-1 text-xs rounded border"
                    :class="store.customColOrder.mode === 'samples' ? 'bg-primary-500 text-white border-primary-500' : 'bg-white text-gray-700 border-gray-300'"
                    @click="setCustomOrderMode('samples')"
                  >Sample by sample</button>
                </div>
                <div v-if="axisOnlyCustomOrder || store.customColOrder.mode === 'metadata'" class="space-y-2">
                  <DropdownMenu
                    v-if="!axisOnlyCustomOrder"
                    v-model="customOrderMetadataColumn"
                    :options="customOrderMetadataOptions"
                    class="w-full"
                  />
                  <Draggable
                    v-model="customMetadataValueOrder"
                    :item-key="identityKey"
                    handle=".custom-order-handle"
                    ghost-class="bg-primary-100"
                    class="max-h-48 overflow-y-auto space-y-1"
                  >
                    <template #item="{ element }">
                      <div class="flex items-center gap-2 px-2 py-1 bg-white border border-gray-200 rounded text-sm">
                        <span class="custom-order-handle cursor-grab text-gray-400">::</span>
                        <span class="truncate">{{ element }}</span>
                      </div>
                    </template>
                  </Draggable>
                </div>
                <Draggable
                  v-else-if="!axisOnlyCustomOrder"
                  v-model="customSampleOrder"
                  :item-key="identityKey"
                  handle=".custom-order-handle"
                  ghost-class="bg-primary-100"
                  class="max-h-56 overflow-y-auto space-y-1"
                >
                  <template #item="{ element }">
                    <div class="flex items-center gap-2 px-2 py-1 bg-white border border-gray-200 rounded text-sm">
                      <span class="custom-order-handle cursor-grab text-gray-400">::</span>
                      <span class="truncate">{{ element }}</span>
                    </div>
                  </template>
                </Draggable>
                <button type="button" class="text-xs text-accent1-700 hover:underline" @click="resetCustomOrder">
                  Reset custom order
                </button>
              </template>
            </div>
          </div>

          <div v-if="context === null || context === 'heatmap'">
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              ColSideColors
            </h3>
            <div class="flex items-center mb-4">
              <CheckboxSelector
                :modelValue="store.colSideColors"
                @update:modelValue="store.setColSideColors"
                :options="colSideColorOptions"
                :displayNames="colSideColorDisplayNames"
              />
            </div>
          </div>
        </CollapseWrapper>
        <!-- Tooltip -->
        <CollapseWrapper
          v-if="context === null || context === 'heatmap' || context === 'phylogeneticTree'"
          v-model="tooltipIsOpen"
          :disabled="false"
          :deletable="false"
          title="Tooltip"
          class="mb-2"
        >
          <div>
            <h3 class="text-md font-semibold mb-2 text-primary-900">
              Select Tooltip
            </h3>

            <!-- Deselect All Button -->
            <div class="flex gap-2 mb-3">
              <button
                @click="deselectAllTooltipFields"
                class="px-3 py-1 text-xs bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition-colors"
              >
                Deselect All
              </button>
            </div>

            <!-- Checkboxes for fields -->
            <div
              class="max-h-64 overflow-y-auto border border-gray-200 rounded p-2 mb-4"
            >
              <div
                v-for="field in availableTooltipFields"
                :key="field"
                class="flex items-center mb-2"
              >
                <input
                  :id="`tooltip-field-${field}`"
                  type="checkbox"
                  :checked="isTooltipFieldSelected(field)"
                  @change="toggleTooltipField(field)"
                  class="mr-2 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                />
                <label
                  :for="`tooltip-field-${field}`"
                  class="text-sm cursor-pointer"
                  :class="{
                    'text-gray-400 italic': sequenceFields.includes(field)
                  }"
                >
                  {{ getDisplayName(field) }}
                  <span v-if="sequenceFields.includes(field)" class="text-xs">
                    (sequence)
                  </span>
                </label>
              </div>
              <div
                v-if="availableTooltipFields.length === 0"
                class="text-sm text-gray-500 italic text-center py-4"
              >
                No metadata fields available
              </div>
            </div>

            <!-- Show Sequences Toggle -->
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Show Sequences in Tooltip
              </h3>
              <ToggleSwitch
                :modelValue="store.showSequencesInTooltip"
                @update:modelValue="store.toggleShowSequencesInTooltip"
              />
            </div>

            <!-- Sequence Preview Length -->
            <div v-if="store.showSequencesInTooltip" class="mt-2">
              <label class="text-sm font-medium text-gray-700 mb-1 block">
                Sequence Preview Length (characters)
              </label>
              <input
                :value="store.sequencePreviewLength"
                @input="
                  (e) =>
                    store.setSequencePreviewLength(
                      Number((e.target as HTMLInputElement).value)
                    )
                "
                type="number"
                min="50"
                max="500"
                step="50"
                class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 text-sm"
              />
            </div>
          </div>
        </CollapseWrapper>
        <!-- ORA -->
        <CollapseWrapper
          v-if="context === null || context === 'ora'"
          v-model="oraIsOpen"
          :disabled="false"
          :deletable="false"
          title="ORA"
          class="mb-2"
        >
          <div class="flex items-center gap-2 mb-2">
            <h3 class="text-md font-semibold cursor-default text-primary-900">
              RowSideColors
            </h3>
            <ToggleSwitch v-model="store.oraRowSideColor" />
          </div>
          <div>
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              Column
            </h3>
            <div class="flex items-center mb-4">
              <DropdownMenu
                v-model="store.oraColumnName"
                :options="rowOrderOptions"
                class="mr-2"
              />
            </div>
          </div>
          <div>
            <h3
              class="text-md font-semibold mb-2 cursor-default text-primary-900"
            >
              Order
            </h3>
            <div class="flex items-center mb-4">
              <DropdownMenu
                v-model="store.oraOrder.name"
                :options="ORAORDEROPTIONS"
                class="mr-2"
              />
              <SortToggleButton
                v-model="store.oraOrder.order"
                :disabled="store.oraOrder.name === 'OLO'"
              />
            </div>
          </div>
          <div>
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Significance (FDR q-value)
              </h3>
              <InfoTooltip 
                description="Benjamini-Hochberg FDR-adjusted significance threshold. Lower values = stricter filtering. Standard: 0.01 (1%), Relaxed: 0.05 (5%)" 
              />
            </div>
            <div class="flex items-center mb-4">
              <DropdownMenu
                v-model="store.significance"
                :options="ORASIGNIFICANCEOPTIONS"
                class="mr-2"
              />
            </div>
          </div>
          <div>
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                Maximum Results (Top N)
              </h3>
              <InfoTooltip 
                description="Applied after significance, transcript count, and GO depth filters. Shows the top enriched terms from the entries that pass those criteria, ranked by combined score (-log10(q-value) x gene_ratio)." 
              />
            </div>
            <div class="flex items-center mb-4">
              <input
                type="range"
                v-model.number="localOraTopN"
                min="10"
                max="200"
                step="10"
                class="w-full mr-2"
              />
              <span class="text-sm font-semibold text-primary-900 min-w-[3rem] text-right">{{ localOraTopN }}</span>
            </div>
          </div>
          <div>
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                {{ getMinimumCountLabel() }}
              </h3>
              <InfoTooltip 
                :description="`Minimum number of ${getEntityLabelPluralLower()} from your filtered set that must contain a term for it to be tested. Higher values increase statistical power but may miss rare terms. Standard: 3 ${getEntityLabelPluralLower()}.`" 
              />
            </div>
            <div class="flex items-center mb-4">
              <input
                type="range"
                v-model.number="localOraMinCount"
                min="1"
                max="20"
                step="1"
                class="w-full mr-2"
              />
              <span class="text-sm font-semibold text-primary-900 min-w-[3rem] text-right">{{ localOraMinCount }}</span>
            </div>
          </div>
          <div v-if="showGoDepthFilter">
            <div class="flex items-center gap-2 mb-2">
              <h3 class="text-md font-semibold cursor-default text-primary-900">
                GO Depth (for visual filtering)
              </h3>
              <InfoTooltip 
                title="GO Depth Visual Filtering"
                description="Applied before Top N. Depth 0 turns this filter off; higher values keep terms at that GO depth or deeper before the final Top N entries are selected."
              />
            </div>
            <div class="flex items-center mb-4 gap-3">
              <input
                type="range"
                :value="goDepthValue"
                @input="(e) => store.setOraGoDepthFilter(Number((e.target as HTMLInputElement).value))"
                min="0"
                :max="maxGoDepth"
                step="1"
                class="w-full accent-primary-600"
              />
              <span class="text-sm font-semibold text-primary-900 min-w-[3rem] text-right">
                {{ goDepthValue === 0 ? 'Off' : goDepthValue }}
              </span>
            </div>
          </div>
        </CollapseWrapper>

        <!-- ORA Tooltip Configuration (Separate Category) -->
        <CollapseWrapper
          v-if="context === null || context === 'ora'"
          v-model="oraTooltipIsOpen"
          :disabled="false"
          :deletable="false"
          title="Tooltip"
          class="mb-2"
        >
          <div>
            <h3 class="text-md font-semibold mb-2 text-primary-900">
              Select Tooltip Fields
            </h3>

            <!-- Deselect All Button -->
            <div class="flex gap-2 mb-3">
              <button
                @click="deselectAllOraTooltipFields"
                class="px-3 py-1 text-xs bg-gray-300 text-gray-700 rounded hover:bg-gray-400 transition-colors"
              >
                Deselect All
              </button>
            </div>

            <!-- Checkboxes for ORA tooltip fields -->
            <div
              class="max-h-64 overflow-y-auto border border-gray-200 rounded p-2 mb-4"
            >
              <div
                v-for="field in availableOraTooltipFields"
                :key="field"
                class="flex items-center mb-2"
              >
                <input
                  :id="`ora-tooltip-field-${field}`"
                  type="checkbox"
                  :checked="isOraTooltipFieldSelected(field)"
                  @change="toggleOraTooltipField(field)"
                  :disabled="field.startsWith('go_') && !isGoTermColumn"
                  class="mr-2 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <label
                  :for="`ora-tooltip-field-${field}`"
                  class="text-sm cursor-pointer"
                  :class="{
                    'text-gray-400 italic': field.startsWith('go_') && !isGoTermColumn
                  }"
                >
                  {{ oraTooltipFieldLabels[field] || field }}
                  <span v-if="field.startsWith('go_') && !isGoTermColumn" class="text-xs">
                    (GO only)
                  </span>
                </label>
              </div>
            </div>
          </div>
        </CollapseWrapper>
      </div>

      <!-- Close Button (Bottom) -->
      <button
        @click="store.reset"
        class="mt-4 border-1 border-accent2-900 bg-white text-accent2-900 hover:bg-accent2-100 py-2 rounded-full self-center w-full"
      >
        Reset
      </button>
      <button
        @click="closeOverlay"
        class="mt-2 border-1 border-accent1-900 bg-accent1-100 text-accent1-900 hover:text-accent1-100 hover:bg-accent1-900 py-2 rounded-full self-center w-full"
      >
        Close
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, watch } from "vue";
import Draggable from "vuedraggable";
import axios from "axios";
import { useRoute } from "vue-router";

import { useVisualizationStore } from "@/stores/visualization";

import CheckboxSelector from "./CheckboxSelector.vue";
import CollapseWrapper from "./CollapseWrapper.vue";
import InfoTooltip from "./InfoTooltip.vue";
import { COLORSCALES } from "@/shared/Colorscales";
import { useColumnsStore } from "@/stores/columns";
import { API_BASE_URL, type Config } from "@/shared/Config";
import type { MetaFormat } from "@/shared/MetaFormat";
import type { RowType } from "@/shared/RowType";
import DropdownMenu from "./DropdownMenu.vue";
import SortToggleButton from "./SortToggleButton.vue";
import ToggleSwitch from "./ToggleSwitch.vue";
import { beautifyLabel } from "@/shared/utils";
import {
  EXPRESSION_SECTIONS,
  getExpressionOption,
} from "@/shared/ExpressionDisplay";
import { getDisplayName, sequenceFields } from "@/shared/metadataDisplayNames";
import { getEntityLabelPlural, getMinimumCountLabel, getEntityLabelPluralLower } from "@/shared/dataTypeLabels";

const columnsStore = useColumnsStore();
const route = useRoute();

//TODO
// * Update reset settings to support base column_id (create configStore)

const ORAORDEROPTIONS = {
  // ORA result ordering options
  attr: "Attribute",
  subset_count: "Observed Count",
  background_count: "Background Count",
  gene_ratio: "Gene Ratio",
  fold_enrichment: "Fold Enrichment",
  p_value: "p-value",
};

const ORASIGNIFICANCEOPTIONS = {
  // Significance thresholds for ORA
  "0.05": 0.05,
  "0.01": 0.01,
  "0.001": 0.001,
};

// Clustering options
const clusterMethodOptions = {
  average: "Average (UPGMA)",
  complete: "Complete",
  ward: "Ward",
};

const clusterDistanceOptions = {
  correlation: "Correlation (1-r)",
  euclidean: "Euclidean",
};

const identityKey = (value: string) => value;
const axisOnlyCustomOrder = computed(() => props.context === "compare" || props.context === "phylogeneticTree");

// Compare plot type options
const plotTypeOptions = {
  line: "Line Plot",
  box: "Box Plot",
  violin: "Violin Plot",
};

const props = defineProps<{
  showSettingsOverlay: boolean;
  context: "heatmap" | "ora" | "phylogeneticTree" | "compare" | null;
  // Compare-specific props (optional, only used when context="compare")
  orthogroupOptions?: Record<string, string>;
  // PhyloTree-specific props (optional, only used when context="phylogeneticTree")
  phyloTreeOrthogroupOptions?: Record<string, string>;
}>();

const config = inject("config") as Config;

const emit = defineEmits<{
  (e: "update:showOverlay", show: boolean): void;
}>();

const store = useVisualizationStore();

const rowOrderName = computed({
  get: () => store.rowOrder.name,
  set: (name: string) => store.setRowOrderName(name),
});

const colOrderName = computed({
  get: () => store.colOrder.name,
  set: (name: string) => store.setColOrderName(name),
});

const orderFeedback = ref<{ axis: "row" | "col" | null; message: string }>({ axis: null, message: "" });
let orderFeedbackTimer: ReturnType<typeof setTimeout> | null = null;

function showOrderFeedback(axis: "row" | "col", message: string) {
  if (orderFeedbackTimer) clearTimeout(orderFeedbackTimer);
  orderFeedback.value = { axis, message };
  orderFeedbackTimer = setTimeout(() => {
    orderFeedback.value = { axis: null, message: "" };
    orderFeedbackTimer = null;
  }, 2800);
}

function selectRowOrder(name: string) {
  const replacedClustering = store.clustering.clusterRows && Boolean(name);
  store.setRowOrderName(name);
  if (replacedClustering) {
    showOrderFeedback("row", "Row clustering is off. Row order is active now.");
  }
}

function selectColOrder(name: string) {
  const replacedClustering = store.clustering.clusterCols && Boolean(name);
  store.setColOrderName(name);
  if (replacedClustering) {
    showOrderFeedback("col", "Column clustering is off. Column order is active now.");
  }
}

const generalIsOpen = ref(true);
const clusteringIsOpen = ref(false);
const rowIsOpen = ref(false);
const colIsOpen = ref(false);
const tooltipIsOpen = ref(false);
const oraIsOpen = ref(true); //DEBUG
const oraTooltipIsOpen = ref(false);
const loadingSampleMetadataTables = new Set<string>();

// Local reactive values for ORA sliders with debouncing
const localOraTopN = ref(store.oraTopN);
const localOraMinCount = ref(store.oraMinCount);

// Debounce timers
let oraTopNTimer: ReturnType<typeof setTimeout> | null = null;
let oraMinCountTimer: ReturnType<typeof setTimeout> | null = null;

// Watch local slider values and debounce updates to store
watch(localOraTopN, (newValue) => {
  if (oraTopNTimer) clearTimeout(oraTopNTimer);
  oraTopNTimer = setTimeout(() => {
    store.oraTopN = newValue;
  }, 300); // 300ms debounce delay
});

watch(localOraMinCount, (newValue) => {
  if (oraMinCountTimer) clearTimeout(oraMinCountTimer);
  oraMinCountTimer = setTimeout(() => {
    store.oraMinCount = newValue;
  }, 300); // 300ms debounce delay
});

// Sync local values when store values change externally (e.g., from reset)
watch(() => store.oraTopN, (newValue) => {
  localOraTopN.value = newValue;
});

watch(() => store.oraMinCount, (newValue) => {
  localOraMinCount.value = newValue;
});

// Check if ORA column is a GO term column
const isGoTermColumn = computed(() => {
  const colName = store.oraColumnName.toLowerCase();
  return colName.includes('go') || 
         colName === 'go_terms' ||
         colName === 'gene_ontology' ||
         colName.startsWith('go_');
});

const maxGoDepth = computed(() => Math.max(0, ...store.oraAvailableGoDepths));
const showGoDepthFilter = computed(() => isGoTermColumn.value && maxGoDepth.value > 0);
const goDepthValue = computed(() => {
  const depth = Number(store.oraGoDepthFilter);
  return Number.isInteger(depth) && depth > 0 ? Math.min(depth, maxGoDepth.value) : 0;
});

// Tooltip configuration
const availableTooltipFields = computed(() => {
  // Get all unique metadata fields from row columns
  const hiddenCols = new Set(config.visualization.hide_columns || []);
  return columnsStore.rowColumns
    .map((c) => c.column_name)
    .filter((name) => !hiddenCols.has(name));
});

const isTooltipFieldSelected = (field: string) => {
  // null means uninitialized (all selected)
  if (store.tooltipFields === null) return true;
  return store.tooltipFields.includes(field);
};

const toggleTooltipField = (field: string) => {
  // null means uninitialized — initialize from all available fields first
  const current = store.tooltipFields !== null
    ? [...store.tooltipFields]
    : [...availableTooltipFields.value];
  const index = current.indexOf(field);
  
  if (index === -1) {
    current.push(field);
  } else {
    current.splice(index, 1);
  }
  
  store.setTooltipFields(current);
};

const deselectAllTooltipFields = () => {
  store.setTooltipFields([]);
};

// ORA Tooltip Fields management
const availableOraTooltipFields = [
  'attribute_name',
  'go_name',
  'go_namespace',
  'go_depth',
  'subset_count',
  'expected_count',
  'background_count',
  'fold_enrichment',
  'gene_ratio',
  'p_value',
  'q_value',
  'combined_score',
  'odds_ratio'
];

const oraTooltipFieldLabels = {
  attribute_name: 'Attribute ID',
  go_name: 'GO Term Name',
  go_namespace: 'GO Category',
  go_depth: 'GO Depth',
  subset_count: 'Observed Count',
  expected_count: 'Expected Count',
  background_count: 'Background Count',
  fold_enrichment: 'Fold Enrichment',
  gene_ratio: 'Gene Ratio',
  p_value: 'P-Value',
  q_value: 'Q-Value (FDR)',
  combined_score: 'Combined Score',
  odds_ratio: 'Odds Ratio'
};

const isOraTooltipFieldSelected = (field: string) => {
  return store.oraTooltipFields.includes(field);
};

const toggleOraTooltipField = (field: string) => {
  const current = [...store.oraTooltipFields];
  const index = current.indexOf(field);
  
  if (index === -1) {
    current.push(field);
  } else {
    current.splice(index, 1);
  }
  
  store.setOraTooltipFields(current);
};

const deselectAllOraTooltipFields = () => {
  store.setOraTooltipFields([]);
};

// Expression display management - use computed to stay in sync with store
const selectedExpressionOption = computed({
  get: () => store.expressionDisplay.optionId,
  set: (value: string) => {
    const option = getExpressionOption(value);
    if (option) {
      store.setExpressionDisplay(option.id, option.layer, option.transform);
    }
  }
});

// No longer needed - computed setter handles this
const onExpressionChange = () => {
  // Kept for backward compatibility, but computed setter now handles updates
};

// Compare expression change handler
const onCompareExpressionChange = (event: Event) => {
  const value = (event.target as HTMLSelectElement).value;
  store.setCompareState({ expression: value });
};

const groupingColumnOptions = computed<Record<string, string>>(() => toOptionsRecord(columnsStore.filterableColColumns));

function defaultGroupingColumn(): string {
  if (columnsStore.tissueColumnName) return columnsStore.tissueColumnName;
  return columnsStore.filterableColColumns[0]?.column_name || '';
}

const selectedGroupingColumn = computed(() => {
  const configured = props.context === 'compare'
    ? store.compare.groupingColumn
    : store.phyloTree.groupingColumn;
  return configured && groupingColumnOptions.value[configured]
    ? configured
    : defaultGroupingColumn();
});

function setGroupingColumn(columnName: string) {
  if (props.context === 'compare') {
    store.setCompareState({ groupingColumn: columnName });
  } else if (props.context === 'phylogeneticTree') {
    store.setPhyloTreeState({ groupingColumn: columnName });
  }
}

// Convert COLORSCALES keys into a Record<string, string> for DropdownMenu options
const colorScaleDropdownOptions = Object.keys(COLORSCALES).reduce(
  (acc, key) => {
    acc[key] = beautifyLabel(key);
    return acc;
  },
  {} as Record<string, string>,
);

// Remove old COLORRANGES definition (now replaced by Expression)

function metadataDisplayName(col: { column_name: string; display_name?: string }): string {
  return col.display_name || getDisplayName(col.column_name);
}

function sortMetadataColumns<T extends { column_name: string; display_name?: string }>(columns: T[]): T[] {
  return [...columns].sort((a, b) => {
    const displayComparison = metadataDisplayName(a).localeCompare(metadataDisplayName(b), undefined, { sensitivity: "base" });
    if (displayComparison !== 0) return displayComparison;
    return a.column_name.localeCompare(b.column_name);
  });
}

function toOptionsRecord(columns: { column_name: string; display_name?: string }[]): Record<string, string> {
  const options: Record<string, string> = {};
  for (const col of sortMetadataColumns(columns)) {
    options[col.column_name] = metadataDisplayName(col);
  }
  return options;
}

// Row order options derived from attribute keys, mapped to beautified labels
const rowOrderOptions = computed<Record<string, string>>(() => {
  const hiddenCols = new Set(config.visualization.hide_columns || []);
  return toOptionsRecord(columnsStore.rowColumns.filter((col) => !hiddenCols.has(col.column_name)));
});

const rowSideColorOptions = computed<string[]>(() => {
  const hiddenCols = new Set(config.visualization.hide_columns || []);
  // Also exclude gene_id/transcript ID columns from row side colors - they're unique per row
  const idColumns = new Set(['gene_id', 'transcript_id', 'id']);
  return sortMetadataColumns(
    columnsStore.rowColumns.filter((col) => !hiddenCols.has(col.column_name) && !idColumns.has(col.column_name)),
  ).map((col) => col.column_name);
});

// Display names for RowSideColors (uses backend display_name from Admin Panel)
const rowSideColorDisplayNames = computed<Record<string, string>>(() => {
  const displayNames: Record<string, string> = {};
  for (const col of sortMetadataColumns(columnsStore.rowColumns)) {
    displayNames[col.column_name] = metadataDisplayName(col);
  }
  return displayNames;
});

// Col order options derived from attribute keys, mapped to beautified labels
const colOrderOptions = computed<Record<string, string>>(() => {
  if (axisOnlyCustomOrder.value) {
    return { tissue_types: metadataDisplayName({ column_name: "tissue_types" }) };
  }
  // Use orderableColColumns for Column Order dropdown (includes tissue_types)
  return toOptionsRecord(columnsStore.orderableColColumns);
});

const colSideColorOptions = computed<string[]>(() =>
  // Use colColumns for ColSideColors (only tissue_types, not individual tissue columns)
  sortMetadataColumns(columnsStore.colColumns).map((c) => c.column_name),
);

// Display names for ColSideColors (uses backend display_name from Admin Panel)
const colSideColorDisplayNames = computed<Record<string, string>>(() => {
  const displayNames: Record<string, string> = {};
  for (const col of sortMetadataColumns(columnsStore.colColumns)) {
    displayNames[col.column_name] = metadataDisplayName(col);
  }
  return displayNames;
});

const customOrderMetadataOptions = computed<Record<string, string>>(() => toOptionsRecord(columnsStore.colColumns));

const customOrderEnabled = computed({
  get: () => store.customColOrder.enabled,
  set: (enabled: boolean) => {
    const replacedClustering = enabled && store.clustering.clusterCols;
    const replacedColumnOrder = enabled && Boolean(store.colOrder.name);
    store.setCustomColOrderState(axisOnlyCustomOrder.value
      ? { enabled, mode: "metadata", metadataColumn: "tissue_types" }
      : { enabled });
    ensureCustomOrderLists();
    if (replacedClustering) {
      showOrderFeedback("col", "Column clustering is off. Custom order is active now.");
    } else if (replacedColumnOrder) {
      showOrderFeedback("col", "Column order is off. Custom order is active now.");
    }
  },
});

const customOrderMetadataColumn = computed({
  get: () => store.customColOrder.metadataColumn || "tissue_types",
  set: (metadataColumn: string) => {
    store.setCustomColOrderState({ metadataColumn, metadataValues: getMetadataValues(metadataColumn) });
  },
});

const customMetadataValueOrder = computed({
  get: () => store.customColOrder.metadataValues,
  set: (metadataValues: string[]) => store.setCustomColOrderState({ metadataValues }),
});

const customSampleOrder = computed({
  get: () => store.customColOrder.sampleNames,
  set: (sampleNamesValue: string[]) => store.setCustomColOrderState({ sampleNames: sampleNamesValue }),
});

const sampleNames = computed(() =>
  columnsStore.sampleMetadata
    .map((record) => String(record.column_name ?? ""))
    .filter(Boolean)
    .sort((a, b) => a.localeCompare(b)),
);

function withMissingValues(current: string[], available: string[]): string[] {
  const kept: string[] = [];
  const keptSet = new Set<string>();
  for (const value of current) {
    if (!value || keptSet.has(value)) continue;
    kept.push(value);
    keptSet.add(value);
  }
  return [...kept, ...available.filter((value) => value && !keptSet.has(value))];
}

function arraysEqual(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((value, index) => value === b[index]);
}

function getMetadataValues(columnName: string): string[] {
  const metadataColumn = columnName || "tissue_types";
  const lookupKey = metadataColumn === "tissue_types" ? (columnsStore.tissueColumnName ?? "tissue") : metadataColumn;
  const values = new Set<string>();
  for (const record of columnsStore.sampleMetadata) {
    const value = record[lookupKey];
    if (Array.isArray(value)) {
      for (const item of value) values.add(String(item));
    } else if (value !== null && value !== undefined && String(value) !== "") {
      values.add(String(value));
    }
  }
  return [...values].sort((a, b) => a.localeCompare(b));
}

function getAxisValues(): string[] {
  return getMetadataValues("tissue_types");
}

async function loadSampleMetadataForVisibleTables() {
  const tableNamesParam = route.params.table_names;
  const tableNames = typeof tableNamesParam === "string"
    ? tableNamesParam.split(",").filter(Boolean)
    : [];

  await Promise.all(tableNames.map(async (tableName) => {
    if (columnsStore.sampleMetadataByTable[tableName] || loadingSampleMetadataTables.has(tableName)) return;
    loadingSampleMetadataTables.add(tableName);
    try {
      const [columnRes, metaRes] = await Promise.all([
        axios.get<MetaFormat[]>(`${API_BASE_URL}/api/columns`, {
          params: { table_name: tableName, meta: false },
        }),
        axios.post(`${API_BASE_URL}/api/data`, {
          table_name: `${tableName}_meta`,
          filters: {},
        }),
      ]);
      const dataColumnNames = new Set(columnRes.data.map((column) => column.column_name));
      const colData = metaRes.data.data || metaRes.data;
      const records = (Array.isArray(colData) ? colData : []).filter((meta: RowType) =>
        dataColumnNames.has(String(meta.column_name ?? "")),
      );
      columnsStore.setSampleMetadata(records as Record<string, unknown>[], tableName);
    } catch (error) {
      console.warn("Could not load sample metadata for custom order", tableName, error);
    } finally {
      loadingSampleMetadataTables.delete(tableName);
    }
  }));
}

function ensureCustomOrderLists() {
  const metadataColumn = axisOnlyCustomOrder.value ? "tissue_types" : store.customColOrder.metadataColumn || "tissue_types";
  const metadataValues = withMissingValues(
    store.customColOrder.metadataValues,
    axisOnlyCustomOrder.value ? getAxisValues() : getMetadataValues(metadataColumn),
  );
  const orderedSampleNames = withMissingValues(store.customColOrder.sampleNames, sampleNames.value);
  const update: Partial<typeof store.customColOrder> = {};
  if (axisOnlyCustomOrder.value && store.customColOrder.mode !== "metadata") update.mode = "metadata";
  if (store.customColOrder.metadataColumn !== metadataColumn) update.metadataColumn = metadataColumn;
  if (!arraysEqual(store.customColOrder.metadataValues, metadataValues)) update.metadataValues = metadataValues;
  if (!arraysEqual(store.customColOrder.sampleNames, orderedSampleNames)) update.sampleNames = orderedSampleNames;
  if (Object.keys(update).length > 0) store.setCustomColOrderState(update);
}

function ensureAxisOnlyColumnOrder() {
  if (!axisOnlyCustomOrder.value) return;
  if (store.colOrder.name !== "tissue_types") store.setColOrderName("tissue_types");
}

function setCustomOrderMode(mode: "metadata" | "samples") {
  if (axisOnlyCustomOrder.value && mode === "samples") return;
  store.setCustomColOrderState({ mode });
  ensureCustomOrderLists();
}

function resetCustomOrder() {
  store.setCustomColOrderState({
    enabled: false,
    mode: "metadata",
    metadataColumn: "tissue_types",
    metadataValues: axisOnlyCustomOrder.value ? getAxisValues() : getMetadataValues("tissue_types"),
    sampleNames: sampleNames.value,
  });
}

watch(
  [() => columnsStore.sampleMetadata, () => store.customColOrder.metadataColumn],
  () => {
    if (store.customColOrder.enabled) ensureCustomOrderLists();
  },
  { deep: true },
);

watch(
  () => props.showSettingsOverlay,
  async (show) => {
    if (!show || props.context === "ora") return;
    ensureAxisOnlyColumnOrder();
    await loadSampleMetadataForVisibleTables();
    if (store.customColOrder.enabled) ensureCustomOrderLists();
  },
);

watch(axisOnlyCustomOrder, () => {
  ensureAxisOnlyColumnOrder();
  if (axisOnlyCustomOrder.value && store.customColOrder.enabled) {
    store.setCustomColOrderState({ mode: "metadata", metadataColumn: "tissue_types" });
    ensureCustomOrderLists();
  }
});

// Close overlay handler
const closeOverlay = () => {
  emit("update:showOverlay", false);
};
</script>
