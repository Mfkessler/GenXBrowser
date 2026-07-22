import type { RouteLocationNormalizedLoaded, Router } from "vue-router";

import type { AssistantAction, ChatMessage, UndoSnapshot } from "@/stores/assistant";
import type { FilterValue } from "@/stores/filters";
import { getExpressionOption } from "@/shared/ExpressionDisplay";

export interface FiltersApi {
  toObject?: () => Record<string, unknown>;
  replaceState?: (state: Record<string, unknown>) => void;
  setFilter: (key: string, filter: FilterValue) => void;
  removeFilter: (key: string) => void;
  clearFilters: () => void;
}

export interface VisualizationApi {
  $state: Record<string, unknown>;
  $patch: (mutator: (state: unknown) => void) => void;
  toObject?: () => Record<string, unknown>;
  replaceState?: (state: Record<string, unknown>) => void;
  setExpressionDisplay?: (id: string, layer: string | null, transform: "raw" | "log2" | "zscore") => void;
}

export interface ColumnsApi {
  rowColumns?: ColumnOption[];
  colColumns?: ColumnOption[];
  filterableColColumns?: ColumnOption[];
  orderableColColumns?: ColumnOption[];
  sampleMetadata?: Array<Record<string, unknown>>;
}

interface ColumnOption {
  column_name: string;
  display_name?: string;
}

export interface CatalogApi {
  selectedTableNames: Set<string>;
  selectAll?: (tableNames: string[]) => void;
}

export interface DispatcherDeps {
  filtersStore: FiltersApi;
  visualizationStore: VisualizationApi;
  columnsStore?: ColumnsApi;
  catalogStore: CatalogApi;
  router: Router;
  route: RouteLocationNormalizedLoaded;
  idColumn?: string;
  hiddenColumns?: string[];
}

interface AuditEntry {
  status: "applied" | "error";
  before: UndoSnapshot;
  after: UndoSnapshot;
  spec: Record<string, unknown>;
  timestamp: string;
  route: string;
  error?: string;
}

const AUDIT_KEY = "genx.assistant.auditLog";
const PHYLO_COMMANDS = new Set(["reset_view", "expand_all", "collapse_all", "collapse_to_species"]);
const TRIGGERS = new Set([
  "export_png", "export_pdf", "export_svg",
  "export_tsv", "export_csv", "export_xlsx", "export_json",
  "open_data_manager", "open_export_modal",
]);
const PATCH_PATHS = new Set([
  "rowLabel", "colLabel", "legend", "colorScale", "rowSideColors", "colSideColors",
  "tooltipFields", "showSequencesInTooltip", "sequencePreviewLength", "rowOrder",
  "rowOrder.name", "rowOrder.order", "colOrder", "colOrder.name", "colOrder.order",
  "customColOrder", "customColOrder.enabled", "customColOrder.mode",
  "customColOrder.metadataColumn", "customColOrder.metadataValues", "customColOrder.sampleNames",
  "clustering", "clustering.clusterRows", "clustering.clusterCols", "clustering.method",
  "clustering.distance", "compare", "compare.plotType", "compare.plotHeight",
  "compare.expression", "compare.selectedOrthogroup", "compare.selectedSpecies", "compare.showAllTranscripts",
  "compare.groupingColumn", "phyloTree", "phyloTree.selectedOrthogroup",
  "phyloTree.collapsedNodes", "phyloTree.branchLengthMode", "phyloTree.groupingColumn",
  "oraRowSideColor", "oraColumnName", "significance", "oraTopN", "oraMinCount",
  "oraGoDepthFilter", "oraTooltipFields", "oraOrder", "oraOrder.name", "oraOrder.order",
  "expressionDisplay",
]);

export function createAssistantActionDispatcher(deps: DispatcherDeps) {
  async function dispatch(action: AssistantAction): Promise<boolean> {
    const before = snapshotState(deps);
    try {
      const summary = await applyStateToken(action.spec, deps);
      action.status = "applied";
      action.summary = summary;
      writeAudit({ status: "applied", before, after: snapshotState(deps), spec: action.spec, timestamp: new Date().toISOString(), route: deps.route.fullPath });
      return true;
    } catch (error) {
      action.status = "error";
      action.error = error instanceof Error ? error.message : "state update failed";
      writeAudit({ status: "error", error: action.error, before, after: snapshotState(deps), spec: action.spec, timestamp: new Date().toISOString(), route: deps.route.fullPath });
      return false;
    }
  }

  async function autoApplyActions(msg: ChatMessage): Promise<boolean> {
    const action = (msg.actions || []).find((item) => item.status === "pending");
    return action ? dispatch(action) : false;
  }

  return { dispatch, autoApplyActions };
}

async function applyStateToken(token: Record<string, unknown>, deps: DispatcherDeps): Promise<string> {
  const filters = objectValue(token.filters, "state_token.filters");
  const patches = objectValue(token.viz_patches, "state_token.viz_patches");
  const tables = arrayValue(token.tables, "state_token.tables");
  const urlPath = typeof token.url_path === "string" ? token.url_path : "";
  const filtersChanged = !matchesCurrentState(filters, deps.filtersStore.toObject?.());
  const tablesChanged = !sameStringSet(tables, deps.catalogStore.selectedTableNames);
  if (filtersChanged) deps.filtersStore.replaceState?.(filters);
  if (tablesChanged) deps.catalogStore.selectAll?.(tables);

  if (urlPath && urlPath !== deps.route.fullPath) {
    await deps.router.push(urlPath).catch(() => undefined);
    await nextFrame();
  } else if (!urlPath && filtersChanged) {
    const query = { ...deps.route.query };
    const activeFilters = filters.filters && typeof filters.filters === "object" && !Array.isArray(filters.filters)
      ? filters.filters as Record<string, unknown>
      : {};
    if (Object.keys(activeFilters).length > 0) query.filters = JSON.stringify(activeFilters);
    else delete query.filters;
    await deps.router.replace({ query }).catch(() => undefined);
    await nextFrame();
  }
  applyVisualizationPatches(patches, deps);

  const triggers = Array.isArray(token.trigger_actions) ? token.trigger_actions.map(String) : [];
  for (const trigger of triggers) {
    if (PHYLO_COMMANDS.has(trigger)) {
      window.dispatchEvent(new CustomEvent("genx:phylo-command", { detail: { command: trigger } }));
    } else if (TRIGGERS.has(trigger)) {
      window.dispatchEvent(new CustomEvent("genx:assistant-trigger", { detail: { action: trigger } }));
    } else {
      throw new Error(`unsupported state-token trigger: ${trigger}`);
    }
  }
  return triggers.length ? `state updated; ${triggers.join(", ")}` : "state updated";
}

function matchesCurrentState(expected: Record<string, unknown>, current: Record<string, unknown> | undefined): boolean {
  if (!current) return false;
  return Object.entries(expected).every(([key, value]) => structurallyEqual(value, current[key]));
}

function structurallyEqual(left: unknown, right: unknown): boolean {
  if (Object.is(left, right)) return true;
  if (Array.isArray(left) || Array.isArray(right)) {
    return Array.isArray(left) && Array.isArray(right)
      && left.length === right.length
      && left.every((value, index) => structurallyEqual(value, right[index]));
  }
  if (!left || !right || typeof left !== "object" || typeof right !== "object") return false;
  const leftRecord = left as Record<string, unknown>;
  const rightRecord = right as Record<string, unknown>;
  const keys = Object.keys(leftRecord);
  return keys.length === Object.keys(rightRecord).length
    && keys.every((key) => Object.prototype.hasOwnProperty.call(rightRecord, key)
      && structurallyEqual(leftRecord[key], rightRecord[key]));
}

function sameStringSet(values: string[], selected: Set<string>): boolean {
  return values.length === selected.size && values.every((value) => selected.has(value));
}

function applyVisualizationPatches(patches: Record<string, unknown>, deps: DispatcherDeps) {
  if (Object.keys(patches).length === 0) return;
  const expression = patches.expressionDisplay;
  if (typeof expression === "string") {
    const option = getExpressionOption(expression);
    if (!option) throw new Error(`unsupported expressionDisplay: ${expression}`);
    deps.visualizationStore.setExpressionDisplay?.(expression, option.layer, option.transform);
  }
  deps.visualizationStore.$patch((rawState) => {
    const state = rawState as Record<string, unknown>;
    for (const [path, value] of Object.entries(patches)) {
      if (path === "expressionDisplay") continue;
      applyPatchPath(state, path, validatePatch(path, value, deps));
    }
  });
}

function validatePatch(path: string, value: unknown, deps: DispatcherDeps): unknown {
  if (!PATCH_PATHS.has(path)) throw new Error(`unsupported visualization path: ${path}`);
  if (path === "rowSideColors" || path === "tooltipFields") return validateColumns(value, deps.columnsStore?.rowColumns, path, deps);
  if (path === "colSideColors") return validateColumns(value, deps.columnsStore?.colColumns, path, deps);
  if (path === "compare.groupingColumn" || path === "phyloTree.groupingColumn") {
    return validateColumn(value, deps.columnsStore?.filterableColColumns, path);
  }
  if (path === "colOrder.name") return validateColumn(value, deps.columnsStore?.orderableColColumns, path);
  if (path === "customColOrder.metadataColumn") return validateColumn(value, deps.columnsStore?.colColumns, path);
  return value;
}

function validateColumn(value: unknown, columns: ColumnOption[] | undefined, path: string): string {
  if (typeof value !== "string") throw new Error(`${path} must be a string`);
  const names = new Map<string, string>();
  for (const column of columns || []) {
    names.set(column.column_name.toLowerCase(), column.column_name);
    if (column.display_name) names.set(column.display_name.toLowerCase(), column.column_name);
  }
  const resolved = names.get(value.toLowerCase());
  if (!resolved) throw new Error(`${path} contains unavailable column: ${value}`);
  return resolved;
}

function validateColumns(value: unknown, columns: ColumnOption[] | undefined, path: string, deps: DispatcherDeps): string[] {
  if (!Array.isArray(value)) throw new Error(`${path} must be an array`);
  const eligible = (columns || [])
    .map((column) => column.column_name)
    .filter((column) => column !== deps.idColumn && !(deps.hiddenColumns || []).includes(column));
  if (value.length === 1 && value[0] === "*") return eligible;
  const names = new Map<string, string>();
  for (const column of columns || []) {
    names.set(column.column_name.toLowerCase(), column.column_name);
    if (column.display_name) names.set(column.display_name.toLowerCase(), column.column_name);
  }
  return value.map((raw) => {
    const resolved = names.get(String(raw).toLowerCase());
    if (!resolved || !eligible.includes(resolved)) throw new Error(`${path} contains unavailable column: ${raw}`);
    return resolved;
  });
}

function applyPatchPath(state: Record<string, unknown>, path: string, value: unknown) {
  const parts = path.split(".");
  let cursor = state;
  for (const part of parts.slice(0, -1)) {
    const next = cursor[part];
    if (!next || typeof next !== "object" || Array.isArray(next)) cursor[part] = {};
    cursor = cursor[part] as Record<string, unknown>;
  }
  cursor[parts.at(-1)!] = value;
}

function objectValue(value: unknown, field: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${field} must be an object`);
  return value as Record<string, unknown>;
}

function arrayValue(value: unknown, field: string): string[] {
  if (!Array.isArray(value)) throw new Error(`${field} must be an array`);
  return value.map(String);
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
}

export function snapshotState(deps: DispatcherDeps): UndoSnapshot {
  let filters: Record<string, unknown> | null = null;
  let visualizations: Record<string, unknown> | null = null;
  try { filters = deps.filtersStore.toObject?.() || null; } catch { /* noop */ }
  try { visualizations = deps.visualizationStore.toObject?.() || null; } catch { /* noop */ }
  return { filters, visualizations, selectedTableNames: [...deps.catalogStore.selectedTableNames], route: deps.route.fullPath };
}

export function restoreSnapshot(msg: ChatMessage, deps: DispatcherDeps) {
  const snapshot = msg.undo;
  if (!snapshot) return;
  if (snapshot.filters) deps.filtersStore.replaceState?.(snapshot.filters);
  if (snapshot.visualizations) deps.visualizationStore.replaceState?.(snapshot.visualizations);
  deps.catalogStore.selectAll?.(snapshot.selectedTableNames || []);
  if (snapshot.route && snapshot.route !== deps.route.fullPath) void deps.router.push(snapshot.route);
  msg.undone = true;
  msg.undo = null;
}

export function readAssistantAuditLog(): AuditEntry[] {
  try { return JSON.parse(localStorage.getItem(AUDIT_KEY) || "[]") as AuditEntry[]; } catch { return []; }
}

function writeAudit(entry: AuditEntry) {
  try { localStorage.setItem(AUDIT_KEY, JSON.stringify([...readAssistantAuditLog(), entry].slice(-250))); } catch { /* noop */ }
}