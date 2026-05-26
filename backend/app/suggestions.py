"""Dynamic prompt suggestions for the AI assistant.

Generates short, dataset-grounded example prompts that the user can click in
the assistant panel. All sampled values come from the actually-loaded H5AD
files and all column labels use the active frontend Display Names.

Public surface:
- :func:`build_suggestion_pool` — collect candidate values once per dataset
  state (cached on the service registry mtime).
- :func:`generate_suggestions` — sample a small set of templates against the
  current pool and return formatted prompt strings.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# Template registry. Each entry declares the slots it needs so the generator
# can skip templates whose pool is empty for the current dataset.
# ``slots`` items are keys into the pool dict built by build_suggestion_pool.
_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "summary",
        "view": "other",
        "slots": ["species"],
        "text": "Summarize the {species} dataset.",
    },
    {
        "id": "shared_row_values",
        "view": "compare",
        "slots": ["row_trait"],
        "text": "Which {row_trait_label} values are shared across all loaded species?",
    },
]


# Module-level cache: a single (mtime, pool) tuple. The mtime probe is cheap
# (already used by /api/overview/mtime) so we re-validate on every request
# and rebuild only when the dataset state actually changed.
_POOL_CACHE: Dict[str, Any] = {"mtime": None, "pool": None, "built_at": 0.0}
_BANK_CACHE: Dict[str, Any] = {"mtime": None, "items": None, "built_at": 0.0}


def _safe_mtime(service, cm) -> Optional[float]:
    try:
        from .overview import _overview_mtime
        mtime = float(_overview_mtime(service, cm))
        overlay_path = getattr(service, "_custom_overlays_path", None)
        if overlay_path and os.path.exists(str(overlay_path)):
            mtime = max(mtime, os.path.getmtime(str(overlay_path)))
        return round(mtime, 3)
    except Exception:  # pragma: no cover — defensive
        return None


def build_suggestion_pool(service, cm) -> Dict[str, List[str]]:
    """Collect candidate values from the live dataset.

    Returns a dict with species plus generic row/sample metadata slots.
    Empty lists are fine — the generator filters templates accordingly.
    """
    mtime = _safe_mtime(service, cm)
    cached = _POOL_CACHE.get("pool")
    if cached is not None and _POOL_CACHE.get("mtime") == mtime:
        return cached

    species: List[str] = []
    species_labels: Dict[str, str] = {}
    sample_traits: List[Dict[str, str]] = []
    row_traits: List[Dict[str, str]] = []
    tree_values: List[str] = []

    try:
        entries = service.get_tables(include_disabled=False)
    except Exception as e:
        logger.warning("suggestion pool: get_tables failed: %s", e)
        entries = []

    seen_sample_trait: set = set()
    # Generic slots harvested from all values of eligible categorical columns.
    # Each entry: {"namespace": "var"|"obs", "column": str, "value": str,
    # "table": species_code}. The generator turns these into generic
    # "filter by X" templates so deployments with arbitrary schemas still
    # produce meaningful suggestions.
    discovered: List[Dict[str, str]] = []
    seen_disc: set = set()
    # Skip columns with these prefixes/exact names — they're never useful as
    # filter slot fillers (free text, ids, scores, paths, ...).
    _BLOCKED_TEXT_COL_SUBSTR = (
        "description", "desc", "name", "path", "score", "pvalue", "p_value",
        "padj", "ensembl", "uniprot", "gene_symbol", "transcript", "gene_id",
    )

    def _uns_value(adata, key: str) -> str:
        try:
            uns = getattr(adata, "uns", {}) or {}
            return str(uns.get(key) or "").strip()
        except Exception:
            return ""

    def _species_display_label(entry, adata, code: str) -> str:
        species_name = _uns_value(adata, "species") if adata is not None else ""
        dataset_name = _uns_value(adata, "name") if adata is not None else ""
        if species_name and dataset_name and species_name.lower() != dataset_name.lower():
            return f"{species_name} ({dataset_name})"
        if species_name:
            return species_name
        if dataset_name:
            return dataset_name
        return str(entry.get("full_name") or entry.get("display_name") or entry.get("table_name") or code)

    def _display_name(col: str) -> str:
        try:
            defs = cm.get_column_definitions() or {}
            spec = defs.get(col) or {}
            return str(spec.get("display_name") or col)
        except Exception:
            return col

    def _column_spec(col: str) -> Dict[str, Any]:
        try:
            defs = cm.get_column_definitions() or {}
            spec = defs.get(col) or {}
            return spec if isinstance(spec, dict) else {}
        except Exception:
            return {}

    def _hidden_columns() -> set:
        try:
            config = cm.get_config() or {}
            frontend = config.get("frontend_settings") or {}
            return {str(item) for item in (frontend.get("hidden_columns") or [])}
        except Exception:
            return set()

    def _is_filterable(col: str) -> bool:
        spec = _column_spec(col)
        if col in _hidden_columns():
            return False
        if spec.get("visible") is False or spec.get("filterable") is False:
            return False
        return True

    def _column_type(col: str, series=None) -> str:
        spec = _column_spec(col)
        raw = str(spec.get("type") or "").lower()
        if spec.get("is_array") or raw == "array":
            return "array"
        if raw in {"text", "bigint", "double precision", "boolean"}:
            return raw
        dtype = str(getattr(series, "dtype", "")).lower()
        if dtype.startswith("float"):
            return "double precision"
        if dtype.startswith("int"):
            return "bigint"
        if dtype.startswith("bool"):
            return "boolean"
        return "text"

    def _array_separator(col: str) -> str:
        sep = str(_column_spec(col).get("array_separator") or ",")
        return sep if sep in {",", "|", ";"} else ","

    def _all_values(col: str, series) -> List[str]:
        col_type = _column_type(col, series)
        if col_type in {"bigint", "double precision", "boolean"}:
            return []
        if col_type == "array":
            values: List[str] = []
            sep = _array_separator(col)
            for raw in series.dropna().astype(str):
                values.extend(part.strip() for part in raw.split(sep) if part.strip())
            if not values:
                return []
            return sorted(set(values), key=lambda value: value.lower())
        return sorted(set(series.dropna().astype(str)), key=lambda value: value.lower())

    def _has_expression_for_samples(adata, mask) -> bool:
        try:
            if not bool(mask.any()):
                return False
            x = getattr(adata, "X", None)
            if x is None:
                return True
            mask_arr = mask.to_numpy() if hasattr(mask, "to_numpy") else mask
            subset = x[mask_arr, :]
            if hasattr(subset, "nnz"):
                return bool(subset.nnz > 0)
            arr = np.asarray(subset)
            if arr.size > 200000:
                arr = arr[:, : max(1, int(200000 / max(1, arr.shape[0])))]
            return bool(arr.size and np.isfinite(arr).any())
        except Exception:
            return True

    def _harvest(adata, code: str, df, namespace: str):
        for col in df.columns:
            col = str(col)
            if not _is_filterable(col):
                continue
            lc = col.lower()
            try:
                s = df[col].dropna()
                if s.empty:
                    continue
                col_type = _column_type(col, s)
                if col_type in {"bigint", "double precision", "boolean"}:
                    continue
                if col_type != "array" and any(b in lc for b in _BLOCKED_TEXT_COL_SUBSTR):
                    continue
                values = _all_values(col, s)
                if len(set(values)) <= 1:
                    continue
                for val in values:
                    if not val or len(val) > 80:
                        continue
                    key = (namespace, col, val)
                    if key in seen_disc:
                        continue
                    seen_disc.add(key)
                    slot = {
                        "namespace": namespace, "column": col,
                        "display_name": _display_name(str(col)),
                        "value": val, "table": code,
                        "table_label": species_labels.get(str(code), str(code)),
                        "column_type": col_type,
                    }
                    if slot["column_type"] == "array":
                        slot["array_separator"] = _array_separator(col)
                    discovered.append(slot)
            except Exception:
                continue

    for entry in entries:
        code = entry.get("_species_code") or entry.get("code")
        if not code:
            continue
        try:
            adata = service.registry.load(code)
        except Exception:
            adata = None
        species.append(str(code))
        species_labels[str(code)] = _species_display_label(entry, adata, str(code))
        if adata is None:
            continue
        # Sample traits from any eligible string/categorical obs column.
        try:
            for col in adata.obs.columns:
                col = str(col)
                if not _is_filterable(col):
                    continue
                series = adata.obs[col].dropna()
                if series.empty:
                    continue
                if _column_type(col, series) in {"bigint", "double precision", "boolean"}:
                    continue
                values = _all_values(col, series)
                if len(set(values)) <= 1:
                    continue
                for v in values:
                    if not v or len(str(v)) > 60:
                        continue
                    mask = adata.obs[col].astype(str) == str(v)
                    if not _has_expression_for_samples(adata, mask):
                        continue
                    key = (col, str(v))
                    if key in seen_sample_trait:
                        continue
                    seen_sample_trait.add(key)
                    sample_traits.append({
                        "column": str(col),
                        "display_name": _display_name(str(col)),
                        "value": str(v),
                        "table": str(code),
                        "table_label": species_labels.get(str(code), str(code)),
                    })
        except Exception:
            pass
        # Generic schema-driven harvest from all eligible values. Prompt token
        # size stays small because only sampled suggestions are returned.
        try:
            _harvest(adata, str(code), adata.var, "var")
            _harvest(adata, str(code), adata.obs, "obs")
        except Exception:
            pass

    tree_store = getattr(service, "gene_trees", None) or getattr(service, "gene_tree_store", None)
    if tree_store is not None:
        for slot in discovered:
            if slot.get("namespace") != "var":
                continue
            value = str(slot.get("value") or "")
            if not value or value in tree_values:
                continue
            try:
                if tree_store.get(value):
                    tree_values.append(value)
            except Exception:
                pass

    seen_row_trait: set = set()
    for slot in discovered:
        if slot.get("namespace") != "var":
            continue
        col = slot.get("column", "")
        if not col or col in seen_row_trait:
            continue
        seen_row_trait.add(col)
        row_traits.append({"column": col, "display_name": _display_name(col)})

    pool = {
        "species": species,
        "species_labels": species_labels,
        "sample_trait": sample_traits,
        "row_trait": row_traits,
        "tree_value": tree_values,
        "discovered": discovered,
    }
    _POOL_CACHE["pool"] = pool
    _POOL_CACHE["mtime"] = mtime
    _POOL_CACHE["built_at"] = time.time()
    return pool


def _eligible_templates(pool: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for tpl in _TEMPLATES:
        if all(pool.get(slot) for slot in tpl["slots"]):
            out.append(tpl)
    return out


# Generic templates rendered against any (column, value) pair harvested from
# the live schema. They keep suggestions useful on deployments whose H5AD
# files use deployment-specific column keys and Display Names.
_GENERIC_TEMPLATE_TEXTS: List[str] = [
    "Show {table}: how many {namespace_label} have {display_name} = {value}?",
    "Filter {table} to {namespace_label} where {display_name} is {value} and summarize.",
    "List the most common values of {display_name} in {table}.",
]

_GENERIC_VIEW_TEMPLATES: Dict[str, List[str]] = {
    "heatmap": [
        "Open a heatmap for {table} where {display_name} is {value}.",
        "Create a heatmap for {table} where {display_name} is {value}.",
        "Open a heatmap for {table} where {display_name} is {value}.",
    ],
    "ora": [
        "Run ORA on {table} for rows where {display_name} is {value}.",
        "Run ORA for {table} where {display_name} is {value}.",
        "Run ORA on {table} for rows where {display_name} is {value}.",
    ],
    "compare": [
        "Compare expression where {display_name} is {value}.",
        "Compare expression profiles where {display_name} is {value}.",
        "Compare sample expression where {display_name} is {value}.",
    ],
    "phylo": [
        "Open the phylo tree where {display_name} is {value}.",
        "Show the phylogenetic tree where {display_name} is {value}.",
        "Open PhyloTree where {display_name} is {value}.",
    ],
}


def _render_generic(tpl_text: str, slot: Dict[str, str]) -> Dict[str, str]:
    namespace_label = "samples" if slot.get("namespace") == "obs" else "genes"
    display_name = _slot_display_name(slot)
    text = tpl_text.format(
        table=slot.get("table_label") or slot.get("table", ""),
        namespace_label=namespace_label,
        column=slot.get("column", ""),
        display_name=display_name,
        value=slot.get("value", ""),
    )
    view = "heatmap" if slot.get("namespace") == "obs" else "ora"
    return {"id": f"generic_{slot.get('namespace')}_{slot.get('column')}", "view": view, "text": text}


def _slot_display_name(slot: Dict[str, str]) -> str:
    return slot.get("display_name") or slot.get("column", "")


def _render_generic_view(
    view: str,
    slot: Dict[str, str],
    *,
    variant: int = 0,
    tables: Optional[List[str]] = None,
    all_table_count: Optional[int] = None,
) -> Dict[str, str]:
    templates = _GENERIC_VIEW_TEMPLATES[view]
    tpl = templates[int(variant or 0) % len(templates)]
    table_label = _tables_label(slot, tables, all_table_count=all_table_count)
    text = tpl.format(
        table=table_label,
        display_name=_slot_display_name(slot),
        value=slot.get("value", ""),
    )
    safe_value = str(slot.get("value", "")).replace(" ", "_")[:40]
    return {
        "id": f"generic_{view}_{variant}_{slot.get('table')}_{slot.get('namespace')}_{slot.get('column')}_{safe_value}",
        "view": view,
        "text": text,
    }


def _tables_label(slot: Dict[str, str], tables: Optional[List[str]], *, all_table_count: Optional[int] = None) -> str:
    if tables and len(tables) > 1:
        return "all species" if all_table_count is not None and len(tables) == int(all_table_count) else "multiple species"
    return slot.get("table_label") or slot.get("table", "")


def _suggestion_action(view: str, tables: List[str], column: str, value: str) -> Dict[str, Any]:
    filters = {
        "filters": {column: {"value": value, "match_mode": "or", "exact": True}},
        "datasetIdFilters": {},
    }
    visualizations: Dict[str, Any] = {}
    if view == "phylo":
        visualizations = {"phyloTree": {"selectedOrthogroup": value}}
    elif view == "compare" and column.lower() in {"ortho_id", "orthogroup", "orthogroup_id"}:
        visualizations = {"compare": {"selectedOrthogroup": value}}
    return {
        "kind": "deeplink",
        "spec": {
            "view": view,
            "tables": tables,
            "filters": filters,
            "visualizations": visualizations,
        },
    }


def _is_actionable_slot(service, cm, view: str, slot: Dict[str, str], pool: Dict[str, Any]) -> bool:
    return _build_actionable_suggestion(service, cm, view, slot, pool) is not None


def _build_actionable_suggestion(
    service,
    cm,
    view: str,
    slot: Dict[str, str],
    pool: Dict[str, Any],
    *,
    variant: int = 0,
    tables_override: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    try:
        from . import assistant_tools as _at
    except Exception:
        return None
    column = str(slot.get("column") or "")
    value = str(slot.get("value") or "")
    namespace = str(slot.get("namespace") or "")
    if not column or not value or namespace != "var":
        return None
    if tables_override is not None:
        tables = [str(item) for item in tables_override if str(item).strip()]
    elif view in {"compare", "phylo"}:
        tables = [str(item) for item in (pool.get("species") or []) if str(item)]
    else:
        table = str(slot.get("table") or "")
        tables = [table] if table else []
    if not tables:
        return None
    try:
        action = _suggestion_action(view, tables, column, value)
        result = _at.tool_build_deeplink(
            service,
            cm,
            view=view,
            tables=tables,
            filters=action["spec"]["filters"],
            visualizations=action["spec"].get("visualizations") or {},
        )
    except Exception:
        return None
    if not isinstance(result, dict) or result.get("error") or not result.get("url_path"):
        return None
    item = _render_generic_view(
        view,
        slot,
        variant=variant,
        tables=tables,
        all_table_count=len(pool.get("species") or []),
    )
    action["url_path"] = result.get("url_path")
    action["view"] = result.get("view") or view
    item["action"] = action
    item["tables"] = result.get("tables") or tables
    item["column"] = column
    item["value"] = value
    return item


def _is_orthogroup_slot(slot: Dict[str, str]) -> bool:
    column = str(slot.get("column") or "").lower()
    display = str(slot.get("display_name") or "").lower()
    return "ortho" in column or "orthogroup" in display


def _slot_key(slot: Dict[str, str]) -> Tuple[str, str, str]:
    return (str(slot.get("table") or ""), str(slot.get("column") or ""), str(slot.get("value") or ""))


def _interleave_by_table(slots: List[Dict[str, str]]) -> List[Dict[str, str]]:
    buckets: Dict[str, List[Dict[str, str]]] = {}
    order: List[str] = []
    for slot in slots:
        table = str(slot.get("table") or "")
        if table not in buckets:
            buckets[table] = []
            order.append(table)
        buckets[table].append(slot)
    out: List[Dict[str, str]] = []
    index = 0
    while True:
        added = False
        for table in order:
            bucket = buckets.get(table) or []
            if index < len(bucket):
                out.append(bucket[index])
                added = True
        if not added:
            break
        index += 1
    return out


def _fill_template(tpl: Dict[str, Any], pool: Dict[str, Any], rng: random.Random) -> Optional[Dict[str, str]]:
    fillers: Dict[str, str] = {}
    for slot in tpl["slots"]:
        values = pool.get(slot) or []
        if not values:
            return None
        choice = rng.choice(values)
        if slot == "sample_trait":
            fillers["sample_trait_column"] = choice.get("column", "")
            fillers["sample_trait_label"] = choice.get("display_name") or choice.get("column", "")
            fillers["sample_trait_value"] = choice.get("value", "")
            fillers["sample_trait_table"] = choice.get("table", "")
        elif slot == "row_trait":
            fillers["row_trait_column"] = choice.get("column", "")
            fillers["row_trait_label"] = choice.get("display_name") or choice.get("column", "")
        else:
            if slot == "species":
                labels = pool.get("species_labels") or {}
                fillers[slot] = str(labels.get(str(choice), choice))
            else:
                fillers[slot] = str(choice)
    return {"id": tpl["id"], "view": tpl.get("view", "other"), "text": tpl["text"].format(**fillers)}


def _build_suggestion_bank(service, cm, pool: Dict[str, Any]) -> List[Dict[str, Any]]:
    mtime = _POOL_CACHE.get("mtime")
    cached = _BANK_CACHE.get("items")
    if cached is not None and _BANK_CACHE.get("mtime") == mtime:
        return cached

    discovered = _interleave_by_table([slot for slot in (pool.get("discovered") or []) if slot.get("namespace") == "var"])
    ortho_slots = [slot for slot in discovered if _is_orthogroup_slot(slot)]
    tree_values = {str(value) for value in (pool.get("tree_value") or [])}
    all_tables = [str(item) for item in (pool.get("species") or []) if str(item)]
    bank: List[Dict[str, Any]] = []
    seen_text: set = set()

    def _add(item: Optional[Dict[str, Any]]) -> bool:
        if not item or item.get("text") in seen_text:
            return False
        seen_text.add(str(item.get("text")))
        bank.append(item)
        return True

    for view in ("ora", "heatmap"):
        added_for_view = 0
        for slot in discovered:
            variants = [0, 1, 2]
            for variant in variants:
                tables_override = all_tables if variant == 2 and len(all_tables) > 1 else None
                if _add(_build_actionable_suggestion(
                    service, cm, view, slot, pool, variant=variant, tables_override=tables_override,
                )):
                    added_for_view += 1
                if added_for_view >= 18:
                    break
            if added_for_view >= 12:
                break

    compare_slots = ortho_slots or discovered
    added_for_view = 0
    for slot in compare_slots:
        for variant in (0, 1, 2):
            if _add(_build_actionable_suggestion(
                service, cm, "compare", slot, pool, variant=variant, tables_override=all_tables,
            )):
                added_for_view += 1
            if added_for_view >= 18:
                break
        if added_for_view >= 18:
            break

    if tree_values and ortho_slots:
        added_for_view = 0
        for slot in ortho_slots:
            if str(slot.get("value") or "") not in tree_values:
                continue
            for variant in (0, 1, 2):
                if _add(_build_actionable_suggestion(
                    service, cm, "phylo", slot, pool, variant=variant, tables_override=all_tables,
                )):
                    added_for_view += 1
                if added_for_view >= 12:
                    break
            if added_for_view >= 12:
                break

    _BANK_CACHE["mtime"] = mtime
    _BANK_CACHE["items"] = bank
    _BANK_CACHE["built_at"] = time.time()
    return bank


def _build_random_suggestion_bank(service, cm, pool: Dict[str, Any], rng: random.Random, *, target: int) -> List[Dict[str, Any]]:
    discovered = [slot for slot in (pool.get("discovered") or []) if slot.get("namespace") == "var"]
    ortho_slots = [slot for slot in discovered if _is_orthogroup_slot(slot)]
    tree_values = {str(value) for value in (pool.get("tree_value") or [])}
    all_tables = [str(item) for item in (pool.get("species") or []) if str(item)]
    desired_views = ["ora", "heatmap", "compare"]
    if tree_values and ortho_slots and target > len(desired_views):
        desired_views.append("phylo")

    bank: List[Dict[str, Any]] = []
    seen_text: set = set()

    def _try_add(view: str, slots: List[Dict[str, str]], *, attempts: int) -> bool:
        if not slots:
            return False
        for _ in range(max(1, attempts)):
            slot = rng.choice(slots)
            variant = rng.randrange(len(_GENERIC_VIEW_TEMPLATES[view]))
            tables_override: Optional[List[str]] = None
            if view in {"compare", "phylo"}:
                tables_override = all_tables
            elif all_tables and len(all_tables) > 1:
                mode = rng.random()
                if mode < 0.40:
                    tables_override = None
                elif mode < 0.70:
                    tables_override = all_tables
                else:
                    tables_override = rng.sample(all_tables, rng.randint(2, len(all_tables)))
            item = _build_actionable_suggestion(
                service, cm, view, slot, pool, variant=variant, tables_override=tables_override,
            )
            text = str(item.get("text")) if item else ""
            if item and text and text not in seen_text:
                seen_text.add(text)
                bank.append(item)
                return True
        return False

    for view in desired_views:
        slots = discovered
        if view == "compare":
            slots = ortho_slots or discovered
        elif view == "phylo":
            slots = [slot for slot in ortho_slots if str(slot.get("value") or "") in tree_values]
        _try_add(view, slots, attempts=60)

    rounds = 0
    while len(bank) < max(target, len(desired_views)) and rounds < target * 80:
        rounds += 1
        view = rng.choice(desired_views)
        slots = discovered
        if view == "compare":
            slots = ortho_slots or discovered
        elif view == "phylo":
            slots = [slot for slot in ortho_slots if str(slot.get("value") or "") in tree_values]
        _try_add(view, slots, attempts=10)
    return bank


def _public_suggestion(item: Dict[str, Any]) -> Dict[str, str]:
    return {
        "id": str(item.get("id") or item.get("text") or "suggestion"),
        "view": str(item.get("view") or "other"),
        "text": str(item.get("text") or ""),
    }


def generate_suggestions(
    service,
    cm,
    *,
    n: int = 4,
    seed: Optional[int] = None,
) -> List[Dict[str, str]]:
    """Render up to ``n`` distinct suggestions for the current dataset.

    Each item is ``{"id": "<template_id>", "text": "<rendered prompt>"}``.
    The caller can pass a deterministic ``seed`` for tests; in production the
    endpoint relies on the default RNG so each refresh yields a fresh mix.
    """
    n = max(1, min(int(n), 10))
    pool = build_suggestion_pool(service, cm)
    templates = _eligible_templates(pool)
    rng = random.Random(seed) if seed is not None else random.Random()
    bank = _build_random_suggestion_bank(service, cm, pool, rng, target=n)
    if not bank:
        bank = _build_suggestion_bank(service, cm, pool)

    if not templates and not bank:
        return []

    rng.shuffle(bank)
    if len(bank) >= n:
        selected: List[Dict[str, Any]] = []
        seen_text: set = set()
        preferred_views = ["ora", "heatmap", "compare"]
        if n > len(preferred_views):
            preferred_views.append("phylo")
        for view in preferred_views:
            match = next((item for item in bank if item.get("view") == view and item.get("text") not in seen_text), None)
            if match:
                selected.append(match)
                seen_text.add(str(match.get("text")))
                if len(selected) >= n:
                    break
        for item in bank:
            if len(selected) >= n:
                break
            text = str(item.get("text"))
            if text in seen_text:
                continue
            selected.append(item)
            seen_text.add(text)
        return [_public_suggestion(item) for item in selected[:n]]

    suggestions: List[Dict[str, Any]] = list(bank)
    seen_text: set = {str(item.get("text")) for item in suggestions}
    rng.shuffle(templates)

    # Fallback only: non-mutating informational prompts are allowed when there
    # are not enough prevalidated action suggestions for this deployment.
    rounds = 0
    while len(suggestions) < n and rounds < n * 5 and templates:
        rounds += 1
        tpl = rng.choice(templates)
        item = _fill_template(tpl, pool, rng)
        if not item or item["text"] in seen_text:
            continue
        seen_text.add(item["text"])
        suggestions.append(item)

    return [_public_suggestion(item) for item in suggestions]
