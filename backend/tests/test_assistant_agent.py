from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


def _load(name: str, relative: str):
    path = Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assistant = _load("gx_assistant", "app/assistant.py")
tools = _load("gx_assistant_tools", "app/assistant_tools.py")
prompt_builder = _load("gx_prompt_builder", "app/prompt_builder.py")


def _service(*, layers=None):
    import numpy as np

    class Adata:
        def __init__(self):
            self.var = pd.DataFrame({
                "tf_family": ["MIKC", "MIKC", "bHLH", None],
                "ortho_id": ["OG1,OG2", "OG1", "OG3", "OG4"],
                "go_terms": ["GO:0009908", None, "GO:1", None],
                "ipr_desc": ["Ribonuclease H1, N-terminal domain superfamily|Other domain", None, None, None],
            })
            self.obs = pd.DataFrame({"tissue": ["leaf", "root"], "group": ["A", None]})
            self.layers = {name: np.zeros((2, 4)) for name in (layers or [])}
            self.X = np.zeros((2, 4))
            self.n_vars = 4
            self.n_obs = 2

    adata = Adata()

    class Registry:
        def load(self, code, ignore_enabled=False):
            return adata if code == "CS" else None

    stored = {}

    def store_filter(payload):
        stored["state"] = payload
        return "0123456789abcdef"

    return SimpleNamespace(
        registry=Registry(), store_filter=store_filter, stored=stored,
        get_tables=lambda include_disabled=False: [{
            "table_name": "capnoides_sempervirens", "_species_code": "CS",
            "full_name": "Capnoides sempervirens",
        }],
    )


def _config():
    return SimpleNamespace(
        get_config=lambda: {}, get_column_mappings=lambda: {},
        get_column_definitions=lambda: {
            "tf_family": {"display_name": "TF Family", "type": "text", "visible": True, "filterable": True},
            "ortho_id": {"display_name": "Orthogroup", "type": "array", "is_array": True, "array_separator": ",", "visible": True, "filterable": True},
            "go_terms": {"display_name": "GO Terms", "type": "array", "is_array": True, "array_separator": ",", "visible": True, "filterable": True},
            "ipr_desc": {"display_name": "InterPro Desc", "type": "array", "is_array": True, "visible": True, "filterable": True},
            "tissue": {"display_name": "Tissue", "type": "text", "visible": True, "filterable": True},
            "group": {"display_name": "Group", "type": "text", "visible": True, "filterable": True},
        },
    )


def test_schema_exposes_native_tools():
    assert {item["function"]["name"] for item in tools.openai_schema()} == {
        "get_current_view", "search_metadata", "compute_analytics", "build_state_token",
    }
    state_tool = next(
        item["function"] for item in tools.openai_schema()
        if item["function"]["name"] == "build_state_token"
    )
    assert "filters" not in state_tool["parameters"]["required"]


def test_get_current_view_returns_authoritative_read_only_snapshot():
    context = {
        "view": "CompareView",
        "route": "/c/CS",
        "tables": ["CS"],
        "filters": {"filters": {"tf_family": {"value": "MIKC"}}},
        "visualizations": {
            "compare": {"groupingColumn": "group", "expression": "zscore"},
            "oraTopN": 10,
        },
    }
    result = tools.dispatch_tool_call(
        "get_current_view", {}, service=_service(), config_manager=_config(), client_context=context,
    )
    assert result == {
        "view": "compare",
        "route": "/c/CS",
        "tables": ["CS"],
        "filters": context["filters"],
        "visualizations": {
            "compare.expression": "zscore",
            "compare.groupingColumn": "group",
        },
        "analysis_results": {},
        "dataset_state": {},
    }


def test_search_metadata_resolves_visible_value_and_display_name():
    result = tools.dispatch_tool_call(
        "search_metadata", {"query": "MIKC", "tables": ["CS"]},
        service=_service(), config_manager=_config(),
    )
    assert result["hits"][0]["column"] == "tf_family"
    assert result["hits"][0]["display_name"] == "TF Family"
    assert result["hits"][0]["value"] == "MIKC"


def test_search_metadata_with_column_bypasses_full_value_index(monkeypatch):
    monkeypatch.setattr(
        tools, "_get_value_counters",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("full index should not be built")),
    )
    result = tools.dispatch_tool_call(
        "search_metadata", {"query": "OG1", "column": "Orthogroup", "tables": ["CS"]},
        service=_service(), config_manager=_config(),
    )
    assert result["hits"][0]["column"] == "ortho_id"
    assert result["hits"][0]["value"] == "OG1"


def test_search_metadata_recognizes_expression_option_as_ui_control():
    result = tools.dispatch_tool_call(
        "search_metadata", {"query": "Z Score", "tables": ["CS"]},
        service=_service(layers=["getmm"]), config_manager=_config(),
    )
    assert result["status"] == "ui_control"
    assert any("zscore" in control["options"] for control in result["controls"])


def test_search_metadata_rejects_hidden_column():
    result = tools.dispatch_tool_call(
        "search_metadata", {"query": "length", "column": "length", "tables": ["CS"]},
        service=_service(), config_manager=_config(),
    )
    assert result["status"] == "unavailable"


def test_search_metadata_exactly_matches_high_cardinality_column():
    result = tools.dispatch_tool_call(
        "search_metadata", {
            "query": "Ribonuclease H1, N-terminal domain superfamily",
            "column": "InterPro Desc",
            "tables": ["CS"],
        }, service=_service(), config_manager=_config(),
    )
    assert result["hits"][0]["column"] == "ipr_desc"
    assert result["hits"][0]["match"] == "exact"


def test_compute_analytics_count_rank_and_has_value():
    service = _service()
    count = tools.dispatch_tool_call(
        "compute_analytics", {"operation": "count", "tables": ["CS"], "filters": {
            "var_filters": {"TF Family": {"has_value": True}},
            "obs_filters": {"Tissue": {"has_value": True}},
        }}, service=service, config_manager=_config(),
    )
    assert count["n_var_match"] == 3
    assert count["n_obs_match"] == 2

    rank = tools.dispatch_tool_call(
        "compute_analytics", {"operation": "rank", "tables": ["CS"],
         "filters": {"var_filters": {"tf_family": {"value": "MIKC"}}},
         "target_column": "Orthogroup"},
        service=service, config_manager=_config(),
    )
    assert rank["top_value"] == "OG1"


def test_build_state_token_preserves_live_state_and_updates_in_place():
    result = tools.dispatch_tool_call(
        "build_state_token", {"view": "heatmap", "tables": ["CS"], "filters": {},
         "viz_patches": {"rowSideColors": ["tf_family"]}},
        service=_service(), config_manager=_config(),
        client_context={
            "view": "heatmap", "tables": ["CS"],
            "filters": {"filters": {"tf_family": {"value": "MIKC", "exact": True}}},
            "visualizations": {"rowSideColors": []},
        },
    )
    token = result["state_token"]
    assert token["url_path"] == ""
    assert token["filters"]["filters"]["tf_family"]["value"] == "MIKC"
    assert token["viz_patches"] == {"rowSideColors": ["tf_family"]}


def test_build_state_token_uses_manifest_controls_for_grouping_and_compare_expression():
    service = _service(layers=["getmm"])
    def metadata_columns(adata, *, sample_metadata=False):
        frame = adata.obs if sample_metadata else adata.var
        return [
            {
                "column_name": str(column),
                "display_name": _config().get_column_definitions().get(str(column), {}).get("display_name", str(column)),
                "is_default_trait": sample_metadata and column == "group",
            }
            for column in frame.columns
        ]

    service._get_configured_metadata_columns = metadata_columns
    result = tools.dispatch_tool_call(
        "build_state_token", {
            "view": "compare", "tables": ["CS"], "filters": {},
            "viz_patches": {
                "compare": {"groupingColumn": "Group", "expression": "zscore"},
            },
        }, service=service, config_manager=_config(),
        client_context={"view": "compare", "tables": ["CS"], "filters": {"filters": {}}},
    )
    assert result["state_token"]["viz_patches"] == {
        "compare.groupingColumn": "group",
        "compare.expression": "zscore",
    }


def test_build_state_token_rejects_control_option_unavailable_for_selected_tables():
    result = tools.dispatch_tool_call(
        "build_state_token", {
            "view": "compare", "tables": ["CS"], "filters": {},
            "viz_patches": {"compare.expression": "zscore-tpm"},
        }, service=_service(), config_manager=_config(),
        client_context={"view": "compare", "tables": ["CS"], "filters": {"filters": {}}},
    )
    assert "Unsupported compare.expression" in result["error"]


def test_build_state_token_accepts_all_native_export_formats():
    actions = [
        "export_png", "export_pdf", "export_svg",
        "export_tsv", "export_csv", "export_xlsx", "export_json",
    ]
    result = tools.dispatch_tool_call(
        "build_state_token", {
            "view": "heatmap", "tables": ["CS"], "trigger_actions": actions,
        }, service=_service(), config_manager=_config(),
        client_context={"view": "heatmap", "tables": ["CS"], "filters": {"filters": {}}},
    )
    assert result["state_token"]["trigger_actions"] == actions


def test_build_state_token_clear_existing_removes_all_filter_scopes():
    result = tools.dispatch_tool_call(
        "build_state_token", {
            "view": "heatmap", "tables": ["CS"],
            "filters": {
                "clear_existing": True,
                "var_filters": {"tf_family": {"value": "bHLH"}},
            },
        }, service=_service(), config_manager=_config(),
        client_context={
            "view": "heatmap", "tables": ["CS"],
            "filters": {
                "filters": {"ortho_id": {"value": "OG1"}},
                "datasetIdFilters": {"capnoides_sempervirens": {"value": "gene-1"}},
                "localDatasetChains": {"capnoides_sempervirens": {"columns": ["ortho_id"]}},
                "localCustomFilters": {"capnoides_sempervirens": {"term": {}}},
            },
        },
    )
    state = result["state_token"]["filters"]
    assert state["filters"] == {"tf_family": {"value": "bHLH", "exact": True}}
    assert state["datasetIdFilters"] == {}
    assert state["localDatasetChains"] == {}
    assert state["localCustomFilters"] == {}


def test_build_state_token_navigates_and_normalizes_concrete_filter():
    result = tools.dispatch_tool_call(
        "build_state_token", {"view": "heatmap", "tables": ["CS"], "filters": {
            "var_filters": {"tf_family": {"value": "MIKC", "has_value": True}},
        }}, service=_service(), config_manager=_config(),
    )
    token = result["state_token"]
    assert token["url_path"].startswith("/h/capnoides_sempervirens?id=")
    assert token["filters"]["filters"]["tf_family"] == {"value": "MIKC", "exact": True}


def test_build_state_token_canonicalizes_scalar_filter_before_navigation_guard():
    result = tools.dispatch_tool_call(
        "build_state_token", {
            "view": "phylo", "tables": ["CS"],
            "filters": {"var_filters": {"ortho_id": "OG1"}},
        }, service=_service(), config_manager=_config(),
    )
    token = result["state_token"]
    assert token["url_path"].startswith("/p/capnoides_sempervirens?id=")
    assert token["filters"]["filters"]["ortho_id"] == {"value": "OG1", "exact": True}


def test_filter_normalization_preserves_scalar_punctuation_and_structures_lists():
    phrase = "Ribonuclease H1, N-terminal domain superfamily"
    assert tools.normalize_filter_pipe_value(phrase) == phrase
    assert tools.normalize_filter_pipe_value(["MIKC", "bHLH"]) == "MIKC|bHLH"


def test_build_state_token_rejects_no_op_and_wrong_axis():
    context = {
        "view": "heatmap", "tables": ["CS"],
        "filters": {"filters": {"tf_family": {"value": "MIKC", "exact": True}}},
    }
    no_op = tools.dispatch_tool_call(
        "build_state_token", {"view": "heatmap", "tables": ["CS"], "filters": {
            "var_filters": {"tf_family": {"value": "MIKC", "exact": True}},
        }}, service=_service(), config_manager=_config(), client_context=context,
    )
    assert no_op["no_op"] is True

    wrong_axis = tools.dispatch_tool_call(
        "build_state_token", {"view": "heatmap", "tables": ["CS"], "filters": {
            "obs_filters": {"tf_family": {"value": "MIKC"}},
        }}, service=_service(), config_manager=_config(),
    )
    assert "not available" in wrong_axis["error"]


def test_agent_loop_materializes_state_token(monkeypatch):
    script = [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "state", "type": "function", "function": {
                "name": "build_state_token", "arguments": json.dumps({
                    "view": "heatmap", "tables": ["CS"],
                    "filters": {"var_filters": {"tf_family": {"value": "MIKC"}}},
                }),
            },
        }]},
        {"role": "assistant", "content": "MIKC is shown."},
    ]

    def fake_stream(cfg, messages, *, tools=None, tool_choice=None):
        yield ("final", script.pop(0), "fake")

    monkeypatch.setattr(assistant, "_stream_with_fallback", fake_stream)
    service = _service()
    events = list(assistant.run_agentic_turn(
        {"model": "fake"}, [{"role": "user", "content": "Show MIKC"}],
        tools=tools.openai_schema(),
        dispatch=lambda name, args: tools.dispatch_tool_call(name, args, service=service, config_manager=_config()),
    ))
    final = [event for event in events if event["type"] == "delta"][-1]["delta"]
    assert "```state_token" in final
    assert "tf_family" in final


def test_agent_loop_disables_tools_after_successful_state_token(monkeypatch):
    choices = []
    script = [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "state", "type": "function", "function": {
                "name": "build_state_token", "arguments": json.dumps({
                    "view": "heatmap", "tables": ["CS"], "filters": {},
                    "viz_patches": {"rowLabel": False},
                }),
            },
        }]},
        {"role": "assistant", "content": "Updated."},
    ]

    def fake_stream(cfg, messages, *, tools=None, tool_choice=None):
        choices.append(tool_choice)
        yield ("final", script.pop(0), "fake")

    monkeypatch.setattr(assistant, "_stream_with_fallback", fake_stream)
    list(assistant.run_agentic_turn(
        {"model": "fake"}, [{"role": "user", "content": "Hide row labels"}],
        tools=tools.openai_schema(),
        dispatch=lambda name, args: tools.dispatch_tool_call(
            name, args, service=_service(), config_manager=_config(),
        ),
    ))
    assert choices == ["required", "none"]


def test_agent_loop_hands_verified_value_to_next_state_call(monkeypatch):
    second_messages = []
    script = [
        {"role": "assistant", "content": "", "tool_calls": [{
            "id": "search", "type": "function", "function": {
                "name": "search_metadata", "arguments": json.dumps({
                    "query": "OG1", "column": "Orthogroup", "tables": ["CS"],
                }),
            },
        }]},
        {"role": "assistant", "content": "Verified."},
    ]

    def fake_stream(cfg, messages, *, tools=None, tool_choice=None):
        if len(script) == 1:
            second_messages.extend(messages)
        yield ("final", script.pop(0), "fake")

    monkeypatch.setattr(assistant, "_stream_with_fallback", fake_stream)
    list(assistant.run_agentic_turn(
        {"model": "fake"}, [{"role": "user", "content": "Open OG1"}],
        tools=tools.openai_schema(),
        dispatch=lambda name, args: tools.dispatch_tool_call(
            name, args, service=_service(), config_manager=_config(),
        ),
    ))
    runtime = next(
        message["content"] for message in second_messages
        if message.get("role") == "user" and message["content"].startswith("[runtime]")
    )
    assert '"column": "ortho_id"' in runtime
    assert '"value": "OG1"' in runtime
    assert "var_filters" in runtime


def test_manifest_and_prompt_use_only_unified_contract():
    manifest = tools.build_instance_manifest(_service(), _config())
    assert manifest["datasets"][0]["id"] == "capnoides_sempervirens"
    prompt = prompt_builder.build_system_prompt(
        base_prompt="", data_context=manifest, ui_context={"current_state": {}},
    )
    assert all(name in prompt for name in ("search_metadata", "compute_analytics", "build_state_token"))
    assert "build_deeplink" not in prompt