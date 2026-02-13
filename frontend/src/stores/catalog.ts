import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useCatalogStore = defineStore("catalog", () => {
  /** Set of table_names the user has selected for analysis */
  const selectedTableNames = ref<Set<string>>(new Set());

  /** Effective row count per dataset (filtered count if filters active, otherwise total) */
  const filteredCounts = ref<Map<string, number | null>>(new Map());

  // ── Selection actions ──────────────────────────────────────────────

  function toggleSelection(tableName: string) {
    const s = new Set(selectedTableNames.value);
    if (s.has(tableName)) {
      s.delete(tableName);
    } else {
      s.add(tableName);
    }
    selectedTableNames.value = s;
  }

  function selectAll(tableNames: string[]) {
    selectedTableNames.value = new Set(tableNames);
  }

  function deselectAll() {
    selectedTableNames.value = new Set();
  }

  function isSelected(tableName: string): boolean {
    return selectedTableNames.value.has(tableName);
  }

  // ── Count tracking ─────────────────────────────────────────────────

  function setFilteredCount(tableName: string, count: number | null) {
    const m = new Map(filteredCounts.value);
    m.set(tableName, count);
    filteredCounts.value = m;
  }

  function getEffectiveCount(tableName: string, fallback: number): number {
    const c = filteredCounts.value.get(tableName);
    return c !== null && c !== undefined ? c : fallback;
  }

  // ── Derived state ──────────────────────────────────────────────────

  const selectedCount = computed(() => selectedTableNames.value.size);

  const selectedTableNamesArray = computed(() =>
    [...selectedTableNames.value],
  );

  return {
    selectedTableNames,
    filteredCounts,
    selectedCount,
    selectedTableNamesArray,
    toggleSelection,
    selectAll,
    deselectAll,
    isSelected,
    setFilteredCount,
    getEffectiveCount,
  };
});
