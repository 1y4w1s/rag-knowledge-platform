# V1.0-C0 — Current Capability Inventory & Cut-Line Preparation

> **Window type:** V1.0 Closure · repo-internal audit only  
> **Date:** 2026-08-25  
> **Status:** `V1_0_INTERNAL_INVENTORY_COMPLETE` (awaiting human review)  
> **HEAD at inventory:** `f06e8d92ed3873efbcecb86d7d2f8b42d2955955`（W10 closure commit）  
> **Prior phase:** W10_CLOSED · Formal T1 MEASURED（Showcase T1-only；≠ Agent/RAG accuracy 100%）

## Purpose

建立可信的 **CURRENT SYSTEM INVENTORY**，作为后续：

1. Suoyin Feature Triage 2026  
2. v1.0 Cut Line Freeze  

的内部事实输入。

**本窗只做：** inspect · classify · verify · document · report  
**本窗禁止：** 新功能 · 重构 · scorer · protocol change · Local Model experiment · LLM-Wiki / Graph / Memory expansion / Evolver / Multi-Agent / MCP / Multimodal expansion · 新研究窗 · 顺手修非阻塞问题 · commit

## Index

| File | Purpose |
|------|---------|
| [`01-current-capability-inventory.md`](01-current-capability-inventory.md) | 34 项能力盘点 |
| [`02-implementation-vs-evidence-matrix.md`](02-implementation-vs-evidence-matrix.md) | 存在 ≠ 被证明 |
| [`03-flags-and-defaults-audit.md`](03-flags-and-defaults-audit.md) | Feature flag / 默认行为 |
| [`04-ci-and-test-surface.md`](04-ci-and-test-surface.md) | CI / 测试面 |
| [`05-install-and-demo-readiness.md`](05-install-and-demo-readiness.md) | Install + Demo |
| [`06-readme-claim-audit.md`](06-readme-claim-audit.md) | README claim 审计（不重写） |
| [`07-v1-0-candidate-cut-line.md`](07-v1-0-candidate-cut-line.md) | INTERNAL candidate cut line |
| [`08-v1-0-closure-gap-list.md`](08-v1-0-closure-gap-list.md) | Closure gaps + Scope-Creep Guard |

## One-page verdicts

| Question | Verdict |
|----------|---------|
| Capabilities inventoried | **34** |
| Status mix | IMPLEMENTED **22** · PARTIAL **8** · EXPERIMENTAL **2** · STUB **2** · ABSENT **0**（见 01） |
| Default experimental flags | L3 / Critic / rerank / HyDE / rewrite / graph / L4 **OFF** — **safe** |
| Memory master switch | `agent_memory_enabled=True` — 基础设施 ON；utilization **未**产品化证明 |
| `V1_0_CI_COVERAGE` | **SUFFICIENT_FOR_STABLE_RAG_V1_0**（C5；原 PARTIAL 已闭合） |
| `INSTALL_PATH_STATUS` | **PARTIAL** |
| `DEMO_READINESS` | **GAP**（无 canonical 面试 Demo path） |
| `NEW_CAPABILITY_REQUIRED_FOR_V1_0` | **NO** |
| Exact Formal claim retained | W10 T1 citation-scope 100% on Showcase T1-only Formal scope only |

## Provenance

```text
W10_CLOSED                    = YES
W10_RESEARCH_WINDOW_STATUS    = CLOSED
NEXT_PHASE                    = V1_0_CLOSURE
eb44_formal_commit            = 6bf35b6a1ac1cbb00a3358b3c231fa52e9f6c951
w10_closure_commit            = f06e8d92ed3873efbcecb86d7d2f8b42d2955955
T1_FORMAL_STATUS              = MEASURED
T1                            = 11/11 citation-scope compliant (Showcase T1-only)
T2 / T3                       = NOT_APPLICABLE
```

## Stop

完成本 inventory 后 **停手**，等待人工 review。  
禁止自动开始：README rewrite · CI fix · Demo 实现 · install fix · v1.0 功能实现 · E-B45 / W11。
