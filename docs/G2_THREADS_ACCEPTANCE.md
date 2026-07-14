# 知岸 — 对话 thread 会话历史 · 手工验收表

> **任务**：G2-4.3（`docs/tasks/discovery-smart-chat-g2-threads-plan.md` Wave 4）  
> **版本**：v1.0  
> **状态**：✅ **G2-4.3 关门**（2026-07-09 · S **8/8** · E 5/5 · A 绿 · S3 首问 title 已 Implement + 浏览器复测 ✅）  
> **用途**：浏览器跟着点，验收 **多 thread 列表 · 新建/切换 · 库内同构**；与 `discovery-smart-chat-g2-threads-prd.md` **G-2-5** S/E 对齐 · Plan **§3.1 五步法**  
> **账号**：与 [`TEST_ACCOUNTS.md`](TEST_ACCOUNTS.md) 一致（`demo_admin` · `demo_member`）

---

## 1. 这表验收什么（30 秒）

对话页 **左侧多一列历史会话**；点 **「+ 新建对话」** 会在服务器 **新建一条 thread**（不是只清屏）；旧 G1 问答并进 **「历史对话」** 默认会话，点一下还能找回来；**`/ask` 与库内 chat 同一套操作**（仅 chip 规则不同：工作区带库名 · 库内不带）。

**主线**：thread 列表 → 新建/切换 → 标题自动 → 刷新持久 → 库内同构 → 边界与审计。

---

## 2. 验收前准备（不计入勾选）

### 2.1 环境

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose up -d
docker compose exec api alembic current   # 期望：020 (head)
```

另开终端（dev 模式）：

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run dev
```

| 检查项 | 地址 | 期望 |
|--------|------|------|
| 前端 | http://localhost:5173/login | 登录页正常 |
| API | http://localhost:8000/health | `database: ok` |
| DeepSeek Key | 项目 `.env` 已配置 | 对话能流式返回 |

### 2.2 演示账号

| 角色 | 用户名 | 密码 | 组织 |
|------|--------|------|------|
| **公司 Admin** | `demo_admin` | `password123` | 知岸演示公司 |
| **研发 Member** | `demo_member` | `password123` | 主部门研发部 |

### 2.3 数据前置（二选一）

**推荐 A**：已跑过 [`G1_ASK_ACCEPTANCE.md`](G1_ASK_ACCEPTANCE.md) **S 主线** 或 [`ORG_DEPARTMENTS_ACCEPTANCE.md`](ORG_DEPARTMENTS_ACCEPTANCE.md) **15 步** — 含可问「年假」的库与 grant。

**最小 B**（未跑 G1/ORG 时）：

1. `demo_admin` · 团队 · 建库「答辩演示库」· 上传 `backend/tests/fixtures/golden_handbook.md`  
2. 侧栏 **对话** → 左侧应见 **至少 1 条** 会话（升级后可能叫「历史对话」）

### 2.4 pytest 基线（开工前 1 分钟 · A 层）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_ask_threads.py tests/test_kb_threads.py tests/test_chat_audit_events.py tests/test_retrieval_golden.py -q
```

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run build
```

期望：thread CRUD + audit 绿 · golden **12/12** · `npm run build` 绿。

---

## 3. 正常用例 S（主流程 · 可勾选）

> **用法**：做完一步勾一步；全部 ✅ = G2-4.3 S 关通过。  
> **对应 Plan §3.1 五步法**：S1～S2 = 步 1～2 · S6 = 步 3 · S5 = 步 4 · §5 A 层 = 步 5。

### S · thread 主线（工作区 `/ask`）

- [x] **S1** · `demo_admin` · 团队空间 · 侧栏点 **「对话」** → 地址栏 `/ask` · **左侧见会话列表**（≥1 条，可能含「历史对话」）· 中间消息区
- [x] **S2** · 点 **「+ 新建对话」**（或 toolbar 等价按钮）→ **列表多一行** · 中间消息区 **空** · 旧会话 **仍在列表**
- [x] **S3** · 在新 thread 输入 **「年假有多少天？」** → **流式出字** · 列表里该会话 **标题变** 为首问前几字（非「新对话」占位）— **2026-07-09 复测 ✅ · 列表显示「年假有多少天？ HH:mm」**
- [x] **S4** · 点列表里 **旧会话**（如「历史对话」）→ **完整问答与引用 chip 恢复** · 再点回 S3 新建会话 → 该 thread 问答仍在
- [x] **S5** · 停留在当前 thread · **F5 刷新** → **当前会话历史仍在**（含 chip）

### S · 库内同构 + UX（Plan §3.1 步 3 · G2-3）

- [x] **S6** · 进任一库详情 → **开始对话** → **同样左侧 thread 列表** · 问一句有回答 · chip **无库名前缀**（仅文档/章节 · G-1 S6 仍过）
- [x] **S7** · 工作区 `/ask` · 消息较多时 **向下滚动** → **输入框仍 sticky 贴底**（UX-1 · G2-3.2）
- [x] **S8** · 浏览器宽度 **≤375px**（或 DevTools 手机模式）· 顶栏 **「历史」** → **抽屉** 打开 thread 列表 · 可选中切换

**S 全勾 = 8/8**

---

## 4. 乱操作 / 边界 E（可勾选）

> 可与 §3 穿插测；不必按序号。来源：PRD **G-2-4** 乱操作表。

- [x] **E1** · 记下他人 thread 的 UUID（或随便改 URL 里 thread id）· 调 `GET /api/v1/ask/threads/{id}/messages` 或硬改前端路由 → **404**（不可见他人会话）
- [x] **E2** · 对某 thread **归档/删除**（列表删除或 PATCH archive）· 再向该 thread **发消息** → **404** 或明确不可发
- [x] **E3** · **未分配** Member（`unit_ids=[]`）硬闯 `/ask` → **禁用提问** + **未分配 Banner**（ORG-2.5 · 与 G1 E17 一致）
- [x] **E4** · 完成 S3 后 · `demo_admin` **撤销** 员工手册 grant · `demo_member` 刷新并打开含该引用的旧 thread → 对应 chip **灰态 / 来源不可用**（E14 回归）
- [x] **E5** · 连点 **「+ 新建对话」** 3 次 → 列表 **多 3 条** · 每次中间 **空** · **先前 thread 不丢**

**E 建议至少勾 E3 · E4 · E5 三条**（E1/E2 需 DevTools 或删会话操作）

---

## 5. 自动化门槛 A（AI 已跑 · 你确认绿即可）

| # | 项 | 命令 | 期望 | 勾选 |
|---|-----|------|------|------|
| **A1** | thread CRUD pytest | `pytest tests/test_ask_threads.py tests/test_kb_threads.py -q` | 绿 | - [x] |
| **A2** | thread chat SSE + `thread_id` 落库 | 含于 A1 · `test_ask_threads` T-thread-5～6 | 绿 | - [x] |
| **A3** | audit 事件 | `pytest tests/test_chat_audit_events.py -q` | `chat.thread_created` 等可查 | - [x] |
| **A4** | golden 回归 | `pytest tests/test_retrieval_golden.py -q` | **12/12** | - [x] |
| **A5** | 前端构建 | `cd frontend; npm run build` | 绿 | - [x] |

---

## 6. PRD G-2-5 / Plan §3.1 对照

| 来源 | 本表 |
|------|------|
| Plan §3.1 步 1 | §3 S1～S2 |
| Plan §3.1 步 2 | §3 S3～S4 |
| Plan §3.1 步 3 | §3 S6 |
| Plan §3.1 步 4 | §3 S5 |
| Plan §3.1 步 5 | §5 A1～A5 |
| PRD G-2-1 S1～S5 | §3 S1～S5 |
| PRD G-2-3 库内同构 | §3 S6 |
| PRD G-2-2 sticky / 375 | §3 S7～S8 |
| PRD G-2-4 E1～E5 | §4 |

---

## 7. G2-4.3 退出 DoD

| # | 条件 | 本表 |
|---|------|------|
| G4-3-1 | S 表 **可勾选** · 含 Plan §3.1 五步法 | §3 |
| G4-3-2 | E 表覆盖 PRD G-2-4 边界 | §4 |
| G4-3-3 | A 层与 PRD G-2-5 / TECH-5.8.6 一致 | §5 |
| G4-3-4 | 试跑记录可填 | §8 |

---

## 8. 试跑记录（请你亲手跑完再填）

| 项 | 值 |
|----|-----|
| 日期 | 2026-07-09 |
| 执行人 | 用户 + AI 浏览器联跑 |
| 环境 | localhost Docker + `npm run dev` · `http://localhost:5173` |
| alembic | **020 (head)** |
| G1 S 或 ORG 15 步已跑 | ☑ 是（最小 B + 浏览器测试库 · 员工手册（人事）grant 测 E4） |
| S 通过数 | **8/8** |
| E 通过数 | **5/5** |
| A 层 | ☑ pytest 15/15 thread + audit + golden 12/12 · ☑ build 绿 · **T-thread-7/8 · T-kb-thread-7** |
| 失败项 # | — |
| 备注 | E3 用临时账号 `demo_unassigned_g2`。E4：grant 撤销后 chip 灰态。**S3 fix**：`maybe_autotitle_thread_from_first_message` · 2026-07-09 Docker rebuild + 浏览器复测通过。 |

---

## 9. 关联文档

- PRD：`docs/tasks/discovery-smart-chat-g2-threads-prd.md` G-2-5  
- Plan：`docs/tasks/discovery-smart-chat-g2-threads-plan.md` G2-4.3 · §3.1  
- TECH：`docs/TECH.md` §5.8 · §5.8.6  
- G-1 前置：`docs/G1_ASK_ACCEPTANCE.md`  
- 组织域：`docs/ORG_DEPARTMENTS_ACCEPTANCE.md`  
- 全模块 BA-FINAL：`docs/BROWSER-MODULE-ACCEPTANCE.md` M6/M12  
- 进度：`docs/previews-gallery.html` G-2 · G2-4.3
