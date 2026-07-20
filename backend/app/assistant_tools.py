"""
Tool registry for the AI assistant agentic loop.

Each tool is a small, pure Python function that operates on the already-loaded
``DataService`` (no new endpoints, no I/O beyond what the HTTP routes already
do). Tools are exposed to the LLM in the OpenAI tool-calling schema; both
Gemini (via the OpenAI-compatible endpoint) and GPT-4o understand this shape.

The LLM uses these tools to *introspect* the data and *compose* a final
answer that contains zero or more markdown action blocks
(``deeplink`` / ``add_filter`` / ``dataset_visibility`` / …). Tool calls do not themselves mutate UI
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
        aliases = [entry.get("table_name"), entry.get("full_name"), entry.get("display_name"), code]
        try:
            adata = service.registry.load(code)
            uns = getattr(adata, "uns", {}) or {}
            aliases.extend([uns.get("species"), uns.get("name")])
            species = str(uns.get("species") or "").strip()
            name = str(uns.get("name") or "").strip()
            if species and name and species.lower() != name.lower():
                aliases.append(f"{species} ({name})")
                aliases.append(f"{name} ({species})")
        except Exception:
            pass
        for key in aliases:
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


def _species_table_lookup(service) -> Dict[str, str]:
    """Return canonical species-code -> table_name mapping for display/URLs."""
    try:
        all_entries = service.get_tables(include_disabled=False)
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for entry in all_entries:
        code = entry.get("_species_code") or entry.get("code")
        table_name = entry.get("table_name") or entry.get("full_name") or code
        if isinstance(code, str) and code and isinstance(table_name, str) and table_name:
            out[code] = table_name
    return out


def _dataset_entries_from_service(service) -> List[Dict[str, Any]]:
    """Return loaded dataset IDs, labels, and aliases without assuming names."""
    try:
        entries = service.get_tables(include_disabled=False)
    except Exception:
        entries = []
    out: List[Dict[str, Any]] = []
    for entry in entries or []:
        table_name = str(entry.get("table_name") or entry.get("full_name") or entry.get("_species_code") or entry.get("code") or "").strip()
        code = str(entry.get("_species_code") or entry.get("code") or "").strip()
        if not table_name:
            continue
        label = str(entry.get("display_name") or entry.get("full_name") or table_name).strip() or table_name
        aliases: List[str] = []
        for value in (table_name, code, entry.get("full_name"), entry.get("display_name")):
            if isinstance(value, str) and value.strip() and value.strip() not in aliases:
                aliases.append(value.strip())
        out.append({"id": table_name, "label": label, "code": code or table_name, "aliases": aliases})
    return out


def _active_view_state_from_context(service, client_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Normalize live frontend dataset visibility from the request context."""
    client_context = client_context if isinstance(client_context, dict) else {}
    supplied = client_context.get("active_view_state")
    if isinstance(supplied, dict):
        datasets = supplied.get("loaded_datasets") or supplied.get("datasets") or []
        visible_ids = supplied.get("visible_dataset_ids") or []
        if isinstance(datasets, list) and isinstance(visible_ids, list):
            loaded = []
            for item in datasets:
                if not isinstance(item, dict):
                    continue
                dataset_id = str(item.get("id") or item.get("table_name") or "").strip()
                if not dataset_id:
                    continue
                aliases = item.get("aliases") if isinstance(item.get("aliases"), list) else []
                loaded.append({
                    "id": dataset_id,
                    "label": str(item.get("label") or item.get("display_name") or dataset_id).strip() or dataset_id,
                    "code": str(item.get("code") or item.get("_species_code") or dataset_id).strip() or dataset_id,
                    "aliases": [str(alias).strip() for alias in aliases if str(alias).strip()],
                })
            available_ids = [item["id"] for item in loaded]
            visible = [str(item).strip() for item in visible_ids if str(item).strip() in set(available_ids)]
            hidden = [dataset_id for dataset_id in available_ids if dataset_id not in set(visible)]
            return {
                "view": supplied.get("view") or client_context.get("view"),
                "route": supplied.get("route") or client_context.get("route"),
                "loaded_datasets": loaded,
                "visible_dataset_ids": visible,
                "hidden_dataset_ids": hidden,
            }

    loaded = _dataset_entries_from_service(service)
    available_ids = [item["id"] for item in loaded]
    raw_visible = []
    for key in ("tables", "selected_table_names"):
        value = client_context.get(key)
        if isinstance(value, list) and value:
            raw_visible = [str(item).strip() for item in value if str(item).strip()]
            break
    visible = [dataset_id for dataset_id in raw_visible if dataset_id in set(available_ids)] or raw_visible
    hidden = [dataset_id for dataset_id in available_ids if dataset_id not in set(visible)]
    return {
        "view": client_context.get("view"),
        "route": client_context.get("route"),
        "loaded_datasets": loaded,
        "visible_dataset_ids": visible,
        "hidden_dataset_ids": hidden,
    }


def _column_series(adata, column: str):
    """Return a pd.Series for a var or obs column, trying both spaces."""
    if column in adata.var.columns:
        return adata.var[column], "var"
    if column in adata.obs.columns:
        return adata.obs[column], "obs"
    return None, None


def _column_display_maps(config_manager=None) -> Dict[str, Dict[str, str]]:
    """Return fresh internal/display column-name maps from project config."""
    internal_to_display: Dict[str, str] = {}
    display_to_internal: Dict[str, str] = {}
    try:
        if config_manager is not None:
            col_defs = config_manager.get_column_definitions() or {}
        else:
            col_defs = {}
    except Exception:
        col_defs = {}

    for internal, spec in col_defs.items():
        if not isinstance(internal, str):
            continue
        if isinstance(spec, dict) and not _column_is_visible(config_manager, internal, spec):
            continue
        display = None
        if isinstance(spec, dict):
            display = spec.get("display_name")
        display = str(display or internal).strip() or internal
        internal_to_display[internal] = display
        display_to_internal[internal.lower()] = internal
        display_to_internal[display.lower()] = internal

    try:
        raw_mappings = config_manager.get_column_mappings() if config_manager is not None else {}
    except Exception:
        raw_mappings = {}
    if isinstance(raw_mappings, dict):
        for internal, display in raw_mappings.items():
            if not isinstance(internal, str) or not isinstance(display, str):
                continue
            internal_to_display.setdefault(internal, display)
            display_to_internal[internal.lower()] = internal
            display_to_internal[display.lower()] = internal

    return {
        "internal_to_display": internal_to_display,
        "display_to_internal": display_to_internal,
    }


def _assistant_config_mtime(config_manager=None) -> float:
    try:
        path = getattr(config_manager, "config_path", None) if config_manager is not None else None
        if path and os.path.exists(str(path)):
            return round(float(os.path.getmtime(str(path))), 3)
    except Exception:
        pass
    return 0.0


def _column_definitions(config_manager=None) -> Dict[str, Any]:
    try:
        return dict(config_manager.get_column_definitions() or {}) if config_manager is not None else {}
    except Exception:
        return {}

def _column_is_visible(config_manager, column: str, spec: Optional[Dict[str, Any]] = None) -> bool:
    if spec is None:
        spec = _column_definitions(config_manager).get(column) or {}
    if isinstance(spec, dict) and spec.get("visible") is False:
        return False
    return True


def _column_is_filterable(config_manager, column: str, spec: Optional[Dict[str, Any]] = None) -> bool:
    if not _column_is_visible(config_manager, column, spec):
        return False
    if spec is None:
        spec = _column_definitions(config_manager).get(column) or {}
    if isinstance(spec, dict) and spec.get("filterable") is False:
        return False
    return True


def _column_type_from_config(config_manager, column: str, series=None) -> str:
    spec = _column_definitions(config_manager).get(column) or {}
    if isinstance(spec, dict):
        raw_type = str(spec.get("type") or "").lower()
        if spec.get("is_array") or raw_type == "array":
            return "array"
        if raw_type in {"text", "bigint", "double precision", "boolean"}:
            return raw_type
    if series is not None:
        dtype = str(getattr(series, "dtype", "")).lower()
        if dtype.startswith("float"):
            return "double precision"
        if dtype.startswith("int"):
            return "bigint"
        if dtype.startswith("bool"):
            return "boolean"
    return "text"


def _column_separator(config_manager, column: str) -> str:
    spec = _column_definitions(config_manager).get(column) or {}
    if isinstance(spec, dict) and (spec.get("is_array") or spec.get("type") == "array"):
        sep = str(spec.get("array_separator") or ",")
        return sep if sep in {",", "|", ";"} else ","
    return ","


def _display_name_for(config_manager, column: str) -> str:
    maps = _column_display_maps(config_manager)
    return maps.get("internal_to_display", {}).get(column, column)


def invalidate_runtime_cache() -> None:
    """Clear assistant schema/value caches after config or dataset changes."""
    _SCHEMA_CACHE.clear()
    _VALUE_COUNTER_CACHE.clear()
    _FILTER_COLUMN_TYPE_CACHE.clear()
    _WARMUP_CACHE["mtime"] = None
    _WARMUP_CACHE["summary"] = None


def _resolve_column_name(config_manager, column: str, known_columns: Optional[set] = None) -> str:
    """Resolve a user/UI display label to the internal H5AD column key."""
    raw = str(column or "").strip()
    if not raw:
        return raw
    if known_columns and raw in known_columns:
        return raw
    maps = _column_display_maps(config_manager)
    resolved = maps.get("display_to_internal", {}).get(raw.lower())
    if resolved and ((not known_columns) or resolved in known_columns):
        return resolved
    if known_columns:
        for c in known_columns:
            if str(c).lower() == raw.lower():
                return str(c)
    return raw


def _normalize_filter_columns_for_df(
    config_manager,
    filters: Optional[Dict[str, Any]],
    columns: set,
) -> Dict[str, Any]:
    if not filters:
        return {}
    out: Dict[str, Any] = {}
    for col, spec in filters.items():
        resolved = _resolve_column_name(config_manager, str(col), columns)
        if resolved not in columns or not _column_is_filterable(config_manager, resolved):
            continue
        out[resolved] = spec
    return out


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


def _split_column_values(series, config_manager, column: str) -> List[str]:
    if _column_type_from_config(config_manager, column, series) == "array":
        return _split_array_values(series, (_column_separator(config_manager, column),))
    return [str(v).strip() for v in series.dropna().astype(str) if str(v).strip()]


def _column_separators_for(config_manager, columns: set) -> Dict[str, str]:
    return {
        str(col): _column_separator(config_manager, str(col))
        for col in columns
        if _column_type_from_config(config_manager, str(col)) == "array"
    }


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


DEFAULT_ANALYSIS_LIMITS: Dict[str, Dict[str, Optional[int]]] = {
    "heatmap": {"max_rows": 1000},
    "compare": {"max_rows": 1000},
    "phylo": {"max_rows": 1000},
    "ora": {"max_rows": 5000},
    "catalog": {"max_rows": None},
}


def get_analysis_limits(config_manager=None) -> Dict[str, Dict[str, Optional[int]]]:
    """Return analysis row limits from project config with backend defaults.

    Project configs may provide either::

      "analysis_limits": {"heatmap": {"max_rows": 1000}}

    or the shorthand::

      "analysis_limits": {"heatmap": 1000}
    """
    limits = {view: dict(spec) for view, spec in DEFAULT_ANALYSIS_LIMITS.items()}
    cfg_limits: Any = {}
    try:
        cfg = config_manager.get_config() if config_manager is not None else {}
        cfg_limits = cfg.get("analysis_limits") or {}
    except Exception:
        cfg_limits = {}

    if isinstance(cfg_limits, dict):
        for view, spec in cfg_limits.items():
            key = str(view or "").strip().lower()
            if key not in limits:
                continue
            raw_max = spec.get("max_rows") if isinstance(spec, dict) else spec
            if raw_max is None:
                limits[key]["max_rows"] = None
                continue
            try:
                value = int(raw_max)
            except (TypeError, ValueError):
                continue
            limits[key]["max_rows"] = value if value > 0 else None
    return limits


def _deeplink_flat_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(filters, dict):
        return {}
    nested = filters.get("filters") if isinstance(filters.get("filters"), dict) else None
    source = nested if isinstance(nested, dict) else filters
    reserved = {
        "tags", "table_names", "filters", "datasetIdFilters", "idColumnName",
        "filterChainColumns", "filterChainOperators", "filterChainGroups", "filterChainVersion",
    }
    return {
        str(col): spec
        for col, spec in source.items()
        if str(col) not in reserved and isinstance(spec, dict)
    }


def _normalize_deeplink_filter_columns(
    service,
    config_manager,
    codes: List[str],
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(filters, dict):
        return filters
    nested = filters.get("filters") if isinstance(filters.get("filters"), dict) else None
    if not isinstance(nested, dict) or not nested:
        return filters
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
    if not known_cols:
        return filters
    normalized = {}
    for col, spec in nested.items():
        resolved = _resolve_column_name(config_manager, str(col), known_cols)
        if resolved in known_cols and _column_is_filterable(config_manager, resolved):
            normalized[resolved] = spec
    return {**filters, "filters": normalized}


def validate_analysis_request_limits(
    service,
    config_manager,
    *,
    view: str,
    tables: List[str],
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate requested tables against the dynamic row limit for a view."""
    v = str(view or "").strip().lower()
    max_rows = get_analysis_limits(config_manager).get(v, {}).get("max_rows")
    if max_rows is None or v == "catalog" or not tables:
        return {"ok": True, "limit": max_rows, "over_limit": [], "counts": []}

    flat_filters = _deeplink_flat_filters(filters or {})
    counts: List[Dict[str, Any]] = []
    over_limit: List[Dict[str, Any]] = []

    for table_name in tables:
        try:
            code = service._normalize_table_name(table_name)
            adata = service.registry.load(code)
        except Exception:
            adata = None
            code = str(table_name)

        if adata is None:
            continue

        var_cols = set(adata.var.columns)
        obs_cols = set(adata.obs.columns)
        var_f = {c: spec for c, spec in flat_filters.items() if c in var_cols}
        obs_f = {c: spec for c, spec in flat_filters.items() if c in obs_cols}
        try:
            cr = tool_count_rows(
                service,
                table=code,
                var_filters=var_f or None,
                obs_filters=obs_f or None,
            )
        except Exception:
            cr = {}
        cr = cr if isinstance(cr, dict) else {}
        n_rows = int(cr.get("n_var_match", cr.get("n_var_total", 0)) or 0)
        item = {"table": str(table_name), "rows": n_rows, "max_rows": max_rows}
        counts.append(item)
        if n_rows > int(max_rows):
            over_limit.append(item)

    if over_limit:
        labels = ", ".join(
            f"{item['table']} ({item['rows']:,}/{int(max_rows):,})"
            for item in over_limit
        )
        return {
            "ok": False,
            "error": (
                f"{v} request exceeds the dynamic {int(max_rows):,} transcript limit: {labels}. "
                "Ask the user for a narrower filter before opening this analysis."
            ),
            "view": v,
            "limit": max_rows,
            "over_limit": over_limit,
            "counts": counts,
            "suggestion": "Ask for a narrower value from an available Display Name column or another sidebar filter to reduce the result size.",
        }
    return {"ok": True, "limit": max_rows, "over_limit": [], "counts": counts}


# ---------------------------------------------------------------------------
# Filter application — shared semantics with the HTTP API
# ---------------------------------------------------------------------------

def _infer_anndata_column_types(df) -> Dict[str, str]:
    """Map AnnData ``.var`` / ``.obs`` columns to ``parse_filters`` types."""
    try:
        from . import filter_parser  # noqa: WPS433
    except ImportError:  # pragma: no cover — tests use spec loader
        import importlib.util as _ilu
        from pathlib import Path as _Path
        _spec = _ilu.spec_from_file_location(
            "_gx_filter_parser_fallback",
            _Path(__file__).resolve().parent / "filter_parser.py",
        )
        if not (_spec and _spec.loader):
            return {}
        filter_parser = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(filter_parser)  # type: ignore[union-attr]
    return filter_parser.infer_dataframe_column_types(df)


def apply_assistant_filters(
    service,
    adata,
    *,
    var_filters: Optional[Dict[str, Any]] = None,
    obs_filters: Optional[Dict[str, Any]] = None,
    var_column_types: Optional[Dict[str, str]] = None,
    obs_column_types: Optional[Dict[str, str]] = None,
    config_manager=None,
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
    var_filters = _normalize_filter_columns_for_df(config_manager, var_filters, set(var_df.columns))
    obs_filters = _normalize_filter_columns_for_df(config_manager, obs_filters, set(obs_df.columns))

    if var_filters:
        try:
            allowed = var_column_types or filter_parser.infer_dataframe_column_types(var_df)
            var_query = filter_parser.parse_filter_query(var_filters, allowed)
            if var_query:
                var_df = filter_parser.apply_filter_query(
                    var_df,
                    var_query,
                    column_separators=_column_separators_for(config_manager, set(var_df.columns)),
                )
        except Exception as e:
            logger.warning("apply_assistant_filters(var) failed: %s", e, exc_info=True)
    if obs_filters:
        try:
            allowed = obs_column_types or filter_parser.infer_dataframe_column_types(obs_df)
            obs_query = filter_parser.parse_filter_query(obs_filters, allowed)
            if obs_query:
                obs_df = filter_parser.apply_filter_query(
                    obs_df,
                    obs_query,
                    column_separators=_column_separators_for(config_manager, set(obs_df.columns)),
                )
        except Exception as e:
            logger.warning("apply_assistant_filters(obs) failed: %s", e, exc_info=True)
    return var_df, obs_df


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

# (species_code, h5ad_mtime) → cached per-table summary block. Insertion-
# ordered so we can evict the oldest entry when the cache grows beyond a
# small bound.
_SCHEMA_CACHE: Dict[Tuple[Any, ...], Dict[str, Any]] = {}

# (species_code, h5ad_mtime, namespace) → list of (column_name, Counter).
# Built lazily by ``_get_value_counters`` and reused across every
# ``tool_resolve_value`` call. The Counter is the dominant cost there;
# rebuilding it on every invocation routinely hit the 20s tool-timeout
# on instances with high-cardinality array columns (go_terms, ipr_desc).
_VALUE_COUNTER_CACHE: Dict[Tuple[str, float, str], List[Tuple[str, "Counter"]]] = {}

# (species_code, h5ad_mtime, namespace, columns) → inferred filter-parser column types.
# Deeplink validation can count the same filters several times; inferring
# column types by sampling columns is avoidable work once a dataset is loaded
# and unchanged. The columns tuple lets exact assistant filters avoid scanning
# unrelated high-cardinality annotation columns on the cold path.
_FILTER_COLUMN_TYPE_CACHE: Dict[Tuple[str, float, str, Tuple[str, ...]], Dict[str, str]] = {}

_WARMUP_CACHE: Dict[str, Any] = {"mtime": None, "summary": None}

# Columns that are pointless to scan with substring-match for resolve_value
# (gene IDs, free-text descriptions). They drown the result list and
# inflate counter-build cost. Exact-match still works because exact
# matches use the same counter and are kept ahead of substring hits.
_RESOLVE_SKIP_COL_SUBSTR = (
    "gene_id", "ensembl", "uniprot", "transcript", "go_terms",
    "description long", "description", "go", "ipr_id", "ipr_desc",
    "db accession", "lineage",
)


def _column_value_counter(series, col: str, config_manager=None) -> Optional["Counter"]:
    """Build a ``Counter`` over the (split) values of ``series``.

    Returns ``None`` for obvious numeric columns or empty series so the
    caller can skip them entirely. Lower-cases are NOT applied here so
    the original spelling survives for the LLM to reuse verbatim.
    """
    try:
        col_type = _column_type_from_config(config_manager, col, series)
        if col_type in {"bigint", "double precision", "boolean"}:
            return None
        values = _split_column_values(series, config_manager, col)
        if not values:
            return None
        return Counter(values)
    except Exception:
        return None


def _get_value_counters(adata, code: str, namespace: str, mtime: float, config_manager=None
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
    key = (code, round(float(mtime), 3), _assistant_config_mtime(config_manager), namespace)
    cached = _VALUE_COUNTER_CACHE.get(key)
    if cached is not None:
        return cached
    df = adata.var if namespace == "var" else adata.obs
    out: List[Tuple[str, "Counter"]] = []
    for col in df.columns:
        col_l = str(col).lower()
        if not _column_is_filterable(config_manager, str(col)):
            continue
        if any(s in col_l for s in _RESOLVE_SKIP_COL_SUBSTR):
            continue
        ctr = _column_value_counter(df[col], col, config_manager)
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


def _cached_filter_column_types(
    service,
    adata,
    code: str,
    namespace: str,
    columns: Optional[List[str]] = None,
    config_manager=None,
) -> Dict[str, str]:
    df = adata.var if namespace == "var" else adata.obs
    selected = tuple(sorted(str(c) for c in (columns or []) if str(c) in df.columns))
    if not selected:
        selected = tuple(str(c) for c in df.columns)
    key = (code, round(float(_h5ad_mtime_for(service, code)), 3), _assistant_config_mtime(config_manager), namespace, selected)
    cached = _FILTER_COLUMN_TYPE_CACHE.get(key)
    if cached is not None:
        return cached
    inferred = {
        col: _column_type_from_config(config_manager, col, df[col])
        for col in selected
        if _column_is_filterable(config_manager, col)
    }
    if not inferred:
        inferred = _infer_anndata_column_types(df.loc[:, list(selected)])
    _FILTER_COLUMN_TYPE_CACHE[key] = inferred
    if len(_FILTER_COLUMN_TYPE_CACHE) > 256:
        try:
            _FILTER_COLUMN_TYPE_CACHE.pop(next(iter(_FILTER_COLUMN_TYPE_CACHE)))
        except StopIteration:
            pass
    return inferred


def tool_list_schema(service, cm, *, max_values_per_col: int = 5) -> Dict[str, Any]:
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
                cache_key = (code, round(os.path.getmtime(path), 3), _assistant_config_mtime(cm), int(max_values_per_col or 0))
        except Exception:
            cache_key = None

        if cache_key is not None and cache_key in _SCHEMA_CACHE:
            cached = _SCHEMA_CACHE[cache_key]
            tables.append({**cached, "table_name": entry.get("table_name")})
            continue

        try:
            adata = service.registry.load(code)
        except Exception:
            adata = None
        if adata is None:
            continue
        try:
            uns = getattr(adata, "uns", {}) or {}
            species_name = str(uns.get("species") or "").strip()
            dataset_name = str(uns.get("name") or "").strip()
        except Exception:
            species_name = ""
            dataset_name = ""
        display_label = species_name or dataset_name or str(entry.get("full_name") or entry.get("display_name") or entry.get("table_name") or code)
        if species_name and dataset_name and species_name.lower() != dataset_name.lower():
            display_label = f"{species_name} ({dataset_name})"
        var_cols = [str(c) for c in adata.var.columns if _column_is_filterable(cm, str(c))]
        obs_cols = [str(c) for c in adata.obs.columns if _column_is_filterable(cm, str(c))]

        def _summary(df, col):
            try:
                s = df[col]
                dtype = str(s.dtype)
                display_name = _display_name_for(cm, col)
                configured_type = _column_type_from_config(cm, col, s)
                spec = _column_definitions(cm).get(col) or {}
                if configured_type in {"double precision", "bigint"} or dtype.startswith("float") or dtype.startswith("int"):
                    nonnull = s.dropna()
                    return {
                        "name": col,
                        "display_name": display_name,
                        "dtype": "numeric",
                        "column_type": configured_type,
                        "visible": True,
                        "filterable": True,
                        "filter_widget": "range",
                        "n_nonnull": int(nonnull.size),
                        "min": float(nonnull.min()) if nonnull.size else None,
                        "max": float(nonnull.max()) if nonnull.size else None,
                    }
                if configured_type == "boolean" or dtype.startswith("bool"):
                    return {
                        "name": col, "display_name": display_name, "dtype": "boolean",
                        "column_type": "boolean", "visible": True, "filterable": True,
                        "filter_widget": "checkbox", "n_true": int(s.sum()),
                    }
                values = _split_column_values(s, cm, col)
                unique = len(set(values))
                item = {
                    "name": col,
                    "display_name": display_name,
                    "dtype": "array" if configured_type == "array" else "text",
                    "column_type": configured_type,
                    "visible": True,
                    "filterable": True,
                    "filter_widget": "text_pills",
                    "match_modes": ["or", "and"],
                    "exact_supported": True,
                    "n_unique": int(unique),
                }
                if configured_type == "array":
                    item["is_array"] = True
                    item["array_separator"] = _column_separator(cm, col)
                if max_values_per_col and values:
                    item["top_values"] = [
                        {"value": value, "count": int(count)}
                        for value, count in Counter(values).most_common(max(1, min(int(max_values_per_col), 20)))
                    ]
                if isinstance(spec, dict) and spec.get("description"):
                    item["description"] = str(spec.get("description"))
                return item
            except Exception:
                return {"name": col, "display_name": _display_name_for(cm, col), "dtype": "unknown"}

        summary_entry = {
            "table_name": entry.get("table_name"),
            "code": code,
            "full_name": display_label,
            "species_name": species_name or None,
            "dataset_name": dataset_name or None,
            "display_label": display_label,
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
        "column_internal_names": _column_display_maps(cm).get("internal_to_display", {}),
        "column_display_names": {
            display: internal
            for internal, display in _column_display_maps(cm).get("internal_to_display", {}).items()
        },
        "views": ["heatmap", "compare", "phylo", "ora", "catalog"],
        "action_kinds": [
            "deeplink", "add_filter", "remove_filter", "clear_filters",
            "select_tables", "set_expression_display", "set_filter_chain", "viz_update",
        ],
        "action_block_schemas": _ACTION_BLOCK_SCHEMAS,
    }


def warmup_runtime_cache(service, cm) -> Dict[str, Any]:
    """Prime static/semi-static assistant metadata caches for this instance."""
    try:
        from .overview import _overview_mtime
        mtime = _overview_mtime(service, cm)
    except Exception:
        mtime = None
    if _WARMUP_CACHE.get("summary") is not None and _WARMUP_CACHE.get("mtime") == mtime:
        return _WARMUP_CACHE["summary"]
    schema = tool_list_schema(service, cm, max_values_per_col=0)
    tables = schema.get("tables") or []
    summary = {
        "mtime": mtime,
        "datasets": [
            {
                # `name` is the canonical dataset identifier that MUST be passed
                # to `tables` in every tool call and action block (build_deeplink,
                # count_rows, resolve_value, deeplink/select_tables blocks, …).
                # The short `code` is legacy/internal only — never pass it.
                "name": t.get("table_name") or t.get("full_name") or t.get("code"),
                "species_name": t.get("species_name") or t.get("full_name") or t.get("table_name"),
                "code": t.get("code"),
                "label": t.get("table_name") or t.get("full_name") or t.get("code"),
                "n_samples": t.get("n_samples"),
                "n_genes": t.get("n_genes"),
            }
            for t in tables
        ],
        "species_names": [t.get("full_name") or t.get("table_name") or t.get("code") for t in tables],
        "structural_columns": {
            "var": sorted({c.get("name") for t in tables for c in (t.get("var_columns") or []) if c.get("name")}),
            "obs": sorted({c.get("name") for t in tables for c in (t.get("obs_columns") or []) if c.get("name")}),
        },
        "column_internal_names": schema.get("column_internal_names", {}),
        "column_display_names": schema.get("column_display_names", {}),
        "views": schema.get("views", []),
    }
    _WARMUP_CACHE["mtime"] = mtime
    _WARMUP_CACHE["summary"] = summary
    return summary


def tool_state_summary(service, cm) -> Dict[str, Any]:
    """Unified cached state summary for fast first-pass assistant routing."""
    return warmup_runtime_cache(service, cm)


def tool_get_available_datasets(service, cm) -> Dict[str, Any]:
    """GAIA discovery alias: list the species/datasets currently loaded.

    Thin, data-agnostic wrapper over :func:`tool_state_summary` exposing the
    GAIA contract name ``get_available_datasets``. Returns only dataset
    identity/shape (no expression values), so it is cheap and safe as the
    first discovery call of a turn.
    """
    summary = tool_state_summary(service, cm)
    return {
        "datasets": summary.get("datasets", []),
        "species_names": summary.get("species_names", []),
        "views": summary.get("views", []),
    }


def tool_get_dataset_schema(service, cm, *, species_id: Optional[str] = None,
                            max_values_per_col: int = 5, **_ignore) -> Dict[str, Any]:
    """GAIA discovery alias: the `.obs`/`.var` layout of loaded datasets.

    Wraps :func:`tool_list_schema` and, when ``species_id`` is given, narrows
    the result to the matching dataset (matched case-insensitively against the
    canonical ``table_name``, short ``code``, display label, or species name).
    Never returns raw expression values — only column metadata, dtypes,
    categorical levels and numeric ranges. This is the only sanctioned source
    of truth for whether a column the user named actually exists.
    """
    full = tool_list_schema(service, cm, max_values_per_col=max_values_per_col)
    if not species_id:
        return full
    tables = full.get("tables") or []
    needle = str(species_id).strip().lower()
    matched = [
        t for t in tables
        if needle in {
            str(t.get("table_name") or "").lower(),
            str(t.get("code") or "").lower(),
            str(t.get("full_name") or "").lower(),
            str(t.get("species_name") or "").lower(),
            str(t.get("display_label") or "").lower(),
        }
    ]
    if not matched:
        return {
            "error": f"No loaded dataset matches species_id '{species_id}'.",
            "available": [
                {"table_name": t.get("table_name"), "code": t.get("code"),
                 "full_name": t.get("full_name")}
                for t in tables
            ],
        }
    return {**full, "tables": matched}


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
        {"key": "colorScale",      "type": "enum",    "store_action": "setColorScale"},
        {"key": "tooltipFields",   "type": "multi_select_var_column_nullable",
         "store_action": "setTooltipFields"},
        {"key": "showSequencesInTooltip", "type": "boolean",
         "store_action": "toggleShowSequencesInTooltip"},
        {"key": "sequencePreviewLength", "type": "integer", "min": 20, "max": 1000,
         "store_action": "setSequencePreviewLength"},
        {"key": "rowSideColors",   "type": "multi_select_var_column",
         "store_action": "setRowSideColors",
         "note": "ONLY values from this control's `options` are valid. Never invent a column."},
        {"key": "colSideColors",   "type": "multi_select_obs_column",
         "store_action": "setColSideColors",
         "note": "ONLY values from this control's `options` are valid (the exact ColSideColors checkboxes in Visualization Settings). Never invent a column or use a raw .obs column that is not listed."},
        {"key": "rowOrder.name",   "type": "select_var_column", "store_action": "setRowOrderName"},
        {"key": "rowOrder.order",  "type": "enum", "options": ["asc", "desc"],
         "store_action": "toggleRowOrder"},
        {"key": "colOrder.name",   "type": "select_obs_column", "store_action": "setColOrderName"},
        {"key": "colOrder.order",  "type": "enum", "options": ["asc", "desc"],
         "store_action": "toggleColOrder"},
        {"key": "customColOrder.enabled", "type": "boolean",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.mode", "type": "enum", "options": ["metadata", "samples"],
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.metadataColumn", "type": "select_obs_column",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.metadataValues", "type": "string_array",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.sampleNames", "type": "string_array",
         "store_action": "setCustomColOrderState"},
        {"key": "clustering.clusterRows", "type": "boolean", "store_action": "setClusterRows"},
        {"key": "clustering.clusterCols", "type": "boolean", "store_action": "setClusterCols"},
        {"key": "clustering.method", "type": "enum",
         "options": ["average", "complete", "ward"], "store_action": "setClusterMethod"},
        {"key": "clustering.distance", "type": "enum",
         "options": ["correlation", "euclidean"], "store_action": "setClusterDistance"},
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
        {"key": "compare.selectedOrthogroup", "type": "select_orthogroup",
         "store_action": "setCompareState"},
        {"key": "compare.selectedSpecies", "type": "multi_select_table",
         "store_action": "setCompareState"},
        {"key": "compare.showAllTranscripts", "type": "boolean",
         "store_action": "setCompareState"},
        {"key": "compare.groupingColumn", "type": "select_obs_column",
         "store_action": "setCompareState"},
        {"key": "colOrder.name", "type": "select_obs_column", "store_action": "setColOrderName",
         "note": "Compare uses the selected sample grouping column as its x-axis column order."},
        {"key": "colOrder.order", "type": "enum", "options": ["asc", "desc"],
         "store_action": "toggleColOrder"},
        {"key": "customColOrder.enabled", "type": "boolean",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.mode", "type": "enum", "options": ["metadata"],
         "store_action": "setCustomColOrderState",
         "note": "Compare x-axis custom order is metadata-only, based on compare.groupingColumn."},
        {"key": "customColOrder.metadataColumn", "type": "select_obs_column",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.metadataValues", "type": "string_array",
         "store_action": "setCustomColOrderState"},
    ],
    "phylo": [
        {"key": "phyloTree.selectedOrthogroup", "type": "select_orthogroup",
         "store_action": "setPhyloTreeState"},
        {"key": "phyloTree.collapsedNodes", "type": "string_array",
         "store_action": "setPhyloCollapsedNodes"},
        {"key": "phyloTree.branchLengthMode", "type": "enum",
         "options": ["cladogram", "phylogram"], "store_action": "setBranchLengthMode"},
        {"key": "phyloTree.groupingColumn", "type": "select_obs_column",
         "store_action": "setPhyloTreeState"},
        {"key": "colOrder.name", "type": "select_obs_column", "store_action": "setColOrderName",
         "note": "Phylo uses the selected sample grouping column as its x-axis column order."},
        {"key": "colOrder.order", "type": "enum", "options": ["asc", "desc"],
         "store_action": "toggleColOrder"},
        {"key": "customColOrder.enabled", "type": "boolean",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.mode", "type": "enum", "options": ["metadata"],
         "store_action": "setCustomColOrderState",
         "note": "Phylo x-axis custom order is metadata-only, based on phyloTree.groupingColumn."},
        {"key": "customColOrder.metadataColumn", "type": "select_obs_column",
         "store_action": "setCustomColOrderState"},
        {"key": "customColOrder.metadataValues", "type": "string_array",
         "store_action": "setCustomColOrderState"},
        {"key": "clustering.clusterCols", "type": "boolean", "store_action": "setClusterCols"},
        {"key": "clustering.method", "type": "enum",
         "options": ["average", "complete", "ward"], "store_action": "setClusterMethod"},
        {"key": "clustering.distance", "type": "enum",
         "options": ["correlation", "euclidean"], "store_action": "setClusterDistance"},
        {"key": "expressionDisplay", "type": "expression_display",
         "store_action": "setExpressionDisplay"},
    ],
    "ora": [
        {"key": "oraRowSideColor", "type": "boolean", "store_action": "toggleOraRowSideColor"},
        {"key": "oraColumnName",  "type": "select_var_column", "store_action": "setOraColumnName"},
        {"key": "significance",   "type": "enum",
         "options": ["0.001", "0.01", "0.05"], "store_action": "setSignificance"},
        {"key": "oraTopN",        "type": "integer", "min": 1, "max": 500, "default": 10,
         "store_action": "setOraTopN"},
        {"key": "oraMinCount",    "type": "integer", "min": 1, "max": 50,
         "store_action": "setOraMinCount"},
        {"key": "oraGoDepthFilter", "type": "integer", "min": 0,
         "store_action": "setOraGoDepthFilter"},
        {"key": "oraTooltipFields", "type": "multi_select_var_column",
         "store_action": "setOraTooltipFields"},
        {"key": "oraOrder.name",  "type": "enum",
         "options": ["attr", "subset_count", "background_count", "gene_ratio", "fold_enrichment", "p_value"],
         "store_action": "setOraOrderName"},
        {"key": "oraOrder.order", "type": "enum",
         "options": ["asc", "desc"], "store_action": "toggleOraOrder"},
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

_ORA_TOOLTIP_FIELDS: List[str] = [
    "attribute_name", "go_name", "go_namespace", "go_depth", "subset_count",
    "expected_count", "background_count", "fold_enrichment", "gene_ratio",
    "p_value", "q_value", "combined_score",
]


def tool_list_view_settings(
    service,
    config_manager=None,
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

    # Resolve the tables in scope: if the caller didn't pass any (or passed the
    # "all" sentinel the frontend/action-blocks use), use every enabled species
    # so the assistant gets the full instance picture. Without this, an "all"
    # token resolves to NO codes and every column/option list comes back empty —
    # which makes the assistant think nothing is selectable and hallucinate a
    # SideColor/column that isn't in the curated Visualization Settings.
    raw_tables = list(tables or [])
    _wants_all = (not raw_tables) or any(
        str(t).strip().lower() in ("all", "*", "alle") for t in raw_tables
    )
    if _wants_all:
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
        # The H5AD loader may preserve a prior primary matrix under the
        # non-selectable ``None`` key. Only named string layers are valid UI
        # selections and sortable capability identifiers.
        layers = {"X"}
        try:
            layers.update(
                layer for layer in adata.layers.keys()
                if isinstance(layer, str) and layer
            )
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

    # SideColors / column-order selectors do NOT accept arbitrary raw .var /
    # .obs columns — only the CURATED, config-defined metadata columns that
    # the Visualization Settings actually expose as checkboxes/dropdowns. The
    # frontend builds these from the column config (collapsing the default
    # trait's source column into the `default_trait` pseudo-column), so we
    # must advertise exactly that set here. Otherwise the assistant would
    # think every raw .obs column (e.g. `tissue`, `condition`) is a valid
    # colSideColor and hallucinate one that hides behind a similar Display
    # Name. Intersect the curated set across the selected tables.
    def _curated_meta_options(sample_metadata: bool) -> Tuple[set, Dict[str, str]]:
        per_table: List[set] = []
        details: Dict[str, str] = {}
        for code in codes:
            try:
                adata = service.registry.load(code)
            except Exception:
                adata = None
            if adata is None:
                continue
            try:
                cols = service._get_configured_metadata_columns(
                    adata, sample_metadata=sample_metadata,
                )
            except Exception:
                cols = []
            names: set = set()
            for col in cols:
                cname = str(col.get("column_name") or "")
                if not cname:
                    continue
                # Collapse the default-trait source column into the pseudo key
                # the store/UI uses, so the assistant emits the same value a
                # human checkbox click would produce.
                key = "default_trait" if col.get("is_default_trait") else cname
                names.add(key)
                details.setdefault(
                    key,
                    str(col.get("display_name") or display_maps.get(key, key)),
                )
            per_table.append(names)
        if per_table:
            common = set.intersection(*per_table) if len(per_table) > 1 else per_table[0]
        else:
            common = set()
        return common, details

    display_maps = _column_display_maps(config_manager).get("internal_to_display", {})

    curated_obs, curated_obs_details = _curated_meta_options(sample_metadata=True)
    curated_var, curated_var_details = _curated_meta_options(sample_metadata=False)

    def _option_details(columns: set) -> List[Dict[str, str]]:
        return [
            {"name": str(col), "display_name": display_maps.get(str(col), str(col))}
            for col in sorted(columns)
        ]

    def _curated_option_details(columns: set, details: Dict[str, str]) -> List[Dict[str, str]]:
        return [
            {"name": str(col), "display_name": details.get(str(col), display_maps.get(str(col), str(col)))}
            for col in sorted(columns)
        ]

    controls_out: List[Dict[str, Any]] = []
    for ctrl in _VIEW_CONTROLS.get(v, []):
        c = dict(ctrl)
        ctype = c.get("type")
        if ctype == "enum" and c["key"] == "colorScale":
            c["options"] = _COLOR_SCALES
        elif ctype == "select_var_column":
            c["options"] = sorted(common_var)
            c["option_details"] = _option_details(common_var)
        elif ctype == "select_obs_column":
            # colOrder.name / customColOrder.metadataColumn — curated obs set.
            c["options"] = sorted(curated_obs)
            c["option_details"] = _curated_option_details(curated_obs, curated_obs_details)
        elif ctype in ("multi_select_var_column", "multi_select_var_column_nullable"):
            # rowSideColors / tooltipFields — curated var set (config-defined).
            c["options"] = sorted(curated_var)
            c["option_details"] = _curated_option_details(curated_var, curated_var_details)
        elif ctype == "multi_select_obs_column":
            # colSideColors — curated obs set ONLY (the Settings checkboxes).
            c["options"] = sorted(curated_obs)
            c["option_details"] = _curated_option_details(curated_obs, curated_obs_details)
        elif ctype == "multi_select_table":
            c["options"] = codes
        if c.get("key") == "oraTooltipFields":
            c["options"] = _ORA_TOOLTIP_FIELDS
        controls_out.append(c)

    return {
        "view": v,
        "tables_considered": codes,
        "expression_options": expression_options,
        "controls": controls_out,
        "available_layers": sorted(common_layers),
        "common_actions": [
            "set_expression_display", "viz_update",
            "add_filter", "remove_filter", "clear_filters", "set_filter_chain",
        ],
    }


def tool_list_distinct_values(
    service,
    config_manager=None,
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
        column = _resolve_column_name(config_manager, column, set(adata.var.columns) | set(adata.obs.columns))
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
    return {"column": column, "display_name": _display_name_for(config_manager, column), "values": values, "truncated": len(values) >= int(limit)}


def tool_get_active_view_state(service, *, client_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return live dataset visibility captured by the frontend for this turn."""
    state = _active_view_state_from_context(service, client_context)
    return {
        **state,
        "available_dataset_ids": [item["id"] for item in state.get("loaded_datasets", [])],
    }


def tool_update_dataset_visibility(
    service,
    *,
    action: str,
    dataset_ids: Optional[List[str]] = None,
    client_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate a requested dataset-card visibility mutation."""
    state = _active_view_state_from_context(service, client_context)
    action_norm = str(action or "").strip().upper()
    if action_norm not in {"SHOW_ONLY", "HIDE", "SHOW_ALL", "ADD"}:
        return {"ok": False, "error": "action must be SHOW_ONLY, HIDE, SHOW_ALL, or ADD", "active_view_state": state}

    available_ids = [item["id"] for item in state.get("loaded_datasets", [])]
    available = set(available_ids)
    visible_ids = [str(item) for item in state.get("visible_dataset_ids", []) if str(item) in available]
    requested_ids = [str(item).strip() for item in (dataset_ids or []) if str(item).strip()]
    unknown = [item for item in requested_ids if item not in available]
    if unknown:
        return {
            "ok": False,
            "error": "dataset_ids must come from get_active_view_state().available_dataset_ids",
            "unknown_dataset_ids": unknown,
            "active_view_state": state,
        }

    if action_norm == "SHOW_ALL":
        next_ids = available_ids
        requested_ids = available_ids
    elif action_norm == "SHOW_ONLY":
        if not requested_ids:
            return {"ok": False, "error": "SHOW_ONLY requires at least one dataset_id", "active_view_state": state}
        next_ids = [item for item in available_ids if item in set(requested_ids)]
    elif action_norm == "HIDE":
        if not requested_ids:
            return {"ok": False, "error": "HIDE requires at least one dataset_id", "active_view_state": state}
        next_ids = [item for item in visible_ids if item not in set(requested_ids)]
    else:
        if not requested_ids:
            return {"ok": False, "error": "ADD requires at least one dataset_id", "active_view_state": state}
        next_ids = [item for item in visible_ids if item in available]
        for item in available_ids:
            if item in requested_ids and item not in next_ids:
                next_ids.append(item)

    labels = {item["id"]: item.get("label") or item["id"] for item in state.get("loaded_datasets", [])}
    return {
        "ok": True,
        "action": action_norm,
        "dataset_ids": requested_ids,
        "visible_dataset_ids_before": visible_ids,
        "visible_dataset_ids_after": next_ids,
        "labels_after": [labels.get(item, item) for item in next_ids],
        "action_block": {
            "action": action_norm,
            "dataset_ids": requested_ids,
            "visible_dataset_ids": next_ids,
        },
    }


def tool_resolve_value(
    service,
    config_manager=None,
    *,
    query: str,
    tables: Optional[List[str]] = None,
    max_hits: int = 10,
) -> Dict[str, Any]:
    """Find which column(s) contain a free-form user term.

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
            counters = _get_value_counters(adata, code, ns_name, mtime, config_manager)
            for col, counter in counters:
                # Exact (case-insensitive) match.
                exact = [v for v in counter if v.lower() == q_lower]
                for v in exact:
                    hits.append({
                        "table": code, "namespace": ns_name, "column": col,
                        "display_name": _display_name_for(config_manager, col),
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
                        "display_name": _display_name_for(config_manager, col),
                        "value": v, "count": counter[v], "match": "substring",
                    })

    # Prefer exact matches, then higher counts.
    hits.sort(key=lambda h: (0 if h["match"] == "exact" else 1, -h["count"]))
    return {"query": query, "hits": hits[: int(max_hits)]}


def tool_search_go_terms(
    service,
    *,
    query: str,
    limit: int = 20,
    only_in_dataset: bool = True,
) -> Dict[str, Any]:
    """Resolve a free-form biological-process term to GO IDs.

    Uses the loaded GO OBO ontology (via ``current_app.go_service``) to
    fuzzy-match human descriptions like ``"photosynthesis"`` or
    ``"flower development"`` to their canonical ``GO:#######`` IDs and
    definitions. This is the GO-aware counterpart to ``resolve_value`` —
    the latter scans column values verbatim and therefore cannot map a
    natural-language process name (which is NOT stored in ``go_terms``)
    to its ID.

    By default results are restricted to GO terms that actually appear
    in the dataset's ``go_terms`` column so the LLM can immediately
    emit an ``add_filter`` on ``go_terms`` without producing an empty
    plot. Set ``only_in_dataset=False`` to also surface ontology terms
    that are not annotated in any loaded H5AD (useful for hierarchy /
    "did you mean" follow-ups).

    Returns ``{available, query, results:[{id,name,namespace,definition,
    in_dataset}], count, in_dataset_count}``.
    """
    if not query or not str(query).strip():
        return {"error": "'query' is required"}

    # Fetch go_service from the Flask app context. Done lazily so the tool
    # module stays importable in non-Flask test contexts.
    go_service = None
    try:
        from flask import current_app  # noqa: WPS433
        go_service = getattr(current_app, "go_service", None)
    except Exception:
        go_service = None

    if not go_service or not getattr(go_service, "is_available", lambda: False)():
        return {
            "available": False,
            "query": query,
            "results": [],
            "message": "GO ontology not loaded on this instance",
        }

    lim = max(1, min(int(limit or 20), 100))
    try:
        # Pull more than `limit` so the dataset-intersection filter still
        # leaves a useful number of hits.
        raw_hits = go_service.search_terms(query, limit=lim * 5) or []
    except Exception as e:
        logger.warning("search_go_terms: ontology search failed: %s", e)
        return {"error": f"GO search failed: {e}"}

    dataset_ids: set = set()
    try:
        dataset_ids = set(service.get_unique_values("go_terms") or [])
    except Exception:
        dataset_ids = set()

    results: List[Dict[str, Any]] = []
    for hit in raw_hits:
        if not isinstance(hit, dict):
            continue
        gid = hit.get("id")
        in_ds = bool(gid and gid in dataset_ids)
        if only_in_dataset and not in_ds:
            continue
        results.append({
            "id": gid,
            "name": hit.get("name"),
            "namespace": hit.get("namespace"),
            "definition": hit.get("definition"),
            "in_dataset": in_ds,
        })
        if len(results) >= lim:
            break

    return {
        "available": True,
        "query": query,
        "results": results,
        "count": len(results),
        "in_dataset_count": sum(1 for r in results if r["in_dataset"]),
        "only_in_dataset": bool(only_in_dataset),
    }


def tool_count_rows(
    service,
    config_manager=None,
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
        var_filters_norm = _normalize_filter_columns_for_df(config_manager, var_filters, set(adata.var.columns))
        obs_filters_norm = _normalize_filter_columns_for_df(config_manager, obs_filters, set(adata.obs.columns))
        var_f, obs_f = apply_assistant_filters(
            service, adata,
            var_filters=var_filters_norm,
            obs_filters=obs_filters_norm,
            var_column_types=_cached_filter_column_types(service, adata, code, "var", list(var_filters_norm.keys()), config_manager) if var_filters_norm else None,
            obs_column_types=_cached_filter_column_types(service, adata, code, "obs", list(obs_filters_norm.keys()), config_manager) if obs_filters_norm else None,
            config_manager=config_manager,
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
    config_manager=None,
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
    ``per_table``. This lets the LLM answer cross-species ranking questions
    in ONE tool call instead of one per species.

    Handles comma/pipe-separated multi-value cells.
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
    coverage_counts: Dict[str, Dict[str, int]] = {}
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
        group_column = _resolve_column_name(config_manager, group_column, set(adata.var.columns))
        var_filters_norm = _normalize_filter_columns_for_df(config_manager, var_filters, set(adata.var.columns))
        if group_column not in adata.var.columns:
            per_table.append({"table": code, "error": f"column '{group_column}' not in .var"})
            continue
        # Validate filter columns up front so the LLM sees a clear error.
        bad = [c for c in (var_filters_norm or {}) if c not in adata.var.columns]
        if bad:
            per_table.append({
                "table": code,
                "error": f"var column(s) not in .var: {bad}",
            })
            continue
        var_f, _ = apply_assistant_filters(
            service, adata, var_filters=var_filters_norm or {}, config_manager=config_manager,
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
        for value, count in local.items():
            coverage_counts.setdefault(value, {})[code] = int(count)
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

    top: List[Dict[str, Any]] = []
    for value, count in combined.most_common(int(top_n)):
        per_table_counts = coverage_counts.get(value, {})
        present_in = [code for code in codes if int(per_table_counts.get(code, 0)) > 0]
        absent_from = [code for code in codes if code not in present_in]
        top.append({
            "value": value,
            "count": int(count),
            "present_in": present_in,
            "absent_from": absent_from,
            "present_table_count": len(present_in),
            "table_count": len(codes),
            "is_present_in_all_tables": len(present_in) == len(codes),
            "per_table_counts": {
                code: int(per_table_counts.get(code, 0)) for code in codes
            },
        })

    return {
        "tables": codes,
        "group_column": group_column,
        "n_rows_considered": total_considered,
        "top": top,
        "per_table": per_table,
    }


def tool_common_values(
    service,
    config_manager=None,
    *,
    column: str,
    tables: Optional[List[str]] = None,
    min_tables: Optional[int] = None,
    limit: int = 500,
    namespace: str = "auto",
    var_filters_per_table: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return the set of values shared across the given tables for a column.

    Use this for cross-species intersection questions about values present in
    all or several loaded datasets.
    Pass ``min_tables=len(tables)`` for a strict intersection; lower values
    find values present in at least N tables.

    ``namespace`` selects which axis of the AnnData to scan:
    - ``"var"`` — row-level annotations from ``.var``
    - ``"obs"`` — sample-level annotations from ``.obs``
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
        column_resolved = _resolve_column_name(
            config_manager, column, set(adata.var.columns) | set(adata.obs.columns)
        )
        # Resolve which namespace contains the column for this table.
        if ns_pref == "var" and column_resolved in adata.var.columns:
            ns = "var"
        elif ns_pref == "obs" and column_resolved in adata.obs.columns:
            ns = "obs"
        elif ns_pref == "auto":
            if column_resolved in adata.var.columns:
                ns = "var"
            elif column_resolved in adata.obs.columns:
                ns = "obs"
            else:
                continue
        else:
            continue
        series = adata.var[column_resolved] if ns == "var" else adata.obs[column_resolved]
        column = column_resolved
        per_table_namespace[code] = ns
        # Optional per-table filter pre-narrow (only for var-namespaced columns).
        vf = vf_map.get(code) or {}
        if vf and ns == "var":
            try:
                var_f, _ = apply_assistant_filters(service, adata, var_filters=vf)
                series = var_f[column_resolved] if column_resolved in var_f.columns else series.iloc[0:0]
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
        "display_name": _display_name_for(config_manager, column),
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
    config_manager=None,
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
        column = _resolve_column_name(config_manager, column, set(adata.var.columns) | set(adata.obs.columns))
        var_filters_norm = _normalize_filter_columns_for_df(config_manager, var_filters, set(adata.var.columns))
        obs_filters_norm = _normalize_filter_columns_for_df(config_manager, obs_filters, set(adata.obs.columns))
        df_full = adata.obs if namespace == "obs" else adata.var
        if column not in df_full.columns:
            per_table.append({"table": code, "error": f"column '{column}' not in .{namespace}"})
            continue
        var_f, obs_f = apply_assistant_filters(
            service, adata,
            var_filters=var_filters_norm or {},
            obs_filters=obs_filters_norm or {},
            config_manager=config_manager,
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
    config_manager=None,
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
        flat_from_payload = _deeplink_flat_filters(filters)
        if flat_from_payload and not isinstance(filters.get("filters"), dict):
            reserved = {
                key: value for key, value in filters.items()
                if key in {
                    "tags", "table_names", "datasetIdFilters", "idColumnName",
                    "filterChainColumns", "filterChainOperators", "filterChainGroups", "filterChainVersion",
                }
            }
            filters = {**reserved, "filters": flat_from_payload}
    except Exception as e:
        logger.warning("filter normalization failed: %s", e)

    try:
        filters = _normalize_deeplink_filter_columns(service, config_manager, codes, filters)
    except Exception as e:
        logger.warning("display-name filter normalization failed: %s", e)

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
    # that axis). This is what makes a sample-metadata filter work for the
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
        nested = _deeplink_flat_filters(filters)
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
        guard_counts: List[Dict[str, Any]] = []
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
                    config_manager=config_manager,
                )
            except Exception:
                cr = {}
            cr = cr if isinstance(cr, dict) else {}
            n_var = int(cr.get("n_var_match", 0))
            n_obs = int(cr.get("n_obs_match", 0))
            guard_counts.append({
                "table": code,
                "rows": n_var,
                "n_var_match": n_var,
                "n_obs_match": n_obs,
            })
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
    else:
        guard_counts = []

    limit = get_analysis_limits(config_manager).get(v, {}).get("max_rows")
    reusable_counts = guard_counts if limit is not None and guard_counts and {
        str(item.get("table")) for item in guard_counts
    } == set(codes) else []
    if reusable_counts:
        over_limit = [
            {"table": item["table"], "rows": int(item["rows"]), "max_rows": limit}
            for item in reusable_counts
            if int(item.get("rows", 0)) > int(limit)
        ]
        limit_check = {
            "ok": not over_limit,
            "view": v,
            "limit": limit,
            "over_limit": over_limit,
            "counts": [
                {"table": item["table"], "rows": int(item["rows"]), "max_rows": limit}
                for item in reusable_counts
            ],
            "suggestion": "Ask for a narrower value from an available Display Name column or another sidebar filter to reduce the result size.",
        }
        if over_limit:
            labels = ", ".join(
                f"{item['table']} ({item['rows']:,}/{int(limit):,})"
                for item in over_limit
            )
            limit_check["error"] = (
                f"{v} request exceeds the dynamic {int(limit):,} transcript limit: {labels}. "
                "Ask the user for a narrower filter before opening this analysis."
            )
    else:
        limit_check = validate_analysis_request_limits(
            service,
            config_manager,
            view=v,
            tables=codes,
            filters=filters,
        )
    if not limit_check.get("ok", True):
        return limit_check

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

    code_to_table = _species_table_lookup(service)
    route_tables = [code_to_table.get(code, code) for code in codes]

    prefix = {"heatmap": "h", "compare": "c", "phylo": "p", "ora": "o"}.get(v, "")
    if v == "catalog":
        url_path = f"/catalog?id={hash_id}"
    else:
        url_path = f"/{prefix}/{','.join(route_tables)}?id={hash_id}"
    out = {"id": hash_id, "url_path": url_path, "view": v, "tables": route_tables}
    if dropped_tables:
        out["dropped_tables"] = dropped_tables
    if warnings:
        out["warnings"] = warnings
    return out


# ---------------------------------------------------------------------------
# OpenAI tool-calling schema
# ---------------------------------------------------------------------------

_FILTER_VALUE_SCHEMA: Dict[str, Any] = {
    "oneOf": [
        {"type": "string"},
        {"type": "number"},
        {"type": "boolean"},
        {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
    ]
}

_FILTER_SPEC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "value": _FILTER_VALUE_SCHEMA,
        "values": {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
        "match_mode": {"type": "string", "enum": ["or", "and"], "default": "or"},
        "exact": {"type": "boolean", "default": True},
        "has_value": {"type": "boolean", "default": False},
    },
    "additionalProperties": False,
}

_FILTER_MAP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": {
        "oneOf": [_FILTER_VALUE_SCHEMA, _FILTER_SPEC_SCHEMA],
    },
}

_STRING_ARRAY_SCHEMA: Dict[str, Any] = {"type": "array", "items": {"type": "string"}}
_NULLABLE_STRING_ARRAY_SCHEMA: Dict[str, Any] = {
    "oneOf": [_STRING_ARRAY_SCHEMA, {"type": "null"}],
}
_ORDER_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "order": {"type": "string", "enum": ["asc", "desc"]},
    },
    "additionalProperties": False,
}
_CLUSTERING_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "clusterRows": {"type": "boolean"},
        "clusterCols": {"type": "boolean"},
        "method": {"type": "string", "enum": ["average", "complete", "ward"]},
        "distance": {"type": "string", "enum": ["correlation", "euclidean"]},
    },
    "additionalProperties": False,
}
_CUSTOM_COL_ORDER_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "enabled": {"type": "boolean"},
        "mode": {"type": "string", "enum": ["metadata", "samples"]},
        "metadataColumn": {"type": "string"},
        "metadataValues": _STRING_ARRAY_SCHEMA,
        "sampleNames": _STRING_ARRAY_SCHEMA,
    },
    "additionalProperties": False,
}
_COMPARE_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "plotType": {"type": "string", "enum": ["line", "box", "violin"]},
        "plotHeight": {"type": "integer", "minimum": 200, "maximum": 1200},
        "selectedOrthogroup": {"type": "string"},
        "selectedSpecies": _STRING_ARRAY_SCHEMA,
        "showAllTranscripts": {"type": "boolean"},
        "groupingColumn": {"type": "string"},
    },
    "additionalProperties": False,
}
_PHYLO_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "selectedOrthogroup": {"type": "string"},
        "collapsedNodes": _STRING_ARRAY_SCHEMA,
        "branchLengthMode": {"type": "string", "enum": ["cladogram", "phylogram"]},
        "groupingColumn": {"type": "string"},
    },
    "additionalProperties": False,
}

_VISUALIZATION_PATCH_PROPERTIES: Dict[str, Any] = {
    "rowLabel": {"type": "boolean"},
    "colLabel": {"type": "boolean"},
    "legend": {"type": "boolean"},
    "colorScale": {"type": "string", "enum": _COLOR_SCALES},
    "rowSideColors": _STRING_ARRAY_SCHEMA,
    "colSideColors": _STRING_ARRAY_SCHEMA,
    "tooltipFields": _NULLABLE_STRING_ARRAY_SCHEMA,
    "showSequencesInTooltip": {"type": "boolean"},
    "sequencePreviewLength": {"type": "integer", "minimum": 20, "maximum": 1000},
    "rowOrder": _ORDER_SCHEMA,
    "rowOrder.name": {"type": "string"},
    "rowOrder.order": {"type": "string", "enum": ["asc", "desc"]},
    "colOrder": _ORDER_SCHEMA,
    "colOrder.name": {"type": "string"},
    "colOrder.order": {"type": "string", "enum": ["asc", "desc"]},
    "customColOrder": _CUSTOM_COL_ORDER_PATCH_SCHEMA,
    "customColOrder.enabled": {"type": "boolean"},
    "customColOrder.mode": {"type": "string", "enum": ["metadata", "samples"]},
    "customColOrder.metadataColumn": {"type": "string"},
    "customColOrder.metadataValues": _STRING_ARRAY_SCHEMA,
    "customColOrder.sampleNames": _STRING_ARRAY_SCHEMA,
    "clustering": _CLUSTERING_PATCH_SCHEMA,
    "clustering.clusterRows": {"type": "boolean"},
    "clustering.clusterCols": {"type": "boolean"},
    "clustering.method": {"type": "string", "enum": ["average", "complete", "ward"]},
    "clustering.distance": {"type": "string", "enum": ["correlation", "euclidean"]},
    "compare": _COMPARE_PATCH_SCHEMA,
    "compare.plotType": {"type": "string", "enum": ["line", "box", "violin"]},
    "compare.plotHeight": {"type": "integer", "minimum": 200, "maximum": 1200},
    "compare.selectedOrthogroup": {"type": "string"},
    "compare.selectedSpecies": _STRING_ARRAY_SCHEMA,
    "compare.showAllTranscripts": {"type": "boolean"},
    "compare.groupingColumn": {"type": "string"},
    "phyloTree": _PHYLO_PATCH_SCHEMA,
    "phyloTree.selectedOrthogroup": {"type": "string"},
    "phyloTree.collapsedNodes": _STRING_ARRAY_SCHEMA,
    "phyloTree.branchLengthMode": {"type": "string", "enum": ["cladogram", "phylogram"]},
    "phyloTree.groupingColumn": {"type": "string"},
    "oraRowSideColor": {"type": "boolean"},
    "oraColumnName": {"type": "string"},
    "significance": {"type": "string", "enum": ["0.001", "0.01", "0.05"]},
    "oraTopN": {"type": "integer", "minimum": 1, "maximum": 500},
    "oraMinCount": {"type": "integer", "minimum": 1, "maximum": 50},
    "oraGoDepthFilter": {"oneOf": [{"type": "integer", "minimum": 0}, {"type": "string"}]},
    "oraTooltipFields": {"type": "array", "items": {"type": "string", "enum": _ORA_TOOLTIP_FIELDS}},
    "oraOrder": _ORDER_SCHEMA,
    "oraOrder.name": {"type": "string", "enum": ["attr", "subset_count", "background_count", "gene_ratio", "fold_enrichment", "p_value"]},
    "oraOrder.order": {"type": "string", "enum": ["asc", "desc"]},
}

_VISUALIZATION_PATCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "description": (
        "Tool Specification: shallow visualization-store patch for controls "
        "that already exist in the manual UI. Strict Property Schemas: each "
        "property below declares its exact JSON type, enum, and numeric bounds. "
        "Validation Rules: row/.var metadata is accepted only by row settings "
        "(rowSideColors, rowOrder, tooltip/ORA columns), while sample/.obs "
        "metadata is accepted only by column/sample settings (colSideColors, "
        "colOrder, groupingColumn, customColOrder.metadataColumn). Call "
        "list_view_settings first for the instance-specific column options."
    ),
    "properties": _VISUALIZATION_PATCH_PROPERTIES,
    "additionalProperties": False,
}

_VIEW_STATE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "tags": {"type": "array", "items": {"type": "string"}},
        "table_names": {"type": "array", "items": {"type": "string"}},
        "filters": _FILTER_MAP_SCHEMA,
        "datasetIdFilters": _FILTER_MAP_SCHEMA,
        "filterChainColumns": {"type": "array", "items": {"type": "string"}},
        "filterChainOperators": {"type": "object", "additionalProperties": {"type": "string", "enum": ["and", "or"]}},
        "filterChainGroups": {"type": "object", "additionalProperties": True},
    },
    "additionalProperties": False,
}

_ACTION_BLOCK_SCHEMAS: Dict[str, Any] = {
    "add_filter": {
        "type": "object",
        "properties": {
            "column": {"type": "string", "minLength": 1},
            "value": _FILTER_VALUE_SCHEMA,
            "values": {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
            "match_mode": {"type": "string", "enum": ["or", "and"], "default": "or"},
            "exact": {"type": "boolean", "default": True},
            "has_value": {"type": "boolean", "default": False},
        },
        "required": ["column"],
        "additionalProperties": False,
    },
    "remove_filter": {
        "type": "object",
        "properties": {"column": {"type": "string", "minLength": 1}},
        "required": ["column"],
        "additionalProperties": False,
    },
    "clear_filters": {"type": "object", "properties": {}, "additionalProperties": False},
    "select_tables": {
        "type": "object",
        "properties": {"tables": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1}},
        "required": ["tables"],
        "additionalProperties": False,
    },
    "set_expression_display": {
        "type": "object",
        "properties": {
            "optionId": {"type": "string", "enum": [o["id"] for o in _EXPRESSION_OPTIONS]},
            "layer": {"type": ["string", "null"], "enum": ["tpm", "tmm", "getmm", "X", None]},
            "transform": {"type": "string", "enum": ["raw", "log2", "zscore"]},
        },
        "required": ["optionId", "transform"],
        "additionalProperties": False,
    },
    "set_filter_chain": {
        "type": "object",
        "properties": {
            "columns": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 2},
            "operator": {"type": "string", "enum": ["and", "or"]},
        },
        "required": ["columns", "operator"],
        "additionalProperties": False,
    },
    "viz_update": {
        "type": "object",
        "properties": {"patch": _VISUALIZATION_PATCH_SCHEMA},
        "required": ["patch"],
        "additionalProperties": False,
    },
    "deeplink": {
        "type": "object",
        "properties": {
            "view": {"type": "string", "enum": ["heatmap", "compare", "phylo", "ora", "catalog"]},
            "tables": {"type": "array", "items": {"type": "string"}},
            "filters": _VIEW_STATE_SCHEMA,
            "visualizations": {"type": "object", "additionalProperties": True},
        },
        "required": ["view", "tables"],
        "additionalProperties": False,
    },
}

_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "state_summary",
            "description": (
                "Return a cached high-level summary of this GenXBrowser "
                "instance: dataset IDs/labels, species names, structural "
                ".var/.obs columns, and fresh display-name mappings. Prefer "
                "this for initial routing; call list_schema only when column "
                "dtypes or per-table details are needed."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_schema",
            "description": (
                "List loaded tables with dynamic row/sample metadata fields, "
                "display labels, dtypes, layers, and compact top categorical "
                "values. Use display labels for prose and internal keys for "
                "tool/action payloads."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_values_per_col": {"type": "integer", "default": 5, "minimum": 0, "maximum": 20},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_view_state",
            "description": (
                "Return the live frontend dataset-card state for this turn: "
                "all loaded dataset IDs/labels/aliases, which dataset cards "
                "are currently visible, and which loaded datasets are hidden. "
                "Call this before any add/remove/show-only/show-all dataset "
                "visibility command. Resolve user shortcuts only against the "
                "returned runtime labels and aliases."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_dataset_visibility",
            "description": (
                "Validate and compose a frontend dataset_visibility action. "
                "Use only dataset_ids returned by get_active_view_state. "
                "HIDE removes visible dataset cards, SHOW_ONLY keeps only "
                "the specified cards, SHOW_ALL renders all loaded datasets, "
                "and ADD appends hidden loaded datasets back into the view."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["SHOW_ONLY", "HIDE", "SHOW_ALL", "ADD"]},
                    "dataset_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["action", "dataset_ids"],
                "additionalProperties": False,
            },
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
                "Find which dynamic metadata field contains a free-form term. "
                "Returns ranked hits with table, namespace, internal column, "
                "Display Name, exact value, and occurrence count. Use before "
                "proposing an add_filter when the column/value is not already "
                "verified."
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
            "name": "search_go_terms",
            "description": (
                "MANDATORY for any user request that mentions a "
                "Gene-Ontology concept by NAME (English or any other "
                "language) — e.g. 'flower development', 'photosynthesis', "
                "'Photosynthese', 'Blütenentwicklung', 'DNA binding', "
                "'cell wall biosynthesis'. The dataset's `go_terms` "
                "column stores `GO:#######` IDs only, never process "
                "names, so neither `resolve_value` nor "
                "`list_distinct_values` on ordinary metadata columns "
                "can resolve such a query. "
                "This tool maps the natural-language name to canonical "
                "GO IDs via the loaded GO OBO ontology and (by default) "
                "only returns IDs that are actually annotated in this "
                "dataset, so the very next step can be `add_filter` on "
                "`go_terms` + `build_deeplink`. ALWAYS try this BEFORE "
                "concluding that no GO match exists. If it returns "
                "`available:false`, only then may you say the ontology "
                "is not loaded."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language GO term name or fragment.",
                    },
                    "limit": {
                        "type": "integer", "default": 20,
                        "minimum": 1, "maximum": 100,
                    },
                    "only_in_dataset": {
                        "type": "boolean", "default": True,
                        "description": (
                            "If true (default), restrict to GO IDs present "
                            "in the dataset's go_terms column. Set false to "
                            "also include ontology terms not annotated in "
                            "any loaded table."
                        ),
                    },
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
                "Rank values in a dynamic row-metadata column after applying "
                "row filters. Handles separator-delimited multi-value cells. "
                "Pass `tables` as an array to aggregate across tables in one "
                "call and use returned coverage fields for cross-table claims."
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
                "Return values shared by multiple tables for a dynamic "
                "metadata column. The column may live in row metadata or "
                "sample metadata; set `namespace` or leave `auto`. Result "
                "includes compact per-table distinct values and total shared "
                "count."
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
                "and `visualizations` use the frontend store shape. The tool "
                "validates dynamic per-view row limits and returns an error "
                "with `over_limit` instead of a URL when filters are required."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {"type": "string", "enum": ["heatmap", "compare", "phylo", "ora", "catalog"]},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "filters": _VIEW_STATE_SCHEMA,
                    "visualizations": _VISUALIZATION_PATCH_SCHEMA,
                },
                "required": ["view", "tables"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_available_datasets",
            "description": (
                "GAIA discovery step 1. List the species/datasets currently "
                "loaded (identity + shape only, no expression values). Call "
                "this first to learn which datasets exist before planning."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dataset_schema",
            "description": (
                "GAIA discovery step 2. Return the `.obs` (sample metadata "
                "columns + categorical levels / numeric ranges) and `.var` "
                "(gene metadata columns) layout for the loaded datasets, "
                "without any raw expression values. Pass `species_id` to scope "
                "to one dataset. This is the ONLY sanctioned way to verify a "
                "column or category exists before emitting any filter, color "
                "group, annotation, or visualization setting."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "species_id": {
                        "type": "string",
                        "description": "Optional table_name / code / species name to scope the schema.",
                    },
                    "max_values_per_col": {"type": "integer", "default": 5},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dispatch_frontend_action",
            "description": (
                "GAIA execution step. Instruct the Vue frontend state manager "
                "to perform ONE UI mutation, exactly as a human user could. "
                "`action_type` MUST be one of: add_filter, remove_filter, "
                "clear_filters, select_tables, set_expression_display, "
                "set_filter_chain, viz_update, deeplink, dataset_visibility, "
                "phylo_action. `payload` is that action block's object. Only "
                "dispatch actions whose columns/values you have verified via "
                "get_dataset_schema. The backend converts this into the "
                "matching action block; never invent unverified payloads."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": [
                            "add_filter", "remove_filter", "clear_filters",
                            "select_tables", "set_expression_display",
                            "set_filter_chain", "viz_update", "deeplink",
                            "dataset_visibility", "phylo_action",
                        ],
                    },
                    "payload": {"type": "object", "additionalProperties": True},
                },
                "required": ["action_type", "payload"],
            },
        },
    },
]


def openai_schema() -> List[Dict[str, Any]]:
    """Return the tool definitions in OpenAI tool-calling shape."""
    # Return a deep copy so callers can't mutate the shared list.
    return json.loads(json.dumps(_TOOL_SCHEMAS))


def _get_dispatch():
    def _tool_args(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in kwargs.items() if k != "client_context"}

    return {
        "state_summary": lambda service, cm, **kw: tool_state_summary(service, cm),
        "get_available_datasets": lambda service, cm, **kw: tool_get_available_datasets(service, cm),
        "list_schema": lambda service, cm, **kw: tool_list_schema(service, cm, **_tool_args(kw)),
        "get_dataset_schema": lambda service, cm, **kw: tool_get_dataset_schema(service, cm, **_tool_args(kw)),
        "get_active_view_state": lambda service, cm, **kw: tool_get_active_view_state(service, client_context=kw.get("client_context")),
        "update_dataset_visibility": lambda service, cm, **kw: tool_update_dataset_visibility(service, **_tool_args(kw), client_context=kw.get("client_context")),
        "list_view_settings": lambda service, cm, **kw: tool_list_view_settings(service, cm, **_tool_args(kw)),
        "resolve_value": lambda service, cm, **kw: tool_resolve_value(service, cm, **_tool_args(kw)),
        "search_go_terms": lambda service, cm, **kw: tool_search_go_terms(service, **_tool_args(kw)),
        "list_distinct_values": lambda service, cm, **kw: tool_list_distinct_values(service, cm, **_tool_args(kw)),
        "count_rows": lambda service, cm, **kw: tool_count_rows(service, cm, **_tool_args(kw)),
        "top_groups": lambda service, cm, **kw: tool_top_groups(service, cm, **_tool_args(kw)),
        "summary_stats": lambda service, cm, **kw: tool_summary_stats(service, cm, **_tool_args(kw)),
        "common_values": lambda service, cm, **kw: tool_common_values(service, cm, **_tool_args(kw)),
        "build_deeplink": lambda service, cm, **kw: tool_build_deeplink(service, cm, **_tool_args(kw)),
    }


def dispatch_tool_call(
    name: str,
    arguments: Dict[str, Any],
    *,
    service,
    config_manager,
    client_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Dispatch a single tool call; never raises."""
    dispatch = _get_dispatch()
    fn = dispatch.get(name)
    if fn is None:
        return {"error": f"unknown tool '{name}'", "available": sorted(dispatch.keys())}
    logger.info("assistant tool dispatch: %s args=%s", name, arguments)
    try:
        call_args = dict(arguments or {})
        call_args["client_context"] = client_context if isinstance(client_context, dict) else {}
        result = fn(service, config_manager, **call_args)
    except TypeError as e:
        return {"error": f"bad arguments: {e}"}
    except Exception as e:  # noqa: BLE001 — the LLM gets the error and can retry.
        logger.warning("tool %s failed: %s", name, e, exc_info=True)
        return {"error": f"{type(e).__name__}: {e}"}
    if isinstance(result, dict):
        keys = sorted(result.keys())[:6]
        logger.info("assistant tool result: %s keys=%s", name, keys)
    return result
