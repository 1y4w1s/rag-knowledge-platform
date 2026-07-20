# 睿阁 RAG 评测体系 · 收尾执行计划

> 本计划涵盖 W1-W6 全部已完成工作的收尾项
> 更新: 2026-07-20 · 新增 2026-07-20 全链路审计发现的 7 个问题

---

## W1-W6 当前状态速览

| 阶段 | 状态 | 完成度 | 剩余 |
|------|------|--------|------|
| W1 测试集版本化 | ✅ 完成 | 100% | — |
| W2 统一评分引擎 | 🟡 做完未接入 | 90% | 新 scoring 引擎接 CI |
| W3 chunk 提取 | ✅ 完成 | 100% | — |
| W4 CI 三层门禁 | 🟡 配完未验证 | 90% | 真实 PR 验证 |
| W5 英文嵌入 + CRAG | ✅ 完成 | 100% | — |
| W6 生成评测 | 🟡 文件就绪未接通 | 80% | 校准集接 Judge + 清理脚本挂 pipeline |

---

## 2026-07-20 全链路审计 — 7 个新发现的问题

### 🔴 致命（必须先修）

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| **A** | **benchmark.yml 数据集名不匹配** → 手动/定时触发全部崩溃 | `.github/workflows/benchmark.yml:108` | `run_retrieval.py` 的加载器只认 `crag`/`enterprise`，不认 `golden_qa`/`expense_qa`/`enterprise_qa`。`default: "golden_qa"` 传进去就挂 |
| **B** | **benchmark.yml 传了 DASHSCOPE_API_KEY，代码读的是 TONGYI_API_KEY** | `.github/workflows/benchmark.yml:112` + `config.py:38` | Secret 名给错了，非 mock 模式下通义嵌入不可用 |

### 🟡 重要（建议修）

| # | 问题 | 文件 | 说明 |
|---|------|------|------|
| **C** | **CRAG 706MB 无条件下载** | `.github/workflows/benchmark.yml:94-101` | 手动跑 golden_qa 也下载 CRAG，加 `if: contains(datasets, 'crag')` |
| **D** | **Golden QA cross domain 仅 3 题** | `golden_qa/v1.0/cases.json` | 跨文档检索测试无统计意义，需扩充 |

### 🟢 已确认无问题（非阻塞）

| # | 问题 | 结论 |
|---|------|------|
| **E** | crag-nightly postgres 用户名 | ✅ 已改为 `raguser`，一致 |
| **F** | benchmark 脚本 `exit(1)` 误触发 | ✅ 未发现 |
| **G** | `from app.main import app` CI 安全 | ✅ 有 try/except 兜底，日志噪声可接受 |

---

## 收尾清单（更新版）

### 第一梯队：独立可做（不需要你操作）

| 编号 | 项 | 文件/范围 | 预估时间 | 前置依赖 |
|------|----|-----------|---------|---------|
| 1 | **README 更新诚实基线** | `README.md`、`docs/master-checklist.md` | 30 分钟 | 无 |
| 2 | **清理脚本挂入 nightly** | 在 `benchmark.yml` 新增一个 step，每次 nightly 先清理旧记录 | 10 分钟 | 无 |
| 3 | **校准集接入 Judge 流程** | 修改 `judge.py`，在每次评分前先用 20 题校准集验证评分一致性 | 1 小时 | 无 |
| **A** | **benchmark.yml 数据集名修复** | `benchmark.yml` default/inputs 改为正确注册名 | 30 分钟 | 无 |
| **C** | **CRAG 下载加条件判断** | `benchmark.yml` CRAG step 加 `if:` | 10 分钟 | 无 |

### 第二梯队：需要你操作

| 编号 | 项 | 操作位置 | 预估时间 |
|------|----|---------|---------|
| **B** | **加 TONGYI_API_KEY 到 GitHub Secrets** | GitHub → Settings → Secrets → `TONGYI_API_KEY` | 2 分钟 |
| 4 | **配置 DEEPSEEK_API_KEY** | 同上 → `DEEPSEEK_API_KEY` | 2 分钟 |
| 5 | **配置 RAG_TEST_PASSWORD** | 同上 → `RAG_TEST_PASSWORD` = `JudgePass123!` | 1 分钟 |

### 第三梯队：依赖 Secrets 配置完成后

| 编号 | 项 | 预估时间 | 前置依赖 |
|------|----|---------|---------|
| 6 | **W2 新评分引擎接入 CI** | 1 小时 | 无 |
| 7 | **端到端全链路验证** | 2 小时 | B、4、5 |
| 8 | **Expense QA + Enterprise QA golden_answer 补充** | 1 小时 | 4 |
| **D** | **Golden QA cross domain 扩充** | 半天 | 无 |

---

## 执行路径

```
第一梯队（纯代码，无需你介入）
  ├── A. benchmark.yml 数据集名修复         ← 致命，先修
  ├── C. CRAG 下载加条件判断
  ├── 1. README 更新诚实基线
  ├── 2. 清理脚本挂入 nightly
  └── 3. 校准集接入 Judge

你操作（约 5 分钟）
  ├── B. 加 TONGYI_API_KEY
  ├── 4. 加 DEEPSEEK_API_KEY
  └── 5. 加 RAG_TEST_PASSWORD

第三梯队（我继续）
  ├── 6. W2 新评分引擎接入 CI
  ├── 7. 全链路验证
  ├── 8. 补充 golden_answer
  └── D. Golden QA cross domain 扩充
```
