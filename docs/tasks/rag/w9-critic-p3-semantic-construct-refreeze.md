# W9 P3-R0.1 — Clean Semantic Construct Re-Freeze

> Date: 2026-08-24
> Base SHA: `ef79178e8dbfe9a9dec0526ef8b003732a819020` (POST_61 / merge of PR #61)
> Branch: `test/agent-l4-w9-critic-p3-semantic-construct-repair`
> State: **PROTOCOL FROZEN / DRY-RUN ONLY**
> Supersedes: PR #63 (`test/agent-l4-w9-critic-p3-protocol-freeze`) — failed construct validity (five-action L1 + denominator=11)

## Hard bans (this window)

- No LM Studio / real GLM / Thinking ON
- No P3-R1 formal measurement
- No merge of PR #63
- No `backend/app` product runtime changes
- No prompt-tuning against model output
- No formal P3 capability result artifact claiming model capability
- Dry-run / mock / deterministic only; `LM_STUDIO_REQUESTS` must remain 0

## RESEARCH_QUESTION

How capable is GLM-4.6V-Flash Thinking OFF at the **SEMANTIC** portion of Critic judgment after deterministic-first responsibilities are handled by the proven control-plane?

## Layer taxonomy (measurement)

| Layer | Name | What it credits |
|---|---|---|
| L0 | `DETERMINISTIC_CONTROL_PLANE` | Proven deterministic ownership (citation syntax/id, provenance/scope, missing citation, known structured conflict, known required fact missing) |
| L1 | `MODEL_SEMANTIC_CAPABILITY` | **Primary metric** — model judgment on SEMANTIC-eligible claims only |
| L2 | `CONTROL_PLANE_EXECUTION` | Joint advisory + control-plane execution after L1 |
| L3 | `FINAL_SAFETY_OUTCOME` | End-to-end safety of the joint outcome |

Rules:

- Primary metric = **L1 only**; never credit deterministic competence to the model.
- Final CriticAction is **joint-derived** advisory + control-plane execution — **NOT** model-owned.
- Old five-action classifier as L1 is **INVALID**.

## SEMANTIC_CONSTRUCT_DEFINITION

L1 task = on **SEMANTIC-eligible claims only**:

1. Claim detection after non-assertive exclusion.
2. Claim–evidence entailment / unsupported / unverifiable (`CONFLICTED` only if not already structural; this suite does **not** require semantic CONFLICTED claims).
3. Emit per-claim status in `{SUPPORTED, UNSUPPORTED, CONFLICTED, UNVERIFIABLE}` with `evaluation_state=JUDGED`, `decision_owner=SEMANTIC`.

Score **claim status** (not `reason_code` equality; not five CriticActions).

## SEMANTIC_ELIGIBILITY_RULE / SEMANTIC_DENOMINATOR

```
NEW_SEMANTIC_DENOMINATOR = 7 cases / 10 claims
SEMANTIC_CASES = [C01, C02, C03, C04, C08, C09, C10]
DETERMINISTIC_ONLY_CASES = [C05, C06, C11]   # plus C07 owner-absent / no SEMANTIC claims
PROTOCOL_INVALID_CASES = [C12]
C07 = L1 NOT_APPLICABLE (empty claims; expected_calls=0; may stay in capability-12)
```

Eligibility rule: case is L1-eligible iff ∃ claim with `decision_owner=SEMANTIC` **and** case is not protocol-invalid.

Frozen accounting constraints:

- `DETERMINISTIC_CASES_IN_L1_DENOMINATOR = 0`
- `PROTOCOL_INVALID_CASES_IN_L1_DENOMINATOR = 0`
- Formal later report must require `semantic_executed == semantic_eligible` (no post-result filtering)

## MODEL_INPUT_SCHEMA

Allowed model-visible fields only:

- `query`
- `final_draft` (buffered answer after content mutations)
- `gated_evidence_snapshot` (prompt-visible evidence)
- `synchronized_citations`
- optional same-run read-only retrieval-scope flag (`retrieval_scope_exhausted`) when not a pre-solved deterministic ownership label for the semantic task

Forbidden:

- oracle / expected_action / expected status
- `decision_owner` / `reason_code` / score / hints
- historical action / hidden recovery labels
- pre-solved deterministic labels (`known_conflict`, `required_fact_missing`, `citation_syntax_valid`, …) when deterministic already owns the field

## MODEL_OUTPUT_SCHEMA

Required L1 object:

```json
{
  "claims": [
    {
      "claim_id": "<case-scoped id>",
      "status": "SUPPORTED|UNSUPPORTED|CONFLICTED|UNVERIFIABLE",
      "evidence_refs": ["E…"]
    }
  ]
}
```

Optional: claim `identity` / text for reconciliation. **Not** the five CriticActions as the L1 object.

## SCORING_POLICY

- `SCORING_POLICY = EXACT` on per-claim **status** against the frozen SEMANTIC oracle slots.
- Drop five-action EXACT from L1 entirely.
- No `ACCEPTABLE_SET` required while uniqueness freezes hold (status-only EXACT).

## ORACLE / uniqueness freezes (before any model call)

| Case / slot | Freeze |
|---|---|
| C04 | unique status `UNSUPPORTED` (`CONFLICTED` reserved for multi-source / known_conflict like C05) |
| C09 CL2 | `UNVERIFIABLE` (future assertion), not `UNSUPPORTED` |
| C03 / C09 / C10 | atomic claim slots as in W9 capability oracle |
| C02 | paraphrase `30日` ≡ `一个月` frozen for this fixture |
| C08 | non-assertive preface excluded; factual claim `SUPPORTED` |

## DETERMINISTIC_EXCLUSIONS

Deterministic-first owns: citation syntax/id, provenance/scope, missing citation, known structured conflict, known required fact missing.

When deterministic blocks: claim `status=null`, `evaluation_state=BLOCKED_BY_DETERMINISTIC`, `decision_owner=DETERMINISTIC`, **no semantic model call**. Those cases are L1 `NOT_APPLICABLE`, not L1 PASS.

## TIMEOUT_POLICY / PARSE_FAILURE_POLICY

- Timeout remains **IN** the L1 denominator → L1 FAIL observation.
- Parse-failure remains **IN** the L1 denominator → L1 FAIL observation.
- Neither may be dropped by post-hoc filtering.

## HIDDEN_RECOVERY_POLICY

- `HIDDEN_RECOVERY_CANNOT_UPGRADE_L1 = YES`
- Model semantic wrong + control-plane recovery success = **L1 FAIL** (L2/L3 may PASS).
- Deterministic preflight solved = L1 `NOT_APPLICABLE` (not L1 PASS).

## MEASUREMENT_STATE taxonomy

`PASS` | `PARTIAL` | `BLOCKED` | `NOT_RUN`

## MODEL_CAPABILITY_RESULT taxonomy (L1)

`MODEL_CAPABILITY_PASS` | `MODEL_CAPABILITY_FAIL` | `MEASUREMENT_PROTOCOL_INVALID` | `NOT_APPLICABLE`

Formal P3 result artifact claiming real model capability: **forbidden in this window** (`FORMAL_RESULT_ARTIFACT_PRESENT = false`).

## Model profile (neutral transplant; not executed here)

- Adapter class: `OpenAICompatibleAdapter`
- Model: `zai-org/glm-4.6v-flash`
- Thinking: OFF
- temperature: 0.0
- max_tokens: 512
- timeout: 60s
- retry: NONE
- no best-of-N

## Relationship to P2-R3

- P2-R3 historical product-path artifact remains protected evidence (`w9-critic-p2-r3-full-product-rerun.json`).
- This construct re-freeze must keep `P2_R3_HISTORICAL_ARTIFACT_DIFF = 0`.
- Product runtime under `backend/app` must keep diff = 0 vs POST_61 for this window.
