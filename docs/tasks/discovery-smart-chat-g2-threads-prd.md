# 发现层 · 企业级对话 thread PRD（G-2）

> **状态**：✅ **P 关** · ✅ **R/L 关**（plan）· ✅ **I 关 G2-0～G2-4.3** · ✅ **G-2 整线**（2026-07-09）  
> **背景**：G-1 `/ask` 验收后用户反馈「新建对话后记录像没了」——G1 MVP 仅前端清 state，无服务端 thread 边界  
> **依赖**：G-1 ✅ · ORG OrgScope · UX-P1 B5 chat 壳层 · Plan：`discovery-smart-chat-g2-threads-plan.md`

---

## 索引

| 节 | 内容 | 状态 |
|----|------|------|
| **G-2-1** | 定位 · thread 语义 · G1 升级 | ✅ 2026-07-08 H2 拍板 |
| **G-2-2** | Thread 列表 · 新建/切换 · 布局 | ✅ 2026-07-08 H2-4 |
| **G-2-3** | `/ask` 与库内 chat 同构 | ✅ H2-5 |
| **G-2-4** | 权限 · 审计 · 乱操作 | ✅ H2-1 · H2-6 · H2-7 |
| **G-2-5** | 验收口径（S/E 摘要） | ✅ `G2_THREADS_ACCEPTANCE.md` · G2-4.3 |

**关联文档**：主 PRD `docs/PRD.md` §5.6 · TECH `docs/TECH.md` **TECH-5.8** · 驾驶舱 `docs/cockpit.html` G-2 区

---

## G-2-1 定位 · thread 语义 · G1 升级 ✅

**这节定什么**：把「对话历史」从 G1 的 **单条连续流** 升级为 **多会话（thread）**；「新建对话」= **服务端新建 thread**，不是只清 React state。

### 与 G-1 对比

| | G-1 MVP | G-2（本交付） |
|--|---------|---------------|
| 新建对话 | 前端 `resetChat()` 清屏 | **POST thread** · 列表多一行 |
| 历史边界 | 同 workspace 下 **全部消息** | **按 thread_id** 加载 |
| 历史 UI | 无列表 | 左侧 **Thread 列表**（260px · 375 drawer） |
| 旧数据 | — | 升级时合并为 **「历史对话」** 默认 thread（H2-2-A） |

### 名词（人话）

| 名词 | 含义 |
|------|------|
| **thread** | 一条独立会话（像微信里一个聊天窗口） |
| **新建对话** | 调 API 建 **空 thread** · 中间消息区空 · **旧会话仍在列表** |
| **历史对话** | G1 旧消息 backfill 时的默认会话标题 |

### 正常流程（S · 摘要）

| # | 用户做什么 | 看见什么 |
|---|------------|----------|
| S1 | 侧栏「对话」→ `/ask` | 左侧 **会话列表** + 中间消息区 |
| S2 | 点 **+ 新建对话** | 列表多一行 · 中间 **空** |
| S3 | 问一句 | 标题自动为首问前若干字 |
| S4 | 点列表里旧会话 | 该 thread **完整问答与引用** 恢复 |
| S5 | F5 刷新 | **当前 thread** 历史仍在 |

### 明确不做

- 多人 **共编** 同一条 thread  
- 对话内 **多轮上下文记忆**（仍每问独立检索）  
- 导出 Word/PDF 会话  
- Admin **查看他人** 对话正文  
- 全文搜索所有历史消息（P2）

---

## G-2-2 Thread 列表 · 新建/切换 · 布局 ✅

### 桌面布局（≥1024）

```
App 侧栏 220px │ Thread 列表 260px │ 消息区 + sticky 输入
```

### 375 移动

- Thread 列表 → 顶栏 **「历史」** 按钮开 **抽屉**
- 输入区 **始终 sticky**（UX-1 · G2-3.2）

### 关键交互

| 元素 | 行为 |
|------|------|
| Thread 列表 | 按 **last_message_at** 倒序 · **今天 / 昨天 / 更早** 分组 |
| **+ 新建对话** | `POST /ask/threads` 或库内 `POST .../threads` → 切到新 thread |
| 点列表项 | `GET .../threads/{id}/messages` → 恢复消息与 citation 灰态 |
| 会话标题 | 首问自动截断（约 40 字）· 可 **PATCH** 改名 |
| 删除/归档 | 用户可 **软删自己的 thread**（H2-7-A · `status=archived`） |
| 空/加载/错态 | 统一 `ChatEmptyPanel` / `ChatLoadingPanel`（G2-3.3 · DESIGN-6） |

### 与 PRD §5.6 对齐

主 PRD **§5.6 对话页**「新建对话」行已更新为：**POST thread + 切换**，不再写「仅前端清空」。

---

## G-2-3 `/ask` 与库内 chat 同构 ✅

**这节定什么**：工作区 `/ask` 与库内 `/knowledge-bases/:id/chat` 使用 **同一套** `ThreadListPanel` + `use-thread-session`；仅 **数据源 API 前缀** 不同。

| 维度 | 工作区 `/ask` | 库内 `.../chat` |
|------|---------------|-----------------|
| Thread API | `/api/v1/ask/threads` | `/api/v1/knowledge-bases/{kb_id}/threads` |
| 发消息 SSE | `POST .../threads/{id}/chat` | 同构 |
| 列表 scope | user + workspace + department | user + kb_id |
| 引用 chip | **带库名**（G-1） | **不带库名** |
| 检索 | 跨 visible 库 | 单库 |

**库详情「开始对话」**：进入后同样见左侧 thread 列表；chip 规则 **不变**（S6 仍过）。

---

## G-2-4 权限 · 审计 · 乱操作 ✅

### 归属（H2-1-A）

| 规则 | 说明 |
|------|------|
| thread **仅本人可见** | 列表/消息 API 按 `user_id` 过滤 |
| Admin | 只看 **统计/审计元数据**，**无** 他人正文 API |

### 切部门（H2-6-A）

| 行为 | 说明 |
|------|------|
| thread 绑 **创建时** `workspace_department_key` | 列表 scope 过滤 Implement 已定 |
| 切部门后 | 旧 thread **仍在列表** · 旧引用可能 **灰态**（E14 已有） |

### 审计（不含用户原文）

| 事件 | action | metadata 示例 |
|------|--------|---------------|
| 新建 thread | `chat.thread_created` | thread_id, thread_kind, workspace, kb_id |
| 发送消息 | `chat.message_sent` | thread_id, citation_count, retrieval_ms · **不含** question 全文 |
| 归档 thread | `chat.thread_archived` | thread_id |

### 乱操作（E · 摘要）

| 乱操作 | 系统怎么处理 | 你怎么验 |
|--------|--------------|----------|
| E1 访问他人 thread_id | **404** | 改 URL id |
| E2 归档后再发消息 | **404** | 删会话后发 |
| E3 未分配 Member `/ask` | **禁用** + Banner（ORG-2.5） | member 无部门 |
| E4 撤 grant 后看历史 thread | chip **来源不可用** | E14 回归 |
| E5 连点新建 | 每次 **新 thread** · 旧的不丢 | 连点 + |

---

## G-2-5 验收口径（S/E 摘要）

> **完整可勾选表**：[`G2_THREADS_ACCEPTANCE.md`](../G2_THREADS_ACCEPTANCE.md) · G2-4.3 ✅ · Plan §3.1 五步法

### 浏览器最小集（Plan §3.1）

1. `/ask` 左侧见列表 · **+ 新建** → 中间空 · 列表多一行  
2. 问一句 → 标题变 · 切旧会话 → 问答完整  
3. 库内 **开始对话** → 同样列表 · chip **无库名**  
4. 刷新 → 当前会话还在  
5. `pytest` 全绿 · golden 12/12 · `npm run build` 绿  

### 自动化门槛（A 层）

| # | 项 | 预期 |
|---|-----|------|
| A1 | thread CRUD pytest | `test_ask_threads.py` · `test_kb_threads.py` 绿 |
| A2 | thread chat SSE + 落库 `thread_id` | T-thread-5～6 绿 |
| A3 | audit 事件 | `test_chat_audit_events.py` 绿 |
| A4 | golden 12/12（G2 默认 **不动** retrieval） | CI 绿 |

### P 关 DoD（G2-4.1）

| # | 条件 | 状态 |
|---|------|------|
| P1 | G-2-1～G-2-4 与 plan H2 拍板一致 | ✅ |
| P2 | 全文落盘本文 | ✅ 2026-07-09 |
| P3 | 主 PRD §5.6 + P1 索引 · TECH-5.8 索引 | ✅ G2-4.1 |

---

## 文档关单（G2-4 · ✅ 2026-07-09）

- **G2-4.1** ✅ PRD G-2-x · TECH-5.8  
- **G2-4.2** ✅ cockpit · master-plan SSOT  
- **G2-4.3** ✅ [`G2_THREADS_ACCEPTANCE.md`](../G2_THREADS_ACCEPTANCE.md) S/E 可勾选 · 待用户试跑 §8
