# 02 — Response Mode Gate (`w10_eb40_response_mode_gate_v1`)

## Versioning

```text
protocol_version = w10_eb40_response_mode_gate_v1
SUPERSEDES_FOR_FUTURE_FORMAL_INPUT_SELECTION = YES
rewrites_historical_result                   = NO
```

Historical E-B16 / E-B17 / E-B19 / E-B20 / E-B21 / E-B22 remain rebuildable.
Denom = gold `asserted_claims` and old BP-A/B/C definitions are **not** silently changed.

## response_mode ∈ {ANSWER, REFUSAL, DEGRADED}

| Mode | Meaning | T2/T3 |
|---|---|---|
| **ANSWER** | Ordinary generated answer asserting claims | potentially eligible if binding passes |
| **REFUSAL** | Explicit product refusal | route to refusal/T4 |
| **DEGRADED** | Service-unavailable / evidence-dump path | **NOT_APPLICABLE** |

```text
DEGRADED ≠ REFUSAL
DEGRADED ≠ ANSWER
citations nonempty ⇏ ANSWER
NOT_APPLICABLE ≠ PASS ≠ 0% unsupported ≠ 100% grounded
```

## Classification source (deterministic)

```text
RESPONSE_MODE_SIGNAL_AVAILABLE = YES
```

Allowed control-plane signals (priority order):

1. `plan_refusal` / `capture_path_submode|capture_mode = product_stream_refusal` → **REFUSAL**
2. `capture_path_submode|capture_mode = product_stream_degraded` → **DEGRADED**
3. `llm_called = true` → **ANSWER**

Product evidence: E-B15 harness enums + `app.services.agent.stream` L1 branch
(`has_available_chat_provider_key() == false` → `stream_degraded_fragment_reply`).

Forbidden: LLM classifier · NLI · embeddings · fuzzy semantic · substring-as-mode.

## BP-D (versioned)

```text
DEGRADED_BP_POLICY = VERSIONED_BP_D
BP_D = DEGRADED_PRODUCT_AFTER
```

Semantics: real Product After · provenance valid · not refusal · not ordinary answer ·
excluded from T2/T3 · retained for availability/degradation accounting.

Does **not** retroactively claim E-B38 was historical BP-A.

## Metrics separation

| Surface | Metrics |
|---|---|
| ANSWER | T2/T3 claim scoring (if bound) |
| REFUSAL | T4 / refusal policy |
| DEGRADED | `degraded_count` / `degraded_rate` (availability — **not** model quality) |
