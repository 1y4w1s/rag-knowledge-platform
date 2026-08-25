# W10 E-B4 — Generation Observation Construct Repair

> **Type:** research / construct design only  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** **COMPLETE** — construct repair designed; gate still closed until future windows implement  
> **Does not:** LLM / LM Studio · generation execution · product runtime (`backend/app`) · pytest 新套件 · 正式 observation 结果 · W9 冻结案改写 · Critic 打分 · P2-R1 解阻

本目录回答唯一问题：**在 E-B3 判定 `E-B_FORMAL_READY = NO` 之后，如何最小修复 observation construct，使正式 generation observation 窗有可辩护的开启条件？**

## Formal gate（本窗结论）

```text
E-B_FORMAL_READY = NO
```

本窗 **只修构造定义**，不消除执行缺口。  
完整 YES 条件见 [`05-updated-readiness-gate.md`](05-updated-readiness-gate.md)。在 B1–B4 被后续窗实际落地之前，**禁止**开正式 observation 执行窗。

### E-B3 blockers → 本窗修复对象

| E-B3 blocker | 本目录交付 |
|---|---|
| B1 无 After 窗 executor | [`01`](01-after-window-executor-boundary.md) 最小路径 + 禁止捷径 + 与 E-A5 分离 |
| B2 无 After 快照 | 同 `01`：快照必须由 After 路径写出，禁止 fixture 回填 |
| B3 T2/T3 缺独立 claim 金标 | [`02`](02-t2-unsupported-claim-gold.md) + [`03`](03-t3-grounding-observation.md) |
| B4 T4 空闸案缺 | [`04`](04-t4-empty-gate-fixture.md) |

## 阅读顺序

1. [`01-after-window-executor-boundary.md`](01-after-window-executor-boundary.md) — Minimal After-window executor  
2. [`02-t2-unsupported-claim-gold.md`](02-t2-unsupported-claim-gold.md) — T2 unsupported claim gold strategy  
3. [`03-t3-grounding-observation.md`](03-t3-grounding-observation.md) — T3 grounding observation strategy  
4. [`04-t4-empty-gate-fixture.md`](04-t4-empty-gate-fixture.md) — T4 empty retrieval / refusal fixture  
5. [`05-updated-readiness-gate.md`](05-updated-readiness-gate.md) — `E-B_FORMAL_READY = YES` 精确条件  

## 上游冻结指针

| Role | Path |
|---|---|
| E-B3 readiness FAIL | `docs/research/w10-eb3-generation-observation-readiness/` |
| E-B2 artifact schema | `docs/research/w10-eb2-generation-observation-schema/` |
| E-B1 observation protocol | `docs/research/w10-eb1-generation-observation-protocol/` |
| E-B0 boundary charter | `docs/research/w10-eb0-generation-boundary/` |
| E-A5 L0 formal（对照，禁止 reuse） | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| E-A2 plan executor（Before only） | `backend/tests/w10_ea2_scope_eligibility.py` · `execute_product_path_plan` |
| E-A4 formal runner（对照形状） | `backend/tests/w10_ea4_formal_window_contract.py` · `run_formal_window` |
| W9 frozen 12 | `backend/tests/fixtures/l4_critic/w9-critic-cases.json` |

## Construct decisions（一句话）

| 议题 | 决议 |
|---|---|
| After executor | 必须经 `prepare_agent_generation` → `_stream_generation_phase`（或诚实同构 After 写入）→ 捕获 `state["content"]`/`state["citations"]`；禁止 E-A5 默认「plan citations = final」 |
| T2 金标 | **独立 claim ledger（人工标注主路径）**；禁止 Critic oracle；禁止仅靠无标注自动切分 |
| T3 接地 | 命题 ∈ gated excerpt 可定位 = grounded；否则 unsupported/unverifiable；结构对齐信号不得冒充语义接地；零 Critic oracle |
| T4 空闸 | **必须新建** research fixture；C04/C07 **不可替代** |
| 门禁 | 全四靶正式窗 YES 需 B1–B4 全消；允许诚实收窄 `targets_measured` 的 **窄窗 YES**（仍要 B1+B2） |

## 本窗未做（故意）

- 未写 `run_formal_observation` / 任何 test module  
- 未创建 empty-gate fixture 文件  
- 未创建 claim gold JSON  
- 未调用任何 LLM / 嵌入 / 本地 GGUF  
- 未改 `backend/app`  
- 未写 `w10-eb2-generation-observation-result.json`  

## 一句话

> **协议与信封已冻；本窗补齐「怎么修构造」；正式 After 观测仍不可开。**

## Stop

构造设计结束。禁止在本窗续写 executor、补 fixture、跑模型、或落正式结果。
