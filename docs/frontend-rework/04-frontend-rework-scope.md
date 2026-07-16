# 前端重做范围清单（技术参考包）

> **用途**：汇总 `00`~`03` 全部产出，给出前端重做需要对接的**新接口、变更数据结构、功能范围**，并区分「待做」与「已在进行」避免重复劳动。
> **配套**：主契约 [`../API_FRONTEND_REFERENCE.md`](../API_FRONTEND_REFERENCE.md) · 知识图谱 [`01-knowledge-graph.html`](01-knowledge-graph.html) · 架构图 [`03-architecture.html`](03-architecture.html) · 事实源 [`00-backend-change-inventory.md`](00-backend-change-inventory.md)。

---

## 0. 阅读顺序建议

1. 先看本文（范围总览）→ 2. 主契约（逐接口字段）→ 3. 知识图谱（理解实体/数据流）→ 4. 架构图（理解边界/部署）。

---

## 1. 需新对接的接口（按优先级）

| 优先级 | 接口 | 说明 | 契约位置 |
|--------|------|------|----------|
| P0 | `POST /feedback` 等 5 个 | 反馈子系统（👍/👎 + 评论 + 统计 + 历史 + 撤回） | 主契约 §六 |
| P0 | `POST /feedback` 的 `message_id` 回填 | 必须从 SSE `done` 事件捕获 `message_id` 再提交 | 主契约 §四 / §六 |
| P1 | `POST /auth/forgot-password` · `POST /auth/reset-password` | 密码重置（无状态 JWT，reset 页只需 `token`） | 主契约 §一 |
| P1 | `PATCH /settings/profile` | 改昵称/用户名 | 主契约 §十三 |
| P1 | `GET /ask/search?q=` | 工作区历史对话搜索 | 主契约 §五 |
| P1 | 文档可见性：`POST .../documents?visibility=` + `PATCH .../documents/{id}/visibility` | `everyone` / `admin_only` | 主契约 §三 |
| P1 | 回收站三件套：`DELETE`（软删）、`.../restore`、`.../permanent`、`GET .../trash` | 软删 = `deleted_at` 时间戳 | 主契约 §三 |
| P2 | `POST/GET/DELETE /api-keys` | API Key 管理面板 | 主契约 §十四 |
| P2 | `POST /agent/approvals/{id}/resolve` | Agent 写库审批（adopt/cancel） | 主契约 §十四（续） |

> **搜索参数修正**：跨库搜索用 `workspace`（personal 或组织 UUID）+ `limit`，**不是** `kb_id`/`offset`（已订正主契约 §七）。

---

## 2. 变更的数据结构

| 结构 | 变更 | 前端影响 |
|------|------|----------|
| `chat_feedback` | 🆕 新表对应前端反馈模型 | 建反馈组件状态、幂等处理（同消息重复提交=更新） |
| `documents.visibility` | 🔧 新增字段 | 列表/详情展示可见性标记；上传与 PATCH 支持设置 |
| `documents.deleted_at` | 🔧 回收站软删 | 列表需区分「正常 / 回收站」；删除=软删，需恢复/永久删 UI |
| SSE `done.message_id` | 🔧 反馈回填键 | ChatPage 必须在 `done` 事件存 `message_id` 供反馈提交 |
| `DashboardStatsResponse` | 🔧 字段重命名 | 看板正在重做：`kb_count`→`knowledge_base_count`、`chat_count`→`chat_message_count`、`document_statuses`→`documents_by_status`(含 `queued`)、`format_share`→`format_distribution`、`trend`→`question_trend`(`date`+`count`)、`recent_activity`→`recent_activities` |
| 上传响应 | 🔧 顶层键 `documents`，无 `failed` | 上传成功解析 `{documents:[...]}`；失败不在响应暴露 |
| `workspace` 枚举 | 🔧 `personal` 或**组织 UUID**（非 `team`/`company`） | 知识库/搜索/工作区切换传组织 ID 字符串 |

---

## 3. 功能范围（前端重做须覆盖）

1. **反馈组件**：对话回答下方的 👍/👎 + 可选评论；提交后展示统计（`approval_rate`）；历史可查可撤回。
2. **密码重置流程**：登录页「忘记密码」→ 邮箱 → reset 页（带 `token`）→ 设新密码。
3. **文档可见性 UI**：上传时选 `everyone`/`admin_only`；详情/列表可改。
4. **回收站**：删除进回收站；回收站列表可恢复/永久删；空态/错态设计（企业态须可理解、可追责）。
5. **API Key 面板**：生成/复制/吊销（Key 仅展示一次）。
6. **对话多轮 + 历史**：threads 创建/列表/切换；历史消息含 `citations`。
7. **安全拒绝态 UX**：输入违规走完整 `token`+`done` 流（`citations=[]`），**按普通回答渲染**，无需特殊错误态（无输出侧拦截）。
8. **Agent 审批流**：展示待审批草稿 → adopt（写库+入库）/ cancel（仅翻转状态）。

---

## 4. 已在进行中的前端改动（避免重复劳动）

| 文件/模块 | 状态 | 备注 |
|-----------|------|------|
| `DashboardPage` | 🔧 重构中 | 看板字段须对齐新 `DashboardStatsResponse` |
| `AppShellLayout` | 🔧 已改 | 布局壳 |
| `AppTopbar` | 🔧 已改 | 顶栏（避免与壳冲突，禁止未落地 ⌘K） |
| `use-theme` | 🔧 已改 | 主题 hook |
| `index.css` | 🔧 已改 | 全局样式 token |
| `TrendChart.tsx` | 🗑 已删 | 看板趋势图组件已移除，勿重建 |
| `dashboard` 组件 | 🔧 重组中 | 看板子组件重构 |

> ⚠️ 重做时先复用上述已改模块，不要从零重写造成冲突。

---

## 5. ⚠️ 对齐时必须避开的坑（来自深读）

1. **HyDE 未接入生产**——前端**不要**做 HyDE 开关/展示/调试入口（`generation.py` 仅定义，只被 benchmark 脚本调用）。
2. **`output_safety_check` 已定义但未被调用**——无需特殊错误态渲染安全回复。
3. **`decompose` 双重触发**导致对话首字延迟偏高——前端可加「思考中」态，但逻辑无需改（服务端问题）。
4. **回收站软删在 `documents/trash.py`，不在 `storage/cleaner.py`**——删除文档链路：DB 软删 + 物理删兜底，接口已齐。
5. **登录限流阈值硬编码**（`login_rate_limit.py`：5/15min、20/5min、锁 1m/5m/15m/1h）——前端可展示锁定时长，无法靠配置灰度。
6. **重置 token 无法主动失效**（无状态 JWT 设计）——不提供「撤回重置邮件」能力。
7. **429**：`chat 30/h`、`upload 20/h`——前端做限流提示文案即可，数值以后端为准。

---

## 6. 验收口径（前端重做）

- [ ] 反馈全链路：👍/👎/评论/统计/历史/撤回 均可走通，`message_id` 正确回填
- [ ] 密码重置：forgot → reset（token）流程闭环
- [ ] 文档可见性：上传 + PATCH 生效，列表/详情正确展示
- [ ] 回收站：软删/恢复/永久删 + 列表，错态可理解
- [ ] API Key：生成/吊销，Key 仅展示一次
- [ ] 对话多轮 + 历史 + citations 正确渲染
- [ ] 安全回复按普通回答渲染（无特殊错误态）
- [ ] Agent 审批：adopt/cancel 流程闭环
- [ ] 看板对齐新 `DashboardStatsResponse` 字段
- [ ] 搜索用 `workspace`（非 `kb_id`/`offset`）
