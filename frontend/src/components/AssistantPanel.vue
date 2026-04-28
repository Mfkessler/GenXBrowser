<template>
  <Transition name="assistant-slide">
    <aside
      v-if="store.open"
      class="fixed top-0 right-0 h-full w-full sm:w-[440px] bg-white border-l border-gray-200 shadow-2xl z-50 flex flex-col"
      role="dialog"
      aria-label="AI Assistant"
    >
      <header class="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-blue-100/40">
        <div class="flex items-center gap-2 min-w-0">
          <AiSparkleIcon class="w-6 h-6 text-blue-600 shrink-0" />
          <div class="min-w-0">
            <div class="text-xs text-gray-500">GenXBrowser</div>
            <h2 class="font-semibold text-gray-800 truncate">{{ store.displayName }}</h2>
          </div>
        </div>
        <div class="flex gap-1">
          <label
            class="flex items-center gap-1.5 px-2 py-1 text-[11px] text-gray-700 hover:bg-gray-100 rounded cursor-pointer select-none"
            v-tooltip="autoExecuteTooltip"
          >
            <input
              type="checkbox"
              class="w-3 h-3 cursor-pointer accent-blue-600"
              :checked="store.autoExecute"
              @change="onToggleAutoExecute(($event.target as HTMLInputElement).checked)"
            />
            <span class="font-medium">Auto-execute</span>
          </label>
          <button
            class="px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 rounded cursor-pointer"
            @click="store.reset()"
            v-tooltip="'Clear conversation'"
          >Clear</button>
          <button
            class="p-1 text-gray-600 hover:bg-gray-100 rounded cursor-pointer"
            aria-label="Close"
            @click="store.open = false"
          >
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </header>

      <div ref="scrollEl" class="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
        <div v-if="store.messages.length === 0" class="text-sm text-gray-600 space-y-3">
          <p>
            Ask about your loaded data. The assistant sees which view, filters and visualizations
            you currently have open and can propose changes, compute summaries or open deep links.
          </p>
          <div class="space-y-2">
            <p class="font-semibold text-gray-700">Try:</p>
            <button
              v-for="p in suggestedPrompts"
              :key="p"
              class="block w-full text-left text-xs bg-white border border-gray-200 hover:border-primary-400 hover:bg-primary-50 rounded-lg px-3 py-2 cursor-pointer"
              @click="send(p)"
            >{{ p }}</button>
          </div>
        </div>

        <template v-for="(msg, idx) in store.messages" :key="idx">
          <!-- User bubble: visible, right-aligned -->
          <div
            v-if="msg.role === 'user'"
            class="max-w-[90%] ml-auto bg-primary-100 border border-primary-500 text-gray-900 rounded-2xl rounded-br-sm px-3 py-2 text-sm whitespace-pre-wrap break-words shadow-sm"
          >{{ msg.content }}</div>

          <!-- Assistant bubble: Markdown, left-aligned, with action chips -->
          <div
            v-else
            class="max-w-[95%] mr-auto bg-white border border-gray-200 text-gray-800 rounded-2xl rounded-bl-sm px-3 py-2 text-sm shadow-sm"
          >
            <div v-if="msg.error" class="text-red-600 text-xs">{{ msg.error }}</div>
            <!-- Thinking trail: streamed reasoning between tool calls.
                 Always rendered above the response so the user sees what the
                 model is reasoning about (collapsible after the answer arrives). -->
            <details
              v-if="msg.thoughts && msg.thoughts.length"
              class="mb-2 text-[11px] text-gray-500 border-l-2 border-blue-200 bg-blue-50/40 pl-2 py-1 rounded-r"
              :open="store.streaming && idx === store.messages.length - 1"
            >
              <summary class="cursor-pointer select-none text-gray-600 italic">
                <span class="font-semibold">Thinking</span>
                <span class="text-gray-400"> ({{ msg.thoughts.length }} step{{ msg.thoughts.length === 1 ? '' : 's' }})</span>
              </summary>
              <div class="mt-1 space-y-1 whitespace-pre-wrap break-words">
                <div v-for="(t, ti) in msg.thoughts" :key="ti" class="text-gray-600">{{ t }}</div>
              </div>
            </details>
            <div
              v-else-if="stripActionBlocks(msg.content)"
              class="assistant-markdown text-sm"
              v-html="renderMarkdown(stripActionBlocks(msg.content))"
            ></div>
            <!-- Streaming placeholder: surface what the assistant is doing
                 instead of just an opaque ellipsis so the user sees progress. -->
            <div
              v-else-if="store.streaming && idx === store.messages.length - 1"
              class="text-xs text-gray-500 italic flex items-center gap-2 min-h-[1.5rem]"
            >
              <span class="inline-flex items-center gap-1.5 shrink-0">
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse"></span>
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" style="animation-delay: 150ms"></span>
                <span class="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" style="animation-delay: 300ms"></span>
              </span>
              <span class="min-w-0 break-words">{{ thinkingLabel(msg) }}</span>
            </div>

            <!-- Tool trace (collapsible) -->
            <details
              v-if="msg.tools && msg.tools.length"
              class="mt-2 text-[11px] text-gray-600 border border-gray-100 rounded bg-gray-50"
            >
              <summary class="cursor-pointer px-2 py-1 select-none">
                <span class="font-semibold">Tools used</span>
                <span class="text-gray-400">({{ msg.tools.length }})</span>
              </summary>
              <ul class="px-3 py-1 space-y-0.5">
                <li v-for="(t, ti) in msg.tools" :key="ti" class="flex items-center gap-2">
                  <span
                    :class="[
                      'inline-block w-1.5 h-1.5 rounded-full shrink-0',
                      t.status === 'done' ? 'bg-primary-500' : 'bg-accent1-400 animate-pulse',
                    ]"
                  ></span>
                  <span class="font-mono">{{ t.name }}</span>
                  <span v-if="t.args" class="text-gray-400 truncate">{{ JSON.stringify(t.args).slice(0, 80) }}</span>
                </li>
              </ul>
            </details>

            <!-- Action chips -->
            <div v-if="msg.actions && msg.actions.length" class="mt-3 flex flex-wrap gap-2">
              <template v-for="(action, ai) in msg.actions" :key="ai">
                <button
                  v-if="action.kind === 'deeplink' && action.status === 'applied' && action.url_path"
                  class="inline-flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="openDeeplink(action.url_path!)"
                >
                  <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5-5 5M6 12h12" />
                  </svg>
                  {{ action.url_path === route.fullPath ? '✓' : '↗' }} Open {{ action.view || "view" }}
                </button>

                <button
                  v-else-if="action.kind === 'viz_update' && action.status !== 'applied'"
                  class="inline-flex items-center gap-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="applyVizUpdate(action)"
                >
                  <AiSparkleIcon class="w-3.5 h-3.5" />
                  Apply view update
                </button>
                <span
                  v-else-if="action.kind === 'viz_update' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-100 text-primary-800 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ View updated</span>

                <button
                  v-else-if="action.kind === 'add_filter' && action.status !== 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-700 hover:bg-primary-900 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="applyAddFilter(action)"
                >
                  + Add filter{{ action.spec.column ? `: ${String(action.spec.column)}` : '' }}
                </button>
                <span
                  v-else-if="action.kind === 'add_filter' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-100 text-primary-900 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ Filter added</span>

                <button
                  v-else-if="action.kind === 'remove_filter' && action.status !== 'applied'"
                  class="inline-flex items-center gap-1 bg-accent1-500 hover:bg-accent1-700 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="applyRemoveFilter(action)"
                >
                  − Remove filter{{ action.spec.column ? `: ${String(action.spec.column)}` : '' }}
                </button>
                <span
                  v-else-if="action.kind === 'remove_filter' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-accent1-100 text-accent1-900 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ Filter removed</span>

                <button
                  v-else-if="action.kind === 'clear_filters' && action.status !== 'applied'"
                  class="inline-flex items-center gap-1 bg-accent1-500 hover:bg-accent1-700 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="applyClearFilters(action)"
                >
                  Clear all filters
                </button>
                <span
                  v-else-if="action.kind === 'clear_filters' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-accent1-100 text-accent1-900 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ Filters cleared</span>

                <span
                  v-else-if="action.kind === 'select_tables' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-100 text-primary-900 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ Selected {{ (action.spec.tables as string[] | undefined)?.join(', ') || 'tables' }}</span>
                <button
                  v-else-if="action.kind === 'select_tables' && action.status !== 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-700 hover:bg-primary-900 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="applySelectTables(action)"
                >Select tables</button>

                <span
                  v-else-if="action.kind === 'set_expression_display' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-100 text-primary-900 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ Expression: {{ String(action.spec.optionId || '') }}</span>
                <button
                  v-else-if="action.kind === 'set_expression_display' && action.status !== 'applied'"
                  class="inline-flex items-center gap-1 bg-primary-700 hover:bg-primary-900 text-white text-xs font-semibold px-3 py-1.5 rounded-full cursor-pointer"
                  @click="applySetExpressionDisplay(action)"
                >Set expression: {{ String(action.spec.optionId || '') }}</button>

                <span
                  v-else-if="action.kind === 'compute' && action.status === 'applied'"
                  class="inline-flex items-center gap-1 bg-gray-100 text-gray-700 text-xs font-semibold px-3 py-1.5 rounded-full"
                >✓ Computed {{ String(action.spec.op || '') }}</span>

                <span
                  v-else-if="action.status === 'error'"
                  class="inline-flex items-center gap-1 bg-red-50 border border-red-200 text-red-700 text-xs font-semibold px-3 py-1.5 rounded-full"
                  :title="action.error"
                >⚠ {{ action.kind }} failed</span>
              </template>
            </div>

            <!-- Undo (appears after at least one action was auto-applied) -->
            <div v-if="msg.undo && !msg.undone" class="mt-2">
              <button
                type="button"
                class="text-xs text-gray-600 hover:text-primary-700 underline cursor-pointer"
                @click="undoMessage(msg)"
              >
                ↶ Undo this step
              </button>
            </div>
            <div v-else-if="msg.undone" class="mt-2 text-[11px] text-gray-400 italic">
              Step undone.
            </div>

            <!-- Compute result tables -->
            <div v-if="computeResultRows(msg).length" class="mt-2 space-y-2">
              <div
                v-for="(r, ri) in computeResultRows(msg)"
                :key="ri"
                class="border border-gray-200 rounded-lg overflow-hidden"
              >
                <div class="px-2 py-1 text-[11px] font-semibold bg-gray-100 text-gray-700">
                  {{ r.title }}
                </div>
                <table class="w-full text-xs">
                  <thead>
                    <tr class="bg-gray-50">
                      <th
                        v-for="h in r.headers"
                        :key="h"
                        class="text-left px-2 py-1 font-medium text-gray-600 border-b border-gray-200"
                      >{{ h }}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="(row, rowIdx) in r.rows" :key="rowIdx" class="hover:bg-gray-50">
                      <td
                        v-for="(cell, ci) in row"
                        :key="ci"
                        class="px-2 py-1 border-b border-gray-100"
                      >{{ cell }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </template>
      </div>

      <form class="border-t border-gray-200 p-3 bg-white" @submit.prevent="submit">
        <div class="flex gap-2">
          <textarea
            v-model="draft"
            :disabled="store.streaming"
            rows="2"
            class="flex-1 resize-none rounded border border-gray-300 focus:border-primary-500 focus:ring-1 focus:ring-primary-500 text-sm p-2 outline-none"
            placeholder="Ask a question about the loaded data…"
            @keydown.enter.exact.prevent="submit"
          />
          <button
            v-if="!store.streaming"
            type="submit"
            class="bg-primary-700 hover:bg-primary-900 text-white px-4 rounded font-semibold text-sm cursor-pointer disabled:opacity-50"
            :disabled="!draft.trim()"
          >Send</button>
          <button
            v-else
            type="button"
            class="bg-gray-500 hover:bg-gray-600 text-white px-4 rounded font-semibold text-sm cursor-pointer"
            @click="store.cancel()"
          >Stop</button>
        </div>
        <p class="mt-2 text-[10px] text-gray-400">
          AI responses may be inaccurate. Verify scientific claims against the source data.
        </p>
      </form>
    </aside>
  </Transition>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { marked } from "marked";
import {
  useAssistantStore,
  type AssistantAction,
  type ChatMessage,
  type ClientContext,
  type UndoSnapshot,
} from "@/stores/assistant";
import { useFiltersStore, type FilterValue } from "@/stores/filters";
import { useVisualizationStore } from "@/stores/visualization";
import { useCatalogStore } from "@/stores/catalog";
import AiSparkleIcon from "@/components/icons/AiSparkleIcon.vue";

const store = useAssistantStore();
const filtersStore = useFiltersStore();
const visualizationStore = useVisualizationStore();
const catalogStore = useCatalogStore();
const router = useRouter();
const route = useRoute();
const draft = ref("");
const scrollEl = ref<HTMLElement | null>(null);

marked.setOptions({ gfm: true, breaks: true });

const suggestedPrompts = [
  "Summarize the loaded datasets.",
  "Which orthogroup is the most represented?",
  "Show ortho_id as a row side color.",
  "Open a heatmap comparing all species.",
];

function stripActionBlocks(content: string): string {
  let out = content
    // Known action blocks (the frontend applies them via chips).
    .replace(
      /```(?:action|deeplink|viz_update|add_filter|remove_filter|clear_filters|select_tables|set_expression_display|compute)\s*\n[\s\S]*?\n```/gi,
      "",
    )
    // Leaked tool-argument JSON that the backend salvaged.
    .replace(/```(?:json|tool)\s*\n[\s\S]*?\n```/gi, "")
    // Any remaining bare ```...``` fence whose body is JSON-shaped —
    // these are leaked tool calls or action payloads the backend didn't
    // recognise; we never want raw JSON shown to the user.
    .replace(/```\s*\n\s*[{[][\s\S]*?\n```/g, "");
  // Trailing unclosed fence (truncated streams) — drop everything from
  // the dangling ``` to the end so partial JSON never reaches the user.
  const fenceCount = (out.match(/```/g) || []).length;
  if (fenceCount % 2 === 1) {
    const last = out.lastIndexOf("```");
    if (last >= 0) out = out.slice(0, last);
  }
  // Inline raw JSON object/array that wasn't fenced — happens when the
  // model dumps a tool result mid-prose. Drop runs starting with `{"`
  // or `[{` that are obviously machine-shaped.
  out = out.replace(/(^|\n)\s*[{[][\s\S]{40,}$/m, (_m, p1) => p1 || "");
  return out.trim();
}

function renderMarkdown(src: string): string {
  if (!src) return "";
  try {
    // Marked is safe by default (escapes HTML). Good enough for trusted SSE text.
    return marked.parse(src, { async: false }) as string;
  } catch {
    return escapeHtml(src);
  }
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Map an internal tool name to a short user-facing description of what
 *  the assistant is doing right now. Intentionally sparse — we just want
 *  the user to know it's not stuck on a black box.
 *  Running form is shown while a tool is in flight; finished form once
 *  the result has come back. */
const TOOL_LABELS: Record<string, { running: string; finished: string }> = {
  list_schema:          { running: "Inspecting datasets",      finished: "Inspected datasets" },
  resolve_value:        { running: "Locating term",            finished: "Located term" },
  list_distinct_values: { running: "Listing values",           finished: "Listed values" },
  count_rows:           { running: "Checking dataset sizes",   finished: "Checked dataset sizes" },
  top_groups:           { running: "Ranking values",           finished: "Ranked values" },
  common_values:        { running: "Comparing across datasets", finished: "Compared datasets" },
  summary_stats:        { running: "Computing statistics",     finished: "Computed statistics" },
  build_deeplink:       { running: "Preparing analysis link",  finished: "Prepared analysis link" },
};

/** Human-readable description of what the assistant is doing right now.
 *  Surfaces the most recent (or currently running) tool so the user
 *  isn't left looking at an opaque "…". */
function thinkingLabel(msg: ChatMessage): string {
  const tools = msg.tools || [];
  // If a tool is currently running, that takes priority over status hints.
  const running = [...tools].reverse().find((t) => t.status === "running");
  if (running) {
    const labels = TOOL_LABELS[running.name] || {
      running: `Running ${running.name}`,
      finished: `Finished ${running.name}`,
    };
    const argHint = running.args ? formatToolArgs(running.args) : "";
    const stepHint = tools.length > 1 ? ` · step ${tools.length}` : "";
    return `${labels.running}${argHint}${stepHint}`;
  }
  // No tool active — surface the latest status phase from the backend.
  if (msg.status) {
    const it = msg.status.iteration;
    const maxIt = msg.status.max_iterations;
    const stepLabel = it && maxIt && maxIt > 1 ? ` · step ${it}/${maxIt}` : "";
    if (msg.status.phase === "model_call") {
      const last = tools[tools.length - 1];
      if (last && last.status === "done") {
        const labels = TOOL_LABELS[last.name];
        if (labels) return `${labels.finished} · interpreting…${stepLabel}`;
      }
      return `Asking the model…${stepLabel}`;
    }
  }
  // Fallback: show last finished tool, otherwise the generic "Thinking".
  const last = tools[tools.length - 1];
  if (last) {
    const labels = TOOL_LABELS[last.name] || {
      running: `Running ${last.name}`,
      finished: `Finished ${last.name}`,
    };
    const argHint = last.args ? formatToolArgs(last.args) : "";
    const stepHint = tools.length > 1 ? ` · step ${tools.length}` : "";
    return `${labels.finished}${argHint}${stepHint}`;
  }
  return "Asking the model…";
}

function formatToolArgs(args: Record<string, unknown>): string {
  // Show 1\u20132 most informative arg keys to give context without flooding.
  const keys = ["query", "column", "group_column", "table", "view", "tables"];
  const parts: string[] = [];
  for (const k of keys) {
    if (args[k] === undefined) continue;
    let v = args[k];
    if (Array.isArray(v)) v = v.join(",");
    const s = String(v);
    if (!s) continue;
    parts.push(`${k}=${s.length > 40 ? s.slice(0, 40) + "\u2026" : s}`);
    if (parts.length >= 2) break;
  }
  return parts.length ? ` (${parts.join(", ")})` : "";
}

function buildClientContext(): ClientContext {
  const tables = typeof route.params.table_names === "string"
    ? (route.params.table_names as string).split(",").filter(Boolean)
    : [];
  // Serialize filters store to plain object (it has Sets + a Map-like filters record).
  let filters: Record<string, unknown> = {};
  try {
    filters = filtersStore.toObject ? filtersStore.toObject() : {};
  } catch {
    filters = {};
  }
  let visualizations: Record<string, unknown> = {};
  try {
    visualizations = visualizationStore.toObject ? visualizationStore.toObject() : {};
  } catch {
    visualizations = {};
  }
  return {
    view: String(route.name || ""),
    route: route.fullPath,
    tables,
    selected_table_names: Array.from(catalogStore.selectedTableNames || []),
    filters,
    visualizations,
    analysis_results: store.analysisContext && Object.keys(store.analysisContext).length
      ? store.analysisContext
      : undefined,
  };
}

function send(prompt: string) {
  draft.value = prompt;
  submit();
}

const autoExecuteTooltip =
  "When enabled, the assistant directly applies filters, view updates and " +
  "navigation as soon as it answers — no manual confirmation required.";

function onToggleAutoExecute(value: boolean) {
  store.setAutoExecute(value);
}

function submit() {
  const text = draft.value.trim();
  if (!text || store.streaming) return;
  draft.value = "";
  store.sendMessage(text, buildClientContext());
}

function openDeeplink(urlPath: string) {
  store.open = false;
  router.push(urlPath);
}

// ---------------------------------------------------------------------------
// Snapshot / Undo — capture pre-action state per assistant message
// ---------------------------------------------------------------------------

function snapshotState(): UndoSnapshot {
  let filters: Record<string, unknown> | null = null;
  let visualizations: Record<string, unknown> | null = null;
  try { filters = filtersStore.toObject ? filtersStore.toObject() : null; } catch { /* empty */ }
  try { visualizations = visualizationStore.toObject ? visualizationStore.toObject() : null; } catch { /* empty */ }
  const selected = Array.from(catalogStore.selectedTableNames || []);
  return {
    filters,
    visualizations,
    selectedTableNames: selected,
    route: route.fullPath,
  };
}

function undoMessage(msg: ChatMessage) {
  const snap = msg.undo;
  if (!snap) return;
  try {
    if (snap.filters) {
      // Partial restore — keep the replaceState/API of the filters store.
      filtersStore.replaceState?.(snap.filters as Parameters<typeof filtersStore.replaceState>[0]);
    }
  } catch { /* empty */ }
  try {
    if (snap.visualizations) {
      const api = (visualizationStore as unknown as {
        replaceState?: (s: Record<string, unknown>) => void;
      }).replaceState;
      api?.(snap.visualizations);
    }
  } catch { /* empty */ }
  try {
    catalogStore.selectAll?.(snap.selectedTableNames || []);
  } catch { /* empty */ }
  if (snap.route && snap.route !== route.fullPath) {
    router.replace(snap.route).catch(() => { /* empty */ });
  }
  msg.undone = true;
  msg.undo = null;
}

function applyVizUpdate(action: AssistantAction) {
  try {
    const patch = (action.spec.patch || action.spec) as Record<string, unknown>;
    // Shallow-merge into the visualization store.
    // Only top-level keys that already exist in the store state are applied.
    const state = visualizationStore.$state as unknown as Record<string, unknown>;
    const safePatch: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(patch)) {
      if (k === "kind" || k === "patch") continue;
      if (k in state) safePatch[k] = v;
    }
    visualizationStore.$patch(safePatch);
    action.status = "applied";
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "viz_update failed";
  }
}

function applyAddFilter(action: AssistantAction) {
  try {
    const spec = action.spec;
    const column = String(spec.column || spec.key || "");
    if (!column) {
      action.status = "error";
      action.error = "missing column";
      return;
    }
    // Normalize multi-value filters to the pipe-separated form the
    // TextFilter chip component expects. The assistant may emit `value`
    // as an array, a comma/newline-separated string, or a `values` field.
    const value = normalizeFilterValue(spec.value ?? (spec as { values?: unknown }).values);
    const rawSpec = spec as {
      match_mode?: unknown;
      exact?: unknown;
    };
    const matchMode: "or" | "and" =
      rawSpec.match_mode === "and" || rawSpec.match_mode === "or"
        ? rawSpec.match_mode
        : "or";
    const exact = rawSpec.exact === undefined ? true : Boolean(rawSpec.exact);
    const filter: FilterValue = {
      value,
      match_mode: matchMode,
      exact,
    };
    filtersStore.setFilter(column, filter);
    action.status = "applied";
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "add_filter failed";
  }
}

/** Convert array / comma-separated / newline-separated input to the pipe-
 *  separated form the filter store + TextFilter component require. Empty
 *  inputs become "" so the `empty` flag still works. */
function normalizeFilterValue(raw: unknown): string {
  if (raw === null || raw === undefined) return "";
  let parts: string[];
  if (Array.isArray(raw)) {
    parts = raw.map((v) => String(v).trim());
  } else {
    const s = String(raw);
    if (!s.trim()) return s;
    parts = s.split(/[,;\n\r|]+/).map((v) => v.trim());
  }
  const seen = new Set<string>();
  const deduped: string[] = [];
  for (const v of parts) {
    if (!v || seen.has(v)) continue;
    seen.add(v);
    deduped.push(v);
  }
  return deduped.join("|");
}

function applyRemoveFilter(action: AssistantAction) {
  try {
    const column = String(action.spec.column || action.spec.key || "");
    if (!column) {
      action.status = "error";
      action.error = "missing column";
      return;
    }
    filtersStore.removeFilter(column);
    action.status = "applied";
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "remove_filter failed";
  }
}

function applyClearFilters(action: AssistantAction) {
  try {
    filtersStore.clearFilters();
    action.status = "applied";
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "clear_filters failed";
  }
}

function applySelectTables(action: AssistantAction) {
  try {
    const list = action.spec.tables as unknown;
    if (!Array.isArray(list)) {
      action.status = "error";
      action.error = "spec.tables must be an array";
      return;
    }
    catalogStore.selectAll?.(list.map((v) => String(v)));
    action.status = "applied";
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "select_tables failed";
  }
}

function applySetExpressionDisplay(action: AssistantAction) {
  try {
    const spec = action.spec as {
      optionId?: string; layer?: string | null; transform?: "raw" | "log2" | "zscore";
    };
    const setter = (visualizationStore as unknown as {
      setExpressionDisplay?: (id: string, layer: string | null, transform: "raw" | "log2" | "zscore") => void;
    }).setExpressionDisplay;
    if (!setter) {
      action.status = "error";
      action.error = "store has no setExpressionDisplay()";
      return;
    }
    setter(String(spec.optionId || "raw"), spec.layer ?? null, spec.transform || "raw");
    action.status = "applied";
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "set_expression_display failed";
  }
}

/** Navigate to a deeplink that the assistant store has already resolved
 *  (server side) into an url_path. Status is already "applied" from the
 *  store hook, so we just push the route. */
function applyDeeplink(action: AssistantAction): boolean {
  try {
    if (!action.url_path) return false;
    if (action.url_path === route.fullPath) return false;
    router.push(action.url_path).catch(() => { /* ignore nav rejection */ });
    return true;
  } catch (e) {
    action.status = "error";
    action.error = (e as Error).message || "deeplink navigation failed";
    return false;
  }
}

/** Auto-apply every pending action of an assistant message. Returns true if any mutation happened. */
function autoApplyActions(msg: ChatMessage): boolean {
  let mutated = false;
  for (const action of msg.actions || []) {
    // Deeplinks are pre-marked "applied" by the store (it just resolves
    // url_path server-side). In auto-execute mode we still want to trigger
    // navigation, so handle them before the pending-only short-circuit.
    if (action.kind === "deeplink") {
      if (applyDeeplink(action)) mutated = true;
      continue;
    }
    if (action.status && action.status !== "pending") continue;
    switch (action.kind) {
      case "viz_update":
        applyVizUpdate(action); mutated = mutated || action.status === "applied"; break;
      case "add_filter":
        applyAddFilter(action); mutated = mutated || action.status === "applied"; break;
      case "remove_filter":
        applyRemoveFilter(action); mutated = mutated || action.status === "applied"; break;
      case "clear_filters":
        applyClearFilters(action); mutated = mutated || action.status === "applied"; break;
      case "select_tables":
        applySelectTables(action); mutated = mutated || action.status === "applied"; break;
      case "set_expression_display":
        applySetExpressionDisplay(action); mutated = mutated || action.status === "applied"; break;
      default: /* compute: handled elsewhere */ break;
    }
  }
  return mutated;
}

interface ResultTable {
  title: string;
  headers: string[];
  rows: Array<Array<string | number>>;
}

function computeResultRows(msg: ChatMessage): ResultTable[] {
  const out: ResultTable[] = [];
  for (const a of msg.actions || []) {
    if (a.kind !== "compute" || a.status !== "applied" || !a.result) continue;
    const res = a.result as { op?: string; results?: Record<string, unknown> };
    if (!res.results) continue;
    for (const [species, payload] of Object.entries(res.results)) {
      const p = payload as Record<string, unknown>;
      if (Array.isArray(p.top)) {
        const rows = (p.top as Array<Record<string, unknown>>).slice(0, 15).map((row) =>
          Object.values(row).map((v) => (typeof v === "number" ? v : String(v))),
        );
        const headers = p.top.length > 0 ? Object.keys(p.top[0] as object) : [];
        out.push({ title: `${species} — ${res.op || "result"}`, headers, rows });
      } else if (p && typeof p === "object") {
        const entries = Object.entries(p).filter(([, v]) => typeof v === "number" || typeof v === "string");
        if (entries.length) {
          out.push({
            title: `${species} — ${res.op || "result"}`,
            headers: ["metric", "value"],
            rows: entries.map(([k, v]) => [k, v as string | number]),
          });
        }
      }
    }
  }
  return out;
}

watch(
  () => store.messages.map((m) => `${(m.content || "").length}:${(m.tools || []).length}:${(m.tools || []).map((t) => t.status).join(",")}:${m.status?.phase || ""}:${m.status?.iteration || 0}`).join("|"),
  () => {
    nextTick(() => {
      if (scrollEl.value) scrollEl.value.scrollTop = scrollEl.value.scrollHeight;
    });
  },
);

// Auto-apply actions + snapshot for undo when streaming ends.
watch(
  () => store.streaming,
  (isStreaming, wasStreaming) => {
    if (wasStreaming && !isStreaming) {
      const last = store.messages[store.messages.length - 1];
      if (!last || last.role !== "assistant" || last.undo) return;
      // Manual mode: leave actions pending so users get explicit chips.
      if (!store.autoExecute) return;
      // Allow the store's post-stream action extraction to finish first.
      nextTick(() => {
        const pre = snapshotState();
        const mutated = autoApplyActions(last);
        if (mutated) last.undo = pre;
      });
    }
  },
);
</script>

<style scoped>
.assistant-slide-enter-active,
.assistant-slide-leave-active {
  transition: transform 0.25s ease;
}
.assistant-slide-enter-from,
.assistant-slide-leave-to {
  transform: translateX(100%);
}
</style>

<style>
/* Scoped :deep() alternatives — apply globally so v-html Markdown styles render. */
.assistant-markdown p { margin: 0 0 0.5rem 0; }
.assistant-markdown p:last-child { margin-bottom: 0; }
.assistant-markdown ul,
.assistant-markdown ol { margin: 0.25rem 0 0.5rem 1.25rem; }
.assistant-markdown li { margin-bottom: 0.125rem; }
.assistant-markdown code {
  background: #f1f5f9;
  color: #be185d;
  padding: 0.05rem 0.3rem;
  border-radius: 0.25rem;
  font-size: 0.82em;
}
.assistant-markdown pre {
  background: #0f172a;
  color: #f1f5f9;
  padding: 0.5rem 0.75rem;
  border-radius: 0.5rem;
  overflow-x: auto;
  font-size: 0.78em;
  margin: 0.25rem 0 0.5rem;
}
.assistant-markdown pre code { background: transparent; color: inherit; padding: 0; }
.assistant-markdown strong { font-weight: 600; color: #111827; }
.assistant-markdown h1,
.assistant-markdown h2,
.assistant-markdown h3 {
  font-weight: 600;
  margin: 0.25rem 0 0.25rem;
  color: #111827;
}
.assistant-markdown h1 { font-size: 1.05rem; }
.assistant-markdown h2 { font-size: 1rem; }
.assistant-markdown h3 { font-size: 0.95rem; }
.assistant-markdown table {
  border-collapse: collapse;
  margin: 0.25rem 0 0.5rem;
  font-size: 0.8em;
}
.assistant-markdown th,
.assistant-markdown td {
  border: 1px solid #e5e7eb;
  padding: 0.125rem 0.375rem;
}
.assistant-markdown a { color: #2563eb; text-decoration: underline; }
</style>
