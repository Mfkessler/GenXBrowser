from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


def _load_filter_parser_module():
    parser_path = Path(__file__).resolve().parents[1] / "app" / "filter_parser.py"
    spec = importlib.util.spec_from_file_location("genxbrowser_filter_parser_has_value", parser_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


filter_parser = _load_filter_parser_module()


def test_parse_has_value_without_search_terms():
    parsed = filter_parser.parse_filter_query(
        {"tissue": {"value": "", "has_value": True}},
        {"tissue": "text"},
    )

    assert parsed == {"tissue": ("has_value", True)}


def test_apply_filter_query_has_value_excludes_null_like_values():
    df = pd.DataFrame({"tissue": ["leaf", "", None, "NULL", "none", "n/a", "NaN", "root"]})

    result = filter_parser.apply_filter_query(df, {"tissue": ("has_value", True)})

    assert result.index.tolist() == [0, 7]


def test_parse_and_apply_negated_has_value_rule():
    df = pd.DataFrame({"tissue": ["leaf", "", None, "root"]})
    parsed = filter_parser.parse_filter_query(
        {"tissue": {"has_value": True, "isNot": True}},
        {"tissue": "text"},
    )

    assert parsed == {"tissue": ("not", ("has_value", True))}
    assert filter_parser.apply_filter_query(df, parsed).index.tolist() == [1, 2]


def test_exact_array_filter_matches_whole_serialized_single_value_before_splitting():
    phrase = "Ribonuclease H1, N-terminal domain superfamily"
    df = pd.DataFrame({"ipr_desc": [phrase, "Other domain, second item", None]})
    parsed = filter_parser.parse_filter_query(
        {"ipr_desc": {"value": phrase, "exact": True}},
        {"ipr_desc": "array"},
    )

    result = filter_parser.apply_filter_query(
        df,
        parsed,
        column_separators={"ipr_desc": ","},
    )

    assert result.index.tolist() == [0]
