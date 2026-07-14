# Eval-Ops · 企业级评估与运维 Plan

> **状态**：✅ 并入 [`enterprise-master-plan.md`](enterprise-master-plan.md) · Phase 0 P0 关单 · P1 **M5 ✅** · **M9 ✅** · **M10 ✅** · Eval-Ops P1 关单 · 下一步 **UX-7** · §0 用户拍板企业级+格式 F 线（2026-07-08）  
> **代号**：**Eval-Ops**（Evaluation + Operations）  
> **背景**：用户拍板 **测试数据 A 档（S tier）**；需系统化评估性能、成本、可靠性等；**UX-P1 前端精品改造搁置**（dashboard compare V ✅ 保留，其余 compare/Implement 暂停）  
> **原则**：**模块化 · 一窗一块 · WIP=1** — 禁止一次读全库、禁止与 UX-P1 I 窗并行

---

## §0 做 & 不做

| 做（Eval-Ops 范围） | 不做（仍 Out of scope / 另线） |
|---------------------|--------------------------------|
| **M1** S 档测试数据脚本（10 库 × 5 文档 · 元数据 · 不调嵌入 API） | **UX-P1** 剩余 compare + Wave A～E **Implement**（**搁置**） |
| **M2** 读路径性能基线（列表 / stats / 跨库搜） | 换 LLM 供应商 · 换嵌入模型 |
| **M4** API 成本估算文档（对话 / 上传 / 重嵌入） | 支付、套餐、计费系统 |
| **M5** 现有限流实测（login / chat / upload） | Redis 多副本限流（Wave 2+） |
| **M9** Demo 环境 3 条 SLO（文档级，可手工量） | Prometheus / Grafana 全套 |
| **M10** 备份恢复演练一次（pg + uploads 卷） | 公网 HTTPS · 多 AZ |
| **M11** 发布回归 checklist 落盘 | OCR · Agent 联网 |
| 结论写入 `docs/tasks/eval-Mx-*.md` 或本节附录 | **L 档** 大量真入库（除非单独拍板预算） |

### UX-P1 搁置说明

| 项 | 处理 |
|----|------|
| 已完成 | dashboard compare **v4.3.2-lite V ✅** · kb-list compare HTML 已产出 🟡 |
| **暂停** | kb-list V 验收、kb-detail 及后续 compare、Wave A～E **Implement** |
| 恢复条件 | Eval-Ops **M1+M2+M4 文档** 过关后，或答辩前 3 个月再评估 UX 线 |
| 文档 | `ux-p1-plan.md` 头索引标 **⏸ 搁置**；cockpit 活跃线切 **Eval-Ops** |

---

## §1 目标（大白话）

| 目标 | 验收长什么样 |
|------|----------------|
| **能 demo 「库多」** | `demo_admin` 登录 → 资料库列表 **≥10 库**，搜得出来 |
| **知道卡不卡** | 有数字：列表 API p95、并发 20 用户错误率 |
| **知道花多少钱** | 能口播：一次对话 / 一次上传 **大约** 多少 token、哪几个 API 计费 |
| **知道能不能追责/恢复** | 审计已有；备份练过一次有记录 |
| **面试能讲** | 「我们按模块做了容量与成本评估，UX 线暂停先补企业底線」 |

---

## §2 模块地图（12 块 · 优先级）

```
P0（先做）  M1 → M2 → M4-doc → M11
P1（加分）  M5 → M9 → M10
已有 ✅     M7（golden RAG）· M8 部分（pytest 隔离）
P2（真 SaaS）M3 深度 · M6 指标栈 · M12 隐私保留策略
```

| ID | 模块 | 产出 | 优先级 | 依赖 |
|----|------|------|--------|------|
| **M1** | 测试数据 S 档 | `backend/scripts/seed_volume_data.py` + `TEST_ACCOUNTS.md` 一节 | **P0** | `seed_enterprise_demo.py` 已跑 |
| **M2** | 读路径性能 | `backend/loadtests/read_paths.js`（k6）+ `eval-M2-report.md` | **P0** | M1 |
| **M4** | API 成本模型 | `eval-M4-cost-model.md`（公式 + 示例） | **P0** | 无（可并行 M1） |
| **M11** | 发布回归清单 | `eval-M11-release-checklist.md` | **P0** | 无 |
| **M5** | 限流实测 | `eval-M5-rate-limit.md` + 可选 pytest 补一条 | P1 ✅ | 无 |
| **M9** | SLO 基线 | `eval-M9-slo.md`（3 条指标） | P1 ✅ | M2 数据更准 |
| **M10** | 备份恢复 | `eval-M10-backup-runbook.md` + 一次演练记录 | P1 ✅ | Docker prod compose |
| **M3** | 写/入库并发 | `eval-M3-ingestion-load.md` | P2 | M1、预算 |
| **M6** | 可观测性 | metrics/结构化日志方案（仅 research） | P2 | Plan-3E 对齐 |
| **M7** | RAG 质量 | 沿用 R5 golden gate | ✅ | — |
| **M8** | 隔离压测 | 并发 SA pytest 小套 | P2 | M2 |
| **M12** | 隐私/保留 | PRD P1 一节草稿 | P2 | — |
| **M13** | 格式矩阵验收 | 各格式 1 fixture · 与 **Format F1～F5** 联动 · **F4 §6 关单 ✅**：`tests/fixtures/ocr/sample_scan.pdf` + `test_ocr_ingestion.py`（mock 绿 · `RUN_OCR_TESTS=1` 可选真引擎） | P2 | Format-F |

---

## §2b 格式扩展 · Format-F（企业级 · 见 master-plan §6）

| ID | 格式 | 优先级 |
|----|------|--------|
| F1 | xlsx | P1 |
| F2 | pptx | P1 |
| F3 | PDF 表格结构化 | P1 |
| F4 | OCR 扫描 PDF（**§6 整波关单 ✅** · F4-1～F4-5 · [`format-f4-ocr-plan.md`](format-f4-ocr-plan.md) §6 · M13 矩阵行） | P2 |
| F5 | 图表多模态（**不做** · 与 F4 分离） | P2 |


## §3 原子任务（P0 明细）

### M1 · S 档测试数据

| 步 | 任务 | 验收 |
|----|------|------|
| M1-1 | 新建 `seed_volume_data.py`：`--tier S` · `--workspace team` · 默认部门「研发部」 | 幂等可重复跑 |
| M1-2 | 10 个 `KnowledgeBase` + 每库 5 `Document`（status=`completed` · **无 chunk/向量**） | `GET /knowledge-bases` 返回 ≥10 |
| M1-3 | 库名可搜（含「产品」「市场」等） | 列表 `?q=产品` 有结果 |
| M1-4 | 更新 `docs/TEST_ACCOUNTS.md`：用法 + **明确不调通义** | 文档可跟跑 |
| M1-5 | pytest：seed 后列表 count（可选 smoke） | 相关测试绿 |

**不做什么**：不调用 embedding · 不上传真 PDF · 不动前端

### M2 · 读路径性能

| 步 | 任务 | 验收 |
|----|------|------|
| M2-1 | k6 脚本：登录 → `GET /knowledge-bases` → `GET /dashboard/stats` | 脚本 README |
| M2-2 | 场景：10 VU / 30s、20 VU / 30s（内网 Docker） | 输出 p50/p95 |
| M2-3 | `eval-M2-report.md`：数字 + **是否需列表分页** 结论 | 你读得懂 |

**初版通过线（可调）**：20 VU · 列表 p95 < 500ms · 0% 5xx

### M4 · 成本模型（纯文档）

| 步 | 任务 | 验收 |
|----|------|------|
| M4-1 | 列计费点：通义 embed · DeepSeek chat · （rerank 若开） | 表格式 |
| M4-2 | 单次对话估算：检索 chunk 数 + prompt ≤3000 + 回答 ~500 | 带公式 |
| M4-3 | 单次上传估算：页数 → chunk 数 → embed 次数 | 带例子 |
| M4-4 | Demo 月预算建议（如 embed < ¥X） | 你拍板数字 |

### M11 · 发布回归清单

> **产出**：[`eval-M11-release-checklist.md`](eval-M11-release-checklist.md) ✅ 2026-07-08

| 步 | 任务 | 验收 |
|----|------|------|
| M11-1 | 合并前：`pytest` · `npm run build` · golden 12/12 | checklist md ✅ |
| M11-2 | 发版后：ORG 15 步抽 3 步 · `/health` · demo 登录列表 | 同上 ✅ |

---

## §4 执行节奏（WIP=1）

| 阶段 | 窗口 | 产出 |
|------|------|------|
| **L** | 本窗 | 本文 §0～§3 确认 |
| **I-1** | M1 一条 | seed 脚本 + TEST_ACCOUNTS |
| **I-2** | M4 文档 | cost-model（可与 M1 并行需**不同对话**） |
| **I-3** | M2 | k6 + report |
| **I-4** | M11 | checklist |
| **P1** | M5/M9/M10 | 按答辩时间表排 |

**预计**：P0 约 **2～3 周**（每周 2～3 个 I 窗，不赶工）

---

## §5 与现有文档关系

| 文档 | 关系 |
|------|------|
| `ux-p1-plan.md` | **⏸ 搁置**；dashboard V ✅ 为冻结锚点 |
| `rag-optimization-plan.md` R1-3 | 文档分页 ✅；**库列表分页** 仅 M2 结论触发 |
| `TECH-SEC` | M5 实测限流 · M6 对齐 SEC-6 |
| `enterprise-wave-plan.md` | M10 备份对齐 Wave 6 |
| `RAG_PRODUCTION_BASELINE.md` | M7 不重复 |

---

## §6 L 关 DoD

- [ ] 用户确认 **§0 边界**（含 UX 搁置）
- [ ] 用户确认 **§2 模块优先级** P0/P1/P2
- [ ] 用户确认 **M1 S 档规格**（10×5 · 无嵌入）
- [ ] 用户确认 **M2 通过线** 或改数字
- [ ] `cockpit.html` 活跃线 → Eval-Ops
- [ ] `ux-p1-plan.md` 标 ⏸

---

## §7 下一窗交接（I 窗 · UX-1）

```
@rag-knowledge-platform/docs/tasks/enterprise-master-plan.md
@rag-knowledge-platform/docs/cockpit.html

【背景】UX-7 ✅ · Admin 切具体部门生效 · Eval-Ops P1 关单

【要求】严格只做 FE P0 **UX-1** 对话输入框 sticky · WIP=1

【验收】长对话时输入框贴底可见 · npm run build 绿 · cockpit 同步
```

---

## §8 下一节（L 窗待确认）

确认 §0 后出 **§3 M2/M4 通过线拍板** 与 **M9 三条 SLO 草案**（对话延迟 / API 可用率 / 列表延迟）。
