"""Probe runner: executes A–H, aggregates Summary + Recommendation."""

from __future__ import annotations

import platform
import sys
from collections import defaultdict
from typing import Any

from app.eval.local_model_profile.adapter import (
    DEFAULT_TIMEOUT_SECONDS,
    OpenAICompatibleAdapter,
    endpoint_host,
)
from app.eval.local_model_profile.probes import ProbeSpec, default_probe_specs
from app.eval.local_model_profile.schema import (
    SCHEMA_VERSION,
    Environment,
    LocalModelProfile,
    ProbeResult,
    Recommendation,
    RecommendationLabel,
    Summary,
    ThinkingMode,
    new_run_id,
    utc_now_iso,
)


class ProbeRunner:
    """Run capability probes against an OpenAI-compatible endpoint."""

    def __init__(
        self,
        adapter: OpenAICompatibleAdapter,
        *,
        thinking_mode: ThinkingMode | str = ThinkingMode.off,
        repeat: int = 3,
        specs: list[ProbeSpec] | None = None,
    ) -> None:
        self.adapter = adapter
        self.thinking_mode = (
            thinking_mode
            if isinstance(thinking_mode, ThinkingMode)
            else ThinkingMode(str(thinking_mode))
        )
        self.repeat = max(1, int(repeat))
        include_h = self.thinking_mode in {
            ThinkingMode.on,
            ThinkingMode.not_controllable,
        }
        self.specs = specs or default_probe_specs(include_thinking_probe=include_h)

    def run(self) -> LocalModelProfile:
        probes: list[ProbeResult] = []
        for spec in self.specs:
            iterations = self.repeat if spec.stability_core else 1
            # Category G = Thinking OFF stability; H = Thinking ON stability.
            # Core repeats are tagged via details; category letter kept on probe.
            for i in range(iterations):
                try:
                    result = spec.run(self.adapter, self.thinking_mode, i)
                except Exception as exc:  # noqa: BLE001 — never abort whole run
                    result = ProbeResult(
                        probe_id=spec.probe_id,
                        category=spec.category,
                        name=spec.name,
                        status="error",
                        passed=False,
                        thinking_mode=self.thinking_mode.value,
                        error=f"runner_error:{exc.__class__.__name__}",
                        details={"message": str(exc)[:200]},
                        repeat_index=i,
                    )
                # Annotate stability category without mixing modes.
                if spec.stability_core and iterations > 1:
                    stab_cat = (
                        "G"
                        if self.thinking_mode == ThinkingMode.off
                        else "H"
                        if self.thinking_mode == ThinkingMode.on
                        else spec.category
                    )
                    result.details = {
                        **result.details,
                        "stability_category": stab_cat,
                        "stability_repeat": iterations,
                    }
                probes.append(result)

        summary = aggregate_summary(probes, thinking_mode=self.thinking_mode)
        recommendation = recommend(probes, thinking_mode=self.thinking_mode)
        return LocalModelProfile(
            schema_version=SCHEMA_VERSION,
            created_at=utc_now_iso(),
            provider=self.adapter.provider,
            endpoint_type="openai_compatible",
            model_id=self.adapter.model,
            thinking_mode=self.thinking_mode.value,
            run_id=new_run_id(),
            environment=Environment(
                python_version=sys.version.split()[0],
                platform=platform.platform(),
                timeout_seconds=self.adapter.timeout_seconds,
                repeat=self.repeat,
                endpoint_host=endpoint_host(self.adapter.base_url),
            ),
            probes=probes,
            summary=summary,
            recommendation=recommendation,
        )


def aggregate_summary(
    probes: list[ProbeResult],
    *,
    thinking_mode: ThinkingMode,
) -> Summary:
    by_cat: dict[str, dict[str, int]] = defaultdict(
        lambda: {"total": 0, "passed": 0, "failed": 0, "timed_out": 0, "unsupported": 0, "error": 0}
    )
    passed = failed = timed_out = unsupported = error = 0
    for p in probes:
        bucket = by_cat[p.category]
        bucket["total"] += 1
        if p.timed_out:
            timed_out += 1
            bucket["timed_out"] += 1
        if p.status == "unsupported":
            unsupported += 1
            bucket["unsupported"] += 1
        elif p.status == "error" or p.timed_out:
            error += 1
            bucket["error"] += 1
        elif p.passed:
            passed += 1
            bucket["passed"] += 1
        else:
            failed += 1
            bucket["failed"] += 1

    stability = _stability_stats(probes, thinking_mode=thinking_mode)
    return Summary(
        total=len(probes),
        passed=passed,
        failed=failed,
        timed_out=timed_out,
        unsupported=unsupported,
        error=error,
        by_category={k: dict(v) for k, v in sorted(by_cat.items())},
        stability=stability,
    )


def _stability_stats(
    probes: list[ProbeResult],
    *,
    thinking_mode: ThinkingMode,
) -> dict[str, Any]:
    groups: dict[str, list[ProbeResult]] = defaultdict(list)
    for p in probes:
        if p.details.get("stability_category"):
            groups[p.probe_id].append(p)
    out: dict[str, Any] = {
        "thinking_mode": thinking_mode.value,
        "probes": {},
    }
    rates: list[float] = []
    for probe_id, items in groups.items():
        n = len(items)
        pcount = sum(1 for x in items if x.passed)
        rate = pcount / n if n else 0.0
        rates.append(rate)
        out["probes"][probe_id] = {
            "repeats": n,
            "pass_count": pcount,
            "pass_rate": round(rate, 4),
            "timed_out_count": sum(1 for x in items if x.timed_out),
        }
    out["mean_pass_rate"] = round(sum(rates) / len(rates), 4) if rates else None
    return out


def recommend(
    probes: list[ProbeResult],
    *,
    thinking_mode: ThinkingMode,
) -> Recommendation:
    """Data-driven recommendation only — no hardcoded GPU vendor claims."""
    reasons: list[str] = []
    by_id = {p.probe_id: p for p in probes if p.repeat_index == 0}

    a = by_id.get("A1")
    if a is None:
        label = RecommendationLabel.unknown
        reasons.append("missing_connectivity_probe")
    elif a.timed_out or a.status == "error" or not a.passed:
        label = RecommendationLabel.unsuitable
        reasons.append("connectivity_failed")
    else:
        b_ok = _core_pass_rate(probes, "B1") >= 0.8
        c_ok = _core_pass_rate(probes, "C1") >= 0.8
        f_ok = all(
            _core_pass_rate(probes, pid) >= 0.6 for pid in ("F1", "F2", "F3", "F4")
        )
        e_ok = _core_pass_rate(probes, "E1") >= 0.6
        mean = _mean_stability(probes)
        if b_ok and c_ok and f_ok and e_ok and (mean is None or mean >= 0.8):
            label = RecommendationLabel.suitable
            reasons.append("core_structured_and_planning_stable")
        elif b_ok or c_ok:
            label = RecommendationLabel.conditional
            reasons.append("partial_structured_capability")
            if not f_ok:
                reasons.append("planning_weak")
            if mean is not None and mean < 0.8:
                reasons.append("stability_below_0.8")
        else:
            label = RecommendationLabel.unsuitable
            reasons.append("structured_output_weak")

    # Thinking ON may be not controllable.
    thinking_off = (
        label.value
        if thinking_mode == ThinkingMode.off
        else RecommendationLabel.unknown.value
    )
    thinking_on = RecommendationLabel.unknown.value
    if thinking_mode == ThinkingMode.on:
        h0 = by_id.get("H0")
        if h0 and h0.error == "NOT_CONTROLLABLE":
            thinking_on = RecommendationLabel.unknown.value
            reasons.append("thinking_on_not_controllable")
            # overall stays based on probes but annotate.
        elif h0 and any(p.timed_out for p in probes if p.probe_id == "H0"):
            thinking_on = RecommendationLabel.unsuitable.value
            reasons.append("thinking_on_timeout_stall")
            label = RecommendationLabel.conditional
        else:
            thinking_on = label.value
    elif thinking_mode == ThinkingMode.not_controllable:
        thinking_on = RecommendationLabel.unknown.value
        reasons.append("thinking_control_not_controllable")

    if thinking_mode == ThinkingMode.off:
        thinking_on = RecommendationLabel.unknown.value

    return Recommendation(
        overall=label.value,
        thinking_off=thinking_off,
        thinking_on=thinking_on,
        reasons=reasons,
    )


def _core_pass_rate(probes: list[ProbeResult], probe_id: str) -> float:
    items = [p for p in probes if p.probe_id == probe_id]
    if not items:
        return 0.0
    return sum(1 for p in items if p.passed) / len(items)


def _mean_stability(probes: list[ProbeResult]) -> float | None:
    groups: dict[str, list[ProbeResult]] = defaultdict(list)
    for p in probes:
        if p.details.get("stability_category"):
            groups[p.probe_id].append(p)
    if not groups:
        return None
    rates = [
        sum(1 for x in items if x.passed) / len(items)
        for items in groups.values()
        if items
    ]
    return sum(rates) / len(rates) if rates else None


def run_profile(
    *,
    base_url: str,
    model: str,
    thinking: str = "off",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    repeat: int = 3,
    api_key: str | None = None,
    provider: str = "openai_compatible",
) -> LocalModelProfile:
    mode = ThinkingMode(thinking)
    adapter = OpenAICompatibleAdapter(
        base_url=base_url,
        model=model,
        api_key=api_key,
        timeout_seconds=timeout,
        thinking_mode=mode,
        provider=provider,
    )
    return ProbeRunner(adapter, thinking_mode=mode, repeat=repeat).run()
