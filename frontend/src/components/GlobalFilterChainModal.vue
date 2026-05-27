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
                class="flex items-center gap-3 rounded-md border border-gray-200 bg-gray-50 px-3 py-2"
                draggable="true"
                @dragstart="dragColumn(index)"
                @dragend="draggedIndex = null"
              >
                <button
                  type="button"
                  class="h-8 w-8 rounded border text-base font-semibold transition-colors"
                  :class="groupFor(element).open
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                    : 'border-gray-300 bg-white text-gray-500 hover:bg-gray-100'"
                  :aria-label="`${groupFor(element).open ? 'Remove' : 'Add'} opening parenthesis before ${labelFor(element)}`"
                  @click.stop="toggleOpenGroup(element)"
                >
                  (
                </button>
                <button
                  type="button"
                  class="inline-flex h-8 w-8 cursor-grab items-center justify-center rounded text-gray-400 hover:bg-white hover:text-gray-700 active:cursor-grabbing"
                  aria-label="Drag filter"
                >
                  <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 6h.01M8 12h.01M8 18h.01M16 6h.01M16 12h.01M16 18h.01" />
                  </svg>
                </button>
                <div class="min-w-0 flex-1">
                  <div class="truncate text-sm font-medium text-gray-900">{{ labelFor(element) }}</div>
                  <div class="truncate text-xs text-gray-500">{{ summaryFor(element) }}</div>
                </div>
                <button
                  type="button"
                  class="h-8 w-8 rounded border text-base font-semibold transition-colors"
                  :class="groupFor(element).close
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
                    : 'border-gray-300 bg-white text-gray-500 hover:bg-gray-100'"
                  :aria-label="`${groupFor(element).close ? 'Remove' : 'Add'} closing parenthesis after ${labelFor(element)}`"
                  @click.stop="toggleCloseGroup(element)"
                >
                  )
                </button>
              </div>

              <div v-if="index < localColumns.length - 1" class="flex items-center gap-3 py-2 pl-14">
                <div class="h-px flex-1 bg-gray-200"></div>
                <button
                  type="button"
                  class="rounded-md border px-3 py-1 text-xs font-semibold transition-colors"
                  :class="operatorFor(element, localColumns[index + 1]) === 'or'
                    ? 'border-emerald-300 bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                    : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-100'"
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
import { getDisplayName } from "@/shared/metadataDisplayNames";

const props = defineProps<{
  open: boolean;
  columns: string[];
  filters: Record<string, FilterValue>;
  labels: Record<string, string | undefined>;
}>();

const emit = defineEmits<{
  close: [];
}>();

const filtersStore = useFiltersStore();
const localColumns = ref<string[]>([]);
const draggedIndex = ref<number | null>(null);
const localGroups = ref<Record<string, FilterChainGroup>>({});

const activeColumns = computed(() => props.columns.filter((column) => props.filters[column]));

watch(
  () => [props.open, props.columns.join("\u0000")],
  () => {
    if (!props.open) return;
    filtersStore.syncFilterChainColumns(activeColumns.value);
    localColumns.value = filtersStore.buildFilterChainPayload(props.filters)?.columns ?? activeColumns.value;
    localGroups.value = filtersStore.getFilterChainGroups(localColumns.value);
  },
  { immediate: true },
);

const groupingState = computed(() => {
  let depth = 0;
  for (const column of localColumns.value) {
    depth += groupFor(column).open || 0;
    depth -= groupFor(column).close || 0;
    if (depth < 0) return { valid: false, depth };
  }
  return { valid: depth === 0, depth };
});

const expressionPreview = computed(() => localColumns.value.map((column, index) => {
  const group = groupFor(column);
  const open = "(".repeat(group.open || 0);
  const close = ")".repeat(group.close || 0);
  const operator = index < localColumns.value.length - 1
    ? ` ${operatorFor(column, localColumns.value[index + 1]).toUpperCase()} `
    : "";
  return `${open}${labelFor(column)}${close}${operator}`;
}).join(""));

function commitOrder() {
  filtersStore.setFilterChainColumns(localColumns.value);
}

function commitAndClose() {
  if (!groupingState.value.valid) return;
  commitOrder();
  filtersStore.setFilterChainGroups(localGroups.value);
  emit("close");
}

function dragColumn(index: number) {
  draggedIndex.value = index;
}

function dropColumn(index: number) {
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
  const group = groupFor(column);
  setGroup(column, { ...group, open: group.open ? 0 : 1 });
}

function toggleCloseGroup(column: string) {
  const group = groupFor(column);
  setGroup(column, { ...group, close: group.close ? 0 : 1 });
}

function operatorFor(left: string, right: string) {
  return filtersStore.getPairOperator(left, right);
}

function toggleOperator(left: string, right: string) {
  filtersStore.togglePairOperator(left, right);
}

function labelFor(column: string): string {
  return getDisplayName(column, props.labels[column]);
}

function summaryFor(column: string): string {
  const value = props.filters[column]?.value;
  return String(value ?? "");
}
</script>
