# v1.1 Benchmark Design — Agent-Native Knowledge Matrix

> **Companion to**: [`v1.1-agent-native-knowledge-charter.md`](v1.1-agent-native-knowledge-charter.md)  
> **Status**: Research design (docs-only) · **Date**: 2026-08-24  
> **Purpose**: Executable benchmark protocol for matrix cells A–F

---

## 1. Design Principles

1. **Substrate is the only variable** — agent, model, corpus, evaluator, and FactGoal labels are fixed per run batch.
2. **No Wiki-only truth** — even cell D/E must produce `EvidenceItem` ledger entries tied to source provenance.
3. **Acceptable-set scoring** — trajectories need not match one golden tool path (W8 semantics).
4. **Denominator first** — publish case count, skip count, and invalid count before any rate.
5. **Cost is not optional** — token and latency columns are required for publication.

---

## 2. Frozen Control Profile

### 2.1 Model Profile (W8/W9 Freeze Semantics)

| Parameter | Value |
|-----------|-------|
| Model | `zai-org/glm-4.6v-flash` (or successor declared in run manifest) |
| Provider | LM Studio / OpenAI-compatible local |
| Thinking | OFF |
| Temperature | 0 |
| Context | 8192 |
| Planner timeout | 90s |
| Max agent steps | Same as W8 P0 (document per run) |

### 2.2 Agent Flag Profiles by Cell

| Cell | `agent_l4_fact_decomposition_enabled` | `agent_l4_evidence_matcher_enabled` | `agent_l4_stop_policy_enabled` | `rag_critic_enabled` | Notes |
|------|--------------------------------------|-------------------------------------|----------------------------------|----------------------|-------|
| A | False | False | False | False* | L3 or legacy thorough baseline |
| B | True | True | True | False* | Full L4 P0 stack |
| C | True | True | True | False* | + graph adapter |
| D | True | True | True | False* | + wiki adapter; hybrid OFF |
| E | True | True | True | False* | + wiki adapter; hybrid fallback ON |

\* Critic runs in dedicated K9 cross-substrate batch; not mixed into primary accuracy runs unless explicitly labeled.

### 2.3 Corpus Freeze

| Field | Specification |
|-------|---------------|
| Corpus ID | `v1.1-pilot-001` (placeholder — assign at K3) |
| Source | Enterprise handbook subset + L4 benchmark v1 compatible docs |
| kb_id | Single workspace KB; no cross-KB unless case-tagged |
| Chunking | Identical ingest pipeline snapshot; substrate-specific indexes derived from same chunks |
| Language | zh-CN primary; en cases optional secondary tag |

---

## 3. Matrix Cell Protocols

### 3.1 Cell A — Hybrid RAG Baseline

**Adapter**: Direct `semantic_search` / `retrieve_workspace_chunks` (existing tools).

**Pre-run gate**:
```bash
cd backend && pytest tests/test_retrieval_golden.py -q
```
Must pass **11/11** Hit@3 before A scores are valid.

**Expected behavior**: Strong T1/T4; weaker T2/T11 without decomposition.

### 3.2 Cell B — Fact-Decomposed Hybrid

**Adapter**: Same as A + FactDecomposer init + EvidenceMatcher post-tool.

**Isolation claim**: B − A = FactGoal decomposition value (not new index).

**Key metrics**: Multi-hop completion (T2), hop efficiency, evidence recall.

### 3.3 Cell C — Graph Baseline

**Adapter**: `knowledge_follow` + entity recall; implementation **TBD after K4 audit**.

**Candidate implementations** (audit in K4):

| Option | Pros | Cons |
|--------|------|------|
| In-repo `graph_entity_recall` extension | No new dep; audit trail | Limited relation types |
| LightRAG offline index | Community baseline | Build/integration cost |
| Minimal co-occurrence graph | Cheap | Weak semantic edges |

**Pre-score gate**: K4 audit PASS + T11 mini-set (≥5) executes without harness error.

### 3.4 Cell D — LLM-Wiki Compiled

**Pipeline**:
```text
Frozen chunks → compile job (LLM) → wiki pages / fact cards
  → knowledge_lookup / knowledge_read tools
  → EvidenceMatcher (must cite source chunk IDs in provenance)
```

**Mandatory audit** (K2): Random 10% of compiled pages checked against source chunks.

**Abort condition**: Audit hallucination rate > 20% → D scores marked INVALID.

### 3.5 Cell E — Wiki + Hybrid

**Pipeline**:
```text
knowledge_lookup (wiki) → if miss or low confidence → hybrid_search
  → merge observations → single EvidenceLedger
```

**Success pattern**: T12 fast path + T6/T7 fallback to hybrid.

### 3.6 Cell F — Self-Evolving (Design Reference Only)

Not executed in v1.1. Benchmark **design** for v1.2:

| Phase | Benchmark |
|-------|-----------|
| Pre-patch | Full matrix A–E on snapshot `S` |
| Post-patch | Same on snapshot `S'` |
| Gate | No regression > 2% on any stratum primary metric |
| Rollback | Re-run on `S` if gate fails |

---

## 4. Case Schema (Pilot v1.1)

Each case is a JSON object (future fixture under `backend/tests/fixtures/v1_1_knowledge/` — **not created in charter window**):

```json
{
  "case_id": "K11-T2-001",
  "primary_taxonomy": "T2",
  "secondary_taxonomy": ["T4"],
  "matrix_cells": ["A", "B", "C", "D", "E"],
  "query": "…",
  "fact_goals": [
    {"id": "F1", "text": "…", "kind": "lookup", "required": true},
    {"id": "F2", "text": "…", "kind": "condition", "required": true}
  ],
  "gold_answer": "…",
  "gold_terminal": "finish",
  "acceptable_tools": ["knowledge_search", "hybrid_search", "knowledge_read"],
  "stratum": "multi_hop",
  "notes": ""
}
```

### 4.1 Pilot Distribution (K3 Minimum)

| Taxonomy | Count | Notes |
|----------|-------|-------|
| T1 | 3 | Baseline sanity |
| T2 | 4 | Multi-hop core |
| T3 | 2 | Version compare |
| T4 | 3 | Condition |
| T5 | 2 | Exception |
| T6 | 3 | Conflict |
| T7 | 2 | Recovery |
| T8 | 1 | Tool failure |
| T9 | 1 | Clarify |
| T10 | 2 | Refuse |
| T11 | 4 | Graph-oriented (C emphasis) |
| T12 | 3 | Wiki lookup (D/E emphasis) |
| **Total** | **30** | |

Stability: **3 trials** per case per cell → 90 trajectories/cell (timeout failures counted, not dropped).

---

## 5. Scoring Rubric

### 5.1 Primary Outcome (Per Trial)

| Outcome | Condition |
|---------|-----------|
| **SUCCESS** | Gold answer matched (semantic + key fact check) AND terminal class correct |
| **PARTIAL** | StopPolicy partial with ≥50% required facts covered AND no unsupported claims |
| **SAFE_REFUSE** | Gold terminal refuse/clarify AND agent matched |
| **FAIL** | Wrong answer, unsafe accept, or wrong terminal |
| **INVALID** | Harness error, scope bug, or audit failure |

### 5.2 Derived Rates

```text
answer_accuracy = (SUCCESS + weighted PARTIAL) / VALID_TRIALS
safe_outcome_rate = (SUCCESS + PARTIAL + SAFE_REFUSE) / EXECUTED_TRIALS
unsupported_claim_rate = trials_with_critic_fail / trials_with_generation
```

### 5.3 Evidence Metrics (Per Trial)

Computed from final `EvidenceState`:

```text
evidence_precision = |correct edges| / |emitted edges|
evidence_recall = |covered required facts| / |required facts|
citation_correctness = |valid citations| / |citations in answer|
```

### 5.4 Cost Aggregation (Per Cell)

Report **median and P95** across valid trials:

- `retrieval_steps`
- `context_tokens`, `prompt_tokens`, `generation_tokens`
- `query_latency_ms` (end-to-end)
- `index_latency_ms` (retrieval-only subset)

Plus **one-time** per cell:

- `index_build_cost_sec`
- `incremental_update_cost_sec` (single doc add)
- `disk_footprint_mb`
- `peak_ram_mb` / `peak_vram_mb`

---

## 6. Run Manifest

Every benchmark batch writes a manifest (gitignored under `backend/artifacts/benchmarks/tmp/`):

```json
{
  "schema_version": "v1.1-benchmark-001",
  "charter_ref": "docs/research/agent-native-knowledge/v1.1-agent-native-knowledge-charter.md",
  "matrix_cell": "B",
  "corpus_id": "v1.1-pilot-001",
  "git_sha": "…",
  "model_profile": { "model": "zai-org/glm-4.6v-flash", "thinking": "off", "timeout_s": 90 },
  "agent_flags": { "agent_l4_fact_decomposition_enabled": true },
  "substrate_adapter": "hybrid_fact_decomposed_v0",
  "case_ids": ["…"],
  "denominator": { "executed": 90, "valid": 88, "invalid": 2, "skipped": 0 },
  "harness_validity": "VALID"
}
```

**INVALID** if: product-path bypass (W9 C12 class), missing denominator field, or Retrieval Golden regression on A-path.

---

## 7. Comparison Report Template

### 7.1 Summary Table (Required)

| Metric | A | B | C | D | E |
|--------|---|---|---|---|---|
| Answer accuracy | | | | | |
| Evidence recall | | | | | |
| Multi-hop completion (T2) | | | | | |
| Hop efficiency | | | | | |
| Retrieval steps (median) | | | | | |
| Total tokens (median) | | | | | |
| Query latency P95 (ms) | | | | | |
| Index build cost (s) | | | | | |
| Timeout rate | | | | | |
| Safe outcome rate | | | | | |
| Unsupported claim rate | | | | | |

### 7.2 Stratum Win Chart

For each taxonomy T1–T12, mark **best cell** only if:

- Δ accuracy ≥ 5% vs A, **AND**
- Safe outcome rate ≥ A, **AND**
- Total tokens ≤ 1.5× A (or explicit cost waiver documented)

Otherwise mark **NO_CLEAR_WINNER**.

---

## 8. Harness Integration Plan (Future Windows)

| Phase | Harness action | Touches runtime? |
|-------|----------------|------------------|
| K1 | Add `KnowledgeSubstrateAdapter` protocol + injection point in eval only | Minimal stub, flag OFF |
| K3 | `backend/app/eval/knowledge_substrate/` package | Eval-only |
| K9 | Extend critic offline cases for wiki provenance | Eval-only |
| K10 | Freeze fixtures under `backend/tests/fixtures/v1_1_knowledge/` | Fixtures only |

**Charter window**: None of the above — design only.

---

## 9. Anti-Patterns (From v1.0 Lessons)

| Anti-pattern | W9/v1.0 lesson | v1.1 rule |
|--------------|----------------|-----------|
| Harness bypasses production plan construction | C12 false pass | Eligibility bit per case |
| Scorer ignores citation scope | P2-R1 BLOCKED | Final-answer scope check mandatory |
| Concluding from 1 invalid case | 11/12 provisional trap | Denominator + invalid split |
| Enabling by default after pilot | All L4 flags OFF | Research ≠ rollout |
| Comparing cells with different models | W8 INCONCLUSIVE ON run | Single model profile per batch |

---

## 10. Acceptance Criteria for Benchmark Design

This design doc is **COMPLETE** when:

- [x] Matrix A–F protocols defined
- [x] All §5 charter metrics mapped to scoring formulas
- [x] Pilot case distribution specified (30 minimum)
- [x] Control profile aligned with W8/W9 freeze
- [x] Run manifest schema defined
- [x] Comparison report template provided
- [x] Anti-patterns documented

---

*End of v1.1 Benchmark Design*
