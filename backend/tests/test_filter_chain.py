from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


def _load_services_module():
    services_path = Path(__file__).resolve().parents[1] / "app" / "services.py"
    spec = importlib.util.spec_from_file_location("genxbrowser_services_filter_chain", services_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GenXBrowserService = _load_services_module().GenXBrowserService


class DummyConfigManager:
    def get_column_definitions(self):
        return {}


def _service():
    service = GenXBrowserService.__new__(GenXBrowserService)
    service.config_manager = DummyConfigManager()
    service._to_display_column_name = lambda column: column
    service._to_h5ad_column_name = lambda column: column
    return service


class DummyAnnData:
    def __init__(self, obs):
        self.obs = obs
        self.obs_names = obs.index


def test_filter_chain_applies_ordered_or_then_and():
    service = _service()
    df = pd.DataFrame({
        "tf_family": ["MIKC", "WRKY", "MIKC", "ERF"],
        "go_terms": ["GO:1", "GO:1", "GO:2", "GO:1"],
        "pfam_desc": ["DomainA", "DomainA", "DomainA", "DomainB"],
    })
    filters = {
        "tf_family": ("eq", "MIKC"),
        "go_terms": ("eq", "GO:1"),
        "pfam_desc": ("eq", "DomainA"),
    }

    result = service._apply_filters(
        df,
        filters,
        filter_chain={
            "columns": ["tf_family", "go_terms", "pfam_desc"],
            "operators": ["or", "and"],
        },
    )

    assert result.index.tolist() == [0, 1, 2]


def test_filter_chain_reorder_changes_evaluation_sequence():
    service = _service()
    df = pd.DataFrame({
        "tf_family": ["MIKC", "WRKY", "MIKC", "ERF"],
        "go_terms": ["GO:1", "GO:1", "GO:2", "GO:1"],
        "pfam_desc": ["DomainA", "DomainA", "DomainA", "DomainB"],
    })
    filters = {
        "tf_family": ("eq", "MIKC"),
        "go_terms": ("eq", "GO:1"),
        "pfam_desc": ("eq", "DomainA"),
    }

    result = service._apply_filters(
        df,
        filters,
        filter_chain={
            "columns": ["pfam_desc", "tf_family", "go_terms"],
            "operators": ["or", "and"],
        },
    )

    assert result.index.tolist() == [0, 1]


def test_filter_chain_respects_explicit_parentheses():
    service = _service()
    df = pd.DataFrame({
        "tf_family": ["MIKC", "MIKC", "WRKY", "ERF"],
        "go_terms": ["GO:1", "GO:2", "GO:2", "GO:3"],
        "pfam_desc": ["DomainB", "DomainA", "DomainA", "DomainA"],
        "is_tf": [False, False, True, False],
    })
    filters = {
        "tf_family": ("eq", "MIKC"),
        "go_terms": ("eq", "GO:1"),
        "pfam_desc": ("eq", "DomainA"),
        "is_tf": ("eq", True),
    }

    result = service._apply_filters(
        df,
        filters,
        filter_chain={
            "columns": ["tf_family", "go_terms", "pfam_desc", "is_tf"],
            "operators": ["and", "or", "and"],
            "groups": {
                "tf_family": {"open": 1},
                "go_terms": {"close": 1},
                "pfam_desc": {"open": 1},
                "is_tf": {"close": 1},
            },
        },
    )

    assert result.index.tolist() == [0, 2]


def test_apply_filters_has_value_excludes_null_like_values():
    service = _service()
    df = pd.DataFrame({
        "tissue": ["leaf", "", None, "NA", "NaN", " root "],
    })

    result = service._apply_filters(df, {"tissue": ("has_value", True)})

    assert result.index.tolist() == [0, 5]


def test_array_filter_treats_missing_annotations_as_non_matches():
    service = _service()
    df = pd.DataFrame({
        "go_terms": pd.Series(["GO:0009908,GO:0008150", pd.NA, "GO:0008150"], dtype="string"),
    })

    result = service._apply_filters(df, {"go_terms": ("array_overlap", ["GO:0009908"])})

    assert result.index.tolist() == [0]


def test_filter_chain_array_filter_treats_missing_annotations_as_non_matches():
    service = _service()
    df = pd.DataFrame({
        "go_terms": pd.Series(["GO:0009908", pd.NA, "GO:0008150"], dtype="string"),
        "tf_family": ["MIKC", "MIKC", "WRKY"],
    })
    filters = {
        "go_terms": ("array_overlap", ["GO:0009908"]),
        "tf_family": ("eq", "MIKC"),
    }

    result = service._apply_filters(
        df,
        filters,
        filter_chain={"columns": ["go_terms", "tf_family"], "operators": ["and"]},
    )

    assert result.index.tolist() == [0]


def test_filter_chain_has_value_mask():
    service = _service()
    df = pd.DataFrame({
        "tissue": ["leaf", "", "root", "NA"],
        "condition": ["control", "control", "stress", "stress"],
    })
    filters = {
        "tissue": ("has_value", True),
        "condition": ("eq", "stress"),
    }

    result = service._apply_filters(
        df,
        filters,
        filter_chain={"columns": ["tissue", "condition"], "operators": ["and"]},
    )

    assert result.index.tolist() == [2]


def test_filter_samples_has_value_excludes_null_like_values():
    service = _service()
    obs = pd.DataFrame({"batch": ["A", "", None, "NA", "B"]}, index=["S1", "S2", "S3", "S4", "S5"])

    result = service._filter_samples(DummyAnnData(obs), {"batch": ("has_value", True)})

    assert result == {"S1", "S5"}


def test_filter_chain_not_inverts_single_column():
    service = _service()
    df = pd.DataFrame({"tf_family": ["MIKC", "WRKY", "MIKC", "ERF"]})
    filters = {"tf_family": ("eq", "MIKC")}

    result = service._apply_filters(
        df,
        filters,
        filter_chain={"columns": ["tf_family"], "operators": [], "nots": ["tf_family"]},
    )

    assert result.index.tolist() == [1, 3]


def test_filter_chain_not_combined_with_and():
    service = _service()
    df = pd.DataFrame({
        "tf_family": ["MIKC", "MIKC", "WRKY", "ERF"],
        "go_terms": ["GO:1", "GO:2", "GO:1", "GO:1"],
    })
    filters = {
        "tf_family": ("eq", "MIKC"),
        "go_terms": ("eq", "GO:1"),
    }

    # NOT tf_family AND go_terms == GO:1 -> rows where tf_family != MIKC and go_terms == GO:1
    result = service._apply_filters(
        df,
        filters,
        filter_chain={
            "columns": ["tf_family", "go_terms"],
            "operators": ["and"],
            "nots": ["tf_family"],
        },
    )

    assert result.index.tolist() == [2, 3]


def test_filter_chain_supports_independent_same_column_terms():
    """Dataset-local "custom" chain terms (frontend '+' button) target the same real
    column as a sidebar filter but carry a unique '<column>::chain::<id>' key so both
    can be independent, separately combinable terms (e.g. TF Family == MIKC OR WRKY)."""
    service = _service()
    df = pd.DataFrame({
        "tf_family": ["MIKC", "WRKY", "bHLH", "MIKC"],
    })
    filters = {
        "tf_family": ("eq", "MIKC"),
        "tf_family::chain::custom1": ("eq", "WRKY"),
    }

    result = service._apply_filters(
        df,
        filters,
        filter_chain={
            "columns": ["tf_family", "tf_family::chain::custom1"],
            "operators": ["or"],
        },
    )

    assert result.index.tolist() == [0, 1, 3]


def test_apply_filters_resolves_custom_chain_key_without_chain_payload():
    """A lone custom-chain term (no `filter_chain` payload / only 1 active filter) must
    still resolve to the real DataFrame column via the non-chain direct-filter loop."""
    service = _service()
    df = pd.DataFrame({"tf_family": ["MIKC", "WRKY", "bHLH"]})

    result = service._apply_filters(df, {"tf_family::chain::only": ("eq", "WRKY")})

    assert result.index.tolist() == [1]
