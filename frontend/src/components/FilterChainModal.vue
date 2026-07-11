<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 px-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="filter-chain-title"
      @click.self="$emit('close')"
    >
      <div class="w-full max-w-2xl rounded-lg bg-white shadow-xl border border-gray-200">
        <div class="flex items-center justify-between border-b border-gray-200 px-5 py-4">
          <div>
            <h2 id="filter-chain-title" class="text-base font-semibold text-gray-900">
              Filter Chain
              <span v-if="datasetId" class="font-normal text-gray-500">— {{ datasetLabel }}</span>
            </h2>
            <p class="mt-1 text-xs text-gray-500">
              Build the exact filter expression. Parentheses are evaluated first.
            </p>
          </div>
          <button
            type="button"
            class="inline-flex h-8 w-8 items-center justify-center rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-800"
            aria-label="Close filter chain"
            @click="$emit('close')"
          >
            <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </div>

        <!-- Dataset-scoped status bar: inherited (read-only) vs. localized (editable) -->
        <div
          v-if="datasetId"
          class="flex items-center justify-between gap-2 border-b border-gray-200 px-5 py-2 text-xs"
          :class="localized ? 'bg-amber-50' : 'bg-sky-50'"
        >
          <div class="flex items-center gap-1.5" :class="localized ? 'text-amber-700' : 'text-sky-700'">
            <svg v-if="!localized" class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" stroke-width="1.5" />
              <path stroke-linecap="round" stroke-width="1.5" d="M3 12h18M12 3c2.5 2.7 4 6 4 9s-1.5 6.3-4 9c-2.5-2.7-4-6-4-9s1.5-6.3 4-9z" />
            </svg>
            <svg v-else class="h-3.5 w-3.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 20V4m0 0l-5 5m5-5l5 5" />
            </svg>
            <span>{{ localized ? 'Local override — changes apply only to this dataset' : 'Inherited from the global filter chain' }}</span>
          </div>
          <button
            v-if="!localized"
            type="button"
            class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-sky-300 bg-white px-2 py-1 font-semibold text-sky-700 hover:bg-sky-100"
            aria-label="Localize filter chain for this dataset"
            v-tooltip="'Copy the global chain into a local, editable override for this dataset'"
            @click="localize"
          >
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
            </svg>
            Localize
          </button>
          <button
            v-else
            type="button"
            class="inline-flex cursor-pointer items-center gap-1 rounded-md border border-amber-300 bg-white px-2 py-1 font-semibold text-amber-700 hover:bg-amber-100"
            aria-label="Reset filter chain to global"
            v-tooltip="'Discard this dataset\'s local override and inherit the global chain again'"
            @click="resetToGlobal"
          >
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h5M20 20v-5h-5M4.5 9a8 8 0 0114-4.9M19.5 15a8 8 0 01-14 4.9" />
            </svg>
            Reset to Global
          </button>
        </div>

        <div class="px-5 py-4">
          <div class="mb-4 rounded-md border border-gray-200 bg-white px-3 py-2">
            <div class="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
              Expression Preview
            </div>
            <div class="break-words font-mono text-sm text-gray-900">
              {{ expressionPreview }}
            </div>
            <div v-if="!groupingState.valid" class="mt-2 text-xs text-red-600">
              Parentheses must be balanced and cannot close before a group has started.
            </div>
          </div>

          <div class="space-y-2">
            <div
              v-for="(element, index) in localColumns"
              :key="element"
              @dragover.prevent
              @drop="dropColumn(index)"
            >
              <div
                class="flex items-center gap-2 rounded-md border px-3 py-2 transition-colors"
                :class="disabledFor(element)
                  ? 'border-gray-200 bg-gray-100 opacity-60'
                  : notFor(element)
                    ? 'border-red-200 bg-red-50'
                    : 'border-gray-200 bg-gray-50'"
                :draggable="canEdit"
                @dragstart="dragColumn(index)"
                @dragend="draggedIndex = null"
              >
                <!-- Include/exclude toggle — completely removes this filter from the
                     dataset's chain (unlike NOT, which negates it). Only shown for a
                     dataset-scoped chain. -->
                <button
                  v-if="datasetId"
                  type="button"
                  role="switch"
                  :aria-checked="!disabledFor(element)"
                  class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  :class="disabledFor(element) ? 'bg-gray-300' : 'bg-emerald-500'"
                  :disabled="!canEdit"
                  :aria-label="`${disabledFor(element) ? 'Include' : 'Exclude'} ${labelFor(element)} in this dataset's filter chain`"
                  v-tooltip="disabledFor(element)
                    ? 'Excluded from this dataset — click to include it again'
                    : 'Included — click to exclude this filter completely for this dataset'"
                  @click.stop="toggleDisabledFor(element)"
                >
                  <span
                    class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                    :class="disabledFor(element) ? 'translate-x-1' : 'translate-x-[18px]'"
                  />
                </button>
                <button
                  type="button"
                  class="h-8 w-8 rounded border text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  :class="groupFor(element).open
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                    : 'border-gray-300 bg-white text-gray-500 hover:bg-gray-100'"
                  :disabled="!canEdit || disabledFor(element)"
                  :aria-label="`${groupFor(element).open ? 'Remove' : 'Add'} opening parenthesis before ${labelFor(element)}`"
                  @click.stop="toggleOpenGroup(element)"
                >
                  (
                </button>
                <button
                  type="button"
                  class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded text-gray-400 hover:bg-white hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-40"
                  :class="canEdit ? 'cursor-grab active:cursor-grabbing' : 'cursor-not-allowed'"
                  :disabled="!canEdit"
                  aria-label="Drag filter"
                >
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 6h.01M8 12h.01M8 18h.01M16 6h.01M16 12h.01M16 18h.01" />
                  </svg>
                </button>
                <!-- NOT toggle — sits directly to the left of the field selector -->
                <button
                  type="button"
                  class="h-8 shrink-0 rounded border px-2 text-[11px] font-bold tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  :class="notFor(element)
                    ? 'border-red-400 bg-red-100 text-red-700 hover:bg-red-200'
                    : 'border-gray-300 bg-white text-gray-400 hover:bg-gray-100'"
                  :disabled="!canEdit || disabledFor(element)"
                  :aria-pressed="notFor(element)"
                  :aria-label="`${notFor(element) ? 'Remove' : 'Add'} NOT negation for ${labelFor(element)}`"
                  v-tooltip="'Negate this filter (NOT)'"
                  @click.stop="toggleNotFor(element)"
                >
                  NOT
                </button>
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-medium text-gray-900" :class="{ 'line-through': disabledFor(element) }">{{ labelFor(element) }}</div>
                  <div class="truncate text-xs text-gray-500">{{ disabledFor(element) ? 'Excluded from this dataset' : summaryFor(element) }}</div>
                </div>
                <button
                  type="button"
                  class="h-8 w-8 rounded border text-base font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  :class="groupFor(element).close
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                    : 'border-gray-300 bg-white text-gray-500 hover:bg-gray-100'"
                  :disabled="!canEdit || disabledFor(element)"
                  :aria-label="`${groupFor(element).close ? 'Remove' : 'Add'} closing parenthesis after ${labelFor(element)}`"
                  @click.stop="toggleCloseGroup(element)"
                >
                  )
                </button>
              </div>

              <div
                v-if="index < localColumns.length - 1 && !disabledFor(element) && !disabledFor(localColumns[index + 1])"
                class="flex items-center gap-3 py-2 pl-14"
              >
                <div class="h-px flex-1 bg-gray-200"></div>
                <button
                  type="button"
                  class="rounded-md border px-3 py-1 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50"
                  :class="operatorFor(element, localColumns[index + 1]) === 'or'
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-100'"
                  :disabled="!canEdit"
                  :aria-label="`Toggle operator between ${labelFor(element)} and ${labelFor(localColumns[index + 1])}`"
                  @click="toggleOperator(element, localColumns[index + 1])"
                >
                  {{ operatorFor(element, localColumns[index + 1]).toUpperCase() }}
                </button>
                <div class="h-px flex-1 bg-gray-200"></div>
              </div>
            </div>
          </div>
        </div>

        <div class="flex justify-end border-t border-gray-200 px-5 py-3">
          <button
            type="button"
            class="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:cursor-not-allowed disabled:bg-gray-400"
            :disabled="!groupingState.valid"
            @click="commitAndClose"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useFiltersStore, type FilterChainGroup, type FilterValue } from "@/stores/filters";
import { getDisplayName } from "@/shared/metadataFields";

const props = defineProps<{
  open: boolean;
  columns: string[];
  filters: Record<string, FilterValue>;
  labels: Record<string, string | undefined>;
  /** When set, the modal edits (or previews) this dataset's local filter chain instead of the global one. */
  datasetId?: string | null;
  /** Human-readable dataset name shown in the modal header, e.g. "Arabidopsis thaliana". */
  datasetLabel?: string;
}>();

const emit = defineEmits<{
  close: [];
}>();

const filtersStore = useFiltersStore();
const localColumns = ref<string[]>([]);
const draggedIndex = ref<number | null>(null);
const localGroups = ref<Record<string, FilterChainGroup>>({});

const activeColumns = computed(() => props.columns.filter((column) => props.filters[column]));

// Whether this dataset currently has its own local chain override.
const localized = computed(() => (props.datasetId ? filtersStore.hasLocalChain(props.datasetId) : false));

// The store "slot" (global=null vs a dataset id) that reads/writes should target.
// Before localization a dataset-scoped modal reads/writes the GLOBAL chain
// (read-only preview of what it inherits); once localized, it targets its own slot.
const chainKey = computed<string | null>(() => (props.datasetId && localized.value ? props.datasetId : null));

// Editing is allowed for the global chain, or for a dataset chain that has been localized.
const canEdit = computed(() => !props.datasetId || localized.value);

function loadChainState() {
  filtersStore.syncFilterChainColumns(activeColumns.value);
  // Use the raw chain (not `buildFilterChainPayload`, which strips disabled columns for
  // the actual query) so disabled rows still render in the modal and can be re-enabled.
  const chain = filtersStore.getEffectiveChainPerDataset(chainKey.value);
  const activeSet = new Set(activeColumns.value);
  localColumns.value = [
    ...chain.columns.filter((column) => activeSet.has(column)),
    ...activeColumns.value.filter((column) => !chain.columns.includes(column)),
  ];
  localGroups.value = filtersStore.getFilterChainGroups(localColumns.value, chainKey.value);
}

watch(
  () => [props.open, props.columns.join("\u0000"), props.datasetId ?? "", localized.value],
  () => {
    if (!props.open) return;
    loadChainState();
  },
  { immediate: true },
);

// Columns that still actively participate in the chain (excludes any dataset-disabled ones).
const enabledColumns = computed(() => localColumns.value.filter((column) => !disabledFor(column)));

const groupingState = computed(() => {
  let depth = 0;
  for (const column of enabledColumns.value) {
    depth += groupFor(column).open || 0;
    depth -= groupFor(column).close || 0;
    if (depth < 0) return { valid: false, depth };
  }
  return { valid: depth === 0, depth };
});

const expressionPreview = computed(() => {
  const cols = enabledColumns.value;
  if (cols.length === 0) return localColumns.value.length > 0 ? "(all filters excluded for this dataset)" : "";
  return cols.map((column, index) => {
    const group = groupFor(column);
    const open = "(".repeat(group.open || 0);
    const close = ")".repeat(group.close || 0);
    const notPrefix = notFor(column) ? "NOT " : "";
    const operator = index < cols.length - 1
      ? ` ${operatorFor(column, cols[index + 1]).toUpperCase()} `
      : "";
    return `${open}${notPrefix}${labelFor(column)}${close}${operator}`;
  }).join("");
});

function disabledFor(column: string): boolean {
  return filtersStore.getDisabled(column, props.datasetId ?? null);
}

function toggleDisabledFor(column: string) {
  if (!canEdit.value) return;
  filtersStore.toggleDisabled(column, props.datasetId ?? null);
}

function localize() {
  if (!props.datasetId) return;
  filtersStore.localizeDatasetChain(props.datasetId, localColumns.value);
}

function resetToGlobal() {
  if (!props.datasetId) return;
  filtersStore.resetDatasetChain(props.datasetId);
}

function commitOrder() {
  if (!canEdit.value) return;
  filtersStore.setFilterChainColumns(localColumns.value, chainKey.value);
}

function commitAndClose() {
  if (!groupingState.value.valid) return;
  if (canEdit.value) {
    commitOrder();
    filtersStore.setFilterChainGroups(localGroups.value, chainKey.value);
  }
  emit("close");
}

function dragColumn(index: number) {
  if (!canEdit.value) return;
  draggedIndex.value = index;
}

function dropColumn(index: number) {
  if (!canEdit.value) return;
  if (draggedIndex.value === null || draggedIndex.value === index) return;
  const nextColumns = [...localColumns.value];
  const [moved] = nextColumns.splice(draggedIndex.value, 1);
  nextColumns.splice(index, 0, moved);
  localColumns.value = nextColumns;
  draggedIndex.value = null;
  commitOrder();
}

function groupFor(column: string): FilterChainGroup {
  return localGroups.value[column] ?? {};
}

function setGroup(column: string, group: FilterChainGroup) {
  localGroups.value = {
    ...localGroups.value,
    [column]: group,
  };
}

function toggleOpenGroup(column: string) {
  if (!canEdit.value) return;
  const group = groupFor(column);
  setGroup(column, { ...group, open: group.open ? 0 : 1 });
}

function toggleCloseGroup(column: string) {
  if (!canEdit.value) return;
  const group = groupFor(column);
  setGroup(column, { ...group, close: group.close ? 0 : 1 });
}

function operatorFor(left: string, right: string) {
  return filtersStore.getPairOperator(left, right, chainKey.value);
}

function toggleOperator(left: string, right: string) {
  if (!canEdit.value) return;
  filtersStore.togglePairOperator(left, right, chainKey.value);
}

function notFor(column: string): boolean {
  return filtersStore.getNot(column, chainKey.value);
}

function toggleNotFor(column: string) {
  if (!canEdit.value) return;
  filtersStore.toggleNot(column, chainKey.value);
}

function labelFor(column: string): string {
  return getDisplayName(column, props.labels[column]);
}

function summaryFor(column: string): string {
  const value = props.filters[column]?.value;
  return String(value ?? "");
}
</script>
