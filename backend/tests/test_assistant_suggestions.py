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
        "tf_family": ["MIKC", "MIKC", "bHLH", "MIKC", "GATA"],
        "ortho_id":  ["OG1", "OG2", "OG3", "OG1", "OG4"],
        "is_tf":     [True, True, True, True, True],
    })
    cs_obs = pd.DataFrame({"tissue": ["leaf", "leaf", "root", "flower"]})

    ps_var = pd.DataFrame({
        "tf_family": ["bHLH", "MIKC"],
        "ortho_id":  ["OG3", "OG1"],
        "is_tf":     [True, True],
    })
    ps_obs = pd.DataFrame({"tissue": ["root", "leaf"]})

    class FakeAdata:
        def __init__(self, var, obs):
            self.var = var
            self.obs = obs
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
    service = SimpleNamespace(
        registry=FakeRegistry(),
        get_tables=lambda include_disabled=False: entries,
    )
    cm = SimpleNamespace(get_config=lambda: {})
    return service, cm


def test_pool_collects_values_from_each_species():
    # Reset cache between tests so mtime detection doesn't reuse a stale pool.
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    service, cm = _make_service()
    pool = suggestions.build_suggestion_pool(service, cm)

    assert set(pool["species"]) == {"CS", "PS"}
    assert "leaf" in pool["tissue"]
    assert "MIKC" in pool["tf_family"]
    assert "OG1" in pool["ortho_id"]
    # No duplicates in any pool list.
    for key in ("species", "tissue", "tf_family", "ortho_id"):
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


def test_generate_suggestions_seed_is_deterministic():
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    service, cm = _make_service()
    a = suggestions.generate_suggestions(service, cm, n=4, seed=7)
    b = suggestions.generate_suggestions(service, cm, n=4, seed=7)
    assert a == b


def test_generate_suggestions_skips_templates_with_empty_pool():
    suggestions._POOL_CACHE["pool"] = None
    suggestions._POOL_CACHE["mtime"] = None

    # Service with one species, no annotations whatsoever.
    class FakeAdata:
        var = pd.DataFrame()
        obs = pd.DataFrame()
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
