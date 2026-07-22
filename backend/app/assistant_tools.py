"""GAIA's native tools and their shared data engine."""

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


def _column_separator(config_manager, column: str, series=None) -> str:
    spec = _column_definitions(config_manager).get(column) or {}
    if isinstance(spec, dict) and (spec.get("is_array") or spec.get("type") == "array"):
        configured = spec.get("array_separator")
        if configured in {",", "|", ";"}:
            return str(configured)
        if series is not None:
            try:
                values = series.dropna().astype(str)
                for candidate in ("|", ";"):
                    if values.str.contains(candidate, regex=False).any():
                        return candidate
            except Exception:
                pass
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
        return _split_array_values(series, (_column_separator(config_manager, column, series),))
    return [str(v).strip() for v in series.dropna().astype(str) if str(v).strip()]


def _column_separators_for(config_manager, frame) -> Dict[str, str]:
    return {
        str(col): _column_separator(config_manager, str(col), frame[col])
        for col in frame.columns
        if _column_type_from_config(config_manager, str(col)) == "array"
    }


def normalize_filter_pipe_value(value: Any) -> Optional[str]:
    """Normalize a filter ``value`` field to the pipe-separated form the
    frontend filter store and TextFilter component expect.

        Structured JSON arrays become multiple frontend chips. Scalar strings
        remain scalar because punctuation can be part of a legitimate metadata
        value. ``None`` and the empty string are passed through unchanged.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        items = [str(v).strip() for v in value]
    else:
        s = str(value)
        return s
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

    Unknown keys are passed through untouched.
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
            cr = _count_rows(
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


def _apply_filters(
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
            logger.warning("_apply_filters: filter_parser unavailable")
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
                    column_separators=_column_separators_for(config_manager, var_df),
                )
        except Exception as e:
            logger.warning("_apply_filters(var) failed: %s", e, exc_info=True)
    if obs_filters:
        try:
            allowed = obs_column_types or filter_parser.infer_dataframe_column_types(obs_df)
            obs_query = filter_parser.parse_filter_query(obs_filters, allowed)
            if obs_query:
                obs_df = filter_parser.apply_filter_query(
                    obs_df,
                    obs_query,
                    column_separators=_column_separators_for(config_manager, obs_df),
                )
        except Exception as e:
            logger.warning("_apply_filters(obs) failed: %s", e, exc_info=True)
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
# ``_search_values`` call. The Counter is the dominant cost there;
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


def _build_schema(service, cm, *, max_values_per_col: int = 5) -> Dict[str, Any]:
    """Build the visible instance schema used by ``INSTANCE_MANIFEST``."""
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

    return {"tables": tables}



# Static catalog of expression-display options. The frontend mirror lives at
# `frontend/src/shared/ExpressionDisplay.ts` — keep these two in sync. The
# tool below filters this list per instance based on which `.layers` are
# actually present in the loaded H5AD files, so the assistant never picks
# an option whose backing layer doesn't exist on this deployment.
_EXPRESSION_OPTIONS: List[Dict[str, Any]] = [
    {"id": "tpm",       "label": "TPM (within-sample)",            "layer": "tpm",    "transform": "raw"},
    {"id": "tmm",       "label": "TMM (between-sample)",           "layer": "tmm",    "transform": "raw"},
    {"id": "getmm",     "label": "GeTMM (gene-length corrected)",  "layer": "getmm",  "transform": "raw"},
    {"id": "log2",      "label": "Log\u2082 (automatic layer)",     "layer": None,     "transform": "log2"},
    {"id": "zscore",    "label": "Z-Score (automatic layer)",       "layer": None,     "transform": "zscore"},
    {"id": "zscore-tpm","label": "Z-Score (on TPM)",               "layer": "tpm",    "transform": "zscore"},
    {"id": "raw",       "label": "Raw Counts",                     "layer": "X",      "transform": "raw"},
]

_TRIGGER_ACTIONS = [
    "export_png", "export_pdf", "export_svg",
    "export_tsv", "export_csv", "export_xlsx", "export_json",
    "open_data_manager", "open_export_modal",
    "reset_view", "expand_all", "collapse_all", "collapse_to_species",
]

# Per-view static descriptors of viz controls beyond the expression display.
# Values are filled in dynamically by `_view_settings` based on the
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
         "note": "Compare stores its expression selection under compare.expression."},
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


def _view_settings(
    service,
    config_manager=None,
    *,
    view: str,
    tables: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Return the available visualization settings for ``view`` on this
    GenXBrowser instance, with valid value spaces resolved against the
    loaded data.

    Settings like expression display depend on which layers are loaded.

    Returns:
        {
          "view": "<view>",
          "tables_considered": [...],
          "expression_options": [{id,label,layer,transform,available,reason}],
          "controls": [{key,type,...,options?,note?}, ...],
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
    def _curated_meta_options(
        sample_metadata: bool,
        *,
        collapse_default_trait: bool = True,
    ) -> Tuple[set, Dict[str, str]]:
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
                frame = adata.obs if sample_metadata else adata.var
                cols = [
                    {
                        "column_name": str(name),
                        "display_name": _display_name_for(config_manager, str(name)),
                    }
                    for name in frame.columns
                    if _column_is_filterable(config_manager, str(name))
                ]
            names: set = set()
            for col in cols:
                cname = str(col.get("column_name") or "")
                if not cname:
                    continue
                # Collapse the default-trait source column into the pseudo key
                # the store/UI uses, so the assistant emits the same value a
                # human checkbox click would produce.
                key = "default_trait" if collapse_default_trait and col.get("is_default_trait") else cname
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
    grouping_obs, grouping_obs_details = _curated_meta_options(
        sample_metadata=True,
        collapse_default_trait=False,
    )
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
            if c.get("key") in {"compare.groupingColumn", "phyloTree.groupingColumn"}:
                c["options"] = sorted(grouping_obs)
                c["option_details"] = _curated_option_details(grouping_obs, grouping_obs_details)
            else:
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
        elif ctype == "expression_display":
            available_expression = [
                option for option in expression_options if option.get("available") is True
            ]
            c["options"] = [str(option["id"]) for option in available_expression]
            c["option_details"] = [
                {"name": str(option["id"]), "display_name": str(option["label"])}
                for option in available_expression
            ]
        if c.get("key") == "oraTooltipFields":
            c["options"] = _ORA_TOOLTIP_FIELDS
        controls_out.append(c)

    return {
        "view": v,
        "tables_considered": codes,
        "expression_options": expression_options,
        "controls": controls_out,
        "available_layers": sorted(common_layers),
    }



def _search_values(
    service,
    config_manager=None,
    *,
    query: str,
    column: Optional[str] = None,
    tables: Optional[List[str]] = None,
    max_hits: int = 10,
) -> Dict[str, Any]:
    """Find which column(s) contain a free-form user term.

    Returns ranked hits ``{table, column, value, count, match}``. Used by the
    Used by ``search_metadata`` so it never guesses the column.

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
            frame = adata.var if ns_name == "var" else adata.obs
            resolved_column = _resolve_column_name(config_manager, column, set(frame.columns)) if column else None
            if column and resolved_column not in frame.columns:
                counters = []
            elif resolved_column:
                targeted = _column_value_counter(frame[resolved_column], resolved_column, config_manager)
                counters = [(resolved_column, targeted)] if targeted is not None else []
            else:
                counters = _get_value_counters(adata, code, ns_name, mtime, config_manager)
            searched_columns = {str(col) for col, _counter in counters}
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

            # High-cardinality/free-text columns are deliberately omitted from
            # the reusable substring counters, but exact values remain valid
            # filter targets. Scan only those omitted, visible columns and only
            # for equality, keeping broad free-text search bounded.
            for col in frame.columns:
                internal = str(col)
                if column and internal != resolved_column:
                    continue
                if internal in searched_columns or not _column_is_filterable(config_manager, internal):
                    continue
                if not any(part in internal.lower() for part in _RESOLVE_SKIP_COL_SUBSTR):
                    continue
                raw_values = frame[col].dropna().astype(str).str.strip()
                raw_exact = raw_values[raw_values.str.lower() == q_lower]
                if not raw_exact.empty:
                    exact_value = str(raw_exact.iloc[0])
                    hits.append({
                        "table": code, "namespace": ns_name, "column": internal,
                        "display_name": _display_name_for(config_manager, internal),
                        "value": exact_value, "count": int(raw_exact.size), "match": "exact",
                    })
                    continue
                counter = _column_value_counter(frame[col], internal, config_manager)
                if counter is None:
                    continue
                exact_value = next((value for value in counter if value.lower() == q_lower), None)
                if exact_value is not None:
                    hits.append({
                        "table": code, "namespace": ns_name, "column": internal,
                        "display_name": _display_name_for(config_manager, internal),
                        "value": exact_value, "count": counter[exact_value], "match": "exact",
                    })

    # Prefer exact matches, then higher counts.
    hits.sort(key=lambda h: (0 if h["match"] == "exact" else 1, -h["count"]))
    return {"query": query, "hits": hits[: int(max_hits)]}



def _count_rows(
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

    try:
        from . import filter_parser  # noqa: WPS433
    except ImportError:  # pragma: no cover - tests use spec loader
        import importlib.util as _ilu
        from pathlib import Path as _Path
        _spec = _ilu.spec_from_file_location(
            "_gx_filter_parser_count_fallback",
            _Path(__file__).resolve().parent / "filter_parser.py",
        )
        if not (_spec and _spec.loader):
            return {"error": "filter parser unavailable"}
        filter_parser = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(filter_parser)  # type: ignore[union-attr]

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
        var_types = _cached_filter_column_types(
            service, adata, code, "var", list(var_filters_norm.keys()), config_manager,
        ) if var_filters_norm else {}
        obs_types = _cached_filter_column_types(
            service, adata, code, "obs", list(obs_filters_norm.keys()), config_manager,
        ) if obs_filters_norm else {}
        var_query = filter_parser.parse_filter_query(var_filters_norm, var_types) if var_filters_norm else {}
        obs_query = filter_parser.parse_filter_query(obs_filters_norm, obs_types) if obs_filters_norm else {}
        try:
            n_var = int(service.get_row_count(code, var_query)) if var_query else int(adata.n_vars)
        except Exception:
            var_f, _ = _apply_filters(
                service, adata, var_filters=var_filters_norm,
                var_column_types=var_types or None, config_manager=config_manager,
            )
            n_var = int(len(var_f))
        try:
            allowed_samples = service._filter_samples(adata, obs_query) if obs_query else None
            n_obs = int(len(allowed_samples)) if allowed_samples is not None else int(adata.n_obs)
        except Exception:
            _, obs_f = _apply_filters(
                service, adata, obs_filters=obs_filters_norm,
                obs_column_types=obs_types or None, config_manager=config_manager,
            )
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


def _rank_values(
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
        var_f, _ = _apply_filters(
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



def _summary_stats(
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
        var_f, obs_f = _apply_filters(
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


def _build_navigation(
    service,
    config_manager=None,
    *,
    view: str,
    tables: List[str],
    filters: Optional[Dict[str, Any]] = None,
    visualizations: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate, persist, and route a complete GAIA view state."""
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
        # Keep complete filter specs so validation uses the exact same parser
        # semantics as the frontend, including has_value and numeric ranges.
        flat_filters: Dict[str, Any] = {}
        for col, spec in nested.items():
            if not isinstance(spec, dict):
                continue
            flat_filters[col] = spec

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
                cr = _count_rows(
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
# Unified assistant contract
# ---------------------------------------------------------------------------

def build_instance_manifest(service, config_manager=None) -> Dict[str, Any]:
    """Build static capabilities injected into every assistant request."""
    schema = _build_schema(service, config_manager, max_values_per_col=0)
    datasets: List[Dict[str, Any]] = []
    columns: Dict[str, Dict[str, Dict[str, Any]]] = {"var": {}, "obs": {}}
    for table in schema.get("tables") or []:
        dataset_id = table.get("table_name") or table.get("code")
        if dataset_id:
            datasets.append({
                "id": dataset_id,
                "code": table.get("code"),
                "label": table.get("display_label") or table.get("full_name") or dataset_id,
                "layers": table.get("layers") or [],
            })
        for namespace, key in (("var", "var_columns"), ("obs", "obs_columns")):
            for column in table.get(key) or []:
                name = column.get("name")
                if name:
                    columns[namespace][name] = {
                        "key": name,
                        "label": column.get("display_name") or name,
                        "type": column.get("column_type") or column.get("dtype") or "text",
                        "array_separator": column.get("array_separator"),
                    }
    views: Dict[str, Any] = {}
    for view in ("heatmap", "compare", "phylo", "ora", "catalog"):
        settings = _view_settings(service, config_manager, view=view, tables=None)
        views[view] = {
            "controls": [
                {key: value for key, value in control.items() if key in {"key", "type", "options", "min", "max"}}
                for control in settings.get("controls") or []
            ],
            "expression_options": [
                option["id"] for option in settings.get("expression_options") or []
                if option.get("available")
            ],
            "trigger_actions": [
                *_TRIGGER_ACTIONS,
            ],
        }
    return {
        "datasets": datasets,
        "columns": {namespace: sorted(items.values(), key=lambda item: item["key"])
                    for namespace, items in columns.items()},
        "views": views,
    }


def _get_go_service():
    """Return the application-scoped ontology service when Flask is active."""
    try:
        from flask import current_app  # noqa: WPS433
        return getattr(current_app, "go_service", None)
    except Exception:
        return None


def _go_columns(adata, requested_column: Optional[str]) -> List[str]:
    """Return GO annotation columns, optionally constrained by the caller."""
    requested = str(requested_column or "").strip().lower()
    columns = [str(name) for name in adata.var.columns]
    if requested:
        return [name for name in columns if name.lower() == requested]
    return [name for name in columns if re.search(r"(^|_)(go|gene_ontology)(_|$)", name.lower())]


def _visible_assistant_columns(service, config_manager, codes: List[str]) -> Dict[str, str]:
    """Return visible/filterable internal keys and their var/obs namespaces."""
    definitions = _column_definitions(config_manager)
    configured = {
        str(name) for name, spec in definitions.items()
        if _column_is_filterable(config_manager, str(name), spec if isinstance(spec, dict) else None)
    }
    strict = bool(definitions)
    visible: Dict[str, str] = {}
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        for namespace, frame in (("var", adata.var), ("obs", adata.obs)):
            for name in frame.columns:
                key = str(name)
                if (not strict or key in configured) and _column_is_filterable(config_manager, key):
                    visible.setdefault(key, namespace)
    return visible


def _resolve_visible_column(config_manager, raw: str, visible: Dict[str, str]) -> Optional[str]:
    resolved = _resolve_column_name(config_manager, str(raw), set(visible))
    return resolved if resolved in visible else None


def tool_search_metadata(service, config_manager=None, *, query: str,
                         column: Optional[str] = None, tables: Optional[List[str]] = None,
                         limit: int = 20) -> Dict[str, Any]:
    """Find verified metadata values and resolve GO descriptions to GO IDs."""
    if not str(query or "").strip():
        return {"error": "query is required"}
    query_key = re.sub(r"[^a-z0-9]", "", str(query).lower())
    control_hits: List[Dict[str, Any]] = []
    for candidate_view in ("heatmap", "compare", "phylo", "ora"):
        settings = _view_settings(
            service, config_manager, view=candidate_view, tables=tables,
        )
        for control in settings.get("controls") or []:
            if not isinstance(control, dict):
                continue
            key = str(control.get("key") or "")
            key_normalized = re.sub(r"[^a-z0-9]", "", key.lower())
            option_keys = {
                re.sub(r"[^a-z0-9]", "", str(option).lower())
                for option in control.get("options") or []
            }
            option_keys.update(
                re.sub(r"[^a-z0-9]", "", str(detail.get("display_name") or "").lower())
                for detail in control.get("option_details") or []
                if isinstance(detail, dict)
            )
            if (
                query_key == key_normalized
                or query_key in option_keys
                or (len(query_key) >= 8 and query_key in key_normalized)
            ):
                control_hits.append({
                    "view": candidate_view,
                    "key": key,
                    "type": control.get("type"),
                    "options": control.get("options") or [],
                })
    if control_hits:
        return {
            "status": "ui_control",
            "query": query,
            "controls": control_hits,
            "next_tool": "build_state_token",
            "instruction": "This term names visualization controls, not metadata. Apply the requested UI change with build_state_token and do not search it as a data value.",
        }
    result = _search_values(
        service, config_manager, query=query, column=column, tables=tables, max_hits=limit,
    )
    codes = _resolve_species_codes(service, tables)
    visible = _visible_assistant_columns(service, config_manager, codes)
    result["hits"] = [
        hit for hit in result.get("hits") or []
        if hit.get("column") in visible
        and visible[hit["column"]] == hit.get("namespace")
    ]
    query_lower = str(query).strip().lower()
    column_hits: List[Dict[str, Any]] = []
    go_columns: List[Tuple[str, str]] = []
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        if adata is not None:
            for namespace, frame in (("var", adata.var), ("obs", adata.obs)):
                for name in frame.columns:
                    internal = str(name)
                    if internal not in visible or visible[internal] != namespace:
                        continue
                    display_name = _display_name_for(config_manager, internal)
                    if query_lower in {internal.lower(), display_name.lower()}:
                        column_hits.append({
                            "table": code,
                            "namespace": namespace,
                            "column": internal,
                            "display_name": display_name,
                            "value": None,
                            "match": "column",
                        })
            go_columns.extend(
                (code, name) for name in _go_columns(adata, column)
                if name in visible and visible[name] == "var"
            )

    if column_hits:
        result["hits"] = column_hits + (result.get("hits") or [])

    is_go_query = bool(re.fullmatch(r"GO:\d{7}", str(query).strip(), re.I))
    if go_columns or is_go_query:
        go_service = _get_go_service()
        if go_service and getattr(go_service, "is_available", lambda: False)():
            try:
                ontology_hits = go_service.search_terms(query, limit=max(1, min(int(limit), 100))) or []
            except Exception as exc:  # noqa: BLE001
                logger.warning("search_metadata GO resolution failed: %s", exc)
                ontology_hits = []
            existing = {(hit.get("column"), hit.get("value")) for hit in result.get("hits") or []}
            for ontology_hit in ontology_hits:
                go_id = ontology_hit.get("id") if isinstance(ontology_hit, dict) else None
                if not go_id:
                    continue
                for code, go_column in go_columns:
                    key = (go_column, go_id)
                    if key in existing:
                        continue
                    result.setdefault("hits", []).append({
                        "table": code,
                        "namespace": "var",
                        "column": go_column,
                        "display_name": _display_name_for(config_manager, go_column),
                        "value": go_id,
                        "label": ontology_hit.get("name"),
                        "description": ontology_hit.get("definition"),
                        "match": "ontology",
                    })
                    existing.add(key)
    if column:
        resolved_column = _resolve_visible_column(config_manager, column, visible)
        if resolved_column is None:
            return {
                "status": "unavailable",
                "error": f"Metadata attribute '{column}' is not available in the active instance schema.",
            }
        requested = resolved_column.lower()
        result["hits"] = [
            hit for hit in result.get("hits") or []
            if str(hit.get("column") or "").lower() == requested
            or str(hit.get("display_name") or "").lower() == requested
        ]
    result["hits"] = result.get("hits", [])[:max(1, min(int(limit), 100))]
    if not result["hits"]:
        result["status"] = "not_found"
    return result


def _split_assistant_filters(
    service,
    config_manager,
    codes: List[str],
    filters: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Resolve flat or explicit axis filter maps for unified assistant tools."""
    source = filters if isinstance(filters, dict) else {}
    explicit_var = source.get("var_filters") if isinstance(source.get("var_filters"), dict) else {}
    explicit_obs = source.get("obs_filters") if isinstance(source.get("obs_filters"), dict) else {}
    flat = _deeplink_flat_filters(source) or source.get("global") or source
    if "var_filters" in source or "obs_filters" in source:
        flat = {
            name: value for name, value in flat.items()
            if name not in {"var_filters", "obs_filters"}
        }

    def _clean(spec: Any) -> Any:
        if not isinstance(spec, dict):
            cleaned = {"value": spec}
            if isinstance(spec, (str, list)):
                cleaned["exact"] = True
            return cleaned
        cleaned = dict(spec)
        value = cleaned.get("value", cleaned.get("values"))
        has_concrete_value = value is not None and value != "" and value != []
        if has_concrete_value:
            cleaned.pop("has_value", None)
            if isinstance(value, (str, list)):
                cleaned.setdefault("exact", True)
        return cleaned

    var_filters = {key: _clean(spec) for key, spec in explicit_var.items()}
    obs_filters = {key: _clean(spec) for key, spec in explicit_obs.items()}
    for code in codes:
        try:
            adata = service.registry.load(code)
        except Exception:
            continue
        known = set(adata.var.columns) | set(adata.obs.columns)
        for name, value in flat.items():
            resolved = _resolve_column_name(config_manager, str(name), known)
            if resolved in adata.var.columns:
                var_filters[resolved] = _clean(value)
            elif resolved in adata.obs.columns:
                obs_filters[resolved] = _clean(value)
    return var_filters, obs_filters


def _validate_unified_columns(
    service,
    config_manager,
    codes: List[str],
    var_filters: Dict[str, Any],
    obs_filters: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    visible = _visible_assistant_columns(service, config_manager, codes)
    normalized_var: Dict[str, Any] = {}
    normalized_obs: Dict[str, Any] = {}
    unavailable: List[str] = []
    for namespace, source, target in (
        ("var", var_filters, normalized_var), ("obs", obs_filters, normalized_obs),
    ):
        for raw, spec in source.items():
            resolved = _resolve_visible_column(config_manager, str(raw), visible)
            if resolved is None or visible.get(resolved) != namespace:
                unavailable.append(str(raw))
            else:
                target[resolved] = spec
    return normalized_var, normalized_obs, sorted(set(unavailable))


def _compile_local_dataset_chains(
    service,
    config_manager,
    codes: List[str],
    chains: Any,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str]]:
    """Compile payload-friendly local rules into the Vue filter-store shape."""
    if not isinstance(chains, dict):
        return {}, {}, []
    visible = _visible_assistant_columns(service, config_manager, codes)
    code_to_table = _species_table_lookup(service)
    table_lookup: Dict[str, str] = {}
    for code in codes:
        table_name = code_to_table.get(code, code)
        table_lookup[code.lower()] = table_name
        table_lookup[table_name.lower()] = table_name
    local_states: Dict[str, Any] = {}
    local_filters: Dict[str, Any] = {}
    unavailable: List[str] = []
    for raw_table, chain in chains.items():
        table_name = table_lookup.get(str(raw_table).strip().lower())
        if table_name is None or not isinstance(chain, dict):
            unavailable.append(str(raw_table))
            continue
        operator = "or" if str(chain.get("operator") or "and").lower() == "or" else "and"
        columns: List[str] = []
        custom: Dict[str, Any] = {}
        nots: Dict[str, bool] = {}
        for index, rule in enumerate(chain.get("rules") or []):
            if not isinstance(rule, dict):
                continue
            resolved = _resolve_visible_column(config_manager, str(rule.get("column") or ""), visible)
            if resolved is None:
                unavailable.append(str(rule.get("column") or ""))
                continue
            key = f"{resolved}::chain::gaia-{index}"
            filter_spec = {
                name: value for name, value in rule.items()
                if name in {"value", "values", "match_mode", "exact", "has_value"}
            }
            if "values" in filter_spec and "value" not in filter_spec:
                filter_spec["value"] = filter_spec.pop("values")
            columns.append(key)
            custom[key] = {"column": resolved, "filter": filter_spec}
            if rule.get("isNot") is True:
                nots[key] = True
        operators = {
            "::".join(sorted((left, right))): operator
            for left, right in zip(columns, columns[1:])
        }
        local_states[table_name] = {
            "columns": columns, "operators": operators, "groups": {},
            "nots": nots, "disabled": {},
        }
        local_filters[table_name] = custom
    return local_states, local_filters, sorted(set(unavailable))


def _active_filter_state(client_context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    context = client_context if isinstance(client_context, dict) else {}
    state = context.get("filters")
    return dict(state) if isinstance(state, dict) else {}


def _live_view_and_tables(client_context: Optional[Dict[str, Any]]) -> Tuple[str, List[str]]:
    context = client_context if isinstance(client_context, dict) else {}
    raw_view = str(context.get("view") or context.get("route") or "").lower()
    if "heatmap" in raw_view or "/h/" in raw_view:
        view = "heatmap"
    elif "compare" in raw_view or "/c/" in raw_view:
        view = "compare"
    elif "phylo" in raw_view or "/p/" in raw_view:
        view = "phylo"
    elif "ora" in raw_view or "/o/" in raw_view:
        view = "ora"
    else:
        view = "catalog"
    tables: List[str] = []
    for candidate in (
        context.get("tables"), context.get("selected_table_names"),
        (_active_filter_state(context).get("table_names")),
    ):
        if isinstance(candidate, list) and candidate:
            tables = [str(item) for item in candidate if str(item).strip()]
            break
    return view, tables


def tool_get_current_view(*, client_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Return the authoritative read-only UI snapshot for grounded explanations."""
    context = client_context if isinstance(client_context, dict) else {}
    view, tables = _live_view_and_tables(context)
    live_visualizations = context.get("visualizations") if isinstance(context.get("visualizations"), dict) else {}
    visualizations: Dict[str, Any] = {}
    for control in _VIEW_CONTROLS.get(view, []):
        key = str(control.get("key") or "")
        value: Any = live_visualizations
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value is not None:
            visualizations[key] = value
    return {
        "view": view,
        "route": str(context.get("route") or ""),
        "tables": tables,
        "filters": _active_filter_state(context),
        "visualizations": visualizations,
        "analysis_results": context.get("analysis_results") if isinstance(context.get("analysis_results"), dict) else {},
        "dataset_state": context.get("active_view_state") if isinstance(context.get("active_view_state"), dict) else {},
    }


def _prepare_viz_patches(
    service,
    config_manager,
    view: str,
    tables: List[str],
    patches: Optional[Dict[str, Any]],
    client_context: Optional[Dict[str, Any]],
    replace_lists: bool,
) -> Tuple[Dict[str, Any], Optional[str]]:
    requested_patches = dict(patches) if isinstance(patches, dict) else {}
    live = client_context.get("visualizations") if isinstance(client_context, dict) else {}
    live = live if isinstance(live, dict) else {}
    settings = _view_settings(service, config_manager, view=view, tables=tables)
    if settings.get("error"):
        return {}, str(settings["error"])
    controls = {
        str(control.get("key")): control
        for control in settings.get("controls") or [] if isinstance(control, dict)
    }

    def _flatten(source: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        flattened: Dict[str, Any] = {}
        for raw_key, value in source.items():
            key = f"{prefix}.{raw_key}" if prefix else str(raw_key)
            if isinstance(value, dict) and key not in controls:
                flattened.update(_flatten(value, key))
            else:
                flattened[key] = value
        return flattened

    def _live_value(path: str) -> Any:
        value: Any = live
        for part in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(part)
        return value

    expression_options = {
        str(option.get("id")): option
        for option in settings.get("expression_options") or []
        if isinstance(option, dict)
    }
    prepared: Dict[str, Any] = {}
    for key, value in _flatten(requested_patches).items():
        control = controls.get(key)
        if control is None:
            return {}, f"Unsupported visualization control for {view}: {key}"
        if control.get("type") == "expression_display":
            option = expression_options.get(str(value))
            if option is None or option.get("available") is not True:
                return {}, f"Unsupported {key} option for the active datasets: {value}"
            prepared[key] = str(value)
            continue

        options = [str(option) for option in control.get("options") or []]
        if options:
            aliases: Dict[str, str] = {option.lower(): option for option in options}
            for detail in control.get("option_details") or []:
                if not isinstance(detail, dict) or not detail.get("name"):
                    continue
                internal = str(detail["name"])
                aliases[internal.lower()] = internal
                if detail.get("display_name"):
                    aliases[str(detail["display_name"]).lower()] = internal

            def _resolve(raw: Any) -> Optional[str]:
                if raw == "*":
                    return "*"
                return aliases.get(str(raw).lower())

            if isinstance(value, list):
                resolved = [_resolve(item) for item in value]
                invalid = [str(raw) for raw, item in zip(value, resolved) if item is None]
                if invalid:
                    return {}, f"Unsupported {key} option(s) for the active datasets: {', '.join(invalid)}"
                value = [item for item in resolved if item is not None]
            else:
                resolved_value = _resolve(value)
                if resolved_value is None:
                    return {}, f"Unsupported {key} option for the active datasets: {value}"
                value = resolved_value

        if isinstance(value, list) and not replace_lists and "*" not in value:
            current = _live_value(key)
            current = current if isinstance(current, list) else []
            value = list(dict.fromkeys([*current, *value]))
        prepared[key] = value
    return prepared, None


def tool_compute_analytics(service, config_manager=None, *, operation: str,
                           tables: Optional[List[str]] = None,
                           filters: Optional[Dict[str, Any]] = None,
                           target_column: Optional[str] = None) -> Dict[str, Any]:
    """Count, rank, or summarize metadata using one filter payload."""
    operation = str(operation or "").lower()
    source = filters if isinstance(filters, dict) else {}
    codes = _resolve_species_codes(service, tables)
    if not codes:
        return {"error": "tables must name at least one loaded dataset"}
    var_filters, obs_filters = _split_assistant_filters(service, config_manager, codes, source)
    var_filters, obs_filters, unavailable = _validate_unified_columns(
        service, config_manager, codes, var_filters, obs_filters,
    )
    if unavailable:
        return {"error": "Metadata attribute(s) not available in the active instance schema: " + ", ".join(unavailable)}
    visible = _visible_assistant_columns(service, config_manager, codes)
    resolved_target = _resolve_visible_column(config_manager, target_column, visible) if target_column else None
    if target_column and resolved_target is None:
        return {"error": f"Metadata attribute '{target_column}' is not available in the active instance schema."}
    if operation == "count":
        return _count_rows(service, config_manager, tables=tables, var_filters=var_filters, obs_filters=obs_filters)
    if operation == "rank":
        if not target_column:
            return {"error": "target_column is required for rank"}
        if visible.get(resolved_target) != "var":
            return {"error": "rank target_column must be a visible transcript/gene metadata column"}
        result = _rank_values(service, config_manager, tables=tables, group_column=resolved_target, var_filters=var_filters)
        rankings = result.get("top") if isinstance(result, dict) else None
        if not isinstance(rankings, list):
            return result
        top = rankings[0] if rankings else {}
        return {
            **result,
            "top_value": top.get("value") if isinstance(top, dict) else None,
            "count": top.get("count") if isinstance(top, dict) else 0,
            "rankings": rankings,
        }
    if operation == "stats":
        if not target_column:
            return {"error": "target_column is required for stats"}
        return _summary_stats(service, config_manager, tables=tables, column=resolved_target,
                      namespace=visible[resolved_target], var_filters=var_filters, obs_filters=obs_filters)
    return {"error": "operation must be count, rank, or stats"}


def tool_build_state_token(service, config_manager=None, *, view: str,
                           tables: Optional[List[str]] = None,
                           filters: Optional[Dict[str, Any]] = None,
                           viz_patches: Optional[Dict[str, Any]] = None,
                           trigger_actions: Optional[List[str]] = None,
                           replace_viz_lists: bool = False,
                           client_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate a complete target state and return one frontend state token."""
    raw_filters = dict(filters) if isinstance(filters, dict) else {}
    actions = [str(item) for item in (trigger_actions or []) if str(item)]
    supported_actions = set(_TRIGGER_ACTIONS)
    invalid = sorted(set(actions) - supported_actions)
    if invalid:
        return {"error": "unsupported trigger action(s): " + ", ".join(invalid)}
    live_view, live_tables = _live_view_and_tables(client_context)
    requested_tables = list(tables or live_tables)
    codes = _resolve_species_codes(service, requested_tables)
    if not codes:
        return {"error": "tables must name at least one loaded dataset"}
    var_filters, obs_filters = _split_assistant_filters(service, config_manager, codes, raw_filters)
    var_filters, obs_filters, unavailable = _validate_unified_columns(
        service, config_manager, codes, var_filters, obs_filters,
    )
    local_states, local_custom, local_unavailable = _compile_local_dataset_chains(
        service, config_manager, codes, raw_filters.get("local_dataset_chains"),
    )
    unavailable.extend(local_unavailable)
    if unavailable:
        return {"error": "Metadata attribute(s) not available in the active instance schema: " + ", ".join(sorted(set(unavailable)))}

    prepared_viz, viz_error = _prepare_viz_patches(
        service, config_manager, str(view or "").lower(), requested_tables,
        viz_patches, client_context, replace_viz_lists,
    )
    if viz_error:
        return {"error": viz_error}

    preserve = raw_filters.get("clear_existing") is not True
    active_filters = _active_filter_state(client_context)
    state_filters = active_filters if preserve else {
        "tags": [],
        "table_names": active_filters.get("table_names", []),
        "filters": {},
        "datasetIdFilters": {},
        "filterChainColumns": [],
        "filterChainOperators": {},
        "filterChainGroups": {},
        "filterChainNots": {},
        "localDatasetChains": {},
        "localCustomFilters": {},
    }
    if active_filters.get("idColumnName"):
        state_filters["idColumnName"] = active_filters["idColumnName"]
    existing_flat = state_filters.get("filters") if isinstance(state_filters.get("filters"), dict) else {}
    state_filters["filters"] = {**existing_flat, **var_filters, **obs_filters}
    if local_states:
        existing_local = state_filters.get("localDatasetChains") if isinstance(state_filters.get("localDatasetChains"), dict) else {}
        existing_custom = state_filters.get("localCustomFilters") if isinstance(state_filters.get("localCustomFilters"), dict) else {}
        state_filters["localDatasetChains"] = {**existing_local, **local_states}
        state_filters["localCustomFilters"] = {**existing_custom, **local_custom}
    live_codes = _resolve_species_codes(service, live_tables)
    in_place = live_view == str(view or "").lower() and set(live_codes) == set(codes)
    if in_place:
        live_filter_state = _active_filter_state(client_context)
        if state_filters == live_filter_state and not prepared_viz and not actions:
            return {
                "error": (
                    "No UI state change was supplied. Provide a non-empty viz_patches, "
                    "filter change, or trigger_actions payload; do not claim success."
                ),
                "no_op": True,
            }
        code_to_table = _species_table_lookup(service)
        return {"ok": True, "state_token": {
            "view": str(view or "").lower(),
            "tables": [code_to_table.get(code, code) for code in codes],
            "filters": state_filters,
            "viz_patches": prepared_viz,
            "trigger_actions": actions,
            "url_path": "",
        }}
    deeplink = _build_navigation(
        service, config_manager, view=view, tables=requested_tables,
        filters={"filters": state_filters["filters"]},
        visualizations=prepared_viz,
    )
    if deeplink.get("error"):
        # A sample-only filter is a valid in-place Sidebar update even when
        # opening/reloading the current view would exceed its transcript cap.
        # Return a token without navigation so the frontend applies the filter
        # rather than falsely reporting that the metadata column is unusable.
        if deeplink.get("over_limit") and obs_filters and not var_filters:
            code_to_table = _species_table_lookup(service)
            return {"ok": True, "state_token": {
                "view": str(view or "").lower(),
                "tables": [code_to_table.get(code, code) for code in codes],
                "filters": state_filters,
                "viz_patches": prepared_viz,
                "trigger_actions": actions,
                "url_path": "",
            }}
        return deeplink
    return {"ok": True, "state_token": {
        "view": deeplink["view"], "tables": deeplink["tables"],
        "filters": state_filters,
        "viz_patches": prepared_viz,
        "trigger_actions": actions, "url_path": deeplink["url_path"],
    }}


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
        "isNot": {"type": "boolean", "default": False},
    },
    "additionalProperties": False,
}

_FILTER_MAP_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": {
        "oneOf": [_FILTER_VALUE_SCHEMA, _FILTER_SPEC_SCHEMA],
    },
}

_UNIFIED_FILTERS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "description": (
        "Complete filter state. Use var_filters for transcript/gene (.var) metadata "
        "and obs_filters for sample (.obs) metadata. Both support "
        "{column: {has_value: true}}. Frontend-shaped {filters: {...}} and "
        "flat column maps are also accepted."
    ),
    "properties": {
        "var_filters": _FILTER_MAP_SCHEMA,
        "obs_filters": _FILTER_MAP_SCHEMA,
        "filters": _FILTER_MAP_SCHEMA,
        "local_dataset_chains": {
            "type": "object",
            "description": "Dataset-local AND/OR chains keyed by full dataset name.",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "operator": {"type": "string", "enum": ["AND", "OR", "and", "or"]},
                    "rules": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "value": _FILTER_VALUE_SCHEMA,
                                "values": {"type": "array", "items": {"type": ["string", "number", "boolean"]}},
                                "match_mode": {"type": "string", "enum": ["or", "and"]},
                                "exact": {"type": "boolean"},
                                "has_value": {"type": "boolean"},
                                "isNot": {"type": "boolean"},
                            },
                            "required": ["column"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["operator", "rules"],
                "additionalProperties": False,
            },
        },
        "clear_existing": {
            "type": "boolean",
            "description": "Set true only when the user explicitly asks to clear existing filters.",
        },
    },
    "additionalProperties": False,
}

_STATE_FILTERS_SCHEMA: Dict[str, Any] = {
    **_UNIFIED_FILTERS_SCHEMA,
    "description": (
        "Filter changes for this state update. Omit this argument for visualization-only "
        "requests so LIVE_UI_STATE filters remain unchanged. Supplied filters are merged "
        "with live state unless clear_existing is true."
    ),
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
        "expression": {"type": "string", "enum": [option["id"] for option in _EXPRESSION_OPTIONS]},
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
    "expressionDisplay": {"type": "string", "enum": [option["id"] for option in _EXPRESSION_OPTIONS]},
    "rowLabel": {"type": "boolean"},
    "colLabel": {"type": "boolean"},
    "legend": {"type": "boolean"},
    "colorScale": {"type": "string", "enum": _COLOR_SCALES},
    "rowSideColors": {
        "type": "array", "items": {"type": "string"},
        "description": "Visible transcript/.var annotation keys; ['*'] selects all eligible RowSideColors.",
    },
    "colSideColors": {
        "type": "array", "items": {"type": "string"},
        "description": "Visible sample/.obs annotation keys; ['*'] selects all eligible ColSideColors.",
    },
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
    "compare.expression": {"type": "string", "enum": [option["id"] for option in _EXPRESSION_OPTIONS]},
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


_TOOL_SCHEMAS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_current_view",
            "description": "Read the authoritative current UI view, datasets, filters, visualization settings, and available analysis results. Use this before explaining the current view. This tool never changes state.",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_metadata",
            "description": "Find a non-empty biological/metadata term and its verified internal key. Never use this tool to select visualization controls such as SideColors; those are declared in INSTANCE_MANIFEST and applied with build_state_token.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "column": {"type": "string"},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compute_analytics",
            "description": "Compute count, rank, or numeric stats after applying the supplied filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {"type": "string", "enum": ["count", "rank", "stats"]},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "filters": _STATE_FILTERS_SCHEMA,
                    "target_column": {"type": "string"},
                },
                "required": ["operation", "tables", "filters"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_state_token",
            "description": "Validate and apply navigation, filters, or visualization controls. For Heatmap SideColors use rowSideColors (.var) and colSideColors (.obs); ['*'] selects all eligible options.",
            "parameters": {
                "type": "object",
                "properties": {
                    "view": {"type": "string", "enum": ["heatmap", "compare", "phylo", "ora", "catalog"]},
                    "tables": {"type": "array", "items": {"type": "string"}},
                    "filters": _UNIFIED_FILTERS_SCHEMA,
                    "viz_patches": _VISUALIZATION_PATCH_SCHEMA,
                    "replace_viz_lists": {
                        "type": "boolean",
                        "description": "False/default merges list controls with LIVE_UI_STATE; true explicitly replaces them.",
                    },
                    "trigger_actions": {"type": "array", "items": {"type": "string", "enum": _TRIGGER_ACTIONS}},
                },
                "required": ["view", "tables"],
                "additionalProperties": False,
            },
        },
    },
]


def openai_schema() -> List[Dict[str, Any]]:
    """Return the modern unified tool definitions."""
    return json.loads(json.dumps(_TOOL_SCHEMAS))


def _get_dispatch():
    def _tool_args(kwargs: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in kwargs.items() if k != "client_context"}

    return {
        "get_current_view": lambda service, cm, **kw: tool_get_current_view(
            client_context=kw.get("client_context"),
        ),
        "search_metadata": lambda service, cm, **kw: tool_search_metadata(service, cm, **_tool_args(kw)),
        "compute_analytics": lambda service, cm, **kw: tool_compute_analytics(service, cm, **_tool_args(kw)),
        "build_state_token": lambda service, cm, **kw: tool_build_state_token(service, cm, **kw),
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
