"""W10 E-B36 human owner stamp issuance — deterministic docs/schema tests."""

from __future__ import annotations

from pathlib import Path
import re

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
EB36_DIR = REPO_ROOT / "docs" / "research" / "w10-eb36-human-owner-stamp-issuance"
STAMP_PATH = EB36_DIR / "01-approved-owner-stamp.md"

REQUIRED_FILES = (
    "README.md",
    "01-approved-owner-stamp.md",
    "02-human-issuance-provenance.md",
    "03-post-issuance-effect-evaluation.md",
    "04-acquisition-entry-status.md",
    "05-eb36-verdict.md",
)

FROZEN_BASE_SHA = "3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6"
ISSUED_AT = "2026-08-25T08:33:45Z"

REQUIRED_YES_GATES = (
    "OWNER_AUTHORIZATION_ISSUED",
    "SOURCE_APPROVED",
    "AFTER_SOURCE_APPROVED",
    "MAY_ISSUE_APPROVED_OWNER_STAMP",
)

MUST_REMAIN_NO_GATES = (
    "ACQUISITION_EXECUTION_READY",
    "E-B_FORMAL_READY",
)

PROHIBITION_MARKERS = (
    "DO NOT",
    "MUST NOT",
    "禁止",
    "⇏",
    "non-goal",
    "Does not",
    "不得",
    "remain",
    "still NO",
    "not flip",
    "Forbidden",
    "forbidden",
    "must remain",
    "FORBIDDEN",
    "≠",
    "not auto",
    "NOT ",
    "**NO**",
    "= NO",
    "keeps READY = NO",
    "still keeps",
)


def _package_text() -> str:
    parts: list[str] = []
    for name in REQUIRED_FILES:
        parts.append((EB36_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def _stamp_text() -> str:
    return STAMP_PATH.read_text(encoding="utf-8")


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


def _has_gate_no(text: str, var: str) -> bool:
    return bool(
        re.search(rf"{re.escape(var)}\s*=\s*NO\b", text)
        or re.search(
            rf"\|\s*`?{re.escape(var)}`?\s*\|\s*\*?\*?\s*NO\s*\*?\*?\s*\|",
            text,
            re.IGNORECASE,
        )
    )


@pytest.mark.parametrize("filename", REQUIRED_FILES)
def test_eb36_required_files_exist(filename: str) -> None:
    path = EB36_DIR / filename
    assert path.is_file(), f"missing {path.relative_to(REPO_ROOT)}"


def test_eb36_exactly_one_canonical_approved_stamp() -> None:
    stamp = _stamp_text()
    package = _package_text()
    assert "CANONICAL" in stamp.upper() or "canonical" in stamp.lower()
    assert "authorization_status       = APPROVED" in stamp
    # Only one stamp file may declare APPROVED authorization_status as the artifact
    approved_status_files = []
    for name in REQUIRED_FILES:
        body = (EB36_DIR / name).read_text(encoding="utf-8")
        if re.search(r"authorization_status\s*=\s*APPROVED\b", body):
            if name.startswith("01-") or "canonical" in body.lower():
                approved_status_files.append(name)
    assert "01-approved-owner-stamp.md" in approved_status_files
    assert package.count("schema_version             = eb30_owner_stamp_v1") >= 1
    # No second APPROVED stamp artifact filename pattern
    stamp_like = list(EB36_DIR.glob("*stamp*.md"))
    assert stamp_like == [STAMP_PATH]


def test_eb36_stamp_core_fields() -> None:
    stamp = _stamp_text()
    assert "stamp_kind                 = OWNER_AFTER_SOURCE_APPROVAL" in stamp
    assert "schema_version             = eb30_owner_stamp_v1" in stamp
    assert "authorization_status       = APPROVED" in stamp
    assert "auto_derived               = false" in stamp
    assert "issuer_class               = human_owner" in stamp
    assert "owner_identity             = suoyin_project_owner" in stamp
    assert "source_identity            = suoyin_local_research_product_after_v1" in stamp
    assert "after_source_id            = suoyin_local_research_product_after_v1" in stamp
    assert "capture_mode               = product_stream" in stamp
    assert "model_backend_identity     = none_no_llm" in stamp
    assert (
        "runtime_identity           = suoyin_backend_venv_cpython_3.11.9_win10_amd64"
        in stamp
    )
    assert f"base_sha                   = {FROZEN_BASE_SHA}" in stamp
    assert "run_identity               = w10_showcase_narrow_*" in stamp
    assert f"issued_at                  = {ISSUED_AT}" in stamp
    assert "review_by                = 2026-09-30" in stamp
    assert "on_trigger               = REVOKE_OR_REISSUE" in stamp


def test_eb36_issued_at_present_iso8601() -> None:
    stamp = _stamp_text()
    assert re.search(
        r"issued_at\s*=\s*\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\b", stamp
    )
    assert ISSUED_AT in stamp
    # Must not reuse freeze frozen_at
    assert "2026-08-25T08:15:42Z" not in stamp.split("issued_at")[1][:80]


def test_eb36_human_provenance_present() -> None:
    prov = (EB36_DIR / "02-human-issuance-provenance.md").read_text(encoding="utf-8")
    assert "confirmation_kind    = HUMAN_OWNER_STAMP_ISSUANCE" in prov
    assert "confirming_party     = suoyin_project_owner" in prov
    assert "auto_derived         = false" in prov
    assert "NOT:" in prov or "It is NOT" in prov
    assert "Cursor-derived" in prov
    assert "CI-derived" in prov
    assert "pytest-derived" in prov


def test_eb36_scope_exact_match() -> None:
    stamp = _stamp_text()
    assert "Showcase Track" in stamp
    assert "BP-A" in stamp
    assert "w9_critic_frozen_12" in stamp
    assert "C01..C11" in stamp or "C01–C11" in stamp
    assert "INELIGIBLE_NOT_SCORED" in stamp
    assert "A4 live LLM" in stamp
    assert "S2 empty-gate" in stamp
    assert "synthetic/isomorphic After" in stamp
    assert "E-B18 author-owned rebound" in stamp
    assert "Development Backend substituted as Formal Source" in stamp


def test_eb36_no_formal_gate_flip() -> None:
    text = _package_text()
    for var in MUST_REMAIN_NO_GATES:
        assert _has_gate_no(text, var), f"expected NO for {var}"
        hits = _lines_declaring_gate_yes(text, var)
        assert not hits, f"{var} unexpectedly YES:\n" + "\n".join(hits)
    assert "FORMAL_OBSERVATION" in text
    assert "NOT_STARTED" in text
    assert "MAY_ENTER_FORMAL_OBSERVATION_WINDOW" in text


def test_eb36_approval_effects_yes() -> None:
    text = _package_text()
    for var in REQUIRED_YES_GATES:
        assert _has_gate_yes(text, var), f"missing YES for {var}"


def test_eb36_no_accidental_llm_pin() -> None:
    stamp = _stamp_text()
    assert "formal_model_identity      = DEFER_TO_BENCHMARK_TRACK" in stamp
    assert "model_backend_identity     = none_no_llm" in stamp
    assert "llm_called_expected        = false" in stamp
    assert "generation_config_ref      = N/A" in stamp
    # Must not claim a concrete local/API model as Formal Primary on stamp
    assert "LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = YES" not in stamp
    assert not re.search(r"formal_model_identity\s*=\s*(?!DEFER_TO_BENCHMARK_TRACK)\S+", stamp)


def test_eb36_dependency_limitation_honest() -> None:
    stamp = _stamp_text()
    assert "DEPENDENCY_SNAPSHOT_PINNED = NO" in stamp
    assert "EXPLICITLY_UNPINNED_SHOWCASE" in stamp
    assert "SHOWCASE_REPRODUCIBILITY_LIMITATION" in stamp
    assert "NOT_ISSUANCE_BLOCKER       = YES" in stamp


def test_eb36_historical_ea4_separation() -> None:
    text = _package_text()
    assert "E-A4" in text or "w10-ea4-formal-window-result" in text
    assert FROZEN_BASE_SHA in text


def test_eb36_waiting_for_acquisition_entry_review() -> None:
    verdict = (EB36_DIR / "05-eb36-verdict.md").read_text(encoding="utf-8")
    assert "OWNER_STAMP_ISSUED_APPROVED" in verdict
    assert "WAITING_FOR_ACQUISITION_ENTRY_REVIEW" in verdict
    assert "ISSUANCE_INTEGRITY = PASS" in verdict
