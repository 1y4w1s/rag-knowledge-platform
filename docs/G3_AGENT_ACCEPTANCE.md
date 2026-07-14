# 知岸 — G3 只读 RAG Agent · 手工验收表

> **任务**：G3-4.3（`docs/tasks/discovery-agent-g3-read-plan.md` Wave 4）  
> **版本**：v1.0  
> **状态**：✅ **脚本就绪**（2026-07-10 · G3-4.2 golden 15/15 runner 绿）  
> **用途**：浏览器跟着点，验收 **快速 / 精准两档 · tool 时间线 · budget · G2 回归**；与 `preview-agent-platform.html` **v4.1** S3～S5 · plan **§8 S/E** 对齐 · plan **§3.1 五步法**  
> **账号**：与 [`TEST_ACCOUNTS.md`](TEST_ACCOUNTS.md) 一致（`demo_admin` · `demo_member`）

---

## 1. 这表验收什么（30 秒）

对话页顶栏新增 **「快速 / 精准」** 开关（工程 `mode=fast|thorough`）。**默认快速** = 现网 G1 单次检索，**无** tool 时间线；切 **精准** 后最多 **5 步只读 tool**，SSE 展示折叠时间线与 **budget-chip**（如 `2/5 步`），**引用 chip 仍在文字前面**（R4-4）。刷新后正文与 citation 在，**不**还原 tool 时间线（H3-2-B）。

**G3 主线**：S3 快速无时间线 → S4 精准有时间线 → S5 手动切模式 → E 边界 → A 层 pytest/golden。

**预览对标**：打开 [`preview-agent-platform.html`](preview-agent-platform.html) 点 **S3 / S4 / S5 / E-budget / E-M / E-empty** 对照 UI 预期。

---

## 2. 验收前准备（不计入勾选）

### 2.1 环境

```powershell
cd D:\MyPrograms\rag-knowledge-platform
docker compose up -d
docker compose exec api alembic current   # 期望：021 (head)
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

**推荐 A**：已跑过 [`G2_THREADS_ACCEPTANCE.md`](G2_THREADS_ACCEPTANCE.md) **S 8/8** 或 [`G1_ASK_ACCEPTANCE.md`](G1_ASK_ACCEPTANCE.md) **S 主线** — 含可问「年假」的库与 grant。

**最小 B**（未跑 G1/G2 时）：

1. `demo_admin` · 团队 · 建库「答辩演示库」· 上传 `backend/tests/fixtures/golden_handbook.md`  
2. 侧栏 **对话** → `/ask` · 左侧 ≥1 条 thread · 顶栏见 **快速 / 精准** 切换

### 2.4 pytest 基线（开工前 1 分钟 · A 层）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
py -3.11 -m pytest tests/test_agent_*.py tests/test_retrieval_golden.py -q
py -3.11 -m pytest tests/test_agent_golden.py -q
```

```powershell
cd D:\MyPrograms\rag-knowledge-platform\frontend
npm run build
npm run test -- thread-stream-abort
```

期望：`test_agent_*` 全绿 · golden_agent **15/15** · retrieval golden **12/12** · build + G3-E1 abort 单测绿。

---

## 3. 正常用例 S（主流程 · 可勾选）

> **用法**：做完一步勾一步。  
> **G3 新增** = S3～S5 · **G2 回归** = S1/S2/S6/S7/S8（Implement 不得破坏）。  
> **对应 plan §3.1 五步法**：步 1 = S3 · 步 2 = S4 · 步 3 = E-budget（§4）· 步 4 = S5 · 步 5 = §5 A 层。

### S · G3 Agent 主线（对齐 preview v4.1 S3～S5）

- [ ] **S3** · `demo_admin` · 团队 · `/ask` · 确认顶栏 **默认「快速」** 高亮 · 问 **「年假有多少天？」** → **流式出字 + citation chip** · **无** Tool 时间线折叠条 · **无** budget-chip 步数（快速等价 1 步检索）
- [ ] **S4** · 同 thread 或新建 · 切 **「精准」** · 问 **「年假和餐补分别是什么标准？」**（或任意跨主题题）→ **出现 Tool 时间线**（如「列库 → 语义检索 → …」）· budget-chip 显示 **1/5～5/5** 随步更新 · **仍有 citation** · citation **先于** 正文流式出现
- [ ] **S5** · 先 **快速** 问一句（无时间线）→ 再切 **精准** 问一句 → **仅精准回答下方** 出现时间线 · **不会** 因问题变复杂而自动升精准（HA-4-A）· 发送中切模式 → 当前流 **停止** · 输入框草稿 **恢复**（G3-E1 · 对标 preview S5）

### S · G2 回归（G3-3.4 不得破坏 · 对标 preview S1/S2/S6/S7/S8）

- [ ] **S1** · 桌面宽屏 · 左侧 thread 列表 **常显**（≈260px）· 点列表项可切换 · 默认仍为 **快速** 模式
- [ ] **S2** · 点 **「+ 新建对话」** → 列表多一行 · 中间消息区空 · 旧 thread 仍在
- [ ] **S6** · 进任一库详情 → **开始对话** → 同样有 **快速/精准** 切换 · 问一句有回答 · chip **无库名前缀**（库内单库规则不变）
- [ ] **S7** · 工作区 `/ask` · 消息较多时向下滚 → **输入框 sticky 贴底**
- [ ] **S8** · 宽度 **≤375px** · 顶栏 **「历史」** 开 drawer · 可选 thread · Agent 切换仍可用

### S · golden 抽检（G3-4.2 · S-agent）

> 浏览器不必跑满 15 题；**A6** 已 CI 挡。此处抽 3 类各 1 条，确认与 `golden_agent_qa.json` 行为一致。

- [ ] **S-agent-1** · **multi_step** · 精准 · 库内问 **「迟到怎么处理？」** → 时间线 ≥2 步 · 有 citation · 章节含 **「1.2 迟到」** 类 chip
- [ ] **S-agent-2** · **refusal** · 精准 · 库内问 **「火星殖民计划进展如何？」** → **无 citation** · 拒答话术（资料不足类）
- [ ] **S-agent-3** · **forbidden_kb** · 精准 · 若可构造：Member 对 **无 grant 库** 相关内容提问 → 时间线某步 **失败/红** 或最终拒答 · **不** 500（越权被截断 · G3-E2）

**G3 S 主线通过 = S3～S5 全勾** · **G2 回归建议 S1/S2/S6 至少勾** · **S-agent 建议 3 类各勾 1**

---

## 4. 乱操作 / 边界 E（可勾选）

> 来源：plan **§8.2** · research **§4.1～§4.2** · preview **E-budget / E-M / E-empty**。可与 §3 穿插测。

### E · 预览继承（G2/G1 · G3 不得破坏）

- [ ] **E1** · 删除某 thread 后再向该 id POST chat → **404**（复用 G2 E2）
- [ ] **E6** · 切换部门 → toast「已切换部门…」· thread 列表按 scope 过滤
- [ ] **E14** · grant 撤销后 · 历史 thread 中对应 chip **灰态 / 来源不可用**

### E · G3 新增边界（plan §8.2 全表）

- [ ] **E-budget** · **精准** · 问复杂跨库题（或多次追问）→ 时间线步数到 **5/5** · budget-chip **warn/变红** · **仍返回答**（基于已有片段 · 不再扩检索）· 对标 preview **E-budget**
- [ ] **E-M** · `demo_member` · 顶栏 **「编辑」** 为 **灰钮 disabled** · 仅 **快速/精准** 可点 · 无写库 POST
- [ ] **E-empty** · 输入框清空 → **发送 disabled** · 不 POST · API 硬闯空 `message` → **422**
- [ ] **G3-E1** · **精准** 发送中 · 切 **快速** 或再切 **精准** → 当前 SSE **Abort** · 无双开流 · 输入草稿恢复 · 可立即再发
- [ ] **G3-E2** · 精准模式 · tool 传越权 `kb_id`（pytest/GAQ-12～15 已挡）· 浏览器侧：Member 无 grant 库内容 **不可** 出现在 citation
- [ ] **G3-E3** · 无可见库账号（未分配 Member）· 精准 POST → **400**「无可用资料库」· 不开 Agent
- [ ] **G3-E4** · 同一用户 1h 内 **快速+精准合计** 发 **31** 次 → 第 31 次 **429**（**不按步数倍乘** · HA-1-A）
- [ ] **G3-E5** · **快速** 模式任意提问 → DevTools EventStream **无** `tool_start` / `tool_result` / `agent_budget`
- [ ] **G3-E6** · 精准 · 空库或无关题（如 S-agent-2）→ **无 citation** · 拒答话术
- [ ] **G3-E7** · 同 thread **连点发送**（上一条仍在生成）→ 第二次 **409**「上一条仍在生成」
- [ ] **G3-E8** · API 硬闯 `mode=edit` → **422** · runtime **仅** 四只读 tool 白名单
- [ ] **G3-E9** · 库内 chat · **精准** → tool 时间线同显 · 默认检索 **当前 kb**（chip 仍无库名前缀）
- [ ] **G3-E10** · Admin **无法** 通过 API 读到他人 agent 问题正文 · audit 仅 metadata（无 query 全文）

**E 建议最少勾**：**E-budget · E-M · E-empty · G3-E1 · G3-E5 · G3-E7**（其余可由 A 层 pytest 覆盖）

---

## 5. 自动化门槛 A（AI 已跑 · 你确认绿即可）

| # | 项 | 命令 | 期望 | 勾选 |
|---|-----|------|------|------|
| **A1** | Agent 单测全集 | `py -3.11 -m pytest tests/test_agent_*.py -q` | 绿 | - [ ] |
| **A2** | G3 边界 + SSE 序 | 含于 A1 · `test_agent_g3_boundaries.py` | G3-E1/E2/E6 · E-budget · §3.3 序 | - [ ] |
| **A3** | dispatch / 409 / 限流 | `test_agent_thread_dispatch.py` · `test_agent_thread_generation_lock.py` | G3-E3～E7 | - [ ] |
| **A4** | Agent audit | `test_agent_audit.py` | G3-E10 · 无 query 全文 | - [ ] |
| **A5** | retrieval golden | `py -3.11 -m pytest tests/test_retrieval_golden.py -q` | **12/12** | - [ ] |
| **A6** | agent golden | `py -3.11 -m pytest tests/test_agent_golden.py -q` | **15/15** · multi_step/refusal/forbidden_kb | - [ ] |
| **A7** | R4-4 SSE | `test_r4_4_streaming.py`（agent 扩展用例） | citation 先于 token | - [ ] |
| **A8** | 前端 build | `cd frontend; npm run build` | 绿 | - [ ] |
| **A9** | G3-E1 abort 单测 | `cd frontend; npm run test -- thread-stream-abort` | rollback + AbortController 绿 | - [ ] |

---

## 6. Plan §3.1 五步法 / §8 对照

| plan §3.1 最小验收集 | 本表 |
|---------------------|------|
| 步 1 · `/ask` 默认快速 · 年假 · 无时间线 · 有 citation | §3 **S3** |
| 步 2 · 切精准 · 跨库题 · 时间线 2～5 步 · 有 citation | §3 **S4** |
| 步 3 · E-budget 5/5 warn · 仍回答 | §4 **E-budget** |
| 步 4 · 快速/精准 31 次/h → 429 | §4 **G3-E4** |
| 步 5 · test_agent_* + golden 15 + retrieval 12 + build | §5 **A1～A9** |

| plan §8.1 预览 S | 本表 |
|------------------|------|
| S3 快速 · 无时间线 | §3 S3 |
| S4 精准 · tool 时间线 | §3 S4 |
| S5 手动切模式 | §3 S5 |
| S1/S2/S6/S7/S8 G2 回归 | §3 S1/S2/S6/S7/S8 |
| S-agent golden 15 题 | §3 S-agent + §5 A6 |

| plan §8.2 边界 E | 本表 |
|------------------|------|
| E-budget · E-M · E-empty | §4 |
| G3-E1～G3-E10 | §4 |

---

## 7. G3-4.3 退出 DoD

| # | 条件 | 本表 |
|---|------|------|
| G4-3-1 | S 表 **可勾选** · 含 preview **S3～S5** + G2 回归 | §3 |
| G4-3-2 | E 表覆盖 plan **§8 全表** | §4 |
| G4-3-3 | A 层与 G3-4.1 / G3-4.2 一致 | §5 |
| G4-3-4 | 试跑记录可填 | §8 |

---

## 8. 试跑记录（请你亲手跑完再填）

| 项 | 值 |
|----|-----|
| 日期 | |
| 执行人 | |
| 环境 | localhost Docker + `npm run dev` · http://localhost:5173 |
| alembic | **021 (head)** |
| G1/G2 前置已跑 | ☐ 是 ☐ 否（最小 B） |
| S3～S5 通过 | /3 |
| G2 回归 S 通过数 | /5 |
| S-agent 抽检 | /3 |
| E 通过数 | /16（建议最少 6 条） |
| A 层 | ☐ A1～A9 全绿 |
| 失败项 # | |
| 备注 | |

---

## 9. 关联文档

- Plan：`docs/tasks/discovery-agent-g3-read-plan.md` §8 · §9 G3-4.3  
- **TECH**：[`docs/TECH.md`](TECH.md) **TECH-7**（G3-5.1 · Agent 数据流 · §2/§3 SSOT）  
- Research：`docs/tasks/discovery-agent-g3-read-research.md` §4  
- 预览：`docs/previews-gallery.html` v4.1（S3/S4/S5 · E-budget · E-M · E-empty）  
- Golden：`docs/golden_agent_qa.json` · runner `backend/tests/test_agent_golden.py`  
- G2 前置：`docs/G2_THREADS_ACCEPTANCE.md`  
- G1 前置：`docs/G1_ASK_ACCEPTANCE.md`  
- 全模块 BA-FINAL：`docs/BROWSER-MODULE-ACCEPTANCE.md`  
- 进度：`docs/previews-gallery.html` G3 · G3-4.3（G3-5.3 文档关单时同步）

---

## 10. 面试 30 秒（G3-4.3）

「G3 验收表把 preview 的 **快速/精准** 两档落成可勾选 S/E：快速就是现网单次检索、UI 无时间线；精准是最多 5 步只读 tool，SSE 先 tool 块再 citation 再 token，budget-chip 实时显示步数。乱操作重点：**步数触顶仍作答**、越权 kb 被截断、限流仍按 **一次发送** 算、发送中切模式 Abort。自动化用 **15 题 agent golden** 分三类（多步/拒答/越权），检索 golden 12 题继续挡 CI。」
