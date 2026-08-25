# 01 — W10 Final Outcome

## Formal T1 (authorized Showcase T1-only Formal scope)

```text
FORMAL_T1_MEASUREMENT_EXECUTED = YES
FORMAL_T1_MEASUREMENT_VALID    = YES
T1_FORMAL_STATUS               = MEASURED

eligible   = 11
compliant  = 11
violation  = 0
excluded   = 1   (C12 = INELIGIBLE_NOT_SCORED)
T1_COMPLIANCE_RATE = 100%

measurement_scope_id  = w10_showcase_t1_only_v1
FORMAL_MEASUREMENT_SCOPE = T1_ONLY
formal_measurement_id = w10_t1_formal_20260825T101800Z
measured_at           = 2026-08-25T10:18:00Z
eb44_formal_commit    = 6bf35b6a1ac1cbb00a3358b3c231fa52e9f6c951
```

### Authorized claim wording

```text
T1 citation-scope compliance on the authorized
Showcase T1-only Formal scope.
```

### Forbidden shorthand

```text
✗ “W10 accuracy = 100%”
✗ “Agent quality = 100%”
✗ “RAG correctness = 100%”
✗ “Formal Observation full stack = 100%”
```

### Predicate (reminder)

```text
compliant = set(final_citation_ids) ⊆ set(gated_scope_ids)
```

No fuzzy match · no LLM judge · no NLI · no gold-claim dependency.

Evidence: [`../w10-eb44-t1-formal-measurement/formal-t1-result.json`](../w10-eb44-t1-formal-measurement/formal-t1-result.json).

---

## T2 / T3 Final Status

```text
T2_FORMAL_STATUS = NOT_APPLICABLE
T3_FORMAL_STATUS = NOT_APPLICABLE
```

### Why N/A

E-B38 Product After (all eligible cases C01–C11):

```text
response_mode = DEGRADED
llm_called    = false
```

E-B40 Response Mode Gate:

```text
DEGRADED ∉ T2/T3 claim-quality denominator
```

### Honest interpretation

```text
NOT_APPLICABLE ≠ PASS
NOT_APPLICABLE ≠ FAIL
NOT_APPLICABLE ≠ 100%
NOT_APPLICABLE ≠ “zero unsupported”
NOT_APPLICABLE ≠ “fully grounded”
```

---

## Observation envelope (v2)

```text
FORMAL_OBSERVATION     = COMPLETED_FOR_T1_V2
FORMAL_OBSERVATION_V2  = COMPLETED
E-B_FORMAL_READY (historical global) = NO   # untouched
```

Historical `E-B_FORMAL_READY=NO` remains the pre-v2 global semantics artifact.  
Scope v2 successor (`w10_showcase_t1_only_v1`) authorizes T1-only Formal Measurement without rewriting that history.
