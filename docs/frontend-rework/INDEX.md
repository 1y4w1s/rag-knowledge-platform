# 前端重做技术参考包 · 索引

> **产品**：睿阁（企业级知识库 RAG）· **基线**：后端未提交改动 + 近期 feature commit（截至 2026-07-15）
> **目标**：为前端重做铺垫——同步后端最新架构、契约与功能范围，所有产出物在此串联。

---

## 一、阅读顺序

```
1. 本索引（你在这）            → 建立全局认知
2. 04 范围清单                 → 前端要做什么（接口/数据结构/功能/避坑）
3. API_FRONTEND_REFERENCE.md   → 逐接口字段契约（已订正 6 处 + 补 Agent 章）
4. 00 后端改动盘点             → 事实源（为什么这么定，附 file:line 铁证）
5. 01 知识图谱（HTML）         → ER / 数据流 / 模块依赖三图
6. 03 架构图（HTML）           → 系统架构 / 模块划分 / 部署拓扑三图
```

---

## 二、文件清单

| 文件 | 形式 | 用途 | 关键内容 |
|------|------|------|----------|
| [`API_FRONTEND_REFERENCE.md`](../API_FRONTEND_REFERENCE.md) | Markdown | **前端对接唯一契约源** | 全量端点 + 请求/响应 + SSE 协议；已订正搜索参数、workspace 枚举、上传 visibility、上传响应键名、看板字段，并补 Agent 审批章 |
| [`00-backend-change-inventory.md`](00-backend-change-inventory.md) | Markdown | 事实源 | 后端改动全量盘点（🆕/🔧/🗑）、7 条关键契约事实、未接线/死代码清单 |
| [`01-knowledge-graph.html`](01-knowledge-graph.html) | 交互式 HTML | 知识图谱 | ① 实体关系图（含 chat_feedback 新实体）② 数据流图（含 OCR/可见性→hybrid检索→生成→反馈回流）③ 模块依赖图 |
| [`03-architecture.html`](03-architecture.html) | 交互式 HTML | 架构图 | ① 系统架构（内网 HTTP）② 模块划分（含前端待建对接边界）③ 部署拓扑（web/api/db/migrate） |
| [`04-frontend-rework-scope.md`](04-frontend-rework-scope.md) | Markdown | 范围清单 | 需对接接口（P0~P2）、变更数据结构、功能范围、已在进行中改动、避坑、验收口径 |

---

## 三、关键事实速查（不可推翻）

- **SSE 协议**：`citation` / `token` / `done`；`done = { message_id, citations }`；`message_id = ChatMessage.id`（反馈唯一键）。
- **feedback 幂等**：同 `message_id` + `user_id` 重复提交更新 `rating`。
- **429**：`chat 30/h`、`upload 20/h`。
- **上传响应**：顶层键 `documents`，**无 `failed`**。
- **搜索参数**：`workspace`（personal 或组织 UUID），**无 `offset`、无 `kb_id`**。
- **文档可见性枚举**：`everyone` / `admin_only`（非 `team`/`company`）。
- **看板字段重命名**：`kb_count`→`knowledge_base_count` 等（见 `04` §2 / `API_FRONTEND_REFERENCE.md` §八）。
- **密码重置**：无状态 JWT（60min），前端 reset 页只需 `token`。

---

## 四、⚠️ 三大"别误做"

1. **HyDE 未接入生产** → 前端不做 HyDE 开关/展示。
2. **`output_safety_check` 未被调用** → 安全回复按普通回答渲染，无特殊错误态。
3. **`decompose` 双重触发** → 仅延迟偏高，前端无感，加「思考中」态即可。

---

## 五、配套既有文档（非本包产出，存在漂移风险，以本包为准）

- `docs/PRD.md` · `docs/TECH.md` · `docs/cockpit.html` · `docs/AGENTS.md`
- 若上述与本文冲突，**以本包 + 后端源码为准**（本包已逐文件深读核对）。
