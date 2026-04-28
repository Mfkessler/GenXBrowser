"""Dynamic prompt suggestions for the AI assistant.

Generates short, dataset-grounded example prompts that the user can click in
the assistant panel. All sampled values come from the actually-loaded H5AD
files (species codes, tissues, TF families, orthogroup IDs) — never invented
— so every suggestion maps to a query that will return data.

Public surface:
- :func:`build_suggestion_pool` — collect candidate values once per dataset
  state (cached on the service registry mtime).
- :func:`generate_suggestions` — sample a small set of templates against the
  current pool and return formatted prompt strings.
"""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Template registry. Each entry declares the slots it needs so the generator
# can skip templates whose pool is empty for the current dataset.
# ``slots`` items are keys into the pool dict built by build_suggestion_pool.
_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "tf_heatmap",
        "slots": ["tf_family", "species"],
        "text": "Show {tf_family} transcription factors as a heatmap in {species}.",
    },
    {
        "id": "tf_heatmap_all",
        "slots": ["tf_family"],
        "text": "Open a heatmap of all {tf_family} transcription factors across every species.",
    },
    {
        "id": "tf_tissue",
        "slots": ["tf_family", "tissue"],
        "text": "Show expression of {tf_family} in {tissue} samples as a heatmap.",
    },
    {
        "id": "tissue_filter",
        "slots": ["tissue", "species"],
        "text": "Filter {species} to {tissue} samples and show the top expressed genes.",
    },
    {
        "id": "ortho_compare",
        "slots": ["ortho_id"],
        "text": "Compare expression of orthogroup {ortho_id} across all species.",
    },
    {
        "id": "ortho_phylo",
        "slots": ["ortho_id"],
        "text": "Open the gene tree for orthogroup {ortho_id}.",
    },
    {
        "id": "ora_tf",
        "slots": ["tf_family", "species"],
        "text": "Run a GO term ORA on {tf_family} transcription factors in {species}.",
    },
    {
        "id": "summary",
        "slots": ["species"],
        "text": "Summarize the {species} dataset.",
    },
    {
        "id": "shared_orthogroups",
        "slots": [],
        "text": "Which orthogroups are shared across all loaded species?",
    },
    {
        "id": "common_tissues",
        "slots": [],
        "text": "Which sample tissues are common to every species?",
    },
    {
        "id": "top_tf_family",
        "slots": ["species"],
        "text": "Which transcription factor family is most represented in {species}?",
    },
]


# Module-level cache: a single (mtime, pool) tuple. The mtime probe is cheap
# (already used by /api/overview/mtime) so we re-validate on every request
# and rebuild only when the dataset state actually changed.
_POOL_CACHE: Dict[str, Any] = {"mtime": None, "pool": None, "built_at": 0.0}


def _safe_mtime(service, cm) -> Optional[float]:
    try:
        from .overview import _overview_mtime
        return float(_overview_mtime(service, cm))
    except Exception:  # pragma: no cover — defensive
        return None


def build_suggestion_pool(service, cm) -> Dict[str, List[str]]:
    """Collect candidate values from the live dataset.

    Returns a dict with these (always-present) keys, each a list of strings:
    ``species``, ``tissue``, ``tf_family``, ``ortho_id``. Empty lists are
    fine — the generator filters templates accordingly.
    """
    mtime = _safe_mtime(service, cm)
    cached = _POOL_CACHE.get("pool")
    if cached is not None and _POOL_CACHE.get("mtime") == mtime:
        return cached

    species: List[str] = []
    tissues: List[str] = []
    tf_families: List[str] = []
    ortho_ids: List[str] = []

    try:
        entries = service.get_tables(include_disabled=False)
    except Exception as e:
        logger.warning("suggestion pool: get_tables failed: %s", e)
        entries = []

    seen_tissue: set = set()
    seen_tf: set = set()
    seen_ortho: set = set()
    # Generic slot harvested from any low-cardinality categorical column.
    # Each entry: {"namespace": "var"|"obs", "column": str, "value": str,
    # "table": species_code}. The generator turns these into generic
    # "filter by X" templates so deployments without tf_family/tissue/
    # ortho_id still produce meaningful suggestions.
    discovered: List[Dict[str, str]] = []
    seen_disc: set = set()
    # Skip columns with these prefixes/exact names — they're never useful as
    # filter slot fillers (free text, ids, scores, paths, ...).
    _BLOCKED_COL_SUBSTR = (
        "id", "name", "path", "score", "pvalue", "p_value", "padj",
        "ensembl", "uniprot", "gene_symbol", "transcript",
    )

    def _harvest(adata, code: str, df, namespace: str):
        for col in df.columns:
            lc = col.lower()
            if any(b in lc for b in _BLOCKED_COL_SUBSTR):
                continue
            try:
                s = df[col].dropna()
                if s.empty:
                    continue
                dtype = str(s.dtype)
                if dtype.startswith("float") or dtype.startswith("int") or dtype.startswith("bool"):
                    continue
                vc = s.astype(str).value_counts()
                if 1 < len(vc) <= 30:
                    for val in vc.head(5).index.tolist():
                        if not val or len(val) > 60:
                            continue
                        key = (namespace, col, val)
                        if key in seen_disc:
                            continue
                        seen_disc.add(key)
                        discovered.append({
                            "namespace": namespace, "column": col,
                            "value": val, "table": code,
                        })
            except Exception:
                continue

    for entry in entries:
        code = entry.get("_species_code") or entry.get("code")
        if not code:
            continue
        species.append(str(code))
        try:
            adata = service.registry.load(code)
        except Exception:
            adata = None
        if adata is None:
            continue
        # Tissues from obs.
        if "tissue" in adata.obs.columns:
            try:
                vals = adata.obs["tissue"].dropna().astype(str)
                top = vals.value_counts().head(20).index.tolist()
                for v in top:
                    if v and v not in seen_tissue:
                        seen_tissue.add(v)
                        tissues.append(v)
            except Exception:
                pass
        # TF families from var (only TF rows, if `is_tf` exists).
        if "tf_family" in adata.var.columns:
            try:
                series = adata.var["tf_family"]
                if "is_tf" in adata.var.columns:
                    mask = adata.var["is_tf"].astype(bool)
                    series = series[mask]
                vals = series.dropna().astype(str)
                top = vals.value_counts().head(15).index.tolist()
                for v in top:
                    if v and v not in seen_tf:
                        seen_tf.add(v)
                        tf_families.append(v)
            except Exception:
                pass
        # Orthogroup ID samples.
        if "ortho_id" in adata.var.columns:
            try:
                oseries = adata.var["ortho_id"].dropna().astype(str)
                oseries = oseries[oseries.str.len() > 0]
                # Cap to first 200 unique IDs per species so the pool stays
                # bounded; the generator picks at random anyway.
                for v in oseries.unique()[:200]:
                    if v not in seen_ortho:
                        seen_ortho.add(v)
                        ortho_ids.append(v)
            except Exception:
                pass
        # Generic schema-driven harvest for any other low-cardinality column.
        try:
            _harvest(adata, str(code), adata.obs, "obs")
            _harvest(adata, str(code), adata.var, "var")
        except Exception:
            pass

    pool = {
        "species": species,
        "tissue": tissues,
        "tf_family": tf_families,
        "ortho_id": ortho_ids,
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
# files don't carry the well-known `tf_family`/`tissue`/`ortho_id` columns.
_GENERIC_TEMPLATE_TEXTS: List[str] = [
    "Show {table}: how many {namespace_label} have {column} = {value}?",
    "Filter {table} to {namespace_label} where {column} is {value} and summarize.",
    "List the most common values of {column} in {table}.",
]


def _render_generic(tpl_text: str, slot: Dict[str, str]) -> Dict[str, str]:
    namespace_label = "samples" if slot.get("namespace") == "obs" else "genes"
    text = tpl_text.format(
        table=slot.get("table", ""),
        namespace_label=namespace_label,
        column=slot.get("column", ""),
        value=slot.get("value", ""),
    )
    return {"id": f"generic_{slot.get('namespace')}_{slot.get('column')}", "text": text}


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
    discovered = pool.get("discovered") or []

    if not templates and not discovered:
        return []

    rng = random.Random(seed) if seed is not None else random.Random()
    rng.shuffle(templates)

    suggestions: List[Dict[str, str]] = []
    seen_text: set = set()

    # Pass 1: well-known slot templates (tf_family/tissue/ortho_id…).
    rounds = 0
    while len(suggestions) < n and rounds < n * 4 and templates:
        rounds += 1
        for tpl in templates:
            if len(suggestions) >= n:
                break
            try:
                fillers = {slot: rng.choice(pool[slot]) for slot in tpl["slots"]}
            except IndexError:
                continue
            text = tpl["text"].format(**fillers)
            if text in seen_text:
                continue
            seen_text.add(text)
            suggestions.append({"id": tpl["id"], "text": text})

    # Pass 2: schema-driven generic templates so under-annotated deployments
    # still get a couple of useful prompts.
    if len(suggestions) < n and discovered:
        shuffled = list(discovered)
        rng.shuffle(shuffled)
        for slot in shuffled:
            if len(suggestions) >= n:
                break
            tpl_text = rng.choice(_GENERIC_TEMPLATE_TEXTS)
            item = _render_generic(tpl_text, slot)
            if item["text"] in seen_text:
                continue
            seen_text.add(item["text"])
            suggestions.append(item)

    return suggestions
