"""Machine-readable LocalModelProfile schema (W7 P0)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

SCHEMA_VERSION = "1.0.0"


class ThinkingMode(str, Enum):
    off = "off"
    on = "on"
    not_controllable = "not_controllable"


class ProbeStatus(str, Enum):
    passed = "pass"
    failed = "fail"
    unsupported = "unsupported"
    error = "error"


class RecommendationLabel(str, Enum):
    suitable = "suitable"
    conditional = "conditional"
    unsuitable = "unsuitable"
    unknown = "unknown"


@dataclass(slots=True)
class Environment:
    python_version: str
    platform: str
    timeout_seconds: float
    repeat: int
    endpoint_host: str = ""  # host only; never include credentials

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ProbeResult:
    probe_id: str
    category: str
    name: str
    status: str
    passed: bool
    thinking_mode: str
    timed_out: bool = False
    latency_ms: float | None = None
    repair_required: bool = False
    schema_success: bool = False
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    repeat_index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProbeResult:
        return cls(
            probe_id=str(data["probe_id"]),
            category=str(data["category"]),
            name=str(data["name"]),
            status=str(data["status"]),
            passed=bool(data["passed"]),
            thinking_mode=str(data.get("thinking_mode", ThinkingMode.off.value)),
            timed_out=bool(data.get("timed_out", False)),
            latency_ms=data.get("latency_ms"),
            repair_required=bool(data.get("repair_required", False)),
            schema_success=bool(data.get("schema_success", False)),
            error=data.get("error"),
            details=dict(data.get("details") or {}),
            repeat_index=int(data.get("repeat_index", 0)),
        )


@dataclass(slots=True)
class Summary:
    total: int
    passed: int
    failed: int
    timed_out: int
    unsupported: int
    error: int
    by_category: dict[str, dict[str, int]] = field(default_factory=dict)
    stability: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Summary:
        return cls(
            total=int(data.get("total", 0)),
            passed=int(data.get("passed", 0)),
            failed=int(data.get("failed", 0)),
            timed_out=int(data.get("timed_out", 0)),
            unsupported=int(data.get("unsupported", 0)),
            error=int(data.get("error", 0)),
            by_category=dict(data.get("by_category") or {}),
            stability=dict(data.get("stability") or {}),
        )


@dataclass(slots=True)
class Recommendation:
    overall: str
    thinking_off: str
    thinking_on: str
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Recommendation:
        return cls(
            overall=str(data.get("overall", RecommendationLabel.unknown.value)),
            thinking_off=str(
                data.get("thinking_off", RecommendationLabel.unknown.value)
            ),
            thinking_on=str(
                data.get("thinking_on", RecommendationLabel.unknown.value)
            ),
            reasons=list(data.get("reasons") or []),
        )


@dataclass(slots=True)
class LocalModelProfile:
    schema_version: str
    created_at: str
    provider: str
    endpoint_type: str
    model_id: str
    thinking_mode: str
    run_id: str
    environment: Environment
    probes: list[ProbeResult]
    summary: Summary
    recommendation: Recommendation

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "provider": self.provider,
            "endpoint_type": self.endpoint_type,
            "model_id": self.model_id,
            "thinking_mode": self.thinking_mode,
            "run_id": self.run_id,
            "environment": self.environment.to_dict(),
            "probes": [p.to_dict() for p in self.probes],
            "summary": self.summary.to_dict(),
            "recommendation": self.recommendation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LocalModelProfile:
        env_raw = data.get("environment") or {}
        env = Environment(
            python_version=str(env_raw.get("python_version", "")),
            platform=str(env_raw.get("platform", "")),
            timeout_seconds=float(env_raw.get("timeout_seconds", 0)),
            repeat=int(env_raw.get("repeat", 1)),
            endpoint_host=str(env_raw.get("endpoint_host", "")),
        )
        return cls(
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            created_at=str(data.get("created_at", "")),
            provider=str(data.get("provider", "")),
            endpoint_type=str(data.get("endpoint_type", "openai_compatible")),
            model_id=str(data.get("model_id", "")),
            thinking_mode=str(data.get("thinking_mode", ThinkingMode.off.value)),
            run_id=str(data.get("run_id", "")),
            environment=env,
            probes=[ProbeResult.from_dict(p) for p in (data.get("probes") or [])],
            summary=Summary.from_dict(data.get("summary") or {}),
            recommendation=Recommendation.from_dict(data.get("recommendation") or {}),
        )


def new_run_id() -> str:
    return uuid4().hex[:12]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
