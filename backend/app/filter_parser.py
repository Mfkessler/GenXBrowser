"""Pure-Python filter spec parser shared by the HTTP API and the AI assistant.

The HTTP routes (:mod:`app.routes`) and the assistant tools
(:mod:`app.assistant_tools`) both need to translate the user-facing filter
grammar — a flexible mapping ``{column: value | list | dict}`` — into the
internal ``(operator, value)`` tuples that :class:`DataService._apply_filters`
understands. Keeping that translation in one Flask-free helper guarantees the
two code paths agree on semantics (most importantly ``match_mode`` and
``exact``), which is what makes assistant-reported counts match what filters
actually do in the UI.

This module has no Flask, no DataService, and no DuckDB dependency on import,
so it can be loaded standalone (e.g. by the test loader).
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

ALLOWED_TYPES = frozenset({"text", "array", "bigint", "double precision", "boolean"})

GoTermExpander = Callable[[str, List[str], bool], Tuple[List[str], bool]]


def _parse_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        val = value.strip().lower()
        if val in {"true", "t"}:
            return True
        if val in {"false", "f"}:
            return False
    return None


def _parse_value(val: Any) -> Any:
    bval = _parse_bool(val)
    if isinstance(bval, bool):
        return bval
    if isinstance(val, str):
        return [v.strip() for v in val.split("|") if v.strip()]
    return val


def _resolve_match_options(spec: Any) -> Tuple[str, bool]:
    """Resolve ``(match_mode, exact)`` from a filter dict, with defaults."""
    if not isinstance(spec, dict):
        return "or", True
    mode_raw = spec.get("match_mode")
    if isinstance(mode_raw, str) and mode_raw.lower() in ("and", "or"):
        mode = mode_raw.lower()
    else:
        mode = "or"
    exact_raw = spec.get("exact")
    exact = exact_raw if isinstance(exact_raw, bool) else True
    return mode, exact


def _text_op_for(values: List[Any], mode: str, exact: bool) -> Optional[Tuple[str, Any]]:
    if not values:
        return None
    if exact:
        return ("in", values) if len(values) > 1 else ("eq", values[0])
    if len(values) == 1:
        return ("text_substr_any", values)
    return ("text_substr_all", values) if mode == "and" else ("text_substr_any", values)


def _array_op_for(values: List[Any], mode: str, exact: bool) -> Optional[Tuple[str, Any]]:
    if not values:
        return None
    if exact:
        return ("array_contains", values) if mode == "and" else ("array_overlap", values)
    return ("array_substr_all", values) if mode == "and" else ("array_substr_any", values)


def parse_filter_query(
    filters: Optional[Dict[str, Any]],
    allowed_columns: Dict[str, str],
    *,
    go_term_expander: Optional[GoTermExpander] = None,
) -> Dict[str, Tuple[str, Any]]:
    """Translate user-facing filter specs into ``(op, value)`` tuples.

    Parameters
    ----------
    filters:
        Mapping ``{column: value | list | {value, match_mode, exact} | …}``.
        Unknown columns are silently skipped (the catalog and the LLM may
        legitimately disagree on which columns exist for a given table).
    allowed_columns:
        Pre-built ``{column: type}`` map. ``type`` must be one of
        :data:`ALLOWED_TYPES`; entries with other types are ignored.
    go_term_expander:
        Optional callable ``(column, values, exact) -> (values, exact)``.
        When set and the column is a GO-term array column, term names are
        expanded to GO IDs. ``parse_filters`` in :mod:`app.routes` wires this
        to the live ``go_service`` from the Flask app.
    """
    if not filters:
        return {}

    # Defensive copy + lower-case the type strings.
    allowed = {
        k: str(v).lower() for k, v in (allowed_columns or {}).items()
        if str(v).lower() in ALLOWED_TYPES
    }

    def _maybe_expand(col_key: str, values: List[Any], exact: bool):
        if go_term_expander is None:
            return values, exact
        try:
            return go_term_expander(col_key, list(values), exact)
        except Exception as exc:  # noqa: BLE001
            logger.warning("go_term_expander failed for %s: %s", col_key, exc)
            return values, exact

    out: Dict[str, Tuple[str, Any]] = {}
    for key, value in filters.items():
        col_type = allowed.get(key)
        if not col_type:
            continue
        if value is None:
            continue

        # Direct boolean.
        if isinstance(value, bool) and col_type == "boolean":
            out[key] = ("eq", value)
            continue

        # Direct list/array.
        if isinstance(value, list):
            values = value
            if col_type == "array":
                out[key] = ("array_overlap", values)
            elif col_type == "text":
                out[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type in ("bigint", "integer", "double precision") and len(values) == 2:
                try:
                    num1 = float(values[0]) if col_type == "double precision" else int(values[0])
                    num2 = float(values[1]) if col_type == "double precision" else int(values[1])
                    if num2 > num1:
                        out[key] = ("range", (num1, num2))
                except (ValueError, TypeError):
                    pass
            continue

        # Direct string.
        if isinstance(value, str):
            values = _parse_value(value)
            if col_type == "text":
                if not values:
                    continue
                out[key] = ("in", values) if len(values) > 1 else ("eq", values[0])
            elif col_type == "boolean":
                out[key] = ("eq", values)
            elif col_type == "array":
                out[key] = ("array_overlap", values)
            continue

        # Dict with "value" key.
        if isinstance(value, dict) and "value" in value:
            values = _parse_value(value["value"])
            if values is None or values == [] or values == "":
                continue
            mode, exact = _resolve_match_options(value)
            if col_type == "text":
                op = _text_op_for(values, mode, exact)
                if op is not None:
                    out[key] = op
            elif col_type == "array":
                values, exact = _maybe_expand(key, values, exact)
                op = _array_op_for(values, mode, exact)
                if op is not None:
                    out[key] = op
            elif col_type in ("bigint", "integer"):
                if not isinstance(values, list) or len(values) != 2:
                    continue
                try:
                    num1, num2 = int(values[0]), int(values[1])
                    if num2 > num1:
                        out[key] = ("range", (num1, num2))
                except ValueError:
                    continue
            elif col_type == "double precision":
                if not isinstance(values, list) or len(values) != 2:
                    continue
                try:
                    num1, num2 = float(values[0]), float(values[1])
                    if num2 > num1:
                        out[key] = ("range", (num1, num2))
                except ValueError:
                    continue
            elif col_type == "boolean":
                out[key] = ("eq", values)
            continue

        # Dict with "type" + "values" keys (newer wire format).
        if isinstance(value, dict) and "type" in value and "values" in value:
            col_type_from_filter = str(value["type"]).lower()
            values = value["values"]
            if not isinstance(values, list):
                values = [values]
            mode, exact = _resolve_match_options(value)
            if col_type_from_filter == "array":
                values, exact = _maybe_expand(key, values, exact)
                op = _array_op_for(values, mode, exact)
                if op is not None:
                    out[key] = op
            elif col_type_from_filter == "text":
                op = _text_op_for(values, mode, exact)
                if op is not None:
                    out[key] = op
            elif col_type_from_filter in ("bigint", "integer", "double precision"):
                if len(values) == 2:
                    try:
                        num1 = float(values[0]) if col_type_from_filter == "double precision" else int(values[0])
                        num2 = float(values[1]) if col_type_from_filter == "double precision" else int(values[1])
                        if num2 > num1:
                            out[key] = ("range", (num1, num2))
                    except (ValueError, TypeError):
                        continue
            elif col_type_from_filter == "boolean":
                out[key] = ("eq", values[0] if values else False)
            continue

        # Dict fallback (other keys, e.g. ``{value, match_mode}`` without ``value``).
        if isinstance(value, dict):
            values = _parse_value(value.get("value", ""))
            mode, exact = _resolve_match_options(value)
            if col_type == "text":
                op = _text_op_for(values, mode, exact)
                if op is not None:
                    out[key] = op
            elif col_type == "array":
                values, exact = _maybe_expand(key, values, exact)
                op = _array_op_for(values, mode, exact)
                if op is not None:
                    out[key] = op
            elif col_type == "boolean":
                out[key] = ("eq", values)

    return out


def infer_dataframe_column_types(df) -> Dict[str, str]:
    """Map a pandas DataFrame's columns to the catalog type vocabulary.

    Used by the assistant tools so AnnData ``.var`` / ``.obs`` frames can be
    filtered with the same grammar the catalog supports. ``array`` is
    detected by sniffing for any cell containing one of the canonical
    separators (``,|;``).
    """
    import pandas as pd  # local import — backend startup cost
    import re as _re

    out: Dict[str, str] = {}
    for col in df.columns:
        s = df[col]
        dtype = s.dtype
        if pd.api.types.is_bool_dtype(dtype):
            out[col] = "boolean"
            continue
        if pd.api.types.is_integer_dtype(dtype):
            out[col] = "bigint"
            continue
        if pd.api.types.is_float_dtype(dtype):
            out[col] = "double precision"
            continue
        try:
            sample = s.dropna().astype(str)
            if len(sample) > 50:
                sample = sample.sample(50, random_state=0)
            if any(_re.search(r"[,|;]", v) for v in sample):
                out[col] = "array"
                continue
        except Exception:
            pass
        out[col] = "text"
    return out


# ----------------------------------------------------------------------------
# Filter application
# ----------------------------------------------------------------------------

def apply_filter_query(
    df,
    filter_query: Dict[str, Tuple[str, Any]],
    *,
    column_separators: Optional[Dict[str, str]] = None,
):
    """Apply ``parse_filter_query`` output to a DataFrame.

    Mirrors the semantics of :meth:`DataService._apply_filters` but is fully
    self-contained — no DataService, no Flask, no DuckDB. The HTTP path keeps
    using the service method (which has extra column-name remapping for the
    catalog); the assistant tools fall back to this helper when their
    DataService stand-in lacks the method (unit tests) or when called
    against a plain AnnData frame.
    """
    if not filter_query or df is None or len(df) == 0:
        return df

    import pandas as pd  # local — backend startup cost
    import re as _re

    column_separators = column_separators or {}
    result = df

    for col, spec in filter_query.items():
        if col not in result.columns:
            return result.iloc[0:0]
        if spec is None:
            continue
        op, value = spec
        s = result[col]

        if op == "eq":
            if isinstance(value, bool):
                result = result[s == value]
            else:
                result = result[s.astype(str).str.strip() == str(value).strip()]
        elif op == "in":
            target = {str(v).strip() for v in (value or [])}
            result = result[s.astype(str).str.strip().isin(target)]
        elif op == "range":
            lo, hi = value
            num = pd.to_numeric(s, errors="coerce")
            result = result[(num >= lo) & (num <= hi)]
        elif op in ("text_substr_any", "text_substr_all"):
            if not isinstance(value, list):
                value = [value]
            if not value:
                continue
            lowered = s.astype(str).str.lower()
            masks = [lowered.str.contains(_re.escape(str(v).lower()), regex=True, na=False) for v in value]
            combined = masks[0].copy()
            for m in masks[1:]:
                combined = (combined & m) if op == "text_substr_all" else (combined | m)
            result = result[combined]
        elif op in ("array_overlap", "array_contains", "array_substr_any", "array_substr_all"):
            sep = column_separators.get(col)
            if sep is None:
                sep = "|" if col.lower().endswith("desc") else ","

            def _check(x, _sep=sep, _op=op, _value=value):
                if isinstance(x, (list, tuple)):
                    items = [str(it) for it in x]
                elif hasattr(x, "tolist"):  # numpy array
                    items = [str(it) for it in x.tolist()]
                elif isinstance(x, str) and x:
                    items = [it.strip() for it in x.split(_sep) if it.strip()]
                else:
                    return False
                if _op == "array_overlap":
                    return any(v in items for v in _value)
                if _op == "array_contains":
                    return all(v in items for v in _value)
                items_lc = [str(it).lower() for it in items]
                if _op == "array_substr_any":
                    return any(any(str(v).lower() in it for it in items_lc) for v in _value)
                return all(any(str(v).lower() in it for it in items_lc) for v in _value)

            result = result[s.apply(_check)]

    return result

