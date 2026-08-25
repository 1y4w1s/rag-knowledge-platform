# W10 E-B8 — Generation Ground Truth Construct Design

> **Type:** research / construct design only  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** **COMPLETE** — ground-truth construct frozen for implementation windows  
> **Does not:** code · LLM / LM Studio · formal generation observation · fixture / gold file creation · annotation run · `backend/app` edits · reserved result write

本目录回答唯一问题：**在正式开跑 generation observation 之前，T2/T3/T4 缺失的 ground-truth 层应如何定义，才能被后续实现窗忠实地落地？**

## Formal gate（本窗结论）

```text
E-B_FORMAL_READY = NO
```

本窗 **只冻结构造**。不消除 E-B7 的 B3 / B4 / B2′ 落地缺口。  
**禁止**以本目录为「可开跑正式 generation observation」依据。

| Gate | Status | Meaning |
|---|---|---|
| `E-B_FORMAL_READY` | **NO** | Full 四靶正式观测仍不可开 |
| Ground-truth construct | **DESIGNED** | ledger / T2 / T3 / T4 / impact 决议已钉 |
| Claim gold file | **ABSENT** | 故意；留给实现窗 |
| Empty-gate fixture | **ABSENT** | 故意；留给实现窗 |

## 阅读顺序

1. [`01-claim-ledger-design.md`](01-claim-ledger-design.md) — 独立 claim ledger：判断单元、粒度、字段、支持/引用关系  
2. [`02-t2-unsupported-claim-construct.md`](02-t2-unsupported-claim-construct.md) — T2 测什么 / 不测什么 / 计分边界  
3. [`03-t3-grounding-construct.md`](03-t3-grounding-construct.md) — T3 excerpt + citation pointer 要求与失败态  
4. [`04-t4-empty-gate-construct.md`](04-t4-empty-gate-construct.md) — T4 空闸 fixture、拒答金标、资格规则  
5. [`05-impact-review.md`](05-impact-review.md) — 是否修订 E-B2、`case_count`、是否新 suite  

## 上游指针

| Role | Path |
|---|---|
| E-B7 readiness recheck（gate NO） | `docs/research/w10-eb7-generation-observation-readiness-recheck/` |
| E-B6 executor（已落地，非正式证据） | `backend/tests/w10_eb6_generation_observation_executor.py` |
| E-B4 construct repair（策略前身） | `docs/research/w10-eb4-generation-observation-construct-repair/` |
| E-B4.5 claim ledger feasibility | `docs/research/w10-eb45-generation-feasibility-audit/04-claim-ledger-feasibility.md` |
| E-B2 frozen envelope | `docs/research/w10-eb2-generation-observation-schema/` |
| E-B1 four targets | `docs/research/w10-eb1-generation-observation-protocol/02-measurement-targets.md` |
| Refusal gold anchor | `backend/app/services/rag/generation.py` · `no_context_reply_for` |

## Construct decisions（一句话）

| 议题 | 决议 |
|---|---|
| 金标权威 | **独立人工 claim ledger**；禁止 Critic oracle / LLM judge / 纯词面重叠自动标 |
| 判断单元 | 一条可真假的 **asserted factual claim**（非 Critic action、非整段拒答话术） |
| 支持关系 | claim ↔ **同次 gated excerpt**（字面或标注者可指出的唯一支撑跨度） |
| 引用关系 | claim ↔ **终态 citation / `[片段N]`**（T3 G2；与 T2 语义支持分离） |
| T2 | 命题相对 gated 池的 `supported \| unsupported \| unverifiable` |
| T3 | 首窗 `grounded = G1 ∧ G2`；G2 失败不得标 grounded |
| T4 | **新 research suite / fixture**；C04/C07 不可替代；拒答金标 = `no_context_reply_for` |
| E-B2 影响 | **需要合同修订或新 suite** 才能把 empty-gate 并入正式信封；claim ledger 为旁路金标协议 |

## 本窗未做（故意）

- 未创建 `w10-eb-generation-claim-gold-v1.json`
- 未创建 `w10-eb-empty-gate-cases.json`（或等价）
- 未改 E-B2 schema / contract 常量
- 未跑 After / 未写 reserved formal result
- 未调用任何 LLM / 嵌入 / LM Studio
- 未改 `backend/app`

## 一句话

> **Ground-truth 层已设计完：独立 ledger + T2/T3/T4 边界 + E-B2 影响决议。正式观测门禁仍关。**

## Stop

构造设计结束。禁止在本窗续写 fixture、标注、执行器改动、或正式 observation。
