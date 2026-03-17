"""Tests for ORA background handling."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


def _load_services_module():
    services_path = Path(__file__).resolve().parents[1] / "app" / "services.py"
    spec = importlib.util.spec_from_file_location("genxbrowser_services", services_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GenXBrowserService = _load_services_module().GenXBrowserService


def test_calculate_ora_uses_annotated_universe() -> None:
    service = GenXBrowserService.__new__(GenXBrowserService)
    service._ora_background_cache = {}
    service._normalize_table_name = lambda table_name: "TS"
    service.get_row_count = lambda table_name, filters: 2

    subset_df = pd.DataFrame(
        {"pfam_desc": ["PFAM_A", ""]},
        index=["gene_a", "gene_b"],
    )
    background_df = pd.DataFrame(
        {"pfam_desc": ["PFAM_A", "PFAM_A", "PFAM_B", ""]},
        index=["gene_a", "gene_b", "gene_c", "gene_d"],
    )

    def fake_get_data(table_name, columns, filters, limit=None, include_virtual_columns=False):
        if filters:
            return subset_df.copy(), {}
        return background_df.copy(), {}

    service.get_data = fake_get_data

    result = service.calculate_ora(
        table_name="test_species",
        column_name="pfam_desc",
        filters={"tf_family": ("eq", "WRKY")},
        significance=1.0,
        top_n=10,
        min_count=1,
        column_type="text",
        topological_filter=False,
    )

    assert result["metadata"]["count"] == 2
    assert result["metadata"]["subset_size"] == 1
    assert result["metadata"]["background_size"] == 3
    assert result["metadata"]["raw_subset_size"] == 2
    assert result["metadata"]["raw_background_size"] == 4
    assert result["metadata"]["unannotated_subset_count"] == 1
    assert result["metadata"]["unannotated_background_count"] == 1
    assert result["results"][0]["attribute"] == "PFAM_A"
    assert result["results"][0]["expected_count"] == 2 / 3