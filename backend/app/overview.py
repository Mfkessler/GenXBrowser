"""
Data-agnostic overview aggregation for the landing page.

Builds a single response describing every enabled species in the project:
per-dataset sample/gene counts, layer availability, metadata coverage ratios,
tissue distributions, TF / orthogroup / gene-tree totals. Results are cached
per (species, h5ad-mtime) to avoid re-scanning AnnData objects on every
request. All outputs are data-driven — fields that are absent in a given
dataset are omitted rather than zero-padded, so the frontend can gate
widgets on presence.
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Canonical annotation columns the landing page may surface. Kept as a
# sensible default list; the actual overview reports whatever columns the
# loaded H5ADs contain, so this set is for the "known bioinformatic
# annotations" coverage matrix only.
KNOWN_ANNOTATIONS = {
    "var": [
        "description",
        "genename",
        "ecnumber",
        "go_terms",
        "ipr_id",
        "pfam_id",
        "is_tf",
        "tf_family",
        "ortho_id",
    ],
    "obs": [
        "tissue",
        "assigned",
        "pct_unmapped",
        "pct_no_feature",
        "pct_trimmed",
    ],
}


_CACHE: Dict[str, Dict[str, Any]] = {}


def _cache_key(service, code: str) -> Optional[str]:
    """Build cache key from species code + h5ad file mtime + config version."""
    try:
        path = None
        species_map = getattr(service.registry, "_species", None)
        if isinstance(species_map, dict) and code in species_map:
            path = species_map[code].get("file_path")
        if path and os.path.exists(path):
            return f"{code}:{os.path.getmtime(path):.3f}"
    except Exception:
        pass
    return None


def _overview_mtime(service, config_manager) -> float:
    """Return the max mtime across h5ad files + the project config file.

    Exposed so the frontend can cache an overview payload and only refetch
    when something meaningful on disk actually changed.
    """
    m = 0.0
    try:
        species_map = getattr(service.registry, "_species", {}) or {}
        for info in species_map.values():
            p = info.get("file_path")
            if p and os.path.exists(p):
                m = max(m, os.path.getmtime(p))
    except Exception:
        pass
    try:
        cfg_path = getattr(config_manager, "config_path", None) or getattr(
            config_manager, "_config_path", None
        )
        if cfg_path and os.path.exists(cfg_path):
            m = max(m, os.path.getmtime(str(cfg_path)))
    except Exception:
        pass
    return round(m, 3)


def _species_metadata(service, code: str) -> Dict[str, Any]:
    """Resolve per-species metadata (name, tags) from the registry.

    Combines the config view (``registry.get_species_list``) with the
    optional ``adata.uns['species']`` hint preferred by users.
    """
    result: Dict[str, Any] = {"full_name": code, "display_name": code, "table_name": code, "tags": []}
    try:
        for entry in service.registry.get_species_list(enabled_only=False):
            if entry.get("code") == code:
                result.update({
                    "full_name": entry.get("full_name") or code,
                    "display_name": entry.get("display_name") or entry.get("full_name") or code,
                    "table_name": entry.get("table_name") or entry.get("full_name") or code,
                    "tags": list(entry.get("tags") or []),
                })
                break
    except Exception:
        pass
    return result


def _non_null_ratio(series: pd.Series) -> float:
    if series.size == 0:
        return 0.0
    try:
        # Empty strings count as missing for our purposes.
        if series.dtype == object:
            filled = series.apply(lambda v: v is not None and (not isinstance(v, float) or not math.isnan(v)) and str(v).strip() != "")
            return float(filled.sum() / series.size)
        return float(1.0 - series.isna().sum() / series.size)
    except Exception:
        return 0.0


def _top_values(series: pd.Series, k: int = 8) -> List[Dict[str, Any]]:
    try:
        vc = series.dropna().astype(str).value_counts().head(k)
        return [{"value": str(idx), "count": int(v)} for idx, v in vc.items()]
    except Exception:
        return []


def _summarize_numeric(series: pd.Series) -> Optional[Dict[str, float]]:
    try:
        s = pd.to_numeric(series, errors="coerce").dropna()
        if s.empty:
            return None
        return {
            "min": float(s.min()),
            "max": float(s.max()),
            "mean": float(s.mean()),
            "median": float(s.median()),
            "count": int(s.size),
        }
    except Exception:
        return None


def _column_summary(series: pd.Series, name: str) -> Dict[str, Any]:
    dtype = str(series.dtype)
    is_numeric = pd.api.types.is_numeric_dtype(series)
    is_bool = pd.api.types.is_bool_dtype(series)
    summary: Dict[str, Any] = {
        "name": name,
        "dtype": dtype,
        "non_null_ratio": round(_non_null_ratio(series), 4),
        "is_numeric": bool(is_numeric),
        "is_boolean": bool(is_bool),
    }
    if is_numeric and not is_bool:
        num = _summarize_numeric(series)
        if num:
            summary["numeric"] = num
    else:
        try:
            summary["n_unique"] = int(series.astype(str).nunique(dropna=True))
        except Exception:
            pass
        summary["top"] = _top_values(series)
    return summary


def _build_species_overview(service, code: str) -> Optional[Dict[str, Any]]:
    adata = service.registry.load(code)
    if adata is None:
        return None

    meta = _species_metadata(service, code)
    # Prefer adata.uns['species'] when set explicitly during prep.
    uns_species = None
    try:
        if hasattr(adata, "uns") and "species" in adata.uns:
            v = adata.uns["species"]
            if isinstance(v, bytes):
                v = v.decode("utf-8", "ignore")
            if isinstance(v, str) and v.strip():
                uns_species = v.strip()
    except Exception:
        uns_species = None
    full_name = uns_species or meta["full_name"] or code
    display_name = meta["display_name"] or full_name
    table_name = meta["table_name"] or full_name
    tags = meta["tags"]

    var_cols = list(adata.var.columns)
    obs_cols = list(adata.obs.columns)
    layers = ["X"] + list(adata.layers.keys())

    result: Dict[str, Any] = {
        "code": code,
        "full_name": full_name,
        "display_name": display_name,
        "table_name": table_name,
        "tags": list(tags),
        "n_samples": int(adata.n_obs),
        "n_genes": int(adata.n_vars),
        "layers": layers,
        "var_columns": var_cols,
        "obs_columns": obs_cols,
    }

    # Metadata coverage — summarise every column, then flag the known ones.
    var_summary = [_column_summary(adata.var[c], c) for c in var_cols]
    obs_summary = [_column_summary(adata.obs[c], c) for c in obs_cols]
    result["var_summary"] = var_summary
    result["obs_summary"] = obs_summary

    # Derived high-signal facts for widgets.
    derived: Dict[str, Any] = {}
    if "tissue" in obs_cols:
        derived["tissue_distribution"] = _top_values(adata.obs["tissue"], k=20)
    if "is_tf" in var_cols:
        try:
            tf_mask = adata.var["is_tf"].astype(bool)
            derived["tf_count"] = int(tf_mask.sum())
            if "tf_family" in var_cols and derived["tf_count"] > 0:
                derived["tf_families"] = _top_values(adata.var.loc[tf_mask, "tf_family"], k=12)
        except Exception:
            pass
    if "ortho_id" in var_cols:
        try:
            oseries = adata.var["ortho_id"].dropna().astype(str)
            oseries = oseries[oseries.str.len() > 0]
            derived["orthogroup_count"] = int(oseries.nunique())
            derived["genes_with_orthogroup"] = int(oseries.size)
        except Exception:
            pass
    for qc in ("assigned", "pct_unmapped", "pct_no_feature", "pct_trimmed"):
        if qc in obs_cols:
            stat = _summarize_numeric(adata.obs[qc])
            if stat:
                derived.setdefault("qc_metrics", {})[qc] = stat
    result["derived"] = derived

    # Annotation coverage matrix flags.
    coverage: Dict[str, Dict[str, float]] = {"var": {}, "obs": {}}
    for col in KNOWN_ANNOTATIONS["var"]:
        if col in var_cols:
            coverage["var"][col] = round(_non_null_ratio(adata.var[col]), 4)
    for col in KNOWN_ANNOTATIONS["obs"]:
        if col in obs_cols:
            coverage["obs"][col] = round(_non_null_ratio(adata.obs[col]), 4)
    result["annotation_coverage"] = coverage

    return result


def build_overview(service, config_manager) -> Dict[str, Any]:
    """Aggregate overview across all enabled species."""
    project_cfg = config_manager.get_config()
    species_cfg = project_cfg.get("species", {}) or {}

    per_species: List[Dict[str, Any]] = []
    for code, info in species_cfg.items():
        if not info.get("enabled", True):
            continue
        key = _cache_key(service, code)
        if key and key in _CACHE:
            per_species.append(_CACHE[key])
            continue
        try:
            entry = _build_species_overview(service, code)
        except Exception as e:
            logger.warning("Overview build failed for %s: %s", code, e)
            entry = None
        if entry:
            if key:
                _CACHE[key] = entry
            per_species.append(entry)

    # Global totals and unions.
    n_samples = sum(s["n_samples"] for s in per_species)
    n_genes = sum(s["n_genes"] for s in per_species)

    tissue_union: Dict[str, Dict[str, int]] = {}
    for s in per_species:
        for item in s["derived"].get("tissue_distribution", []) or []:
            row = tissue_union.setdefault(item["value"], {})
            row[s["code"]] = row.get(s["code"], 0) + int(item["count"])

    total_orthogroups = 0
    any_ortho = False
    try:
        ortho_ids: set = set()
        for s in per_species:
            adata = service.registry.load(s["code"])
            if adata is not None and "ortho_id" in adata.var.columns:
                any_ortho = True
                vals = adata.var["ortho_id"].dropna().astype(str)
                ortho_ids.update(v for v in vals if v)
        total_orthogroups = len(ortho_ids)
    except Exception:
        total_orthogroups = 0

    gene_tree_count = 0
    try:
        gts = getattr(service, "gene_trees", None) or getattr(service, "gene_tree_store", None)
        if gts is not None and hasattr(gts, "count"):
            gene_tree_count = int(gts.count())
        elif gts is not None and hasattr(gts, "_trees"):
            gene_tree_count = len(gts._trees)
    except Exception:
        pass

    tf_total = 0
    for s in per_species:
        tf_total += int(s["derived"].get("tf_count", 0) or 0)

    project_name = project_cfg.get("project_name") or "GenXBrowser"
    version = project_cfg.get("version") or ""

    return {
        "project": {
            "name": project_name,
            "version": version,
            "description": project_cfg.get("description", ""),
        },
        "mtime": _overview_mtime(service, config_manager),
        "global": {
            "n_species": len(per_species),
            "n_samples": n_samples,
            "n_genes": n_genes,
            "orthogroup_count": total_orthogroups if any_ortho else 0,
            "has_orthogroups": any_ortho,
            "gene_tree_count": gene_tree_count,
            "tf_total": tf_total,
            "tissue_union": [
                {"tissue": t, "counts": counts, "total": sum(counts.values())}
                for t, counts in sorted(tissue_union.items(), key=lambda kv: -sum(kv[1].values()))
            ],
        },
        "species": per_species,
    }


def invalidate_cache() -> None:
    """Clear the in-memory overview cache (admin reload / config change)."""
    _CACHE.clear()
