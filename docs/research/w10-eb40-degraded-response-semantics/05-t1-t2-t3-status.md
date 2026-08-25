# 05 — T1 / T2 / T3 status (E-B38 under E-B40)

## T1 — citation scope compliance

```text
T1_REAL_AFTER_INPUT_READY              = NO
T1_REQUIRES_COMPANION_REACQUISITION    = YES
T1_EB38_APPLICABILITY                  = BLOCKED_MISSING_SCOPE
```

Records have final `citations` + `gen_plan_reference` (hash only).
Missing: `plan_citations` / `gated_chunks_ordered` / `authorized_scope` / `align_bucket`.

Forbidden: infer authorized scope from final citations; treat `final ⊆ final` as T1 pass.

## T2 — unsupported assertion rate

```text
T2_EB38_APPLICABILITY = NOT_APPLICABLE
```

Reason: all C01–C11 `response_mode=DEGRADED` → excluded from T2 denominator.
Not PASS. Not 0% unsupported.

## T3 — grounding

```text
T3_EB38_APPLICABILITY = NOT_APPLICABLE
```

Reason: same response-mode gate. Not PASS. Not 100% grounded.

## Formal

```text
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                  = NOT_STARTED
```
