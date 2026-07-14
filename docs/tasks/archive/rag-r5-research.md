# Research · Plan-RAG R5 评测闭环

> **状态**：✅ R5-1 + R5-2 本窗（2026-07-06）· R5-3～R5-4 待排  
> **依据**：`rag-optimization-plan.md` §8 · EW-C1 · `docs/golden_qa.md` v0.3

---

## R5-1 · 3 句话摘要

1. **现有代码在哪**：`docs/golden_qa.md` v0.3（GQ-1～10）+ `test_retrieval_golden.py` 内联 `GOLDEN_QA_CASES` 元组；`run_golden_production_baseline.py` 从测试模块 import 同一元组；fixture 文档 `golden_handbook.md` / 动态 PDF / DOCX。
2. **测什么**：抽 JSON 单源 `tests/fixtures/golden_qa.json`；补 **GQ-11 表格切片**（R2-2）与 **GQ-12 改写问法**（hybrid 语义/词面）；`test_retrieval_golden.py` Hit@3 **12/12** + 全量 pytest 绿。
3. **风险**：改 `golden_handbook.md` 须回归 GQ-1～10；改写问法在 mock 词重叠下须有足够 CJK 字重叠；JSON 字段变更须同步 baseline 脚本与 `golden_qa.md`。

---

## EW-C1 vs R5-1 缺口

| 维度 | EW-C1 ✅ | R5-1 本窗补 |
|------|----------|-------------|
| 题量 | GQ-1～10 | **GQ-11～12**（≥12 条） |
| 载体 | md 表 + Python 元组 | **`fixtures/golden_qa.json` SSOT** |
| 跨页/条款号/否定 | ✅ GQ-4/7/8/10 | 保持 |
| R2-2 表格 chunk | 无 golden | **GQ-11** |
| 自然改写问法 | 无 | **GQ-12** |
| R5-2 Hit@3 CI | 已有 pytest | ✅ 独立 CI job + TECH/AGENTS 文档化 |

---

## R5-2 · 3 句话摘要

1. **现有代码在哪**：`.github/workflows/ci.yml` 原 backend 全量 pytest 已含 golden；R5-2 拆出显式 job **`R5-2 golden Hit@3 gate`**，`backend` job `needs` 该 gate。
2. **测什么**：CI 跑 `pytest tests/test_retrieval_golden.py` · mock 嵌入 · **12/12**；本地同命令；全量 pytest 仍 271 绿。
3. **风险**：mock 绿 ≠ 通义生产基线；R5-3 人工抽检仍须；golden 失败时 backend job 跳过（`needs` 链）。

---

## R5-2 验收对照（plan DoD）

| # | 条件 |
|---|------|
| 1 | CI 有独立 **`R5-2 golden Hit@3 gate`** job；命令 `test_retrieval_golden.py` |
| 2 | `backend` pytest job `needs` golden gate |
| 3 | `rag-optimization-plan.md` §8 R5-2 + `TECH.md` §6.6 + `AGENTS.md` 验收口径同步 |
| 4 | 本地 golden **12/12** · 全量 pytest 绿 |
| 5 | `cockpit.html` 下一关改为 R5 KB 审窗 / R5-3 |

**不做**：R5-3 浏览器抽检 · R5-4 demo · KB 审窗 · 顶栏/支付/OCR

---

## R5-3～R5-4（下窗 backlog）

| ID | 做什么 | 触发 |
|----|--------|------|
| R5-3 | 人工对话抽检 GQ+改写题引用 | 企业 demo 前 |
| R5-4 | `ENTERPRISE_DEMO_SCRIPT.md` 与 golden 12 题对齐 | Plan-D8 试跑 |

---

## R5-1 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H1 | 单源放哪 | JSON 在 fixtures→plan 字面一致、测试与 baseline 同读；继续 Python 元组→双份维护 | **JSON SSOT** | ✅ 本窗默认 |
| H2 | 新题放哪 | 扩 `golden_handbook.md` 加表格→GQ-1～10 同库回归；新 md 文件→多 fixture 路径 | **扩 handbook + 同 source=md** | ✅ 本窗默认 |
| H3 | GQ-11 验什么 | 只验 content 含 300→稳；加 chunk_kind=table→要扩 RetrievedChunk，超 R5-1 | **content + section 2.2 餐补** | ✅ 本窗默认 |
| H4 | GQ-12 问法 | 改写「带薪年休假…」→测非原词问法；再加 parent-child 长节→要新 fixture、更重 | **仅改写问法 GQ-12** | ✅ 本窗默认 |
| H5 | 本窗边界 | 做 R5-1 扩题+JSON；R5-2 CI 门禁 / R5-3 人工 / R5-4 demo 对齐 | **仅 R5-1** | ✅ 本窗默认 |

---

## R5-1 验收对照（plan DoD）

| # | 条件 |
|---|------|
| 1 | `tests/fixtures/golden_qa.json` ≥12 条；含跨页、条款号、表格、改写问法标签 |
| 2 | `test_retrieval_golden.py` 从 JSON 加载；`golden_qa.md` v0.4 与 JSON 一致 |
| 3 | `run_golden_production_baseline.py` 仍可读同一 case 列表 |
| 4 | golden Hit@3 **12/12**；全量 pytest 绿 |
| 5 | `rag-optimization-plan.md` §8 R5-1 + `cockpit.html` + `AGENTS.md` 同步 |

**不做**：R5-3 浏览器抽检 · R5-4 demo 脚本 · KB 审窗 · 顶栏/支付/OCR · 改 retrieval/rerank 逻辑
