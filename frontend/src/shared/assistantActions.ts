import type { Router, RouteLocationNormalizedLoaded } from "vue-router";

import type { AssistantAction, ChatMessage, UndoSnapshot } from "@/stores/assistant";
import type { FilterValue } from "@/stores/filters";

export type ActionStatus = "applied" | "error" | "pending";

export interface ActionAuditEntry {
  id: string;
  actionKind: AssistantAction["kind"];
  status: Exclude<ActionStatus, "pending">;
  summary?: string;
  error?: string;
  before: UndoSnapshot;
  after: UndoSnapshot;
  spec: Record<string, unknown>;
  timestamp: string;
  route: string;
}

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
  setCompareState?: (state: { expression?: string; selectedSpecies?: string[] }) => void;
}

export interface CatalogApi {
  selectedTableNames: Set<string>;
  selectAll?: (tableNames: string[]) => void;
}

export interface DispatcherDeps {
  filtersStore: FiltersApi;
  visualizationStore: VisualizationApi;
  catalogStore: CatalogApi;
  router: Router;
  route: RouteLocationNormalizedLoaded;
}

export interface DispatchResult {
  mutated: boolean;
  summary?: string;
}

type ActionHandler = (action: AssistantAction, deps: DispatcherDeps) => DispatchResult | Promise<DispatchResult>;

const AUDIT_KEY = "genx.assistant.auditLog";
const MAX_AUDIT_ENTRIES = 250;

const COLOR_SCALES = new Set([
  "VIRIDIS", "BLUES", "GREENS", "REDS", "GREYS", "ORANGES", "PURPLES",
  "TURBO", "INFERNO", "MAGMA", "PLASMA", "CIVIDIS", "WARM", "COOL",
  "CUBEHELIXDEFAULT", "BUGN", "BUPU", "GNBU", "ORRD", "PUBUGN", "PUBU",
  "PURD", "RDPU", "YLGNBU", "YLGN", "YLORBR", "YLORRD",
]);

const EXPRESSION_OPTIONS: Record<string, { layer: string | null; transform: "raw" | "log2" | "zscore" }> = {
  tpm: { layer: "tpm", transform: "raw" },
  tmm: { layer: "tmm", transform: "raw" },
  getmm: { layer: "getmm", transform: "raw" },
  log2: { layer: "tpm", transform: "log2" },
  zscore: { layer: "getmm", transform: "zscore" },
  "zscore-tpm": { layer: "tpm", transform: "zscore" },
  raw: { layer: "X", transform: "raw" },
};

const SIGNIFICANCE_THRESHOLDS = new Set(["0.001", "0.01", "0.05", "0.1"]);
const CLUSTER_METHODS = new Set(["average", "complete", "ward"]);
const CLUSTER_DISTANCES = new Set(["correlation", "euclidean"]);

const ALLOWED_PATCH_PATHS: Record<string, (value: unknown) => unknown> = {
  rowLabel: booleanValue,
  colLabel: booleanValue,
  legend: booleanValue,
  colorScale: enumValue(COLOR_SCALES, "colorScale"),
  rowSideColors: stringArrayValue("rowSideColors"),
  colSideColors: stringArrayValue("colSideColors"),
  tooltipFields: nullableStringArrayValue("tooltipFields"),
  showSequencesInTooltip: booleanValue,
  sequencePreviewLength: integerRangeValue("sequencePreviewLength", 20, 1000),
  "rowOrder.name": stringValue("rowOrder.name"),
  "rowOrder.order": enumValue(new Set(["asc", "desc"]), "rowOrder.order"),
  "colOrder.name": stringValue("colOrder.name"),
  "colOrder.order": enumValue(new Set(["asc", "desc"]), "colOrder.order"),
  "clustering.clusterRows": booleanValue,
  "clustering.clusterCols": booleanValue,
  "clustering.method": enumValue(CLUSTER_METHODS, "clustering.method"),
  "clustering.distance": enumValue(CLUSTER_DISTANCES, "clustering.distance"),
  "compare.plotType": enumValue(new Set(["line", "box", "violin"]), "compare.plotType"),
  "compare.plotHeight": integerRangeValue("compare.plotHeight", 200, 1200),
  "compare.selectedOrthogroup": stringValue("compare.selectedOrthogroup"),
  "compare.selectedSpecies": stringArrayValue("compare.selectedSpecies"),
  "compare.showAllTranscripts": booleanValue,
  "phyloTree.selectedOrthogroup": stringValue("phyloTree.selectedOrthogroup"),
  "phyloTree.collapsedNodes": stringArrayValue("phyloTree.collapsedNodes"),
  "phyloTree.branchLengthMode": enumValue(new Set(["cladogram", "phylogram"]), "phyloTree.branchLengthMode"),
  oraColumnName: stringValue("oraColumnName"),
  significance: enumValue(SIGNIFICANCE_THRESHOLDS, "significance"),
  oraTopN: integerRangeValue("oraTopN", 1, 500),
  oraMinCount: integerRangeValue("oraMinCount", 1, 50),
  oraGoDepthFilter: stringValue("oraGoDepthFilter"),
  oraTooltipFields: stringArrayValue("oraTooltipFields"),
  "oraOrder.name": enumValue(new Set(["p_value", "q_value", "fold_enrichment", "subset_count", "combined_score"]), "oraOrder.name"),
  "oraOrder.order": enumValue(new Set(["asc", "desc"]), "oraOrder.order"),
};

export class ActionRegistry {
  private handlers = new Map<AssistantAction["kind"], ActionHandler>();

  register(kind: AssistantAction["kind"], handler: ActionHandler): this {
    this.handlers.set(kind, handler);
    return this;
  }

  async execute(action: AssistantAction, deps: DispatcherDeps): Promise<DispatchResult> {
    const handler = this.handlers.get(action.kind);
    if (!handler) {
      throw new Error(`unsupported action kind: ${action.kind}`);
    }
    return handler(action, deps);
  }
}

export function createAssistantActionDispatcher(deps: DispatcherDeps) {
  const registry = new ActionRegistry()
    .register("viz_update", applyVizUpdate)
    .register("add_filter", applyAddFilter)
    .register("remove_filter", applyRemoveFilter)
    .register("clear_filters", applyClearFilters)
    .register("select_tables", applySelectTables)
    .register("set_expression_display", applySetExpressionDisplay)
    .register("deeplink", applyDeeplink)
    .register("compute", () => ({ mutated: false }));

  async function dispatch(action: AssistantAction): Promise<boolean> {
    const before = snapshotState(deps);
    try {
      const result = await registry.execute(action, deps);
      if (action.status !== "error") {
        action.status = "applied";
      }
      if (result.summary) action.summary = result.summary;
      writeAudit(action, before, snapshotState(deps), deps.route.fullPath);
      return result.mutated && action.status === "applied";
    } catch (error) {
      action.status = "error";
      action.error = error instanceof Error ? error.message : "action failed";
      writeAudit(action, before, snapshotState(deps), deps.route.fullPath);
      return false;
    }
  }

  async function autoApplyActions(msg: ChatMessage): Promise<boolean> {
    let mutated = false;
    for (const action of msg.actions || []) {
      if (action.kind !== "deeplink" && action.status && action.status !== "pending") continue;
      mutated = (await dispatch(action)) || mutated;
    }
    return mutated;
  }

  return { dispatch, autoApplyActions };
}

export function snapshotState(deps: DispatcherDeps): UndoSnapshot {
  let filters: Record<string, unknown> | null = null;
  let visualizations: Record<string, unknown> | null = null;
  try { filters = deps.filtersStore.toObject ? deps.filtersStore.toObject() : null; } catch { /* empty */ }
  try { visualizations = deps.visualizationStore.toObject ? deps.visualizationStore.toObject() : null; } catch { /* empty */ }
  return {
    filters,
    visualizations,
    selectedTableNames: Array.from(deps.catalogStore.selectedTableNames || []),
    route: deps.route.fullPath,
  };
}

export function restoreSnapshot(msg: ChatMessage, deps: DispatcherDeps) {
  const snap = msg.undo;
  if (!snap) return;
  try {
    if (snap.filters) deps.filtersStore.replaceState?.(snap.filters);
  } catch { /* empty */ }
  try {
    if (snap.visualizations) deps.visualizationStore.replaceState?.(snap.visualizations);
  } catch { /* empty */ }
  try {
    deps.catalogStore.selectAll?.(snap.selectedTableNames || []);
  } catch { /* empty */ }
  if (snap.route && snap.route !== deps.route.fullPath) {
    deps.router.replace(snap.route).catch(() => { /* empty */ });
  }
  msg.undone = true;
  msg.undo = null;
}

export function readAssistantAuditLog(): ActionAuditEntry[] {
  try {
    const raw = localStorage.getItem(AUDIT_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeAudit(action: AssistantAction, before: UndoSnapshot, after: UndoSnapshot, route: string) {
  const entry: ActionAuditEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`,
    actionKind: action.kind,
    status: action.status === "error" ? "error" : "applied",
    summary: action.summary,
    error: action.error,
    before,
    after,
    spec: action.spec,
    timestamp: new Date().toISOString(),
    route,
  };
  try {
    const items = [entry, ...readAssistantAuditLog()].slice(0, MAX_AUDIT_ENTRIES);
    localStorage.setItem(AUDIT_KEY, JSON.stringify(items));
  } catch {
    /* local audit is best-effort; action execution must not depend on storage. */
  }
}

function applyVizUpdate(action: AssistantAction, deps: DispatcherDeps): DispatchResult {
  const patch = (action.spec.patch || action.spec) as Record<string, unknown>;
  const entries = normalizePatchEntries(patch);
  const validated = entries.map(({ path, value }) => ({
    path,
    value: validatePatchValue(path.join("."), value),
  }));
  if (validated.length === 0) throw new Error("no valid visualization patch keys");

  const state = deps.visualizationStore.$state;
  const applied: Array<{ path: string; value: unknown }> = [];
  deps.visualizationStore.$patch((currentState: unknown) => {
    const root = currentState as Record<string, unknown>;
    for (const { path, value } of validated) {
      if (!(path[0] in state)) continue;
      let cursor: Record<string, unknown> | null = root;
      for (let index = 0; index < path.length - 1; index++) {
        const next = cursor[path[index]];
        if (!next || typeof next !== "object" || Array.isArray(next)) {
          cursor = null;
          break;
        }
        cursor = next as Record<string, unknown>;
      }
      if (!cursor) continue;
      cursor[path[path.length - 1]] = value;
      applied.push({ path: path.join("."), value });
    }
  });

  if (applied.length === 0) throw new Error("no patch keys matched the visualization store");
  return {
    mutated: true,
    summary: applied.map(({ path, value }) => `${path} -> ${formatValue(value)}`).join(", "),
  };
}

function applyAddFilter(action: AssistantAction, deps: DispatcherDeps): DispatchResult {
  const spec = action.spec;
  const column = nonEmptyString(spec.column || spec.key, "column");
  const rawSpec = spec as { match_mode?: unknown; exact?: unknown };
  const matchMode = rawSpec.match_mode === "and" || rawSpec.match_mode === "or" ? rawSpec.match_mode : "or";
  const exact = rawSpec.exact === undefined ? true : booleanValue(rawSpec.exact);
  deps.filtersStore.setFilter(column, {
    value: normalizeFilterValue(spec.value ?? (spec as { values?: unknown }).values),
    match_mode: matchMode,
    exact,
  });
  return { mutated: true, summary: `${column}=${formatValue(spec.value)}` };
}

function applyRemoveFilter(action: AssistantAction, deps: DispatcherDeps): DispatchResult {
  const column = nonEmptyString(action.spec.column || action.spec.key, "column");
  deps.filtersStore.removeFilter(column);
  return { mutated: true, summary: column };
}

function applyClearFilters(_action: AssistantAction, deps: DispatcherDeps): DispatchResult {
  deps.filtersStore.clearFilters();
  return { mutated: true, summary: "all filters" };
}

async function applySelectTables(action: AssistantAction, deps: DispatcherDeps): Promise<DispatchResult> {
  const tables = action.spec.tables;
  if (!Array.isArray(tables)) throw new Error("spec.tables must be an array");
  const values = tables.map((value) => nonEmptyString(value, "table"));
  deps.catalogStore.selectAll?.(values);
  const activeAnalysisRoute = activeDatasetRoutePrefix(deps.route.path);

  if (activeAnalysisRoute && activeAnalysisRoute !== "p") {
    if (activeAnalysisRoute === "c") {
      deps.visualizationStore.setCompareState?.({ selectedSpecies: values });
    }
    const query = { ...deps.route.query };
    if (activeAnalysisRoute === "c") {
      delete query.tables;
    }
    await deps.router.replace({
      name: deps.route.name ?? undefined,
      params: {
        ...deps.route.params,
        table_names: values.join(","),
      },
      query,
    }).catch(() => { /* ignore nav rejection */ });
  }

  return { mutated: true, summary: values.join(", ") };
}

function applySetExpressionDisplay(action: AssistantAction, deps: DispatcherDeps): DispatchResult {
  const optionId = nonEmptyString(action.spec.optionId || "raw", "optionId");
  const option = EXPRESSION_OPTIONS[optionId];
  if (!option) throw new Error(`unsupported expression option: ${optionId}`);
  const layer = action.spec.layer === undefined ? option.layer : nullableStringValue(action.spec.layer, "layer");
  const transform = action.spec.transform === undefined
    ? option.transform
    : enumValue(new Set(["raw", "log2", "zscore"]), "transform")(action.spec.transform) as "raw" | "log2" | "zscore";
  if (!deps.visualizationStore.setExpressionDisplay) throw new Error("store has no setExpressionDisplay()");
  deps.visualizationStore.setExpressionDisplay(optionId, layer, transform);
  if (deps.route.path.startsWith("/c/") && deps.visualizationStore.setCompareState) {
    deps.visualizationStore.setCompareState({ expression: optionId });
  }
  return { mutated: true, summary: optionId };
}

function activeDatasetRoutePrefix(path: string): "h" | "o" | "c" | "p" | null {
  const match = path.match(/^\/(h|o|c|p)(?:\/|$)/);
  return match ? match[1] as "h" | "o" | "c" | "p" : null;
}

function applyDeeplink(action: AssistantAction, deps: DispatcherDeps): DispatchResult {
  if (!action.url_path || action.url_path === deps.route.fullPath) return { mutated: false };
  deps.router.push(action.url_path).catch(() => { /* ignore nav rejection */ });
  return { mutated: true, summary: action.url_path };
}

function normalizePatchEntries(patch: Record<string, unknown>) {
  const entries: Array<{ path: string[]; value: unknown }> = [];
  function walk(prefix: string[], value: unknown) {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      if (prefix.length > 0) entries.push({ path: prefix, value });
      return;
    }
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      if (prefix.length === 0 && (key === "kind" || key === "patch")) continue;
      const nextPath = key.includes(".") ? [...prefix, ...key.split(".")] : [...prefix, key];
      if (child !== null && typeof child === "object" && !Array.isArray(child)) walk(nextPath, child);
      else entries.push({ path: nextPath, value: child });
    }
  }
  walk([], patch);
  return entries;
}

function validatePatchValue(path: string, value: unknown): unknown {
  const validator = ALLOWED_PATCH_PATHS[path];
  if (!validator) throw new Error(`unsupported visualization setting: ${path}`);
  return validator(value);
}

function normalizeFilterValue(raw: unknown): string {
  if (raw === null || raw === undefined) return "";
  const parts = Array.isArray(raw)
    ? raw.map((value) => String(value).trim())
    : String(raw).split(/[,;\n\r|]+/).map((value) => value.trim());
  const seen = new Set<string>();
  return parts.filter((value) => {
    if (!value || seen.has(value)) return false;
    seen.add(value);
    return true;
  }).join("|");
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return String(value);
  if (Array.isArray(value)) return `[${value.map(formatValue).join(", ")}]`;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function nonEmptyString(value: unknown, field: string): string {
  const text = String(value ?? "").trim();
  if (!text) throw new Error(`missing ${field}`);
  return text;
}

function stringValue(field: string) {
  return (value: unknown) => nonEmptyString(value, field);
}

function nullableStringValue(value: unknown, field: string): string | null {
  if (value === null) return null;
  return nonEmptyString(value, field);
}

function stringArrayValue(field: string) {
  return (value: unknown): string[] => {
    if (!Array.isArray(value)) throw new Error(`${field} must be an array`);
    return value.map((item) => nonEmptyString(item, field));
  };
}

function nullableStringArrayValue(field: string) {
  return (value: unknown): string[] | null => {
    if (value === null) return null;
    return stringArrayValue(field)(value);
  };
}

function booleanValue(value: unknown): boolean {
  if (typeof value !== "boolean") throw new Error("expected boolean");
  return value;
}

function integerRangeValue(field: string, min: number, max: number) {
  return (value: unknown): number => {
    if (!Number.isInteger(value)) throw new Error(`${field} must be an integer`);
    const numberValue = Number(value);
    if (numberValue < min || numberValue > max) throw new Error(`${field} must be between ${min} and ${max}`);
    return numberValue;
  };
}

function enumValue(options: Set<string>, field: string) {
  return (value: unknown): string => {
    const text = nonEmptyString(value, field);
    if (!options.has(text)) throw new Error(`${field} must be one of: ${Array.from(options).join(", ")}`);
    return text;
  };
}
