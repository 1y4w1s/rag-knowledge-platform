# 07 — T1 / T2 / T3 readiness (separate)

T1 ready **never** implies T2/T3 ready.

## T1 — final citation scope

### Frozen need (E-B16 / E-B24)

```text
T1 = After final_citations vs plan/gated (authorized) scope
No claim gold required for the T1 contrast itself
```

### E-B38 inputs available

| Input | Present on C01–C11 records? |
|---|---|
| `citations` / final citations | YES |
| `plan_citations` / gated chunk list / `gated_chunks_ordered` | **NO** |
| `align_bucket` | **NO** |
| `authorized_scope` snapshot | **NO** |
| `gen_plan_reference` (hash only) | YES (not enough to contrast) |

### Verdict

```text
T1_REAL_AFTER_INPUT_READY = NO
```

Blockers: missing plan/gated scope material on acquisition records; degraded citation dump not classified as a scorable T1 After under a dedicated frozen rule (UNCLASSIFIED BP).

---

## T2 — unsupported assertion rate

### Frozen need

Bound After + claim gold under declared BP; denom = gold `asserted_claims`; labels from gold only; empty denom → `NOT_APPLICABLE` (not 0.0 PASS).

### Can it run without inventing asserted claims?

**No.** Unrebounded E-B12B gold is `synthetic_authored` → BP-A INCOMPATIBLE. BP-B INVALID (pool + often presence). Using gold rows as if degraded After asserted them would invent asserted claims.

### Verdict

```text
T2_REAL_AFTER_INPUT_READY = NO
```

---

## T3 — G1 ∧ G2 grounding

### Frozen need

Same binding as T2 **plus** legal claimed-unit universe **plus** `final_citations` / `[片段N]` mapping via `gated_chunks_ordered` and supporting evidence ids.

### Gaps on real After

| Need | Status |
|---|---|
| BP-A bind | FAIL (INCOMPATIBLE) |
| Claimed-unit universe corresponding to actual After assertions | unresolved / unrebounded |
| Gold supporting ids (`E1`/`E2`) ↔ product `chunk_id` UUIDs | mismatched |
| `gated_chunks_ordered` on acquisition record | missing |

### Verdict

```text
T3_REAL_AFTER_INPUT_READY = NO
```
