# 01 — Executors · artifact · honesty

## 1. Executors

```text
execute_score_t2(observed_after, claim_gold, binding_policy=BP-A)
  → restamped T2CaseResult (implementation stamps)

execute_score_t3(..., final_citations, gated_chunks_ordered, align_bucket)
  → restamped T3CaseResult
```

Both call E-B19 contract formulas, then restamp:

| Field | Contract (E-B19) | Implementation (E-B20) |
|---|---|---|
| `protocol_version` | `w10_eb19_…_contract_v1` | `w10_eb20_…_implementation_v1` |
| `artifact_kind` | `T2_T3_SCORER_CONTRACT` | `T2_T3_SCORER_IMPLEMENTATION` |
| `contract_only` | true | false |
| `implementation_only` | — | true |
| `formal_measurement` | false | false |

## 2. Artifact

`build_implementation_artifact()` scores the E-B18 BP-A compatibility pack
(default) and emits:

```text
protocol_version, artifact_kind, window, parents, binding_policy,
gates, cases[], summary, honesty, formal_measurement=false,
implementation_only=true
```

Per case:

```text
case_id, grounding_observation_status, refusal_observation_status,
t2, t3, honesty{product_faithfulness_proven=false, t3_pointer_source, …}
```

## 3. Citation pointer policy (compat pack)

| Mode | Behavior |
|---|---|
| Default | Use After `final_citations` (often empty on author-owned After) |
| `attach_gold_supporting_pointers=True` | Attach gold supporting ids — wiring-only G2 proof |

Neither mode proves product LLM citation behavior.

## 4. Validation rejects

- `E-B_FORMAL_READY != NO`
- `formal_measurement=true`
- `product_faithfulness_proven=true`
- Forbidden oracle keys (`llm_judge`, `nli_label`, `expected_action`, …)
- Ill-formed T2/T3 rate / G1∧G2 invariants (delegated to E-B19 shape checks)
