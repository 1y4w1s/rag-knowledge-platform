# Suoyin V1.0 — Canonical Benchmark & Evidence Summary

> **Canonical** release evidence surface.  
> Baseline HEAD: `3289f65`.  
> Numbers without **scope + execution class** are not release claims.  
> BEIR / public-dataset deep history → [`benchmark-public-report.md`](benchmark-public-report.md) (**HISTORICAL** / research).  
> CI contract → [`project/v1-0-release-cut-line.md`](project/v1-0-release-cut-line.md) §CI Contract.

```text
Measurement on a bounded scope  ≠  general capability proof
```

---

## Execution classes

| Class | Meaning |
|-------|---------|
| **PR_CI** | Blocks merge on `master` via `.github/workflows/ci.yml` |
| **RELEASE** | Intended for release / nightly / dispatch checks; not ordinary PR |
| **MANUAL** | Operator / live stack; not automated gate |
| **RESEARCH** | Research archive / Formal protocol; not product accuracy proof |
| **HISTORICAL** | Dated snapshot; may differ from current CI gate numbers |

---

## A. Retrieval Hit@3 golden（classic gate）

| Field | Value |
|-------|--------|
| **Metric** | Hit@3 |
| **Value** | **11/11** |
| **Scope** | Classic gate IDs `GQ-1`…`GQ-12` minus missing `GQ-9`; fixture under `backend/tests/fixtures/` |
| **Provenance** | `tests/test_retrieval_golden.py` · mock embeddings on PR `test` job |
| **Execution class** | **PR_CI / BLOCKING** |
| **Claim boundary** | Regression gate for retrieval/ingest changes on this frozen set. **≠** general Q&A accuracy. |

Full golden fixture size: **109** cases (`golden_qa` in `baseline.json`). Pytest may execute the full parametrize set; the **hard public gate narrative** for “11/11” is the classic subset above. Do not equate “109” or any historical “135 passed” pytest tally with the 11/11 gate without stating which surface.

---

## B. Real / local-BGE retrieval baseline

Source: `backend/tests/benchmark/baseline.json` (`version: v5`, updated_at `2026-07-23`) · enforced by `rag-golden` + `benchmark-gate` (`ci_baseline_check.py`).

| Field | Value |
|-------|--------|
| **Metric** | Hit@k (k=3) on `golden_qa` non-rejection set |
| **Value** | **baseline = 0.955** · **allowed_drop = 0.02** · **absolute_min = 0.90** |
| **Scope** | `run_benchmark.py --dataset golden_qa` · **local BGE** · `--skip-entity-extract` (no paid LLM) |
| **Provenance** | baseline.json `golden_qa` · CI jobs `rag-golden` / `benchmark-gate` |
| **Execution class** | **PR_CI / BLOCKING** |
| **Claim boundary** | Local-BGE retrieval regression vs frozen baseline. **≠** answer accuracy, Agent quality, or production SLA. |

PR CI is paid-LLM independent but **not** claimed fully offline: BGE artifacts may need configured HF mirror/cache.

---

## C. Enterprise / Advanced measurements

### C.1 Enterprise QA — CI gate

| Field | Value |
|-------|--------|
| **Metric** | Hit@3 |
| **Value** | **0.60** (60%) gate baseline · `drop_fail_pp=0.05` · `absolute_min=0.50` |
| **Scope** | `enterprise_qa` · local BGE · `rag-enterprise` → `benchmark-gate` |
| **Provenance** | baseline.json `enterprise_qa` · note: G3 2026-08-03 ruler Hit@3=60% (54/90) |
| **Execution class** | **PR_CI / BLOCKING** |
| **Claim boundary** | CI regression floor for enterprise retrieval set. |

### C.2 Enterprise QA — dated observation（not the CI floor）

| Field | Value |
|-------|--------|
| **Metric** | Hit@3 |
| **Value** | **71.1%** (0.711) |
| **Scope** | n=90 · real local BGE · 2026-08-09 FTS-adaptation A/B control (production RRF 1.0/1.5) |
| **Provenance** | README / `docs/benchmark-public-report.md` · cn-fts adapt artifacts |
| **Execution class** | **HISTORICAL / MANUAL** snapshot |
| **Claim boundary** | Dated observation under that experiment. **≠** current CI gate (60%). Do not treat as permanent Enterprise score. |

### C.3 Advanced QA

| Field | Value |
|-------|--------|
| **Metric** | Hit@3 |
| **Value** | **14/14** (= 1.0 on non-rejection) · `drop_fail_pp=0.10` |
| **Scope** | `advanced_qa` · local BGE · `rag-advanced` |
| **Provenance** | baseline.json · note C2 measured 2026-07-21 |
| **Execution class** | **PR_CI / BLOCKING** |
| **Claim boundary** | Small-n advanced retrieval gate. **≠** general “advanced Agent” capability. |

### C.4 CRAG

| Field | Value |
|-------|--------|
| **Metric** | Hit@3 |
| **Value** | sample100 historical ~0.26; NW-2 retest sample100=0.02; full ~1/2706 |
| **Scope** | CRAG scripts · informational |
| **Execution class** | **RELEASE** informational / **HISTORICAL** |
| **Claim boundary** | Not a PR blocker; environment-sensitive. |

---

## D. Agent Golden 168

| Field | Value |
|-------|--------|
| **Metric** | Suite size / scenario coverage |
| **Value** | **168** cases (`backend/tests/golden_agent_qa.json`) |
| **Scope** | Agent behavior golden; `tests/test_agent_golden.py` |
| **Provenance** | TECH-7 / fixture loader references |
| **Execution class** | **RELEASE_ONLY / MANUAL** |
| **Claim boundary** | Suite **exists** for release/manual runs. **≠** ordinary PR CI proof of Agent quality. |

---

## E. ADV（adversarial frozen panel）

| Field | Value |
|-------|--------|
| **Metric** | Primary strata pass · trial pass |
| **Value** | primary **2/4** · trials **10/20** · per-stratum **0/5 · 5/5 · 5/5 · 0/5** (ANS/UNA/PART/CON) |
| **Scope** | Frozen four-strata panel · local model `zai-org/glm-4.6v-flash` · dated 2026-08-23 convergence |
| **Provenance** | [`status/v1-convergence-status-2026-08-23.md`](status/v1-convergence-status-2026-08-23.md) · [`status/adversarial-v1-convergence-2026-08-23.md`](status/adversarial-v1-convergence-2026-08-23.md) |
| **Execution class** | **RESEARCH_ARCHIVE** / CHARACTERIZED |
| **Claim boundary** | Characterized residual failures (ANS trigger / CON terminal). Rollout **NO**. **≠** universal adversarial robustness. |

---

## F. W9 Critic

| Field | Value |
|-------|--------|
| **Metric** | Implementation + bounded research evidence |
| **Value** | Code present; flags default **OFF**; runtime rollout **NO** |
| **Scope** | Critic → directed re-retrieval research; Formal Critic quality **not** general semantic Critic proof |
| **Provenance** | Cut Line risky-feature map · config `rag_critic_*` / `agent_l3_critic_retrieval_enabled` |
| **Execution class** | **RESEARCH_ARCHIVE** |
| **Claim boundary** | Keep Critic **DEFAULT OFF**. Do not upgrade W9 into production Critic quality claim. |

---

## G. W10 Formal（Showcase T1-only）

| Field | Value |
|-------|--------|
| **Metric** | T1 citation-scope compliance (`final_citation_ids ⊆ gated_scope_ids`) |
| **Value** | eligible **11** · compliant **11** · violation **0** · excluded **1** · rate **100%** on that scope |
| **Scope** | Authorized Showcase **T1-only** Formal scope `w10_showcase_t1_only_v1` |
| **Provenance** | commit `6bf35b6` · `docs/research/w10-eb44-t1-formal-measurement/formal-t1-result.json` · [`research/w10-closure/`](research/w10-closure/) |
| **Execution class** | **RESEARCH_ARCHIVE** (sealed Formal) |
| **T2** | **NOT_APPLICABLE** |
| **T3** | **NOT_APPLICABLE** |
| **Claim boundary** | **Only:** “T1 citation-scope compliance on the authorized Showcase T1-only Formal scope.” **Never:** 100% RAG accuracy · 100% Agent accuracy · 100% grounding accuracy · T2/T3 PASS. |

Product After used for that Formal path was **DEGRADED** (`llm_called=false`) — see W10 closure known limitations.

---

## H. C4 canonical demo

| Field | Value |
|-------|--------|
| **Metric** | Scripted product-path PASS layers |
| **Value** | `V1_0_C4_CANONICAL_DEMO_PASS` when layers SYSTEM_REACHABLE … CITATION_SOURCE_OK (+ unsupported refuse) pass |
| **Scope** | `scripts/demo.ps1` · auth → KB → ingest → index → grounded Q+citation → unsupported refuse |
| **Provenance** | commit `bc025c4` · README Canonical Demo · live chat provider required |
| **Execution class** | **MANUAL** |
| **Claim boundary** | Proves the **public product path** under documented provider config. **≠** general accuracy, Critic/L3/L4, load/SLA, or multi-provider matrix. |

---

## Number audit（common ambiguous figures）

| Figure | Status | How to cite |
|-------|--------|-------------|
| **11/11** Hit@3 | **VALID** PR_CI classic gate | Always say mock golden gate subset |
| **0.955** | **VALID** PR_CI local-BGE baseline | With drop/min thresholds |
| **109** | **VALID** fixture size | Not the same as 11/11 |
| **135** | **HISTORICAL / ambiguous** pytest tally in old notes | Prefer 109 / 11; do not use as gate |
| **60%** Enterprise | **VALID** CI gate | Distinct from 71.1% |
| **71.1%** | **HISTORICAL** dated observation | Scope n=90 · 2026-08-09 |
| **14/14** | **VALID** Advanced CI baseline | Small-n |
| **168** | **VALID** Agent Golden size | RELEASE/MANUAL only |
| **2/4 · 10/20** | **VALID** ADV CHARACTERIZED | Research archive |
| **100%** (W10 T1) | **VALID only** as T1 citation-scope on Showcase Formal | Never bare “100% accuracy” |
| BEIR Hit@3 (52% / 23% / …) | **HISTORICAL** public-dataset report | Not v1.0 product gate |

---

## Related

- [`architecture.md`](architecture.md)  
- [`status/v1-known-limitations.md`](status/v1-known-limitations.md)  
- [`benchmark-public-report.md`](benchmark-public-report.md) (BEIR / HISTORICAL)  
- [`research/v1-0-closure-inventory/04-ci-and-test-surface.md`](research/v1-0-closure-inventory/04-ci-and-test-surface.md)  
