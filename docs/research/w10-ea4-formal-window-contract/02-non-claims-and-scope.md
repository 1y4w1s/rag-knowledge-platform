# 02 — Non-claims and out of scope

> 大白话：这窗只是把「以后正式跑评测时，结果文件长什么样、谁有资格当 runner、能喊什么口号」写死。  
> **没有**真的跑评测，也**没有**给 P2-R1 开绿灯。

## Explicit non-claims (钉死)

| Non-claim | Meaning |
|---|---|
| E-A4 **does not execute** formal evaluation | No batch run over the frozen 12; no reserved result file written |
| E-A4 **does not produce** measurement results | Schema examples are labeled `SCHEMA_EXAMPLE_NOT_A_RUN` and `measurement_valid=false` |
| E-A4 **does not change** product runtime | No edits to `backend/app` services, APIs, retrieval, chat, critic, P2-R1 execute path |
| E-A4 **does not call** LLMs / LM Studio | Validators are pure Python structure checks |
| E-A4 **does not unblock P2-R1** | Envelope requires `p2_r1_status=BLOCKED` and `does_not_unblock_p2_r1=true` |
| E-A4 **does not** prove generation-final safety | Observation point is plan-construction citations only |
| E-A4 **does not** score Critic oracle capability | Critic action / CP oracles remain out of charter |
| 11/11 scope-safe **≠** 12/12 product PASS | C12 stays out of denominator |

## Forbidden marketing / progress language

Do **not** write in progress, cockpit, PR, or result summaries:

- 「P2-R1 unblocked / PASS / PARTIAL-unblocked」
- 「generation-final safety PASS」
- 「Critic oracle capability PASS from E-A4」
- 「reuse P2-R3 formal runner as W10 SSOT」
- 「execute_frozen_case is the E-A2 formal path」

## Out of scope (intentionally NOT done)

1. Implementing the batch formal runner that writes `w10-ea4-formal-window-result.json`
2. Extending E-A2 executor to `_stream_generation_phase` / `state["citations"]`
3. Remapping C12 oracle under Direction A
4. Direction B DiD merge filter / `CriticScopeContext`
5. Editing `docs/status/progress.md` / cockpit to claim unblock
6. Creating sample **filled** formal result files that look like real runs
7. Importing or calling `execute_frozen_case` for product-denominator scoring

## Allowed claim reminder

唯一允许的测量声称：

```text
plan-construction citation scope compliance
```
