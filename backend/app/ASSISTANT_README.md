# GenXBrowser AI Assistant - Developer Reference

Compact spec of the backend assistant (`assistant.py`, `assistant_tools.py`,
`prompt_builder.py`, `suggestions.py`) plus its frontend contract.

---

## 1. HTTP endpoints

| Path | Method | Body / Returns |
|---|---|---|
| `/api/assistant/chat` | POST | `{messages, stream, include_context, client_context}` → **SSE** (fallback JSON) |
| `/api/assistant/suggestions` | GET | live prompt suggestions, JSON |
| `/api/assistant/deeplink` | POST | persist view state, return share URL |
| `/api/assistant/compute` | POST | reserved for future server-side compute |
| `/api/llm/config`, `/api/llm/test` | GET/POST | LLM provider config + connectivity probe |

### SSE event types (chat)
`delta` (token stream, may carry `replace:true`), `status`
(`phase`+iteration), `tool` (`status: running|done`), `thought`,
`done` (`{model, iterations}`), `error`.

---

## 2. Request flow

1. Frontend POSTs chat history + `client_context` (route, view, filters,
   visualizations, active dataset visibility, selection, …).
2. Backend: scope-guard fast path (greetings / out-of-scope) → assemble
   system prompt with **injected live data + UI state** → enter
   `run_agentic_turn`.
3. Agentic loop (max **10 iterations**, per-tool deadline ~15 s, model
   call timeout derived from gunicorn budget):
   - stream tokens as `delta`
   - on `tool_calls`: intercept action-block tags, dispatch real tools
     in a `ThreadPoolExecutor`, append `{role:"tool",...}` messages,
     re-prompt
   - on plain text: run `retag_action_fences`, deeplink repair, emit
     `done`
4. Iteration cap → forced final completion with note
   `"(Note: tool iteration cap reached.)"`.

---

## 3. `assistant.py` internals

- `run_agentic_turn(cfg, messages, tools, dispatch, max_iterations=10,
  tool_deadline_s=90)` - generator yielding event dicts.
- `_stream_with_fallback` / `_stream_once` - streaming + single retry
  with provider fallback **only** if nothing has been sent to the
  client yet (or LLM signals “tool_calls unsupported”).
- **Tool-call intercept** for mis-emitted action blocks:
  - `_ACTION_BLOCK_TAGS` - fenced-block tag set.
  - `_ACTION_BLOCK_TOOL_NAMES` - same names; if the model emits one of
    these as a `tool_call`, convert args → fenced action block, append
    to assistant content, return synthetic
    `{"ok":true,"applied":"emitted as action block; frontend will apply"}`.
  - `_ACTION_KEY_SIGNATURES` - required-key signatures used to confirm
    payload shape before intercept.
- **Leaked-block salvage** (`_extract_leaked_tool_calls`,
  `_TOOL_KEY_SIGNATURES`): when the model writes a real tool call as a
  ```json``` block in prose, strip + dispatch + nudge.
- **`retag_action_fences`**: rewrites bare or `json` fences whose body
  matches an action signature to the canonical tag; trims unterminated
  trailing fences (max_tokens truncation).
- **Coverage grounding**: results from `top_groups` are stored and
  spliced into the final answer to correct over-generalised claims
  (`present_in`, `absent_from`, `is_present_in_all_tables`).
- **State**: stateless across requests. Three in-process caches keyed on
  `(species_code, h5ad_mtime, config_mtime, …)`:
  `_SCHEMA_CACHE`, `_VALUE_COUNTER_CACHE`, `_FILTER_COLUMN_TYPE_CACHE`.

---

## 4. Tools (`assistant_tools.py`)

All tools are pure-read, return `dict`, never raise (dispatcher wraps
errors as `{"error": "..."}`).

| Tool | Purpose |
|---|---|
| `state_summary` | Cheap dataset/UI summary; **prefer over `list_schema`** |
| `list_schema` | Full `.var`/`.obs` columns + dtypes + sampled values |
| `get_active_view_state` | Loaded vs. visible/hidden dataset cards |
| `update_dataset_visibility` | Build validated `dataset_visibility` action |
| `list_view_settings` | View-specific viz controls + valid expression layers |
| `resolve_value` | Fuzzy-match a term against metadata columns |
| `search_go_terms` | GO process name → GO IDs (dataset-present only by default) |
| `list_distinct_values` | Enum of values for a column (prefix-filter, array-aware) |
| `count_rows` | Row counts under filters, per table or pooled |
| `top_groups` | Ranked values + cross-table presence facts |
| `common_values` | Intersection of column values across tables |
| `summary_stats` | min/max/mean/median/std for numeric columns |
| `build_deeplink` | Validate state → persisted share URL |

`build_deeplink` is the canonical place where the assistant produces
URLs: it normalises species inputs (codes, full/display names, aliases)
to canonical `table_name`, expands `"all"`/`"*"`/`"every"` sentinels,
joins multi-value filters with `|`, enforces per-view row caps, and
rejects empty plots.

Conventions for every tool:
- Resolve user/LLM column input via `_resolve_column_name`.
- Probe filterability and dtype via `_column_is_filterable` /
  `_column_type_from_config`.
- Multi-table returns use `{per_table: [...], totals: {...}}`.
- Never hardcode a column name. Use the config registry.

---

## 5. Prompt (`prompt_builder.py`)

Sections in order: `ROLE` → `CALL_VS_ACTION` → `ACTION_GRAMMAR`
(includes `COLUMN_EXISTENCE_GUARD` and has-value semantics) →
`TOOL_POLICY` (prefer `state_summary`; rule 9 has_value; rule 12 phylo
toolbar) → `FEWSHOT` → injected `DATA_CONTEXT` (column lists, capped
~6 kB) → injected `UI_CONTEXT` (live route, view, filters,
visualizations, selection, analysis_results, active_view_state).

The injected context is wrapped in
`<<<GENX_DATA_BEGIN>>> … <<<GENX_DATA_END>>>` and explicitly marked as
**data, not instructions**. Display names are used in conversation but
all action payloads must use internal column names.

---

## 6. Suggestions (`suggestions.py`)

Called by `/api/assistant/suggestions`. Builds a pool from live
datasets (species, sample/row traits, tree values, generic schema
slots), renders generic templates, pre-validates each candidate
through `build_deeplink`, interleaves results across tables. Output:
`{suggestions: [{id, view, text}, …], count}`. **Templates are
data-agnostic** - they reference column types/roles, not specific
column names.

---

## 7. Action-block protocol (frontend contract)

Fenced JSON blocks that the LLM writes into assistant content; frontend
extracts via regex and dispatches through
`shared/assistantActions.ts`.

| Tag | Spec |
|---|---|
| `add_filter` | `{column, value? \| values?, match_mode?, exact?, has_value?}` |
| `remove_filter` | `{column}` |
| `clear_filters` | `{}` |
| `select_tables` | `{tables:[...]}` |
| `dataset_visibility` | `{action: SHOW_ONLY\|HIDE\|SHOW_ALL\|ADD, dataset_ids?, visible_dataset_ids?}` |
| `set_expression_display` | `{optionId, layer?, transform?}` |
| `set_filter_chain` | `{columns:[...], operator: AND\|OR}` |
| `viz_update` | `{patch:{dot.path: value, …}}` |
| `deeplink` | `{view, tables, filters, visualizations}` |
| `phylo_action` | `{command: reset_view\|expand_all\|collapse_all\|collapse_to_species}` |

Backend intercept guarantees these tags **never reach the client as
OpenAI `tool_calls`** - if the model mis-emits them as tools, the loop
rewrites them into fenced blocks and returns synthetic success.

---

## 8. Conventions & pitfalls

- **Data-agnostic everywhere.** No backend file may hardcode dataset,
  species, or column names. Drive everything from
  `/api/tables` + `config_manager.get_column_definitions()` +
  `list_schema`.
- **Column existence guard.** Before emitting any filter the model
  must verify the column exists; frontend
  (`applyAddFilter`/`applyRemoveFilter`/`applySetFilterChain`) rejects
  unknown columns (`findAnyColumn` against the union of
  `rowColumns | filterableColColumns | colColumns |
  orderableColColumns`). Always ask the user when ambiguous instead of
  guessing.
- **`has_value` semantics.** It maps to the per-column “Has value”
  checkbox in the Sidebar. Emit as
  `add_filter {column: <verified>, has_value: true}`. Not a generic
  non-null predicate; must name a real column.
- **`phylo_action` is route-scoped.** Frontend rejects the action
  unless the current route is the PhyloTree view; it is delivered via
  a `window` `CustomEvent('genx:phylo-command')` because tree state is
  imperative inside the child component, not in Pinia. The view binds
  the listener in `onMounted` / `onUnmounted`.
- **Species code vs `table_name`.** Internally the assistant accepts
  species codes, full names, display names, and aliases. URLs and
  action payloads must always use canonical `table_name` -
  `build_deeplink` is the only place that resolves codes to URLs.
- **Iteration cap fallback.** After 6 loops the agent makes one final
  no-tools call and appends the cap note. Do not bypass; raising the
  cap usually masks a prompt or schema bug.
- **SSE ordering & `replace`.** Frames are append-only unless
  `delta.replace === true` (used to wipe pre-tool “thinking” buffers
  or leaked code blocks). The frontend depends on the order of
  `status`/`tool`/`delta`/`done` events.
- **Undo.** Frontend snapshots
  `{filters, visualizations, selectedTableNames, route}` before each
  applied action; one-step undo runs entirely client-side.
- **Caches.** All caches keyed by content-mtimes, so dropping a new
  h5ad or editing the config invalidates them automatically.

---

## 9. Extending

### Add a tool
1. Implement `tool_<name>(service, config_manager, **kwargs)` returning
   a dict (never raise).
2. Register in the dispatch dict and append OpenAI-shape schema to the
   tool-schemas list.
3. If the tool consumes columns/values, resolve via
   `_resolve_column_name` / `_column_type_from_config`.
4. Add coverage in `tests/test_assistant.py`.

### Add an action-block kind
1. Choose tag, add to `_ACTION_BLOCK_TAGS`,
   `_ACTION_BLOCK_TOOL_NAMES`, `_ACTION_KEY_SIGNATURES`,
   `_ACTION_BLOCK_SCHEMAS`.
2. Document syntax in `ACTION_GRAMMAR`; add policy line to
   `TOOL_POLICY` if needed.
3. Frontend: extend `ActionKind` (`stores/assistant.ts`), the fenced
   regex, add an `apply<Kind>` dispatcher and `.register(...)` it,
   plus a chip in `AssistantPanel.vue`.

### Add a prompt section
Add a constant in `prompt_builder.py`, slot it into the parts list of
`build_system_prompt`, and inject any dynamic payload via the existing
`data_context` / `ui_context` parameters. Stay within the ~12 kB total
UI-context budget.

---

## 10. Tests

Backend (`backend/tests/`):
- `test_assistant.py` - loop, message accumulation, tool dispatch, intercept.
- `test_assistant_agent.py` - agentic-turn fixtures, iteration cap.
- `test_assistant_suggestions.py` - suggestion generation.
- `test_filter_chain.py`, `test_filter_has_value.py` - filter semantics.
- `test_metadata_config_consistency.py`,
  `test_discovery_default_sample_metadata.py` - config / schema.
- `test_overview.py`, `test_sequence_store.py`,
  `test_ora_statistics.py` - adjacent endpoints touched by the assistant.

Frontend (`frontend/src/shared/assistantActions.spec.ts`) covers the
dispatcher, column-existence guard, and action chip lifecycle.
