"""Unit tests for the AI-assistant tool loop and tool registry."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List

import pandas as pd


def _load(name: str, relative: str):
    p = Path(__file__).resolve().parents[1] / relative
    spec = importlib.util.spec_from_file_location(name, p)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


assistant = _load("gx_assistant", "app/assistant.py")
tools = _load("gx_assistant_tools", "app/assistant_tools.py")
prompt_builder = _load("gx_prompt_builder", "app/prompt_builder.py")


# ---------------------------------------------------------------------------
# Fake DataService that mimics the subset of methods the tools call.
# ---------------------------------------------------------------------------

def _make_fake_service():
    """A minimal stand-in for DataService with two species CS, PS."""
    cs_var = pd.DataFrame({
        "genename": [f"CSG{i:03d}" for i in range(6)],
        "tf_family": ["MIKC", "MIKC", "bHLH", "MIKC", None, "GATA"],
        "ortho_id": ["OG1,OG2", "OG1", "OG3", "OG1", "OG4", "OG2,OG5"],
        "is_tf": [True, True, True, True, False, True],
        "length": [100, 200, 150, 300, 250, 180],
    }, index=[f"CSG{i:03d}" for i in range(6)])
    cs_obs = pd.DataFrame({
        "tissue": ["leaf", "root", "leaf", "flower"],
        "assigned": [1000, 2000, 1500, 800],
    }, index=[f"S{i}" for i in range(4)])

    ps_var = pd.DataFrame({
        "genename": [f"PSG{i:03d}" for i in range(3)],
        "tf_family": ["MIKC", "bHLH", None],
        "ortho_id": ["OG1", "OG3", "OG1,OG3"],
        "is_tf": [True, True, False],
    }, index=[f"PSG{i:03d}" for i in range(3)])
    ps_obs = pd.DataFrame({"tissue": ["leaf", "root"]}, index=["p0", "p1"])

    import numpy as np

    class FakeAdata:
        def __init__(self, var, obs):
            self.var = var
            self.obs = obs
            self.X = np.zeros((len(obs), len(var)))
            self.layers: Dict[str, Any] = {}
            self.n_vars = len(var)
            self.n_obs = len(obs)

    store: Dict[str, Any] = {}
    loaded = {
        "CS": FakeAdata(cs_var, cs_obs),
        "PS": FakeAdata(ps_var, ps_obs),
    }

    class FakeRegistry:
        def load(self, code, ignore_enabled=False):
            return loaded.get(code)

    entries = [
        {"table_name": "Capnoides sempervirens", "_species_code": "CS", "full_name": "Capnoides sempervirens"},
        {"table_name": "Papaver somniferum", "_species_code": "PS", "full_name": "Papaver somniferum"},
    ]

    def store_filter(payload):
        # Fake 16-char hash.
        import hashlib
        h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
        store[h] = payload
        return h

    def get_tables(include_disabled=False):
        return entries

    return SimpleNamespace(
        get_tables=get_tables,
        registry=FakeRegistry(),
        store_filter=store_filter,
        _store=store,
    )


# ---------------------------------------------------------------------------
# tool_list_schema
# ---------------------------------------------------------------------------

def test_list_schema_returns_both_species_with_columns():
    svc = _make_fake_service()
    res = tools.tool_list_schema(svc, None)
    codes = sorted(t["code"] for t in res["tables"])
    assert codes == ["CS", "PS"]
    cs = next(t for t in res["tables"] if t["code"] == "CS")
    var_names = [c["name"] for c in cs["var_columns"]]
    assert "tf_family" in var_names and "ortho_id" in var_names
    assert "heatmap" in res["views"]


# ---------------------------------------------------------------------------
# tool_resolve_value — the MIKC case
# ---------------------------------------------------------------------------

def test_resolve_value_finds_mikc_in_tf_family():
    svc = _make_fake_service()
    res = tools.tool_resolve_value(svc, query="MIKC", tables=["CS"])
    assert res["hits"], res
    top = res["hits"][0]
    assert top["column"] == "tf_family"
    assert top["value"] == "MIKC"
    assert top["match"] == "exact"
    assert top["count"] == 3
    assert top["table"] == "CS"


def test_resolve_value_substring_is_ranked_below_exact():
    svc = _make_fake_service()
    res = tools.tool_resolve_value(svc, query="MIKC")
    # First hit must be exact even across both species.
    assert res["hits"][0]["match"] == "exact"


# ---------------------------------------------------------------------------
# tool_count_rows
# ---------------------------------------------------------------------------

def test_count_rows_respects_var_filter():
    svc = _make_fake_service()
    res = tools.tool_count_rows(svc, table="CS", var_filters={"tf_family": ["MIKC"]})
    assert res["n_var_match"] == 3
    assert res["n_var_total"] == 6


def test_count_rows_unknown_table():
    svc = _make_fake_service()
    res = tools.tool_count_rows(svc, table="XX")
    assert "error" in res


# ---------------------------------------------------------------------------
# tool_top_groups — "which orthogroup is most represented?"
# ---------------------------------------------------------------------------

def test_top_groups_ortho_id_splits_arrays():
    svc = _make_fake_service()
    res = tools.tool_top_groups(
        svc, table="CS", group_column="ortho_id",
        var_filters={"tf_family": ["MIKC"]}, top_n=5,
    )
    # MIKC rows: ortho_ids "OG1,OG2", "OG1", "OG1" → OG1 appears 3×.
    assert res["top"][0]["value"] == "OG1"
    assert res["top"][0]["count"] == 3


def test_top_groups_multi_table_reports_value_coverage():
    svc = _make_fake_service()
    res = tools.tool_top_groups(
        svc, tables=["CS", "PS"], group_column="ortho_id",
        var_filters={"tf_family": ["GATA"]}, top_n=5,
    )
    first = res["top"][0]
    assert first["value"] == "OG2"
    assert first["present_in"] == ["CS"]
    assert first["absent_from"] == ["PS"]
    assert first["present_table_count"] == 1
    assert first["table_count"] == 2
    assert first["is_present_in_all_tables"] is False
    assert first["per_table_counts"] == {"CS": 1, "PS": 0}


# ---------------------------------------------------------------------------
# tool_build_deeplink
# ---------------------------------------------------------------------------

def test_build_deeplink_heatmap_returns_url_path():
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(
        svc, view="heatmap", tables=["CS"],
        filters={"filters": {"tf_family": {"value": "MIKC"}}},
    )
    assert res["url_path"].startswith("/h/CS?id=")
    assert res["view"] == "heatmap"
    assert res["tables"] == ["CS"]


def test_build_deeplink_rejects_unknown_view():
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(svc, view="rainbow", tables=["CS"])
    assert "error" in res


def test_build_deeplink_expands_all_sentinel_to_every_table():
    """`tables=['all']` should expand to every enabled species."""
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(svc, view="heatmap", tables=["all"])
    # Both fake species (CS, PS) should have been resolved.
    assert set(res["tables"]) == {"CS", "PS"}
    assert res["url_path"].startswith("/h/")


def test_build_deeplink_expands_empty_tables_when_filters_dont_drop_all():
    """An empty table list also expands to every enabled species."""
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(svc, view="ora", tables=[])
    assert set(res["tables"]) == {"CS", "PS"}


def test_build_deeplink_all_sentinel_with_filter_drops_empty_tables():
    """After expansion, the existing var-filter empty-table guard should
    still prune species whose .var rows don't match.

    PS has tf_family values {"MIKC", "bHLH", None} — filtering for
    "GATA" leaves PS empty so it must be dropped.
    """
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(
        svc, view="heatmap", tables=["all"],
        filters={"filters": {"tf_family": {"value": "GATA"}}},
    )
    assert res["tables"] == ["CS"]


def test_build_deeplink_accepts_legacy_flat_filter_shape():
    """Older prompt examples used {column: spec} directly for deeplink
    filters. The assistant guard must still count those filters instead of
    treating the request as unfiltered.
    """
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(
        svc, view="heatmap", tables=["all"],
        filters={"tf_family": {"value": "GATA", "match_mode": "or", "exact": True}},
    )
    assert res["tables"] == ["CS"]
    stored = svc._store[res["id"]]
    assert stored["filters"]["filters"]["tf_family"]["value"] == "GATA"


def test_build_deeplink_obs_filter_drops_species_without_matching_samples():
    """Sample-metadata filters (e.g. tissue=flower) must drop species
    whose .obs has zero matching samples — not fail the whole deeplink.

    The fake service has CS with one 'flower' sample and PS with no
    flower samples; filtering for tissue=flower must therefore keep CS
    and drop PS.
    """
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(
        svc, view="compare", tables=["all"],
        filters={"filters": {"tissue": {"value": "flower"}}},
    )
    assert res["tables"] == ["CS"]
    dropped = {d["table"] for d in res.get("dropped_tables", [])}
    assert "PS" in dropped


def test_build_deeplink_obs_filter_no_match_anywhere_returns_error():
    """If a sample filter has zero matches in every species the deeplink
    must refuse rather than open empty plots."""
    svc = _make_fake_service()
    res = tools.tool_build_deeplink(
        svc, view="heatmap", tables=["all"],
        filters={"filters": {"tissue": {"value": "moon-base"}}},
    )
    assert "error" in res
    assert res.get("dropped_tables")


# ---------------------------------------------------------------------------
# tool_list_view_settings — instance-aware viz settings discovery
# ---------------------------------------------------------------------------

def test_list_view_settings_marks_unavailable_layers():
    """Expression options whose backing layer is missing in the loaded
    AnnData must be returned with ``available == False``.

    The fake AnnData has no ``.layers`` (only the default ``X``), so
    every option targeting tpm/tmm/getmm should be unavailable while
    the raw-counts option stays available.
    """
    svc = _make_fake_service()
    res = tools.tool_list_view_settings(svc, view="heatmap")
    assert res["view"] == "heatmap"
    by_id = {o["id"]: o for o in res["expression_options"]}
    assert by_id["raw"]["available"] is True
    assert by_id["tpm"]["available"] is False
    assert "reason" in by_id["tpm"]
    # Color scale enum is populated.
    color_ctrl = next(c for c in res["controls"] if c.get("key") == "colorScale")
    assert "VIRIDIS" in color_ctrl["options"]


def test_list_view_settings_exposes_new_visualization_controls():
    svc = _make_fake_service()
    heatmap = tools.tool_list_view_settings(svc, view="heatmap", tables=["CS"])
    heatmap_keys = {c["key"] for c in heatmap["controls"]}
    assert {"customColOrder.enabled", "customColOrder.metadataColumn"} <= heatmap_keys

    compare = tools.tool_list_view_settings(svc, view="compare", tables=["CS"])
    compare_keys = {c["key"] for c in compare["controls"]}
    assert {"compare.groupingColumn", "customColOrder.metadataValues"} <= compare_keys

    phylo = tools.tool_list_view_settings(svc, view="phylo", tables=["CS"])
    phylo_keys = {c["key"] for c in phylo["controls"]}
    assert {"phyloTree.groupingColumn", "phyloTree.branchLengthMode"} <= phylo_keys

    ora = tools.tool_list_view_settings(svc, view="ora", tables=["CS"])
    ora_by_key = {c["key"]: c for c in ora["controls"]}
    assert "oraRowSideColor" in ora_by_key
    assert ora_by_key["significance"]["options"] == ["0.001", "0.01", "0.05"]
    assert "0.1" not in ora_by_key["significance"]["options"]


def test_list_view_settings_rejects_unknown_view():
    svc = _make_fake_service()
    res = tools.tool_list_view_settings(svc, view="rainbow")
    assert "error" in res


# ---------------------------------------------------------------------------
# dispatch_tool_call — the adapter used by the loop
# ---------------------------------------------------------------------------

def test_dispatch_unknown_tool_returns_error_not_raise():
    svc = _make_fake_service()
    res = tools.dispatch_tool_call("nope", {}, service=svc, config_manager=None)
    assert "error" in res and "nope" in res["error"]


def test_dispatch_passes_args_through():
    svc = _make_fake_service()
    res = tools.dispatch_tool_call(
        "resolve_value", {"query": "MIKC"}, service=svc, config_manager=None,
    )
    assert res["hits"]


def test_openai_schema_has_expected_tools():
    names = {t["function"]["name"] for t in tools.openai_schema()}
    assert {"list_schema", "list_view_settings", "resolve_value",
            "count_rows", "top_groups", "build_deeplink"} <= names


def test_visualization_patch_schema_is_strict_and_axis_documented():
    schema = next(
        t["function"]["parameters"]["properties"]["visualizations"]
        for t in tools.openai_schema()
        if t["function"]["name"] == "build_deeplink"
    )
    assert schema["additionalProperties"] is False
    assert "rowSideColors" in schema["properties"]
    assert "customColOrder.metadataColumn" in schema["properties"]
    assert "compare.groupingColumn" in schema["properties"]
    assert "phyloTree.groupingColumn" in schema["properties"]
    assert "row/.var metadata" in schema["description"]


# ---------------------------------------------------------------------------
# run_agentic_turn with a scripted LLM — end-to-end loop
# ---------------------------------------------------------------------------

def _make_fake_llm(script: List[Dict[str, Any]]):
    """Scripted ``_stream_with_fallback`` replacement.

    ``script`` is a list of assistant-message dicts to return in order.
    Each scripted dict is delivered as a single ``("final", msg, model)``
    event — i.e. no streaming deltas — so existing assertions about the
    final delta payload still hold.
    """
    calls_left = list(script)

    def fake(cfg, messages, *, tools=None):
        if not calls_left:
            yield ("final", {"content": "done", "role": "assistant"}, "fake")
            return
        yield ("final", calls_left.pop(0), "fake")

    return fake


def test_agentic_loop_mikc_scenario(monkeypatch):
    """Full scripted dialogue mirroring the MIKC+CS example."""
    svc = _make_fake_service()

    def dispatch(name, args):
        return tools.dispatch_tool_call(name, args, service=svc, config_manager=None)

    script = [
        # Turn 1: LLM asks resolve_value.
        {
            "role": "assistant", "content": "",
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "resolve_value",
                             "arguments": json.dumps({"query": "MIKC", "tables": ["CS"]})},
            }],
        },
        # Turn 2: build_deeplink.
        {
            "role": "assistant", "content": "",
            "tool_calls": [{
                "id": "c2", "type": "function",
                "function": {"name": "build_deeplink",
                             "arguments": json.dumps({
                                 "view": "heatmap", "tables": ["CS"],
                                 "filters": {"filters": {"tf_family": {"value": "MIKC"}}},
                             })},
            }],
        },
        # Turn 3: final textual answer.
        {
            "role": "assistant",
            "content": "Found 3 MIKC genes in CS.\n\n```add_filter\n{\"column\":\"tf_family\",\"value\":\"MIKC\"}\n```",
        },
    ]

    monkeypatch.setattr(assistant, "_stream_with_fallback", _make_fake_llm(script))

    events = list(assistant.run_agentic_turn(
        cfg={"model": "fake"},
        initial_messages=[{"role": "user", "content": "MIKC in CS als Heatmap"}],
        tools=tools.openai_schema(),
        dispatch=dispatch,
        max_iterations=6,
    ))

    types = [e["type"] for e in events]
    assert types.count("tool_start") == 2
    assert types.count("tool_result") == 2
    assert types[-2] == "delta"
    assert types[-1] == "done"

    # The second tool result must contain a valid /h/CS?id= URL.
    deeplink_result = [e for e in events if e["type"] == "tool_result" and e["name"] == "build_deeplink"][0]
    assert deeplink_result["result"]["url_path"].startswith("/h/CS?id=")

    # Final delta must contain our scripted markdown action block.
    final = [e for e in events if e["type"] == "delta"][0]
    assert "```add_filter" in final["delta"]


def test_agentic_loop_hits_iteration_cap(monkeypatch):
    """If the LLM keeps calling tools forever we must still terminate."""
    svc = _make_fake_service()

    def dispatch(name, args):
        return tools.dispatch_tool_call(name, args, service=svc, config_manager=None)

    infinite_tool_call = {
        "role": "assistant", "content": "",
        "tool_calls": [{
            "id": "x", "type": "function",
            "function": {"name": "list_schema", "arguments": "{}"},
        }],
    }
    # Exactly `max_iterations` tool-calling turns, then a final text turn for the cap-fallback.
    script = [infinite_tool_call, infinite_tool_call, {"role": "assistant", "content": "capped."}]
    monkeypatch.setattr(assistant, "_stream_with_fallback", _make_fake_llm(script))

    events = list(assistant.run_agentic_turn(
        cfg={"model": "fake"},
        initial_messages=[{"role": "user", "content": "go"}],
        tools=tools.openai_schema(),
        dispatch=dispatch,
        max_iterations=2,
    ))
    # At most `max_iterations` tool pairs; last event must be done|error.
    assert events[-1]["type"] in ("done", "error")


# ---------------------------------------------------------------------------
# prompt_builder
# ---------------------------------------------------------------------------

def test_prompt_builder_includes_all_sections():
    p = prompt_builder.build_system_prompt(
        base_prompt="CustomBase.", data_context={"x": 1}, ui_context={"view": "heatmap"},
    )
    assert "CustomBase." in p
    assert "GenXBrowser AI assistant" in p
    assert "add_filter" in p
    assert "CURRENT_DATA_CONTEXT" in p
    assert "USER_UI_CONTEXT" in p


def test_prompt_builder_truncates_huge_data_context():
    big = {"blob": "x" * 20000}
    p = prompt_builder.build_system_prompt(base_prompt="", data_context=big)
    assert "truncated" in p


def test_prompt_builder_contains_call_vs_action_guard():
    """The rule 'never print tool args as text' must be in the prompt."""
    p = prompt_builder.build_system_prompt(base_prompt="")
    assert "NEVER print tool-call arguments" in p
    assert "tool_calls" in p


# ---------------------------------------------------------------------------
# common_values (cross-species intersection)
# ---------------------------------------------------------------------------

def test_common_values_strict_intersection():
    svc = _make_fake_service()
    r = tools.dispatch_tool_call(
        "common_values",
        {"column": "ortho_id", "tables": ["CS", "PS"]},
        service=svc, config_manager=None,
    )
    assert "error" not in r
    # CS has OG1,OG2,OG3,OG4,OG5  |  PS has OG1,OG3  → intersection = {OG1,OG3}
    assert set(r["values"]) == {"OG1", "OG3"}
    assert r["n_common"] == 2
    assert r["min_tables"] == 2


def test_common_values_with_min_tables_one_union():
    svc = _make_fake_service()
    r = tools.dispatch_tool_call(
        "common_values",
        {"column": "ortho_id", "tables": ["CS", "PS"], "min_tables": 1},
        service=svc, config_manager=None,
    )
    assert set(r["values"]) == {"OG1", "OG2", "OG3", "OG4", "OG5"}


def test_top_groups_caps_top_n():
    """top_n is capped to 1000 server-side to keep context small."""
    svc = _make_fake_service()
    r = tools.dispatch_tool_call(
        "top_groups",
        {"table": "CS", "group_column": "ortho_id", "top_n": 999999},
        service=svc, config_manager=None,
    )
    assert len(r["top"]) <= 1000


# ---------------------------------------------------------------------------
# Leaked-tool-call salvage
# ---------------------------------------------------------------------------

def test_extract_leaked_tool_calls_matches_top_groups_signature():
    content = (
        "Sure, computing now.\n\n"
        "```json\n"
        "{\"table\":\"CS\",\"group_column\":\"ortho_id\","
        "\"var_filters\":{\"tf_family\":[\"MIKC\"]},\"top_n\":1,\"split_arrays\":true}\n"
        "```\n"
    )
    leaked = assistant._extract_leaked_tool_calls(content)
    assert len(leaked) == 1
    name, args, _span = leaked[0]
    assert name == "top_groups"
    assert args["group_column"] == "ortho_id"


def test_extract_leaked_ignores_real_action_blocks():
    content = (
        "```add_filter\n{\"column\":\"tf_family\",\"value\":\"MIKC\"}\n```"
    )
    assert assistant._extract_leaked_tool_calls(content) == []


def test_strip_leaked_tool_blocks_removes_span():
    content = (
        "Hello\n\n```json\n{\"query\":\"MIKC\"}\n```\n\nDone."
    )
    leaked = assistant._extract_leaked_tool_calls(content)
    cleaned = assistant._strip_leaked_tool_blocks(content, [s for _, _, s in leaked])
    assert "```" not in cleaned
    assert "Hello" in cleaned and "Done." in cleaned


def test_agentic_loop_salvages_leaked_tool_call(monkeypatch):
    """Model returns tool-args JSON as text → loop must dispatch + re-prompt."""
    svc = _make_fake_service()

    def dispatch(name, args):
        return tools.dispatch_tool_call(name, args, service=svc, config_manager=None)

    script = [
        # Turn 1: LLM leaks a top_groups call as JSON text (no tool_calls).
        {
            "role": "assistant",
            "content": (
                "Computing:\n\n```json\n"
                "{\"table\":\"CS\",\"group_column\":\"ortho_id\","
                "\"var_filters\":{\"tf_family\":[\"MIKC\"]},\"top_n\":1,\"split_arrays\":true}\n"
                "```"
            ),
        },
        # Turn 2: after salvage, LLM produces real answer.
        {
            "role": "assistant",
            "content": "The top orthogroup is OG1.\n\n```add_filter\n{\"column\":\"ortho_id\",\"value\":\"OG1\"}\n```",
        },
    ]
    monkeypatch.setattr(assistant, "_stream_with_fallback", _make_fake_llm(script))

    events = list(assistant.run_agentic_turn(
        cfg={"model": "fake"},
        initial_messages=[{"role": "user", "content": "top orthogroup"}],
        tools=tools.openai_schema(),
        dispatch=dispatch,
        max_iterations=4,
    ))

    types = [e["type"] for e in events]
    # The salvage path must emit a tool_start/tool_result for top_groups,
    # then the real final answer.
    assert types.count("tool_start") >= 1
    assert types.count("tool_result") >= 1
    tool_starts = [e for e in events if e["type"] == "tool_start"]
    assert any(e["name"] == "top_groups" for e in tool_starts)
    final = [e for e in events if e["type"] == "delta"][0]
    assert "add_filter" in final["delta"]
    assert types[-1] == "done"

