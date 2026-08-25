# 01 — Contract schema · formulas · statuses

> Design freeze for tests-only T2/T3 scorer contract. No formal observation.

## 1. Artifact identity

| Field | Value |
|---|---|
| `protocol_version` | `w10_eb19_t2_t3_scorer_contract_v1` |
| `artifact_kind` | `T2_T3_SCORER_CONTRACT` |
| Parents | E-B17 binding gate · E-B18 BP-A compatibility · E-B8 constructs · E-B16 LAAE |

## 2. T2CaseResult required fields

```text
protocol_version, artifact_kind, target=T2, case_id, status,
binding_verdict, asserted_claim_count, unsupported_claim_count,
unsupported_rate, label_counts, formal_measurement=false, contract_only=true
```

### Status matrix

| Status | `unsupported_rate` | When |
|---|---|---|
| `OBSERVED_SLOT` | float in [0,1] = num/denom | Bound + denom>0 |
| `NOT_APPLICABLE` | null | denom 0 / BP-C |
| `INVALID` | null | bind fail / gold evidence integrity fail |
| `INCOMPATIBLE` | null | BindingVerdict.INCOMPATIBLE |
| `NOT_OBSERVED` | null | targets exclude T2 |

### Formula

```text
unsupported_rate = |{c ∈ asserted : label=unsupported}| / |asserted|
```

- `unverifiable` ∈ denom；∉ unsupported numerator  
- Scorer **never** re-labels  

## 3. T3CaseResult required fields

```text
protocol_version, artifact_kind, target=T3, case_id, status,
binding_verdict, asserted_claim_count, grounded_claim_count,
grounded_rate, align_bucket, per_claim[], formal_measurement=false,
contract_only=true
```

### per_claim

```text
claim_id, label, g1, g2, grounded, supporting_evidence_ids,
resolved_pointer_ids
```

Invariant: `grounded ⇔ g1 ∧ g2`（shape validator enforces）.

### G1 / G2

| | True iff |
|---|---|
| G1 | `label==supported` ∧ supporting ids non-empty ⊆ observed gated |
| G2 | Exact id hit from `final_citations` **or** `[片段N]`→`gated_chunks_ordered[N-1]` ∩ supporting |

## 4. Pipeline（shared）

```text
1. targets include? else NOT_OBSERVED
2. Binding Gate (E-B17) under declared BP-*
3. supported evidence integrity (invalidate, never re-label)
4. denom 0 → NOT_APPLICABLE
5. score formulas → OBSERVED_SLOT (contract_only)
```

## 5. Honesty

Contract scores prove **wiring / formula determinism** only.  
They do **not** prove product LLM faithfulness or formal readiness.
