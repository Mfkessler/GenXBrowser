"""
Tool registry for the AI assistant agentic loop.

Each tool is a small, pure Python function that operates on the already-loaded
``DataService`` (no new endpoints, no I/O beyond what the HTTP routes already
do). Tools are exposed to the LLM in the OpenAI tool-calling schema; both
Gemini (via the OpenAI-compatible endpoint) and GPT-4o understand this shape.

The LLM uses these tools to *introspect* the data and *compose* a final
answer that contains zero or more markdown action blocks
(``deeplink`` / ``add_filter`` / …). Tool calls do not themselves mutate UI
state — the frontend is responsible for that, based on the final action
blocks. This keeps the trust boundary crisp: the backend validates and
inspects, the frontend applies.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_species_codes(service, tables: Optional[List[str]]) -> List[str]:
    """Resolve arbitrary table/species identifiers to canonical species codes."""
    try:
        all_entries = service.get_tables(include_disabled=False)
    except Exception:
        return []
    lookup: Dict[str, str] = {}
    for entry in all_entries:
        code = entry.get("_species_code") or entry.get("code")
        if not code:
            continue
        for key in (entry.get("table_name"), entry.get("full_name"), code):
            if isinstance(key, str) and key:
                lookup[key.lower()] = code
    if not tables:
        return [v for v in dict.fromkeys(lookup.values())]
    out: List[str] = []
    for t in tables:
        key = str(t or "").strip().lower()
        if not key:
            continue
        c = lookup.get(key)
        if c and c not in out:
            out.append(c)
    return out


def _column_series(adata, column: str):
    """Return a pd.Series for a var or obs column, trying both spaces."""
    if column in adata.var.columns:
        return adata.var[column], "var"
    if column in adata.obs.columns:
        return adata.obs[column], "obs"
    return None, None


def _split_array_values(series, separators: Tuple[str, ...] = (",", "|", ";")) -> List[str]:
    """Explode a Series of potentially-multi-valued strings into a flat list."""
    pattern = "[" + re.escape("".join(separators)) + "]"
    out: List[str] = []
    for v in series.dropna().astype(str):
        for part in re.split(pattern, v):
            part = part.strip()
            if part:
                out.append(part)
    return out


def normalize_filter_pipe_value(value: Any) -> Optional[str]:
    """Normalize a filter ``value`` field to the pipe-separated form the
    frontend filter store and TextFilter component expect.

    The assistant frequently emits multi-value filters as either:
      - a JSON array  ``["OG1","OG2"]``
      - a comma-separated string  ``"OG1, OG2"``
      - a newline-separated string
    All three must end up as ``"OG1|OG2"`` so the TextFilter component
    splits them into individual chips. ``None`` and the empty string are
    passed through unchanged (used by the ``empty`` filter mode).
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value]
    else:
        s = str(value)
        if not s.strip():
            return s
        # Split on common separators users / LLMs emit. Pipe is the canonical
        # separator the frontend expects, so we must collapse , ; \n into |.
        items = re.split(r"[,;\n\r|]+", s)
    items = [v.strip() for v in items if v and str(v).strip()]
    if not items:
        return ""
    # De-duplicate while preserving order.
    seen: Dict[str, bool] = {}
    deduped: List[str] = []
    for v in items:
        if v not in seen:
            seen[v] = True
            deduped.append(v)
    return "|".join(deduped)


def normalize_filter_payload(filters: Any) -> Any:
    """Recursively normalize ``filters`` so any ``{value: ...}`` entry that
    carries multiple values uses the pipe-separated form.

    Accepts both the top-level deeplink filter shape
    (``{"filters": {col: {value, strict, empty}}}``) and a flat
    ``{col: {value, strict, empty}}`` mapping. Unknown keys are passed
    through untouched.
    """
    if not isinstance(filters, dict):
        return filters
    out: Dict[str, Any] = {}
    for key, val in filters.items():
        if isinstance(val, dict) and ("value" in val or "values" in val):
            # Single filter spec.
            spec = dict(val)
            raw = spec.pop("values", None)
            if raw is None:
                raw = spec.get("value")
            spec["value"] = normalize_filter_pipe_value(raw)
            out[key] = spec
        elif isinstance(val, dict):
            out[key] = normalize_filter_payload(val)
        else:
            out[key] = val
    return out


# ---------------------------------------------------------------------------
# Filter application — shared semantics with the HTTP API
# ---------------------------------------------------------------------------

def _infer_anndata_column_types(df) -> Dict[str, str]:
    """Map AnnData ``.var`` / ``.obs`` columns to ``parse_filters`` types."""
    from . import filter_parser  # noqa: WPS433
    return filter_parser.infer_dataframe_column_types(df)


def apply_assistant_filters(
    service,
    adata,
    *,
    var_filters: Optional[Dict[str, Any]] = None,
    obs_filters: Optional[Dict[str, Any]] = None,
):
    """Apply rich filter specs to an AnnData's ``.var`` / ``.obs`` frames.

    Returns ``(filtered_var, filtered_obs)``. Each filter dict accepts the
    same shape as the HTTP API: a plain value, a list, or
    ``{"value": ..., "match_mode": "or"|"and", "exact": bool}``. Numeric
    range filters use ``[min, max]`` on the value list. Delegates to
    :func:`app.filter_parser.parse_filter_query` and
    :meth:`DataService._apply_filters` so tool counts always agree with what
    the UI would compute for the same filter.
    """
    # filter_parser is Flask-free and safe to import in any load context
    # (production package, importlib spec loader, etc.).
    try:
        from . import filter_parser  # noqa: WPS433 — avoid circulars at import
    except ImportError:  # pragma: no cover — tests use spec loader
        import importlib.util as _ilu
        from pathlib import Path as _Path
        _spec = _ilu.spec_from_file_location(
            "_gx_filter_parser_fallback",
            _Path(__file__).resolve().parent / "filter_parser.py",
        )
        if not (_spec and _spec.loader):
            logger.warning("apply_assistant_filters: filter_parser unavailable")
            return adata.var, adata.obs
        filter_parser = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(filter_parser)  # type: ignore[union-attr]

    var_df = adata.var
    obs_df = adata.obs

    if var_filters:
        try:
            allowed = filter_parser.infer_dataframe_column_types(var_df)
            var_query = filter_parser.parse_filter_query(var_filters, allowed)
            if var_query:
                var_df = filter_parser.apply_filter_query(var_df.copy(), var_query)
        except Exception as e:
            logger.warning("apply_assistant_filters(var) failed: %s", e, exc_info=True)
    if obs_filters:
        try:
            allowed = filter_parser.infer_dataframe_column_types(obs_df)
            obs_query = filter_parser.parse_filter_query(obs_filters, allowed)
            if obs_query:
                obs_df = filter_parser.apply_filter_query(obs_df.copy(), obs_query)
        except Exception as e:
            logger.warning("apply_assistant_filters(obs) failed: %s", e, exc_info=True)
    return var_df, obs_df


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

# (species_code, h5ad_mtime) → cached per-table summary block. Insertion-
# ordered so we can evict the oldest entry when the cache grows beyond a
# small bound.
_SCHEMA_CACHE: Dict[Tuple[str, float], Dict[str, Any]] = {}

# (species_code, h5ad_mtime, namespace) → list of (column_name, Counter).
# Built lazily by ``_get_value_counters`` and reused across every
# ``tool_resolve_value`` call. The Counter is the dominant cost there;
# rebuilding it on every invocation routinely hit the 20s tool-timeout
# on instances with high-cardinality array columns (go_terms, ipr_desc).
_VALUE_COUNTER_CACHE: Dict[Tuple[str, float, str], List[Tuple[str, "Counter"]]] = {}

# Columns that are pointless to scan with substring-match for resolve_value
# (gene IDs, free-text descriptions). They drown the result list and
# inflate counter-build cost. Exact-match still works because exact
# matches use the same counter and are kept ahead of substring hits.
_RESOLVE_SKIP_COL_SUBSTR = (
    "gene_id", "ensembl", "uniprot", "transcript", "go_terms",
    "description long", "description", "go", "ipr_id", "ipr_desc",
    "db accession", "lineage",
)


def _column_value_counter(series, col: str) -> Optional["Counter"]:
    """Build a ``Counter`` over the (split) values of ``series``.

    Returns ``None`` for obvious numeric columns or empty series so the
    caller can skip them entirely. Lower-cases are NOT applied here so
    the original spelling survives for the LLM to reuse verbatim.
    """
    try:
        dtype = str(series.dtype)
        if dtype.startswith("float") or dtype.startswith("int"):
            return None
        values = _split_array_values(series)
        if not values:
            return None
        return Counter(values)
    except Exception:
        return None


def _get_value_counters(adata, code: str, namespace: str, mtime: float
                        ) -> List[Tuple[str, "Counter"]]:
    """Cached per-column value counters for ``namespace`` ('var' or 'obs').

    Keyed by (species_code, mtime, namespace). The first call for a given
    h5ad pays the build cost; subsequent calls are dictionary lookups.
    The cache automatically invalidates when the file mtime changes.

    High-cardinality / free-text columns listed in
    ``_RESOLVE_SKIP_COL_SUBSTR`` are excluded entirely — building a
    ``Counter`` over (e.g.) ``ipr_desc`` with >20k unique values across
    three species single-threadedly under the GIL was the dominant cost
    that caused parallel ``resolve_value`` calls to hit the tool
    timeout. They are also poor filter targets (the LLM would never
    filter ``ipr_desc`` by substring), so dropping them is a net
    improvement for resolve quality too.
    """
    key = (code, round(float(mtime), 3), namespace)
    cached = _VALUE_COUNTER_CACHE.get(key)
    if cached is not None:
        return cached
    df = adata.var if namespace == "var" else adata.obs
    out: List[Tuple[str, "Counter"]] = []
    for col in df.columns:
        col_l = str(col).lower()
        if any(s in col_l for s in _RESOLVE_SKIP_COL_SUBSTR):
            continue
        ctr = _column_value_counter(df[col], col)
        if ctr is not None:
            out.append((col, ctr))
    _VALUE_COUNTER_CACHE[key] = out
    if len(_VALUE_COUNTER_CACHE) > 128:
        try:
            _VALUE_COUNTER_CACHE.pop(next(iter(_VALUE_COUNTER_CACHE)))
        except StopIteration:
            pass
    return out


def _h5ad_mtime_for(service, code: str) -> float:
    """Best-effort h5ad mtime for cache keys; ``0.0`` on failure.

    A constant fallback still gives correctness — the cache key is just
    less specific. mtime moves cache invalidation to the file system.
    """
    try:
        species_map = getattr(getattr(service, "registry", None), "_species", None) or {}
        info = species_map.get(code) if isinstance(species_map, dict) else None
        path = info.get("file_path") if isinstance(info, dict) else None
        if path and os.path.exists(path):
            return os.path.getmtime(path)
    except Exception:
        pass
    return 0.0


def tool_list_schema(service, cm, *, max_values_per_col: int = 0) -> Dict[str, Any]:
    """High-level schema the LLM needs to pick tables/columns/filters.

    Returns a compact dict. Uses ``build_overview`` via the caller to stay in
    sync with the landing page; falls back to direct registry inspection.

    Per-table summaries are cached by (species code, h5ad mtime); rebuilding
    only happens when the underlying file changes. Across an unchanged
    deployment this turns the call into a constant-time dict lookup.
    """
    tables: List[Dict[str, Any]] = []
    try:
        entries = service.get_tables(include_disabled=False)
    except Exception as e:
        return {"error": f"get_tables failed: {e}", "tables": []}

    species_map = getattr(getattr(service, "registry", None), "_species", None) or {}

    for entry in entries:
        code = entry.get("_species_code") or entry.get("code")
        if not code:
            continue

        # mtime-keyed cache lookup — falls back to a direct rebuild if the
        # registry doesn't expose a file path.
        cache_key: Optional[Tuple[str, float]] = None
        try:
            info = species_map.get(code) if isinstance(species_map, dict) else None
            path = info.get("file_path") if isinstance(info, dict) else None
            if path and os.path.exists(path):
                cache_key = (code, round(os.path.getmtime(path), 3))
        except Exception:
            cache_key = None

        if cache_key is not None and cache_key in _SCHEMA_CACHE:
            cached = _SCHEMA_CACHE[cache_key]
            tables.append({**cached, "table_name": entry.get("table_name"),
                           "full_name": entry.get("table_name")})
            continue

        try:
            adata = service.registry.load(code)
        except Exception:
            adata = None
        if adata is None:
            continue
        var_cols = list(adata.var.columns)
        obs_cols = list(adata.obs.columns)

        def _summary(df, col):
            try:
                s = df[col]
                dtype = str(s.dtype)
                if dtype.startswith("float") or dtype.startswith("int"):
                    nonnull = s.dropna()
                    return {
                        "name": col,
                        "dtype": "numeric",
                        "n_nonnull": int(nonnull.size),
                        "min": float(nonnull.min()) if nonnull.size else None,
                        "max": float(nonnull.max()) if nonnull.size else None,
                    }
                if dtype.startswith("bool"):
                    return {"name": col, "dtype": "boolean", "n_true": int(s.sum())}
                unique = s.dropna().astype(str).nunique()
                return {"name": col, "dtype": "text", "n_unique": int(unique)}
            except Exception:
                return {"name": col, "dtype": "unknown"}

        summary_entry = {
            "table_name": entry.get("table_name"),
            "code": code,
            "full_name": entry.get("table_name"),
            "n_samples": int(adata.n_obs),
            "n_genes": int(adata.n_vars),
            "layers": ["X"] + list(adata.layers.keys()),
            "var_columns": [_summary(adata.var, c) for c in var_cols],
            "obs_columns": [_summary(adata.obs, c) for c in obs_cols],
        }

        if cache_key is not None:
            # Strip the volatile display name before caching so renames don't
            # require an mtime bump to take effect.
            _SCHEMA_CACHE[cache_key] = {
                k: v for k, v in summary_entry.items() if k not in ("table_name", "full_name")
            }
            # Keep cache from growing unbounded across config reloads.
            if len(_SCHEMA_CACHE) > 64:
                # Drop oldest insertion-order entry.
                try:
                    _SCHEMA_CACHE.pop(next(iter(_SCHEMA_CACHE)))
                except StopIteration:
                    pass

        tables.append(summary_entry)

    # Common action-block vocabulary so the LLM remembers what to emit.
    return {
        "tables": tables,
        "views": ["heatmap", "compare", "phylo", "ora", "catalog"],
        "action_kinds": [
            "deeplink", "add_filter", "remove_filter", "clear_filters",
            "select_tables", "set_expression_display", "viz_update",
        ],
    }


# Static catalog of expression-display options. The frontend mirror lives at
# `frontend/src/shared/ExpressionDisplay.ts` — keep these two in sync. The
# tool below filters this list per instance based on which `.layers` are
# actually present in the loaded H5AD files, so the assistant never picks
# an option whose backing layer doesn't exist on this deployment.
_EXPRESSION_OPTIONS: List[Dict[str, Any]] = [
    {"id": "tpm",       "label": "TPM (within-sample)",            "layer": "tpm",    "transform": "raw"},
    {"id": "tmm",       "label": "TMM (between-sample)",           "layer": "tmm",    "transform": "raw"},
    {"id": "getmm",     "label": "GeTMM (gene-length corrected)",  "layer": "getmm",  "transform": "raw"},
    {"id": "log2",      "label": "Log\u2082 (on TPM)",             "layer": "tpm",    "transform": "log2"},
    {"id": "zscore",    "label": "Z-Score (on GeTMM)",             "layer": "getmm",  "transform": "zscore"},
    {"id": "zscore-tpm","label": "Z-Score (on TPM)",               "layer": "tpm",    "transform": "zscore"},
    {"id": "raw",       "label": "Raw Counts",                     "layer": "X",      "transform": "raw"},
]

# Per-view static descriptors of viz controls beyond the expression display.
# Values are filled in dynamically by `tool_list_view_settings` based on the
# loaded data (e.g. `oraColumnName.options` is the intersection of `.var`
# columns across the selected tables).
_VIEW_CONTROLS: Dict[str, List[Dict[str, Any]]] = {
    "heatmap": [
        {"key": "rowLabel",        "type": "boolean", "store_action": "toggleRowLabel"},
        {"key": "colLabel",        "type": "boolean", "store_action": "toggleColLabel"},
        {"key": "legend",          "type": "boolean", "store_action": "toggleLegend"},
        {"key": "hideEmpty",       "type": "boolean", "store_action": "toggleHideEmpty"},
        {"key": "colorScale",      "type": "enum",    "store_action": "setColorScale"},
        {"key": "rowSideColors",   "type": "multi_select_var_column",
         "store_action": "setRowSideColors"},
        {"key": "colSideColors",   "type": "multi_select_obs_column",
         "store_action": "setColSideColors"},
        {"key": "rowOrder.name",   "type": "select_var_column", "store_action": "setRowOrderName"},
        {"key": "colOrder.name",   "type": "select_obs_column", "store_action": "setColOrderName"},
        {"key": "expressionDisplay", "type": "expression_display",
         "store_action": "setExpressionDisplay"},
    ],
    "compare": [
        {"key": "compare.plotType",   "type": "enum",
         "options": ["line", "box", "violin"], "store_action": "setCompareState"},
        {"key": "compare.plotHeight", "type": "integer",
         "min": 200, "max": 1200, "store_action": "setCompareState"},
        {"key": "compare.expression", "type": "expression_display",
         "store_action": "setCompareState",
         "note": "Compare view stores its own expression copy. Use action 'set_expression_display' which mirrors to BOTH expressionDisplay and compare.expression."},
        {"key": "compare.showAllTranscripts", "type": "boolean",
         "store_action": "setCompareState"},
    ],
    "phylo": [
        {"key": "phyloTree.selectedOrthogroup", "type": "select_orthogroup",
         "store_action": "setPhyloTreeState"},
        {"key": "expressionDisplay", "type": "expression_display",
         "store_action": "setExpressionDisplay"},
    ],
    "ora": [
        {"key": "oraColumnName",  "type": "select_var_column", "store_action": "setOraColumnName"},
        {"key": "significance",   "type": "enum",
         "options": ["0.001", "0.01", "0.05", "0.1"], "store_action": "setSignificance"},
        {"key": "oraTopN",        "type": "integer", "min": 1, "max": 500,
         "store_action": "setOraTopN"},
        {"key": "oraMinCount",    "type": "integer", "min": 1, "max": 50,
         "store_action": "setOraMinCount"},
        {"key": "oraTopologicalFilter", "type": "boolean",
         "store_action": "toggleOraTopologicalFilter"},
        {"key": "oraOrder.name",  "type": "enum",
         "options": ["p_value", "fold_enrichment", "subset_count"],
         "store_action": "setOraOrderName"},
    ],
}

# Color-scale enum options the frontend exposes (mirrors COLORSCALES in
# frontend/src/shared/Colorscales.ts).
_COLOR_SCALES: List[str] = [
    "VIRIDIS", "BLUES", "GREENS", "REDS", "GREYS", "ORANGES", "PURPLES",
    "TURBO", "INFERNO", "MAGMA", "PLASMA", "CIVIDIS", "WARM", "COOL",
    "CUBEHELIXDEFAULT", "BUGN", "BUPU", "GNBU", "ORRD", "PUBUGN", "PUBU",
    "PURD", "RDPU", "YLGNBU", "YLGN", "YLORBR", "YLORRD",
]


def tool_list_view_settings(
    service,
    *,
    view: str,
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return the available visualization settings for ``view`` on this
    GenXBrowser instance, with valid value spaces resolved against the
    loaded data.

    Why this exists: settings like the expression-display dropdown depend
    on which `.layers` the H5AD files actually contain — different
    deployments have different layer sets. The LLM MUST call this tool
    before emitting a `set_expression_display` / `viz_update` action so
    it never picks a value that is not selectable in the current UI.

    Returns:
        {
          "view": "<view>",
          "tables_considered": [...],
          "expression_options": [{id,label,layer,transform,available,reason}],
          "controls": [{key,type,...,options?,note?}, ...],
          "common_actions": ["set_expression_display", "viz_update"]
        }
    """
    allowed = {"heatmap", "compare", "phylo", "ora", "catalog"}
    v = str(view or "").strip().lower()
    if v not in allowed:
        return {"error": f"Unknown view '{view}'", "allowed": sorted(allowed)}

    # Resolve the tables in scope: if the caller didn't pass any, use every
    # enabled species so the assistant gets the full instance picture.
    raw_tables = list(tables or [])
    if not raw_tables:
        try:
            entries = service.get_tables(include_disabled=False)
            raw_tables = [
                str(e.get("_species_code") or e.get("code"))
                for e in entries
                if (e.get("_species_code") or e.get("code"))
            ]
        except Exception as e:
            return {"error": f"get_tables failed: {e}"}
    codes = _resolve_species_codes(service, raw_tables) if raw_tables else []

    # Inspect each table once, collect available layers and column sets.
    layer_sets: List[set] = []
    var_col_sets: List[set] = []
    obs_col_sets: List[set] = []
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            adata = None
        if adata is None:
            continue
        layers = {"X"}
        try:
            layers.update(set(adata.layers.keys()))
        except Exception:
            pass
        layer_sets.append(layers)
        try:
            var_col_sets.append(set(adata.var.columns))
        except Exception:
            var_col_sets.append(set())
        try:
            obs_col_sets.append(set(adata.obs.columns))
        except Exception:
            obs_col_sets.append(set())

    # Layer is "available" if it exists in the intersection of all selected
    # tables (so the frontend can compute the same value uniformly across
    # multi-species panels). For view="catalog" or no tables loaded we keep
    # them all marked available.
    if layer_sets:
        common_layers = set.intersection(*layer_sets) if len(layer_sets) > 1 else layer_sets[0]
    else:
        common_layers = {"X", "tpm", "tmm", "getmm"}

    expression_options: List[Dict[str, Any]] = []
    for opt in _EXPRESSION_OPTIONS:
        layer = opt.get("layer")
        avail = (layer is None) or (str(layer) in common_layers)
        entry = {
            "id": opt["id"],
            "label": opt["label"],
            "layer": layer,
            "transform": opt["transform"],
            "available": bool(avail),
        }
        if not avail:
            entry["reason"] = (
                f"layer '{layer}' is not present in all selected tables "
                f"(available layers: {sorted(common_layers)})"
            )
        expression_options.append(entry)

    # Var/Obs column intersections drive enum values for column-selectors.
    common_var = set.intersection(*var_col_sets) if var_col_sets else set()
    common_obs = set.intersection(*obs_col_sets) if obs_col_sets else set()

    controls_out: List[Dict[str, Any]] = []
    for ctrl in _VIEW_CONTROLS.get(v, []):
        c = dict(ctrl)
        ctype = c.get("type")
        if ctype == "enum" and c["key"] == "colorScale":
            c["options"] = _COLOR_SCALES
        elif ctype == "select_var_column":
            c["options"] = sorted(common_var)
        elif ctype == "select_obs_column":
            c["options"] = sorted(common_obs)
        elif ctype == "multi_select_var_column":
            c["options"] = sorted(common_var)
        elif ctype == "multi_select_obs_column":
            c["options"] = sorted(common_obs)
        controls_out.append(c)

    return {
        "view": v,
        "tables_considered": codes,
        "expression_options": expression_options,
        "controls": controls_out,
        "available_layers": sorted(common_layers),
        "common_actions": [
            "set_expression_display", "viz_update",
            "add_filter", "remove_filter", "clear_filters",
        ],
    }


def tool_list_distinct_values(
    service,
    *,
    column: str,
    table: Optional[str] = None,
    prefix: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """Return up to ``limit`` distinct values for a column (optionally per table)."""
    if not column:
        return {"error": "'column' is required"}
    codes = _resolve_species_codes(service, [table] if table else None)
    if not codes:
        return {"error": "No matching species/table"}
    values: List[str] = []
    seen = set()
    prefix_l = (prefix or "").lower()
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        if adata is None:
            continue
        series, _ns = _column_series(adata, column)
        if series is None:
            continue
        for v in _split_array_values(series):
            if prefix_l and not v.lower().startswith(prefix_l):
                continue
            if v in seen:
                continue
            seen.add(v)
            values.append(v)
            if len(values) >= int(limit):
                break
        if len(values) >= int(limit):
            break
    return {"column": column, "values": values, "truncated": len(values) >= int(limit)}


def tool_resolve_value(
    service,
    *,
    query: str,
    tables: Optional[List[str]] = None,
    max_hits: int = 10,
) -> Dict[str, Any]:
    """Find which column(s) contain a free-form term like ``"MIKC"``.

    Returns ranked hits ``{table, column, value, count, match}``. Used by the
    LLM before emitting an ``add_filter`` block so it never guesses the column.

    The per-column ``Counter`` over each species' ``.var`` / ``.obs`` is
    cached by (code, mtime, namespace) — a cold call rebuilds, every
    subsequent call is O(columns × unique_values_in_each) at most and
    typically returns in well under a second.
    """
    if not query:
        return {"error": "'query' is required"}
    codes = _resolve_species_codes(service, tables)
    if not codes:
        return {"error": "No matching species"}
    q_lower = query.strip().lower()
    hits: List[Dict[str, Any]] = []

    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        if adata is None:
            continue

        mtime = _h5ad_mtime_for(service, code)
        for ns_name in ("var", "obs"):
            counters = _get_value_counters(adata, code, ns_name, mtime)
            for col, counter in counters:
                # Exact (case-insensitive) match.
                exact = [v for v in counter if v.lower() == q_lower]
                for v in exact:
                    hits.append({
                        "table": code, "namespace": ns_name, "column": col,
                        "value": v, "count": counter[v], "match": "exact",
                    })
                if exact:
                    continue
                # Skip free-text / very-high-cardinality columns for
                # substring matching to avoid drowning the LLM in noise.
                col_l = col.lower()
                if any(s in col_l for s in _RESOLVE_SKIP_COL_SUBSTR):
                    continue
                subs = [v for v in counter if q_lower in v.lower()]
                # Keep top 3 by count per column.
                subs.sort(key=lambda x: -counter[x])
                for v in subs[:3]:
                    hits.append({
                        "table": code, "namespace": ns_name, "column": col,
                        "value": v, "count": counter[v], "match": "substring",
                    })

    # Prefer exact matches, then higher counts.
    hits.sort(key=lambda h: (0 if h["match"] == "exact" else 1, -h["count"]))
    return {"query": query, "hits": hits[: int(max_hits)]}


def tool_count_rows(
    service,
    *,
    table=None,
    tables=None,
    var_filters: Optional[Dict[str, Any]] = None,
    obs_filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Count ``.var`` and ``.obs`` rows after applying the given filters.

    Accepts EITHER ``table`` (single species code) OR ``tables`` (list).
    With a list the result aggregates per-table counts under
    ``per_table`` and totals under ``totals`` so the LLM only needs ONE
    call instead of N.

    Filter shape per column accepts the same grammar as the HTTP filter
    API: a plain value, a list, or ``{"value":..., "match_mode":"or"|"and",
    "exact":bool}``. Numeric range filters use ``[min, max]`` on the value
    list. This delegates to the same parser and applier used by the
    interactive UI, so counts always match what a real filter would yield.
    """
    raw = _coerce_tables_arg(table, tables)
    if not raw:
        return {"error": "Provide 'table' or 'tables'"}
    multi = isinstance(raw, list) and len(raw) > 1
    codes = _resolve_species_codes(service, raw if isinstance(raw, list) else [raw])
    if not codes:
        return {"error": f"Unknown table(s) '{raw}'"}

    per_table: List[Dict[str, Any]] = []
    tot_var = tot_obs = tot_var_total = tot_obs_total = 0
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception as e:
            per_table.append({"table": code, "error": f"load failed: {e}"})
            continue
        if adata is None:
            per_table.append({"table": code, "error": "table not loaded"})
            continue
        var_f, obs_f = apply_assistant_filters(
            service, adata,
            var_filters=var_filters or {},
            obs_filters=obs_filters or {},
        )
        n_var = int(len(var_f))
        n_obs = int(len(obs_f))
        per_table.append({
            "table": code,
            "n_var_total": int(adata.n_vars),
            "n_obs_total": int(adata.n_obs),
            "n_var_match": n_var,
            "n_obs_match": n_obs,
        })
        tot_var += n_var
        tot_obs += n_obs
        tot_var_total += int(adata.n_vars)
        tot_obs_total += int(adata.n_obs)

    if not multi:
        # Single-table backward-compatible payload.
        return per_table[0] if per_table else {"error": "no result"}
    return {
        "per_table": per_table,
        "totals": {
            "n_var_total": tot_var_total, "n_obs_total": tot_obs_total,
            "n_var_match": tot_var, "n_obs_match": tot_obs,
        },
    }


def _coerce_tables_arg(table, tables) -> Optional[Any]:
    """Normalise the (table, tables) input pair into either a string or list.

    LLMs sometimes pass `table=["AT","SL"]` or `tables="AT"` — accept both.
    """
    if tables is not None:
        if isinstance(tables, str):
            return [tables] if tables else None
        if isinstance(tables, list):
            return [str(t) for t in tables if t] or None
    if table is not None:
        if isinstance(table, list):
            return [str(t) for t in table if t] or None
        if isinstance(table, str):
            return table if table else None
    return None


def tool_top_groups(
    service,
    *,
    table=None,
    tables=None,
    group_column: str,
    var_filters: Optional[Dict[str, Any]] = None,
    top_n: int = 10,
    split_arrays: bool = True,
) -> Dict[str, Any]:
    """Count occurrences per value in a ``.var`` column after filtering.

    Accepts EITHER ``table`` (single species code) OR ``tables`` (list).
    With a list, counts are summed across all tables and a combined
    ranking is returned under ``top`` plus per-table breakdowns under
    ``per_table``. This lets the LLM answer cross-species questions
    ("which orthogroup has the most MADS genes overall?") in ONE tool
    call instead of one per species.

    Handles comma/pipe-separated multi-value cells (e.g. ``ortho_id``,
    ``pfam_id``).
    """
    top_n = max(1, min(int(top_n or 10), 1000))
    raw = _coerce_tables_arg(table, tables)
    if not raw:
        return {"error": "Provide 'table' or 'tables'"}
    multi = isinstance(raw, list) and len(raw) > 1
    codes = _resolve_species_codes(service, raw if isinstance(raw, list) else [raw])
    if not codes:
        return {"error": f"Unknown table(s) '{raw}'"}

    combined: Counter = Counter()
    per_table: List[Dict[str, Any]] = []
    total_considered = 0
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception as e:
            per_table.append({"table": code, "error": f"load failed: {e}"})
            continue
        if adata is None:
            per_table.append({"table": code, "error": "table not loaded"})
            continue
        if group_column not in adata.var.columns:
            per_table.append({"table": code, "error": f"column '{group_column}' not in .var"})
            continue
        # Validate filter columns up front so the LLM sees a clear error.
        bad = [c for c in (var_filters or {}) if c not in adata.var.columns]
        if bad:
            per_table.append({
                "table": code,
                "error": f"var column(s) not in .var: {bad}",
            })
            continue
        var_f, _ = apply_assistant_filters(
            service, adata, var_filters=var_filters or {},
        )
        filtered = var_f[group_column]
        n_rows = int(len(var_f))
        total_considered += n_rows
        if split_arrays:
            values = _split_array_values(filtered)
        else:
            values = [str(v) for v in filtered.dropna() if str(v)]
        local = Counter(values)
        combined.update(local)
        per_table.append({
            "table": code,
            "n_rows_considered": n_rows,
            "top": [
                {"value": v, "count": int(n)}
                for v, n in local.most_common(int(top_n))
            ],
        })

    if not multi:
        # Single-table backward-compatible payload.
        first = per_table[0] if per_table else {}
        if "error" in first:
            return first
        return {
            "table": codes[0],
            "group_column": group_column,
            "n_rows_considered": first.get("n_rows_considered", 0),
            "top": first.get("top", []),
        }

    return {
        "tables": codes,
        "group_column": group_column,
        "n_rows_considered": total_considered,
        "top": [
            {"value": v, "count": int(n)}
            for v, n in combined.most_common(int(top_n))
        ],
        "per_table": per_table,
    }


def tool_common_values(
    service,
    *,
    column: str,
    tables: Optional[List[str]] = None,
    min_tables: Optional[int] = None,
    limit: int = 500,
    namespace: str = "auto",
    var_filters_per_table: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return the set of values shared across the given tables for a column.

    Use this for cross-species intersection questions like "which orthogroups
    are present in ALL species" or "which tissues appear in every dataset".
    Pass ``min_tables=len(tables)`` for a strict intersection; lower values
    find values present in at least N tables.

    ``namespace`` selects which axis of the AnnData to scan:
      - ``"var"`` — gene-level annotations (orthogroups, TF families, ...)
      - ``"obs"`` — sample-level annotations (tissue, condition, ...)
      - ``"auto"`` — try ``var`` first, then ``obs`` (per-table).

    ``var_filters_per_table`` optionally narrows each table first (same shape
    as :func:`tool_count_rows`'s ``var_filters``). Only applied when the
    column lives in ``.var``.
    """
    codes = _resolve_species_codes(service, tables)
    if not codes:
        return {"error": "no matching species"}
    if min_tables is None:
        min_tables = len(codes)
    min_tables = max(1, min(int(min_tables), len(codes)))
    ns_pref = (namespace or "auto").lower()

    vf_map = var_filters_per_table or {}
    per_table: Dict[str, set] = {}
    per_table_namespace: Dict[str, str] = {}
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        if adata is None:
            continue
        # Resolve which namespace contains the column for this table.
        if ns_pref == "var" and column in adata.var.columns:
            ns = "var"
        elif ns_pref == "obs" and column in adata.obs.columns:
            ns = "obs"
        elif ns_pref == "auto":
            if column in adata.var.columns:
                ns = "var"
            elif column in adata.obs.columns:
                ns = "obs"
            else:
                continue
        else:
            continue
        series = adata.var[column] if ns == "var" else adata.obs[column]
        per_table_namespace[code] = ns
        # Optional per-table filter pre-narrow (only for var-namespaced columns).
        vf = vf_map.get(code) or {}
        if vf and ns == "var":
            try:
                var_f, _ = apply_assistant_filters(service, adata, var_filters=vf)
                series = var_f[column] if column in var_f.columns else series.iloc[0:0]
            except Exception as e:  # noqa: BLE001
                logger.warning("common_values pre-narrow failed for %s: %s", code, e)
                series = series.iloc[0:0]
        per_table[code] = set(_split_array_values(series))

    if not per_table:
        return {"error": "no usable tables"}

    # Count in how many tables each value appears.
    counter: Counter = Counter()
    for vals in per_table.values():
        for v in vals:
            counter[v] += 1

    common = [v for v, c in counter.items() if c >= min_tables]
    common.sort()
    truncated = False
    if len(common) > int(limit):
        common = common[: int(limit)]
        truncated = True

    return {
        "column": column,
        "tables": list(per_table.keys()),
        "namespaces": per_table_namespace,
        "per_table_distinct": {k: sorted(v)[:50] for k, v in per_table.items()},
        "min_tables": min_tables,
        "n_common": int(sum(1 for _, c in counter.items() if c >= min_tables)),
        "values": common,
        "truncated": truncated,
    }


def tool_summary_stats(
    service,
    *,
    table=None,
    tables=None,
    column: str,
    namespace: str = "obs",
    var_filters: Optional[Dict[str, Any]] = None,
    obs_filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Min/max/mean/median/std for a numeric column after filtering.

    Accepts EITHER ``table`` (single species code) OR ``tables`` (list).
    With a list each table is reported under ``per_table`` plus a
    pooled summary under ``pooled``.
    """
    raw = _coerce_tables_arg(table, tables)
    if not raw:
        return {"error": "Provide 'table' or 'tables'"}
    multi = isinstance(raw, list) and len(raw) > 1
    codes = _resolve_species_codes(service, raw if isinstance(raw, list) else [raw])
    if not codes:
        return {"error": f"Unknown table(s) '{raw}'"}

    import pandas as pd

    if namespace not in ("obs", "var"):
        return {"error": f"unknown namespace '{namespace}' (expected 'obs' or 'var')"}

    per_table: List[Dict[str, Any]] = []
    pooled: List[float] = []
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception as e:
            per_table.append({"table": code, "error": f"load failed: {e}"})
            continue
        if adata is None:
            per_table.append({"table": code, "error": "table not loaded"})
            continue
        df_full = adata.obs if namespace == "obs" else adata.var
        if column not in df_full.columns:
            per_table.append({"table": code, "error": f"column '{column}' not in .{namespace}"})
            continue
        var_f, obs_f = apply_assistant_filters(
            service, adata,
            var_filters=var_filters or {},
            obs_filters=obs_filters or {},
        )
        df = obs_f if namespace == "obs" else var_f
        s = pd.to_numeric(df[column], errors="coerce").dropna()
        if s.empty:
            per_table.append({"table": code, "column": column, "namespace": namespace, "count": 0})
            continue
        per_table.append({
            "table": code, "column": column, "namespace": namespace,
            "count": int(s.size),
            "min": float(s.min()), "max": float(s.max()),
            "mean": float(s.mean()), "median": float(s.median()),
            "std": float(s.std()),
        })
        pooled.extend(s.tolist())

    if not multi:
        return per_table[0] if per_table else {"error": "no result"}

    if not pooled:
        return {
            "tables": codes, "column": column, "namespace": namespace,
            "per_table": per_table, "pooled": {"count": 0},
        }
    import pandas as _pd
    sp = _pd.Series(pooled)
    return {
        "tables": codes, "column": column, "namespace": namespace,
        "per_table": per_table,
        "pooled": {
            "count": int(sp.size),
            "min": float(sp.min()), "max": float(sp.max()),
            "mean": float(sp.mean()), "median": float(sp.median()),
            "std": float(sp.std()),
        },
    }


def tool_build_deeplink(
    service,
    *,
    view: str,
    tables: List[str],
    filters: Optional[Dict[str, Any]] = None,
    visualizations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist a view state and return ``{id, url_path}``.

    Mirrors ``/api/assistant/deeplink`` but callable from the tool loop so the
    LLM can get the URL *before* emitting its final answer, then embed it.
    """
    allowed = {"heatmap", "compare", "phylo", "ora", "catalog"}
    v = str(view or "").strip().lower()
    if v not in allowed:
        return {"error": f"Unknown view '{view}'", "allowed": sorted(allowed)}

    # Auto-expand the "all loaded species" sentinel so the LLM can request
    # every table without having to enumerate species codes itself. Empty
    # input or any of the literals "all" / "*" / "__all__" expands to the
    # full list of enabled tables.
    raw_tables = list(tables or [])
    sentinels = {"all", "*", "__all__", "every", "everything"}
    if not raw_tables or any(str(t).strip().lower() in sentinels for t in raw_tables):
        try:
            entries = service.get_tables(include_disabled=False)
            raw_tables = [
                str(e.get("_species_code") or e.get("code"))
                for e in entries
                if (e.get("_species_code") or e.get("code"))
            ]
        except Exception as e:
            logger.warning("auto-expand of 'all tables' failed: %s", e)

    codes = _resolve_species_codes(service, raw_tables)
    if v != "catalog" and not codes:
        return {"error": "at least one known table is required for this view"}

    filters = filters or {}
    visualizations = visualizations or {}
    # Normalize multi-value filter entries so the persisted state matches
    # what the frontend filter store expects (pipe-separated chips).
    try:
        filters = normalize_filter_payload(filters)
    except Exception as e:
        logger.warning("filter normalization failed: %s", e)

    # GUARD: Never let the assistant open an empty plot (heatmap / compare /
    # ora / phylo). For data-bearing views, drop any selected table that has
    # zero rows matching the requested filters. If every table is empty,
    # refuse to build the deeplink so the LLM has to apologise + suggest
    # something else instead of producing dead links.
    #
    # Filters in the deeplink payload live under ``filters.filters`` as a
    # FLAT mapping (the frontend filter store doesn't separate gene vs
    # sample columns). For each table we look at the loaded AnnData and
    # split the columns into var- (gene) and obs- (sample) filters,
    # then check `n_var_match` and `n_obs_match` independently. A table
    # is kept only if BOTH counts are non-zero (or no filter applies to
    # that axis). This is what makes "tissue=flower" work for the
    # Compare view: a species with zero flower samples gets dropped here
    # instead of failing the whole deeplink.
    dropped_tables: List[Dict[str, Any]] = []
    warnings: List[str] = []
    # SCHEMA VALIDATION: drop filter columns that don't exist in any of the
    # selected tables and record a warning so the LLM can mention it instead
    # of silently emitting a deep-link with no-op filters.
    if codes and isinstance(filters, dict):
        nested_pre = filters.get("filters") if isinstance(filters.get("filters"), dict) else None
        if isinstance(nested_pre, dict) and nested_pre:
            known_cols: set = set()
            for code in codes:
                try:
                    adata = service.registry.load(code)
                except Exception:
                    adata = None
                if adata is None:
                    continue
                known_cols.update(adata.var.columns)
                known_cols.update(adata.obs.columns)
            if known_cols:
                unknown_cols = [c for c in nested_pre.keys() if c not in known_cols]
                if unknown_cols:
                    cleaned = {c: vs for c, vs in nested_pre.items() if c not in unknown_cols}
                    filters = dict(filters)
                    filters["filters"] = cleaned
                    warnings.append(
                        "Dropped unknown filter column(s): "
                        + ", ".join(sorted(unknown_cols))
                    )

    if v in {"heatmap", "compare", "phylo", "ora"} and codes:
        nested = (filters.get("filters") or {}) if isinstance(filters, dict) else {}
        # Normalize {col: {value: "v1|v2", ...}} → {col: [v1, v2]}.
        flat_filters: Dict[str, List[str]] = {}
        for col, spec in nested.items():
            if not isinstance(spec, dict):
                continue
            raw = spec.get("value")
            if isinstance(raw, list):
                vals = [str(x) for x in raw if str(x).strip()]
            elif isinstance(raw, str) and raw:
                vals = [x for x in raw.split("|") if x]
            else:
                vals = []
            if vals:
                flat_filters[col] = vals

        kept: List[str] = []
        for code in codes:
            if not flat_filters:
                kept.append(code)
                continue
            try:
                adata = service.registry.load(code)
            except Exception:
                adata = None
            if adata is None:
                # Don't penalise on load errors — let the view surface them.
                kept.append(code)
                continue
            var_cols = set(adata.var.columns)
            obs_cols = set(adata.obs.columns)
            var_f = {c: vs for c, vs in flat_filters.items() if c in var_cols}
            obs_f = {c: vs for c, vs in flat_filters.items() if c in obs_cols}
            try:
                cr = tool_count_rows(
                    service, table=code,
                    var_filters=var_f or None,
                    obs_filters=obs_f or None,
                )
            except Exception:
                cr = {}
            cr = cr if isinstance(cr, dict) else {}
            n_var = int(cr.get("n_var_match", 0))
            n_obs = int(cr.get("n_obs_match", 0))
            var_ok = (not var_f) or n_var > 0
            obs_ok = (not obs_f) or n_obs > 0
            if var_ok and obs_ok:
                kept.append(code)
            else:
                if not var_ok:
                    reason = "no transcripts match the gene filters"
                else:
                    reason = "no samples match the sample filters"
                dropped_tables.append({"table": code, "reason": reason})
        if not kept:
            return {
                "error": "all selected tables have zero rows matching the filters; refuse to open empty plot",
                "dropped_tables": dropped_tables,
                "view": v,
            }
        codes = kept
    try:
        size = len(json.dumps({"f": filters, "v": visualizations}))
    except Exception:
        return {"error": "payload not JSON-serialisable"}
    if size > 32000:
        return {"error": f"payload too large ({size} bytes)"}

    try:
        hash_id = service.store_filter({
            "filters": filters or {"__placeholder": True},
            "visualizations": visualizations or {"__placeholder": True},
        })
    except Exception as e:
        return {"error": f"store_filter failed: {e}"}

    prefix = {"heatmap": "h", "compare": "c", "phylo": "p", "ora": "o"}.get(v, "")
    if v == "catalog":
        url_path = f"/catalog?id={hash_id}"
    else:
        url_path = f"/{prefix}/{','.join(codes)}?id={hash_id}"
    out = {"id": hash_id, "url_path": url_path, "view": v, "tables": codes}
    if dropped_tables:
        out["dropped_tables"] = dropped_tables
    if warnings:
        out["warnings"] = warnings
    return out


# ---------------------------------------------------------------------------
# OpenAI tool-calling schema
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "list_schema",
            "description": (
                "List the available species/tables with their .var and .obs "
                "columns, dtypes, and layers. Call this first when you need "
                "to know what data exists."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_view_settings",
            "description": (
                "List the visualization settings available for a view on "
                "this GenXBrowser instance. Returns the expression-display "
                "options actually selectable here (filtered by layers that "
                "exist in the loaded H5AD files), plus per-view controls "
                "(toggles, color scales, ORA columns, plot types, ...). "
                "ALWAYS call this BEFORE emitting `set_expression_display` "
                "or `viz_update` so you never pick a value that the user "
                "cannot select in the UI — the option set is "
                "instance-dependent because deployments load different "
                "expression layers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {
                        "type": "string",
                        "enum": ["heatmap", "compare", "phylo", "ora", "catalog"],
                    },
                    "tables": {
                        "type": "array", "items": {"type": "string"},
                        "description": (
                            "Optional: restrict to these species codes. "
                            "Defaults to every loaded table — the result "
                            "then reflects the intersection of layers / "
                            "columns across all tables."
                        ),
                    },
                },
                "required": ["view"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "resolve_value",
            "description": (
                "Find which column contains a free-form term (e.g. 'MIKC' → "
                "tf_family). Returns ranked hits with table, column, value "
                "and occurrence count. Use before proposing an add_filter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "tables": {
                        "type": "array", "items": {"type": "string"},
                        "description": "Optional: limit to these tables/species codes.",
                    },
                    "max_hits": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_distinct_values",
            "description": (
                "List up to `limit` distinct values in a column, optionally "
                "filtered by a case-insensitive prefix. Handles array columns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "table": {"type": "string"},
                    "prefix": {"type": "string"},
                    "limit": {"type": "integer", "default": 50, "minimum": 1, "maximum": 500},
                },
                "required": ["column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_rows",
            "description": (
                "Count .var (genes) and .obs (samples) rows matching the "
                "filters. Pass `tables` as an ARRAY to count across "
                "multiple species in ONE call (returns per_table + totals). "
                "Filter values can be a string, a list of allowed strings "
                "(array-aware), or {min,max,contains,equals}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "single species code (or use `tables` for multiple)"},
                    "tables": {"type": "array", "items": {"type": "string"}, "description": "multiple species codes — preferred over repeated single-table calls"},
                    "var_filters": {"type": "object", "additionalProperties": True},
                    "obs_filters": {"type": "object", "additionalProperties": True},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "top_groups",
            "description": (
                "Rank values in a .var column by how many genes carry them, "
                "after applying var_filters. Handles comma/pipe-separated "
                "cells (ortho_id, pfam_id). Pass `tables` as an ARRAY to "
                "aggregate across species in ONE call — strongly preferred "
                "over calling this once per species. Use to answer 'which "
                "orthogroup is most represented overall?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "single species code (or use `tables` for multiple)"},
                    "tables": {"type": "array", "items": {"type": "string"}, "description": "multiple species codes — combined ranking returned in `top`, plus `per_table` breakdown"},
                    "group_column": {"type": "string"},
                    "var_filters": {"type": "object", "additionalProperties": True},
                    "top_n": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                    "split_arrays": {"type": "boolean", "default": True},
                },
                "required": ["group_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "common_values",
            "description": (
                "Return values shared by multiple tables for a column. "
                "Use for cross-species questions like 'which orthogroups "
                "are present in ALL species' OR sample-level ones like "
                "'which tissues appear in every dataset'. The column may "
                "live in `.var` (gene annotations) or `.obs` (sample "
                "annotations); set `namespace` accordingly or leave on "
                "'auto'. Result includes `per_table_distinct` showing the "
                "first 50 values per table — use it to compare coverage. "
                "Capped at 500 returned shared values; use `n_common` for "
                "the total count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "namespace": {
                        "type": "string", "enum": ["auto", "var", "obs"],
                        "default": "auto",
                    },
                    "min_tables": {
                        "type": "integer",
                        "description": "min number of tables a value must appear in; default = all given tables (strict intersection).",
                    },
                    "limit": {"type": "integer", "default": 500, "minimum": 1, "maximum": 1000},
                    "var_filters_per_table": {
                        "type": "object",
                        "description": "optional per-table var_filters; keys are species codes.",
                        "additionalProperties": True,
                    },
                },
                "required": ["column", "tables"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "summary_stats",
            "description": "min/max/mean/median/std of a numeric column after filtering. Pass `tables` as an ARRAY to compute across multiple species in ONE call (per_table + pooled).",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string", "description": "single species code (or use `tables` for multiple)"},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "column": {"type": "string"},
                    "namespace": {"type": "string", "enum": ["var", "obs"], "default": "obs"},
                    "var_filters": {"type": "object", "additionalProperties": True},
                    "obs_filters": {"type": "object", "additionalProperties": True},
                },
                "required": ["column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_deeplink",
            "description": (
                "Persist a view state and return a shareable URL path. "
                "Views: heatmap | compare | phylo | ora | catalog. `filters` "
                "and `visualizations` use the frontend store shape."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {"type": "string"},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "filters": {"type": "object", "additionalProperties": True},
                    "visualizations": {"type": "object", "additionalProperties": True},
                },
                "required": ["view", "tables"],
            },
        },
    },
]


def openai_schema() -> List[Dict[str, Any]]:
    """Return the tool definitions in OpenAI tool-calling shape."""
    # Return a deep copy so callers can't mutate the shared list.
    return json.loads(json.dumps(_TOOL_SCHEMAS))


def _get_dispatch():
    return {
        "list_schema": lambda service, cm, **kw: tool_list_schema(service, cm, **kw),
        "list_view_settings": lambda service, cm, **kw: tool_list_view_settings(service, **kw),
        "resolve_value": lambda service, cm, **kw: tool_resolve_value(service, **kw),
        "list_distinct_values": lambda service, cm, **kw: tool_list_distinct_values(service, **kw),
        "count_rows": lambda service, cm, **kw: tool_count_rows(service, **kw),
        "top_groups": lambda service, cm, **kw: tool_top_groups(service, **kw),
        "summary_stats": lambda service, cm, **kw: tool_summary_stats(service, **kw),
        "common_values": lambda service, cm, **kw: tool_common_values(service, **kw),
        "build_deeplink": lambda service, cm, **kw: tool_build_deeplink(service, **kw),
    }


def dispatch_tool_call(
    name: str,
    arguments: Dict[str, Any],
    *,
    service,
    config_manager,
) -> Dict[str, Any]:
    """Dispatch a single tool call; never raises."""
    dispatch = _get_dispatch()
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"unknown tool '{name}'", "available": sorted(dispatch.keys())}
    try:
        return fn(service, config_manager, **(arguments or {}))
    except TypeError as e:
        return {"error": f"bad arguments: {e}"}
    except Exception as e:  # noqa: BLE001 — the LLM gets the error and can retry.
        logger.warning("tool %s failed: %s", name, e, exc_info=True)
        return {"error": f"{type(e).__name__}: {e}"}
