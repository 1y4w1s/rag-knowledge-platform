# v1.1 Benchmark Validity & Confound Audit (K0.5)

> **Status**: K0.5 deliverable · **Date**: 2026-08-24  
> **Parent**: [`v1.1-agent-native-knowledge-charter.md`](v1.1-agent-native-knowledge-charter.md)  
> **Companion**: [`benchmark-design.md`](benchmark-design.md)  
> **Runtime diff**: 0 · **Test diff**: 0  
> **Gate**: K1 **BLOCKED** until K0.5 validity signoff (this document + charter/design alignment)

---

## 0. Purpose & Verdict Summary

v1.1 charter (K0) defined matrix cells A–F and fixed controls, but several **validity confounds** would invalidate substrate causal claims if left unresolved:

| Confound | K0 state | K0.5 resolution |
|----------|----------|-----------------|
| Control-plane vs substrate conflated in A/B | A = L3 OFF, B = L4 ON | Split **Layer S** (substrate-only) from **Control-Plane Ablation** |
| Critic ON/OFF mixed into accuracy runs | Inconsistent across cells | Layer S: Critic **OFF** + post-hoc safety scoring; Layer P: Critic **ON** |
| Product-path harness bypass (W9 C12) | Mentioned only in anti-patterns | **Product-Path Eligibility Law** (spec) |
| Wiki compile → eval leakage | Not specified | **Wiki Leakage Protocol** |
| `graph_entity_recall` treated as GraphRAG baseline | Charter §9 hook ambiguity | **Graph Baseline Fairness** — audit gate before C cell |
| Tool surface differs by substrate | `knowledge_follow` no-op on A/B/D | **Normalized vs Native Affordance** regimes |
| Token/step budgets unequal | Not explicit | **Equal-Budget** + **Native-Budget/Pareto** regimes |
| Build cost deferral heuristic | K4 ">10× A → defer" | **Compile Cost Accounting** + Pareto decision |
| Temporal/version queries (T3) | Taxonomy only | **Temporal Knowledge** axis decision |
| Single A–F matrix overloaded | One table for all claims | **Revised Matrix** (6 experimental layers) |

**K0.5 outcome**: Methodology moves from **REVISE** → **VALIDITY-HARDENED (pending signoff)**. Implementation (K1+) remains blocked until §12 gate checklist is signed.

---

## 1. Task 1 — Experimental Layers

### 1.1 Layer Taxonomy (Replaces Monolithic A–F Causal Table)

| Layer ID | Name | Causal question | Variable(s) | Fixed across cells |
|--------|------|-----------------|-------------|-------------------|
| **A0** | Legacy / Production Reference | "What does production do today?" | None (observational) | Production flags, production tool wiring |
| **CP** | Control-Plane Ablation | "Does L4 FactGoal stack add value over flat hybrid?" | L4 flags (decomposer, matcher, stop, reflection) | Substrate = Hybrid (A-class), Critic OFF, Regime N tools |
| **S** | Substrate Capability Matrix | "Which knowledge representation best supports grounded answers?" | **Knowledge substrate only** | Corpus, model, FactGoal labels, EvidenceLedger, Stop Policy, planner, critic setting (**OFF**), budgets, evaluator, context window, **L4 control-plane profile (fixed ON or OFF per batch — document in manifest)** |
| **NA** | Native-Affordance Matrix | "Does substrate-native traversal beat normalized interface?" | Tool regime (N vs A) | Substrate, equal-budget or native-budget (declared) |
| **P** | Product-System Matrix | "Does full product path (Critic ON) remain safe across substrates?" | Substrate (optional cross-check) | Critic **ON**, production entry, real scope/budget/orchestration |
| **T** | Temporal / Update Matrix | "How do representation and knowledge-state freshness interact?" | Compile snapshot age, update policy | See §9 |
| **F** | Self-Evolution Feasibility | "Is offline patch loop justified?" | Design only (v1.2) | — |

### 1.2 Layer S — Substrate Capability Matrix (Primary Causal Claim)

**Only variable**: knowledge substrate adapter backend (index structure, compilation artifact, retrieval implementation, hop strategy).

**Held constant** (identical across all Layer S cells):

- Frozen corpus snapshot ID and chunk provenance
- Local model profile (W8/W9 freeze)
- Frozen FactGoal labels per case (from L4 benchmark v1 schema — not re-generated per cell)
- EvidenceLedger integration path (Layer 3 invariants)
- Stop Policy rules and step budget
- Planner prompt, tool **schema names** (Regime N — see §6)
- Critic at runtime: **OFF** (prefer OFF for **all** Layer S cells)
- Evaluator version and scoring rubric
- Context window and timeout policy
- **L4 control-plane profile**: fixed per Layer S batch (recommended: **L4 ON** for all substrates so substrate comparison is not confounded with L3 vs L4; document choice in ValidityManifest)

### 1.3 A0 — Legacy / Production Reference (Non-Causal)

**Purpose**: Baseline observability for product today. **Not** included in substrate causal attribution denominators.

| Field | Value |
|-------|-------|
| Entry | Production `/chat` or documented production-equivalent harness profile |
| Flags | Whatever production uses (typically L4 OFF, Critic per product default) |
| Claim type | `LEGACY_REFERENCE` only — no "substrate X beats production" without Layer S/P parity |
| Denominator | Separate from `SUBSTRATE_CAUSAL_DENOMINATOR` |

### 1.4 Redefined Causal Baselines (Split Axes)

Old charter implied A vs B mixed **substrate** and **control-plane**. K0.5 splits:

| Comparison | Layer | Cell definitions | Isolated effect |
|------------|-------|------------------|-----------------|
| Hybrid flat vs Hybrid + FactGoal | **CP** | CP-0: Hybrid, L4 OFF · CP-1: Hybrid, L4 ON | Control-plane (FactGoal stack) |
| Hybrid vs Graph vs Wiki vs Wiki+Hybrid | **S** | S-A: Hybrid · S-C: Graph (post-K4 audit) · S-D: Wiki · S-E: Wiki+Hybrid | Substrate representation (L4 profile fixed) |
| Normalized tools vs native traversal | **NA** | Same substrate, Regime N vs Regime A | Interface affordance (not pure representation) |
| Substrate under Critic ON | **P** | P-A … P-E | Product safety / recovery (not substrate accuracy primary) |

**Naming**: Retain A–E as **substrate shorthand** in reports, but always prefix with layer ID in manifests (`layer=S`, `substrate_id=A`).

---

## 2. Task 2 — Critic / Safety Measurement

### 2.1 Layer S — Runtime Critic Fixed OFF

| Rule | Detail |
|------|--------|
| Runtime | `rag_critic_enabled=false` for **all** Layer S cells |
| Rationale | Critic recovery paths differ by substrate observation shape; mixing runtime Critic confounds substrate capability with product recovery |
| Scoring | **Deterministic post-hoc** pass on frozen trajectory outputs |

### 2.2 Post-Hoc Safety Scoring (Layer S — Required)

Same final answer text + EvidenceLedger snapshot → offline scorer (no re-generation):

| Metric | Definition |
|--------|------------|
| `unsupported_claim_rate` | Claims in final answer not supported by ledger + source excerpts / total claims |
| `citation_correctness` | Valid provenance (chunk_id / wiki_page_id → source chunk) / citations cited |
| `evidence_precision` | Correct FactGoal edges / emitted edges |
| `scope_provenance_safety` | No out-of-scope KB/workspace/run citations; foreign evidence not in published answer |
| `compilation_trust_violation` | Wiki summary treated as ground truth without ledger edge (D/E specific) |

Scorer version pinned in ValidityManifest (`post_hoc_scorer_id`).

### 2.3 Layer P — Product-System Matrix (Critic ON)

| Rule | Detail |
|------|--------|
| Runtime | `rag_critic_enabled=true` for **all** Layer P cells |
| Entry | Production path eligibility (§3) |
| Primary metrics | Safe outcome rate, Critic recovery success, zero unsafe accept |
| Claim type | `PRODUCT_SYSTEM_CLAIM` |

### 2.4 Claim Type Discipline

| Claim type | Layer | Example valid statement |
|------------|-------|-------------------------|
| `SUBSTRATE_CAPABILITY_CLAIM` | S (+ NA if labeled) | "Wiki substrate S-D achieved higher T12 lookup success than S-A at equal budget" |
| `PRODUCT_SYSTEM_CLAIM` | P | "With Critic ON, S-E had zero unsafe accepts on product-path-eligible cases" |
| `CONTROL_PLANE_CLAIM` | CP | "CP-1 improved T2 multi-hop vs CP-0 without new index" |
| `LEGACY_REFERENCE` | A0 | "Production answered 72% on pilot set (not comparable to Layer S without profile match)" |
| `AFFORDANCE_CLAIM` | NA | "Graph Regime A reduced hops vs Regime N at 1.3× token cost" |

**Invalid**: Publishing Layer S accuracy as product safety guarantee, or Layer P results as substrate representation superiority without regime declaration.

---

## 3. Task 3 — Product-Path Eligibility Law

> **Source lesson**: W9 P2-R1 **C12** — harness bypassed `prepare_agent_generation`, injected foreign chunks into `_stream_generation_phase`, mock tool scope → false `safe_outcome`. See `docs/tasks/rag/w9-critic-p2-r1-next-remediation-analysis.md`.

### 3.1 PRODUCT_PATH_ELIGIBILITY_PRECONDITION

A case trial is eligible for **`PRODUCT_CAPABILITY_DENOMINATOR`** only if **all** hold:

1. **Production entry point** — `run_react_loop` (or documented production-equivalent) from first tool dispatch through generation finalize
2. **Real scope** — `AgentToolScope` + `resolve_kb_ids` enforced; no pre-injected `gated_chunks`
3. **Real budget & orchestration** — same step budget, deadline, and critic budget as production profile
4. **No illegal evidence injection** — frozen oracle evidence enters only via successful scoped tool outcomes or documented production injection points
5. **No validation bypass** — `prepare_agent_generation`, `gate_agent_chunks`, and post-revision critic paths not mocked away

### 3.2 Ineligibility Outcomes

| Classification | Meaning | In denominator? |
|----------------|---------|-----------------|
| `PRODUCT_PATH_ELIGIBLE` | All preconditions met | Yes (Layer P) |
| `COMPONENT_ONLY` | Unit/component harness; not full product path | No — tag for Layer S component tests only |
| `MEASUREMENT_PROTOCOL_INVALID` | Harness construction violates preconditions (C12 class) | No — counts as **invalid**, triggers BLOCKED gate |

### 3.3 Spec-Only (K0.5)

This section is **measurement protocol specification only**. No harness implementation in K0.5 window. K1+ adapters must emit `product_path_eligibility` per trial in ValidityManifest.

### 3.4 v1.1 Application

| Layer | Eligibility required? |
|-------|----------------------|
| S | No (eval harness may use substrate adapter injection; declare `COMPONENT_ONLY` or `EVAL_SUBSTRATE_PATH`) |
| P | **Yes** — mandatory |
| A0 | Production path by definition |

---

## 4. Task 4 — Wiki Leakage Protocol

Compiled wiki (substrates D/E) introduces **train-test leakage** risk if evaluation questions or answers appear in compile inputs.

### 4.1 Strict Compile / Evaluation Isolation

```text
[Corpus chunks only] → COMPILE (offline) → ARTIFACT → FREEZE (hash) → MANIFEST → EVAL (frozen cases)
                              ↑                           ↑
                         no eval cases              no re-compile during eval
```

### 4.2 Compiler Allowed Inputs

| Allowed | Forbidden |
|---------|-----------|
| Frozen corpus chunk text + metadata (chunk_id, doc_id, kb_id) | Benchmark case JSON (`query`, `gold_answer`, `fact_goals`) |
| Enterprise handbook source docs in corpus snapshot | Evaluation holdout question lists |
| Compile prompt templates (generic, no case IDs) | Case IDs, taxonomy tags (T1–T13), stratum labels |
| Entity/relation extractors on corpus | Oracle chunk IDs from gold fixtures |
| Prior compile artifact version (for incremental update tests only, separate manifest) | Answer strings or acceptable-set keys |

### 4.3 Freeze Chain

| Step | Output |
|------|--------|
| 1. Compile | `wiki_artifact/` directory |
| 2. Freeze artifact | `artifact_sha256`, file manifest |
| 3. Freeze compile manifest | compiler version, model ID, prompt hash, input corpus_id, timestamp |
| 4. Evaluation | Cases loaded from **separate** fixture tree; eval harness references frozen `artifact_sha256` only |

### 4.4 Leakage Audit Checklist (Required Before D/E Layer S Scoring)

| Check | Method | Fail action |
|-------|--------|-------------|
| Question overlap | n-gram / embedding similarity: case `query` vs wiki page titles and Q→A pairs | FAIL if similarity > threshold (document threshold in manifest) |
| Answer-string leakage | Exact + normalized match: `gold_answer` substrings in wiki body | FAIL if unambiguous match |
| Oracle chunk leakage | Gold supporting chunk IDs must not appear as wiki "summary source" shortcuts without provenance | FAIL |
| Case-ID leakage | No `K11-T*` strings in artifact | FAIL |
| Template leakage | Compile prompts must not include benchmark taxonomy definitions | FAIL |

Audit log required in ValidityManifest (`wiki_leakage_audit_status`: PASS | FAIL | WAIVED with rationale).

### 4.5 T12 Fairness Rule

**T12 (Compiled lookup) must not reward Wiki specially.**

| Rule | Detail |
|------|--------|
| T12 cases | Must be answerable from **source corpus** via hybrid path (S-A) with acceptable effort |
| Wiki advantage | T12 measures lookup **efficiency**, not exclusive knowledge |
| Scoring | Report T12 success **and** hop/token delta vs S-A; stratum win requires defensible efficiency gain, not sole-source answer |
| Invalid T12 | Case whose answer exists only in compiled artifact and not in source chunks → **INVALID_STRATUM** |

---

## 5. Task 5 — Graph Baseline Fairness

### 5.1 Terminology (Mandatory)

| Term | Meaning |
|------|---------|
| `CURRENT_GRAPH_ENTITY_RECALL` | In-repo experimental hook (`graph_entity_recall` in `retrieval.py`, default OFF) — **recall augmentation**, not a GraphRAG baseline |
| `GRAPH_RAG_BASELINE` | Credible, frozen, reproducible graph index + adapter meeting Layer S invariants — **only this qualifies for S-C cell** |

**K0.5 rule**: Never equate the two. K4 audit must explicitly state which implementation (if any) earns `GRAPH_RAG_BASELINE` status.

### 5.2 K4 Pre-Implementation Audit (Required Before S-C Scoring)

Audit memo must document:

1. Implementation choice (in-repo extension vs LightRAG vs minimal co-occurrence — or NONE)
2. Build reproducibility (deterministic inputs → deterministic index hash)
3. Provenance-compatible evidence — graph observations emit `EvidenceItem` with chunk/source provenance
4. T11 mini-set feasibility (≥5 cases execute without harness error)
5. Build cost table (see §8)
6. Explicit **PASS / DEFER / FAIL** with evidence

### 5.3 Deferral Policy (Replaces ">10× A Build Cost → Defer")

**Removed heuristic**: Charter K4 "Build cost > 10× A → C remains optional" is **superseded**.

**New rule**:

| Condition | Action |
|-----------|--------|
| K4 audit PASS + minimal credible pilot (T11 mini-set runs) | S-C eligible for Layer S matrix |
| Build cost high but pilot completes | **Pareto decision** — include S-C on cost-accuracy frontier; do not auto-defer |
| `TARGET_HARDWARE_INFEASIBLE` | Only valid pre-measurement deferral — must document RAM/disk/time proof that pilot cannot run on declared benchmark hardware profile |
| Audit FAIL (no provenance, non-reproducible, harness broken) | S-C **excluded** from causal matrix; report as INCONCLUSIVE |

---

## 6. Task 6 — Tool Affordance Confound

Substrates differ in native traversal capability. Comparing Graph walk vs Hybrid flat search confounds **representation** with **interface affordance**.

### 6.1 Regime N — Normalized Interface

| Tool | Semantics |
|------|-----------|
| `knowledge_search` | Broad NL recall (adapter maps to substrate index) |
| `knowledge_read` | Fetch bounded excerpt by stable ID |

**All substrates** must implement Regime N. Planner prompt and tool schema **unchanged**.

Optional additional tools return structured `unsupported` in Regime N (no silent no-op without observation).

### 6.2 Regime A — Native Affordance

| Substrate | Additional native tools |
|-----------|-------------------------|
| Hybrid (S-A) | `hybrid_search` (explicit), doc/chunk adjacency if available |
| Graph (S-C) | `knowledge_follow`, `knowledge_lookup` (entity/relation) |
| Wiki (S-D/E) | `knowledge_lookup`, `knowledge_follow` (wiki links) |

### 6.3 Interpretation Rule

| Regime | Valid claim |
|--------|-------------|
| N | **Substrate capability** under fair interface (Layer S primary) |
| A | **Affordance advantage** (Layer NA) — e.g., fewer hops, lower tokens |
| A | **NOT** valid as pure "representation is better" without Regime N counterpart |

Layer S default: **Regime N**. Layer NA: paired runs N vs A per substrate with manifest flag `affordance_regime`.

---

## 7. Task 7 — Token / Budget Fairness

### 7.1 Equal-Budget Regime (Primary for Layer S Causal Claims)

| Parameter | Fixed across compared cells |
|-----------|----------------------------|
| Max agent steps | Same integer (W8 P0 documented value) |
| Max retrieval tool calls | Same cap |
| Context window | 8192 (model profile) |
| Planner timeout | 90s |
| Per-trial token soft cap | Optional equal cap (e.g., 24k total); exceeding → `BUDGET_EXCEEDED` terminal (counted, not dropped) |

**Comparison validity**: S-A vs S-D vs S-E must use Equal-Budget unless explicitly running Native-Budget/Pareto batch.

### 7.2 Native-Budget / Pareto Regime

| Parameter | Policy |
|-----------|--------|
| Steps/tokens | Each substrate uses **native** optimal defaults (documented per adapter) |
| Recording | **Mandatory** full trace: per-step tokens, latency, retrieval count |
| Claim | Pareto frontier points only — no single "winner" from unequal budgets |
| Chart | Accuracy vs total tokens, accuracy vs latency, hops vs tokens |

Both regimes may coexist in same research program but **must not be mixed** in one denominator without stratification.

---

## 8. Task 8 — Compile Cost Accounting

Every substrate report must include full cost decomposition. Wiki/Graph cells cannot claim accuracy without cost table.

### 8.1 Cost Components

| Component | Symbol | Definition |
|-----------|--------|------------|
| Initial build | `BuildCost` | Wall time + compute to create index/artifact from frozen corpus v0 |
| Incremental update | `UpdateCost(d)` | Cost to ingest one document update (or batch size documented) |
| Full rebuild | `RebuildCost` | Cost to rebuild from scratch after schema/compiler change |
| Storage | `StorageCost` | Disk footprint (MB) + optional object store |
| Query cost | `QueryCost` | Median tokens + latency per query (eval batch) |

### 8.2 Amortization Model

```text
TotalCost(N) = BuildCost + UpdateCost × Δdocs + N × QueryCost
```

| Derived metric | Formula |
|----------------|---------|
| Amortized build per query | `BuildCost / N` |
| Break-even N vs baseline | Smallest N where `TotalCost_Substrate(N) < TotalCost_Baseline(N)` |

Report at N ∈ {100, 1_000, 10_000} for enterprise planning scenarios.

### 8.3 Manifest Fields

`compile_cost_manifest` block in ValidityManifest (§11) — required for S-C, S-D, S-E before stratum wins.

---

## 9. Task 9 — Temporal Knowledge

T3 (Version comparison) and incremental update scenarios touch two distinct axes:

| Axis | Definition | Examples |
|------|------------|----------|
| **Representation** | How knowledge is stored (chunk, graph, wiki) | S-layer substrates |
| **Knowledge-state** | Corpus snapshot time, document version, stale vs fresh compile | Snapshot `v2024-Q1` vs `v2024-Q2` |

### 9.1 K0.5 Decision (Explicit)

**Primary v1.1 treatment**: **Orthogonal axis** within Layer **T** (Temporal / Update Matrix), not a separate substrate ID.

| Layer T cell | Variables |
|--------------|-----------|
| T-fix-S-D | Substrate S-D, frozen wiki artifact age 0, corpus v1 |
| T-stale-S-D | Same artifact, corpus updated (+Δdocs), **no recompile** (stale wiki test) |
| T-fresh-S-D | Corpus v2, **incremental recompile** |
| T-fix-S-A | Hybrid baseline on same snapshot pairs |

**Alternative (deferred unless K10 scale demands)**: Independent substrate "Temporal-Wiki" — only if Layer T orthogonal runs show representation × freshness interaction dominates; must be declared in manifest as `substrate_id=FRESH-WIKI`.

**Not vague**: v1.1 pilot (K3–K6) may **omit Layer T** runs; if omitted, no temporal freshness claims. Layer T is **optional for pilot**, **required for any v1.1 closeout claim about version comparison (T3)**.

---

## 10. Task 10 — Revised Matrix Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│ A0  LEGACY / PRODUCTION REFERENCE (observational, non-causal)            │
├──────────────────────────────────────────────────────────────────────────┤
│ CP  CONTROL-PLANE ABLATION — CP-0 (L4 OFF) vs CP-1 (L4 ON) on Hybrid     │
├──────────────────────────────────────────────────────────────────────────┤
│ S   SUBSTRATE CAUSAL MATRIX — S-A|S-C|S-D|S-E; Regime N; Critic OFF      │
├──────────────────────────────────────────────────────────────────────────┤
│ NA  NATIVE-AFFORDANCE MATRIX — Regime N vs A per substrate (Layer NA)    │
├──────────────────────────────────────────────────────────────────────────┤
│ P   PRODUCT-SYSTEM MATRIX — Critic ON; product-path eligibility required │
├──────────────────────────────────────────────────────────────────────────┤
│ T   TEMPORAL / UPDATE MATRIX — snapshot age × recompile policy (optional)│
├──────────────────────────────────────────────────────────────────────────┤
│ F   SELF-EVOLUTION FEASIBILITY — design only (v1.2); offline patch loop  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 10.1 Substrate ID Mapping (Charter Compatibility)

| Legacy cell | Layer S ID | Notes |
|-------------|------------|-------|
| A | S-A | Hybrid RAG |
| B | CP-1 (not S-layer) | FactGoal = control plane, not substrate |
| C | S-C | Requires K4 `GRAPH_RAG_BASELINE` audit PASS |
| D | S-D | Wiki compiled |
| E | S-E | Wiki + Hybrid |
| F | F | v1.2 design reference |

### 10.2 Recommended Execution Order (Updated)

1. **A0** — document production reference (optional)
2. **CP** — CP-0 vs CP-1 (RQ1 control-plane)
3. **S-A** — hybrid baseline + Retrieval Golden 11/11 gate
4. **S-D / S-E** — after K2 compile audit + wiki leakage PASS
5. **S-C** — after K4 graph audit PASS only
6. **NA** — paired affordance runs on winning S candidates
7. **P** — Critic ON product-path batch (K9 class)
8. **T** — if T3 claims needed
9. **F** — design review only

---

## 11. Task 11 — ValidityManifest Schema

Every benchmark batch MUST write a ValidityManifest (extends run manifest in `benchmark-design.md` §6).

### 11.1 Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `schema_version` | string | yes | e.g. `v1.1-validity-001` |
| `charter_ref` | string | yes | Path + git sha of charter |
| `validity_audit_ref` | string | yes | This document path + sha |
| `batch_id` | string | yes | Unique run batch identifier |
| `git_sha` | string | yes | Repo commit |
| `harness_validity` | enum | yes | `VALID` \| `INVALID` \| `PROVISIONAL` |
| `k0_5_signoff` | boolean | yes | false until human signoff |

### 11.2 Experimental Layer Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `experimental_layer` | enum | yes | `A0` \| `CP` \| `S` \| `NA` \| `P` \| `T` \| `F` |
| `layer_cell_id` | string | yes | e.g. `S-A`, `CP-1`, `P-E` |
| `substrate_id` | string | if S/NA/P | `A` \| `C` \| `D` \| `E` |
| `claim_types_allowed` | string[] | yes | Subset of §2.4 claim types |

### 11.3 Control Plane Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `corpus_id` | string | yes | Frozen corpus snapshot |
| `model_profile` | object | yes | Model, thinking, temp, ctx, timeout |
| `agent_flags` | object | yes | L4 flags documented |
| `fact_goal_source` | enum | yes | `FROZEN_LABELS` \| `LIVE_DECOMPOSER` (S-layer must use FROZEN_LABELS) |
| `critic_runtime` | enum | yes | `OFF` (Layer S) \| `ON` (Layer P) |
| `post_hoc_scorer_id` | string | if critic OFF | Scorer version for §2.2 |
| `planner_prompt_hash` | string | yes | Detect planner drift |

### 11.4 Affordance & Budget Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `affordance_regime` | enum | yes | `N` (normalized) \| `A` (native) |
| `budget_regime` | enum | yes | `EQUAL` \| `NATIVE_PARETO` |
| `max_agent_steps` | int | yes | Step cap |
| `max_retrieval_calls` | int | yes | Retrieval cap |
| `token_soft_cap` | int | no | Equal-budget cap if set |
| `token_trace_complete` | boolean | yes | All steps logged |

### 11.5 Product Path Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `product_path_eligibility` | enum | yes | `PRODUCT_PATH_ELIGIBLE` \| `COMPONENT_ONLY` \| `MEASUREMENT_PROTOCOL_INVALID` |
| `eligibility_checks` | object | yes | Booleans for §3.1 preconditions 1–5 |
| `c12_class_bypass_detected` | boolean | yes | Must be false for Layer P |

### 11.6 Wiki / Compile Block (S-D, S-E, Layer T)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `wiki_artifact_sha256` | string | if wiki | Frozen artifact hash |
| `compile_manifest_ref` | string | if wiki | Pointer to compile manifest |
| `wiki_leakage_audit_status` | enum | if wiki | `PASS` \| `FAIL` \| `WAIVED` |
| `wiki_leakage_audit_log_ref` | string | if wiki | Audit artifact path |
| `compile_cost_manifest` | object | if wiki/graph | §8 components populated |

### 11.7 Graph Block (S-C)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `graph_baseline_type` | enum | if graph | `GRAPH_RAG_BASELINE` \| `CURRENT_GRAPH_ENTITY_RECALL` \| `NONE` |
| `k4_audit_status` | enum | if graph | `PASS` \| `DEFER` \| `FAIL` |
| `k4_audit_ref` | string | if graph | Audit memo path |
| `index_reproducible_hash` | string | if graph | Deterministic index hash |

### 11.8 Temporal Block (Layer T)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `corpus_snapshot_version` | string | if T | e.g. `v2024-Q1` |
| `wiki_artifact_age_policy` | enum | if T | `FRESH` \| `STALE` \| `RECOMPILED` |
| `temporal_axis_mode` | enum | if T | `ORTHOGONAL` \| `INDEPENDENT_SUBSTRATE` |

### 11.9 Denominator Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `denominator.executed` | int | yes | Trials run |
| `denominator.valid` | int | yes | Valid trials |
| `denominator.invalid` | int | yes | Invalid (incl. protocol invalid) |
| `denominator.skipped` | int | yes | Skipped |
| `substrate_causal_denominator` | int | if S | Valid Layer S trials only |
| `product_capability_denominator` | int | if P | Product-path-eligible only |

### 11.10 Gate Block

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `retrieval_golden_passed` | boolean | if hybrid path | 11/11 Hit@3 |
| `k1_gate_status` | enum | yes | `OPEN` \| `BLOCKED_PENDING_K0_5_VALIDITY_SIGNOFF` |
| `blocking_confounds` | string[] | yes | Empty when signed off |

### 11.11 Example (Abbreviated)

```json
{
  "schema_version": "v1.1-validity-001",
  "validity_audit_ref": "docs/research/agent-native-knowledge/benchmark-validity-audit.md@abc123",
  "experimental_layer": "S",
  "layer_cell_id": "S-D",
  "substrate_id": "D",
  "claim_types_allowed": ["SUBSTRATE_CAPABILITY_CLAIM"],
  "critic_runtime": "OFF",
  "post_hoc_scorer_id": "v1.1-posthoc-001",
  "affordance_regime": "N",
  "budget_regime": "EQUAL",
  "product_path_eligibility": "COMPONENT_ONLY",
  "wiki_artifact_sha256": "…",
  "wiki_leakage_audit_status": "PASS",
  "k1_gate_status": "BLOCKED_PENDING_K0_5_VALIDITY_SIGNOFF",
  "blocking_confounds": []
}
```

---

## 12. Task 12 — Gate K1

### 12.1 Status

```text
K1_SUBSTRATE_ADAPTER_INTERFACE_SPEC
  GATE = BLOCKED_PENDING_K0_5_VALIDITY_SIGNOFF
```

No K1 implementation (adapter protocol, stubs, contract tests) until all conditions below are **RESOLVED** and `k0_5_signoff=true` on a review manifest.

### 12.2 Gate Conditions (All Required)

| # | Condition | K0.5 doc section | Status |
|---|-----------|------------------|--------|
| G1 | Experimental layers A0 / CP / S / NA / P / T / F defined; B reclassified as CP | §1, §10 | RESOLVED |
| G2 | Layer S fixed controls enumerated; substrate-only variable | §1.2 | RESOLVED |
| G3 | A0 separated from causal denominator | §1.3 | RESOLVED |
| G4 | Critic OFF (S) vs ON (P) policy + post-hoc scorer | §2 | RESOLVED |
| G5 | SUBSTRATE vs PRODUCT claim types | §2.4 | RESOLVED |
| G6 | Product-Path Eligibility Law (C12 lesson) | §3 | RESOLVED (spec) |
| G7 | Wiki compile/eval isolation + leakage audit | §4 | RESOLVED (spec) |
| G8 | T12 fairness rule | §4.5 | RESOLVED |
| G9 | GRAPH_RAG_BASELINE ≠ CURRENT_GRAPH_ENTITY_RECALL | §5 | RESOLVED |
| G10 | K4 deferral → Pareto + TARGET_HARDWARE_INFEASIBLE only | §5.3 | RESOLVED |
| G11 | Regime N vs Regime A affordance split | §6 | RESOLVED |
| G12 | Equal-Budget vs Native-Pareto regimes | §7 | RESOLVED |
| G13 | TotalCost(N) compile accounting | §8 | RESOLVED |
| G14 | Temporal axis: ORTHOGONAL (Layer T) | §9 | RESOLVED |
| G15 | ValidityManifest schema complete | §11 | RESOLVED |
| G16 | Charter + benchmark-design aligned to this audit | charter §K0.5, design §0 | PENDING merge |
| G17 | Human signoff `k0_5_signoff=true` | — | PENDING reviewer |

### 12.3 Unblocks K1 When

1. This document merged on research branch
2. Charter K1 marked BLOCKED with pointer here
3. `benchmark-design.md` references layers, regimes, ValidityManifest
4. Reviewer sets G17 (checklist review — no runtime work)

### 12.4 K1 Scope Reminder (Not Started in K0.5)

K1 deliverable remains: `KnowledgeSubstrateAdapter` protocol + eval-only stubs, default OFF, Retrieval Golden 11/11 on adapter=A path — **after** gate OPEN.

---

## 13. Signoff Checklist

- [ ] All §12 G1–G15 resolved in documentation
- [ ] G16 — charter/design PR merged
- [ ] G17 — research owner signoff
- [ ] No runtime or test diff in K0.5 PR
- [ ] K1 explicitly not started

---

*End of K0.5 Benchmark Validity & Confound Audit*
