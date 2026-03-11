<template>
  <div v-if="visible" class="modal-overlay" @click.self="close">
    <div class="modal-container">
      <div class="modal-header">
        <h2>
          {{ target === 'var' ? `Add ${getEntityLabel()} Metadata` : 'Add Sample Metadata' }}
        </h2>
        <button class="close-btn" @click="close">✕</button>
      </div>

      <div class="modal-body">
        <!-- Step 1: Input -->
        <div v-if="step === 1" class="step-content">
          <div class="step-indicator">
            <span class="step active">1. Input</span>
            <span class="step">2. Validate</span>
            <span class="step">3. Confirm</span>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Dataset (Species)</label>
              <select v-model="form.dataset" class="form-control">
                <option value="" disabled>Select a dataset...</option>
                <option v-for="ds in datasets" :key="ds.code" :value="ds.code">
                  {{ ds.code }} — {{ ds.display_name || ds.full_name }}
                </option>
              </select>
            </div>
            <div class="form-group checkbox-group">
              <label class="toggle-label">
                <input type="checkbox" v-model="form.applyToAll" />
                Apply to all datasets
              </label>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>Column Name <span class="hint">(internal, snake_case)</span></label>
              <input
                v-model="form.columnName"
                type="text"
                class="form-control"
                placeholder="e.g. my_annotation"
                @input="autoDisplayName"
              />
            </div>
            <div class="form-group">
              <label>Display Name <span class="hint">(human-readable)</span></label>
              <input
                v-model="form.displayName"
                type="text"
                class="form-control"
                placeholder="e.g. My Annotation"
              />
            </div>
          </div>

          <div class="form-group">
            <label>Data <span class="hint">(Any delimiter, with header row — select ID &amp; value columns below)</span></label>
            <div class="data-input-actions">
              <button class="btn-link" @click="triggerFileUpload">📁 Upload TSV file</button>
              <span class="hint">or paste below</span>
            </div>
            <input
              ref="fileInput"
              type="file"
              accept=".tsv,.txt,.csv"
              class="hidden"
              @change="onFileUpload"
            />
            <textarea
              v-model="form.data"
              class="form-control data-textarea"
              rows="10"
              :placeholder="`col1\tcol2\tcol3\nID001\t42\tTissue A\nID002\t17\tTissue B\n...`"
            ></textarea>
            <div class="data-stats" v-if="form.data">
              {{ dataLineCount }} data rows (excluding header)
            </div>
          </div>

          <!-- Column Mapping (shown as soon as header row is detectable) -->
          <div v-if="parsedHeaders.length >= 2" class="column-mapping-box">
            <div class="column-mapping-header">
              <span class="column-mapping-title">Column Mapping</span>
              <span class="column-mapping-hint">Choose which column contains the IDs and which the values</span>
            </div>
            <div class="column-mapping-row">
              <div class="column-mapping-field">
                <label class="column-mapping-label">
                  🔑 ID Column
                  <span class="hint">(matched against dataset IDs)</span>
                </label>
                <select v-model="form.idColumn" class="form-control form-control-sm">
                  <option v-for="(col, idx) in parsedHeaders" :key="idx" :value="col">
                    {{ col }}
                  </option>
                </select>
              </div>
              <div class="column-mapping-arrow">→</div>
              <div class="column-mapping-field">
                <label class="column-mapping-label">
                  📊 Value Column
                  <span class="hint">(imported as the new metadata column)</span>
                </label>
                <select v-model="form.valueColumn" class="form-control form-control-sm">
                  <option v-for="(col, idx) in parsedHeaders" :key="idx" :value="col">
                    {{ col }}
                  </option>
                </select>
              </div>
            </div>
            <div v-if="columnMappingWarning" class="column-mapping-warning">
              ⚠️ {{ columnMappingWarning }}
            </div>
            <div v-if="parsedSampleRow" class="column-mapping-preview">
              <span class="preview-label">Preview (first row):</span>
              <span class="preview-id">ID: <code>{{ parsedSampleRow.id }}</code></span>
              <span class="preview-sep">→</span>
              <span class="preview-value">Value: <code>{{ parsedSampleRow.value }}</code></span>
            </div>
          </div>

          <div class="form-group">
            <label>Separator</label>
            <div class="radio-group">
              <label class="radio-label">
                <input type="radio" v-model="form.separator" value="\t" /> Tab
              </label>
              <label class="radio-label">
                <input type="radio" v-model="form.separator" value="," /> Comma
              </label>
              <label class="radio-label">
                <input type="radio" v-model="form.separator" value=";" /> Semicolon
              </label>
              <label class="radio-label">
                <input type="radio" v-model="form.separator" value="\s+" /> Whitespace
              </label>
            </div>
          </div>
        </div>

        <!-- Step 2: Validation Result -->
        <div v-if="step === 2" class="step-content">
          <div class="step-indicator">
            <span class="step done">1. Input ✓</span>
            <span class="step active">2. Validate</span>
            <span class="step">3. Confirm</span>
          </div>

          <div v-if="validating" class="loading-state">
            <div class="spinner-small"></div>
            <span>Validating data against dataset...</span>
          </div>

          <div v-else-if="validationError" class="validation-error">
            <h3>⚠️ Validation Failed</h3>
            <p>{{ validationError }}</p>
          </div>

          <div v-else-if="validationResult" class="validation-result">
            <h3>Validation Results</h3>

            <div class="stats-grid">
              <div class="stat-card good">
                <div class="stat-value">{{ validationResult.matched }}</div>
                <div class="stat-label">Matched IDs</div>
              </div>
              <div :class="['stat-card', validationResult.unmatched > 0 ? 'warn' : 'good']">
                <div class="stat-value">{{ validationResult.unmatched }}</div>
                <div class="stat-label">Unmatched IDs</div>
              </div>
              <div class="stat-card neutral">
                <div class="stat-value">{{ validationResult.missing_in_data }}</div>
                <div class="stat-label">Missing in Data</div>
              </div>
              <div class="stat-card info">
                <div class="stat-value">{{ validationResult.type_inferred }}</div>
                <div class="stat-label">Inferred Type</div>
              </div>
            </div>

            <!-- Match ratio bar -->
            <div class="match-bar-container">
              <div class="match-bar">
                <div
                  class="match-bar-fill"
                  :style="{ width: matchPercent + '%' }"
                ></div>
              </div>
              <span class="match-percent">{{ matchPercent }}% match rate</span>
            </div>

            <!-- Unmatched IDs (collapsible) -->
            <details v-if="validationResult.unmatched > 0" class="unmatched-details">
              <summary>
                Show {{ Math.min(validationResult.unmatched_ids.length, 50) }} unmatched IDs
                <span v-if="validationResult.unmatched > 50">
                  (showing first 50 of {{ validationResult.unmatched }})
                </span>
              </summary>
              <div class="unmatched-list">
                <code v-for="id in validationResult.unmatched_ids" :key="id" class="unmatched-id">
                  {{ id }}
                </code>
              </div>
            </details>

            <!-- Sample values -->
            <div class="sample-values" v-if="validationResult.sample_values?.length">
              <h4>Sample Values</h4>
              <div class="sample-list">
                <code v-for="(val, i) in validationResult.sample_values" :key="i">{{ val }}</code>
              </div>
            </div>

            <!-- Type override -->
            <div class="form-group">
              <label>Override Inferred Type <span class="hint">(optional)</span></label>
              <select v-model="typeOverride" class="form-control form-control-sm">
                <option value="">Use inferred: {{ validationResult.type_inferred }}</option>
                <option value="text">Text</option>
                <option value="bigint">Integer</option>
                <option value="double precision">Float</option>
                <option value="boolean">Boolean</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Step 3: Confirm -->
        <div v-if="step === 3" class="step-content">
          <div class="step-indicator">
            <span class="step done">1. Input ✓</span>
            <span class="step done">2. Validate ✓</span>
            <span class="step active">3. Confirm</span>
          </div>

          <div v-if="confirming" class="loading-state">
            <div class="spinner-small"></div>
            <span>Applying metadata...</span>
          </div>

          <div v-else-if="confirmError" class="validation-error">
            <h3>⚠️ Import Failed</h3>
            <p>{{ confirmError }}</p>
          </div>

          <div v-else-if="confirmResult" class="confirm-success">
            <h3>✅ Import Successful</h3>
            <p>Column <strong>{{ form.columnName }}</strong> has been added.</p>
            <div class="results-summary">
              <div v-for="(res, code) in confirmResult.results" :key="code" class="result-row">
                <code>{{ code }}</code>
                <span :class="['result-status', res.status]">{{ res.status }}</span>
                <span v-if="res.matched">{{ res.matched }}/{{ res.total }} matched</span>
                <span v-if="res.persisted" class="persist-badge">💾 Persisted to H5AD</span>
              </div>
            </div>
          </div>

          <div v-else class="confirm-options">
            <h3>Confirm Import</h3>

            <div class="confirm-summary">
              <div class="confirm-item">
                <strong>Column:</strong> {{ form.columnName }} ({{ form.displayName }})
              </div>
              <div class="confirm-item">
                <strong>Target:</strong> {{ target === 'var' ? '.var (Gene metadata)' : '.obs (Sample metadata)' }}
              </div>
              <div class="confirm-item">
                <strong>Dataset:</strong> {{ form.applyToAll ? 'All datasets' : form.dataset }}
              </div>
              <div class="confirm-item">
                <strong>Type:</strong> {{ typeOverride || validationResult?.type_inferred }}
              </div>
              <div class="confirm-item">
                <strong>Matched:</strong> {{ validationResult?.matched }} / {{ validationResult?.total_provided }}
              </div>
            </div>

            <div class="persist-option">
              <label class="toggle-label">
                <input type="checkbox" v-model="persistToH5ad" />
                <strong>Persist to H5AD file</strong>
                <span class="hint">(Survives backend restarts / container recreation)</span>
              </label>
            </div>
          </div>
        </div>
      </div>

      <div class="modal-footer">
        <button v-if="step > 1 && !confirmResult" class="btn btn-secondary" @click="prevStep">
          ← Back
        </button>
        <div class="spacer"></div>
        <button v-if="step === 1" class="btn btn-primary" :disabled="!canValidate" @click="validate">
          Validate →
        </button>
        <button v-if="step === 2 && validationResult" class="btn btn-primary" @click="step = 3">
          Continue →
        </button>
        <button
          v-if="step === 3 && !confirmResult && !confirming"
          class="btn btn-primary"
          @click="confirmImport"
        >
          ✓ Import
        </button>
        <button v-if="confirmResult" class="btn btn-primary" @click="close">
          Done
        </button>
      </div>
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, watch, type PropType } from 'vue';
import axios from 'axios';
import { getEntityLabel } from '@/shared/dataTypeLabels';
import { resolveColumnMapping, splitDelimitedLine } from '@/shared/metadataImport';

interface Dataset {
  code: string;
  full_name: string;
  display_name: string;
  enabled: boolean;
}

interface ValidationResult {
  total_provided: number;
  total_existing: number;
  matched: number;
  unmatched: number;
  missing_in_data: number;
  unmatched_ids: string[];
  type_inferred: string;
  header: string[];
  sample_values: string[];
}

export default defineComponent({
  name: 'MetadataImportModal',
  props: {
    visible: { type: Boolean, required: true },
    target: { type: String as PropType<'var' | 'obs'>, default: 'var' },
    datasets: { type: Array as PropType<Dataset[]>, default: () => [] },
    adminToken: { type: String, default: '' },
    apiBaseUrl: { type: String, default: '' },
  },
  emits: ['close', 'imported'],
  setup(props, { emit }) {
    const step = ref(1);
    const fileInput = ref<HTMLInputElement | null>(null);

    const form = ref({
      dataset: '',
      columnName: '',
      displayName: '',
      data: '',
      separator: '\t',
      applyToAll: false,
      idColumn: '',
      valueColumn: '',
    });

    const validating = ref(false);
    const validationError = ref('');
    const validationResult = ref<ValidationResult | null>(null);
    const typeOverride = ref('');

    const confirming = ref(false);
    const confirmError = ref('');
    const confirmResult = ref<any>(null);
    const persistToH5ad = ref(false);

    // Parse the header row from the current data
    const parsedHeaders = computed<string[]>(() => {
      if (!form.value.data.trim()) return [];
      const firstLine = form.value.data.trim().split('\n')[0];
      const cols = splitDelimitedLine(firstLine, form.value.separator).filter((c: string) => c);
      return cols.length >= 2 ? cols : [];
    });

    // Keep manual selections when the parsed headers still contain them.
    watch(parsedHeaders, (headers: string[]) => {
      if (!headers.length) return;
      const mapping = resolveColumnMapping(headers, props.target, {
        idColumn: form.value.idColumn,
        valueColumn: form.value.valueColumn,
      });
      form.value.idColumn = mapping.idColumn;
      form.value.valueColumn = mapping.valueColumn;
    }, { immediate: true });

    const columnMappingWarning = computed<string>(() => {
      if (!parsedHeaders.value.length) return '';
      if (form.value.idColumn === form.value.valueColumn) return 'ID and value column must be different.';
      return '';
    });

    const parsedSampleRow = computed<{ id: string; value: string } | null>(() => {
      if (!form.value.data.trim() || parsedHeaders.value.length < 2) return null;
      const lines = form.value.data.trim().split('\n');
      if (lines.length < 2) return null;
      const headers = splitDelimitedLine(lines[0], form.value.separator);
      const row = splitDelimitedLine(lines[1], form.value.separator);
      const idIdx = headers.indexOf(form.value.idColumn);
      const valIdx = headers.indexOf(form.value.valueColumn);
      if (idIdx < 0 || valIdx < 0) return null;
      return { id: row[idIdx] ?? '', value: row[valIdx] ?? '' };
    });

    const dataLineCount = computed(() => {
      const lines = form.value.data.trim().split('\n');
      return Math.max(0, lines.length - 1);
    });

    const matchPercent = computed(() => {
      if (!validationResult.value) return 0;
      const total = validationResult.value.total_provided;
      if (total === 0) return 0;
      return Math.round((validationResult.value.matched / total) * 100);
    });

    const canValidate = computed(() => {
      return (
        form.value.dataset &&
        form.value.columnName.trim() &&
        form.value.data.trim() &&
        // If headers are detectable, require valid distinct mapping
        (parsedHeaders.value.length < 2 || (
          form.value.idColumn &&
          form.value.valueColumn &&
          form.value.idColumn !== form.value.valueColumn
        ))
      );
    });

    function getHeaders() {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (props.adminToken) {
        headers['Authorization'] = `Bearer ${props.adminToken}`;
      }
      return headers;
    }

    function autoDisplayName() {
      // Auto-generate display name from column name
      const name = form.value.columnName;
      form.value.displayName = name
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (l: string) => l.toUpperCase());
    }

    function triggerFileUpload() {
      fileInput.value?.click();
    }

    function onFileUpload(event: Event) {
      const input = event.target as HTMLInputElement;
      const file = input.files?.[0];
      if (!file) return;

      const reader = new FileReader();
      reader.onload = (e) => {
        form.value.data = (e.target?.result as string) || '';
        // Auto-detect separator
        const firstLine = form.value.data.split('\n')[0];
        if (firstLine.includes('\t')) form.value.separator = '\t';
        else if (firstLine.includes(';')) form.value.separator = ';';
        else if (firstLine.includes(',')) form.value.separator = ',';
        else if (/\s{2,}/.test(firstLine) || / /.test(firstLine.replace(/^\S+/, ''))) form.value.separator = '\s+';
      };
      reader.readAsText(file);
    }

    async function validate() {
      validating.value = true;
      validationError.value = '';
      validationResult.value = null;

      try {
        const resp = await axios.post(
          `${props.apiBaseUrl}/api/admin/metadata/import`,
          {
            dataset: form.value.dataset,
            target: props.target,
            column_name: form.value.columnName.trim(),
            display_name: form.value.displayName.trim(),
            data: form.value.data,
            separator: form.value.separator === '\\t' ? '\t' : form.value.separator,
            id_column: form.value.idColumn || undefined,
            value_column: form.value.valueColumn || undefined,
          },
          { headers: getHeaders() }
        );

        if (resp.data.success) {
          validationResult.value = resp.data.validation;
          step.value = 2;
        } else {
          validationError.value = resp.data.error || 'Validation failed';
          step.value = 2;
        }
      } catch (err: any) {
        validationError.value = err.response?.data?.error || err.message || 'Validation failed';
        step.value = 2;
      } finally {
        validating.value = false;
      }
    }

    async function confirmImport() {
      confirming.value = true;
      confirmError.value = '';
      confirmResult.value = null;

      try {
        const resp = await axios.post(
          `${props.apiBaseUrl}/api/admin/metadata/import/confirm`,
          {
            dataset: form.value.dataset,
            target: props.target,
            column_name: form.value.columnName.trim(),
            display_name: form.value.displayName.trim(),
            data: form.value.data,
            separator: form.value.separator === '\\t' ? '\t' : form.value.separator,
            id_column: form.value.idColumn || undefined,
            value_column: form.value.valueColumn || undefined,
            type_override: typeOverride.value || undefined,
            persist_to_h5ad: persistToH5ad.value,
            apply_to_all_datasets: form.value.applyToAll,
          },
          { headers: getHeaders() }
        );

        if (resp.data.success) {
          confirmResult.value = resp.data;
          emit('imported', resp.data);
        } else {
          confirmError.value = resp.data.error || 'Import failed';
        }
      } catch (err: any) {
        confirmError.value = err.response?.data?.error || err.message || 'Import failed';
      } finally {
        confirming.value = false;
      }
    }

    function prevStep() {
      if (step.value > 1) step.value--;
    }

    function close() {
      // Reset state
      step.value = 1;
      form.value = { dataset: '', columnName: '', displayName: '', data: '', separator: '\t', applyToAll: false, idColumn: '', valueColumn: '' };
      validationResult.value = null;
      validationError.value = '';
      confirmResult.value = null;
      confirmError.value = '';
      typeOverride.value = '';
      persistToH5ad.value = false;
      emit('close');
    }

    return {
      step,
      form,
      fileInput,
      validating,
      validationError,
      validationResult,
      typeOverride,
      confirming,
      confirmError,
      confirmResult,
      persistToH5ad,
      dataLineCount,
      matchPercent,
      canValidate,
      parsedHeaders,
      columnMappingWarning,
      parsedSampleRow,
      autoDisplayName,
      triggerFileUpload,
      onFileUpload,
      validate,
      confirmImport,
      prevStep,
      close,
      getEntityLabel,
    };
  },
});
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-container {
  background: white;
  border-radius: 12px;
  width: 640px;
  max-width: 90vw;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h2 {
  margin: 0;
  font-size: 18px;
  color: #1f2937;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 18px;
  color: #6b7280;
  padding: 4px 8px;
  border-radius: 4px;
}

.close-btn:hover {
  background: #f3f4f6;
  color: #111827;
}

.modal-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
}

.modal-footer {
  display: flex;
  align-items: center;
  padding: 16px 24px;
  border-top: 1px solid #e5e7eb;
  gap: 12px;
}

.spacer {
  flex: 1;
}

/* Step indicator */
.step-indicator {
  display: flex;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f3f4f6;
}

.step {
  font-size: 13px;
  font-weight: 500;
  color: #9ca3af;
  padding: 4px 12px;
  border-radius: 16px;
}

.step.active {
  color: #2563eb;
  background: #eff6ff;
}

.step.done {
  color: #059669;
  background: #ecfdf5;
}

/* Forms */
.form-row {
  display: flex;
  gap: 16px;
  align-items: flex-end;
}

.form-group {
  margin-bottom: 16px;
  flex: 1;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #374151;
}

.hint {
  font-weight: 400;
  color: #9ca3af;
}

.form-control {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-control-sm {
  padding: 6px 10px;
  font-size: 13px;
}

.data-textarea {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  resize: vertical;
  min-height: 120px;
}

.data-input-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 8px;
}

.btn-link {
  background: none;
  border: none;
  color: #2563eb;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

.btn-link:hover {
  text-decoration: underline;
}

.hidden {
  display: none;
}

.data-stats {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.radio-group {
  display: flex;
  gap: 20px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  cursor: pointer;
}

.checkbox-group {
  display: flex;
  align-items: flex-end;
}

.toggle-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  cursor: pointer;
}

/* Validation Results */
.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 40px;
  color: #6b7280;
}

.spinner-small {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.validation-error {
  padding: 20px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  color: #991b1b;
}

.validation-error h3 {
  margin: 0 0 8px 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  padding: 12px;
  border-radius: 8px;
  text-align: center;
}

.stat-card.good {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.stat-card.warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.stat-card.neutral {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
}

.stat-card.info {
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.stat-label {
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
}

.match-bar-container {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.match-bar {
  flex: 1;
  height: 8px;
  background: #e5e7eb;
  border-radius: 4px;
  overflow: hidden;
}

.match-bar-fill {
  height: 100%;
  background: #22c55e;
  border-radius: 4px;
  transition: width 0.3s;
}

/* Column Mapping */
.column-mapping-box {
  margin-top: 12px;
  background: #f0f7ff;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  padding: 14px 16px;
}

.column-mapping-header {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.column-mapping-title {
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
}

.column-mapping-hint {
  font-size: 12px;
  color: #6b7280;
}

.column-mapping-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
}

.column-mapping-field {
  flex: 1;
}

.column-mapping-label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
}

.column-mapping-arrow {
  font-size: 20px;
  color: #6b7280;
  padding-bottom: 6px;
  flex-shrink: 0;
}

.column-mapping-warning {
  margin-top: 8px;
  font-size: 12px;
  color: #b45309;
  background: #fffbeb;
  border: 1px solid #fcd34d;
  border-radius: 4px;
  padding: 6px 10px;
}

.column-mapping-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
  color: #374151;
}

.preview-label {
  color: #9ca3af;
  margin-right: 4px;
}

.preview-sep {
  color: #9ca3af;
}

.preview-id code,
.preview-value code {
  background: #f3f4f6;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 12px;
}

.match-percent {
  font-size: 13px;
  font-weight: 600;
  color: #374151;
  white-space: nowrap;
}

.unmatched-details {
  margin-bottom: 16px;
}

.unmatched-details summary {
  cursor: pointer;
  font-size: 13px;
  color: #6b7280;
  padding: 8px;
}

.unmatched-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 8px;
  max-height: 150px;
  overflow-y: auto;
}

.unmatched-id {
  font-size: 11px;
  background: #fef2f2;
  color: #991b1b;
  padding: 2px 6px;
  border-radius: 3px;
}

.sample-values h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #374151;
}

.sample-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.sample-list code {
  font-size: 12px;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 4px;
}

/* Confirm */
.confirm-summary {
  background: #f9fafb;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 16px;
}

.confirm-item {
  font-size: 13px;
  padding: 4px 0;
  color: #374151;
}

.persist-option {
  padding: 12px 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
}

.confirm-success {
  text-align: center;
  padding: 20px;
}

.confirm-success h3 {
  color: #059669;
}

.results-summary {
  margin-top: 16px;
  text-align: left;
}

.result-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-bottom: 1px solid #f3f4f6;
  font-size: 13px;
}

.result-status {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
}

.result-status.applied {
  background: #ecfdf5;
  color: #059669;
}

.result-status.skip {
  background: #f9fafb;
  color: #6b7280;
}

.result-status.error {
  background: #fef2f2;
  color: #dc2626;
}

.persist-badge {
  font-size: 11px;
  color: #d97706;
}

/* Buttons */
.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #2563eb;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #1d4ed8;
}

.btn-secondary {
  background: #f3f4f6;
  color: #374151;
}

.btn-secondary:hover {
  background: #e5e7eb;
}
</style>
