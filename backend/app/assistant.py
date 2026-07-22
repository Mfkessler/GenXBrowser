"""
AI Assistant integration for GenXBrowser.

Implements a thin OpenAI-compatible chat proxy with primary/fallback model
selection, optional SSE streaming, and a helper for building the system
context that describes currently loaded datasets. Configuration is read from
``project_config.json`` under ``llm_config`` and can be edited via the admin
panel.

All outbound HTTP uses the stdlib (``urllib.request``) to avoid adding a new
dependency. No API-key material ever leaks to clients: GETs on the config
return a redacted placeholder, and this module only sends the key in the
``Authorization`` header of the upstream request.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from threading import Lock
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

REDACTED_PLACEHOLDER = "__set__"


# ----------------------------------------------------------------------------
# Config helpers
# ----------------------------------------------------------------------------

def get_llm_config(config_manager) -> Dict[str, Any]:
    """Return the raw ``llm_config`` dict (may include the real api_key)."""
    cfg = config_manager.get_config().get("llm_config") or {}
    return dict(cfg)


def is_assistant_enabled(config_manager) -> bool:
    """Assistant is enabled iff explicitly flagged and endpoint + key present."""
    cfg = get_llm_config(config_manager)
    return bool(
        cfg.get("enabled")
        and (cfg.get("api_base") or "").strip()
        and (cfg.get("api_key") or "").strip()
        and (cfg.get("model") or "").strip()
    )


def redact_llm_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with ``api_key`` replaced by a placeholder when set."""
    redacted = dict(cfg or {})
    if redacted.get("api_key"):
        redacted["api_key"] = REDACTED_PLACEHOLDER
    return redacted


def merge_llm_config_update(current: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge an admin update into the stored config.

    Preserves the existing ``api_key`` when the incoming value is missing,
    empty, or the redacted placeholder. This allows the admin UI to submit
    the config form without clearing the secret.
    """
    merged = dict(current or {})
    for key, value in (incoming or {}).items():
        if key == "api_key":
            if value in (None, "", REDACTED_PLACEHOLDER):
                continue
            merged["api_key"] = value
        else:
            merged[key] = value
    return merged


# ----------------------------------------------------------------------------
# Rate limiting (in-memory token bucket, per IP)
# ----------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window limiter where each call can carry a weight.

    Used both as a plain "max N requests / window" guard (the chat endpoint
    treats one request as weight=1) and as an iteration-weighted guard for
    the agentic loop, where one chat turn that fires N tool calls counts
    as N requests instead of 1. This keeps a single very-chatty session
    from monopolising the upstream LLM budget without hurting short turns.

    The window is implemented as a deque of (timestamp, weight) tuples
    plus a running sum so the hot path stays O(1) amortised.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max = max_requests
        self.window = window_seconds
        self._hits: Dict[str, deque] = {}
        self._sum: Dict[str, int] = {}
        self._lock = Lock()

    def allow(self, key: str, weight: int = 1) -> Tuple[bool, int]:
        try:
            w = max(1, int(weight))
        except (TypeError, ValueError):
            w = 1
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            cur_sum = self._sum.get(key, 0)
            while q and now - q[0][0] > self.window:
                _, old_w = q.popleft()
                cur_sum -= old_w
            if cur_sum + w > self.max:
                retry_in = int(self.window - (now - q[0][0])) + 1 if q else 1
                self._sum[key] = cur_sum
                return False, retry_in
            q.append((now, w))
            self._sum[key] = cur_sum + w
            return True, 0

    def charge(self, key: str, weight: int) -> None:
        """Retroactively add `weight - 1` more units after a request finished.

        The chat endpoint pre-charges weight=1 in `allow()`, then calls this
        once the agentic loop knows how many tool iterations actually ran.
        """
        try:
            extra = max(0, int(weight) - 1)
        except (TypeError, ValueError):
            extra = 0
        if extra == 0:
            return
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            q.append((now, extra))
            self._sum[key] = self._sum.get(key, 0) + extra


# ----------------------------------------------------------------------------
# Upstream call (OpenAI-compatible /v1/chat/completions)
# ----------------------------------------------------------------------------

def _build_url(api_base: str, path: str) -> str:
    base = (api_base or "").rstrip("/")
    path = path.lstrip("/")
    if base.endswith("/v1"):
        return f"{base}/{path}"
    return f"{base}/v1/{path}"


def _post_json(
    url: str,
    api_key: str,
    payload: Dict[str, Any],
    timeout: int,
    stream: bool = False,
) -> urllib.request.addinfourl:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": "GenXBrowser-Assistant/1.0",
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def call_chat_completion(
    cfg: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    stream: bool = False,
    model_override: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[Any] = None,
) -> urllib.request.addinfourl:
    """Send a chat completion request. Caller is responsible for closing.

    When ``tools`` is provided the payload uses OpenAI tool-calling shape.
    Messages may then include ``role: "tool"`` entries and assistant turns
    may carry ``tool_calls``; both stay untouched on the way to the upstream.
    """
    model = model_override or cfg.get("model")
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": float(cfg.get("temperature", 0.2)),
        "max_tokens": int(cfg.get("max_tokens", 1024)),
        "stream": bool(stream),
    }
    if tools:
        payload["tools"] = tools
        payload["parallel_tool_calls"] = False
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    url = _build_url(cfg["api_base"], "chat/completions")
    base_timeout = int(cfg.get("request_timeout_s", 60))
    # Gunicorn kills a sync/gthread worker when a request exceeds its worker
    # timeout. The assistant may try both primary and fallback models, so a
    # single upstream read timeout must fit safely inside that outer budget.
    # Otherwise an unavailable LLM endpoint turns into a full backend worker
    # abort instead of a recoverable chat error.
    try:
        worker_timeout = int(os.environ.get("GUNICORN_TIMEOUT", "120"))
    except (TypeError, ValueError):
        worker_timeout = 120
    model_attempts = 2 if cfg.get("fallback_model") else 1
    per_attempt_cap = max(10, int((worker_timeout - 20) / max(1, model_attempts)))
    if stream:
        configured_stream_timeout = cfg.get("stream_timeout_s") or os.environ.get("GENX_LLM_STREAM_TIMEOUT")
        try:
            stream_timeout = int(configured_stream_timeout) if configured_stream_timeout else min(base_timeout, 45)
        except (TypeError, ValueError):
            stream_timeout = min(base_timeout, 45)
        timeout_s = min(stream_timeout, per_attempt_cap)
    else:
        timeout_s = min(base_timeout, per_attempt_cap)
    return _post_json(url, cfg["api_key"], payload, timeout_s, stream=stream)


def test_connection(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a minimal chat completion probe against the configured endpoint."""
    if not cfg.get("api_base") or not cfg.get("api_key") or not cfg.get("model"):
        return {"ok": False, "error": "api_base, api_key and model are required"}
    probe_messages = [
        {"role": "system", "content": "You are a connectivity probe. Reply with the single word 'ok'."},
        {"role": "user", "content": "ping"},
    ]
    started = time.monotonic()
    try:
        resp = call_chat_completion(cfg, probe_messages, stream=False)
        try:
            body = resp.read().decode("utf-8", errors="replace")
        finally:
            resp.close()
        data = json.loads(body)
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        return {
            "ok": True,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "model": data.get("model") or cfg.get("model"),
            "sample": (content or "")[:80],
        }
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:500]
        return {"ok": False, "error": f"HTTP {e.code}: {detail}", "latency_ms": int((time.monotonic() - started) * 1000)}
    except Exception as e:
        return {"ok": False, "error": str(e), "latency_ms": int((time.monotonic() - started) * 1000)}



# ----------------------------------------------------------------------------
# Agentic tool-calling loop
# ----------------------------------------------------------------------------

def _complete_once(
    cfg: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[List[Dict[str, Any]]],
    model_override: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Single non-streaming completion. Returns (assistant_message, model, error)."""
    try:
        resp = call_chat_completion(
            cfg, messages, stream=False, model_override=model_override,
            tools=tools, tool_choice="auto" if tools else None,
        )
        try:
            body = resp.read().decode("utf-8", errors="replace")
        finally:
            resp.close()
        data = json.loads(body)
        msg = data.get("choices", [{}])[0].get("message") or {}
        return msg, data.get("model") or model_override, None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        return None, None, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return None, None, f"{type(e).__name__}: {e}"


def _stream_once(
    cfg: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[List[Dict[str, Any]]],
    model_override: Optional[str] = None,
    tool_choice: Optional[str] = None,
) -> Iterator[Tuple[str, Any]]:
    """Stream a single chat completion. Yields tuples:

    - ``("delta", text)`` for each incremental content chunk.
    - ``("final", message_dict, model_used)`` once the upstream finishes —
      ``message_dict`` is a fully-assembled assistant message with both
      accumulated ``content`` and (if any) the assembled ``tool_calls``.
    - ``("error", err_string)`` on transport / HTTP failure (no final).

    The streaming variant lets the agentic loop forward content tokens to
    the SSE client AS THEY ARRIVE rather than waiting for the whole
    completion. Tool calls are buffered (by ``index``) and only acted on
    at end-of-stream — exactly the same shape the non-streaming path used
    to emit, so the rest of the loop stays untouched.
    """
    try:
        resp = call_chat_completion(
            cfg, messages, stream=True, model_override=model_override,
            tools=tools, tool_choice=tool_choice if tools else None,
        )
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        yield ("error", f"HTTP {e.code}: {detail}")
        return
    except Exception as e:  # noqa: BLE001
        yield ("error", f"{type(e).__name__}: {e}")
        return

    content_parts: List[str] = []
    tc_acc: Dict[int, Dict[str, Any]] = {}
    used_model = model_override

    try:
        for raw in resp:
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if obj.get("model"):
                used_model = obj["model"]
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content")
            if content:
                content_parts.append(content)
                yield ("delta", content)
            for tc in delta.get("tool_calls") or []:
                idx = tc.get("index", 0)
                slot = tc_acc.setdefault(idx, {
                    "id": "",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                })
                if tc.get("id"):
                    slot["id"] = tc["id"]
                if tc.get("type"):
                    slot["type"] = tc["type"]
                fn = tc.get("function") or {}
                if fn.get("name"):
                    slot["function"]["name"] += fn["name"]
                if fn.get("arguments"):
                    slot["function"]["arguments"] += fn["arguments"]
    finally:
        try:
            resp.close()
        except Exception:  # noqa: BLE001
            pass

    final_msg: Dict[str, Any] = {
        "role": "assistant",
        "content": "".join(content_parts),
    }
    if tc_acc:
        final_msg["tool_calls"] = [tc_acc[i] for i in sorted(tc_acc.keys())]
    yield ("final", final_msg, used_model)


def _stream_with_fallback(
    cfg: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[List[Dict[str, Any]]],
    tool_choice: Optional[str] = None,
) -> Iterator[Tuple[str, Any]]:
    """Stream from primary model, fall back once on transport error.

    Critical: only switches to fallback if the primary fails BEFORE any
    content / tool_call delta has been emitted to the caller. Once we
    started streaming content, the caller's UI is already showing tokens
    from the primary model — silently restarting with a different model
    would either duplicate tokens or jump in the middle.
    """
    last_err: Optional[str] = None
    for model in [m for m in (cfg.get("model"), cfg.get("fallback_model")) if m]:
        emitted = False
        had_error = False
        for ev in _stream_once(
            cfg, messages, tools=tools, model_override=model,
            tool_choice=tool_choice,
        ):
            kind = ev[0]
            if kind == "error":
                last_err = f"{ev[1]} (model={model})"
                logger.warning("LLM streaming failure: %s", last_err)
                if tools and _tool_calling_unsupported_error(ev[1]):
                    had_error = True
                    break
                if emitted:
                    # Already streamed partial output to client — don't
                    # silently retry; surface the error.
                    yield ("error", last_err)
                    return
                had_error = True
                break
            if kind == "delta":
                emitted = True
            yield ev
        if not had_error:
            return
    yield ("error", last_err or "no usable model")


def _tool_calling_unsupported_error(error: Any) -> bool:
    text = str(error or "").lower()
    return (
        "unexpected keyword argument 'tools'" in text
        or 'unexpected keyword argument "tools"' in text
        or "got an unexpected keyword argument tools" in text
        or "does not support tools" in text
        or "tool_calls not supported" in text
    )


def _complete_with_fallback(
    cfg: Dict[str, Any],
    messages: List[Dict[str, Any]],
    *,
    tools: Optional[List[Dict[str, Any]]],
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """Try primary model, fall back once to ``fallback_model``."""
    last_err: Optional[str] = None
    for model in [m for m in (cfg.get("model"), cfg.get("fallback_model")) if m]:
        msg, used, err = _complete_once(cfg, messages, tools=tools, model_override=model)
        if msg is not None:
            return msg, used, None
        last_err = f"{err} (model={model})"
        logger.warning("LLM upstream failure: %s", last_err)
        if tools and _tool_calling_unsupported_error(err):
            continue
    return None, None, last_err or "no usable model"



def run_agentic_turn(
    cfg: Dict[str, Any],
    initial_messages: List[Dict[str, Any]],
    *,
    tools: List[Dict[str, Any]],
    dispatch: "callable[[str, Dict[str, Any]], Dict[str, Any]]",
    max_iterations: int = 6,
    tool_deadline_s: float = 90.0,
) -> Iterator[Dict[str, Any]]:
    """Drive a tool-calling loop and yield progress events.

    Yields dicts of shape ``{"type": "tool_start"|"tool_result"|"delta"|"done"|"error", ...}``.

    The caller (SSE handler) is responsible for translating events into wire
    frames. The final ``delta`` event contains the assistant's text answer.
    """
    messages: List[Dict[str, Any]] = list(initial_messages)
    started = time.monotonic()
    last_model: Optional[str] = None
    last_state_token: Optional[Dict[str, Any]] = None

    for iteration in range(int(max_iterations)):
        if time.monotonic() - started > float(tool_deadline_s):
            yield {"type": "error", "error": f"tool-loop timeout after {int(tool_deadline_s)}s"}
            return

        # Surface model-side latency so the UI can show "Asking the model"
        # instead of an opaque "Thinking…" while we wait for the upstream.
        yield {
            "type": "status",
            "phase": "model_call",
            "iteration": iteration + 1,
            "max_iterations": int(max_iterations),
        }

        # Stream the completion. Content tokens are forwarded to the SSE
        # client as they arrive (huge perceived-latency win); tool_calls
        # are buffered until end-of-stream and dispatched after.
        msg: Optional[Dict[str, Any]] = None
        used_model: Optional[str] = None
        err: Optional[str] = None
        emitted_chars = 0  # how many content chars we already streamed
        for ev in _stream_with_fallback(
            cfg, messages, tools=tools,
            tool_choice="required" if iteration == 0 else ("none" if last_state_token else "auto"),
        ):
            kind = ev[0]
            if kind == "delta":
                chunk = ev[1] or ""
                emitted_chars += len(chunk)
                yield {"type": "delta", "delta": chunk}
            elif kind == "final":
                msg = ev[1]
                used_model = ev[2]
            elif kind == "error":
                err = ev[1]
                break

        if msg is None:
            yield {"type": "error", "error": err or "upstream failure"}
            return
        last_model = used_model

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            content = msg.get("content") or ""
            # Native function calling guarantees that tool arguments are not
            # embedded in assistant prose; return the final text verbatim.
            cleaned = content
            if last_state_token and not re.search(r"```state_token\s*\n", content, re.I):
                cleaned = (
                    content.rstrip()
                    + ("\n\n" if content.strip() else "")
                    + "```state_token\n"
                    + json.dumps(last_state_token, ensure_ascii=False)
                    + "\n```"
                )
            if emitted_chars == 0:
                # Some models return content only at end-of-stream (rare).
                yield {"type": "delta", "delta": cleaned}
            elif cleaned != content:
                yield {"type": "delta", "delta": cleaned, "replace": True}
            yield {"type": "done", "model": used_model, "iterations": iteration + 1}
            return

        # Append the assistant turn verbatim so the follow-up references the ids.
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": tool_calls,
        })

        # If we already streamed content tokens to the client this turn,
        # but the model ALSO emitted tool_calls, the streamed content was
        # really "thinking" prose, not the final answer. Wipe the bubble
        # (replace with empty) and re-emit it as a `thought` event so the
        # UI shows it under the dedicated thoughts section instead of
        # leaking pre-tool reasoning into the answer.
        if emitted_chars > 0:
            yield {"type": "delta", "delta": "", "replace": True}
            emitted_chars = 0

        # Surface the interim "thought" prose (if any) so the UI can show
        # what the model is reasoning about between tool calls.
        thought_text = (msg.get("content") or "").strip()
        if thought_text:
            # Strip any stray fenced action/JSON blocks — the user only sees
            # plain reasoning, not leaked machine payloads.
            cleaned_thought = re.sub(r"```[\s\S]*?```", "", thought_text).strip()
            if cleaned_thought:
                yield {"type": "thought", "content": cleaned_thought[:1000]}

        # Dispatch all tool calls in this turn IN PARALLEL. Each tool is a
        # read-only DuckDB / metadata lookup so they're safe to overlap and
        # this is the main latency win on multi-tool turns.
        prepared: List[Tuple[str, str, Dict[str, Any]]] = []
        for call in tool_calls:
            call_id = call.get("id") or ""
            fn = (call.get("function") or {})
            name = fn.get("name") or ""
            raw_args = fn.get("arguments") or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except Exception:
                args = {}
            prepared.append((call_id, name, args))

        real_prepared = prepared

        # Surface "running" markers up front so the UI shows every tool
        # call concurrently rather than serially.
        for call_id, name, args in real_prepared:
            yield {"type": "tool_start", "id": call_id, "name": name, "args": args}

        results: Dict[str, Dict[str, Any]] = {}
        # Per-tool wall-clock timeout: ensures one slow tool (e.g. an
        # H5AD load) cannot stall the whole agentic turn. Tunable via
        # GENX_TOOL_TIMEOUT (seconds, default 15). The first call to a
        # tool that builds a per-column value-counter cache (like
        # ``resolve_value`` on a fresh boot) can legitimately take 10-15s
        # on multi-species deployments — subsequent calls hit the cache
        # in milliseconds. The default is generous enough to cover the
        # cold path while still bounding genuinely-stuck dispatches.
        try:
            tool_timeout = float(os.environ.get("GENX_TOOL_TIMEOUT", "15"))
        except (TypeError, ValueError):
            tool_timeout = 20.0
        if len(real_prepared) == 1:
            call_id, name, args = real_prepared[0]
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(dispatch, name, args)
                try:
                    results[call_id] = fut.result(timeout=tool_timeout) or {}
                except FuturesTimeout:
                    logger.warning("dispatch(%s) timed out after %.1fs", name, tool_timeout)
                    results[call_id] = {"error": f"tool '{name}' timed out after {tool_timeout:.0f}s"}
                except Exception as e:  # noqa: BLE001
                    logger.warning("dispatch(%s) failed: %s", name, e, exc_info=True)
                    results[call_id] = {"error": f"{type(e).__name__}: {e}"}
        else:
            with ThreadPoolExecutor(max_workers=min(4, len(real_prepared))) as pool:
                future_map = {
                    pool.submit(dispatch, name, args): (call_id, name)
                    for call_id, name, args in real_prepared
                }
                for future in future_map:
                    call_id, name = future_map[future]
                    try:
                        results[call_id] = future.result(timeout=tool_timeout) or {}
                    except FuturesTimeout:
                        logger.warning("dispatch(%s) timed out after %.1fs", name, tool_timeout)
                        results[call_id] = {"error": f"tool '{name}' timed out after {tool_timeout:.0f}s"}
                    except Exception as e:  # noqa: BLE001
                        logger.warning("dispatch(%s) failed: %s", name, e, exc_info=True)
                        results[call_id] = {"error": f"{type(e).__name__}: {e}"}

        for call_id, name, _args in real_prepared:
            result = results.get(call_id, {})
            yield {"type": "tool_result", "id": call_id, "name": name, "result": result}

            # Feed the result back to the LLM.
            try:
                content = json.dumps(result, ensure_ascii=False)
            except Exception:
                content = json.dumps({"error": "non-serialisable tool result"})
            if len(content) > 8000:
                content = content[:8000] + "…(truncated)"
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "name": name,
                "content": content,
            })
            if name == "search_metadata" and result.get("status") == "ui_control":
                messages.append({
                    "role": "user",
                    "content": (
                        "[runtime] The searched term is a registered UI control, not metadata. "
                        "Call build_state_token now using the returned control keys/options and "
                        "the user's requested operation. For all/every options use the ['*'] "
                        "sentinel instead of enumerating options. Keep viz_patches and "
                        "trigger_actions as top-level tool arguments, never inside filters. "
                        "Do not call search_metadata again."
                    ),
                })
            elif name == "search_metadata" and isinstance(result.get("hits"), list):
                verified = [
                    {
                        "namespace": hit.get("namespace"),
                        "column": hit.get("column"),
                        "value": hit.get("value"),
                    }
                    for hit in result["hits"]
                    if isinstance(hit, dict) and hit.get("column") and hit.get("value") is not None
                ]
                if verified:
                    messages.append({
                        "role": "user",
                        "content": (
                            "[runtime] Metadata discovery returned verified values: "
                            + json.dumps(verified[:10], ensure_ascii=False)
                            + ". If the user's command targets matching rows, the next "
                            "build_state_token call must include the chosen hit as an exact "
                            "var_filters or obs_filters change according to its namespace. "
                            "Do not replace a verified concrete value with has_value."
                        ),
                    })
            if name == "build_state_token" and isinstance(result, dict):
                token = result.get("state_token")
                if isinstance(token, dict):
                    last_state_token = token

    # ── Iteration cap reached ────────────────────────────────────────────
    # The model kept requesting tools past the configured limit. Force one
    # last completion WITHOUT tools so it can summarise what it found, then
    # always close with a clear, user-facing notice — never a raw/cryptic
    # error string. `replace: True` wipes any leaked partial bubble content.
    cap_notice = (
        "\n\n---\n"
        f"⚠️ **Step limit reached.** I stopped after {int(max_iterations)} "
        "tool steps without finishing this request.\n\n"
        "This usually means the request was very complex or ambiguous. You can:\n"
        "- rephrase it more specifically or break it into smaller steps, or\n"
        "- raise the limit in the Admin panel (GAIA → max tool iterations)."
    )

    final, used_model, err = _complete_with_fallback(cfg, messages, tools=None)
    if final is None:
        # Even the no-tools fallback failed — show the notice (not a cryptic
        # raw error) so the user still receives an actionable message.
        msg_text = (
            "I couldn't complete this request within the allowed number of steps."
            + cap_notice
        )
        if err:
            logger.warning("iteration cap fallback completion failed: %s", err)
        yield {
            "type": "delta",
            "delta": msg_text,
            "replace": True,
            "model": last_model,
            "iterations": int(max_iterations),
        }
        yield {"type": "done", "model": last_model, "iterations": int(max_iterations)}
        return
    final_text = final.get("content") or ""
    if last_state_token and not re.search(r"```state_token\s*\n", final_text, re.I):
        final_text = (
            final_text.rstrip()
            + ("\n\n" if final_text.strip() else "")
            + "```state_token\n"
            + json.dumps(last_state_token, ensure_ascii=False)
            + "\n```"
        )
    yield {
        "type": "delta",
        "delta": (final_text or "").rstrip() + cap_notice,
        "replace": True,
        "model": used_model or last_model,
        "iterations": int(max_iterations),
    }
    yield {"type": "done", "model": used_model or last_model, "iterations": int(max_iterations)}
