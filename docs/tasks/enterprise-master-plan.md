# 知岸 · 企业级总计划（Master Plan）

> **状态**：✅ L 窗 · 用户拍板 **真·企业级路线**（2026-07-08）  
> **答辩**：2027-05 · **WIP=1** · 一次只推进一条原子任务  
> **SSOT 索引**：本文 = 总地图 · 细节见各子 plan（eval-ops / ux-p1 / rag-optimization / kb-pages-polish）

---

## §0 北极星 & 边界

| 做（企业级） | 不做 |
|--------------|------|
| 可运营、可追责、可部署、可证明 RAG、格式可扩展 | 支付 / 积分 / 公网 HTTPS / 多租户 SaaS 计费 |
| Eval-Ops：数据 · 性能 · 成本 · 备份 · SLO | 一次 Implement 改完全站 |
| 格式 F1～F5 分阶段 | F4/F5 与 Eval-Ops P0 抢窗口 |
| UX-P1 **答辩前 3 个月再开**（dashboard V ✅ 保留） | endless 预览抛光 |

---

## §1 已完成基线（不用再排）

| 域 | 已完成 |
|----|--------|
| **MVP 九页 + RBAC + 组织部门** | Wave 0～5 · W1～W5+ · ORG 15/15 |
| **RAG** | hybrid · R1～R5 · golden 12/12 · rerank · **R6 backlog**（外部调研 · §12） |
| **发现层 G-1/G-2** | 工作区 `/ask` 跨库 · **thread 列表/UI ✅** · TECH-5.7/5.8 · `G2_THREADS_ACCEPTANCE.md` 待用户勾选 |
| **企业安全** | JWT · 隔离 · 登录/API 限流 · 审计落库 · 删库清盘 |
| **3E 部分** | 3E-2 删 processing→409 · 3E-6 可观测 · 3E-7 指纹字段 |
| **部署** | Wave 6 Docker · `/health` · DEPLOY.md |
| **UX 锚点** | dashboard compare v4.3.2-lite **V ✅** |

---

## §2 五条并行线（优先级）

```
① Eval-Ops（现在） → ② 后端模块补强 → ③ 格式 F 线 → ④ 前端 P0 修 bug → ⑤ UX 精品（暂缓）
```

| 线 | 代号 | 优先级 | 说明 |
|----|------|--------|------|
| **①** | Eval-Ops | **P0 · 当前** | M1 测试数据 → M2 性能 → M4 成本 → M11 清单 |
| **②** | BE-Enterprise | P0～P1 | 见 §4 后端模块表 |
| **③** | Format-F | P1～P2 | F1 xlsx → F2 pptx → F3 PDF表 → F4 OCR → F5 多模态 |
| **④** | FE-P0 | P0 | UX-1～8 **Implement**（无 compare，直接修 bug） |
| **⑤** | UX-P1 | **⏸** | 全站 compare + 视觉 · 2027 Q1 再评估 |

---

## §3 时间轴（2026 Q3 → 2027 Q2）

| 阶段 | 时间 | 主题 | 交付 |
|------|------|------|------|
| **Phase 0** | 2026-07～08 | **Eval-Ops P0** | seed S 档 · k6 报告 · 成本文档 · 发布 checklist |
| **Phase 1** | 2026-09～10 | **后端企业债 + FE P0** | 3E-3 引用失效 · 审计页 · UX-7 等 · 库列表分页（若 M2 要） |
| **Phase 2** | 2026-11～2027-01 | **格式 F1～F3** | xlsx · pptx · PDF 表格 |
| **Phase 3** | 2027-02～03 | **Eval-Ops P1 + 运维** | 备份演练 · SLO · Redis 限流调研 |
| **Phase 4** | 2027-04～05 | **UX 恢复 + 答辩** | UX-P1 挑 P0 页 Implement · 全站回归 · 脚本对齐 |

---

## §4 后端模块计划

| 模块 | 现状 | 待做 | 优先级 | 依赖 |
|------|------|------|--------|------|
| **auth** | JWT · 登录/API 限流 ✅ | Redis 多副本限流 | P2 | Phase 3 |
| **audit** | 写库 ✅ · 查询 API ✅ · **审计页 UI ✅** | — | — | — |
| **knowledge_base** | CRUD · scope · **列表分页 ✅** | 列表 perf 索引/缓存（M2 backlog） | P2 | M2 结论 |
| **documents** | 分页 · 筛选 · 409 ✅ | 软删 3E-5 · 回收站 API | P2 | — |
| **documents/upload** | 白名单 4 格式 ✅ | F 线扩展白名单 | P1 | Format-F |
| **ingestion/parser** | pdf/md/docx/txt ✅ | F1/F2/F3 解析器插件 | P1 | Format-F |
| **ingestion/chunker** | 表格 chunk ✅ | 大表拆分策略 | P2 | F1 |
| **rag/retrieval** | hybrid+rerank ✅ | 维持 golden gate | 维护 | — |
| **rag/chat** | SSE · **thread CRUD ✅** · 历史 ✅ · audit ✅ | 多轮上下文记忆 | P2 | — |
| **search** | 跨库搜 ✅ | 结果分页 · 索引优化 | P2 | M2 |
| **dashboard/stats** | OrgScope ✅ | 成本/用量聚合（M4 后） | P2 | M4 |
| **storage/cleaner** | 删库清盘 ✅ | 定时 orphan 扫描 | P2 | M10 |
| **org/units/grants** | ✅ | 维持 ORG 回归 | 维护 | — |
| **health** | DB only ✅ | readiness：embed API 探测（可选） | P2 | — |
| **observability** | 3E-6 audit 聚合 ✅ | Prometheus metrics（M6） | P2 | Phase 3 |

---

## §5 前端 · 按页面计划

| 页面 | 路由 | 现状 | 待做 | 线 | 优先级 |
|------|------|------|------|-----|--------|
| **登录** | `/login` | 可用 ✅ | UX-P1 抛光 ⏸ | ⑤ | P2 |
| **概览** | `/dashboard` | v4.3.2-lite 锚点 ✅ | Implement lite（⏸）· Ops 三格已有 | ⑤/② | P2 |
| **资料库列表** | `/knowledge-bases` | **分页 v1 ✅** · 24/页 · URL · 跳页 | InfoBanner（⏸）· M1 数据验 | ①/⑤ | P1 |
| **库详情** | `/knowledge-bases/:id` | 表+筛选+分页 ✅ | 3E-3 引用失效 ✅ · sticky（⏸） | ②/⑤ | P1 |
| **文档预览** | `.../preview/:docId` | 可用 ✅ · **源文档已删态 ✅** | z-index/375（⏸） | ②/⑤ | P1 |
| **对话** | `.../chat` | **G-2 thread ✅** · 历史 ✅ · UX-1 sticky ✅ | `G2_THREADS_ACCEPTANCE.md` S6～S8 | 发现层 | — |
| **工作区对话** | `/ask` | **G-1 跨库 ✅** · **G-2 thread ✅** | `G2_THREADS_ACCEPTANCE.md` S1～S5 | 发现层 | — |
| **成员** | `/members` | ✅ | 表视觉统一 ⏸ | ⑤ | P2 |
| **组织部门** | `/org/departments` | 15/15 ✅ | **UX-6 picker** · **UX-7 Admin 切部门** | ④ | **P0** |
| **组织设置** | `/org/settings` | ✅ | 表单分组 ⏸ | ⑤ | P2 |
| **账号设置** | `/account` | ✅ | 改密视觉 ⏸ | ⑤ | P2 |
| **（新）审计** | `/admin/audit` | **✅** | 审计日志列表 · Admin only | ② | P1 |
| **（新）帮助** | `/help` | ❌ | PRD P1 关于/帮助 | ② | P2 |

### FE P0 · UX 债（不依赖 UX-P1 compare，直接修）

| ID | 页面 | 改什么 |
|----|------|--------|
| UX-1 | 对话 | 输入框 sticky 贴底 |
| UX-2 | 壳层 | 回概览面包屑竞态 |
| UX-3 | 预览 | 退出菜单 z-index |
| UX-4 | 列表/概览/详情 | member 无权限 **中文 toast** |
| UX-6 | 组织 | 建部门后 picker 无需 F5 |
| UX-7 | 组织 | **Admin 切具体部门生效**（BUG） |
| UX-8 | 壳层 | 切部门 toast 确认 |

---

## §6 格式扩展 · Format-F（已加入总计划）

| ID | 格式 | 后端 | 前端 | 优先级 | 说明 |
|----|------|------|------|--------|------|
| **F1** | **Excel .xlsx** | openpyxl → sheet/表 → MD table chunk | 上传白名单 · 详情 file_type 图标 | **P1** | 公司台账常见 |
| **F2** | **PPT .pptx** | python-pptx → 标题+正文+备注 | 同上 | P1 | 培训课件 |
| **F3** | **PDF 表格** | pdfplumber `extract_tables()` | 失败态文案 | P1 | 补 PDF 弱项 |
| **F4** | **扫描 PDF OCR**（✅ **I + §6 关单** 2026-07-08） | PaddleOCR/pdf2image → `ParsedBlock`+页码 → 现有 ingestion | failed/超限中文文案 · 可选 `OCR_ENABLED` | **P2 · ✅** | **不用多模态 LLM** · 见 [`format-f4-ocr-plan.md`](format-f4-ocr-plan.md) §6 |
| **F5** | **图表/多模态** | 多模态 API + 图 chunk | 预览缩略图 | P2 | **与 F4 分离** · 用户 2026-07-08 不做 |

**权宜（F1～F3 未做前）**：Excel→导出 MD · PPT→导出 PDF(文字层)。**扫描 PDF**：F4 ✅ 可选 OCR（`DEPLOY.md` §4.1）· 未装引擎时仍 failed。  
**F4-6 backlog**：PNG/JPG 单图上传（plan §F4-6）。

---

## §7 Eval-Ops 子计划（Phase 0 明细）

见 [`eval-ops-plan.md`](eval-ops-plan.md) · **M1→M2→M4→M11** · UX ⏸。

| 新增 | M13 格式矩阵（P2） | 每种格式 1 fixture · completed · 对话引用 · 与 F 线联动 |

---

## §8 原子任务 · 代码线（WIP=1 顺序）

| # | 线 | 任务 | 窗 |
|---|-----|------|-----|
| 1～11 | — | Eval-Ops · 3E-3 · UX-1/7 · 库列表分页 · … | ✅ 见上表历史 |
| **12** | ④ | **UX-2** 回概览面包屑竞态 | I · ✅ 2026-07-09 |
| 13 | ④ | **UX-3** 预览退出菜单 z-index | I · ✅ 2026-07-09 |
| 14 | ④ | **UX-4** member 乱操作中文 toast 全站 | I · ✅ 2026-07-09 |
| 15 | ④ | **UX-6** 建部门后 picker 免 F5 | I · ✅ 2026-07-09 |
| 16 | ④ | **UX-8** 切部门 toast 文案（可选 · 行为 ✅） | I/C |
| — | ③ | ~~**F4** OCR~~ | ✅ **§6 关单** 2026-07-08 |

> **代码线 #12～16 全 ✅ 后** → 进入 **§9 计划最后一关**（浏览器全模块验收）。**未做完 §9 不算 Phase 1 关门。**

---

## §9 计划最后一关 · 浏览器全模块验收（BA-FINAL）· ✅ 2026-07-09

> **状态**：✅ **关门** · 用户口头「BA-FINAL ✅」· M1～M12 全表 ✅  
> **清单**：[`BROWSER-MODULE-ACCEPTANCE.md`](../BROWSER-MODULE-ACCEPTANCE.md) · 流程：[`docs/process/BROWSER-ACCEPTANCE.md`](../../../docs/process/BROWSER-ACCEPTANCE.md)

| 步 | 做什么 | 通过标准 |
|----|--------|----------|
| BA-0 | Docker · health ok · 浏览器开站 | §0 开测前勾满 |
| BA-1 | **M1～M12 逐模块** | 清单表 **全部 ✅** |
| BA-2 | gap 处理 | 建议项入 backlog |
| BA-3 | 文档 | `cockpit.html` · 本节 ✅ · 用户口头关门 |

| # | 模块 | 状态 |
|----|------|------|
| M1 | 登录 · 工作区 | ✅ 2026-07-09 |
| M2 | 概览 | ✅ 2026-07-08 |
| M3 | 资料库列表 | ✅ 2026-07-09 |
| M4 | 库详情 | ✅ |
| M5 | 文档预览 | ✅ 2026-07-09 |
| M6 | 对话 · 引用 | ✅ 2026-07-08 |
| M7 | member 只读 | ✅ 2026-07-09 |
| M8 | 组织 · 部门 | ✅ 2026-07-09 |
| M9 | 成员 · 团队设置 | ✅ 2026-07-09 |
| M10 | 操作审计 | ✅ 2026-07-09 |
| M11 | 账号设置 | ✅ 2026-07-09 |
| M12 | 组织隔离 · grant | ✅ 2026-07-08 |

**备注**：验收环境 `localhost:5173` dev；M5 E2 删文档 chip 未专测（3E-3 pytest 已绿）；开发 compose uploads 无持久卷。

---

## §10 子 plan 索引

| 文件 | 管什么 |
|------|--------|
| `enterprise-master-plan.md` | **本文 · 总地图** |
| `eval-ops-plan.md` | 评估运维 M1～M13 |
| `ux-p1-plan.md` | ⏸ 精品 UI compare |
| `kb-pages-polish-plan.md` | Plan-3E 细节 |
| `rag-optimization-plan.md` | RAG R 线 |
| `enterprise-wave-plan.md` | 部署 EW 线 |
| `format-f4-ocr-plan.md` | **F4** 扫描 PDF OCR · F4-1～F4-5 · **§6 整波关单 ✅** |
| `format-f4-ocr-research.md` | F4 Research · H1～H7 |
| `discovery-smart-chat-prd.md` | **G-1** 工作区 `/ask` 跨库 · PRD G-1-1～5 ✅ · TECH-5.7 |
| `discovery-smart-chat-plan.md` | **G-1** Implement · G1-0～5 ✅ · `G1_ASK_ACCEPTANCE.md` |
| `discovery-smart-chat-g2-threads-prd.md` | **G-2** thread 列表/切换 · PRD G-2-1～5 ✅ · TECH-5.8 |
| `discovery-smart-chat-g2-threads-plan.md` | **G-2** Implement · G2-0～4.3 ✅ · `G2_THREADS_ACCEPTANCE.md` |
| [`cockpit.html`](../cockpit.html) | 当前关 + 下一步（**SSOT 进度**） |

---

## §11 下一窗交接（C/M · BA-FINAL · 代码线 UX-3/4/6 ✅ 后可开）

```
@rag-knowledge-platform/docs/BROWSER-MODULE-ACCEPTANCE.md
@rag-knowledge-platform/docs/tasks/enterprise-master-plan.md §9
@docs/process/BROWSER-ACCEPTANCE.md
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/docs/TEST_ACCOUNTS.md

【背景】UX-6 ✅ · 代码线 #12～15 全 ✅ · §9 BA-FINAL = 计划最后一关

【要求】严格 WIP=1 · 一次只验一个模块（M3→M10→M7→…）· **你亲手点** · AI 不代签 · 除非 P0 否则不写代码

【验收】M1～M12 表全勾 ✅ 或 gap 入 backlog · cockpit §9 BA-FINAL ✅ · 你口头「BA-FINAL ✅」
```

---

## §13 下一窗交接（用户试跑 · G-2 验收表）

```
@rag-knowledge-platform/docs/G2_THREADS_ACCEPTANCE.md
@rag-knowledge-platform/docs/cockpit.html
@rag-knowledge-platform/docs/TEST_ACCOUNTS.md

【背景】G-2 G2-0～G2-4.3 ✅ · 验收表脚本就绪 · A 层 pytest 30 + golden 12/12 + build 绿

【要求】浏览器按 G2_THREADS_ACCEPTANCE.md §3 S1～S8 + §4 E · **你亲手勾选** · 填 §8 试跑记录

【验收】S/E 勾选 · 口头「G-2 验收 ✅」· 失败项入 backlog 另开 I 窗
```
