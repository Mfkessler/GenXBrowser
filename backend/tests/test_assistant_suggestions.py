"""Unit tests for the dynamic prompt-suggestion generator."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

import numpy as np
import pandas as pd


def _load(name: str, relative: str):
    p = Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(name, p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


suggestions = _load("gx_suggestions", "app/suggestions.py")


def _make_service():
    cs_var = pd.DataFrame({
        "tf_family": ["MIKC", "MIKC", "bHLH", "MIKC", "GATA", "ERF", "NAC", "MYB"],
        "ortho_id":  ["OG1", "OG2", "OG3", "OG1", "OG4", "OG5", "OG6", "OG7"],
        "is_tf":     [True, True, True, True, True, True, True, True],
    })
    cs_obs = pd.DataFrame({"tissue": ["leaf", "leaf", "root", "flower"]})
    cs_obs["condition"] = ["Leaf", "Leaf", "Root", "Flower"]

    ps_var = pd.DataFrame({
        "tf_family": ["bHLH", "MIKC"],
        "ortho_id":  ["OG3", "OG1"],
        "is_tf":     [True, True],
    })
    ps_obs = pd.DataFrame({"tissue": ["root", "leaf"], "condition": ["Root", "Leaf"]})

    class FakeAdata:
        def __init__(self, var, obs):
            self.var = var
            self.obs = obs
            self.X = np.ones((len(obs), len(var)))
            self.n_vars = len(var)
            self.n_obs = len(obs)

    loaded = {"CS": FakeAdata(cs_var, cs_obs), "PS": FakeAdata(ps_var, ps_obs)}

    class FakeRegistry:
        def load(self, code, ignore_enabled=False):
            return loaded.get(code)

    entries = [
        {"_species_code": "CS"},
        {"_species_code": "PS"},
    ]
    class FakeTrees:
        def get(self, og_id):
            return "(a,b);" if og_id == "OG1" else None

    service = SimpleNamespace(
        registry=FakeRegistry(),
        get_tables=lambda include_disabled=False: entries,
        gene_trees=FakeTrees(),
        store_filter=lambda payload: "abc123def4567890",
    )
    cm = SimpleNamespace(
        get_config=lambda: {},
        get_column_definitions=lambda: {
            "tf_family": {"display_name": "Family"},
            "ortho_id": {"display_name": "Group ID"},
            "condition": {"display_name": "Condition"},
            "tissue": {"display_name": "Tissue"},
        },
    )
    return service, cm


def test_pool_collects_values_from_each_species():
    # Reset cache between tests so mtime detection doesn't reuse a stale pool.
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    service, cm = _make_service()
    pool = suggestions.build_suggestion_pool(service, cm)

    assert set(pool["species"]) == {"CS", "PS"}
    assert any(item["value"] == "Flower" and item["display_name"] == "Condition" for item in pool["sample_trait"])
    assert any(item["value"] == "MIKC" for item in pool["discovered"])
    assert any(item["value"] == "OG1" for item in pool["discovered"])
    assert any(item["value"] == "OG7" for item in pool["discovered"])
    assert pool["tree_value"] == ["OG1"]
    # No duplicates in any pool list.
    for key in ("species", "tree_value"):
        assert len(pool[key]) == len(set(pool[key])), key


def test_generate_suggestions_returns_distinct_filled_prompts():
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    service, cm = _make_service()
    items = suggestions.generate_suggestions(service, cm, n=4, seed=42)

    assert 1 <= len(items) <= 4
    texts = [it["text"] for it in items]
    # Distinct rendered strings.
    assert len(set(texts)) == len(texts)
    # No unfilled placeholders left over.
    for t in texts:
        assert "{" not in t and "}" not in t


def test_generate_suggestions_balances_primary_views_when_available(monkeypatch):
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None
    suggestions._BANK_CACHE["items"] = None
    suggestions._BANK_CACHE["mtime"] = None

    def fake_actionable(_service, _cm, view, slot, _pool, **kwargs):
        item = suggestions._render_generic_view(view, slot, variant=kwargs.get("variant", 0), tables=kwargs.get("tables_override"))
        item["action"] = {"kind": "deeplink", "url_path": f"/{view}/fake", "spec": {"view": view}}
        return item

    monkeypatch.setattr(suggestions, "_build_actionable_suggestion", fake_actionable)

    service, cm = _make_service()
    items = suggestions.generate_suggestions(service, cm, n=4, seed=12)
    assert {"ora", "heatmap", "compare"}.issubset({it.get("view") for it in items})


def test_generate_suggestions_uses_display_names_for_filter_examples():
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    service, cm = _make_service()
    items = suggestions.generate_suggestions(service, cm, n=10, seed=3)
    assert any(("Family" in it["text"] or "Group ID" in it["text"]) for it in items)


def test_generate_suggestions_emits_phylo_examples_for_tree_values(monkeypatch):
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None
    suggestions._BANK_CACHE["items"] = None
    suggestions._BANK_CACHE["mtime"] = None

    def fake_actionable(_service, _cm, view, slot, pool, **kwargs):
        if view == "phylo" and slot.get("value") not in set(pool.get("tree_value") or []):
            return None
        item = suggestions._render_generic_view(view, slot, variant=kwargs.get("variant", 0), tables=kwargs.get("tables_override"))
        item["action"] = {"kind": "deeplink", "url_path": f"/{view}/fake", "spec": {"view": view}}
        return item

    monkeypatch.setattr(suggestions, "_build_actionable_suggestion", fake_actionable)

    service, cm = _make_service()
    items = suggestions.generate_suggestions(service, cm, n=10, seed=2)
    phylo = [it for it in items if it.get("view") == "phylo"]
    assert phylo
    assert all("OG1" in it["text"] for it in phylo)
    assert all("CS" not in it["text"] and "PS" not in it["text"] for it in phylo)


def test_compare_examples_use_orthogroups_without_dataset_names(monkeypatch):
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None
    suggestions._BANK_CACHE["items"] = None
    suggestions._BANK_CACHE["mtime"] = None

    def fake_actionable(_service, _cm, view, slot, _pool, **kwargs):
        item = suggestions._render_generic_view(view, slot, variant=kwargs.get("variant", 0), tables=kwargs.get("tables_override"))
        item["action"] = {"kind": "deeplink", "url_path": f"/{view}/fake", "spec": {"view": view}}
        return item

    monkeypatch.setattr(suggestions, "_build_actionable_suggestion", fake_actionable)

    service, cm = _make_service()
    items = suggestions.generate_suggestions(service, cm, n=10, seed=5)
    compare = [it for it in items if it.get("view") == "compare"]
    assert compare
    assert all("OG" in it["text"] or "Group ID" in it["text"] for it in compare)
    assert all("CS" not in it["text"] and "PS" not in it["text"] for it in compare)


def test_generate_suggestions_seed_is_deterministic():
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None
    suggestions._BANK_CACHE["items"] = None
    suggestions._BANK_CACHE["mtime"] = None

    service, cm = _make_service()
    a = suggestions.generate_suggestions(service, cm, n=4, seed=7)
    b = suggestions.generate_suggestions(service, cm, n=4, seed=7)
    assert a == b


def test_shuffle_samples_more_than_first_orthogroups(monkeypatch):
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None
    suggestions._BANK_CACHE["items"] = None
    suggestions._BANK_CACHE["mtime"] = None

    def fake_actionable(_service, _cm, view, slot, _pool, **kwargs):
        item = suggestions._render_generic_view(view, slot, variant=kwargs.get("variant", 0), tables=kwargs.get("tables_override"))
        item["action"] = {"kind": "deeplink", "url_path": f"/{view}/fake", "spec": {"view": view}}
        return item

    monkeypatch.setattr(suggestions, "_build_actionable_suggestion", fake_actionable)

    service, cm = _make_service()
    seen_ogs = set()
    for seed in range(25):
        for item in suggestions.generate_suggestions(service, cm, n=4, seed=seed):
            for token in item["text"].replace(".", "").split():
                if token.startswith("OG"):
                    seen_ogs.add(token)

    assert {"OG1", "OG2", "OG3", "OG4"} <= seen_ogs


def test_heatmap_and_ora_keep_species_text_but_compare_phylo_do_not(monkeypatch):
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None
    suggestions._BANK_CACHE["items"] = None
    suggestions._BANK_CACHE["mtime"] = None

    def fake_actionable(_service, _cm, view, slot, _pool, **kwargs):
        item = suggestions._render_generic_view(view, slot, variant=kwargs.get("variant", 0), tables=kwargs.get("tables_override"))
        item["action"] = {"kind": "deeplink", "url_path": f"/{view}/fake", "spec": {"view": view}}
        return item

    monkeypatch.setattr(suggestions, "_build_actionable_suggestion", fake_actionable)

    service, cm = _make_service()
    items = suggestions.generate_suggestions(service, cm, n=10, seed=19)
    by_view = {item["view"]: item["text"] for item in items}
    heatmap_text = by_view.get("heatmap", "")
    ora_text = by_view.get("ora", "")
    assert "CS" in heatmap_text or "PS" in heatmap_text or "all species" in heatmap_text or "multiple species" in heatmap_text
    assert "CS" in ora_text or "PS" in ora_text or "all species" in ora_text or "multiple species" in ora_text
    assert "CS" not in by_view.get("compare", "") and "PS" not in by_view.get("compare", "")
    assert "CS" not in by_view.get("phylo", "") and "PS" not in by_view.get("phylo", "")


def test_generate_suggestions_skips_templates_with_empty_pool():
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    # Service with one species, no annotations whatsoever.
    class FakeAdata:
        var = pd.DataFrame()
        obs = pd.DataFrame()
        X = np.empty((0, 0))
        n_vars = 0
        n_obs = 0

    class FakeRegistry:
        def load(self, code, ignore_enabled=False):
            return FakeAdata()

    service = SimpleNamespace(
        registry=FakeRegistry(),
        get_tables=lambda include_disabled=False: [{"_species_code": "AA"}],
    )
    cm = SimpleNamespace(get_config=lambda: {})

    items = suggestions.generate_suggestions(service, cm, n=4, seed=1)
    # Only species-only or no-slot templates can match; result must be valid
    # (possibly fewer than 4) and contain no placeholder syntax.
    for it in items:
        assert "{" not in it["text"]
