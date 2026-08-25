# 02 — Non-claims and out of scope

> 大白话：这窗只是把「以后正式做 generation observation 时，结果文件长什么样、不能拿谁的旧工件冒充、能喊什么口号」写死。  
> **没有**真的跑生成，也**没有**证明回答质量 / grounding / Critic。

## Explicit non-claims（钉死）

| Non-claim | Meaning |
|---|---|
| E-B2 **does not execute** generation observation | No `_stream_generation_phase`；no formal result file |
| E-B2 **does not prove** generation quality | Forbidden claim: `generation quality proven` |
| E-B2 **does not prove** grounding | Forbidden claim: `grounding proven` |
| E-B2 **does not validate** Critic | Forbidden claim: `Critic validated` |
| E-B2 **does not reuse** E-A5 11/11 | Different `observation_point`；validator rejects EA5 shapes |
| E-B2 **does not reuse** P2-R3 runners/artifacts | Forbidden runner identities + field reject |
| E-B2 **does not change** product runtime | No `backend/app` edits |
| E-B2 **does not call** LLMs / LM Studio | Validators are pure structure checks |
| E-B2 **does not unblock P2-R1** | Envelope requires `p2_r1_status=BLOCKED` |

## Forbidden marketing / progress language

Do **not** write in progress, cockpit, PR, or summaries:

- 「generation quality proven / PASS」
- 「grounding proven」
- 「Critic validated / Critic oracle capability from E-B2」
- 「E-A5 11/11 = generation observation PASS」
- 「reuse P2-R3 formal runner as generation SSOT」
- 「P2-R1 unblocked」

## Out of scope（intentionally NOT done）

1. Writing `w10-eb2-generation-observation-result.json` as a filled formal observation
2. Running generation / align / citation regeneration
3. Filling `final_content_observation` / `final_citations` with live or fixture answers
4. Treating W9 Critic fixture `answer` as After-window content
5. Product remediation / DiD probes / Multimodal
6. Importing `execute_frozen_case` or P2-R3 formal runners

## Allowed claim reminder

唯一允许的声称：

```text
generation observation artifact produced
```

本窗语义 = **契约 / schema example 冻结**，不是「四靶已测」。
