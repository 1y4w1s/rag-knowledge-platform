# 03 — Separation from E-A5 / P2-R3 / Critic

> Hard isolation rules. Validators must fail closed.

## 1. E-A5 artifact reuse — REJECT

E-A5 measures **plan-construction** citation scope (`observation_point=plan_construction_citations`).  
E-B2 reserves **generation-final** content + citations (`observation_point=generation_final_content_and_citations`).

| E-A5 signal | E-B2 rule |
|---|---|
| File `w10-ea4-formal-window-result.json` | Must not be overwritten; must not validate as E-B2 payload |
| `artifact_schema_version=w10-ea4-formal-window-v1` | Reject |
| `observation_point=plan_construction_citations` | Reject |
| Array key `per_case_result` | Reject（本信封只用 `per_case_observation`） |
| Fields `scorer_observation_point`, `scope_compliance_pass`, `adapter_protocol_version` | Reject |
| Claim `plan-construction citation scope compliance` in `asserted` | Reject（不在 E-B2 allowed） |
| Arithmetic merge of 11/11 with future T1–T4 | Forbidden in docs / claims |

一句话：

> **plan-construction citation scope ≠ generation observation artifact.**

## 2. P2-R3 artifact reuse — REJECT

| Forbidden identity / token | Why |
|---|---|
| `w9_critic_p2_r3_formal_runner` | Wrong stack |
| `w9_critic_p2_r3_batch_runner` | Wrong stack |
| `FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN` | P2-R3 mode label |
| `w9_critic_p2_r3_formal_product_rerun_v1` | P2-R3 protocol |
| Files such as `w9-critic-p2-r3-full-product-rerun.json` as E-B2 result | Reject overwrite / reuse |

Any `runner_id` / `runner_module` containing `w9_critic_p2_r3` or `execute_frozen_case` fails validation.

## 3. Critic oracle fields — REJECT

Generation observation does **not** consume Critic capability oracles.

Forbidden keys (top-level or per-case):

- `expected_action`
- `oracle_cases` / `oracle_case`
- `critic_score` / `critic_capability` / `critic_actions`
- `capability_label`
- `w9_critic_oracle`

Fixture `w9-critic-capability-contract.json` remains Critic research only; **not** a generation gold standard.

## 4. Positive identity for E-B2

| Must be true |
|---|
| `protocol_version=w10_eb2_generation_observation_v1` |
| `artifact_schema_version=w10-eb2-generation-observation-v1` |
| `observation_point=generation_final_content_and_citations` |
| `runner_id=w10_eb2_generation_observation_runner` |
| `runner_module=tests.w10_eb2_generation_observation_contract` |
| `measurement_claims.allowed == ["generation observation artifact produced"]` |
| `p2_r1_status=BLOCKED` ∧ `does_not_unblock_p2_r1=true` |
