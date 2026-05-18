<template>
  <div class="admin-panel">
    <!-- Auth Gate -->
    <div v-if="authRequired && !authenticated" class="auth-gate">
      <div class="auth-card">
        <h2>🔒 Admin Access</h2>
        <p>Enter the admin token to access the configuration panel.</p>
        <div class="auth-form">
          <input
            v-model="tokenInput"
            type="password"
            class="form-control"
            placeholder="Admin token"
            @keyup.enter="authenticate"
          />
          <button class="btn btn-primary" @click="authenticate" :disabled="!tokenInput">
            Authenticate
          </button>
        </div>
        <p v-if="authError" class="auth-error">{{ authError }}</p>
      </div>
    </div>

    <!-- Main Panel -->
    <template v-else>
      <header class="admin-header">
        <div class="header-left">
          <h1>GenXBrowser Admin</h1>
          <span class="version-badge" v-if="config">v{{ config.version }}</span>
        </div>
        <div class="header-actions">
          <!-- Profile Dropdown -->
          <div class="profile-dropdown" v-if="!loading">
            <button class="btn btn-outline" @click="showProfileMenu = !showProfileMenu">
              📋 Profiles
            </button>
            <div v-if="showProfileMenu" class="dropdown-menu">
              <div class="dropdown-header">Config Profiles</div>
              <button class="dropdown-item" @click="openSaveProfile">💾 Save current as profile</button>
              <div v-if="profiles.length" class="dropdown-divider"></div>
              <button
                v-for="p in profiles"
                :key="p.name"
                class="dropdown-item"
                @click="loadProfile(p.name)"
              >
                📁 {{ p.name }}
                <span class="dropdown-hint">{{ p.species_count }} species, {{ p.columns_count }} cols</span>
              </button>
              <div v-if="!profiles.length" class="dropdown-empty">No saved profiles</div>
            </div>
          </div>

          <button @click="reloadConfig" class="btn btn-outline">
            🔄 Reload
          </button>
          <button @click="saveConfig" class="btn btn-primary" :disabled="!hasChanges">
            💾 Save
          </button>
          <button @click="restartBackend" class="btn btn-warning">
            ⚡ Restart
          </button>
        </div>
      </header>

      <div v-if="loading" class="loading-state">
        <div class="spinner"></div>
        <p>Loading configuration...</p>
      </div>

      <div v-else-if="error" class="error-state">
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
            <span class="tab-icon">{{ tab.icon }}</span>
            {{ tab.label }}
          </button>
        </div>

        <!-- Tab Content -->
        <div class="tab-content">
          <!-- Project Settings -->
          <div v-show="activeTab === 'project'" class="section">
            <h2>Project Settings</h2>
            <div class="form-grid">
              <div class="form-group">
                <label>Project Name</label>
                <input v-model="config.project_name" type="text" class="form-control" />
              </div>
              <div class="form-group">
                <label>Version</label>
                <input v-model="config.version" type="text" class="form-control" readonly />
              </div>
            </div>
            <div class="form-group">
              <label>Description</label>
              <textarea v-model="config.description" class="form-control" rows="3"></textarea>
            </div>
          </div>

          <!-- Species Management -->
          <div v-show="activeTab === 'species'" class="section">
            <div class="section-header">
              <div>
                <h2>Species / Datasets</h2>
                <p class="info">
                  Species are auto-discovered from H5AD files. Toggle on/off and configure display names and tags.
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
                          active: config?.species?.[dataset.code]?.enabled !== false,
                          inactive: config?.species?.[dataset.code]?.enabled === false
                        }"
                      >●</span>
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

          <!-- Metadata (Chip Manager) -->
          <div v-show="activeTab === 'metadata'" class="section">
            <h2>Metadata Columns</h2>
            <p class="info">
              Manage visibility, display names, and order of metadata columns.
              Drag chips to reorder — this controls how they appear in the sidebar and other column selectors.
              Double-click a chip label to rename it.
            </p>

            <MetadataChipManager
              v-if="config.column_definitions"
              :column-definitions="config.column_definitions"
              :tissue-column="config.tissue_column ?? null"
              @update:columns="onColumnsUpdate"
              @update:tissue-column="config.tissue_column = $event"
              @add-metadata="openMetadataImport"
              @delete-column="deleteColumn"
            />
          </div>

          <!-- Frontend Settings -->
          <div v-show="activeTab === 'frontend'" class="section">
            <h2>Frontend Display Settings</h2>

            <div class="form-group">
              <label>Default Columns <span class="hint">(comma-separated, shown by default)</span></label>
              <input
                :value="config.frontend_settings?.default_columns?.join(', ') || ''"
                @input="updateArray('default_columns', ($event.target as HTMLInputElement).value)"
                type="text"
                class="form-control"
                placeholder="gene_id, description, ortho_id"
              />
            </div>

            <div class="form-group">
              <label>Hidden Columns <span class="hint">(comma-separated, completely hidden from UI)</span></label>
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
              Usually set via environment variables in Docker Compose. Changes here require a backend restart.
            </p>

            <div class="form-group">
              <label>H5AD Data Directory</label>
              <input v-model="config.data_paths.h5ad_dir" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label>Gene Trees Path</label>
              <input v-model="config.data_paths.gene_trees_path" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label>Sequences Directory</label>
              <input v-model="config.data_paths.sequences_dir" type="text" class="form-control" />
            </div>
          </div>

          <!-- AI Assistant -->
          <div v-show="activeTab === 'assistant'" class="section">
            <h2>AI Assistant</h2>
            <p class="info">
              Configure an OpenAI-compatible chat completion endpoint. When disabled or unconfigured,
              the assistant UI is completely hidden from end users.
            </p>

            <template v-if="config.llm_config">
              <div
                v-if="config.llm_config.enabled && (!config.llm_config.api_base || !config.llm_config.model)"
                class="banner banner-warning"
              >
                ⚠️ Assistant is enabled but <strong>API base</strong> and <strong>model</strong> must both be set for it to work.
              </div>

              <div class="form-group">
                <label class="toggle-label">
                  <input type="checkbox" v-model="config.llm_config.enabled" />
                  <span>Enable assistant</span>
                </label>
              </div>

              <div class="form-group">
                <label>API base URL</label>
                <input
                  v-model="config.llm_config.api_base"
                  type="text"
                  class="form-control"
                  placeholder="https://api.openai.com"
                />
                <small class="hint">Base URL for an OpenAI-compatible endpoint; <code>/v1/chat/completions</code> is appended automatically.</small>
              </div>

              <div class="form-group">
                <label>API key</label>
                <input
                  v-model="config.llm_config.api_key"
                  type="password"
                  class="form-control"
                  autocomplete="off"
                  :placeholder="config.llm_config.api_key === REDACTED_PLACEHOLDER ? 'Already configured — leave blank to keep' : 'sk-…'"
                />
                <small class="hint">
                  Stored server-side only. Shown as <code>__set__</code> when already configured; leave empty on save to keep the existing key.
                </small>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label>Primary model</label>
                  <input v-model="config.llm_config.model" type="text" class="form-control" placeholder="gpt-4o-mini" />
                </div>
                <div class="form-group">
                  <label>Fallback model <span class="hint">(optional)</span></label>
                  <input v-model="config.llm_config.fallback_model" type="text" class="form-control" />
                </div>
              </div>

              <div class="form-group">
                <label>System prompt</label>
                <textarea
                  v-model="config.llm_config.system_prompt"
                  class="form-control"
                  rows="6"
                ></textarea>
                <small class="hint">Runtime context about the loaded datasets is appended automatically.</small>
              </div>

              <div class="form-row">
                <div class="form-group">
                  <label>Temperature</label>
                  <input
                    v-model.number="config.llm_config.temperature"
                    type="number"
                    class="form-control"
                    min="0"
                    max="2"
                    step="0.05"
                  />
                </div>
                <div class="form-group">
                  <label>Max tokens</label>
                  <input
                    v-model.number="config.llm_config.max_tokens"
                    type="number"
                    class="form-control"
                    min="16"
                    max="16384"
                  />
                </div>
                <div class="form-group">
                  <label>Request timeout (s)</label>
                  <input
                    v-model.number="config.llm_config.request_timeout_s"
                    type="number"
                    class="form-control"
                    min="5"
                    max="600"
                  />
                </div>
              </div>

              <div class="form-group">
                <button
                  class="btn btn-outline"
                  :disabled="llmTestRunning || !config.llm_config.api_base || !config.llm_config.model"
                  @click="testLlmConnection"
                >
                  {{ llmTestRunning ? 'Testing…' : '🔌 Test connection' }}
                </button>
                <div v-if="llmTestResult" class="test-result" :class="llmTestResult.ok ? 'ok' : 'err'">
                  <template v-if="llmTestResult.ok">
                    ✅ Connected to <code>{{ llmTestResult.model }}</code> in {{ llmTestResult.latency_ms }} ms.
                  </template>
                  <template v-else>
                    ❌ {{ llmTestResult.error }}
                  </template>
                </div>
                <small class="hint">Uses the unsaved values above (falling back to the stored API key when the field is empty).</small>
              </div>
            </template>
          </div>
        </div>
      </div>

      <!-- Status Bar -->
      <div v-if="statusMessage" :class="['status-bar', statusType]">
        {{ statusMessage }}
      </div>

      <!-- Metadata Import Modal -->
      <MetadataImportModal
        :visible="showImportModal"
        :target="importTarget"
        :datasets="datasets"
        :admin-token="adminToken"
        :api-base-url="apiBaseUrl"
        @close="showImportModal = false"
        @imported="onMetadataImported"
      />

      <!-- Metadata Delete Confirmation Modal -->
      <div v-if="deleteModalColumn" class="modal-overlay" @click.self="closeDeleteModal">
        <div class="modal-sm">
          <h3>Delete Custom Metadata</h3>
          <p style="color: #6b7280; font-size: 14px; margin: 0 0 16px 0;">
            Delete <strong>{{ deleteModalColumn }}</strong> from the application metadata configuration.
          </p>
          <label class="toggle-label" style="margin-bottom: 20px; display: flex; align-items: flex-start; gap: 8px;">
            <input type="checkbox" v-model="deleteFromH5ad" />
            <span>
              <strong>Permanently delete from H5AD files</strong>
              <span class="hint" style="display: block;">Removes the column from the underlying .h5ad file for each enabled dataset.</span>
            </span>
          </label>
          <div class="modal-actions">
            <button class="btn btn-outline" @click="closeDeleteModal">Cancel</button>
            <button class="btn btn-danger" :disabled="deleteRunning" @click="confirmDeleteColumn">
              {{ deleteRunning ? 'Deleting…' : 'Delete' }}
            </button>
          </div>
        </div>
      </div>

      <!-- Reload Confirmation Modal -->
      <div v-if="showReloadConfirm" class="modal-overlay" @click.self="showReloadConfirm = false">
        <div class="modal-sm">
          <h3>⚠️ Discard unsaved changes?</h3>
          <p style="color: #6b7280; font-size: 14px; margin: 0 0 20px 0;">
            You have unsaved changes. Reloading will overwrite them with the last saved version on disk.
          </p>
          <div class="modal-actions">
            <button class="btn btn-outline" @click="showReloadConfirm = false">Back</button>
            <button class="btn btn-warning" @click="_doReload">Discard &amp; Reload</button>
          </div>
        </div>
      </div>

      <!-- Save Profile Modal -->
      <div v-if="showSaveProfileModal" class="modal-overlay" @click.self="showSaveProfileModal = false">
        <div class="modal-sm">
          <h3>Save Config Profile</h3>
          <div class="form-group">
            <label>Profile Name</label>
            <input
              v-model="profileName"
              type="text"
              class="form-control"
              placeholder="e.g. production, minimal"
              @keyup.enter="saveProfile"
            />
          </div>
          <div class="form-group">
            <label>Description <span class="hint">(optional)</span></label>
            <input v-model="profileDescription" type="text" class="form-control" />
          </div>
          <div class="modal-actions">
            <button class="btn btn-outline" @click="showSaveProfileModal = false">Cancel</button>
            <button class="btn btn-primary" :disabled="!profileName.trim()" @click="saveProfile">
              Save Profile
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script lang="ts">
import { defineComponent, ref, computed, onMounted } from 'vue';
import axios from 'axios';
import MetadataChipManager from '@/components/MetadataChipManager.vue';
import MetadataImportModal from '@/components/MetadataImportModal.vue';
import { useColumnsStore } from '@/stores/columns';

interface Config {
  project_name: string;
  version: string;
  description?: string;
  species: Record<string, SpeciesConfig>;
  column_mappings: { h5ad_to_display: Record<string, string> };
  column_definitions: Record<string, ColumnDefinition>;
  sample_metadata_columns?: { enabled: boolean; columns: string[] };
  tissue_column?: string | null;
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
  llm_config?: {
    enabled: boolean;
    api_base: string;
    api_key: string;
    model: string;
    fallback_model: string;
    system_prompt: string;
    request_timeout_s: number;
    max_tokens: number;
    temperature: number;
  };
}

interface SpeciesConfig {
  full_name?: string;
  display_name?: string;
  enabled?: boolean;
  tags?: string[];
  [key: string]: unknown;
}

interface ColumnDefinition {
  display_name?: string;
  type?: string;
  visible?: boolean;
  is_meta?: boolean;
  is_sample_metadata?: boolean;
  is_array?: boolean;
  array_separator?: string;
  order?: number;
  source?: 'auto' | 'custom';
  sortable?: boolean;
}

interface Dataset {
  code: string;
  full_name: string;
  display_name: string;
  enabled: boolean;
  [key: string]: unknown;
}

interface DatasetResponse {
  code: string;
  full_name?: string;
  display_name?: string;
  enabled?: boolean;
  [key: string]: unknown;
}

interface Profile {
  name: string;
  project_name?: string;
  description?: string;
  species_count?: number;
  columns_count?: number;
}

export default defineComponent({
  name: 'AdminPanel',
  components: { MetadataChipManager, MetadataImportModal },
  setup() {
    const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || '';
    const adminBaseUrl = `${apiBaseUrl}/api/admin`;
    const columnsStore = useColumnsStore();

    // Auth state
    const authRequired = ref(false);
    const authenticated = ref(false);
    const adminToken = ref('');
    const tokenInput = ref('');
    const authError = ref('');

    // Config state
    const config = ref<Config | null>(null);
    const originalConfig = ref('');
    const loading = ref(true);
    const error = ref<string | null>(null);
    const statusMessage = ref('');
    const statusType = ref<'success' | 'error' | 'info'>('info');

    // UI state
    const activeTab = ref('project');
    const datasets = ref<Dataset[]>([]);
    const profiles = ref<Profile[]>([]);
    const showProfileMenu = ref(false);
    const showSaveProfileModal = ref(false);
    const profileName = ref('');
    const profileDescription = ref('');
    const showReloadConfirm = ref(false);

    // Import modal state
    const showImportModal = ref(false);
    const importTarget = ref<'var' | 'obs'>('var');
    const deleteModalColumn = ref<string | null>(null);
    const deleteFromH5ad = ref(false);
    const deleteRunning = ref(false);

    const tabs = [
      { id: 'project', label: 'Project', icon: '⚙️' },
      { id: 'species', label: 'Species', icon: '🧬' },
      { id: 'metadata', label: 'Metadata', icon: '📊' },
      { id: 'frontend', label: 'Frontend', icon: '🎨' },
      { id: 'paths', label: 'Data Paths', icon: '📁' },
      { id: 'assistant', label: 'AI Assistant', icon: '🤖' },
    ];

    // AI assistant test-connection state
    const llmTestRunning = ref(false);
    const llmTestResult = ref<{ ok: boolean; latency_ms?: number; model?: string; error?: string } | null>(null);

    const REDACTED_PLACEHOLDER = '__set__';

    function ensureLlmConfig(c: Config | null) {
      if (!c) return;
      if (!c.llm_config) {
        c.llm_config = {
          enabled: false,
          api_base: '',
          api_key: '',
          model: '',
          fallback_model: '',
          system_prompt: '',
          request_timeout_s: 60,
          max_tokens: 1024,
          temperature: 0.2,
        };
      }
    }

    async function testLlmConnection() {
      if (!config.value?.llm_config) return;
      llmTestRunning.value = true;
      llmTestResult.value = null;
      try {
        const payload: Record<string, unknown> = { ...config.value.llm_config };
        // If key is empty or placeholder, don't send → backend will use stored key
        if (!payload.api_key || payload.api_key === REDACTED_PLACEHOLDER) {
          delete payload.api_key;
        }
        const resp = await axios.post(`${adminBaseUrl}/llm/test`, payload, {
          headers: getAuthHeaders(),
        });
        llmTestResult.value = { ok: true, latency_ms: resp.data.latency_ms, model: resp.data.model };
      } catch (err: unknown) {
        llmTestResult.value = { ok: false, error: getRequestErrorMessage(err, 'Test failed') };
      } finally {
        llmTestRunning.value = false;
      }
    }

    const hasChanges = computed(() => {
      return JSON.stringify(config.value) !== originalConfig.value;
    });

    function getAuthHeaders() {
      const headers: Record<string, string> = {};
      if (adminToken.value) {
        headers['Authorization'] = `Bearer ${adminToken.value}`;
      }
      return headers;
    }

    function getRequestErrorMessage(err: unknown, fallback: string): string {
      if (axios.isAxiosError<{ error?: string }>(err)) {
        return err.response?.data?.error || err.message || fallback;
      }
      return err instanceof Error ? err.message : fallback;
    }

    // ========== Auth ==========

    async function checkAuth() {
      try {
        const resp = await axios.get(`${adminBaseUrl}/auth/check`);
        authRequired.value = resp.data.auth_required;
        if (!resp.data.auth_required) {
          authenticated.value = true;
        }
      } catch {
        // Auth check failed, assume no auth required
        authenticated.value = true;
      }
    }

    async function authenticate() {
      authError.value = '';
      adminToken.value = tokenInput.value;
      try {
        const resp = await axios.get(`${adminBaseUrl}/auth/check`, {
          headers: { Authorization: `Bearer ${tokenInput.value}` },
        });
        if (resp.data.authenticated) {
          authenticated.value = true;
          sessionStorage.setItem('admin_token', tokenInput.value);
          loadConfig();
          loadDatasets();
          loadProfiles();
        } else {
          authError.value = 'Invalid token';
          adminToken.value = '';
        }
      } catch {
        authError.value = 'Authentication failed';
        adminToken.value = '';
      }
    }

    // ========== Config CRUD ==========

    async function loadConfig() {
      loading.value = true;
      error.value = null;
      try {
        const resp = await axios.get(`${adminBaseUrl}/config`, {
          headers: getAuthHeaders(),
        });
        config.value = resp.data.config;
        ensureLlmConfig(config.value);
        originalConfig.value = JSON.stringify(config.value);
        showStatus('Configuration loaded', 'success');
      } catch (err: unknown) {
        error.value = getRequestErrorMessage(err, 'Failed to load');
        showStatus(error.value!, 'error');
      } finally {
        loading.value = false;
      }
    }

    async function saveConfig() {
      if (!config.value) return;
      try {
        await axios.put(`${adminBaseUrl}/config`, config.value, {
          headers: getAuthHeaders(),
        });
        originalConfig.value = JSON.stringify(config.value);
        // Refresh the app's column store so changes are visible immediately
        await columnsStore.refreshColumns();
        showStatus('Configuration saved!', 'success');
      } catch (err: unknown) {
        showStatus(getRequestErrorMessage(err, 'Save failed'), 'error');
      }
    }

    async function reloadConfig() {
      if (hasChanges.value) {
        showReloadConfirm.value = true;
        return;
      }
      await _doReload();
    }

    async function _doReload() {
      showReloadConfirm.value = false;
      try {
        const resp = await axios.post(`${adminBaseUrl}/config/reload`, {}, {
          headers: getAuthHeaders(),
        });
        config.value = resp.data.config;
        ensureLlmConfig(config.value);
        originalConfig.value = JSON.stringify(config.value);
        await columnsStore.refreshColumns();
        showStatus('Configuration reloaded from disk', 'success');
      } catch (err: unknown) {
        showStatus(getRequestErrorMessage(err, 'Reload failed'), 'error');
      }
    }

    async function restartBackend() {
      if (!confirm('This will restart the backend. Continue?')) return;
      try {
        await axios.post(`${adminBaseUrl}/restart`, {}, {
          headers: getAuthHeaders(),
        });
        showStatus('Backend restart initiated...', 'info');
      } catch (err: unknown) {
        showStatus(getRequestErrorMessage(err, 'Restart request sent'), 'info');
      }
    }

    async function loadDatasets() {
      try {
        const resp = await axios.get<{ datasets: DatasetResponse[] }>(`${adminBaseUrl}/datasets`, {
          headers: getAuthHeaders(),
        });
        datasets.value = (resp.data.datasets ?? []).map((dataset) => ({
          ...dataset,
          code: dataset.code,
          full_name: dataset.full_name ?? dataset.code,
          display_name: dataset.display_name ?? dataset.full_name ?? dataset.code,
          enabled: dataset.enabled ?? true,
        }));
      } catch {
        console.error('Failed to load datasets');
      }
    }

    // ========== Profiles ==========

    async function loadProfiles() {
      try {
        const resp = await axios.get(`${adminBaseUrl}/config/profiles`, {
          headers: getAuthHeaders(),
        });
        profiles.value = resp.data.profiles || [];
      } catch {
        profiles.value = [];
      }
    }

    function openSaveProfile() {
      showProfileMenu.value = false;
      showSaveProfileModal.value = true;
      profileName.value = '';
      profileDescription.value = '';
    }

    async function saveProfile() {
      if (!profileName.value.trim()) return;
      try {
        await axios.post(
          `${adminBaseUrl}/config/save-profile`,
          { name: profileName.value.trim(), description: profileDescription.value },
          { headers: getAuthHeaders() }
        );
        showSaveProfileModal.value = false;
        showStatus(`Profile '${profileName.value}' saved`, 'success');
        loadProfiles();
      } catch (err: unknown) {
        showStatus(getRequestErrorMessage(err, 'Failed to save profile'), 'error');
      }
    }

    async function loadProfile(name: string) {
      showProfileMenu.value = false;
      if (!confirm(`Load profile '${name}'? This will replace current configuration.`)) return;
      try {
        const resp = await axios.post(
          `${adminBaseUrl}/config/load-profile`,
          { name },
          { headers: getAuthHeaders() }
        );
        config.value = resp.data.config;
        ensureLlmConfig(config.value);
        originalConfig.value = JSON.stringify(config.value);
        await columnsStore.refreshColumns();
        showStatus(`Profile '${name}' loaded`, 'success');
      } catch (err: unknown) {
        showStatus(getRequestErrorMessage(err, 'Failed to load profile'), 'error');
      }
    }

    // ========== Metadata ==========

    function onColumnsUpdate(updatedDefs: Record<string, ColumnDefinition>) {
      if (config.value) {
        config.value.column_definitions = updatedDefs;
      }
    }

    function openMetadataImport(target: 'var' | 'obs') {
      importTarget.value = target;
      showImportModal.value = true;
    }

    async function onMetadataImported() {
      await loadConfig();
      await columnsStore.refreshColumns();
      showStatus('Metadata imported successfully', 'success');
    }

    function deleteColumn(columnName: string) {
      deleteModalColumn.value = columnName;
      deleteFromH5ad.value = false;
    }

    function closeDeleteModal() {
      if (deleteRunning.value) return;
      deleteModalColumn.value = null;
      deleteFromH5ad.value = false;
    }

    async function confirmDeleteColumn() {
      if (!deleteModalColumn.value) return;
      const columnName = deleteModalColumn.value;
      deleteRunning.value = true;
      try {
        await axios.delete(
          `${adminBaseUrl}/metadata/${columnName}?persist=${deleteFromH5ad.value}`,
          { headers: getAuthHeaders() }
        );
        deleteModalColumn.value = null;
        deleteFromH5ad.value = false;
        await loadConfig();
        await columnsStore.refreshColumns();
        showStatus(`Column '${columnName}' deleted`, 'success');
      } catch (err: unknown) {
        showStatus(getRequestErrorMessage(err, 'Delete failed'), 'error');
      } finally {
        deleteRunning.value = false;
      }
    }

    // ========== Helpers ==========

    function updateTags(code: string, value: string) {
      if (!config.value) return;
      config.value.species[code].tags = value.split(',').map((t: string) => t.trim()).filter((t: string) => t);
    }

    function updateArray(field: 'default_columns' | 'hidden_columns', value: string) {
      if (!config.value) return;
      config.value.frontend_settings[field] = value.split(',').map((t: string) => t.trim()).filter((t: string) => t);
    }

    function showStatus(message: string, type: 'success' | 'error' | 'info') {
      statusMessage.value = message;
      statusType.value = type;
      setTimeout(() => { statusMessage.value = ''; }, 4000);
    }

    // ========== Init ==========

    onMounted(async () => {
      const stored = sessionStorage.getItem('admin_token');
      if (stored) {
        adminToken.value = stored;
        tokenInput.value = stored;
      }

      await checkAuth();

      if (authenticated.value) {
        loadConfig();
        loadDatasets();
        loadProfiles();
      }
    });

    // Close dropdown on outside click
    if (typeof document !== 'undefined') {
      document.addEventListener('click', (e: MouseEvent) => {
        const target = e.target as HTMLElement;
        if (!target.closest('.profile-dropdown')) {
          showProfileMenu.value = false;
        }
      });
    }

    return {
      authRequired, authenticated, adminToken, tokenInput, authError, authenticate,
      config, loading, error, statusMessage, statusType,
      activeTab, tabs, hasChanges, datasets,
      loadConfig, saveConfig, reloadConfig, restartBackend, updateTags, updateArray,
      onColumnsUpdate, openMetadataImport, onMetadataImported, deleteColumn,
      deleteModalColumn, deleteFromH5ad, deleteRunning, closeDeleteModal, confirmDeleteColumn,
      showImportModal, importTarget,
      profiles, showProfileMenu, showSaveProfileModal,
      profileName, profileDescription, openSaveProfile, saveProfile, loadProfile,
      columnsStore, showReloadConfirm, _doReload, apiBaseUrl,
      llmTestRunning, llmTestResult, testLlmConnection, REDACTED_PLACEHOLDER,
    };
  },
});
</script>

<style scoped>
.admin-panel {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  color: #1f2937;
}

/* Auth Gate */
.auth-gate {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}

.auth-card {
  background: white;
  padding: 40px;
  border-radius: 12px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
  text-align: center;
  max-width: 400px;
  width: 100%;
}

.auth-card h2 { margin: 0 0 12px 0; }

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 20px;
}

.auth-error {
  color: #dc2626;
  margin-top: 12px;
  font-size: 14px;
}

/* Header */
.admin-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e5e7eb;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-header h1 {
  margin: 0;
  font-size: 24px;
  color: #111827;
}

.version-badge {
  padding: 2px 10px;
  background: #eff6ff;
  color: #2563eb;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Buttons */
.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-primary { background: #2563eb; color: white; }
.btn-primary:hover:not(:disabled) { background: #1d4ed8; }

.btn-outline { background: white; color: #374151; border: 1px solid #d1d5db; }
.btn-outline:hover { background: #f9fafb; border-color: #9ca3af; }

.btn-warning { background: #f59e0b; color: white; }
.btn-warning:hover { background: #d97706; }

.btn-danger { background: #dc2626; color: white; }
.btn-danger:hover:not(:disabled) { background: #b91c1c; }

/* Profile Dropdown */
.profile-dropdown { position: relative; }

.dropdown-menu {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.12);
  min-width: 260px;
  z-index: 100;
  overflow: hidden;
}

.dropdown-header {
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 700;
  color: #6b7280;
  text-transform: uppercase;
  border-bottom: 1px solid #f3f4f6;
}

.dropdown-item {
  display: flex;
  flex-direction: column;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 13px;
  text-align: left;
  color: #374151;
}

.dropdown-item:hover { background: #f3f4f6; }

.dropdown-hint { font-size: 11px; color: #9ca3af; margin-top: 2px; }
.dropdown-divider { border-top: 1px solid #f3f4f6; }
.dropdown-empty { padding: 12px 14px; font-size: 12px; color: #9ca3af; text-align: center; }

/* Loading / Error */
.loading-state, .error-state { text-align: center; padding: 60px; }

.spinner {
  border: 4px solid #e5e7eb;
  border-top: 4px solid #2563eb;
  border-radius: 50%;
  width: 40px;
  height: 40px;
  animation: spin 0.8s linear infinite;
  margin: 0 auto 16px;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* Tabs */
.tabs {
  display: flex;
  gap: 2px;
  border-bottom: 2px solid #e5e7eb;
  margin-bottom: 24px;
}

.tab {
  padding: 10px 20px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  color: #6b7280;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  gap: 6px;
}

.tab:hover { color: #2563eb; background: #f8fafc; }
.tab.active { color: #2563eb; border-bottom-color: #2563eb; }
.tab-icon { font-size: 16px; }

/* Section */
.section {
  background: white;
  padding: 28px;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  border: 1px solid #f3f4f6;
}

.section h2 { margin: 0 0 16px 0; font-size: 20px; color: #111827; }
.section-header { margin-bottom: 20px; }

.info {
  padding: 12px 16px;
  background: #eff6ff;
  border-left: 4px solid #2563eb;
  border-radius: 4px;
  font-size: 13px;
  color: #1e40af;
  margin-bottom: 20px;
}

.hint { font-weight: 400; color: #9ca3af; font-size: 12px; }

/* Forms */
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.form-group { margin-bottom: 16px; }

.form-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.banner { padding: 10px 14px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
.banner-warning { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; }
.toggle-label { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-weight: 500; }
.toggle-label input { width: 18px; height: 18px; }
.test-result { margin-top: 10px; padding: 8px 12px; border-radius: 6px; font-size: 14px; display: inline-block; }
.test-result.ok { background: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0; }
.test-result.err { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.test-result code { background: rgba(0,0,0,0.06); padding: 1px 5px; border-radius: 3px; }

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  font-size: 13px;
  color: #374151;
}

.form-control {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  box-sizing: border-box;
  transition: border-color 0.2s;
}

.form-control:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-control-sm { padding: 5px 8px; font-size: 13px; }

/* Species Table */
.species-table-container {
  overflow-x: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.species-table { width: 100%; border-collapse: collapse; }
.species-table thead { background: #f9fafb; }

.species-table th {
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #6b7280;
  font-size: 12px;
  text-transform: uppercase;
  border-bottom: 2px solid #e5e7eb;
}

.species-table td {
  padding: 8px 12px;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: middle;
}

.species-table tbody tr:hover { background: #f9fafb; }
.species-table .disabled-row { opacity: 0.5; }

.species-code {
  background: #2563eb;
  color: white;
  padding: 3px 8px;
  border-radius: 4px;
  font-weight: 600;
  font-size: 12px;
}

.status-indicator { font-size: 18px; }
.status-indicator.active { color: #22c55e; }
.status-indicator.inactive { color: #d1d5db; }

.toggle-inline { display: flex; cursor: pointer; }

.toggle-inline input {
  position: relative;
  width: 40px;
  height: 20px;
  -webkit-appearance: none;
  appearance: none;
  background: #d1d5db;
  outline: none;
  border-radius: 12px;
  transition: 0.3s;
  cursor: pointer;
}

.toggle-inline input:checked { background: #22c55e; }

.toggle-inline input::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  top: 2px;
  left: 2px;
  background: white;
  transition: 0.3s;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.toggle-inline input:checked::before { left: 22px; }

/* Status Bar */
.status-bar {
  position: fixed;
  bottom: 20px;
  right: 20px;
  padding: 12px 20px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-weight: 500;
  font-size: 14px;
  z-index: 1000;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from { transform: translateX(300px); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}

.status-bar.success { background: #22c55e; color: white; }
.status-bar.error { background: #ef4444; color: white; }
.status-bar.info { background: #3b82f6; color: white; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.modal-sm {
  background: white;
  padding: 28px;
  border-radius: 12px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.modal-sm h3 { margin: 0 0 20px 0; font-size: 18px; }

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
</style>
