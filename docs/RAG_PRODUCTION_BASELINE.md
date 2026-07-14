# RAG 生产嵌入基线（EW-C2）

> **版本**：v0.6 · **日期**：2026-07-07（KB 详情 `n is not iterable` 修障 ✅）  
> **用途**：记录 golden GQ-1～12 的 **Hit@3** 基线；对比 CI mock 嵌入与 **通义 text-embedding-v2** 生产嵌入差异。  
> **权威用例表**：[`golden_qa.md`](golden_qa.md) · SSOT [`backend/tests/fixtures/golden_qa.json`](../backend/tests/fixtures/golden_qa.json)

---

## 1. 摘要

| 项 | 结果 |
|----|------|
| **Mock 嵌入（CI）** | **12/12** Hit@3 ✅ · `pytest tests/test_retrieval_golden.py` · 2026-07-06 R5-1 |
| **通义嵌入（生产）** | **12/12** Hit@3 ✅ · `run_golden_production_baseline.py` · 2026-07-07 R5-3a |
| **手跑脚本** | `backend/scripts/run_golden_production_baseline.py` |
| **结论** | mock 与通义 **均为 12/12 全绿**；无 mock 绿、通义红案例 |

---

## 2. Mock 基线（CI · 词重叠 mock）

**命令**（`backend/` 目录）：

```powershell
$env:EMBEDDING_PROVIDER='mock'
py -3.11 -m pytest tests/test_retrieval_golden.py -v
```

**运行记录**：2026-07-06 · Windows · Python 3.11 · **10 passed in ~10s**

| ID | 问题（摘要） | Hit@3 | 备注 |
|----|-------------|-------|------|
| GQ-1 | 年假有多少天？ | ✅ | MD |
| GQ-2 | 迟到怎么处理？ | ✅ | MD |
| GQ-3 | 年终奖什么时候发？ | ✅ | MD |
| GQ-4 | annual leave 10 days which page | ✅ | PDF 页码 |
| GQ-5 | 每月餐补多少钱？ | ✅ | MD |
| GQ-6 | 年假需要提前多久申请？ | ✅ | MD |
| GQ-7 | 员工手册 1.2 条款… | ✅ | 条款号 |
| GQ-8 | 迟到超过 30 分钟不会按旷工算吧？ | ✅ | 否定问法 |
| GQ-9 | 年假有多少天？ | ✅ | DOCX |
| GQ-10 | annual leave apply two weeks… | ✅ | PDF 跨页合并切片 |

---

## 3. 通义嵌入手跑（生产抽测）

### 3.1 前置

1. 项目根 `.env` 已配置 `TONGYI_API_KEY` + `EMBEDDING_PROVIDER=tongyi`（**勿提交 Git**）
2. PostgreSQL 可连（本机 `localhost:5432` 或 Docker `zhiku-postgres`）
3. DashScope 账户 **嵌入 API 有可用配额**（见 §3.3）

### 3.2 命令

```powershell
cd backend
$env:EMBEDDING_PROVIDER='tongyi'
py -3.11 scripts/run_golden_production_baseline.py
```

可选 JSON 明细：`py -3.11 scripts/run_golden_production_baseline.py --json`

脚本行为：对 GQ-1～12 **各建独立库 → 入库 fixture → hybrid Top-3 检索 → 对照 golden 期望字段**；不走 pytest 内 mock。

### 3.3 手跑记录

#### 首次尝试（2026-07-06 上午）

| 项 | 值 |
|----|-----|
| 嵌入 API | ❌ HTTP 403 `AllocationQuota.FreeTierOnly` |
| 处理 | DashScope 关闭「免费额度用完即停」+ 开通 `text-embedding-v2` 付费 |

#### 正式抽测 · 扩题前（2026-07-06 · GQ-1～10）

| 项 | 值 |
|----|-----|
| 命令 | `EMBEDDING_PROVIDER=tongyi` + `run_golden_production_baseline.py --json` |
| 环境 | Windows · Python 3.11 · 本机 Postgres · 约 **20s** |
| 模型 | 通义 `text-embedding-v2` · 1536 维 |
| **Hit@3 合计** | **10/10** ✅ |

> R5-1 扩至 GQ-12 后，见下 **R5-3a** 全量 12 题记录。

#### R5-3a 全量抽测（2026-07-07 · GQ-1～12）

| 项 | 值 |
|----|-----|
| 命令 | `EMBEDDING_PROVIDER=tongyi` + `run_golden_production_baseline.py`（可选 `--json`） |
| 环境 | Windows · Python 3.11 · 本机 Postgres · 约 **24s** |
| 模型 | 通义 `text-embedding-v2` · 1536 维 |
| **Hit@3 合计** | **12/12** ✅ |

| ID | 问题（摘要） | Hit@3 | Top-1 section | Top-1 page |
|----|-------------|-------|---------------|------------|
| GQ-1 | 年假有多少天？ | ✅ | `1.1 年假` | — |
| GQ-2 | 迟到怎么处理？ | ✅ | `1.2 迟到` | — |
| GQ-3 | 年终奖什么时候发？ | ✅ | `2.1 年终奖` | — |
| GQ-4 | annual leave 10 days which page | ✅ | `Chapter 1 Attendance` | 2 |
| GQ-5 | 每月餐补多少钱？ | ✅ | `2.2 餐补` | — |
| GQ-6 | 年假需要提前多久申请？ | ✅ | `1.1 年假` | — |
| GQ-7 | 员工手册 1.2 条款… | ✅ | `1.2 迟到` | — |
| GQ-8 | 迟到超过 30 分钟不会按旷工算吧？ | ✅ | `1.2 迟到` | — |
| GQ-9 | 年假有多少天？（DOCX） | ✅ | `1.1 年假` | — |
| GQ-10 | annual leave apply two weeks… | ✅ | `Chapter 1 Attendance` | 2 |
| GQ-11 | 餐补福利表里每月多少钱？ | ✅ | `2.2 餐补` | — |
| GQ-12 | 带薪年休假可以休多少天？ | ✅ | `1.1 年假` | — |

> **与 mock 对比**：12 题 **无分歧**（mock ✅ = 通义 ✅）。GQ-11 表格切片 Top-2 为 table chunk（`| 餐补 | 300 元/月 |`），Hit@3 内仍命中期望字段；GQ-12 改写问法 Top-1 正确命中 `1.1 年假`。

---

## 4. Mock vs 通义：差异说明（白话）

| 维度 | Mock（CI） | 通义（生产） |
|------|------------|--------------|
| **向量怎么来** | 按问题/正文 **词重叠** 哈希到 1536 维 | 通义 **text-embedding-v2** 语义向量 |
| **目的** | 保证 hybrid 管道、切片元数据、RRF 逻辑 **可回归** | 衡量真实用户问法下的 **检索命中率** |
| **成本** | 免费、离线、秒级 | 按 token 计费，10 题约数十次嵌入调用 |
| **实测（2026-07-07）** | 本 golden 集 mock 与通义 **均为 12/12**，无 mock 绿、通义红案例 |
| **能否代替** | ❌ mock 全绿 **不能** 证明生产检索质量 | ✅ 企业 demo 前须本表通义 **≥11/12**（建议目标，可随补跑调整） |

**为何 CI 不用通义**：贵、需 Key、网络依赖；EW-C2 用 **手跑 + 本文档** 留生产基线，不塞进 GitHub Actions。

---

## 5. 对话现象（浏览器抽检 · R5-3b ✅）

> **环境**：2026-07-07 · `http://localhost/` · `demo_admin` · 资料库「答辩演示库」（`golden_handbook.md` + 补传 `golden_handbook.pdf`）· 对话页 `/knowledge-bases/{kb_id}/chat`  
> **通义 Hit@3 12/12** 已在 R5-3a 验证；本节为 **端到端对话 + 引用卡片** 人工抽检。

### 5.1 Baseline 三题（P1～P3）

| # | 用户问 | 回答要点（实测） | 引用卡片（实测） | 结果 |
|---|--------|-----------------|-----------------|------|
| **P1** | 年假有多少天？ | 10 天；来源 1.1 年假 | chip#1 `golden_handbook.md · 1.1 年假` · 摘录「年假10天…提前两周」 | ✅ |
| **P2** | 迟到超过 30 分钟不会按旷工算吧？ | **会**按旷工半天（否定问法未误导） | chip#1 `1.2 迟到` · 摘录含「旷工」 | ✅ |
| **P3** | annual leave 10 days which page | 英文答 · **第 2 页** | chip#2 `golden_handbook.pdf · Chapter 1 Attendance · p.2` · 摘录含 `annual leave 10 days` | ✅ |

### 5.2 Golden 加测（GQ-11 / GQ-12）

| ID | 用户问 | 回答要点（实测） | 引用卡片（实测） | 结果 |
|----|--------|-----------------|-----------------|------|
| **GQ-11** | 餐补福利表里每月多少钱？ | 300 元 | chip#1 `2.2 餐补` · 摘录「每月餐补 300 元」 | ✅ |
| **GQ-12** | 带薪年休假可以休多少天？ | 10 天（改写问法） | chip#1 `1.1 年假` | ✅ |

**合计**：**5/5 Pass**（P1～P3 + GQ-11 + GQ-12）

### 5.3 Gap 清单（不修 retrieval · backlog）

| 级别 | 现象 | 影响 |
|------|------|------|
| 可选 | P3 / GQ-11 的 **Top-1 chip** 有时为 MD 节而非 PDF 页码 / 表格 chunk（#2 仍含期望字段） | 演示时优先点 chip#2 或看正文页码句；检索 Hit@3 已绿 |
| 可选 | GQ-11 出现两个 `2.2 餐补` chip（正文 + 表格切片，R2-2 预期行为） | 无功能错 |
| **P1 前端** | 资料库详情 `/knowledge-bases/:id` 报 `Unexpected Application Error: n is not iterable` | **✅ 2026-07-07 修障**：grants/筛选 state 非数组时兜底 · `npm run build` 绿 · 浏览器列表→详情（答辩演示库）正常 |

**你怎么验（浏览器）**：`demo_admin` 登录 → 答辩演示库 → 对话页逐条问上表 → 点 chip 核对摘录。

---

## 6. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-06 | EW-C2 初版：mock 10/10；通义配额阻断 |
| 2026-07-06 | 通义付费开通后补跑：**10/10** Hit@3 全绿（GQ-1～10） |
| 2026-07-07 | **R5-3a**：R5-1 扩题后全量手跑 GQ-1～12 · **12/12** Hit@3 全绿 |
| 2026-07-07 | **R5-3b**：浏览器对话抽检 P1～P3 + GQ-11/12 · **5/5 Pass** · §5 落盘 · 详情页 `n is not iterable` 记 backlog |
| 2026-07-07 | **KB 详情修障**：grants/部门树/高级筛选非数组兜底 · 列表→「答辩演示库」详情 · `npm run build` 绿 |
