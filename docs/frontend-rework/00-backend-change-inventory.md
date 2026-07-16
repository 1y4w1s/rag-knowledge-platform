# 后端改动全量盘点（事实源）

> **用途**：前端重做技术参考包的事实基线。本文档是所有后续图（知识图谱 / 架构图）、契约与范围清单的唯一事实来源。
> **基线**：工作区未提交改动 + 近期 feature commit（截至 2026-07-15）。
> **主契约文档**：[`../API_FRONTEND_REFERENCE.md`](../API_FRONTEND_REFERENCE.md)（已据本文档订正 6 处 + 补 Agent 审批章）。
> **图例**：🆕 new（新增） · 🔧 modified（修改） · 🗑 deprecated（废弃）。

---

## 0. 读法说明

- 全量 API 端点面已在主契约文档中列出，**本文只标注"变化点"与"前端必须知道的坑"**，不重复罗列全部端点。
- 凡标注 ⚠️ 的条目，都是**会坑到前端对齐**的事实，务必看 §5。
- 所有结论均来自对后端源码的**逐文件深读**（非猜测），关键处附 `file:line` 铁证。

---

## 1. 未提交的新增子系统（最贴近前端即将对接的真实接口）

### 1.1 反馈子系统 `chat_feedback`（🆕 全链路）

| 层 | 位置 |
|----|------|
| 表 | `chat_feedback`（**唯一新增表**） |
| 路由 | `backend/app/api/feedback.py` |
| Schema | `backend/app/schemas/feedback.py` |
| Service | `backend/app/services/rag/feedback.py` |
| 迁移 | `alembic/versions/d057befd441b_add_chat_feedback.py` |

**端点（5 个，路径前缀 `/api/v1`）：**

- `POST /feedback` — 提交/更新反馈（幂等）
- `GET /feedback/messages/{message_id}` — 查当前用户对某消息的反馈（无则返回 `null`）
- `GET /feedback/stats` — 统计（可选 `?kb_id=`）
- `GET /feedback/history` — 当前用户反馈历史（分页）
- `DELETE /feedback/{feedback_id}` — 撤回反馈

**契约要点（已与 `feedback.py` 逐字核对）：**
- `message_id` 来自 SSE `done` 事件（`= ChatMessage.id`），是反馈唯一键。
- **幂等**：同 `message_id` + `user_id` 第二次提交会更新 `rating`，不新增行。
- `rating`：`1`=👍，`0`=👎；`feedback_text` 可选。

### 1.2 安全过滤 `safety_filter`（🆕 输入侧）

- `backend/app/services/rag/safety_filter.py`
- 在 `chat.py` **第 1.5 步**调用（输入违规检测），违规时返回 canned 安全回复。
- ⚠️ 输出侧 `output_safety_check` 已定义但**未被调用**（见 §5-2）。

### 1.3 嵌入缓存（🔧 `embedder.py` +92 行）

- LRU + TTL 缓存（容量 5000，TTL 3600s），仅对 `tongyi` 嵌入 + 单条命中生效。
- **注：这不是 HyDE**（HyDE 未接入生产，见 §5-1）。这 92 行是缓存逻辑。

### 1.4 复合问题多路召回（🔧 `chat.py` +40 / `retrieval.py` +29）

- `decompose_query` 最多拆 **3 路** → 各路独立召回 → 合并去重 → 重排。
- ⚠️ **双重触发**：`chat.py` 第 2.5 步与 `retrieve_chunks` 内部都调用 `decompose_query`，产生嵌套多路召回 + 额外 LLM 调用（见 §5-3）。功能正确，延迟偏高，前端无感。

### 1.5 检索后压缩（🔧 `generation.py`）

- `dedup_and_compress`：Jaccard 相似度 >0.7 去重 + 单块 800 字截断。

### 1.6 切片升级（🔧 `chunker.py`）

- `SENTENCE_END` 正则新增**英文句边界**（`.` + 空格 + 大写/数字）。
- `SOFT_MAX_MARGIN = 0.2`：软上限 1.2× 保句完整（不硬切断句子）。
- `_last_sentence` 复用同一正则做**句级重叠**。
- 此优化有意且干净，**前端重做不需要关心，但后端不会回退**（记录以防误改）。

---

## 2. 近期已提交、前端需对齐的功能

| 功能 | 端点/位置 | 标记 |
|------|-----------|------|
| 找回密码 / 重置 | `POST /auth/forgot-password`、`POST /auth/reset-password` | 🆕 |
| 文档回收站 | `DELETE .../documents/{id}`（软删）、`.../restore`、`.../permanent`、`GET .../trash` | 🆕 |
| PDF OCR | `ocr_enabled` 解析管线 | 🆕 |
| 文档可见性 | 上传 `?visibility=` + `PATCH .../visibility`（`everyone`/`admin_only`） | 🆕 |
| API Key 管理 | `POST/GET/DELETE /api-keys` | 🆕 |
| 多轮上下文 | `.../threads` + 历史消息 | 🆕 |
| 工作区历史对话搜索 | `GET /ask/search?q=` | 🆕 |
| 审计筛选增强 | `GET /admin/audit-logs` 参数 | 🔧 |
| 登录渐进锁限 + IP 限流 | `services/auth/login_rate_limit.py` | 🔧 |
| 生产部署 | `docker-compose.prod.yml` + `/health` 健康检查 | 🔧 |

> 上述端点全量面见主契约文档，本文不再展开。

---

## 3. 数据模型变更

| 表 | 变更 | 说明 |
|----|------|------|
| `chat_feedback` | 🆕 新增 | 反馈主表，外键 `message_id`→`chat_messages.id`、外键 `user_id`→`users.id` |
| `documents` | 🔧 +`visibility` | `DocumentVisibility`: `everyone` / `admin_only` |
| `documents` | 🔧 +`deleted_at` | 回收站软删标识（非 `status` 字段，是独立时间戳列） |
| `chat_messages` | — | `id` 即反馈用的 `message_id`；存 `citations`、`retrieval_duration_ms` |
| `users` | — | **无**重置令牌列（见下） |

**密码重置设计自洽说明**：`forgot/reset-password` 端点存在，但 `users` 表**无**重置令牌列——因为重置采用**无状态 JWT**（复用 `jwt_secret`，claim `type=password_reset`，有效期 60 分钟）。前端 reset 页只需携带 `token` 参数，无需后端存储。

---

## 4. API 端点面（引用主契约）

全量端点见 [`../API_FRONTEND_REFERENCE.md`](../API_FRONTEND_REFERENCE.md)。本盘点已据深读结果对该文档订正 **6 处**：

1. 搜索参数 `kb_id`/`offset` → `workspace`（必填，personal 或组织 UUID）+ `limit` 1–50，无 offset（`search.py:32`）
2. `workspace` 枚举 `team`/`company` → `personal` 或**组织 UUID 字符串**（`knowledge_bases.py:39`）
3. 文档上传补 `visibility` query 参数（`documents.py:89`）
4. 上传响应 `{items, failed}` → 顶层键 `documents`，**无 `failed`**（`schemas/document.py:37`）
5. 看板响应字段对齐 `DashboardStatsResponse`（看板正在重做）
6. 补 `POST /agent/approvals/{approval_id}/resolve` 章（`agent.py:52`）

---

## 5. ⚠️ 前端必须知道的"未接线 / 死代码"（避免误做）

1. **HyDE 未接入生产**：`generate_hypothetical_answer` 仅在 `generation.py` 定义，只被 `scripts/benchmark_hyde.py` 调用。**前端无需 HyDE 开关/展示/调试入口。**
2. **`output_safety_check` 已定义但未被调用**：无输出侧拦截事件。输入违规时仍走完整 `token` + `done` 流（`citations=[]`）。**前端只需把安全 canned 回复当普通回答渲染，无需特殊错误态。**
3. **`decompose` 双重触发**（§1.4）：功能正确但延迟偏高，前端无感，仅"知晓"。
4. **回收站软删在 `documents/trash.py`，不在 `storage/cleaner.py`**（cleaner 只删磁盘）。删除文档 = DB 软删（`deleted_at`）+ 物理删兜底两层，删除/恢复/永久删接口已齐。
5. **登录限流阈值硬编码**（`login_rate_limit.py`：5/15min、20/5min、锁 1m/5m/15m/1h），不在 `config.py`——前端可展示锁定时长，但无法靠配置灰度。
6. **重置 token 无法主动失效**：`RESET_TOKEN_KEY_PREFIX` 为死代码（无状态 JWT 设计使然，非 bug，但记录以免误以为可"撤回重置邮件"）。

---

## 6. 关键契约事实（不可推翻）

- **SSE 协议**：`citation` / `token` / `done`；`done = { message_id, citations }`；`message_id = ChatMessage.id`（反馈唯一键）。
- **feedback 幂等**：每人每消息一条，重复提交更新 `rating`。
- **429**：`chat 30/h`、`upload 20/h`（`services/auth/api_rate_limit.py:17-20` 确认）。
- **上传响应**：顶层键 `documents`，无 `failed`。
- **搜索参数**：`workspace`（非 `kb_id`、无 `offset`）。
- **文档可见性枚举**：`everyone` / `admin_only`（非 `team`/`company`）。

---

## 7. 待前端重做对接的总览（详见 `04-frontend-rework-scope.md`）

- **需新对接接口**：feedback 全套、找回密码/重置、`PATCH /settings/profile`、`/ask/search`、文档可见性、回收站三件套、API Key 管理、Agent 审批 resolve。
- **变更数据结构**：`chat_feedback` 模型、`documents` 可见性/回收站字段、SSE `done.message_id` 回填、看板 `DashboardStatsResponse` 字段重命名。
- **功能范围**：反馈组件、密码重置流程、文档可见性 UI、回收站、API Key 面板、对话多轮 + 历史、安全拒绝态 UX（普通渲染）、Agent 审批流。
