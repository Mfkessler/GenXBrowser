<template>
  <div class="admin-panel">
    <header class="admin-header">
      <h1>GenXBrowser Admin Panel</h1>
      <div class="header-actions">
        <button @click="reloadConfig" class="btn btn-secondary">
          <span class="icon">🔄</span> Reload Config
        </button>
        <button @click="saveConfig" class="btn btn-primary" :disabled="!hasChanges">
          <span class="icon">💾</span> Save Changes
        </button>
        <button @click="restartBackend" class="btn btn-warning">
          <span class="icon">🔄</span> Restart Backend
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>Loading configuration...</p>
    </div>

    <div v-else-if="error" class="error">
      <p>{{ error }}</p>
      <button @click="loadConfig" class="btn btn-primary">Retry</button>
    </div>

    <div v-else class="admin-content">
      <!-- Tabs -->
      <div class="tabs">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          :class="['tab', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        <!-- Project Settings -->
        <div v-show="activeTab === 'project'" class="section">
          <h2>Project Settings</h2>
          <div class="form-group">
            <label>Project Name:</label>
            <input v-model="config.project_name" type="text" class="form-control" />
          </div>
          <div class="form-group">
            <label>Description:</label>
            <textarea v-model="config.description" class="form-control" rows="3"></textarea>
          </div>
          <div class="form-group">
            <label>Version:</label>
            <input v-model="config.version" type="text" class="form-control" readonly />
          </div>
        </div>

        <!-- Species Management -->
        <div v-show="activeTab === 'species'" class="section">
          <div class="section-header">
            <div>
              <h2>Species / Datasets</h2>
              <p class="info">
                <strong>Note:</strong> Species are auto-discovered from H5AD files. 
                Toggle species on/off and configure display names and tags.
              </p>
            </div>
          </div>

          <div class="species-table-container">
            <table class="species-table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Full Name</th>
                  <th>Display Name</th>
                  <th>Status</th>
                  <th>Enabled</th>
                  <th>Tags</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="dataset in datasets"
                  :key="dataset.code"
                  :class="{ 'disabled-row': config?.species?.[dataset.code]?.enabled === false }"
                >
                  <td><code class="species-code">{{ dataset.code }}</code></td>
                  <td>
                    <input
                      v-if="config?.species?.[dataset.code]"
                      v-model="config.species[dataset.code].full_name"
                      type="text"
                      class="form-control form-control-sm"
                    />
                  </td>
                  <td>
                    <input
                      v-if="config?.species?.[dataset.code]"
                      v-model="config.species[dataset.code].display_name"
                      type="text"
                      class="form-control form-control-sm"
                    />
                  </td>
                  <td>
                    <span 
                      class="status-indicator"
                      :class="{ 
                        'active': config?.species?.[dataset.code]?.enabled !== false,
                        'inactive': config?.species?.[dataset.code]?.enabled === false
                      }"
                      :title="config?.species?.[dataset.code]?.enabled !== false ? 'Active' : 'Disabled'"
                    >
                      ●
                    </span>
                  </td>
                  <td>
                    <label class="toggle-inline">
                      <input
                        v-if="config?.species?.[dataset.code]"
                        type="checkbox"
                        v-model="config.species[dataset.code].enabled"
                      />
                      <span class="toggle-slider"></span>
                    </label>
                  </td>
                  <td>
                    <input
                      v-if="config?.species?.[dataset.code]"
                      :value="config.species[dataset.code].tags ? config.species[dataset.code].tags.join(', ') : ''"
                      @input="updateTags(dataset.code, ($event.target as HTMLInputElement).value)"
                      type="text"
                      class="form-control form-control-sm"
                      placeholder="tag1, tag2"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Column Definitions -->
        <div v-show="activeTab === 'columns'" class="section">
          <h2>{{ getEntityMetadataColumnsLabel() }} (.var)</h2>
          <p class="info">
            Configure {{ getEntityLabelPluralLower() }} metadata columns (from .var). These appear in the {{ getEntityLabelPlural() }} tab.
          </p>

          <div class="search-box">
            <input
              v-model="columnSearch"
              type="text"
              :placeholder="`Search ${getEntityLabelPluralLower()} columns...`"
              class="form-control"
            />
          </div>

          <div class="columns-table">
            <table>
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Display Name</th>
                  <th>Type</th>
                  <th>Meta</th>
                  <th>Visible</th>
                  <th>Array</th>
                  <th>Order</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(colDef, colName) in filteredColumns"
                  :key="colName"
                  class="column-row"
                >
                  <td><code>{{ colName }}</code></td>
                  <td>
                    <input
                      v-model="colDef.display_name"
                      type="text"
                      class="form-control form-control-sm"
                    />
                  </td>
                  <td>
                    <select v-model="colDef.type" class="form-control form-control-sm">
                      <option value="text">text</option>
                      <option value="bigint">bigint</option>
                      <option value="double precision">double precision</option>
                      <option value="boolean">boolean</option>
                      <option value="array">array</option>
                    </select>
                  </td>
                  <td>
                    <input type="checkbox" v-model="colDef.is_meta" />
                  </td>
                  <td>
                    <input type="checkbox" v-model="colDef.visible" />
                  </td>
                  <td>
                    <input type="checkbox" v-model="colDef.is_array" />
                  </td>
                  <td>
                    <input
                      v-model.number="colDef.order"
                      type="number"
                      class="form-control form-control-sm"
                      min="0"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Sample Metadata Columns -->
        <div v-show="activeTab === 'samples'" class="section">
          <h2>Sample Metadata Columns (.obs)</h2>
          <p class="info">
            Configure sample metadata columns (from .obs). These appear in the Samples tab.
          </p>

          <div class="form-group">
            <label class="toggle">
              <input 
                type="checkbox" 
                v-model="config.sample_metadata_columns.enabled"
                v-if="config.sample_metadata_columns"
              />
              <input 
                type="checkbox" 
                disabled
                v-else
              />
              <span class="slider"></span>
              <span class="label">
                {{ config.sample_metadata_columns?.enabled ? 'Sample Metadata Enabled' : 'Sample Metadata Disabled' }}
              </span>
            </label>
          </div>

          <div class="search-box">
            <input
              v-model="columnSearch"
              type="text"
              placeholder="Search sample columns..."
              class="form-control"
            />
          </div>

          <div class="columns-table">
            <table>
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Display Name</th>
                  <th>Type</th>
                  <th>Visible</th>
                  <th>Order</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(colDef, colName) in filteredColumns"
                  :key="colName"
                  class="column-row"
                >
                  <td><code>{{ colName }}</code></td>
                  <td>
                    <input
                      v-model="colDef.display_name"
                      type="text"
                      class="form-control form-control-sm"
                    />
                  </td>
                  <td>
                    <select v-model="colDef.type" class="form-control form-control-sm">
                      <option value="text">text</option>
                      <option value="bigint">bigint</option>
                      <option value="double precision">double precision</option>
                      <option value="boolean">boolean</option>
                    </select>
                  </td>
                  <td>
                    <input type="checkbox" v-model="colDef.visible" />
                  </td>
                  <td>
                    <input
                      v-model.number="colDef.order"
                      type="number"
                      class="form-control form-control-sm"
                      min="0"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Frontend Settings -->
        <div v-show="activeTab === 'frontend'" class="section">
          <h2>Frontend Display Settings</h2>
          
          <div class="form-group">
            <label>Default Columns (shown by default):</label>
            <input
              :value="config.frontend_settings?.default_columns?.join(', ') || ''"
              @input="updateArray('default_columns', ($event.target as HTMLInputElement).value)"
              type="text"
              class="form-control"
              placeholder="gene_id, description, og"
            />
          </div>

          <div class="form-group">
            <label>Hidden Columns (completely hidden):</label>
            <input
              :value="config.frontend_settings?.hidden_columns?.join(', ') || ''"
              @input="updateArray('hidden_columns', ($event.target as HTMLInputElement).value)"
              type="text"
              class="form-control"
            />
          </div>
        </div>

        <!-- Data Paths -->
        <div v-show="activeTab === 'paths'" class="section">
          <h2>Data Paths</h2>
          <p class="info">
            These paths are usually set via environment variables in Docker Compose.
          </p>
          
          <div class="form-group">
            <label>H5AD Data Directory:</label>
            <input v-model="config.data_paths.h5ad_dir" type="text" class="form-control" />
          </div>
          <div class="form-group">
            <label>Gene Trees Path:</label>
            <input v-model="config.data_paths.gene_trees_path" type="text" class="form-control" />
          </div>
          <div class="form-group">
            <label>Sequences Directory:</label>
            <input v-model="config.data_paths.sequences_dir" type="text" class="form-control" />
          </div>
        </div>
      </div>
    </div>

    <!-- Status Bar -->
    <div v-if="statusMessage" :class="['status-bar', statusType]">
      {{ statusMessage }}
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted, watch } from 'vue';
import axios from 'axios';
import { getEntityMetadataColumnsLabel, getEntityLabelPlural, getEntityLabelPluralLower } from '@/shared/dataTypeLabels';

interface Species {
  code: string;
  full_name: string;
  display_name: string;
  enabled: boolean;
  tags?: string[];
  available_layers?: string[];
  layer_preference?: string;
}

interface ColumnDefinition {
  display_name: string;
  type: string;
  is_array: boolean;
  is_meta: boolean;
  is_sample_metadata?: boolean;
  visible: boolean;
  sortable?: boolean;
  filterable?: boolean;
  order: number;
  description?: string;
}

interface Config {
  project_name: string;
  version: string;
  description?: string;
  species: Record<string, Species>;
  column_mappings: {
    h5ad_to_display: Record<string, string>;
  };
  column_definitions: Record<string, ColumnDefinition>;
  sample_metadata_columns?: {
    enabled: boolean;
    columns: string[];
    default_visible_columns: string[];
    description?: string;
  };
  frontend_settings: {
    default_columns: string[];
    hidden_columns: string[];
    column_order: string[];
  };
  data_paths: {
    h5ad_dir: string;
    gene_trees_path: string;
    sequences_dir: string;
  };
}

export default defineComponent({
  name: 'AdminPanel',
  setup() {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '/api';
    const adminBaseUrl = `${apiBaseUrl}/api/admin`;
    
    const config = ref<Config | null>(null);
    const originalConfig = ref<string>('');
    const loading = ref(true);
    const error = ref<string | null>(null);
    const statusMessage = ref('');
    const statusType = ref<'success' | 'error' | 'info'>('info');
    
    const activeTab = ref('project');
    const columnSearch = ref('');
    const datasets = ref<any[]>([]);
    
    const tabs = [
      { id: 'project', label: 'Project Settings' },
      { id: 'species', label: 'Species' },
      { id: 'columns', label: `Columns (${getEntityLabelPlural()})` },
      { id: 'samples', label: 'Columns (Samples)' },
      { id: 'frontend', label: 'Frontend' },
      { id: 'paths', label: 'Data Paths' },
    ];

    const hasChanges = computed(() => {
      return JSON.stringify(config.value) !== originalConfig.value;
    });

    const filteredColumns = computed(() => {
      if (!config.value?.column_definitions) return {};
      
      const search = columnSearch.value.toLowerCase();
      
      // Filter by search and current tab
      const isGeneTab = activeTab.value === 'columns';
      const isSampleTab = activeTab.value === 'samples';
      
      return Object.fromEntries(
        Object.entries(config.value.column_definitions).filter(([key, val]) => {
          // Filter by tab
          if (isGeneTab && val.is_sample_metadata) return false;
          if (isSampleTab && !val.is_sample_metadata) return false;
          
          // Filter by search
          if (!search) return true;
          return key.toLowerCase().includes(search) ||
                 val.display_name.toLowerCase().includes(search);
        })
      );
    });

    async function loadConfig() {
      loading.value = true;
      error.value = null;
      try {
        const response = await axios.get(`${apiBaseUrl}/api/admin/config`);
        config.value = response.data.config;
        originalConfig.value = JSON.stringify(config.value);
        showStatus('Configuration loaded', 'success');
      } catch (err: any) {
        error.value = err.response?.data?.error || err.message || 'Failed to load configuration';
        showStatus(error.value, 'error');
      } finally {
        loading.value = false;
      }
    }

    async function loadDatasets() {
      try {
        const response = await axios.get(`${adminBaseUrl}/datasets`);
        datasets.value = response.data.datasets;
      } catch (err: any) {
        console.error('Failed to load datasets:', err);
        showStatus('Failed to load dataset information', 'error');
      }
    }

    async function saveConfig() {
      if (!config.value) return;
      
      try {
        const response = await axios.put(`${apiBaseUrl}/api/admin/config`, config.value);
        originalConfig.value = JSON.stringify(config.value);
        showStatus('Configuration saved successfully!', 'success');
      } catch (err: any) {
        const errorMsg = err.response?.data?.error || err.message || 'Failed to save configuration';
        showStatus(errorMsg, 'error');
      }
    }

    async function reloadConfig() {
      try {
        const response = await axios.post(`${apiBaseUrl}/api/admin/config/reload`);
        config.value = response.data.config;
        originalConfig.value = JSON.stringify(config.value);
        showStatus('Configuration reloaded from file', 'success');
      } catch (err: any) {
        const errorMsg = err.response?.data?.error || 'Failed to reload configuration';
        showStatus(errorMsg, 'error');
      }
    }

    async function restartBackend() {
      if (!confirm('This will restart the backend. Continue?')) return;
      
      try {
        await axios.post(`${apiBaseUrl}/api/admin/restart`);
        showStatus('Backend restart initiated. Please wait...', 'info');
      } catch (err: any) {
        const errorMsg = err.response?.data?.error || 'Restart request sent (manual restart may be required)';
        showStatus(errorMsg, 'info');
      }
    }

    function updateTags(code: string, value: string) {
      if (!config.value) return;
      config.value.species[code].tags = value.split(',').map(t => t.trim()).filter(t => t);
    }

    function updateArray(field: 'default_columns' | 'hidden_columns', value: string) {
      if (!config.value) return;
      config.value.frontend_settings[field] = value.split(',').map(t => t.trim()).filter(t => t);
    }

    function showStatus(message: string, type: 'success' | 'error' | 'info') {
      statusMessage.value = message;
      statusType.value = type;
      setTimeout(() => {
        statusMessage.value = '';
      }, 5000);
    }

    onMounted(() => {
      loadConfig();
      loadDatasets();
    });

    return {
      config,
      loading,
      error,
      statusMessage,
      statusType,
      activeTab,
      columnSearch,
      tabs,
      hasChanges,
      filteredColumns,
      datasets,
      loadConfig,
      saveConfig,
      reloadConfig,
      restartBackend,
      updateTags,
      updateArray,
      loadDatasets,
      // Dynamic label functions
      getEntityMetadataColumnsLabel,
      getEntityLabelPlural,
      getEntityLabelPluralLower,
    };
  },
});
</script>

<style scoped>
.admin-panel {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e0e0e0;
}

.admin-header h1 {
  margin: 0;
  font-size: 28px;
  color: #333;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 5px;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #545b62;
}

.btn-warning {
  background: #ffc107;
  color: #333;
}

.btn-warning:hover {
  background: #e0a800;
}

.loading, .error {
  text-align: center;
  padding: 50px;
}

.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #007bff;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
  margin: 0 auto 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.tabs {
  display: flex;
  gap: 5px;
  border-bottom: 2px solid #e0e0e0;
  margin-bottom: 30px;
}

.tab {
  padding: 12px 24px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  color: #666;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
}

.tab:hover {
  color: #007bff;
  background: #f8f9fa;
}

.tab.active {
  color: #007bff;
  border-bottom-color: #007bff;
}

.section {
  background: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.section h2 {
  margin-top: 0;
  margin-bottom: 20px;
  font-size: 22px;
  color: #333;
}

.info {
  padding: 12px;
  background: #e7f3ff;
  border-left: 4px solid #007bff;
  margin-bottom: 20px;
  border-radius: 4px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #555;
}

.form-control {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-control:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0,123,255,0.1);
}

.form-control-sm {
  padding: 5px 8px;
  font-size: 13px;
}

.species-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  gap: 30px;
}

.section-header h2 {
  margin-bottom: 10px;
}

.bulk-actions {
  min-width: 300px;
}

.bulk-actions label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #555;
  font-size: 14px;
}

.bulk-action-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.bulk-action-row select {
  flex: 1;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
}

.species-table-container {
  overflow-x: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.species-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

.species-table thead {
  background: #f8f9fa;
  position: sticky;
  top: 0;
  z-index: 5;
}

.species-table th {
  padding: 12px 10px;
  text-align: left;
  font-weight: 600;
  color: #555;
  font-size: 13px;
  text-transform: uppercase;
  border-bottom: 2px solid #dee2e6;
  white-space: nowrap;
}

.species-table td {
  padding: 10px;
  border-bottom: 1px solid #e0e0e0;
  vertical-align: middle;
}

.species-table tbody tr:hover {
  background: #f8f9fa;
}

.species-table tbody tr.disabled-row {
  opacity: 0.5;
  background: #f9f9f9;
}

.species-code {
  background: #007bff;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 13px;
  display: inline-block;
}

.status-indicator {
  font-size: 20px;
  display: inline-block;
}

.status-indicator.active {
  color: #4caf50;
}

.status-indicator.inactive {
  color: #ccc;
}

.toggle-inline {
  display: flex;
  align-items: center;
  cursor: pointer;
  margin: 0;
}

.toggle-inline input {
  position: relative;
  width: 44px;
  height: 22px;
  -webkit-appearance: none;
  background: #ccc;
  outline: none;
  border-radius: 20px;
  transition: 0.3s;
  cursor: pointer;
}

.toggle-inline input:checked {
  background: #4caf50;
}

.toggle-inline input::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  background: white;
  transition: 0.3s;
}

.toggle-inline input:checked::before {
  left: 24px;
}

.species-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.species-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
}

.species-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-bottom: 1px solid #ddd;
}

.species-header h3 {
  margin: 0;
  font-size: 18px;
  font-family: monospace;
}

.species-body {
  padding: 15px;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}

.toggle input {
  position: relative;
  width: 50px;
  height: 24px;
  -webkit-appearance: none;
  background: #ccc;
  outline: none;
  border-radius: 20px;
  transition: 0.3s;
}

.toggle input:checked {
  background: #4caf50;
}

.toggle input::before {
  content: '';
  position: absolute;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  background: white;
  transition: 0.3s;
}

.toggle input:checked::before {
  left: 28px;
}

.search-box {
  margin-bottom: 20px;
}

.columns-table {
  max-height: 600px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.columns-table table {
  width: 100%;
  border-collapse: collapse;
}

.columns-table thead {
  position: sticky;
  top: 0;
  background: #f8f9fa;
  z-index: 10;
}

.columns-table th,
.columns-table td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #e0e0e0;
}

.columns-table th {
  font-weight: 600;
  color: #555;
  font-size: 13px;
  text-transform: uppercase;
}

.columns-table td code {
  background: #f4f4f4;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

.column-row:hover {
  background: #f8f9fa;
}

.status-bar {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 15px 25px;
  border-radius: 5px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.2);
  font-weight: 500;
  z-index: 1000;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.status-bar.success {
  background: #4caf50;
  color: white;
}

.status-bar.error {
  background: #f44336;
  color: white;
}

.status-bar.info {
  background: #2196f3;
  color: white;
}
</style>
