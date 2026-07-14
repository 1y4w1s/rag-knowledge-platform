# 知岸（rag-knowledge-platform）前后端工程评分报告

> 评估对象：`frontend/`（React 19 + TypeScript + Vite）、`backend/`（FastAPI + PostgreSQL/pgvector）
> 评估时间：2026-07-14
> 评分尺度：满分 10.0 分（10.0 = 业界标杆；8.0–8.9 = 良好；7.0–7.9 = 可接受/需改进；<7.0 = 明显短板）
> 评估方法：基于业界通用工程评估框架的维度，**非自行编造**。参考框架——
> - 代码质量 / 可维护性：SonarQube / SQALE 质量模型、Google Style Guide、Clean Architecture / SOLID
> - 安全：OWASP Top 10、OWASP ASVS
> - 性能：Web Vitals、RAIL 模型
> - API：Richardson 成熟度模型、Microsoft REST API Guidelines
> - 数据库：关系型/向量库设计通则、pgvector 官方建议
> - 扩展/高可用：12-Factor App、无状态/水平扩展原则
> - 测试：测试金字塔（单元 / 集成 / 端到端）、覆盖率门禁
>
> 所有评分依据均来自实际代码证据（文件路径 + 行号），由只读代码审查得出，未改动任何文件。

---

## 一、前端评分

| # | 维度（业界标准来源） | 分值 | 关键依据摘要 |
|---|----------------------|------|--------------|
| 1 | 代码质量与规范性（SonarQube/SQALE、Google Style Guide） | **8.5** | `tsconfig.app.json` 开启 `strict`/`noUnusedLocals` 等；全仓仅 1 处 `as any`；零 `console.log`、零 `TODO/FIXME`。**缺 ESLint/Prettier 门禁**（`package.json` 无 `lint` 脚本）。 |
| 2 | 组件化与可复用性（组件化评估通则） | **8.5** | `components/ui/` 基础组件库 + 场景化空态；按特性域清晰分层；逻辑下沉到 `use-*` hooks。但 `authHeaders()` 在 5 个 api 文件重复定义、HTTP 封装未统一。 |
| 3 | 性能优化：加载速度 / 渲染效率（Web Vitals、RAIL） | **8.0** | 路由级 `lazy()`+`Suspense`（`routes/index.tsx:19-66`）；Vite 手动拆 `react-vendor`/`vendor`（`vite.config.ts:81-94`）；`useMemo/useCallback` 广泛使用。但**无统一请求缓存/去重层**（无 React Query/SWR），防抖为各组件自实现。 |
| 4 | 可维护性与可扩展性（可维护性模型） | **8.0** | 特性化目录、状态走 Context；页面 130–371 行且逻辑已抽 hooks，可接受。但 `API_BASE="/api/v1"` 在 ~11 个文件重复；个别内联 hex 色值（`routes/index.tsx:104/149`）与 CSS 变量令牌不一致。 |
| 5 | 用户体验与交互设计（可用性 / a11y） | **8.5** | 加载/空/错误态覆盖充分（骨架屏、统一 `EmptyState`、`RouteFallback` 带 `role="status" aria-live`）；表单校验体系完整；`aria-*` 覆盖 83 个文件；移动端抽屉式导航。设计令牌仍偶有内联 hex 瑕疵。 |
| 6 | 安全性：XSS 防护等（OWASP Top 10 / ASVS） | **7.5** | **零 `dangerouslySetInnerHTML`、零 `eval`**；搜索高亮改用安全解析器 `renderHeadline`（`SearchSnippet.tsx:17-51`）；生产 CSP 严格（`vite.config.ts:9-16`）。**红标**：`access_token` 存于 `localStorage`（`auth-storage.ts:22/36`），存在 XSS 盗令风险，企业级宜改 httpOnly+Secure Cookie。 |
| 7 | 测试与质量保障（测试金字塔 / 覆盖率门禁） | **6.0** | Vitest 已就绪（`vite.config.ts:60-64`）；共 11 个测试文件，覆盖叶子组件与工具。但**登录/对话/知识库 CRUD 等关键主流程无集成/页面级测试**，未设覆盖率阈值。 |

**前端综合评分（算术平均）：7.9 / 10 —— 良好，可用性/类型安全突出，测试与安全令牌处理为最优先改进项。**

---

## 二、后端评分

| # | 维度（业界标准来源） | 分值 | 关键依据摘要 |
|---|----------------------|------|--------------|
| 1 | 架构设计与分层合理性（Clean Architecture / 分层） | **9.0** | 四层结构 `api/services/models/schemas` + `core`；`main.py:48-82` 仅装配无业务；路由极薄（`knowledge_bases.py:35-107`）；业务与 HTTP 解耦（service 抛领域异常）。 |
| 2 | API 设计与规范性（Richardson / MS REST Guidelines） | **8.5** | 统一 `prefix="/api/v1"`；统一错误形状由 `exception_handlers.py` 接管；Pydantic 请求/响应分离；分页 `limit/offset` 且 `limit le=100`；自带 OpenAPI。少量 api 文件仍直接 `raise HTTPException`（约 15 处），与约定略不一致。 |
| 3 | 数据库设计与查询效率（关系/向量设计通则） | **9.0** | SQLAlchemy 2.0 异步 + `asyncpg`；`pgvector` 用 `Vector` + **HNSW 索引**（`005_document_chunks.py`）；混合检索（向量 Top-20 + FTS + RRF + rerank）；补 `documents(kb_id)` 索引；stats 子查询避免 N+1。原始 SQL 仅探活/建索引，无拼接。 |
| 4 | 安全性与权限控制（OWASP / RBAC） | **8.5** | JWT 全局中间件（`security.py:86-108`）+ API Key fallback；完善 RBAC（`require_org_role`/`require_owner`）；**kb 隔离双层校验**（路由 + 检索后 `_enforce_kb_scope`，`retrieval.py:177-202`）；登录滑动窗口限流。**红标**：`config.py:31` `jwt_secret` 默认值可运行、`re_embed_token=""`；内部接口仅靠 `X-Re-Embed-Token` 头保护。 |
| 5 | 错误处理与日志机制（可观测性通则） | **8.0** | 领域异常层次完整（`exceptions.py`）；`audit_logs` 表 + `write_audit_log` 审计链路；结构化 `logging.getLogger(__name__)`。**缺显式 catch-all 500 处理器**，未捕获异常走 FastAPI 默认，日志缺结构化上下文。 |
| 6 | 可扩展性与高可用性（12-Factor / 水平扩展） | **7.5** | 全异步、`pool_pre_ping` 连接池、JWT 无状态天然可横扩。**红标**：限流为进程内内存（`login_rate_limit.py` 自承多副本须换 Redis）；`BackgroundTasks` 非持久化（入库/重嵌任务 worker 重启即丢），无 Celery/Redis 队列，**多副本下限流与任务可靠性失效**。 |
| 7 | 代码可维护性（文件/圈复杂度） | **7.5** | 多数 service <200 行、类型提示/docstring 良好、配置集中 `pydantic-settings`。但**超大文件**：`thread_persistence.py` 613 行、`agent/stream.py` 553、`rag/retrieval.py` 515、`chunker.py` 423、`org/scope.py` 409；检索逻辑 KB 与 Workspace 双份平行实现（约 260 行重复）。 |
| 8 | 测试与质量保障（测试金字塔） | **9.0** | `pytest.ini` `asyncio_mode=auto`；`tests/` 90+ 文件；**golden 检索测试**（`test_retrieval_golden.py` Hit@3）；多租户隔离测试（`test_org_kb_access`/`test_retrieval_security` 等）；审计测试；`loadtests/` k6 脚本与基准。 |

**后端综合评分（算术平均）：8.4 / 10 —— 良好偏上，分层/检索/测试达企业级；共享态（限流/任务队列）与默认密钥为最优先改进项。**

---

## 三、综合对比

| 维度 | 前端 | 后端 |
|------|------|------|
| 代码质量 / 规范 | 8.5 | 9.0（架构分层） |
| 组件化 / 架构 | 8.5 | 9.0 |
| 性能 / DB 效率 | 8.0 | 9.0 |
| 可维护性 / 可扩展 | 8.0 | 7.5 |
| 用户体验 / 错误处理 | 8.5 | 8.0 |
| 安全性 / 权限 | 7.5 | 8.5 |
| 测试 | 6.0 | 9.0 |
| **综合** | **7.9** | **8.4** |

**总体结论**：后端成熟度整体高于前端。后端在架构分层、混合检索、多租户隔离、测试覆盖上已达企业级；前端在类型安全、组件化、交互态/可访问性上也属良好，但**测试覆盖与认证令牌存储**明显弱于后端。两端共同的核心短板是**「进程内共享状态」**（前端无请求缓存层、后端限流/任务队列在内存），在水平扩展与一致性上存在隐患。

---

## 四、改进建议（按优先级）

### P0 — 安全与可靠性（上线前必改）
1. **前端认证令牌存储**（`frontend/src/lib/auth-storage.ts:22/36`）：将 `access_token` 由 `localStorage` 改为 **httpOnly + Secure + SameSite Cookie**（由后端 `Set-Cookie` 下发），彻底消除 XSS 盗令面。生产 CSP 仅作缓解，非根治。
2. **后端默认密钥强制化**（`backend/app/core/config.py:31,42`）：生产环境若未显式覆盖 `jwt_secret` / `re_embed_token`，启动即 **fail-fast 拒绝**；并接入密钥管理服务（如 Vault / KMS），禁止仓库默认值可运行。
3. **后端限流/任务队列外置**：将登录限流、API 限流、入库/重嵌任务迁移到 **Redis + Celery/ARQ**（与 AGENTS.md 中 TECH-SEC P1、Plan-3E 一致），消除多副本下限流失效与任务丢失。

### P1 — 工程化门禁与一致性
4. **前端补 ESLint + Prettier 门禁**：加 `.eslintrc`/`.prettierrc` 并接入 `lint` 脚本与 CI，补齐缺失的质量自动化闸门。
5. **统一 HTTP 封装**（`frontend/src/lib/`）：抽出单一 `http.ts`，收敛 `authHeaders()`（×5）、`API_BASE`（×11）、`authFetch`（未共享）重复，统一 baseURL / Bearer / 错误归一化 / stale-scope 处理。
6. **后端补全 catch-all 500 处理器**（`exception_handlers.py`）：注册全局 `Exception` 处理器，输出结构化错误日志与统一响应体，避免 FastAPI 默认 500 丢失上下文。

### P2 — 可维护性深化
7. **大文件拆分**（后端）：`thread_persistence.py`(613) / `agent/stream.py`(553) / `rag/retrieval.py`(515) / `chunker.py`(423) / `org/scope.py`(409) 按职责拆分为 <300 行模块（遵循 AGENTS.md 单文件软上限）。
8. **检索逻辑去重**（`rag/retrieval.py`）：KB 与 Workspace 两套向量召回抽公共 `_vector_recall(scope)`，消除约 260 行平行实现。
9. **设计令牌一致性**（前端）：清理 `routes/index.tsx:104/149` 等内联 hex，统一走 `index.css` CSS 变量 + Tailwind 主题。

### P3 — 测试补强
10. **前端关键路径集成测试**：为登录、注册、发消息、知识库 CRUD 补 Testing Library 页面级用例，并设置 **coverage 阈值**（与后端 pytest 体系对齐）。
11. **统一防抖/请求缓存工具**（前端）：引入轻量 `useDebounce` hook 与可选的 React Query/SWR，收敛各组件自实现 `setTimeout` 防抖、减少路由切换重复拉取。

---

### 评估说明
- 评分基于**可静态/代码层面核实**的证据；运行时指标（真实 TTFB、并发上限）需借助 `loadtests/` 已有 k6 脚本与线上监控补充。
- 本报告为只读审查产物，未修改任何源码。最优先项（P0）与 AGENTS.md 北极星中的「可运营/可追责/可上线」企业 P0 完全一致，建议纳入下一波企业化任务排期。
