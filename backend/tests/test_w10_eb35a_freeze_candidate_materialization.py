"""W10 E-B35a freeze candidate materialization — tests-only deterministic validation."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EB35A_DIR = REPO_ROOT / "docs" / "research" / "w10-eb35a-freeze-candidate-materialization"

REQUIRED_FILES = (
    "README.md",
    "01-human-supplied-candidate-values.md",
    "02-runtime-and-git-observation.md",
    "03-showcase-freeze-candidate-record.md",
    "04-candidate-consistency-audit.md",
    "05-human-confirmation-sheet.md",
    "06-eb35a-verdict.md",
)

FORBIDDEN_STATUS_VARS = (
    "SOURCE_IDENTITY_COMPLETE",
    "CAPTURE_MODE_FROZEN",
    "MAY_ISSUE_APPROVED_OWNER_STAMP",
    "OWNER_AUTHORIZATION_ISSUED",
    "SOURCE_APPROVED",
    "AFTER_SOURCE_APPROVED",
    "ACQUISITION_EXECUTION_READY",
    "E-B_FORMAL_READY",
    "BASE_SHA_FROZEN",
    "AUTHORIZATION_SCOPE_FROZEN",
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
    "∧",
    "only where",
    "future",
    "later human",
    "human freeze",
    "predicate",
    "Forbidden",
    "forbidden",
    "must remain",
    "≠",
    "not ",
    "NOT ",
    "No ",
    "**NO**",
    "= NO",
    "UNSET",
    "PENDING",
    "BLOCKED",
)

ALLOWED_PROVENANCE_TAGS = (
    "HUMAN_SUPPLIED_CANDIDATE",
    "REPOSITORY_VERIFIED_CANDIDATE",
    "RUNTIME_OBSERVED_CANDIDATE",
    "DEFER_TO_BENCHMARK_TRACK",
    "HUMAN_CONFIRMATION_REQUIRED",
    "REPOSITORY_OR_RUNTIME_OBSERVED_CANDIDATE",
)

ACHIEVED_FROZEN_PATTERNS = (
    re.compile(r"^\s*freeze_status\s*=\s*FROZEN\b"),
    re.compile(r"\bHUMAN_FROZEN\s*=\s*YES\b"),
    re.compile(r"\bBASE_SHA_FROZEN\s*=\s*YES\b"),
    re.compile(r"\bAUTHORIZATION_SCOPE_FROZEN\s*=\s*YES\b"),
    re.compile(r"^\s*authorization_status\s*=\s*APPROVED\b"),
)

TICKED_CHECKBOX = re.compile(r"\[x\]", re.IGNORECASE)


def _package_text() -> str:
    parts: list[str] = []
    for name in REQUIRED_FILES:
        parts.append((EB35A_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def _lines_declaring_forbidden_yes(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        # Skip markdown table rows that only report gate state as NO elsewhere
        for var in FORBIDDEN_STATUS_VARS:
            if re.search(rf"{re.escape(var)}\s*=\s*YES\b", line):
                violations.append(stripped)
                break
            # Table form: | `VAR` | YES |
            if re.search(
                rf"\|\s*`?{re.escape(var)}`?\s*\|\s*\*?\*?\s*YES\s*\*?\*?\s*\|",
                line,
                re.IGNORECASE,
            ):
                violations.append(stripped)
                break
    return violations


def _achieved_frozen_lines(text: str) -> list[str]:
    violations: list[str] = []
    for line in text.splitlines():
        if any(marker in line for marker in PROHIBITION_MARKERS):
            continue
        if "≠" in line or "not " in line.lower() or "forbidden" in line.lower():
            continue
        for pattern in ACHIEVED_FROZEN_PATTERNS:
            if pattern.search(line):
                violations.append(line.strip())
                break
    return violations


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_eb35a_required_files_exist(filename: str) -> None:
    path = EB35A_DIR / filename
    assert path.is_file(), f"missing {path.relative_to(REPO_ROOT)}"


def test_eb35a_pending_human_confirmation_status() -> None:
    text = _package_text()
    assert "FREEZE_CANDIDATE_STATUS" in text
    assert "PENDING_HUMAN_CONFIRMATION" in text
    assert "E-B35A_FREEZE_CANDIDATE_MATERIALIZED = YES" in text
    record = (EB35A_DIR / "03-showcase-freeze-candidate-record.md").read_text(
        encoding="utf-8"
    )
    assert "freeze_status                = PENDING_HUMAN_CONFIRMATION" in record
    # Achieved assignment only — prose forbidding FROZEN is allowed
    assigned_frozen = [
        line.strip()
        for line in record.splitlines()
        if re.search(r"^\s*freeze_status\s*=\s*FROZEN\b", line)
    ]
    assert not assigned_frozen, assigned_frozen


def test_eb35a_forbidden_approval_gates_not_yes() -> None:
    text = _package_text()
    violations = _lines_declaring_forbidden_yes(text)
    assert not violations, "forbidden YES gates found:\n" + "\n".join(violations)


def test_eb35a_no_achieved_frozen_or_approved_stamp() -> None:
    text = _package_text()
    violations = _achieved_frozen_lines(text)
    assert not violations, "achieved FROZEN/APPROVED markers:\n" + "\n".join(
        violations
    )


def test_eb35a_human_checklist_not_auto_ticked() -> None:
    sheet = (EB35A_DIR / "05-human-confirmation-sheet.md").read_text(encoding="utf-8")
    # Allow only prose saying boxes must not be ticked — no [x] confirmation ticks
    assert "ANY_CHECKBOX_TICKED            = NO" in sheet
    assert TICKED_CHECKBOX.search(sheet) is None
    assert sheet.count("[ ]") >= 15


def test_eb35a_provenance_tags_legal() -> None:
    text = _package_text()
    # Must not claim HUMAN_FROZEN as achieved provenance for candidate values
    assert "HUMAN_FROZEN" not in text or "≠ HUMAN_FROZEN" in text
    for tag in (
        "HUMAN_SUPPLIED_CANDIDATE",
        "RUNTIME_OBSERVED_CANDIDATE",
        "REPOSITORY_VERIFIED_CANDIDATE",
        "DEFER_TO_BENCHMARK_TRACK",
        "HUMAN_CONFIRMATION_REQUIRED",
    ):
        assert tag in text, f"missing required provenance tag {tag}"
    # Sanity: allowed set documented
    for tag in ALLOWED_PROVENANCE_TAGS:
        assert isinstance(tag, str) and tag


def test_eb35a_lm_studio_not_formal_primary() -> None:
    text = _package_text()
    assert "LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO" in text or (
        "LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY  = NO" in text
    )
    assert "Development Generation Backend" in text
    assert "formal_model_identity" in text
    assert "DEFER_TO_BENCHMARK_TRACK" in text
    assert "LM Studio" in text


def test_eb35a_waiting_and_no_eb35b() -> None:
    verdict = (EB35A_DIR / "06-eb35a-verdict.md").read_text(encoding="utf-8")
    assert "WAITING_FOR_HUMAN_CONFIRMATION" in verdict
    assert "E-B35b entered                       = NO" in verdict
    assert "SOURCE_IDENTITY_COMPLETE             = NO" in verdict
    assert "CAPTURE_MODE_FROZEN                  = NO" in verdict


def test_eb35a_base_sha_not_frozen_despite_observed() -> None:
    obs = (EB35A_DIR / "02-runtime-and-git-observation.md").read_text(encoding="utf-8")
    record = (EB35A_DIR / "03-showcase-freeze-candidate-record.md").read_text(
        encoding="utf-8"
    )
    assert "observed_base_sha" in obs
    assert "BASE_SHA_FROZEN                      = NO" in obs or (
        "BASE_SHA_FROZEN" in obs and "BASE_SHA_FROZEN                      = NO" in (
            EB35A_DIR / "06-eb35a-verdict.md"
        ).read_text(encoding="utf-8")
    )
    assert "base_sha_frozen          = NO" in record
    assert "BASE_SHA_FROZEN          = NO" in record
    assert "WORKING_TREE_CLEAN       = NO" in record
    assert "BASE_SHA_CANDIDATE_READY = NO" in record
    assert "BLOCKED_PENDING_OWNER_REVIEW" in obs
