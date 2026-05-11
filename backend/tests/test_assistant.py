"""Tests for the AI assistant config helpers and LLM proxy module."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


def _load_module(name: str, relative_path: str):
    module_path = Path(__file__).resolve().parents[1] / relative_path
    spec = importlib.util.spec_from_file_location(name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


assistant = _load_module("genxbrowser_assistant", "app/assistant.py")


class DummyCM:
    def __init__(self, cfg):
        self._cfg = {"llm_config": cfg} if cfg is not None else {}

    def get_config(self):
        return self._cfg


def test_is_assistant_enabled_requires_all_fields():
    assert assistant.is_assistant_enabled(DummyCM(None)) is False
    assert assistant.is_assistant_enabled(DummyCM({})) is False
    assert assistant.is_assistant_enabled(DummyCM({"enabled": True})) is False
    assert assistant.is_assistant_enabled(DummyCM({
        "enabled": True, "api_base": "x", "api_key": "y"
    })) is False  # missing model
    assert assistant.is_assistant_enabled(DummyCM({
        "enabled": True, "api_base": "x", "api_key": "y", "model": "m"
    })) is True
    assert assistant.is_assistant_enabled(DummyCM({
        "enabled": False, "api_base": "x", "api_key": "y", "model": "m"
    })) is False


def test_redact_llm_config_hides_api_key():
    red = assistant.redact_llm_config({"api_key": "secret-123", "model": "m"})
    assert red["api_key"] == assistant.REDACTED_PLACEHOLDER
    assert red["model"] == "m"
    # Missing key is not added.
    assert "api_key" not in assistant.redact_llm_config({"model": "m"})


def test_merge_preserves_stored_api_key_on_placeholder_or_empty():
    stored = {"api_key": "real-secret", "model": "m1", "api_base": "b1"}
    incoming_redacted = {"api_key": assistant.REDACTED_PLACEHOLDER, "model": "m2"}
    merged = assistant.merge_llm_config_update(stored, incoming_redacted)
    assert merged["api_key"] == "real-secret"
    assert merged["model"] == "m2"
    assert merged["api_base"] == "b1"

    merged_empty = assistant.merge_llm_config_update(stored, {"api_key": "", "model": "m3"})
    assert merged_empty["api_key"] == "real-secret"

    merged_new = assistant.merge_llm_config_update(stored, {"api_key": "new-secret"})
    assert merged_new["api_key"] == "new-secret"


def test_rate_limiter_blocks_after_threshold():
    rl = assistant.RateLimiter(max_requests=3, window_seconds=60)
    assert rl.allow("ip-a")[0]
    assert rl.allow("ip-a")[0]
    assert rl.allow("ip-a")[0]
    ok, retry = rl.allow("ip-a")
    assert ok is False
    assert retry > 0
    # Other keys are independent.
    assert rl.allow("ip-b")[0]


def test_build_url_handles_v1_suffix():
    assert assistant._build_url("https://x.example", "chat/completions") == "https://x.example/v1/chat/completions"
    assert assistant._build_url("https://x.example/", "chat/completions") == "https://x.example/v1/chat/completions"
    assert assistant._build_url("https://x.example/v1", "chat/completions") == "https://x.example/v1/chat/completions"


def test_test_connection_returns_ok_on_success():
    cfg = {"api_base": "https://x", "api_key": "k", "model": "m", "request_timeout_s": 5, "max_tokens": 8, "temperature": 0.1}
    fake_body = json.dumps({"model": "m", "choices": [{"message": {"content": "ok"}}]}).encode()

    fake_resp = MagicMock()
    fake_resp.read.return_value = fake_body
    fake_resp.close.return_value = None

    with patch.object(assistant, "_post_json", return_value=fake_resp):
        result = assistant.test_connection(cfg)
    assert result["ok"] is True
    assert result["model"] == "m"


def test_test_connection_missing_fields():
    result = assistant.test_connection({"api_base": "", "api_key": "", "model": ""})
    assert result["ok"] is False


def test_complete_chat_falls_back_to_secondary_model():
    cfg = {"api_base": "https://x", "api_key": "k", "model": "primary", "fallback_model": "fallback"}

    calls = []

    def fake_call(cfg_, messages, stream=False, model_override=None):
        calls.append(model_override)
        if model_override == "primary":
            import urllib.error
            raise urllib.error.HTTPError("u", 500, "boom", {}, None)
        fake_resp = MagicMock()
        fake_resp.read.return_value = json.dumps({"model": "fallback", "choices": [{"message": {"content": "hi"}}]}).encode()
        fake_resp.close.return_value = None
        return fake_resp

    with patch.object(assistant, "call_chat_completion", side_effect=fake_call):
        result = assistant.complete_chat(cfg, [{"role": "user", "content": "hey"}])
    assert result["ok"] is True
    assert result["model"] == "fallback"
    assert calls == ["primary", "fallback"]


def test_streaming_timeout_is_capped_below_worker_timeout(monkeypatch):
    cfg = {
        "api_base": "https://x",
        "api_key": "k",
        "model": "primary",
        "fallback_model": "fallback",
        "request_timeout_s": 60,
    }
    captured = {}

    def fake_post(url, api_key, payload, timeout, stream=False):
        captured["timeout"] = timeout
        captured["stream"] = stream
        fake_resp = MagicMock()
        fake_resp.read.return_value = b'{"choices":[{"message":{"content":"ok"}}]}'
        fake_resp.close.return_value = None
        return fake_resp

    monkeypatch.setenv("GUNICORN_TIMEOUT", "120")
    with patch.object(assistant, "_post_json", side_effect=fake_post):
        assistant.call_chat_completion(cfg, [{"role": "user", "content": "hi"}], stream=True)

    assert captured["stream"] is True
    assert captured["timeout"] <= 50
