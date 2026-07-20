# 睿阁 RAG 评测体系 · 收尾执行计划

> 本计划涵盖 W1-W6 全部已完成工作的收尾项
> 完成度：约 70%。剩下的 30% 是集成+验证+文档

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

## 收尾清单

### 第一梯队：独立可做（不需要你操作）

| 编号 | 项 | 文件/范围 | 预估时间 | 前置依赖 |
|------|----|-----------|---------|---------|
| 1 | **README 更新诚实基线** | `README.md`、`docs/master-checklist.md` | 30 分钟 | 无 |
| 2 | **清理脚本挂入 nightly** | 在 `benchmark.yml` 新增一个 step，每次 nightly 先清理旧记录 | 10 分钟 | 无 |
| 3 | **校准集接入 Judge 流程** | 修改 `judge.py`，在每次评分前先用 20 题校准集验证评分一致性 | 1 小时 | 无 |

### 第二梯队：需要你操作

| 编号 | 项 | 操作位置 | 预估时间 | 前置依赖 |
|------|----|---------|---------|---------|
| 4 | **配置 DEEPSEEK_API_KEY** | GitHub → Settings → Secrets and variables → Actions → 新建 `DEEPSEEK_API_KEY` | 2 分钟 | 你需要在 DeepSeek 平台获取 API Key |
| 5 | **配置 RAG_TEST_PASSWORD** | GitHub Secrets → 新建 `RAG_TEST_PASSWORD`，值为 `JudgePass123!` | 1 分钟 | 无 |

### 第三梯队：依赖 Secrets 配置完成后

| 编号 | 项 | 文件/范围 | 预估时间 | 前置依赖 |
|------|----|-----------|---------|---------|
| 6 | **W2 新评分引擎接入 CI** | 修改 `ci.yml` rag-benchmark job，同时跑新旧引擎输出对比 | 1 小时 | 无（不依赖 Secrets） |
| 7 | **端到端全链路验证** | 触发一次真实 PR → 观察全部 job 是否绿 → 检查 benchmark 报告 | 2 小时 | 4、5 |
| 8 | **Expense QA + Enterprise QA golden_answer 补充** | 重复 W6.1 流程，为 213 题生成 golden_answer | 1 小时 | 4 |

---

## 执行路径

```
第一梯队（纯代码，无需你介入）
  ├── 1. README 更新诚实基线
  ├── 2. 清理脚本挂入 nightly
  └── 3. 校准集接入 Judge

你操作（约 3 分钟）
  ├── 4. 加 DEEPSEEK_API_KEY
  └── 5. 加 RAG_TEST_PASSWORD

第三梯队（我继续）
  ├── 6. 新评分引擎接入 CI
  ├── 7. 全链路验证
  └── 8. 补充 Expense + Enterprise golden_answer
```

---

## 当前已确认的测试集数据一览

| 测试集 | 类型 | 题数 | 拒答题 | 版本化 | golden_answer |
|--------|------|------|--------|--------|--------------|
| Golden QA | 自建中文（员工手册） | 109 | 20 | ✅ v1.0 | ✅ 109/109 |
| Expense QA | 自建中文（报销制度） | 105 | 4 | ✅ v1.0 | ❌ 0/105 |
| Enterprise QA | 自建中文（6 份企业文档） | 108 | 16 | ✅ v1.0 | ❌ 0/108 |
| CRAG English | 外部英文 Wikipedia | 100 / 4409 | 0 | — | ❌ |

## 真实基线

| 测试集 | Hit@3 | 嵌入模型 | 说明 |
|--------|-------|---------|------|
| Golden QA | 95.5% | bge-small-zh | 中文单文档检索 |
| Expense QA | 91.1% | bge-small-zh | 格式依赖已消除 |
| Enterprise QA | ~25% | bge-small-zh | content_contains 从 chunk 提取，诚实基线 |
| CRAG English | 26% | bge-small-en-v1.5 | 原 19%（bge-small-zh），+7pp |

## 诚实版 README 基线表（待写入）

```
| 测试集 | Hit@3 | 说明 |
|--------|-------|------|
| Golden QA (109题) | 95.5% | 中文单文档检索，20题拒答独立报告 |
| Expense QA (105题) | 91.1% | 中文报销制度，格式无关 |
| Enterprise QA (108题) | ~25% | 6份异质企业文档，诚实基线 |
| CRAG English (100题) | 26% | 英文检索，bge-small-en |
| Faithfulness | — | 待 LLM-as-judge 评估 |
```
