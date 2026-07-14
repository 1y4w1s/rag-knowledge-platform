# Research · Plan-RAG R3 检索质量

> **状态**：✅ R3-3 Research 已关（2026-07-07 · 企业选型：不 Implement）· R3-4 ✅ · R3-2 ✅ · R3-1 ✅  
> **依据**：`rag-optimization-plan.md` §6 · `TECH.md` TECH-4 §4.6

---

## 3 句话摘要

1. **现有代码在哪**：hybrid 检索 `services/rag/retrieval.py`（向量 Top-20 + FTS Top-20）· RRF 融合 `services/rag/rrf.py`（`k=60` 硬编码、两路等权）· 配置 `core/config.py` 仅有 `retrieval_min_top1_similarity`。
2. **测什么**：`test_retrieval_hybrid.py` RRF 单元 + SA-3 隔离；端到端 `test_retrieval_golden.py` Hit@3 10 题（mock 词重叠嵌入）；改融合参数须 **10/10 绿** 再落盘。
3. **风险**：FTS 权重过高→语义近义问法 miss；向量权重过高→条款号/英文原词题 miss（GQ-4/GQ-8）；`k` 过小→Top-1 过度集中、双路互补弱。

---

## R3 条目现状

| ID | 项 | 现状 | 下一原子 |
|----|-----|------|----------|
| R3-1 | hybrid 调参 | RRF `k`/权重硬编码 | ✅ 本窗 |
| R3-2 | Rerank | ✅ `rerank.py` · RRF 20→5 | ✅ 本窗 |
| R3-3 | Query 改写 | ✅ Research 已关 · **不 Implement**（golden+通义 12/12） | 触发：生产 miss 或 Plan 授权 |
| R3-4 | 安全 kb+workspace | ✅ `kb_id` 二次校验 + 复核测试 | ✅ 本窗 |

---

## R3-1 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H1 | RRF 平滑常数 `k` | k=60（文献常用）→排名靠后的 chunk 仍有一点分，双路互补稳；k=20→更看前几名，易把「只在一路 Top-3」的块挤掉 | **60** | ✅ 本窗默认（golden 10/10 基线） |
| H2 | 向量 vs 全文权重 | 等权 1/1→与 Wave 3.4 行为一致；FTS 略高→「1.1 年假」类原词更稳，纯语义问法可能略降 | **vector=1.0 · fts=1.2** | ✅ 本窗默认 |
| H3 | 参数放哪 | 进 `Settings` + `.env`→运维可 A/B 不改代码；写死在 rrf.py→调参要发版 | **Settings** | ✅ 本窗默认 |
| H4 | 本窗是否改 recall 数 | 改 Top-20→影响 DB 负载与 RRF 输入分布，超出 R3-1 | **不动 20/20** | ✅ 本窗默认 |

---

## R3-1 验收对照（plan DoD）

| # | 条件 |
|---|------|
| 1 | `reciprocal_rank_fusion` 支持 `k` + 分路 `weights` |
| 2 | `retrieve_chunks` 从 `settings` 读参，默认与 H1/H2 一致 |
| 3 | 单元测试覆盖加权 RRF；golden Hit@3 **10/10**；全量 pytest 绿 |
| 4 | `rag-optimization-plan.md` §6 R3-1 节 + cockpit 同步 |

**不做**：rerank · query 改写 · 顶栏/支付/OCR · 改 recall limit。

---

## R3-2 · 3 句话摘要

1. **现有代码在哪**：`retrieve_chunks` 在 RRF 后直接取 Top-5 返回；无 rerank 模块；`Settings` 仅有 RRF 参数。
2. **测什么**：新增 `rerank.py` 单测（mock 重排）+ 端到端 `test_retrieval_golden.py` Hit@3 须 **10/10**；`RERANK_ENABLED=false` 时行为与 R3-1 一致。
3. **风险**：生产 API 失败须回落 RRF 顺序；mock 与 golden 词重叠嵌入须一致，避免 rerank 把正确 chunk 挤出 Top-3。

---

## R3-2 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H5 | rerank 用哪家 | 通义 `qwen3-rerank`（同 `TONGYI_API_KEY`）→ 和嵌入一家、不用装大模型；本地 cross-encoder→要多依赖、Docker 镜像变大 | **tongyi API** | ✅ 本窗默认 |
| H6 | RRF 与 rerank 怎么接 | RRF 先取 20 条再 rerank 到 5→符合 TECH「Top20→5」，语义精排有空间；RRF 直接 Top-5 再 rerank→候选太少、提升有限 | **RRF 20 → rerank 5** | ✅ 本窗默认 |
| H7 | 测试环境怎么排 | 词重叠 mock（与 golden 嵌入 mock 同思路）→ pytest 无 Key 也能验重排逻辑；调真 API→CI 不稳定、要 Key | **mock 词重叠** | ✅ 本窗默认 |
| H8 | 能否关掉 rerank | `RERANK_ENABLED=false`→退回 R3-1 纯 RRF Top-5，方便对比与排障 | **默认 true** | ✅ 本窗默认 |
| H9 | 本窗是否改 recall | 改向量/全文各 Top-20→动 DB 负载与 RRF 分布，超出 R3-2 | **不动 20/20** | ✅ 本窗默认 |

---

## R3-2 验收对照（plan DoD）

| # | 条件 |
|---|------|
| 1 | `services/rag/rerank.py`：通义 API + mock 词重叠；API 失败回落 RRF 顺序 |
| 2 | `retrieve_chunks`：RRF `top_n=rerank_input_top_n`（默认 20）→ rerank → Top-5；`RERANK_ENABLED=false` 时等同 R3-1 |
| 3 | `Settings`：`RERANK_ENABLED` · `RERANK_PROVIDER` · `RERANK_MODEL` · `RERANK_INPUT_TOP_N` |
| 4 | 单测覆盖 mock 重排 + disabled 回落；golden Hit@3 **10/10**；全量 pytest 绿 |
| 5 | `rag-optimization-plan.md` §6 R3-2 节 + cockpit + AGENTS 同步 |

---

## R3-4 · 3 句话摘要

1. **现有代码在哪**：`retrieve_chunks` 在向量/全文 recall 已 `WHERE kb_id`；R3-2 新增 `rerank_chunks` 仅重排候选、不拉新数据；`require_kb_access` 在 chat API 做 SA-1/SA-2；L3 搜索 API 有 `workspace` 过滤（S7/S8）。
2. **测什么**：R3-2 后须 **显式** 在 `RERANK_ENABLED=true` 下重跑 SA-3；补 enterprise personal vs org 库隔离；`RetrievedChunk` 带 `kb_id` + rerank 后 `_enforce_kb_scope` 剔除跨库。
3. **风险**：rerank 只改顺序、理论上不引跨库；防御性二次校验防未来 refactor 回归；workspace 在检索层靠 kb 归属间接保证，不靠 query 参数。

---

## R3-4 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H10 | rerank 后要不要二次 kb 校验 | 加 `_enforce_kb_scope`→多一层保险，万一以后有人改坏 recall 不会把别库片段送进 LLM；不加→和现在一样靠 SQL WHERE，测试绿但无兜底 | **加二次校验** | ✅ 本窗默认 |
| H11 | RetrievedChunk 是否带 kb_id | 带→单测/E2E 可直接断言 SA-3，不用回查 DB；不带→只能事后查 chunk 表 | **带 kb_id** | ✅ 本窗默认 |
| H12 | workspace 怎么验 | 企业用户建 personal + org 两库，查 personal 库不得命中 org 秘密→覆盖「同账号跨空间」；chat API 仍靠 kb_id+权限，本窗不重复 SA-2 | **retrieve_chunks 层补测** | ✅ 本窗默认 |

---

## R3-4 验收对照（plan DoD）

| # | 条件 |
|---|------|
| 1 | `RetrievedChunk.kb_id` + `retrieve_chunks` rerank 后 `_enforce_kb_scope` |
| 2 | `test_retrieval_security.py`：SA-3 rerank 开启 + workspace personal/org 隔离 + 单元 `_enforce_kb_scope` |
| 3 | golden Hit@3 **10/10**；全量 pytest 绿 |
| 4 | `rag-optimization-plan.md` §6 R3-4 节 + cockpit + AGENTS 同步 |

**不做**：query 改写 · 顶栏/支付/OCR · 改 recall limit · chat API 加 workspace 参数

---

## R3-3 · 3 句话摘要

1. **现有代码在哪**：对话检索 `services/rag/retrieval.py` 的 `retrieve_chunks` — 用户原问 **一次** `embed_texts` + **一次** `_fts_recall`，RRF（R3-1）→ rerank（R3-2）→ `_enforce_kb_scope`（R3-4）；`chat.py` 把 `message` 原样传入；**无** HyDE / 多 query 模块；L3 跨库搜走独立 API、不经此函数。
2. **测什么**：`test_retrieval_golden.py` **12/12**（含 GQ-12「带薪年休假」改写问法 · mock 词重叠嵌入）；若 Implement 须 **12/12 不退化** + 新增 query 改写单测（mock LLM）；企业抽测用真通义嵌入看 paraphrase 题是否比现状更稳（R5-3）。
3. **风险**：golden 已满 → Implement **边际收益小**，主要价值是答辩/面试可讲「query 扩展」；HyDE 假想段落可能编造词、把向量路带偏；多 query 成倍嵌入/DB 负载与首 token 延迟；CI mock 与生产 LLM 改写质量不一致。

---

## R3-3 · 方案对比（HyDE vs 多 query）

| 维度 | **HyDE**（假想文档嵌入） | **多 query 融合**（LLM 出 2～3 个搜题变体） |
|------|--------------------------|---------------------------------------------|
| **做什么** | 先让 LLM 写一段「像知识库里会出现的回答」，**嵌入这段假想文**做向量 recall | 让 LLM 列出 2～3 个不同说法的**搜索问句**，每句各跑向量+FTS，再把多路排名 **RRF 合并** |
| **解决啥** | 问法与文档用语差距大（口语 vs 条款体）时，向量路更接近 chunk 文本 | 同义/改写/中英混问（如 GQ-12）时，多路 recall 提高「至少一路 Top-20 命中」概率 |
| **对 FTS** | 通常 **仍用用户原问** 做全文（条款号/英文原词靠 FTS 路，见 GQ-4/7） | 每变体各跑 FTS，条款号题更稳，但 **DB 查询次数 ×N** |
| **额外成本** | +1 次 LLM 调用 + 仍 1 次嵌入（向量路） | +1 次 LLM 调用 + **N 次嵌入** + **N 组** vector/FTS recall |
| **与现有栈** | 只改向量 recall 的 query 向量来源；RRF/rerank 结构可不变 | 在 RRF 前扩展为「2N 路 ranked list」或「先各路 hybrid 再总 RRF」 |
| **golden 12/12** | GQ-12 已绿 → **难指望 CI 指标提升**；收益在 mock 测不到的「真嵌入 paraphrase」 | 同上；GQ-12 专为此类设计，Implement 后 golden 可能 **不变** |
| **答辩可讲** | 「用 LLM 桥接 query–document 语义鸿沟」 | 「Multi-query + RRF 提高召回覆盖面」 |

**Research 结论（✅ 2026-07-07 企业选型）**：golden + 通义生产基线 **12/12**，**不 Implement R3-3**。若将来 miss 驱动再做：**多 query + RRF 扩展**（非 HyDE 主路径）· `QUERY_REWRITE_ENABLED=false` 默认关 · 须可观测 + 限流先行。详见 H13～H24。

---

## R3-3 待确认假设

| 假设 | 人话选项 | 选这个的后果（白话） | 默认 | 状态 |
|------|----------|----------------------|------|------|
| H13 | 本条目要不要 Implement | **只做 Research 文档**→ golden 仍 12/12、零延迟零成本，答辩口播靠本文；**要做代码**→多一次 LLM 调用/问，首答慢几百 ms～1s，CI 须补 mock，面试能指具体文件 | **Research 关即可；Implement 留 Plan 待触发** | ✅ 用户确认（2026-07-07 · 企业选型：不 Implement） |
| H14 | 主策略选哪条 | **HyDE**→向量搜「假想答案」、全文仍搜原问，适合口语问书面库；**多 query**→2～3 个问法各搜一遍再合并，适合 GQ-12 类改写；**都不做**→维持现状，plan 标 backlog | **都不做**（将来若做 → 多 query） | ✅ 用户确认（2026-07-07 · 都不做） |
| H15 | 多 query 时 LLM 出几条 | 2 条变体→延迟/成本约 2× recall，通常够；3 条→召回更宽但 DB 更慢，golden 难体现差异 | **2 变体 + 原问共 3 路**（原问必保留一路） | ✅ 授权默认（Implement 未排） |
| H16 | 多路结果怎么合并 | **所有 ranked list 扔进同一个 RRF**（chunk_id 去重）→与 R3-1 一致、改 `retrieve_chunks` 一处；**每路先 hybrid 再手工并分**→逻辑重复、难测 | **扩展 RRF 输入列表**（原问 vector/fts + 变体 vector/fts） | ✅ 授权默认（Implement 未排） |
| H17 | HyDE 时 FTS 用谁 | **FTS 始终用户原问**→「1.2 条款」类题仍靠全文路（推荐与 H14 多 query 组合时：变体只走向量）；**FTS 也用假想文**→条款号/英文原词题可能 miss（GQ-4/7 风险） | **FTS=原问；HyDE 仅向量**（若选 HyDE） | ✅ 授权默认（Implement 未排） |
| H18 | 改写用哪家 LLM | **DeepSeek**（同回答 `deepseek-chat`）→ Key 已有、与生成一致；**通义**→多一家依赖，但与 embed/rerank 同厂 | **DeepSeek** | ✅ 授权默认（Implement 未排） |
| H19 | LLM 失败/超时 | **静默回落原问检索**→用户仍能答，只是没改写加成；**整问失败/拒答**→体验差，仅适合严格实验 | **回落原问** | ✅ 授权默认（Implement 未排） |
| H20 | 功能开关默认值 | **默认关** `QUERY_REWRITE_ENABLED=false`→生产与 CI 行为与现在一致，答辩 demo 手动开；**默认开**→每问多调 LLM、成本与延迟全量上涨 | **默认关** | ✅ 授权默认（Implement 未排） |
| H21 | pytest 怎么测 | **mock LLM 返回固定变体**→无 Key 可测 RRF 合并与开关；**只测 disabled**→Implement 逻辑无单测覆盖；真 API→CI 不稳定 | **mock 固定变体 + disabled=现状** | ✅ 授权默认（Implement 未排） |
| H22 | 作用范围 | **仅 `retrieve_chunks`（对话）**→与 R3 范围一致、L3 发现层不动；**L3 正文搜也改**→范围扩到 `search` API，需另开 plan | **仅对话检索** | ✅ 授权默认（Implement 未排） |
| H23 | rerank 用哪个 query | **始终用户原问** rerank→排序仍对齐用户意图；**用主变体/假想文** rerank→可能与用户看到的问法不一致 | **rerank 用原问** | ✅ 授权默认（Implement 未排） |
| H24 | 本窗是否写 Implement plan | **Research 关后另开 L 窗**写 `rag-r3-plan.md` 原子任务→符合 WIP=1；**同窗夹 plan**→阶段混 | **Research 关 → 再 L 窗** | ✅ 用户确认（2026-07-07 · 不排 L 窗直至 miss 触发） |

---

## R3-3 验收对照（Research DoD · 本窗）

| # | 条件 |
|---|------|
| 1 | 本节 **3 句话摘要** + HyDE vs 多 query 对比表 |
| 2 | H13～H24 假设表含 **后果（白话）** |
| 3 | 用户拍板 H13/H14（做不做 · 选哪条）或标 🟡 留 Plan | ✅ H13 不 Implement · H14 都不做（2026-07-07） |
| 4 | `rag-optimization-plan.md` §6 R3-3 Research 行 + `cockpit.html` 同步 |
| 5 | **本窗不写** `services/rag/` 实现代码 |

**不做（本窗）**：Implement · 改 retrieval/rerank · 顶栏/支付/OCR · L3 搜索 · 动 golden 题面
