"""ADVERSARIAL P3 real retrieval layer (Layer R) orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.eval.adversarial_capability.capability_cases import CAPABILITY_CASE_BY_ID, CapabilityCase
from app.eval.adversarial_capability.corpus_fixtures import CORPUS_BY_ID
from app.eval.adversarial_capability.p1_freeze import load_p1_manifest
from app.eval.adversarial_capability.p2_design import PRIMARY_CAPABILITY_CASE_IDS, ROUND_START_MASTER_SHA
from app.eval.adversarial_capability.p3_retrieval import rank_corpus_chunks, score_case_retrieval
from app.services.ingestion.embedder import embed_texts

STAGE = "ADVERSARIAL_P3_REAL_RETRIEVAL"
SCHEMA_VERSION = "w8-adversarial-p3-real-retrieval-v1"
REPORT_REL = Path("tests/fixtures/l4_adversarial_capability/w8-adversarial-p3-real-retrieval.json")
ARTIFACT_TMP = Path("artifacts/benchmarks/tmp/reports/w8-adversarial-p3-real-retrieval.json")
TOP_K = 5
EMBED_PROVIDER = "bge"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def git_sha() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=_repo_root(),
            text=True,
            timeout=10,
        )
        return out.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def _chunk_content_hash(corpus_id: str) -> str:
    corpus = CORPUS_BY_ID[corpus_id]
    payload = [{"chunk_id": c["chunk_id"], "text": c["text"]} for c in corpus.chunks]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_p1_corpus_identity(manifest: dict[str, Any]) -> dict[str, Any]:
    mismatches: list[str] = []
    for case in manifest.get("capability_cases", []):
        if case["case_id"] not in PRIMARY_CAPABILITY_CASE_IDS:
            continue
        code = CAPABILITY_CASE_BY_ID[case["case_id"]]
        if code.corpus_fingerprint != case["corpus_fingerprint"]:
            mismatches.append(f"{case['case_id']}: fingerprint")
        if _chunk_content_hash(code.corpus_fixture_id) != _chunk_content_hash(case["corpus_fixture_id"]):
            mismatches.append(f"{case['case_id']}: chunk hash")
    return {
        "p1_manifest_schema": manifest.get("schema_version"),
        "CAPABILITY_VALID_DENOMINATOR": manifest.get("CAPABILITY_VALID_DENOMINATOR"),
        "corpus_identity_valid": len(mismatches) == 0,
        "mismatches": mismatches,
    }


async def _embed_all(texts: list[str]) -> list[list[float]]:
    return await embed_texts(texts, provider=EMBED_PROVIDER)


async def run_case_retrieval(case: CapabilityCase) -> dict[str, Any]:
    corpus = CORPUS_BY_ID[case.corpus_fixture_id]
    texts = [case.question] + [c["text"] for c in corpus.chunks]
    vectors = await _embed_all(texts)
    query_vector = vectors[0]
    chunk_vectors = {
        corpus.chunks[i]["chunk_id"]: vectors[i + 1] for i in range(len(corpus.chunks))
    }
    hits = rank_corpus_chunks(
        corpus=corpus,
        query_vector=query_vector,
        chunk_vectors=chunk_vectors,
        top_k=TOP_K,
    )
    row = score_case_retrieval(case, hits)
    row["corpus_fixture_id"] = case.corpus_fixture_id
    row["corpus_fingerprint"] = case.corpus_fingerprint
    row["embedding_provider"] = EMBED_PROVIDER
    row["embedding_model"] = settings.embedding_provider
    return row


def ready_for_p4(case_rows: list[dict[str, Any]], identity: dict[str, Any]) -> tuple[bool, str]:
    if not identity.get("corpus_identity_valid"):
        return False, "corpus_identity_invalid"
    if identity.get("CAPABILITY_VALID_DENOMINATOR") != 4:
        return False, "denominator_not_4"
    if len(case_rows) != 4:
        return False, "incomplete_cases"
    return True, "p3_valid_for_layer_a"


async def run_adversarial_p3_real_retrieval(*, adv_p3_base_sha: str | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    manifest = load_p1_manifest(_repo_root() / "backend")
    identity = verify_p1_corpus_identity(manifest)
    case_rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for cid in PRIMARY_CAPABILITY_CASE_IDS:
        case = CAPABILITY_CASE_BY_ID[cid]
        try:
            case_rows.append(await run_case_retrieval(case))
        except Exception as exc:  # noqa: BLE001 — measurement boundary
            errors.append(f"{cid}: {exc}")
    ready, ready_reason = ready_for_p4(case_rows, identity)
    state = "PASS" if ready and not errors else ("CHARACTERIZED" if case_rows else "INVALID")
    if errors and not case_rows:
        state = "INVALID"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "stage": STAGE,
        "round_start_master_sha": ROUND_START_MASTER_SHA,
        "adv_p3_base_sha": adv_p3_base_sha or git_sha(),
        "p2_frozen": True,
        "layer": "REAL_RETRIEVAL_VALIDATION",
        "embedding_provider": EMBED_PROVIDER,
        "top_k": TOP_K,
        "corpus_identity": identity,
        "cases": case_rows,
        "errors": errors,
        "measurement_state": state,
        "ready_for_p4": ready and not errors,
        "ready_for_p4_reason": ready_reason if ready else (errors[0] if errors else ready_reason),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "product_remediation": False,
    }
    root = _repo_root()
    for rel in (REPORT_REL, ARTIFACT_TMP):
        out = root / "backend" / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload["output_paths"] = [str(root / "backend" / REPORT_REL)]
    return payload


def main() -> int:
    payload = asyncio.run(run_adversarial_p3_real_retrieval())
    print(
        f"state={payload['measurement_state']} ready_for_p4={payload['ready_for_p4']} "
        f"cases={len(payload['cases'])}"
    )
    return 0 if payload["measurement_state"] in {"PASS", "CHARACTERIZED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
