# AGENTS.md — 睿阁

## 北极星（2026-07-06 起 · 优先级高于旧「答辩/demo」表述）

- **产品名**：**睿阁**（原名「知岸」，2026-07-14 品牌更名；代码目录仍为 `rag-knowledge-platform`，不重命名文件夹）
- **目标**：**企业级知识库 RAG 产品**——团队可协作、可审计、可部署、可长期运营；多格式文档上传 → 结构入库 → hybrid 检索 → **引用溯源对话**。
- **不再以毕设答辩为决策主轴**：`docs/ENTERPRISE_DEMO_SCRIPT.md`、15min 计时、R8 试跑等**仅作回归参考**，不得因为「演示能过」而推迟审计、存储一致、限流、评测闭环等企业项。
- **账号类型**：个人版（单人）/ 企业版（组织 + Owner/Admin + Member）。
- **LLM**：DeepSeek + 阿里云通义千问（Key **仅服务端**）；嵌入模型锁定后勿随意更换（见 `TECH.md` §4.4）。
- **P0 产品底线（不可砍）**：对话**必须**带引用（文档名 + 位置 + 片段）；无依据须明确拒答；**kb_id / workspace 隔离**；Member 只读 + 可对话。

### 企业级对齐 ≠ 无限加功能

| 做 | 不做（PRD §14 / Wave 2+） |
|----|---------------------------|
| 审计、限流、存储一致、状态机、软删/去重（Plan-3E） | 支付、积分、套餐计费 |
| RAG 评测闭环、检索提质（Plan-RAG R2～R5） | **F5 多模态**、复杂 Agent 联网 |
| **Format-F4 扫描 PDF OCR ✅**（[`format-f4-ocr-plan.md`](docs/tasks/format-f4-ocr-plan.md) · F4-1～F4-5 · 2026-07-08） | PNG/JPG 单图 · 对话贴图 OCR · F5 多模态 |
| 生产部署（**HTTP 内网**，见 `enterprise-wave-plan.md` §3；**HTTPS 不做**）、备份、可观测（Wave 6 + 3E-6） | 多租户 SaaS 商业化 · 公网 HTTPS |
| 对话历史 / 多 thread（PRD P1，按 plan 排） | 无引用的「纯聊天」模式 |

**权威 backlog（企业向）**：`kb-pages-polish-plan.md` **Plan-3E** · `docs/TECH.md` **TECH-SEC P1** · `rag-optimization-plan.md` **R2～R5** · `002-plan.md` **Wave 6** · PRD **P1** 节。

## 当前阶段

| 项 | 状态 |
|----|------|
| **MVP 功能面** | ✅ Wave 0～5 + workspace W1～W5+；RAG 主链路 + 九页 + 企业 RBAC |
| **企业化下一波** | ✅ 阶段 A/B/C/D/E · **EW-D1～D6 ✅** · **R1 ✅** · **R2 ✅** · **R3-1 ✅** · **R3-2 ✅** · **R3-3 Research ✅（不 Implement）** · **R3-4 ✅** · **R4-1 ✅** · **R4-2 ✅** · **R4-3 ✅** · **R4-4 ✅** · **R5-1 ✅** · **R5-2 ✅** · **R5-3 ✅** · **R5-4 ✅** · **Plan-3E-6 ✅** |
| **驾驶舱 / 旧 plan 文案** | 可能仍写「答辩 / R8」；**以本节北极星为准**，文档漂移时先 B 类对齐索引 |

### 企业优先级（新任务默认参照，非强制一次做完）

1. **可运营 / 可追责**：Plan-3E-4 存储清盘 → 3E-1 审计落库 → 3E-2 删文档状态机 → 3E-3 引用失效 UX  
2. **可上线**：Wave 6 **内网 HTTP** 部署（无 TLS）+ 环境/迁移/健康检查；TECH-SEC P1 登录限流 + API rate limit  
3. **RAG 可证明**：Plan-RAG R5 golden 扩题 + Hit@3 基线；R3 rerank 评估；对话多轮/历史（PRD P1）  
4. **发现层**：Plan-10 / R1 跨库搜 — **EW-E1 ✅** · **R1-2 ✅** · **EW-E2 ✅** 单库分页 · **R1-4 ✅** 详情高级筛选  
5. **体验抛光**：DESIGN 对齐、R6 视觉债——**不抢** 1～3 的企业 P0

## 协作硬约束

1. 一个对话只做一个极小任务（对应 plan 里**一条**原子任务）。
2. 动手前必读：`docs/PRD.md`、`docs/TECH.md`、`docs/tasks/*-plan.md`；**企业向任务**须对照 Plan-3E / TECH-SEC P1 / Plan-RAG，不单看 002-plan MVP 勾。
3. 改功能 / 库 / 权限 / 审计 → 同步 PRD、TECH、plan、驾驶舱 HTML。
4. 不擅自扩展：支付、积分等 **Wave 2+**（见 PRD §14）。
5. **分步确认**（根目录 `CLAUDE.md`）；完整版落盘 `docs/`。
6. 只讨论睿阁；禁止提及其他无关项目。
7. **安全默认企业思维**：新接口先想隔离、审计点、幂等、错态；MVP 档过了不算「企业完成」。
8. **TECH 须含大白话表**；用户是产品负责人，不是背术语的实习生。
9. **单文件长度**：见下节；**≥400 行必须先 plan 拆分**。

## 单文件长度与目录（睿阁专用）

> 跨项目总则见根目录 `CLAUDE.md`「单文件长度控制」。TECH-6 目录约定见 `docs/TECH.md` §6.1。

| 路径 | 职责 | 软上限 |
|------|------|--------|
| `backend/app/api/*.py` | 路由：接请求、调 service，不写 RAG 细节 | ≤200 行 |
| `backend/app/services/**/*.py` | 业务：入库、切片、检索、权限 | ≤300 行 |
| `backend/app/models/*.py`、`schemas/*.py` | 表模型 / Pydantic | ≤250 行 |
| `backend/tests/test_*.py` | 按场景拆分（permissions / golden / upload） | ≤400 行 |
| `frontend/src/pages/**/*.tsx` | 一主路由一文件 | ≤200 行 |

**拆分示例**：RAG → `api/chat.py` + `services/rag/*`；入库 → `ingestion/parser|chunker|embedder`；存储 → `services/storage/cleaner.py`（Plan-3E-4）。

**AI 完工汇报须附**：改动文件清单 + 行数；≥300 行须说明为何不拆。

## 安全与合规（企业档）

> 完整策略：`docs/TECH.md` **TECH-SEC**

| 档 | 内容 | 状态 |
|----|------|------|
| **MVP（已做）** | JWT、RBAC、kb_id 隔离、上传白名单、Key 仅服务端、SA-1～3 | ✅ |
| **P1 企业化（下一波）** | `audit_logs`、登录失败限流、API rate limit、删库/删文档存储一致、ingestion 可观测 | 🟡 Plan-3E + TECH-SEC |
| **Wave 2+** | 备份策略、数据保留期、删账号级联 | 📋 PRD 后续 |

**AI 行为**：用户说「能 demo 就行」→ 拦；改 RAG/权限/删除链路 → 提醒审计点与 pytest，不单说 build 绿。

## 技术方向

- **栈**：FastAPI + **PostgreSQL/pgvector** + React；BackgroundTasks（见 `TECH.md`）
- **RAG**：结构优先切片 + **hybrid RRF**；提质走 Plan-RAG，不以 mock 测试绿代替生产抽测
- **部署**：Docker Compose → **Wave 6 生产态**（HTTPS、密钥、迁移、健康检查）

## 当前资产（基线）

| 项 | 状态 |
|----|------|
| PRD | ✅ v0.1（P1 节 = 企业 backlog） |
| TECH | ✅ TECH-1～6 + TECH-SEC |
| 开发清单 | ✅ `002-plan.md`（MVP + **Wave 6.1～6.4 ✅** 2026-07-07） |
| 驾驶舱 | ✅ `docs/cockpit.html`（与 002-plan Wave 6 对齐；§8 ①15min 计时仍须用户亲手） |
| 代码基线 | Wave 0～5、workspace、Plan-11/2.x 权限 UX、RAG Wave 3、对话 Wave 5.2 |
| UI | ✅ `DESIGN.md` + preview token；企业态仍要过 AGENTS UI 硬约束 |

## UI/UX 硬约束（2026-07-04 起）

> **企业产品观感**：deliberate product，非 AI 模板堆组件；功能能跑不够。

**Implement 前（动前端必过）**

| 检查 | 标准 |
|------|------|
| **依据** | `DESIGN.md` + `design-preview.html`；禁止未落地顶栏 ⌘K 等与壳冲突 |
| **层级** | 顶栏 = 导航；筛选/搜索进内容区 |
| **反模板** | 禁止万能居中空态、cold zinc 系统红、emoji 风插画 |
| **气质** | L5 暖白 + E6 暖褐 + F4 衬线；全站同一套 token |
| **细节** | 4/8 间距；focus/hover；空态/错态/加载态都要设计 |
| **企业态** | 权限拒绝、审计相关、引用失效等错态须**可理解、可追责**，不许裸 `Not Found` |

## 验收口径（企业向）

| 类型 | 通过标准 |
|------|----------|
| **功能** | plan DoD + pytest **A 层** · smoke 建议 · **BA-FINAL** 全模块见 `BROWSER-MODULE-ACCEPTANCE.md` + master-plan §9 |
| **RAG** | 改 `services/rag|ingestion|retrieval` → **必须先** CI job **`R5-2 golden Hit@3 gate`** 绿（`test_retrieval_golden.py` 12/12）；关键题人工抽测（R5-3） |
| **安全/权限** | 跨库 403、member 写操作 403、审计事件可查（3E 落地后） |
| **部署** | 外网 HTTPS 可访问；`/health` database ok |
| **不再单独过关** | 「15min 脚本计时」「答辩口播背稿」——可作为回归，不作延期企业项的理由 |

## 踩坑区

> **跨项目通用坑**（PowerShell 命令、端口、流程）：[`../docs/process/PITFALLS.md`](../docs/process/PITFALLS.md) · 新坑优先写项目特有，通用坑写分册。

- **Docker API 改后端后须 rebuild（2026-07-04）**：`docker compose build api && docker compose up -d api`；验收 OpenAPI 含新路由。
- **详情页文档列表可能过期（2026-07-04）**：轮询停后列表可过期；DELETE/重试 404 → refetch 自愈；focus 同步。删/重试逻辑须对称（见 R5-S1）。
- **只读审查 vs 修复须分对话（2026-07-04）**：审窗只出 gap；修复另开 I 窗。
- **Plan 1.6 空库 + `?status=`（2026-07-04）**：空库勿叠 onboarding；见 `kb-pages-polish-plan.md` Plan-6。
- **测试嵌入 ≠ 生产嵌入（2026-07-06）**：`test_retrieval_golden` 用 mock 向量；**企业验收**须用真嵌入 + 真 DeepSeek 抽测 golden 题，不能只看 CI 绿。
- **对话是「单轮问答」不是「多轮记忆」（2026-07-06）**：MVP 每问独立检索；多轮上下文 + 历史 UI 在 PRD P1，企业化须单独 plan，勿假设已实现。
- **删库清盘（EW-A1 ✅ 2026-07-06）**：`services/storage/cleaner.py` · 删库后调 `remove_kb_tree`；清盘失败只打日志不挡 DB 删。
- **详情页 `n is not iterable`（2026-07-07）**：ORG-4.3 共享面板/grants API 若 `items` 缺失会把 state 设成非数组，展开面板或 `for…of` 时白屏。`asGrantList`/`asUnitList` + `buildDepartmentTree`/`normalizeDocumentListFilters` 兜底；改前端后须 `npm run build` 并 rebuild `web` 容器。
- **浏览器验收 UX gap（2026-07-08）**：① ~~对话页 `ChatPage` 用 `min-h` 非固定高度，输入框随 `main` 滚动下沉（UX-1）~~ **UX-1 ✅**（2026-07-09）；② ~~预览/对话异步 `setOverride` 导致回概览顶栏仍显示资料库路径（UX-2）~~ **UX-2 ✅**（2026-07-09）；③ ~~预览页头像「退出登录」与右栏文档信息叠层（UX-3）~~ **UX-3 ✅**（2026-07-09）；④ ~~member 乱操作 toast 仅库详情灰按钮有、列表/概览/硬闯 URL 反馈弱（UX-4）~~ **UX-4 ✅**（2026-07-09）；⑤ ~~组织页建部门后 picker 须 F5（UX-6）~~ **UX-6 ✅**（2026-07-09）；⑥ ~~公司 Admin 切具体部门无效~~ **UX-7 ✅**（2026-07-09）；⑦ ~~切部门强制跳概览~~ **UX-8 ✅** 留当前页 + toast（2026-07-09）。详见 `docs/cockpit.html` UX backlog。
- **库内对话「当前资料库」下拉错位（2026-07-09）**：`ChatPage` 拉库列表须带 `department_id` scope（与 `/ask` 一致）；当前库不在列表时 `<select>` 会显示第一项名称 · `withCurrentKnowledgeBase()` 兜底。
