# G-1 · 工作区智能问答（方案 C）· Plan

> **状态**：✅ Plan 已落盘（2026-07-08）→ ✅ G1-0～G1-4 Implement · ✅ G1-5.1 TECH · ✅ G1-5.2 cockpit · ✅ G1-5.3 手工验收表  
> **依据**：`discovery-smart-chat-prd.md` ✅ · `discovery-smart-chat-research.md` ✅  
> **拍板**：**效果优先**（用户 2026-07-08 要求不考虑改动量）· 见 §1

---

## §0 做 & 不做

| 做 | 不做 |
|----|------|
| 侧栏「对话」→ **`/ask`** · 概览提问 → `/ask?q=` | 顶栏 ⌘K · 独立 `/search` 对话页 |
| **`POST /ask/chat`** SSE + **`GET /ask/messages`** 历史 | 替换库内 `/knowledge-bases/{id}/chat` |
| 跨 **visible_kb_ids** hybrid 检索 + rerank Top-5 | 按库循环 N 次 retrieve（H1-B） |
| 引用 **`库名 · 文档 · 章节 · p.页码`**（工作区） | 工作区 chip 仍用单库格式 |
| **工作区 thread 落库**（刷新仍见历史 · E14 灰态 chip） | Wave 1 不落库（H4-D） |
| Top-5 **多库多样性**（E7 · H7） | 5 chip 全来自同一库时不做处理 |
| 库内 chat **补传 `department_id`**（H8 · 与搜文档一致） | 改 RAG golden 单库路径语义 |
| OrgScope / M5 限流 / 未分配禁用 / 空库空态 | 支付 · 积分 · OCR · Agent 联网 |
| pytest T-ask-1～7 + 库内回归 + golden 12/12 + `npm run build` | 改 PRD 已定稿节 |

---

## §1 拍板记录（Research H1～H8 · 效果优先）

| 假设 | 选定 | 状态 |
|------|------|------|
| **H1-A** | 一次 SQL · `kb_id IN visible_kb_ids` · 新文件 `retrieval_workspace.py` | ✅ Plan |
| **H2-A** | `POST /api/v1/ask/chat` + `GET /api/v1/ask/messages` | ✅ Plan |
| **H3-A** | `CitationPayload` 统一 +`kb_id`/`kb_name` · 库内 UI 不展示库名 | ✅ Plan |
| **H4-A** | 扩表：`thread_kind` + `kb_id` 可空 + workspace 上下文列 · 工作区历史 | ✅ Plan（非 H4-D） |
| **H5-A** | 无可见库 → API 400 + 前端空态引导 | ✅ Plan |
| **H6-A** | 单库 `retrieve_chunks` **不动** · 多库新函数 | ✅ Plan |
| **H7** | rerank 后 diversity：多库均有命中时 Top-5 **每库至少 1 条**（上限 5 · 见 G1-2.3） | ✅ Plan |
| **H8** | `chat-api.ts` / `ask-api.ts` 均 `appendScopeQuery` | ✅ Plan |

---

## §2 原子任务（I 窗按序 · WIP=1 · 一次只做一条或标注「可同窗」的小步）

### Wave 0 · 数据模型（Implement 前基线 pytest 绿）

| # | 任务 | 文件 / 动作 | 验收 |
|---|------|-------------|------|
| **G1-0.1** | Alembic：`chat_messages` 增 `thread_kind`（`knowledge_base` \| `workspace`）· `kb_id` **nullable** · `workspace_kind` · `workspace_org_id` · `workspace_department_key`（存 `department_id` 或 `all` 或空=主部门） | `alembic/versions/017_chat_workspace_thread.py` | `alembic upgrade head` 绿 · 旧行默认 `knowledge_base` + 原 `kb_id` |
| **G1-0.2** | 模型 + persistence：`save_kb_chat_turn` / `save_workspace_chat_turn` · `list_workspace_chat_messages` | `models/chat_message.py` · `services/rag/persistence.py` | 现有 `test_chat_messages.py` **仍绿** |
| **G1-0.3** | Dashboard stats：`chat_message_count` 等 **仅统计 `thread_kind=knowledge_base`**（或 `kb_id IS NOT NULL`） | `services/dashboard/stats.py` | `test_dashboard.py` 绿 · workspace 消息不计入「资料库对话」格 |

### Wave 1 · 跨库检索 + 引用 schema（动 RAG · **必跑 golden**）

| # | 任务 | 文件 / 动作 | 验收 |
|---|------|-------------|------|
| **G1-1.1** | `retrieve_workspace_chunks(db, query, scope, org_scope)`：JOIN `knowledge_bases` 取 `kb_name` · vector+FTS recall 用 `kb_scope_clause` · 全局 RRF · rerank | `services/rag/retrieval_workspace.py`（新建 ≤300 行） | 单元/集成：personal 2 库仅命中 A · org member 无兄弟库 chunk |
| **G1-1.2** | `_apply_kb_diversity(chunks, top_k=5)`：若 ≥2 库且 score ≥ gate，保证每库 ≥1 条再填满（H7） | 同上或 `services/rag/diversity.py` | T-ask-6：两库同主题 → chip **kb_name 不同** |
| **G1-1.3** | `chunk_to_citation` 扩展 / `workspace_chunk_to_citation`：输出含 `kb_id` · `kb_name` | `retrieval.py` 或 `retrieval_workspace.py` | 库内路径仍可调旧函数（无 kb_name 或前端忽略） |
| **G1-1.4** | `CitationPayload` / SSE：`kb_id` · `kb_name` 可选字段（库内可不填） | `schemas/chat.py` | `test_chat.py` R4-3 契约扩展或兼容 optional |

**Wave 1 DoD**：`pytest tests/test_retrieval_golden.py` **12/12** · `test_retrieval_security.py` 绿 · 新增 `test_retrieval_workspace.py` 绿

### Wave 2 · 工作区对话 API

| # | 任务 | 文件 / 动作 | 验收 |
|---|------|-------------|------|
| **G1-2.1** | `stream_workspace_chat_events`：retrieve_workspace → gate → SSE → `save_workspace_chat_turn` | `services/rag/chat.py` 或 `workspace_chat.py` | SSE：citation 含 kb_name · done 含 message_id |
| **G1-2.2** | `POST /ask/chat`：`workspace` 必填 · `department_id` · M5 · 未分配 403 · `visible_kb_ids` 空 → 400 | `api/ask.py` | T-ask-4 · T-ask-5 · T-ask-1 |
| **G1-2.3** | `GET /ask/messages`：按 user + workspace 上下文拉历史 · citation 不可见 → `source_status`（ORG-1.7） | `api/ask.py` · 复用 `is_kb_visible_in_org_scope` | T-ask-2 · E14 pytest |
| **G1-2.4** | `main.py` 注册 `ask_router` | `main.py` | OpenAPI 见 `/ask/chat` |
| **G1-2.5** | `test_ask_chat.py`：T-ask-1～7 全表 | `tests/test_ask_chat.py` | A1 · A2 绿 |

**Wave 2 DoD**：`pytest` 全绿 · curl SSE 手工一条

### Wave 3 · 库内 chat scope 对齐（H8 · 可与 G1-2 分窗）

| # | 任务 | 文件 / 动作 | 验收 |
|---|------|-------------|------|
| **G1-3.1** | `chat-api.ts`：`streamChat` / `fetchChatMessages` / `resolveCitation` 走 `appendScopeQuery` | `frontend/src/lib/chat-api.ts` | Network 见 `department_id` · org isolation 手工 |
| **G1-3.2** | 后端库内 chat 已有 `department_id` — **仅补 pytest** 若缺 | `tests/test_org_isolation.py` 可选 1 条 | 切部门后检索范围变 |

### Wave 4 · 前端 `/ask` 页 + 入口

| # | 任务 | 文件 / 动作 | 验收 |
|---|------|-------------|------|
| **G1-4.1** | `ask-api.ts`：stream + fetch messages + `appendScopeQuery` | `lib/ask-api.ts` | 与 search-api 同模式 |
| **G1-4.2** | `use-ask-session.ts`（或泛化 hook）：无 kbId · workspace 历史 | `lib/use-ask-session.ts` | 刷新仍加载历史 |
| **G1-4.3** | `AskPage.tsx`：无 `ChatToolbar` 库切换 · 页头「对话」/「当前空间」· `canUseTeamBusiness` · 空库空态 | `pages/AskPage.tsx` | E9 · E17 浏览器 |
| **G1-4.4** | 路由 `/ask` · `isChatNavActive` 匹配 | `routes/index.tsx` · `sidebar-nav.tsx` | E8 未登录 → login |
| **G1-4.5** | `AppSidebar` chatPath → `/ask` | `AppSidebar.tsx` | S2 侧栏进工作区对话 |
| **G1-4.6** | `DashboardZoneA`：`/ask?q=` · 占位「输入问题，在全部资料库中检索…」· 无 recentKbId 也可问（有库即可） | `DashboardZoneA.tsx` | S5 |
| **G1-4.7** | `formatCitationLabel(citation, 'workspace')` · `ChatMessageList` 预览用 `citation.kb_id` | `chat-api.ts` · `ChatMessageList.tsx` · `CitationChip.tsx` | S1 chip 库名在前 · S6 库内仍无库名 |
| **G1-4.8** | 切 workspace → 清 thread / 跳概览（PRD E11）· 切部门 toast（E3） | `AskPage` + workspace/department context | 手工 E3 · E11 |

**Wave 4 DoD**：`npm run build` 绿 · PRD S1～S7 浏览器勾选

### Wave 5 · 文档 + 关单

| # | 任务 | 文件 | 验收 |
|---|------|------|------|
| **G1-5.1** | TECH 补 `/ask` 路由 + 数据流 3～5 步（TECH-5 或 TECH-6 小节） | `docs/TECH.md` | 与 plan 一致 | ✅ 2026-07-09 · §3.5.2 · TECH-5.7 |
| **G1-5.2** | `cockpit.html` G-1 Implement ✅ · PRD 索引 | `docs/cockpit.html` | SSOT | ✅ 2026-07-09
| **G1-5.3** | 手工验收表（摘 PRD G-1-5 S/E） | `docs/G1_ASK_ACCEPTANCE.md` | 用户勾选 | ✅ 2026-07-09

---

## §2.1 实施顺序（强制）

```
G1-0.* → G1-1.* → G1-2.* → G1-3.* → G1-4.* → G1-5.*
         ↑ golden gate
```

**推荐第一窗 I**：`G1-0.1` + `G1-0.2`（迁移 + persistence，不动检索）  
**第二窗 I**：`G1-1.1`～`G1-1.4`（检索 + schema，**必须 golden**）  
**第三窗 I**：`G1-2.*`（API + pytest）  
**第四窗 I**：`G1-4.*`（前端；`G1-3.1` 可并入或单独）  
**第五窗 I**：`G1-5.*`

---

## §3 大白话（Implement 前须听懂）

**一句话**：侧栏点「对话」进 **`/ask`**，不用选资料库；系统在 **当前空间、当前部门能看到的所有库** 里一起搜，流式回答；每条引用前加 **库名**；刷新页面 **对话还在**；从库详情「开始对话」仍是 **只搜这一个库**，引用 **不带库名**。

| 名词 | 人话 |
|------|------|
| `/ask` | 工作区对话页，页头不出现单一库名 |
| visible_kb_ids | 此刻你能看到的资料库 ID 列表（和列表页、找文档同一套规则） |
| thread_kind | 消息属于「某个库的对话」还是「整个工作区的对话」 |
| diversity | 多个库都有依据时，引用里 **尽量每个库都露一个**，不是 5 条全来自同一库 |
| appendScopeQuery | 请求 URL 自动带上 workspace 和部门，和后端 OrgScope 对齐 |

**你怎么验（最小集）**

1. `demo_admin` · 团队 · 侧栏 **对话** →「年假有多少天？」→ 回答 + chip **带库名** · 含「10」  
2. `demo_member` · 研发 · 问员工手册 → 有引用 · **没有**薪酬库  
3. 库详情 **开始对话** → chip **无库名** · 只搜该库  
4. 概览输入框回车 → `/ask?q=` 自动发问  
5. 刷新 `/ask` → **历史还在**；撤 grant 后旧 chip **灰/不可用**  
6. 终端：`pytest tests/test_ask_chat.py tests/test_retrieval_golden.py` 绿 · `npm run build` 绿  

**这回不做**：顶栏全局搜、**多 thread 列表与 thread 表（→ G2 `discovery-smart-chat-g2-threads-plan.md`）**、支付、改 embedding 模型。

---

## §8 G1 后续 · G-2 企业级历史（2026-07-08 用户提）

> G1-4 交付的是 **单条连续流**（刷新能加载，但「新建对话」只清屏 · 无会话列表）。  
> **企业级多 thread + UX 大修** 单独立项 → **`docs/tasks/discovery-smart-chat-g2-threads-plan.md`**（**P ✅ · V ✅ · L ✅** 2026-07-09 · 下一窗 **I · G2-0.1**）。

| G1 已有 | G2 补 |
|---------|--------|
| 消息落库 · citation 溯源 | `chat_threads` 表 · 列表 UI |
| `GET /ask/messages` flat | `GET /ask/threads` + 按 thread 拉消息 |
| 新建对话 = 前端清空 | POST 新 thread · 旧会话可点回 |

**WIP=1**：G1-5 文档关单与 G2 P 窗可并行；**G2 Implement 须在 G2 Plan L 关之后**。

---

## §4 验收映射（PRD G-1-5 → Plan）

| PRD | Plan 覆盖 |
|-----|-----------|
| S1～S4 | G1-2.5 · G1-4 浏览器 |
| S5 | G1-4.6 |
| S6 | G1-4.7 · 库内页不变 |
| S7 | G1-4.7 · citation.kb_id 预览 |
| E1 · E5 | G1-2.5 T-ask-3 |
| E7 | G1-1.2 · T-ask-6 |
| E14 | G1-2.3 |
| E17 | G1-4.3 |
| A1～A3 | G1-2.5 · golden · build |

---

## §5 门禁三题（Implement 前自答）

1. **触发点**：侧栏/概览 → `/ask` → `POST /api/v1/ask/chat?workspace=&department_id=`（团队）  
2. **数据流**：resolve scope → `retrieve_workspace_chunks` → gate → SSE（citation+token）→ `save_workspace_chat_turn` → 前端 chip 点 `citation.kb_id` 预览  
3. **怎么验**：§3 浏览器 6 步 + `test_ask_chat.py` + `test_retrieval_golden` 12/12 + build  

---

## §6 Plan 退出 DoD

| # | 条件 | 状态 |
|---|------|------|
| L1 | 本文落盘 | ✅ 2026-07-08 |
| L2 | §0 边界 + §1 拍板已记录 | ✅ |
| L3 | §3 大白话用户听懂 | 🟡 |
| L4 | §5 门禁三题能答 | 🟡 |
| L5 | 用户确认 → 才可开 **I 窗**（@ 本文件 + 指定 G1-x.x） | 🟡 |

---

## §7 下一窗交接（I · 建议从 G1-0.1 起）

```
@rag-knowledge-platform/AGENTS.md
@rag-knowledge-platform/docs/tasks/discovery-smart-chat-plan.md
@rag-knowledge-platform/docs/tasks/discovery-smart-chat-prd.md
@rag-knowledge-platform/docs/cockpit.html

【背景】G-1 L 关 Plan ✅ · 效果优先拍板 H4-A/H7/H8 · 库内 chat 保留

【要求】严格只做 plan **G1-0.1 + G1-0.2**（迁移 + persistence）· 不动 retrieval · 不动前端

【验收】alembic head 绿 · test_chat_messages + test_chat 仍绿 · 汇报改动文件与行数
```
