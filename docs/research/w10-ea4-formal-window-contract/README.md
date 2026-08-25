# W10 E-A4 — E-A2 Formal Window Contract Freeze

> **Type:** research + **test-only** schema freeze  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** **FROZEN** — narrow E-A2 formal evaluation *window contract*  
> **Does not:** execute formal evaluation · write result artifacts · call LLM / LM Studio · change `backend/app` · unblock P2-R1

本目录冻结 **E-A4**：在 E-A3 给出「窄窗 CONDITIONAL GO」之后，把**预留正式评测工件契约**钉死——只冻结 schema / runner 身份 / 声称边界，**不跑**评测、**不产出**正式结果文件。

## 阅读顺序

1. [`01-frozen-contract.md`](01-frozen-contract.md) — 预留 JSON 工件 schema · runner 身份 · 声称边界 · `measurement_validity`
2. [`02-non-claims-and-scope.md`](02-non-claims-and-scope.md) — 明确非声称 / 本窗外
3. [`03-relation-to-ea1-ea2-ea3.md`](03-relation-to-ea1-ea2-ea3.md) — 与 E-A1 / E-A2 / E-A3 的绑定关系
4. [`reserved-artifact.schema.json`](reserved-artifact.schema.json) — JSON Schema 镜像（非正式结果）

## 程序指针（权威）

| Role | Path |
|---|---|
| E-A1 eligibility protocol | `docs/research/w10-ea1-scope-eligibility/` |
| E-A2 deterministic adapter | `backend/tests/w10_ea2_scope_eligibility.py` |
| E-A3 readiness review | `docs/research/w10-ea3-measurement-readiness-review.md` |
| E-A4 contract module (tests only) | `backend/tests/w10_ea4_formal_window_contract.py` |
| E-A4 schema tests | `backend/tests/test_w10_ea4_formal_window_contract.py` |

## 一句话结论

| 断言 | 状态 |
|---|---|
| 窄窗正式工件的 **reserved schema** 已冻结 | **FROZEN**（本目录 + tests 模块） |
| Runner 身份 ≠ P2-R1 `execute_frozen_case` ≠ P2-R3 formal runner | **FROZEN**（常量 + 校验拒绝） |
| 允许声称仅「plan-construction citation scope compliance」 | **FROZEN** |
| 正式评测已执行 / 已有正式结果 | **否**（本窗故意不做） |
| P2-R1 已解阻 | **否**（仍为 BLOCKED；本契约禁止此声称） |

## 验收（本窗）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
.\.venv\Scripts\python.exe -m pytest tests/test_w10_ea4_formal_window_contract.py -q
```

## Stop

契约冻结即停。正式执行已由 E-A5 落盘 `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json`。L1 生成平面下一研究边界 → [`../w10-eb0-generation-boundary/`](../w10-eb0-generation-boundary/)——**不是** P2-R1 解阻、**不是**产品 runtime 补丁。
