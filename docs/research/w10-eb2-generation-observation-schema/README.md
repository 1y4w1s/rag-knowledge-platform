# W10 E-B2 — Generation Observation Artifact Schema Freeze

> **Type:** research + **test-only** schema freeze  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Status:** **FROZEN** — reserved generation observation artifact contract  
> **Does not:** execute generation · write formal observation results · call LLM / LM Studio · change `backend/app` · reuse E-A5 / P2-R3 artifacts · score Critic oracles · unblock P2-R1

本目录冻结 **E-B2**：在 E-B1 钉死观察点协议之后，把**未来** generation observation 结果信封钉死——只冻结 schema / 身份隔离 / 声称边界与确定性校验，**不跑**生成、**不产出**正式观测结果。

## 阅读顺序

1. [`01-frozen-contract.md`](01-frozen-contract.md) — 预留 JSON 工件 schema · 身份常量 · 分案字段 · 声称边界
2. [`02-non-claims-and-scope.md`](02-non-claims-and-scope.md) — 明确非声称 / 本窗外
3. [`03-separation-from-ea5-p2r3-critic.md`](03-separation-from-ea5-p2r3-critic.md) — 与 E-A5 / P2-R3 / Critic oracle 的硬隔离
4. [`reserved-artifact.schema.json`](reserved-artifact.schema.json) — JSON Schema 镜像（非正式结果）

## 程序指针（权威）

| Role | Path |
|---|---|
| E-B1 observation protocol | `docs/research/w10-eb1-generation-observation-protocol/` |
| E-B0 generation boundary | `docs/research/w10-eb0-generation-boundary/` |
| E-A5 formal L0 result (do **not** reuse) | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| E-B2 contract module (tests only) | `backend/tests/w10_eb2_generation_observation_contract.py` |
| E-B2 schema tests | `backend/tests/test_w10_eb2_generation_observation_contract.py` |

## 一句话结论

| 断言 | 状态 |
|---|---|
| 生成观测信封的 **reserved schema** 已冻结 | **FROZEN**（本目录 + tests 模块） |
| `observation_point` = `generation_final_content_and_citations` | **FROZEN**（const；≠ E-A5 `plan_construction_citations`） |
| E-A5 / P2-R3 / Critic oracle 字段复用被校验拒绝 | **FROZEN** |
| 允许声称仅「generation observation artifact produced」 | **FROZEN** |
| 正式 generation observation 已执行 / 质量已证 | **否**（本窗故意不做） |
| grounding / Critic 已验证 | **否**（forbidden claims） |

## 验收（本窗）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
.\.venv\Scripts\python.exe -m pytest tests/test_w10_eb2_generation_observation_contract.py -q
```

## Stop

契约冻结即停。**禁止**把本目录写成「生成已测 / grounding proven / Critic validated」。下一窗才可谈正式 observation 执行（仍须零 LLM 或另开授权窗）；不得覆盖 `w10-ea4-formal-window-result.json`。
