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


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_list_schema(service, cm, *, max_values_per_col: int = 0) -> Dict[str, Any]:
    """High-level schema the LLM needs to pick tables/columns/filters.

    Returns a compact dict. Uses ``build_overview`` via the caller to stay in
    sync with the landing page; falls back to direct registry inspection.
    """
    tables: List[Dict[str, Any]] = []
    try:
        entries = service.get_tables(include_disabled=False)
    except Exception as e:
        return {"error": f"get_tables failed: {e}", "tables": []}

    for entry in entries:
        code = entry.get("_species_code") or entry.get("code")
        if not code:
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

        tables.append({
            "table_name": entry.get("table_name"),
            "code": code,
            "full_name": entry.get("table_name"),
            "n_samples": int(adata.n_obs),
            "n_genes": int(adata.n_vars),
            "layers": ["X"] + list(adata.layers.keys()),
            "var_columns": [_summary(adata.var, c) for c in var_cols],
            "obs_columns": [_summary(adata.obs, c) for c in obs_cols],
        })

    # Common action-block vocabulary so the LLM remembers what to emit.
    return {
        "tables": tables,
        "views": ["heatmap", "compare", "phylo", "ora", "catalog"],
        "action_kinds": [
            "deeplink", "add_filter", "remove_filter", "clear_filters",
            "select_tables", "set_expression_display", "viz_update",
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

        # Scan categorical-ish columns of .var and .obs.
        for ns_name, df in (("var", adata.var), ("obs", adata.obs)):
            for col in df.columns:
                try:
                    series = df[col]
                    dtype = str(series.dtype)
                    # Skip obvious numerics.
                    if dtype.startswith("float") or dtype.startswith("int"):
                        continue
                    values = _split_array_values(series)
                    if not values:
                        continue
                    counter = Counter(values)
                    # Exact (case-insensitive) match.
                    exact = [v for v in counter if v.lower() == q_lower]
                    for v in exact:
                        hits.append({
                            "table": code, "namespace": ns_name, "column": col,
                            "value": v, "count": counter[v], "match": "exact",
                        })
                    # Substring match (skip if exact already recorded for this column).
                    if not exact:
                        subs = [v for v in counter if q_lower in v.lower()]
                        # Keep top 3 by count per column.
                        subs.sort(key=lambda x: -counter[x])
                        for v in subs[:3]:
                            hits.append({
                                "table": code, "namespace": ns_name, "column": col,
                                "value": v, "count": counter[v], "match": "substring",
                            })
                except Exception:
                    continue

    # Prefer exact matches, then higher counts.
    hits.sort(key=lambda h: (0 if h["match"] == "exact" else 1, -h["count"]))
    return {"query": query, "hits": hits[: int(max_hits)]}


def tool_count_rows(
    service,
    *,
    table: str,
    var_filters: Optional[Dict[str, Any]] = None,
    obs_filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Count ``.var`` and ``.obs`` rows after applying the given filters.

    Filter shape per column: a string, a list of allowed strings, or
    ``{"min":x,"max":y}`` / ``{"contains":"substr"}``. Array-valued columns
    (comma/pipe-separated) are matched by substring containment per value.
    """
    codes = _resolve_species_codes(service, [table])
    if not codes:
        return {"error": f"Unknown table '{table}'"}
    code = codes[0]
    try:
        adata = service.registry.load(code)
    except Exception as e:
        return {"error": f"load failed: {e}"}
    if adata is None:
        return {"error": "table not loaded"}

    import pandas as pd

    def _apply(df, filt):
        mask = pd.Series([True] * len(df), index=df.index)
        for col, spec in (filt or {}).items():
            if col not in df.columns:
                return mask & False
            s = df[col]
            if isinstance(spec, list):
                # Array columns: any configured separator in any cell matches?
                text = s.astype(str)
                m = pd.Series([False] * len(df), index=df.index)
                for v in spec:
                    m |= text.str.contains(
                        rf"(?:^|[,|;\s]){re.escape(str(v))}(?:[,|;\s]|$)",
                        regex=True, na=False,
                    ) | (text == str(v))
                mask &= m
            elif isinstance(spec, dict):
                if "min" in spec:
                    mask &= pd.to_numeric(s, errors="coerce") >= float(spec["min"])
                if "max" in spec:
                    mask &= pd.to_numeric(s, errors="coerce") <= float(spec["max"])
                if "contains" in spec:
                    mask &= s.astype(str).str.contains(str(spec["contains"]), na=False, regex=False)
                if "equals" in spec:
                    mask &= s.astype(str) == str(spec["equals"])
            else:
                mask &= s.astype(str) == str(spec)
        return mask

    var_mask = _apply(adata.var, var_filters or {})
    obs_mask = _apply(adata.obs, obs_filters or {})
    return {
        "table": code,
        "n_var_total": int(adata.n_vars),
        "n_obs_total": int(adata.n_obs),
        "n_var_match": int(var_mask.sum()),
        "n_obs_match": int(obs_mask.sum()),
    }


def tool_top_groups(
    service,
    *,
    table: str,
    group_column: str,
    var_filters: Optional[Dict[str, Any]] = None,
    top_n: int = 10,
    split_arrays: bool = True,
) -> Dict[str, Any]:
    """Count occurrences per value in a ``.var`` column after filtering.

    Handles comma/pipe-separated multi-value cells (e.g. ``ortho_id``,
    ``pfam_id``). Used to answer "which orthogroup is most represented?".
    """
    # Hard cap — otherwise a naive LLM can blow up context with 47k+ rows.
    top_n = max(1, min(int(top_n or 10), 1000))
    codes = _resolve_species_codes(service, [table])
    if not codes:
        return {"error": f"Unknown table '{table}'"}
    code = codes[0]
    try:
        adata = service.registry.load(code)
    except Exception as e:
        return {"error": f"load failed: {e}"}
    if adata is None:
        return {"error": "table not loaded"}
    if group_column not in adata.var.columns:
        return {"error": f"column '{group_column}' not in .var of {code}"}

    # Re-use count_rows' filter logic by applying it to var only.
    filt_result = tool_count_rows(service, table=code, var_filters=var_filters or {})
    if "error" in filt_result:
        return filt_result

    # Compute mask again (cheap) for indexing.
    import pandas as pd
    var = adata.var
    mask = pd.Series([True] * len(var), index=var.index)
    for col, spec in (var_filters or {}).items():
        if col not in var.columns:
            return {"error": f"var column '{col}' does not exist"}
        s = var[col]
        if isinstance(spec, list):
            text = s.astype(str)
            m = pd.Series([False] * len(var), index=var.index)
            for v in spec:
                m |= text.str.contains(
                    rf"(?:^|[,|;\s]){re.escape(str(v))}(?:[,|;\s]|$)", regex=True, na=False,
                ) | (text == str(v))
            mask &= m
        else:
            mask &= s.astype(str) == str(spec)

    filtered = var[mask][group_column]
    if split_arrays:
        values = _split_array_values(filtered)
    else:
        values = [str(v) for v in filtered.dropna() if str(v)]
    counter = Counter(values)
    top = [
        {"value": v, "count": int(n)}
        for v, n in counter.most_common(int(top_n))
    ]
    return {
        "table": code,
        "group_column": group_column,
        "n_rows_considered": int(mask.sum()),
        "top": top,
    }


def tool_common_values(
    service,
    *,
    column: str,
    tables: Optional[List[str]] = None,
    min_tables: Optional[int] = None,
    limit: int = 500,
    var_filters_per_table: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return the set of values shared across the given tables for a column.

    Use this for cross-species intersection questions like "which orthogroups
    are present in ALL species". Pass ``min_tables=len(tables)`` for a strict
    intersection; lower values find values present in at least N tables.

    ``var_filters_per_table`` optionally narrows each table first (same shape
    as :func:`tool_count_rows`'s ``var_filters``).
    """
    codes = _resolve_species_codes(service, tables)
    if not codes:
        return {"error": "no matching species"}
    if min_tables is None:
        min_tables = len(codes)
    min_tables = max(1, min(int(min_tables), len(codes)))

    vf_map = var_filters_per_table or {}
    per_table: Dict[str, set] = {}
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        if adata is None or column not in adata.var.columns:
            continue
        series = adata.var[column]
        # Optional per-table filter pre-narrow.
        vf = vf_map.get(code) or {}
        if vf:
            import pandas as pd
            mask = pd.Series([True] * len(adata.var), index=adata.var.index)
            for col, spec in vf.items():
                if col not in adata.var.columns:
                    mask &= False
                    continue
                s = adata.var[col]
                if isinstance(spec, list):
                    text = s.astype(str)
                    m = pd.Series([False] * len(adata.var), index=adata.var.index)
                    for v in spec:
                        m |= text.str.contains(
                            rf"(?:^|[,|;\s]){re.escape(str(v))}(?:[,|;\s]|$)",
                            regex=True, na=False,
                        ) | (text == str(v))
                    mask &= m
                else:
                    mask &= s.astype(str) == str(spec)
            series = series[mask]
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
        "min_tables": min_tables,
        "n_common": int(sum(1 for _, c in counter.items() if c >= min_tables)),
        "values": common,
        "truncated": truncated,
    }


def tool_summary_stats(
    service,
    *,
    table: str,
    column: str,
    namespace: str = "obs",
    var_filters: Optional[Dict[str, Any]] = None,
    obs_filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Min/max/mean/median/std for a numeric column after filtering."""
    codes = _resolve_species_codes(service, [table])
    if not codes:
        return {"error": f"Unknown table '{table}'"}
    code = codes[0]
    try:
        adata = service.registry.load(code)
    except Exception as e:
        return {"error": f"load failed: {e}"}
    if adata is None:
        return {"error": "table not loaded"}

    import pandas as pd

    df = adata.obs if namespace == "obs" else adata.var
    if column not in df.columns:
        return {"error": f"column '{column}' not in .{namespace} of {code}"}

    # Build per-namespace mask.
    filt = obs_filters if namespace == "obs" else var_filters
    mask = pd.Series([True] * len(df), index=df.index)
    for col, spec in (filt or {}).items():
        if col not in df.columns:
            continue
        s = df[col]
        if isinstance(spec, list):
            mask &= s.astype(str).isin([str(v) for v in spec])
        else:
            mask &= s.astype(str) == str(spec)

    s = pd.to_numeric(df.loc[mask, column], errors="coerce").dropna()
    if s.empty:
        return {"table": code, "column": column, "namespace": namespace, "count": 0}
    return {
        "table": code,
        "column": column,
        "namespace": namespace,
        "count": int(s.size),
        "min": float(s.min()),
        "max": float(s.max()),
        "mean": float(s.mean()),
        "median": float(s.median()),
        "std": float(s.std()),
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

    codes = _resolve_species_codes(service, tables or [])
    if v != "catalog" and not codes:
        return {"error": "at least one known table is required for this view"}

    filters = filters or {}
    visualizations = visualizations or {}
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
    return {"id": hash_id, "url_path": url_path, "view": v, "tables": codes}


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
                    "max_hits": {"type": "integer", "default": 10},
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
                    "limit": {"type": "integer", "default": 50},
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
                "filters. Filter values can be a string, a list of allowed "
                "strings (array-aware), or {min,max,contains,equals}."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "var_filters": {"type": "object", "additionalProperties": True},
                    "obs_filters": {"type": "object", "additionalProperties": True},
                },
                "required": ["table"],
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
                "cells (ortho_id, pfam_id). Use to answer 'which orthogroup "
                "is most represented in the current heatmap?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "group_column": {"type": "string"},
                    "var_filters": {"type": "object", "additionalProperties": True},
                    "top_n": {"type": "integer", "default": 10},
                    "split_arrays": {"type": "boolean", "default": True},
                },
                "required": ["table", "group_column"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "common_values",
            "description": (
                "Return values shared by multiple tables for a .var column. "
                "Use for cross-species questions like 'which orthogroups are "
                "present in ALL species'. Capped at 500 values; use the "
                "`n_common` field for the total count."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "column": {"type": "string"},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "min_tables": {
                        "type": "integer",
                        "description": "min number of tables a value must appear in; default = all given tables (strict intersection).",
                    },
                    "limit": {"type": "integer", "default": 500},
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
            "description": "min/max/mean/median/std of a numeric column after filtering.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {"type": "string"},
                    "column": {"type": "string"},
                    "namespace": {"type": "string", "enum": ["var", "obs"], "default": "obs"},
                    "var_filters": {"type": "object", "additionalProperties": True},
                    "obs_filters": {"type": "object", "additionalProperties": True},
                },
                "required": ["table", "column"],
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
