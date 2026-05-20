import { defineStore } from "pinia";
import { ref, computed } from "vue";
import axios from "axios";
import { API_BASE_URL } from "@/shared/Config";
import { fetchFeatures, type FeatureFlags } from "@/shared/landingApi";

export type ActionKind =
  | "deeplink"
  | "viz_update"
  | "add_filter"
  | "remove_filter"
  | "clear_filters"
  | "select_tables"
  | "set_expression_display"
  | "compute";

export interface AssistantAction {
  kind: ActionKind;
  spec: Record<string, unknown>;
  url_path?: string;
  view?: string;
  status?: "pending" | "applied" | "error";
  result?: unknown;
  error?: string;
  /** Human-readable summary of what an action applied (e.g.
   *  "compare.plotType → box, colorScale → VIRIDIS"). Filled in by the
   *  per-kind apply* handlers so the chip can show details. */
  summary?: string;
}

export interface ToolTrace {
  id: string;
  name: string;
  status: "running" | "done";
  args?: Record<string, unknown>;
  summary?: Record<string, unknown>;
}

/** Snapshot of mutable UI state captured *before* a message applied actions. */
export interface UndoSnapshot {
  filters: Record<string, unknown> | null;
  visualizations: Record<string, unknown> | null;
  selectedTableNames: string[] | null;
  route: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  actions?: AssistantAction[];
  deeplink?: { view: string; url_path: string } | null;
  error?: string;
  tools?: ToolTrace[];
  /** Latest progress hint surfaced from the backend (e.g. "model_call").
   *  Used by the panel to render a meaningful label while we wait. */
  status?: { phase: string; iteration?: number; max_iterations?: number } | null;
  /** When set, the UI shows an Undo button that restores this snapshot. */
  undo?: UndoSnapshot | null;
  /** True after the user clicks Undo — snapshot is cleared. */
  undone?: boolean;
  /** Streamed intermediate "thoughts" the model emits between tool calls,
   *  surfaced live so the user sees the reasoning trail. */
  thoughts?: string[];
}

export interface ClientContext {
  view?: string;
  route?: string;
  tables?: string[];
  selected_table_names?: string[];
  filters?: Record<string, unknown>;
  visualizations?: Record<string, unknown>;
  selection?: unknown;
  visible_genes?: string[];
  /** Lightweight digest of the visible analysis results (ORA, etc.) so
   *  the assistant can answer questions like "do you see a pattern?"
   *  about what the user is currently looking at. */
  analysis_results?: Record<string, unknown>;
}

const AUTO_EXECUTE_STORAGE_KEY = "genx.assistant.autoExecute";

function readAutoExecutePref(): boolean {
  try {
    return localStorage.getItem(AUTO_EXECUTE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export const useAssistantStore = defineStore("assistant", () => {
  const features = ref<FeatureFlags | null>(null);
  const open = ref(false);
  const streaming = ref(false);
  const messages = ref<ChatMessage[]>([]);
  const abortController = ref<AbortController | null>(null);
  // When true, the panel directly applies pending actions (filters, viz
  // updates, deeplink navigation) as soon as the model finishes streaming,
  // instead of surfacing per-action confirmation chips.
  const autoExecute = ref<boolean>(readAutoExecutePref());
  // Per-view analysis result digests (e.g. ORA results per table). Components
  // call setAnalysisContext() after their data refreshes.
  const analysisContext = ref<Record<string, unknown>>({});

  const enabled = computed(() => features.value?.assistant_enabled === true);
  const displayName = computed(() => features.value?.assistant?.display_name || "AI Assistant");

  async function loadFeatures() {
    if (features.value) return;
    try {
      features.value = await fetchFeatures();
    } catch {
      features.value = null;
    }
  }

  function reset() {
    cancel();
    messages.value = [];
  }

  function cancel() {
    if (abortController.value) {
      abortController.value.abort();
      abortController.value = null;
    }
    streaming.value = false;
  }

  async function sendMessage(text: string, clientContext?: ClientContext) {
    const clean = text.trim();
    if (!clean || streaming.value) return;
    messages.value.push({ role: "user", content: clean });
    // Push the assistant placeholder, then grab the REACTIVE reference back
    // out of the array. Mutating the raw local object directly does NOT
    // trigger Vue's array proxy, so streamed delta tokens were invisible
    // until the final `streaming.value = false` write forced a re-render —
    // which the user perceived as "no streaming, just the final answer".
    messages.value.push({ role: "assistant", content: "", actions: [] });
    const assistantMsg = messages.value[messages.value.length - 1] as ChatMessage;

    streaming.value = true;
    const controller = new AbortController();
    abortController.value = controller;

    try {
      // Build the request history. We must drop FAILED turns entirely so the
      // model never sees an orphaned user message (which it would interpret
      // as continuing the previous, errored task — that was the bug where a
      // new prompt re-ran the old MADS reasoning after a tool-loop timeout).
      // A turn is "failed" when its assistant entry has an `error` and no
      // usable content. We pair-drop the matching user message before it.
      const historyForServer: { role: string; content: string }[] = [];
      const list = messages.value;
      for (let i = 0; i < list.length; i++) {
        const m = list[i];
        if (m.role === "user") {
          const next = list[i + 1];
          const failed =
            next &&
            next.role === "assistant" &&
            !!next.error &&
            !(next.content && next.content.trim());
          if (failed) {
            // Skip both the user prompt and the failed assistant placeholder.
            i += 1;
            continue;
          }
          historyForServer.push({ role: m.role, content: m.content });
        } else if (m.role === "assistant") {
          // Only forward assistant turns that produced visible text.
          if (m.content && m.content.trim()) {
            historyForServer.push({ role: m.role, content: m.content });
          }
        } else {
          historyForServer.push({ role: m.role, content: m.content });
        }
      }

      const body: Record<string, unknown> = {
        messages: historyForServer,
        stream: true,
        include_context: true,
      };
      if (clientContext) body.client_context = clientContext;

      const resp = await fetch(`${API_BASE_URL}/api/assistant/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!resp.ok) {
        const errText = await resp.text().catch(() => resp.statusText);
        assistantMsg.error = `Request failed (${resp.status}): ${errText.slice(0, 200)}`;
        assistantMsg.content = "";
        return;
      }
      if (!resp.body) {
        assistantMsg.error = "No response body";
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split(/\n\n/);
        buffer = events.pop() || "";
        for (const ev of events) {
          const lines = ev.split(/\n/);
          const eventLine = lines.find((l) => l.startsWith("event:"));
          const dataLine = lines.find((l) => l.startsWith("data:"));
          if (!dataLine) continue;
          const evType = eventLine ? eventLine.slice(6).trim() : "";
          const payload = dataLine.slice(5).trim();
          if (!payload) continue;
          try {
            const obj = JSON.parse(payload);
            if (evType === "tool") {
              const trace: ToolTrace = {
                id: String(obj.id || ""),
                name: String(obj.name || ""),
                status: obj.status === "done" ? "done" : "running",
                args: obj.args,
                summary: obj.summary,
              };
              assistantMsg.tools = assistantMsg.tools || [];
              // Merge on id (running → done) instead of duplicating.
              const idx = assistantMsg.tools.findIndex((t) => t.id === trace.id && t.id);
              if (idx >= 0) assistantMsg.tools[idx] = { ...assistantMsg.tools[idx], ...trace };
              else assistantMsg.tools.push(trace);
            } else if (evType === "status") {
              assistantMsg.status = {
                phase: String(obj.phase || ""),
                iteration: typeof obj.iteration === "number" ? obj.iteration : undefined,
                max_iterations: typeof obj.max_iterations === "number" ? obj.max_iterations : undefined,
              };
            } else if (evType === "thought") {
              const t = String(obj.content || "").trim();
              if (t) {
                assistantMsg.thoughts = assistantMsg.thoughts || [];
                assistantMsg.thoughts.push(t);
              }
            } else if (typeof obj.delta === "string") {
              // The backend may set `replace: true` to swap the bubble's
              // content (used for retag-cleanup or to wipe pre-tool
              // "thinking" prose that turned out to be intermediate). The
              // default mode is append.
              if (obj.replace === true) {
                assistantMsg.content = obj.delta;
              } else {
                assistantMsg.content += obj.delta;
              }
            } else if (obj.error) {
              assistantMsg.error = String(obj.error);
            }
          } catch {
            /* ignore malformed frames */
          }
        }
      }

      await extractAndDispatchActions(assistantMsg, clientContext);
    } catch (e: unknown) {
      if ((e as { name?: string }).name !== "AbortError") {
        assistantMsg.error = (e as Error).message || "Network error";
      }
    } finally {
      streaming.value = false;
      abortController.value = null;
    }
  }

  async function extractAndDispatchActions(msg: ChatMessage, clientContext?: ClientContext) {
    const re = /```(action|deeplink|viz_update|add_filter|remove_filter|clear_filters|select_tables|set_expression_display|compute)\s*\n([\s\S]*?)\n```/gi;
    const blocks: Array<{ tag: string; spec: Record<string, unknown>; kind: AssistantAction["kind"] }> = [];
    let m: RegExpExecArray | null;
    while ((m = re.exec(msg.content)) !== null) {
      const tag = m[1].toLowerCase();
      let spec: Record<string, unknown>;
      try {
        spec = JSON.parse(m[2]);
      } catch {
        continue;
      }
      const kind = (tag === "action" ? String(spec.kind || "").toLowerCase() : tag) as AssistantAction["kind"];
      if (!kind) continue;
      blocks.push({ tag, spec, kind });
    }
    const actionAwareFilters = deriveFiltersForAssistantActions(clientContext?.filters, blocks);

    msg.actions = msg.actions || [];
    for (const { spec, kind } of blocks) {
      const action: AssistantAction = { kind, spec, status: "pending" };
      msg.actions.push(action);

      if (kind === "deeplink") {
        try {
          const deeplinkFilters = mergeDeeplinkFilters(actionAwareFilters, spec.filters);
          const { data } = await axios.post(`${API_BASE_URL}/api/assistant/deeplink`, {
            view: spec.view,
            tables: spec.tables || [],
            filters: deeplinkFilters,
            visualizations: spec.visualizations || {},
          });
          action.url_path = data.url_path;
          action.view = data.view;
          action.status = "applied";
          if (!msg.deeplink) msg.deeplink = { view: data.view, url_path: data.url_path };
        } catch (e) {
          action.status = "error";
          const guardMessage = formatDeeplinkGuardError(e);
          action.error = guardMessage || (e as Error).message || "deeplink failed";
          if (guardMessage && !msg.content.includes(guardMessage)) {
            msg.content = `${msg.content.trim()}\n\n${guardMessage}`;
          }
        }
      } else if (kind === "compute") {
        try {
          const payload = {
            op: spec.op,
            args: spec.args || {},
            tables: spec.tables || clientContext?.tables || [],
            filters: spec.filters || clientContext?.filters || {},
          };
          const { data } = await axios.post(`${API_BASE_URL}/api/assistant/compute`, payload);
          action.result = data;
          action.status = "applied";
        } catch (e) {
          action.status = "error";
          action.error = (e as Error).message || "compute failed";
        }
      }
      // viz_update / add_filter stay "pending" and are applied from the UI via applyAction().
    }
  }

  function deriveFiltersForAssistantActions(
    contextFilters: Record<string, unknown> | undefined,
    blocks: Array<{ kind: AssistantAction["kind"]; spec: Record<string, unknown> }>,
  ): Record<string, unknown> {
    const state = cloneFilterState(contextFilters);
    for (const block of blocks) {
      if (block.kind === "clear_filters") {
        state.filters = {};
      } else if (block.kind === "remove_filter") {
        const column = String(block.spec.column || block.spec.key || "").trim();
        if (column) delete state.filters[column];
      } else if (block.kind === "add_filter") {
        const column = String(block.spec.column || block.spec.key || "").trim();
        if (!column) continue;
        const rawSpec = block.spec as { value?: unknown; values?: unknown; match_mode?: unknown; exact?: unknown };
        state.filters[column] = {
          value: rawSpec.values !== undefined ? rawSpec.values : rawSpec.value,
          match_mode: rawSpec.match_mode === "and" ? "and" : "or",
          exact: rawSpec.exact === undefined ? true : rawSpec.exact === true,
        };
      }
    }
    return state;
  }

  function cloneFilterState(contextFilters: Record<string, unknown> | undefined): Record<string, unknown> & {
    filters: Record<string, unknown>;
    datasetIdFilters: Record<string, unknown>;
  } {
    const source = contextFilters && typeof contextFilters === "object" ? contextFilters : {};
    const nestedFilters = source.filters && typeof source.filters === "object" && !Array.isArray(source.filters)
      ? source.filters as Record<string, unknown>
      : {};
    const datasetIdFilters = source.datasetIdFilters && typeof source.datasetIdFilters === "object" && !Array.isArray(source.datasetIdFilters)
      ? source.datasetIdFilters as Record<string, unknown>
      : {};
    return {
      ...source,
      tags: Array.isArray(source.tags) ? [...source.tags] : [],
      table_names: Array.isArray(source.table_names) ? [...source.table_names] : [],
      filters: { ...nestedFilters },
      datasetIdFilters: { ...datasetIdFilters },
    };
  }

  function mergeDeeplinkFilters(
    derivedFilters: Record<string, unknown>,
    explicitFilters: unknown,
  ): Record<string, unknown> {
    const explicit = explicitFilters && typeof explicitFilters === "object" && !Array.isArray(explicitFilters)
      ? explicitFilters as Record<string, unknown>
      : {};
    const derivedNested = derivedFilters.filters && typeof derivedFilters.filters === "object" && !Array.isArray(derivedFilters.filters)
      ? derivedFilters.filters as Record<string, unknown>
      : {};
    const explicitNested = extractFilterMap(explicit);
    const derivedDataset = derivedFilters.datasetIdFilters && typeof derivedFilters.datasetIdFilters === "object" && !Array.isArray(derivedFilters.datasetIdFilters)
      ? derivedFilters.datasetIdFilters as Record<string, unknown>
      : {};
    const explicitDataset = explicit.datasetIdFilters && typeof explicit.datasetIdFilters === "object" && !Array.isArray(explicit.datasetIdFilters)
      ? explicit.datasetIdFilters as Record<string, unknown>
      : {};

    return {
      ...derivedFilters,
      ...copyFilterStateMetadata(explicit),
      tags: Array.isArray(explicit.tags) ? explicit.tags : (Array.isArray(derivedFilters.tags) ? derivedFilters.tags : []),
      table_names: Array.isArray(explicit.table_names) ? explicit.table_names : (Array.isArray(derivedFilters.table_names) ? derivedFilters.table_names : []),
      filters: { ...derivedNested, ...explicitNested },
      datasetIdFilters: { ...derivedDataset, ...explicitDataset },
    };
  }

  function extractFilterMap(rawFilters: Record<string, unknown>): Record<string, unknown> {
    if (rawFilters.filters && typeof rawFilters.filters === "object" && !Array.isArray(rawFilters.filters)) {
      return rawFilters.filters as Record<string, unknown>;
    }
    const reserved = new Set([
      "tags", "table_names", "filters", "datasetIdFilters", "idColumnName",
      "filterChainColumns", "filterChainGroups", "filterChainVersion",
    ]);
    return Object.fromEntries(
      Object.entries(rawFilters).filter(([key, value]) => {
        if (reserved.has(key)) return false;
        if (value === null || value === undefined) return false;
        if (Array.isArray(value)) return true;
        if (typeof value !== "object") return true;
        const spec = value as Record<string, unknown>;
        return "value" in spec || "values" in spec || "match_mode" in spec || "exact" in spec;
      }),
    );
  }

  function copyFilterStateMetadata(rawFilters: Record<string, unknown>): Record<string, unknown> {
    const allowed = new Set([
      "tags", "table_names", "datasetIdFilters", "idColumnName",
      "filterChainColumns", "filterChainGroups", "filterChainVersion",
    ]);
    return Object.fromEntries(Object.entries(rawFilters).filter(([key]) => allowed.has(key)));
  }

  function formatDeeplinkGuardError(error: unknown): string | null {
    if (!axios.isAxiosError(error)) return null;
    const data = error.response?.data as Record<string, unknown> | undefined;
    if (!data || !Array.isArray(data.over_limit)) return null;
    const limit = typeof data.limit === "number" ? data.limit : null;
    const overLimit = data.over_limit as Array<Record<string, unknown>>;
    const tableSummary = overLimit
      .map((item) => {
        const table = String(item.table || "dataset");
        const rows = typeof item.rows === "number" ? item.rows.toLocaleString() : String(item.rows || "too many");
        return `${table} (${rows}${limit ? `/${limit.toLocaleString()}` : ""})`;
      })
      .join(", ");
    const view = String(data.view || "analysis");
    const suggestion = typeof data.suggestion === "string"
      ? data.suggestion
      : "Please add a gene, orthogroup, TF family, GO term, tissue, or another sidebar filter to reduce the result size.";
    return `I can't open the ${view} yet because the requested data exceeds the current ${limit?.toLocaleString() || "configured"} transcript limit: ${tableSummary}. ${suggestion}`;
  }

  function setAnalysisContext(key: string, payload: unknown | null) {
    if (payload === null || payload === undefined) {
      delete analysisContext.value[key];
    } else {
      analysisContext.value[key] = payload;
    }
  }

  function clearAnalysisContext(prefix?: string) {
    if (!prefix) {
      analysisContext.value = {};
      return;
    }
    for (const k of Object.keys(analysisContext.value)) {
      if (k.startsWith(prefix)) delete analysisContext.value[k];
    }
  }

  function setAutoExecute(value: boolean) {
    autoExecute.value = value;
    try {
      localStorage.setItem(AUTO_EXECUTE_STORAGE_KEY, value ? "1" : "0");
    } catch {
      /* storage may be unavailable (private mode); state still flips in-memory. */
    }
  }

  return {
    features,
    open,
    streaming,
    messages,
    analysisContext,
    autoExecute,
    enabled,
    displayName,
    loadFeatures,
    sendMessage,
    cancel,
    reset,
    setAnalysisContext,
    clearAnalysisContext,
    setAutoExecute,
  };
});