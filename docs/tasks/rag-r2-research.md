# Research · Plan-RAG R2 索引管道

> **状态**：✅ R2-1 已关 · 🟡 R2-2 假设已落盘（2026-07-06）  
> **依据**：`rag-optimization-plan.md` §5 · `TECH.md` TECH-4 §4.3.6

---

## 3 句话摘要

1. **现有代码在哪**：切片 `services/ingestion/chunker.py`（`structure_chunk`）· 跨页合并 `parser.py` `_merge_cross_page_blocks` · 参数 `IngestionConfig`（1000/80/150）· 管道 `pipeline.py`。
2. **测什么**：R2-1 新增 `test_chunker.py` 锁 TECH-4.3.2 行为；端到端仍靠 `test_retrieval_golden.py` Hit@3（mock 嵌入）。
3. **风险**：改 chunk 参数可能让 golden 某题 miss；R2-1 **不调参**（golden 已 10/10），只加回归测试防未来漂移。

---

## R2 条目现状

| ID | 项 | 现状 | 下一原子 |
|----|-----|------|----------|
| R2-1 | 切片回归 | 参数已对齐 TECH；**缺单元测试** | ✅ 本窗 |
| R2-2 | 表格/Parent-Child | ✅ 本窗 | — |
| R2-3 | 内容去重 | ✅ EW-D1 · migration 013 | — |
| R2-4 | 重嵌入 | ✅ 本窗 | — |
| R2-5 | 存储一致 | ✅ EW-A1 删库 · lifecycle 删文档 | — |

---

## R2-1 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H1 | golden 全绿是否还要调参 | 不调→只加测试锁行为，上传切片逻辑不变；调→可能提升/降低 Hit@3，须重跑通义基线 | 不调参 | ✅ 用户授权（本窗背景 221 绿） |
| H2 | 跨页测私有函数还是只 E2E | 单测 `_merge_cross_page_blocks`→快、准；只 E2E→慢且难定位 | 单测 + golden PDF 题 | ✅ |

---

## R2-2 三句话摘要

1. **现有代码在哪**：`chunker.py` 结构切片 · `parser.py` 无表格分支 · `document_chunks` 无 parent 列 · `retrieval.py` 全 chunk 参与 hybrid。
2. **测什么**：`test_chunker.py` 增表格/父子用例；端到端仍靠 `test_retrieval_golden.py` Hit@3 10/10（golden 无表格，单节短段行为不变）。
3. **风险**：误把正文当表格会多切 chunk；parent 入库检索会重复命中——须 **parent 不入索引**、检索命中 child 后 **LLM 用 parent 全文**。

---

## R2-2 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H3 | 表格识别范围 | 只做 MD pipe + DOCX 表格→手册里 Markdown/DOCX 表格单独成块；PDF 表格下波再做→PDF 里表格仍跟正文混切 | MD + DOCX | ✅ 本窗默认 |
| H4 | Parent 何时建 | 仅当一节被切成 **2+ 子块** 才建 parent→单段章节（golden 多数）不变；长节检索命中小块后对话上下文变整节 | 2+ 子块 | ✅ 本窗默认 |
| H5 | Parent 是否参与检索 | parent **不嵌入、不进 FTS**→搜的还是小块，不会同一节占满 Top-3；命中后 `chat` 用 parent 全文喂 LLM | 不入索引 | ✅ 本窗默认 |
| H6 | 库表变更 | migration 加 `parent_chunk_id` + `chunk_kind`→须跑 alembic；旧数据 `chunk_kind=text` 兼容 | 要 migration | ✅ 本窗默认 |

---

## R2-4 三句话摘要

1. **现有代码在哪**：嵌入 `embedder.py`（通义 v2 硬编码）· 入库 `pipeline.py` 写 `embedding` · **无** `embedding_model` 列 · **无** 全库重嵌任务。
2. **测什么**：`test_re_embed.py` 锁 stale 检测、parent 跳过、批量更新；端到端仍靠 `test_retrieval_golden.py` Hit@3 10/10（mock 嵌入逻辑不变）。
3. **风险**：换模型后旧向量与新 query 向量空间不一致→检索全废；须 **打模型标签 + 后台批量重嵌**；维度变更须另开 migration（本窗假设仍 1536）。

---

## R2-4 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H7 | 模型标签存哪 | 每 chunk 存 `embedding_model`→能精确知道哪条旧了；只存全局配置→不知道谁该重嵌 | 每 chunk 列 | ✅ 本窗默认 |
| H8 | 谁触发重嵌 | 仅运维 CLI + 带密钥的内部 API→用户看不到「索引管理」；做前端按钮→违背 PRD「用户不直接管向量」 | CLI + internal API | ✅ 本窗默认 |
| H9 | 重嵌范围 | 只更新 `embedding_model` 为空或与当前配置不一致的 chunk→省 API 费；每次全量重算→浪费 | 仅 stale | ✅ 本窗默认 |
| H10 | 维度变了怎么办 | 本窗 **不** 自动改 pgvector 列维→换不同维度模型须另开 migration + plan；同维换模型名→跑重嵌即可 | 仍 1536 | ✅ 本窗默认 |
