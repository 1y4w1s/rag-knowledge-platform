# 01 — Previous blockers (final reclassification)

> Labels only: `RESOLVED` | `PARTIALLY_RESOLVED` | `BLOCKING`.  
> Baseline: E-B7 recheck + E-B8 construct + E-B9a/E-B9b contract freezes.

## Summary

| # | Topic | Classification | One-line why |
|---|---|---|---|
| 1 | After-window executor | **RESOLVED** | E-B6 test-only isomorphic executor exists; C12 ineligible; no Critic/P2-R3 runners |
| 2 | After snapshots | **PARTIALLY_RESOLVED** | Isomorphic After writable; product `_stream_generation_phase` After absent; reserved formal write locked |
| 3 | Claim gold (T2/T3) | **PARTIALLY_RESOLVED** | E-B9a schema+validator frozen; annotated ledger file **intentionally absent** |
| 4 | Empty gate (T4) | **PARTIALLY_RESOLVED** | E-B9b S2 suite contract frozen; real `w10-eb-empty-gate-cases.json` **intentionally absent** |
| 5 | Artifact identity | **RESOLVED** | E-B2 / E-A5 / P2-R3 / Critic / claim-gold / empty-gate identities isolated; reserved formal correctly absent |

**Full formal still blocked** because items 2–4 retain clearance residuals (see exact blockers in `04-final-gate.md`).

---

## 1. After-window executor → **RESOLVED**

| Evidence | Status |
|---|---|
| `backend/tests/w10_eb6_generation_observation_executor.py` | Present |
| Surfaces `observe_case` / `run_isomorphic_observation_suite` / `capture_isomorphic_after` | Present |
| Path: E-A2 prepare → author body → real `align_citations_to_answer` | Present |
| `execute_frozen_case` / P2-R3 formal runners | Not used |
| Product `_stream_generation_phase` wired for formal | **Not required for RESOLVED(C1)**; still absent for C2 honesty |

C1 (E-B4)「执行器存在」cleared. Residual LLM path belongs under **After snapshots**, not executor absence.

---

## 2. After snapshots → **PARTIALLY_RESOLVED**

| Capability | Status |
|---|---|
| Isomorphic After for C01–C11 (non-null content + citations) | Yes |
| C12 After fabricate refused | Yes |
| `observation_point=generation_final_content_and_citations` | Yes |
| `llm_called=false` honesty on isomorphic path | Yes |
| Product-LLM After via `_stream_generation_phase` | **Absent** |
| Reserved `w10-eb2-generation-observation-result.json` | **Absent** (expected; write refused by E-B6) |
| `measurement_valid=true` on smoke/synthetic path | **Hard-locked false** |

**Why not RESOLVED:** Full / honest formal denominator still lacks product generation终态 + authorized formal persistence. Synthetic After proves wiring only.

---

## 3. Claim gold → **PARTIALLY_RESOLVED**

### Cleared by E-B9a

| Deliverable | Status |
|---|---|
| Protocol `w10_eb_generation_claim_gold_v1` | Frozen |
| Schema `w10-eb-generation-claim-gold-v1.schema.json` | Present |
| Validator `validate_claim_gold_ledger` | Present |
| Critic oracle / LLM-judge keys rejected | Present |
| Module constant `E_B_FORMAL_READY = "NO"` | Frozen honesty |

### Still open (C3 residual)

| Expected for Full formal | Status |
|---|---|
| Annotated `w10-eb-generation-claim-gold-v1.json` | **Absent**（E-B9a `assert_gold_file_absent` requires this） |
| Human (non-LLM) labels bound to After / synthetic `content_sha256` | **Absent** |
| Cases covering T2/T3 denominators for measured targets | **Absent** |

**Contract ≠ gold.** Schema freeze does **not** clear C3.

---

## 4. Empty gate → **PARTIALLY_RESOLVED**

### Cleared by E-B9b

| Deliverable | Status |
|---|---|
| Suite id `w10_eb_empty_gate_v1` · `case_count=2` · purpose `empty_gate_refuse_ok` | Frozen |
| Strategy `S2_companion` | Frozen |
| Schema + validator | Present |
| W9 `w9_critic_frozen_12` / E-B2 v1 identity untouched | Asserted |
| C04/C07 substitute forbidden | Asserted |
| Refusal gold mirrors product `NO_CONTEXT_REPLY(_EN)` | Asserted |
| `E_B_EMPTY_GATE_CONTRACT_READY = "YES"` | Contract-only |
| Module `E_B_FORMAL_READY = "NO"` | Frozen honesty |

### Still open (C4 residual)

| Expected for Full formal | Status |
|---|---|
| Real fixture `w10-eb-empty-gate-cases.json` | **Absent**（E-B9b requires absence during contract freeze） |
| Eligible cases with `evidence_count=0` + `expected_refusal=true` on disk | **Absent** |
| Dual-suite Full formal packaging contract（E-B2 envelope + empty suite composition） | **Not frozen** as executable formal combo |
| Formal empty-gate result file | Correctly **absent** |

**Contract ≠ denominator.** S2 identity alone does **not** clear C4.

---

## 5. Artifact identity → **RESOLVED**

Isolation / anti-collision (E-B7 `03` still holds; E-B9a/9b add distinct layers):

| Layer | Identity | Collision risk |
|---|---|---|
| L-Obs | `w10_eb2_generation_observation_v1` · suite `w9_critic_frozen_12` | Distinct from Critic runners / E-A5 |
| L-Gold | `CLAIM_GOLD_LEDGER` · `w10_eb_generation_claim_gold_v1` | Independent; not nested in E-A5 |
| L-Empty | `w10_eb_empty_gate_v1` · `EMPTY_GATE_SUITE_SCHEMA_EXAMPLE` | Explicitly ≠ `w9_critic_frozen_12` |
| L-EA5 | `w10-ea4-formal-window-result.json` · plan-construction point | E-B validators reject EA5 shapes |
| L-Formal-E-B | reserved observation result | Correctly **absent** pre-authorization |

**RESOLVED** means: identities are frozen and non-colliding.  
It does **not** mean a formal observation result may be written.

---

## E-B4 condition matrix (after E-B9a/9b)

| Cond | Needed for Full YES | Status after E-B10 |
|---|---|---|
| C1 Executor | Yes | **Met** |
| C2 After snapshots | Yes | **Partial** |
| C3 Claim gold | Yes | **Partial**（schema yes · annotated ledger no） |
| C4 Empty-gate | Yes | **Partial**（suite contract yes · real cases no） |
| C5 Hygiene | Yes | **Met** |

**Full YES ⇒ C1∧C2∧C3∧C4∧C5 = false.**
