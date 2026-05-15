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
