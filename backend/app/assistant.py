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
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
    url = _build_url(cfg["api_base"], "chat/completions")
    return _post_json(url, cfg["api_key"], payload, int(cfg.get("request_timeout_s", 60)), stream=stream)


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
# SSE streaming with primary / fallback
# ----------------------------------------------------------------------------

def stream_chat(
    cfg: Dict[str, Any],
    messages: List[Dict[str, str]],
) -> Iterator[str]:
    """Yield SSE-formatted string chunks for a chat completion.

    Falls back to ``fallback_model`` on a primary-model 4xx/5xx. Always emits
    a final ``event: done`` frame.
    """
    primary = cfg.get("model")
    fallback = cfg.get("fallback_model") or None
    tried: List[str] = []
    last_error: Optional[str] = None

    for model in [m for m in (primary, fallback) if m]:
        if model in tried:
            continue
        tried.append(model)
        try:
            resp = call_chat_completion(cfg, messages, stream=True, model_override=model)
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code} on {model}"
            logger.warning("LLM upstream error (%s): %s", model, last_error)
            continue
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning("LLM upstream failure (%s): %s", model, last_error)
            continue

        yield f"event: start\ndata: {json.dumps({'model': model})}\n\n"
        try:
            for raw in resp:
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
                if not line:
                    continue
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        obj = json.loads(payload)
                        delta = (
                            obj.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content")
                        )
                        if delta:
                            yield f"data: {json.dumps({'delta': delta})}\n\n"
                    except json.JSONDecodeError:
                        continue
        finally:
            resp.close()

        yield f"event: done\ndata: {json.dumps({'model': model})}\n\n"
        return

    yield f"event: error\ndata: {json.dumps({'error': last_error or 'no usable model'})}\n\n"


def complete_chat(cfg: Dict[str, Any], messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Non-streaming chat completion with primary/fallback retry."""
    primary = cfg.get("model")
    fallback = cfg.get("fallback_model") or None
    last_error: Optional[str] = None
    for model in [m for m in (primary, fallback) if m]:
        try:
            resp = call_chat_completion(cfg, messages, stream=False, model_override=model)
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
            return {"ok": True, "model": data.get("model") or model, "content": content}
        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code} on {model}: {e.read().decode('utf-8', errors='replace')[:300]}"
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
    return {"ok": False, "error": last_error or "no usable model"}


# ----------------------------------------------------------------------------
# Leaked-tool-call salvage
# ----------------------------------------------------------------------------
# Some OpenAI-compatible backends (notably Qwen) occasionally emit tool
# arguments as a ```json``` (or ```tool```) code block in the assistant text
# instead of going through the tool_calls protocol. We detect and rescue
# these by mapping the key signature to one of our registered tools.

_TOOL_KEY_SIGNATURES: List[Tuple[str, frozenset, frozenset]] = [
    # (tool_name, required_keys, allowed_keys)
    ("top_groups", frozenset({"table", "group_column"}),
        frozenset({"table", "group_column", "var_filters", "top_n", "split_arrays"})),
    ("resolve_value", frozenset({"query"}),
        frozenset({"query", "tables", "max_hits"})),
    ("count_rows", frozenset({"table"}),
        frozenset({"table", "var_filters", "obs_filters"})),
    ("summary_stats", frozenset({"table", "column"}),
        frozenset({"table", "column", "namespace", "var_filters", "obs_filters"})),
    ("build_deeplink", frozenset({"view"}),
        frozenset({"view", "tables", "filters", "visualizations"})),
    ("list_distinct_values", frozenset({"column"}),
        frozenset({"column", "table", "prefix", "limit"})),
    ("list_schema", frozenset(), frozenset()),
]

# Strip fenced code blocks whose language is "json" or "tool" (not one of the
# real action-block tags) before emitting text to the user.
_ACTION_BLOCK_TAGS = {
    "deeplink", "viz_update", "add_filter", "remove_filter", "clear_filters",
    "select_tables", "set_expression_display", "action", "compute",
}
_FENCE_RE = re.compile(r"```([A-Za-z_][A-Za-z0-9_]*)\s*\n([\s\S]*?)\n```", re.MULTILINE)
# Matches both tagged AND untagged fences. The untagged variant catches
# bare ```{...}``` blocks that some models emit instead of using the
# proper action-block tag.
_FENCE_ANY_RE = re.compile(r"```([A-Za-z_][A-Za-z0-9_]*)?\s*\n([\s\S]*?)\n```", re.MULTILINE)

# Action-block signatures used to recognise leaked / mis-tagged fences.
_ACTION_KEY_SIGNATURES: List[Tuple[str, frozenset, frozenset]] = [
    ("add_filter", frozenset({"column"}),
        frozenset({"column", "value", "values", "strict", "empty"})),
    ("remove_filter", frozenset({"column"}), frozenset({"column"})),
    ("clear_filters", frozenset(), frozenset()),
    ("select_tables", frozenset({"tables"}), frozenset({"tables"})),
    ("set_expression_display", frozenset({"optionId"}),
        frozenset({"optionId", "layer", "transform"})),
    ("viz_update", frozenset({"patch"}), frozenset({"patch"})),
    ("deeplink", frozenset({"view"}),
        frozenset({"view", "tables", "filters", "visualizations"})),
]


def _match_action_signature(obj: Dict[str, Any]) -> Optional[str]:
    keys = frozenset(obj.keys())
    for name, required, allowed in _ACTION_KEY_SIGNATURES:
        if not required.issubset(keys):
            continue
        if allowed and not keys.issubset(allowed):
            continue
        return name
    return None


def retag_action_fences(content: str) -> str:
    """Re-tag fenced JSON blocks that match an action signature.

    Some models emit action payloads as ```json``` or as a bare ``` ``` ```
    fence. Without re-tagging, the frontend parser ignores them and the
    user sees raw JSON in chat. We rewrite the fence's opening line to use
    the matching action language tag (e.g. ``add_filter``) so the existing
    extractor picks them up.

    Also strips any TRAILING unclosed fence whose body looks like JSON —
    those happen when ``max_tokens`` truncates the response mid-block and
    would otherwise show up as raw JSON in the chat bubble.
    """
    if not content:
        return content

    # Drop a trailing unclosed fence (no closing ```) whose body looks
    # like JSON. Any unclosed fence at the end of the message is at best
    # an incomplete action payload — safer to discard than to render.
    if "```" in content:
        last_open = content.rfind("```")
        # If the fence we found has no matching closer, last_open is unclosed.
        # We test by counting fence markers: an even number means all closed.
        fence_count = content.count("```")
        if fence_count % 2 == 1:
            head = content[:last_open].rstrip()
            tail = content[last_open + 3:]
            tail_body = tail.split("\n", 1)[1] if "\n" in tail else tail
            looks_json = tail_body.lstrip().startswith(("{", "["))
            # Always drop unclosed fences whose body looks like JSON or whose
            # tag is one of our action / json / tool tags.
            tag = (tail.split("\n", 1)[0] or "").strip().lower()
            if looks_json or tag in _ACTION_BLOCK_TAGS or tag in ("", "json", "tool"):
                content = head

    if "```" not in content:
        return content

    out: List[str] = []
    last = 0
    for match in _FENCE_ANY_RE.finditer(content):
        tag = (match.group(1) or "").lower()
        body = match.group(2) or ""
        out.append(content[last:match.start()])
        last = match.end()

        if tag in _ACTION_BLOCK_TAGS:
            # Already a recognised action block \u2014 keep verbatim.
            out.append(match.group(0))
            continue

        # Try to recognise the body as an action payload.
        try:
            obj = json.loads(body)
        except Exception:
            obj = None
        if isinstance(obj, dict):
            name = _match_action_signature(obj)
            if name:
                out.append(f"```{name}\n{body}\n```")
                continue

        # Unrecognised \u2014 if it is a bare/json/tool fence containing JSON,
        # drop it (otherwise the user sees a raw JSON code block).
        looks_like_json = body.lstrip().startswith(("{", "["))
        if tag in ("", "json", "tool") and looks_like_json:
            continue

        out.append(match.group(0))

    out.append(content[last:])
    return "".join(out)


def _extract_leaked_tool_calls(content: str) -> List[Tuple[str, Dict[str, Any], Tuple[int, int]]]:
    """Return list of (tool_name, args, (span_start, span_end)) parsed from text."""
    out: List[Tuple[str, Dict[str, Any], Tuple[int, int]]] = []
    if not content:
        return out
    for match in _FENCE_RE.finditer(content):
        tag = (match.group(1) or "").lower()
        body = match.group(2) or ""
        if tag in _ACTION_BLOCK_TAGS:
            continue  # legitimate action block
        try:
            obj = json.loads(body)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue
        keys = frozenset(obj.keys())
        # Find the best-matching tool signature.
        best: Optional[str] = None
        for name, required, allowed in _TOOL_KEY_SIGNATURES:
            if not required.issubset(keys):
                continue
            if allowed and not keys.issubset(allowed):
                continue
            best = name
            break
        if best is None:
            continue
        out.append((best, obj, match.span()))
    return out


def _strip_leaked_tool_blocks(content: str, spans: List[Tuple[int, int]]) -> str:
    """Remove the given character spans from `content` and tidy whitespace."""
    if not spans:
        return content
    # Sort descending so edits don't shift subsequent spans.
    for start, end in sorted(spans, key=lambda s: -s[0]):
        content = content[:start] + content[end:]
    # Collapse 3+ newlines that the removal may have created.
    content = re.sub(r"\n{3,}", "\n\n", content).strip()
    return content


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
            tools=tools, tool_choice="auto" if tools else None,
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
        for ev in _stream_once(cfg, messages, tools=tools, model_override=model):
            kind = ev[0]
            if kind == "error":
                last_err = f"{ev[1]} (model={model})"
                logger.warning("LLM streaming failure: %s", last_err)
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
        for ev in _stream_with_fallback(cfg, messages, tools=tools):
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
            # Salvage: if the model leaked tool args as a code block instead
            # of using the tool_calls protocol, parse and dispatch them, then
            # loop once more so the model can produce a real answer.
            leaked = _extract_leaked_tool_calls(content)
            if leaked and iteration < int(max_iterations) - 1:
                logger.info("Salvaging %d leaked tool call(s) from assistant text", len(leaked))
                # Append the (cleaned) assistant turn so the model sees its own draft.
                cleaned = _strip_leaked_tool_blocks(content, [span for _, _, span in leaked])
                # We already streamed the leaked JSON to the client. Replace
                # the assistant bubble's content with the cleaned version
                # so the user never sees the raw payload.
                if emitted_chars > 0:
                    yield {"type": "delta", "delta": cleaned, "replace": True}
                messages.append({"role": "assistant", "content": cleaned})
                # Feed each leaked call back as a synthetic tool result.
                for name, args, _span in leaked:
                    synthetic_id = f"salvage-{iteration}-{name}"
                    yield {"type": "tool_start", "id": synthetic_id, "name": name, "args": args}
                    try:
                        result = dispatch(name, args) or {}
                    except Exception as e:  # noqa: BLE001
                        logger.warning("salvage dispatch(%s) failed: %s", name, e, exc_info=True)
                        result = {"error": f"{type(e).__name__}: {e}"}
                    yield {"type": "tool_result", "id": synthetic_id, "name": name, "result": result}
                    try:
                        payload = json.dumps(result, ensure_ascii=False)
                    except Exception:
                        payload = json.dumps({"error": "non-serialisable tool result"})
                    if len(payload) > 8000:
                        payload = payload[:8000] + "…(truncated)"
                    # Use a user-role nudge because there's no matching
                    # tool_call_id to attach a tool-role message to.
                    messages.append({
                        "role": "user",
                        "content": (
                            f"[runtime] I intercepted a tool-argument JSON for `{name}` "
                            f"in your last reply. You MUST use the tool_calls protocol "
                            f"for tools — do not print JSON in the text. Here is the "
                            f"result I computed for you:\n{payload}\n\nContinue: produce "
                            f"the final answer now, ending with any required action blocks."
                        ),
                    })
                # Reset the streamed-char counter for the next iteration so a
                # subsequent retag-replace doesn't double-fire.
                emitted_chars = 0
                continue  # re-prompt with tool results included

            # Final assistant message — content was already streamed via
            # delta events above. Apply retag_action_fences as a defensive
            # post-processing step; if it changed anything, send a
            # `replace` delta so the client swaps the bubble's content
            # for the cleaned-up version. Otherwise nothing more to send.
            cleaned = retag_action_fences(content)
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

        # Surface "running" markers up front so the UI shows every tool
        # call concurrently rather than serially.
        for call_id, name, args in prepared:
            yield {"type": "tool_start", "id": call_id, "name": name, "args": args}

        results: Dict[str, Dict[str, Any]] = {}
        # Per-tool wall-clock timeout: ensures one slow tool (e.g. an
        # H5AD load) cannot stall the whole agentic turn. Tunable via
        # GENX_TOOL_TIMEOUT (seconds, default 30). The first call to a
        # tool that builds a per-column value-counter cache (like
        # ``resolve_value`` on a fresh boot) can legitimately take 10-15s
        # on multi-species deployments — subsequent calls hit the cache
        # in milliseconds. The default is generous enough to cover the
        # cold path while still bounding genuinely-stuck dispatches.
        try:
            tool_timeout = float(os.environ.get("GENX_TOOL_TIMEOUT", "30"))
        except (TypeError, ValueError):
            tool_timeout = 20.0
        if len(prepared) == 1:
            call_id, name, args = prepared[0]
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
            with ThreadPoolExecutor(max_workers=min(4, len(prepared))) as pool:
                future_map = {
                    pool.submit(dispatch, name, args): (call_id, name)
                    for call_id, name, args in prepared
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

        for call_id, name, _args in prepared:
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

    # Iteration cap hit — force one more call without tools to get text.
    final, used_model, err = _complete_with_fallback(cfg, messages, tools=None)
    if final is None:
        yield {"type": "error", "error": err or "iteration cap hit and no fallback response"}
        return
    final_text = retag_action_fences(final.get("content") or "")
    yield {
        "type": "delta",
        "delta": final_text + "\n\n_(Note: tool iteration cap reached.)_",
        "model": used_model or last_model,
        "iterations": int(max_iterations),
    }
    yield {"type": "done", "model": used_model or last_model, "iterations": int(max_iterations)}
