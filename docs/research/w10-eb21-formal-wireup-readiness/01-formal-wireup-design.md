# 01 — Formal wireup design

> Design only. No reserved write. No gate flip.

## 0. Problem

E-B20 lands tests-only executors + `T2_T3_SCORER_IMPLEMENTATION` artifact and
maps case statuses onto E-B2 `grounding_observation_status` **honesty enums**.

It does **not**:

- write `artifact_kind=FORMAL_OBSERVATION_RESULT`
- set `formal_measurement=true`
- populate reserved `w10-eb2-generation-observation-result.json`
- prove product LLM faithfulness

This window freezes **how** a future authorized formal composer would attach
scorer output to the E-B2 observation envelope.

---

## 1. How scorer output enters the E-B2 artifact

### 1.1 Pipeline (LAAE formal compose)

```text
┌──────────────────────────────────────────────────────────────┐
│ 1. Capture (E-B15 lineage)                                   │
│    prepare → _stream_generation_phase → After body/citations │
│    → E-B2 per_case After slots                               │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 2. Binding Gate (E-B17) under explicit BP-A | BP-B | BP-C    │
│    case_id · gold_ledger_hash · observed_content_hash · pool │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 3. Scorer (E-B20 executors)                                  │
│    execute_score_t2 / execute_score_t3                       │
│    → T2CaseResult / T3CaseResult (labels from gold only)     │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ 4. Compose                                                   │
│    A. Project status → E-B2 grounding/refusal enums          │
│    B. Emit companion formal score artifact (same run_id)     │
│    C. Fill measurement_validity + targets_measured           │
│    D. Reserved write ONLY if E-B_FORMAL_READY=YES + unlock   │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 Two layers (do not collapse)

| Layer | Identity | Holds |
|---|---|---|
| **L-Obs** | E-B2 `w10_eb2_generation_observation_v1` | After slots · eligibility · status enums · `measurement_validity` |
| **L-Score** | Companion formal score artifact (new contract) | Full T2/T3 case results · binding_verdict · rates · per_claim G1∧G2 |

Aligns with E-B8 决议 A (external ledger / soft bind; E-B2 v1 const need not
grow for first formal). Mirrors T1 pattern: E-B2 keeps `scope_compliance_result`
slot; detailed T2/T3 payloads live beside the envelope until an optional E-B2.1.

### 1.3 Status projection (already proven in E-B20)

Reuse `map_scorer_status_to_grounding_observation` / `_combine_grounding_status`:

| Scorer status | E-B2 `grounding_observation_status` |
|---|---|
| `OBSERVED_SLOT` | `OBSERVED_SLOT` |
| `NOT_APPLICABLE` / `NOT_OBSERVED` | `NOT_OBSERVED` |
| `INVALID` / `INCOMPATIBLE` | `INELIGIBLE` |

Rules:

- `OBSERVED_SLOT` only when `targets_measured` includes T2 and/or T3 **and**
  Binding = `BOUND` **and** denom allows a defined rate.
- C12 remains `INELIGIBLE` for both grounding and refusal.
- BP-C cases: T2/T3 → `NOT_APPLICABLE` → grounding `NOT_OBSERVED`; refusal
  path owns T4 (empty-gate companion suite).

### 1.4 What must **not** enter L-Obs

| Forbidden | Why |
|---|---|
| Free-text rates in `notes` as sole score store | Unauditable; bypasses shape validators |
| E-A5 keys (`scope_compliance_pass`, `per_case_result`, …) | Hard reject in E-B2 |
| Critic oracle keys | Hard reject |
| Claiming `grounding proven` from rates | Forbidden claim string |
| Copying E-B20 `implementation_only=true` stamps into formal | Different artifact class |

### 1.5 Recommended compose modes

| Mode | When | Behavior |
|---|---|---|
| **W1 Soft compose (primary)** | First Full/Narrow formal with T2/T3 | L-Obs status + After fields; L-Score companion sharing `run_id`/`base_sha`; optional soft pointer in `notes` or future optional `parent_scorer_artifact` |
| **W2 E-B2.1 additive (backup)** | Owner wants single-file audit trail | New protocol revision adds nullable `t2_result` / `t3_result` objects on `per_case_observation` (E-B1 draft fields as structured objects, not bare floats alone) |
| **Anti-pattern** | — | Promote E-B18 compat-pack scores as product faithfulness; flip validity without unlock |

**This design freezes W1 as the first formal path.** W2 is a later contract bump, not a silent field smuggle into v1.

---

## 2. Formal result schema — required fields

### 2.1 L-Obs (E-B2) — already frozen; formal fill rules

**Top-level (required consts unchanged):**

| Field | Formal fill |
|---|---|
| `protocol_version` | `w10_eb2_generation_observation_v1` |
| `artifact_schema_version` | `w10-eb2-generation-observation-v1` |
| `artifact_kind` | `FORMAL_OBSERVATION_RESULT` |
| `run_id` / `base_sha` | Real run identity (not `SCHEMA_EXAMPLE_*`) |
| `suite_id` / `case_count` | `w9_critic_frozen_12` / `12` |
| `observation_point` | `generation_final_content_and_citations` |
| `eligibility_summary.targets_measured` | Authorized subset of `{T1,T2,T3}` on this envelope; T4 only via S2 companion |
| `measurement_validity` | See §3 |
| `measurement_claims.asserted` | ⊆ `{generation observation artifact produced}` |
| `p2_r1_status` | `BLOCKED` |
| Reserved filename | `w10-eb2-generation-observation-result.json` |

**Per-case After slots:**

| Field | Formal fill when T2/T3 measured |
|---|---|
| `final_content_observation` | Non-null After body (or `INELIGIBLE`) |
| `final_citations` | Post-align citations (`[]` on refusal) |
| `gen_plan_reference` | Plan id/hash |
| `scope_compliance_result` | T1 slot when T1 ∈ targets |
| `grounding_observation_status` | Projected from scorer (§1.3) |
| `refusal_observation_status` | T4 / refusal path; not a stand-in for T2 rates |

### 2.2 L-Score companion — fields to freeze in next impl contract

Suggested identity (impl window freezes literals):

| Field | Value / rule |
|---|---|
| `protocol_version` | e.g. `w10_eb22_formal_t2_t3_score_v1` (next window) |
| `artifact_kind` | `FORMAL_T2_T3_SCORE_RESULT` |
| `parent_observation_protocol` | `w10_eb2_generation_observation_v1` |
| `parent_run_id` / `parent_base_sha` | **Must equal** L-Obs `run_id` / `base_sha` |
| `binding_policy` | Declared suite-level default + per-case override |
| `formal_measurement` | `true` only under gate YES + unlock |
| `implementation_only` | `false` |
| `cases[]` | Same shape as E-B20 case record **after restamp**: `case_id`, statuses, `t2`, `t3`, honesty |
| `t2` / `t3` | E-B19/E-B20 required fields: rates, counts, `binding_verdict`, T3 `per_claim[]` with G1∧G2 |
| `honesty.product_faithfulness_proven` | `true` **only** if BP-A ∧ live/authorized After ∧ owner auth; else `false` |
| `honesty.t3_pointer_source` | `after_final_citations` for formal product path; forbid silent `gold_supporting_ids_wiring_only` as product proof |

### 2.3 Aggregate / suite summary (L-Score)

| Field | Rule |
|---|---|
| Macro unsupported / grounded rates | Mean over cases with `OBSERVED_SLOT` only |
| `NOT_APPLICABLE` / `INELIGIBLE` | Excluded from macro numerators and denominators |
| `INVALID` / `INCOMPATIBLE` | Force suite `measurement_valid=false` if any such case was required by `targets_measured` |

---

## 3. `measurement_validity` definition (formal T2/T3)

### 3.1 Inherit E-B2 required keys

| Key | Formal rule |
|---|---|
| `measurement_valid` | `true` iff artifact_kind formal **and** all honesty gates below pass **and** `invalid_reasons=[]` |
| `invalid_reasons` | Non-empty when `measurement_valid=false`; codes ⊆ allowlist |
| `structurally_schema_ok` | `true` |
| `observation_point_honest` | `true` (After = content/citations, not plan-as-final) |
| `ea5_artifact_not_reused` | `true` |
| `p2_r3_artifact_not_reused` | `true` |
| `critic_oracle_fields_absent` | `true` |
| `p2_r1_remains_blocked` | `true` |
| `llm_called` | Must match reality; **E-B2 freeze currently forces `false`** → A4 live path needs an authorized thaw / contract revision before live formal |

### 3.2 Additional validity conditions for T2/T3 (design)

`measurement_valid=true` with `T2` or `T3` ∈ `targets_measured` additionally requires:

1. **Gate:** write-time `E-B_FORMAL_READY=YES` (and packaging auth for any T4 claim).
2. **Bind:** every OBSERVED T2/T3 case has BindingVerdict `BOUND` under declared BP.
3. **Gold:** labels only from claim gold; no LLM/NLI/fuzzy re-label.
4. **Pointers:** T3 G2 uses After `final_citations` / `[片段N]`→gated order — not gold-id wiring-only.
5. **L-Score link:** companion artifact present and `parent_run_id` matches.
6. **BP honesty:** BP-B scores cannot set `product_faithfulness_proven=true`.
7. **Compat pack:** E-B18 author-owned rebound pack alone is **insufficient** for `measurement_valid=true` product narrative (may only support protocol/smoke validity under narrow unlock).

### 3.3 Proposed new `invalid_reasons` codes (for next contract window)

| Code | When |
|---|---|
| `FORMAL_GATE_LOCKED` | Attempted formal write while `E-B_FORMAL_READY=NO` |
| `BINDING_INCOMPATIBLE` | Gate returned INCOMPATIBLE |
| `GOLD_AFTER_HASH_MISMATCH` | Codec / space mismatch |
| `SCORER_COMPANION_MISSING` | T2/T3 targeted but L-Score absent |
| `SCORER_RUN_ID_MISMATCH` | L-Score parent ids ≠ L-Obs |
| `BP_POLICY_VIOLATION` | e.g. BP-C case scored as OBSERVED T2 |
| `WIRING_ONLY_POINTER_AS_PRODUCT` | `gold_supporting_ids_wiring_only` under product claim |
| `COMPAT_PACK_AS_PRODUCT_FAITHFULNESS` | E-B18 pack scored as live faithfulness |
| `LLM_CALLED_FREEZE_VIOLATION` | Live LLM without authorized `llm_called` thaw |

Existing E-B2 codes remain authoritative; new codes require an allowlist extension in the contract/impl window — **not** this design-only window.

---

## 4. BP-A / BP-B / BP-C isolation in formal

### 4.1 Per-policy formal roles

| Policy | Formal role | T2/T3 | What `measurement_valid=true` may mean |
|---|---|---|---|
| **BP-A `observed_after`** | Formal **product-path candidate** | Score after rebound gold ↔ live/authorized After | After-bound unsupported / grounded rates under declared targets — still **not** “grounding proven” claim string |
| **BP-B `synthetic_authored`** | Protocol / scorability only | Score allowed for wiring smoke | At most protocol integrity; **must** keep `product_faithfulness_proven=false`; prefer `measurement_valid=false` or Narrow non-product footnote if present in formal packaging |
| **BP-C `refusal_exclude`** | T4 exclusion | Skip T2/T3 (`NOT_APPLICABLE`) | Refusal / empty-gate only (S2 suite) |

### 4.2 Isolation rules (hard)

1. **Declare policy per case** (and suite default). Silent default-to-BP-A forbidden.
2. **No cross-policy macro** without stratified breakdown (BP-A rate ≠ BP-B rate blended as one KPI).
3. **BP-B After** must pass claim-text presence; E-B15 degraded/refusal bodies that fail presence stay `INVALID` / out of OBSERVED (AG-4 residual).
4. **BP-A** requires content-string hash codec equality (E-B18 cleared on compat pack only; live rebound still AG-5).
5. **BP-C** must not populate T2/T3 rates as `0.0` PASS.
6. **Suite packaging:** W9×12 envelope = T1/T2/T3 candidates; empty-gate = companion S2; never merge into `case_count=12` silently.

### 4.3 Honesty matrix

| Input material | Allowed formal narrative |
|---|---|
| E-B18 BP-A compat pack (author-owned After) | Protocol rebound / scorer wire smoke — **not** product LLM faithfulness |
| E-B15 A1/A2 degraded/refusal | Capture harness proof — not BP-B presence green for C01–C11 |
| Future live A4 After + rebound gold | BP-A product-path observation (still forbidden claim strings) |
| E-B6 synthetic `[eb6-synthetic:…]` | AG-6 OPEN — never pair with E-B12B claim_texts as formal T2/T3 |

---

## 5. Design freeze stamp

```text
FORMAL_WIREUP_ARCHITECTURE     = LAAE compose (Capture→Bind→Score→Project→Write)
E-B2_SCORE_FIELD_STRATEGY      = W1 companion L-Score (primary); W2 E-B2.1 backup
STATUS_PROJECTION              = E-B20 map (unchanged)
MEASUREMENT_VALIDITY_T2_T3     = gate ∧ bind ∧ gold-only ∧ companion ∧ BP honesty
BP_ISOLATION                   = declare · stratify · no silent blend
FORMAL_WIREUP_IMPLEMENTED      = NO
E-B_FORMAL_READY               = NO
```
