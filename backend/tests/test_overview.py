"""Tests for the landing-page overview aggregation."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


overview = _load_module("genxbrowser_overview", "app/overview.py")


class FakeAnnData:
    def __init__(self, obs: pd.DataFrame, var: pd.DataFrame, layers=None):
        self.obs = obs
        self.var = var
        self.layers = layers or {}
        self.n_obs = len(obs)
        self.n_vars = len(var)


class FakeRegistry:
    def __init__(self, data):
        self._data = data
        self._species = {
            code: {"file_path": f"/tmp/{code}.h5ad", "enabled": True}
            for code in data
        }

    def load(self, code):
        return self._data.get(code)

    def get_species_list(self, enabled_only=True):
        return [
            {
                "code": code,
                "full_name": f"Species {code}",
                "display_name": f"Species {code}",
                "table_name": f"Species {code}",
                "tags": ["plants"],
                "enabled": True,
                "available_layers": [],
            }
            for code in self._data
        ]

    # Legacy helper used by older tests.
    def get_species_info(self, code):
        return {"code": code, "table_name": f"Species {code}", "tags": ["plants"]}


class FakeService:
    def __init__(self, data):
        self.registry = FakeRegistry(data)


class FakeCM:
    def __init__(self, cfg):
        self._cfg = cfg

    def get_config(self):
        return self._cfg


def _make_adata_full():
    obs = pd.DataFrame({
        "tissue": ["leaf", "leaf", "root", "flower", "root"],
        "assigned": [100, 200, 180, 160, 175],
        "pct_unmapped": [5.0, 6.0, 7.0, 5.5, 6.2],
    })
    var = pd.DataFrame({
        "gene_id": ["g1", "g2", "g3", "g4"],
        "is_tf": [True, False, True, False],
        "tf_family": ["MYB", "", "bHLH", ""],
        "ortho_id": ["OG1", "OG2", "OG1", ""],
        "go_terms": ["GO:1", "GO:2", "", ""],
    })
    return FakeAnnData(obs, var, layers={"tpm": None, "tmm": None})


def _make_adata_sparse():
    obs = pd.DataFrame({"sample_id": ["s1", "s2"]})
    var = pd.DataFrame({"gene_id": ["g1", "g2"]})
    return FakeAnnData(obs, var)


def test_build_overview_aggregates_global_totals():
    overview.invalidate_cache()
    service = FakeService({"PS": _make_adata_full(), "CS": _make_adata_sparse()})
    cm = FakeCM({
        "project_name": "Test",
        "version": "1.0",
        "species": {
            "PS": {"enabled": True},
            "CS": {"enabled": True},
            "ZZ": {"enabled": False},
        }
    })
    out = overview.build_overview(service, cm)
    assert out["project"]["name"] == "Test"
    assert out["global"]["n_species"] == 2
    assert out["global"]["n_samples"] == 5 + 2
    assert out["global"]["n_genes"] == 4 + 2
    codes = sorted(s["code"] for s in out["species"])
    assert codes == ["CS", "PS"]


def test_build_overview_gates_on_column_presence():
    overview.invalidate_cache()
    service = FakeService({"PS": _make_adata_full(), "CS": _make_adata_sparse()})
    cm = FakeCM({"species": {"PS": {"enabled": True}, "CS": {"enabled": True}}})
    out = overview.build_overview(service, cm)
    ps = next(s for s in out["species"] if s["code"] == "PS")
    cs = next(s for s in out["species"] if s["code"] == "CS")

    # PS has tissue/tf/ortho signals.
    assert "tissue_distribution" in ps["derived"]
    assert ps["derived"]["tf_count"] == 2
    assert ps["derived"]["orthogroup_count"] == 2
    assert "qc_metrics" in ps["derived"]
    assert "pct_unmapped" in ps["derived"]["qc_metrics"]
    # CS has none — no tissue, no tf, no orthogroup.
    assert "tissue_distribution" not in cs["derived"]
    assert "tf_count" not in cs["derived"]
    assert "orthogroup_count" not in cs["derived"]


def test_build_overview_tissue_union_totals():
    overview.invalidate_cache()
    service = FakeService({"PS": _make_adata_full()})
    cm = FakeCM({"species": {"PS": {"enabled": True}}})
    out = overview.build_overview(service, cm)
    tissues = {row["tissue"]: row["total"] for row in out["global"]["tissue_union"]}
    assert tissues == {"leaf": 2, "root": 2, "flower": 1}


def test_disabled_species_excluded():
    overview.invalidate_cache()
    service = FakeService({"PS": _make_adata_full()})
    cm = FakeCM({"species": {"PS": {"enabled": False}}})
    out = overview.build_overview(service, cm)
    assert out["species"] == []
    assert out["global"]["n_species"] == 0
