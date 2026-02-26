<template>
  <div class="chip-manager">
    <!-- Tab Header -->
    <div class="chip-tabs">
      <button
        :class="['chip-tab', { active: activeTarget === 'var' }]"
        @click="activeTarget = 'var'"
      >
        {{ getEntityLabelPlural() }} (.var)
      </button>
      <button
        :class="['chip-tab', { active: activeTarget === 'obs' }]"
        @click="activeTarget = 'obs'"
      >
        Samples (.obs)
      </button>
    </div>

    <!-- Search -->
    <div class="chip-search">
      <input
        v-model="searchQuery"
        type="text"
        :placeholder="`Search ${activeTarget === 'var' ? getEntityLabelPluralLower() : 'sample'} columns...`"
        class="search-input"
      />
    </div>

    <!-- Info Banner -->
    <div class="chip-info">
      <span class="info-icon">ℹ️</span>
      Drag to reorder · Click 👁 to show/hide · Double-click label to rename · Change the green badge to override the data type
    </div>

    <!-- Draggable Chips -->
    <draggable
      v-model="filteredChips"
      :group="activeTarget"
      item-key="name"
      handle=".chip-drag-handle"
      ghost-class="chip-ghost"
      drag-class="chip-dragging"
      @end="onDragEnd"
      class="chip-container"
    >
      <template #item="{ element }">
        <div
          :class="['metadata-chip', { disabled: !element.visible, custom: element.source === 'custom' }]"
        >
          <span class="chip-drag-handle" title="Drag to reorder">⠿</span>

          <!-- Visibility Toggle -->
          <button
            class="chip-visibility"
            :title="element.visible ? 'Visible – click to hide' : 'Hidden – click to show'"
            @click="toggleVisibility(element)"
          >
            <span v-if="element.visible" class="eye-icon">👁</span>
            <span v-else class="eye-icon eye-off">👁‍🗨</span>
          </button>

          <!-- Display Name (editable) -->
          <span
            v-if="editingChip !== element.name"
            class="chip-label"
            @dblclick="startEditing(element)"
            :title="`Column: ${element.name} — Double-click to rename`"
          >
            {{ element.display_name }}
          </span>
          <input
            v-else
            ref="editInput"
            v-model="editValue"
            class="chip-edit-input"
            @blur="finishEditing(element)"
            @keyup.enter="finishEditing(element)"
            @keyup.escape="cancelEditing"
          />

          <!-- Column Name Badge -->
          <code class="chip-code" :title="element.name">{{ element.name }}</code>

          <!-- Type Select (editable) -->
          <select
            class="chip-type-select"
            :value="element.type"
            :title="`Type: ${element.type} — click to change`"
            @change="changeType(element, ($event.target as HTMLSelectElement).value)"
            @click.stop
          >
            <option v-for="t in TYPE_OPTIONS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>

          <!-- Delete button for custom columns -->
          <button
            v-if="element.source === 'custom'"
            class="chip-delete"
            title="Remove custom column"
            @click="$emit('delete-column', element.name)"
          >
            ✕
          </button>
        </div>
      </template>
    </draggable>

    <!-- Add New Metadata Chip -->
    <button
      class="add-chip"
      @click="$emit('add-metadata', activeTarget)"
      :title="`Add new ${activeTarget === 'var' ? getEntityLabelLower() : 'sample'} metadata column`"
    >
      <span class="add-icon">+</span>
      Add {{ activeTarget === 'var' ? getEntityLabel() : 'Sample' }} Metadata
    </button>

    <!-- Summary -->
    <div class="chip-summary">
      <span>{{ visibleCount }} visible</span>
      <span class="separator">·</span>
      <span>{{ hiddenCount }} hidden</span>
      <span class="separator">·</span>
      <span>{{ totalCount }} total</span>
      <span v-if="customCount > 0" class="separator">·</span>
      <span v-if="customCount > 0" class="custom-badge">{{ customCount }} custom</span>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, watch, nextTick, type PropType } from 'vue';
import draggable from 'vuedraggable';
import {
  getEntityLabelPlural,
  getEntityLabelPluralLower,
  getEntityLabel,
  getEntityLabelLower,
} from '@/shared/dataTypeLabels';

export interface ChipItem {
  name: string;
  display_name: string;
  type: string;
  visible: boolean;
  is_meta: boolean;
  is_sample_metadata: boolean;
  is_array: boolean;
  order: number;
  source: 'auto' | 'custom';
  sortable?: boolean;
}

export default defineComponent({
  name: 'MetadataChipManager',
  components: { draggable },
  props: {
    /** All column definitions from backend config */
    columnDefinitions: {
      type: Object as PropType<Record<string, any>>,
      required: true,
    },
  },
  emits: ['update:columns', 'add-metadata', 'delete-column'],
  setup(props, { emit }) {
    const activeTarget = ref<'var' | 'obs'>('var');
    const searchQuery = ref('');
    const editingChip = ref<string | null>(null);
    const editValue = ref('');
    const editInput = ref<HTMLInputElement | null>(null);

    // Build chip arrays from column definitions
    const varChips = ref<ChipItem[]>([]);
    const obsChips = ref<ChipItem[]>([]);

    function buildChips() {
      const defs = props.columnDefinitions || {};
      const varList: ChipItem[] = [];
      const obsList: ChipItem[] = [];

      for (const [name, def] of Object.entries(defs)) {
        const chip: ChipItem = {
          name,
          display_name: def.display_name || name.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
          type: def.type || 'text',
          visible: def.visible !== false,
          is_meta: def.is_meta || false,
          is_sample_metadata: def.is_sample_metadata || false,
          is_array: def.is_array || false,
          order: def.order ?? 999,
          source: def.source || 'auto',
          sortable: def.sortable,
        };

        if (chip.is_sample_metadata) {
          obsList.push(chip);
        } else {
          varList.push(chip);
        }
      }

      // Sort by order, then by name
      varList.sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));
      obsList.sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));

      varChips.value = varList;
      obsChips.value = obsList;
    }

    watch(() => props.columnDefinitions, buildChips, { immediate: true, deep: true });

    // Current active chips
    const activeChips = computed({
      get: () => activeTarget.value === 'var' ? varChips.value : obsChips.value,
      set: (val: ChipItem[]) => {
        if (activeTarget.value === 'var') {
          varChips.value = val;
        } else {
          obsChips.value = val;
        }
      },
    });

    // Filtered by search
    const filteredChips = computed({
      get: () => {
        const q = searchQuery.value.toLowerCase();
        if (!q) return activeChips.value;
        return activeChips.value.filter(
          (c) =>
            c.name.toLowerCase().includes(q) ||
            c.display_name.toLowerCase().includes(q)
        );
      },
      set: (val: ChipItem[]) => {
        // If searching, we need to merge the reordered subset back
        if (searchQuery.value) {
          const filteredNames = new Set(val.map((c) => c.name));
          const rest = activeChips.value.filter((c) => !filteredNames.has(c.name));
          // Insert rest items back at their original positions
          activeChips.value = [...val, ...rest];
        } else {
          activeChips.value = val;
        }
      },
    });

    // Stats
    const visibleCount = computed(() => activeChips.value.filter((c) => c.visible).length);
    const hiddenCount = computed(() => activeChips.value.filter((c) => !c.visible).length);
    const totalCount = computed(() => activeChips.value.length);
    const customCount = computed(() => activeChips.value.filter((c) => c.source === 'custom').length);

    function toggleVisibility(chip: ChipItem) {
      chip.visible = !chip.visible;
      emitUpdate();
    }

    function startEditing(chip: ChipItem) {
      editingChip.value = chip.name;
      editValue.value = chip.display_name;
      nextTick(() => {
        const input = document.querySelector('.chip-edit-input') as HTMLInputElement;
        input?.focus();
        input?.select();
      });
    }

    function finishEditing(chip: ChipItem) {
      if (editValue.value.trim()) {
        chip.display_name = editValue.value.trim();
      }
      editingChip.value = null;
      emitUpdate();
    }

    function cancelEditing() {
      editingChip.value = null;
    }

    const TYPE_OPTIONS = [
      { value: 'text',             label: 'T  – Text' },
      { value: 'bigint',           label: 'N  – Integer' },
      { value: 'double precision', label: 'F  – Float' },
      { value: 'boolean',          label: 'B  – Boolean' },
      { value: 'array',            label: '[] – Array' },
    ];

    function changeType(element: ChipItem, newType: string) {
      element.type = newType;
      emitUpdate();
    }

    function onDragEnd() {
      emitUpdate();
    }

    function emitUpdate() {
      // Rebuild column definitions from chips with updated order
      const result: Record<string, any> = {};

      // Process var chips first
      varChips.value.forEach((chip, index) => {
        result[chip.name] = {
          display_name: chip.display_name,
          type: chip.type,
          is_array: chip.is_array,
          is_meta: chip.is_meta,
          is_sample_metadata: false,
          visible: chip.visible,
          sortable: chip.sortable ?? true,
          order: index,
          source: chip.source,
        };
      });

      // Then obs chips (continue order numbering)
      const offset = varChips.value.length;
      obsChips.value.forEach((chip, index) => {
        result[chip.name] = {
          display_name: chip.display_name,
          type: chip.type,
          is_array: chip.is_array,
          is_meta: chip.is_meta,
          is_sample_metadata: true,
          visible: chip.visible,
          sortable: chip.sortable ?? true,
          order: offset + index,
          source: chip.source,
        };
      });

      emit('update:columns', result);
    }

    function shortenType(type: string): string {
      const map: Record<string, string> = {
        text: 'T',
        bigint: 'N',
        'double precision': 'F',
        boolean: 'B',
        array: '[]',
      };
      return map[type] || type.charAt(0).toUpperCase();
    }

    return {
      activeTarget,
      searchQuery,
      editingChip,
      editValue,
      editInput,
      filteredChips,
      visibleCount,
      hiddenCount,
      totalCount,
      customCount,
      toggleVisibility,
      startEditing,
      finishEditing,
      cancelEditing,
      onDragEnd,
      shortenType,
      TYPE_OPTIONS,
      changeType,
      // Label helpers
      getEntityLabelPlural,
      getEntityLabelPluralLower,
      getEntityLabel,
      getEntityLabelLower,
    };
  },
});
</script>

<style scoped>
.chip-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chip-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 2px solid #e5e7eb;
  padding-bottom: 0;
}

.chip-tab {
  padding: 10px 24px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  color: #6b7280;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.chip-tab:hover {
  color: #2563eb;
  background: #f0f4ff;
}

.chip-tab.active {
  color: #2563eb;
  border-bottom-color: #2563eb;
}

.chip-search {
  position: relative;
}

.search-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 14px;
  background: #f9fafb;
  transition: border-color 0.2s;
  box-sizing: border-box;
}

.search-input:focus {
  outline: none;
  border-color: #2563eb;
  background: white;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.chip-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #eff6ff;
  border-left: 4px solid #2563eb;
  border-radius: 4px;
  font-size: 13px;
  color: #1e40af;
}

.info-icon {
  flex-shrink: 0;
}

.chip-type-select {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 4px;
  border-radius: 4px;
  border: 1px solid #d1fae5;
  background: #ecfdf5;
  color: #065f46;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  max-width: 90px;
  appearance: none;
  -webkit-appearance: none;
  text-align: center;
}

.chip-type-select:hover,
.chip-type-select:focus {
  border-color: #6ee7b7;
  background: #d1fae5;
  outline: none;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

.chip-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 100px;
}

.metadata-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  transition: all 0.2s;
  cursor: default;
}

.metadata-chip:hover {
  border-color: #93c5fd;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.06);
}

.metadata-chip.disabled {
  background: #f9fafb;
  opacity: 0.6;
  border-style: dashed;
}

.metadata-chip.custom {
  border-left: 3px solid #8b5cf6;
}

.chip-ghost {
  opacity: 0.4;
  background: #dbeafe;
  border: 2px dashed #2563eb;
}

.chip-dragging {
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  transform: rotate(1deg);
}

.chip-drag-handle {
  cursor: grab;
  color: #9ca3af;
  font-size: 16px;
  user-select: none;
  padding: 0 2px;
  flex-shrink: 0;
}

.chip-drag-handle:active {
  cursor: grabbing;
}

.chip-visibility {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  font-size: 16px;
  flex-shrink: 0;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.chip-visibility:hover {
  opacity: 1;
}

.eye-off {
  opacity: 0.35;
}

.chip-label {
  font-size: 14px;
  font-weight: 500;
  color: #1f2937;
  cursor: text;
  flex-grow: 0;
  white-space: nowrap;
  min-width: 60px;
}

.chip-edit-input {
  font-size: 14px;
  font-weight: 500;
  padding: 2px 6px;
  border: 1px solid #2563eb;
  border-radius: 4px;
  outline: none;
  background: #eff6ff;
  min-width: 80px;
  max-width: 200px;
}

.chip-code {
  font-size: 11px;
  background: #f3f4f6;
  color: #6b7280;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  white-space: nowrap;
  flex-shrink: 0;
}

.chip-type {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: #e0e7ff;
  color: #4338ca;
  flex-shrink: 0;
  text-transform: uppercase;
}

.chip-delete {
  background: none;
  border: none;
  cursor: pointer;
  color: #ef4444;
  font-size: 14px;
  padding: 2px 4px;
  border-radius: 4px;
  flex-shrink: 0;
  margin-left: auto;
  transition: background 0.2s;
}

.chip-delete:hover {
  background: #fef2f2;
}

.add-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  background: #f8fafc;
  border: 2px dashed #cbd5e1;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #64748b;
  transition: all 0.2s;
}

.add-chip:hover {
  border-color: #2563eb;
  color: #2563eb;
  background: #f0f4ff;
}

.add-icon {
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}

.chip-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #f9fafb;
  border-radius: 8px;
  font-size: 13px;
  color: #6b7280;
}

.separator {
  color: #d1d5db;
}

.custom-badge {
  color: #7c3aed;
  font-weight: 600;
}
</style>
