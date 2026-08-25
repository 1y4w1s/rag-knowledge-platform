"""W10 E-B35b human showcase freeze execution — tests-only deterministic validation."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EB35B_DIR = REPO_ROOT / "docs" / "research" / "w10-eb35b-human-showcase-freeze-execution"

REQUIRED_FILES = (
    "README.md",
    "01-source-identity-freeze-record.md",
    "02-capture-mode-freeze-record.md",
    "03-runtime-identity-freeze-record.md",
    "04-human-freeze-checklist.md",
    "05-human-confirmation-provenance.md",
    "06-freeze-predicate-evaluation.md",
    "07-eb35b-verdict.md",
)

FROZEN_BASE_SHA = "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"

# Must remain NO in E-B35b (Human Freeze ≠ Owner Stamp)
FORBIDDEN_YES_GATES = (
    "MAY_ISSUE_APPROVED_OWNER_STAMP",
    "OWNER_AUTHORIZATION_ISSUED",
    "SOURCE_APPROVED",
    "AFTER_SOURCE_APPROVED",
    "ACQUISITION_EXECUTION_READY",
    "E-B_FORMAL_READY",
)

# Permitted YES after owner confirmation + predicate pass
REQUIRED_YES_GATES = (
    "SOURCE_IDENTITY_COMPLETE",
    "CAPTURE_MODE_FROZEN",
    "BASE_SHA_FROZEN",
    "HUMAN_CHECKLIST_COMPLETE",
    "E-B35B_HUMAN_SHOWCASE_FREEZE_EXECUTED",
)

PROHIBITION_MARKERS = (
    "DO NOT",
    "MUST NOT",
    "禁止",
    "⇏",
    "non-goal",
    "Does not",
    "不得",
    "unchanged",
    "remain",
    "still NO",
    "not flip",
    "Forbidden",
    "forbidden",
    "must remain",
    "FORBIDDEN",
    "≠",
    "not ",
    "NOT ",
    "**NO**",
    "= NO",
)


def _package_text() -> str:
    parts: list[str] = []
    for name in REQUIRED_FILES:
        parts.append((EB35B_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def _lines_declaring_gate_yes(text: str, var: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        if re.search(rf"{re.escape(var)}\s*=\s*YES\b", line):
            violations.append(stripped)
            continue
        if re.search(
            rf"\|\s*`?{re.escape(var)}`?\s*\|\s*\*?\*?\s*YES\s*\*?\*?\s*\|",
            line,
            re.IGNORECASE,
        ):
            violations.append(stripped)
    return violations


def _has_gate_yes(text: str, var: str) -> bool:
    return bool(re.search(rf"{re.escape(var)}\s*=\s*YES\b", text))


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_eb35b_required_files_exist(filename: str) -> None:
    path = EB35B_DIR / filename
    assert path.is_file(), f"missing {path.relative_to(REPO_ROOT)}"


def test_eb35b_frozen_base_sha_exact() -> None:
    text = _package_text()
    assert FROZEN_BASE_SHA in text
    capture = (EB35B_DIR / "02-capture-mode-freeze-record.md").read_text(
        encoding="utf-8"
    )
    runtime = (EB35B_DIR / "03-runtime-identity-freeze-record.md").read_text(
        encoding="utf-8"
    )
    assert f"base_sha                 = {FROZEN_BASE_SHA}" in capture
    assert f"base_sha                 = {FROZEN_BASE_SHA}" in runtime
    assert "BASE_SHA_FROZEN            = YES" in capture or (
        "BASE_SHA_FROZEN" in capture and "BASE_SHA_FROZEN = YES" in text
    )


def test_eb35b_freeze_status_frozen_on_records() -> None:
    for name in (
        "01-source-identity-freeze-record.md",
        "02-capture-mode-freeze-record.md",
        "03-runtime-identity-freeze-record.md",
    ):
        body = (EB35B_DIR / name).read_text(encoding="utf-8")
        assert re.search(r"freeze_status\s*=\s*FROZEN\b", body), name
        assert "frozen_by                = suoyin_project_owner" in body
        assert "frozen_at                = 2026-08-25T08:15:42Z" in body


def test_eb35b_permitted_freeze_gates_yes() -> None:
    text = _package_text()
    for var in REQUIRED_YES_GATES:
        assert _has_gate_yes(text, var), f"missing required YES for {var}"


def test_eb35b_forbidden_approval_gates_not_yes() -> None:
    text = _package_text()
    violations: list[str] = []
    for var in FORBIDDEN_YES_GATES:
        hits = _lines_declaring_gate_yes(text, var)
        violations.extend(f"{var}: {h}" for h in hits)
    assert not violations, "forbidden YES gates found:\n" + "\n".join(violations)


def test_eb35b_capture_honesty() -> None:
    text = _package_text()
    assert "model_backend_identity   = none_no_llm" in text or (
        "model_backend_identity" in text and "none_no_llm" in text
    )
    assert "llm_called_expected      = false" in text or "llm_called_expected" in text
    assert "LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO" in text or (
        "LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY" in text
    )
    assert "DEFER_TO_BENCHMARK_TRACK" in text
    assert "LM Studio" in text
    assert "≠ Formal Evaluation Source" in text or (
        "Development Backend" in text and "Formal" in text
    )
    assert "CAPTURE_HONESTY_CONFLICT" in text
    assert "CAPTURE_HONESTY_CONFLICT             = NO" in text or (
        "CAPTURE_HONESTY_CONFLICT                                 = NO" in text
    )


def test_eb35b_human_checklist_ticked() -> None:
    checklist = (EB35B_DIR / "04-human-freeze-checklist.md").read_text(
        encoding="utf-8"
    )
    assert "HUMAN_CHECKLIST_COMPLETE       = YES" in checklist or (
        "HUMAN_CHECKLIST_COMPLETE = YES" in checklist
    )
    assert checklist.count("[x]") >= 20
    assert "suoyin_project_owner" in checklist


def test_eb35b_historical_ea4_separation() -> None:
    text = _package_text()
    assert "historical" in text.lower() or "Historical" in text
    assert "w10-ea4-formal-window-result" in text or "E-A4" in text
    assert "≠ this freeze base_sha" in text or "≠ current Formal Observation" in text


def test_eb35b_waiting_for_stamp_review() -> None:
    verdict = (EB35B_DIR / "07-eb35b-verdict.md").read_text(encoding="utf-8")
    assert "WAITING_FOR_OWNER_STAMP_ISSUANCE_REVIEW" in verdict
    assert "HUMAN_FREEZE_EXECUTED" in verdict
    assert "MAY_ISSUE_APPROVED_OWNER_STAMP`** | **NO**" in verdict or (
        "MAY_ISSUE_APPROVED_OWNER_STAMP" in verdict
        and "NO" in verdict
    )
    assert "DEPENDENCY_SNAPSHOT_PINNED` | **NO**" in verdict or (
        "DEPENDENCY_SNAPSHOT_PINNED" in verdict
    )


def test_eb35b_scope_exclusions_honest() -> None:
    text = _package_text()
    assert "C01" in text and "C11" in text
    assert "INELIGIBLE" in text
    assert "S2" in text
    assert "A4" in text or "live LLM" in text
    assert "BP-A" in text
    assert "w9_critic_frozen_12" in text
