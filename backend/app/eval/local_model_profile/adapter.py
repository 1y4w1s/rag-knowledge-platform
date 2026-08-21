"""OpenAI-compatible chat completion adapter for local model probes.

Reuses the same HTTP shape as product providers (``/chat/completions`` + httpx),
but is **parameterized** by CLI/env — it does not change default CHAT_PROVIDER
or wire into Agent runtime.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

import httpx

from app.eval.local_model_profile.schema import ThinkingMode

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 60.0
API_KEY_ENV_CANDIDATES = (
    "LOCAL_MODEL_API_KEY",
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "LM_STUDIO_API_KEY",
)


@dataclass(slots=True)
class CompletionResult:
    content: str
    raw: dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    thinking_control_applied: bool = False
    thinking_control_supported: bool | None = None
    error: str | None = None
    timed_out: bool = False
    http_status: int | None = None


def resolve_api_key(explicit: str | None = None) -> str:
    if explicit:
        return explicit
    for name in API_KEY_ENV_CANDIDATES:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    # LM Studio often accepts any non-empty bearer; keep empty for true anonymous.
    return ""


def endpoint_host(base_url: str) -> str:
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    return parsed.hostname or ""


class OpenAICompatibleAdapter:
    """Thin OpenAI-compatible client (sync httpx; CI-mockable)."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        thinking_mode: ThinkingMode | str = ThinkingMode.off,
        provider: str = "openai_compatible",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = resolve_api_key(api_key)
        self.timeout_seconds = float(timeout_seconds)
        self.thinking_mode = (
            thinking_mode
            if isinstance(thinking_mode, ThinkingMode)
            else ThinkingMode(str(thinking_mode))
        )
        self.provider = provider
        self._thinking_control_supported: bool | None = None

    @property
    def thinking_control_supported(self) -> bool | None:
        return self._thinking_control_supported

    def chat_completion(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 512,
        extra_body: dict[str, Any] | None = None,
    ) -> CompletionResult:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        thinking_applied = self._apply_thinking_controls(payload, messages)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if extra_body:
            payload.update(extra_body)

        started = time.perf_counter()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                resp = client.post(url, headers=headers, json=payload)
            latency_ms = (time.perf_counter() - started) * 1000.0
            if resp.status_code >= 400:
                return CompletionResult(
                    content="",
                    raw=_safe_json(resp),
                    latency_ms=latency_ms,
                    error=f"http_{resp.status_code}",
                    http_status=resp.status_code,
                    thinking_control_applied=thinking_applied,
                    thinking_control_supported=self._thinking_control_supported,
                )
            data = resp.json()
            choice = ((data.get("choices") or [{}])[0]) or {}
            message = choice.get("message") or {}
            content = message.get("content") or ""
            if not isinstance(content, str):
                content = str(content)
            tool_calls = message.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                tool_calls = []
            self._observe_thinking_support(data, content)
            return CompletionResult(
                content=content,
                raw=data if isinstance(data, dict) else {},
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                finish_reason=choice.get("finish_reason"),
                thinking_control_applied=thinking_applied,
                thinking_control_supported=self._thinking_control_supported,
                http_status=resp.status_code,
            )
        except httpx.TimeoutException as exc:
            latency_ms = (time.perf_counter() - started) * 1000.0
            return CompletionResult(
                content="",
                latency_ms=latency_ms,
                error=f"timeout:{exc.__class__.__name__}",
                timed_out=True,
                thinking_control_applied=thinking_applied,
                thinking_control_supported=self._thinking_control_supported,
            )
        except Exception as exc:  # noqa: BLE001 — probe harness must continue
            latency_ms = (time.perf_counter() - started) * 1000.0
            logger.warning("local model probe completion failed: %s", exc)
            return CompletionResult(
                content="",
                latency_ms=latency_ms,
                error=f"provider_error:{exc.__class__.__name__}",
                thinking_control_applied=thinking_applied,
                thinking_control_supported=self._thinking_control_supported,
            )

    def _apply_thinking_controls(
        self,
        payload: dict[str, Any],
        messages: list[dict[str, Any]],
    ) -> bool:
        """Best-effort thinking toggle for OpenAI-compatible local servers.

        LM Studio / Qwen / GLM variants differ; we try common knobs and record
        whether control appears supported. Never crashes the run.
        """
        mode = self.thinking_mode
        if mode == ThinkingMode.not_controllable:
            self._thinking_control_supported = False
            return False

        # Common OpenAI-compatible extras (ignored by servers that don't know them).
        if mode == ThinkingMode.off:
            payload["enable_thinking"] = False
            payload["thinking"] = {"type": "disabled"}
            # Soft instruction — not counted as schema repair.
            if messages and messages[0].get("role") == "system":
                messages[0] = {
                    **messages[0],
                    "content": (
                        str(messages[0].get("content") or "")
                        + "\nDo not show chain-of-thought. Answer directly."
                    ).strip(),
                }
        else:
            payload["enable_thinking"] = True
            payload["thinking"] = {"type": "enabled"}
        return True

    def _observe_thinking_support(self, data: dict[str, Any], content: str) -> None:
        # Heuristic: if server echoes reasoning/thinking fields, control surface exists.
        message = ((data.get("choices") or [{}])[0] or {}).get("message") or {}
        has_field = any(
            key in message for key in ("reasoning_content", "reasoning", "thinking")
        )
        if has_field:
            self._thinking_control_supported = True
            return
        if self._thinking_control_supported is None:
            # Unknown until a dedicated thinking probe decides.
            self._thinking_control_supported = None


def _safe_json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {"raw": data}
    except (json.JSONDecodeError, ValueError):
        return {"text": resp.text[:500]}
