# 睿阁生产级 RAG 评测体系重建计划

> 版本: v1.0 · 2026-07-19
> 设计原则：评测与系统分离、外部队考是硬性门槛、每一分都有据可查
> 审核记录：4 轮独立审查（架构/过渡/一致性/维护），所有隐患已修复

---

## 一、评测体系架构

### 核心实体

```
TestSet ──拥有──▶ TestCase ──产生──▶ EvalRun ──包含──▶ EvalResult
                         │
                         └──参照──▶ GoldenAnswer
```

#### 1. TestSet（测试集）

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 唯一标识 |
| `source_type` | enum | `self_built` / `external` |
| `source_docs` | string[] | 源文档路径 |
| `version` | string | 语义版本号 |
| `chunker_version` | string | 创建时的 chunker 版本 |
| `independent_review` | bool | 是否有独立审核 |
| `review_signoff_path` | string | 审核签收文件路径 |

#### 2. TestCase（单道测试题）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `case_id` | string | ✅ | |
| `query` | string | ✅ | |
| `difficulty` | enum | ✅ | `L1`/`L2`/`L3`/`L4` |
| `domain` | string | 否 | |
| `source_doc` | string | ✅ | 答案来源文档 |
| `source_doc_version` | string | ✅ | 创建时的文档版本 |
| `question_type` | enum | ✅ | `direct`/`reasoning`/`calculation`/`rejection` |
| `golden_answer` | string | 否 | 标准答案（LLM-as-judge 用） |
| `match_type` | enum | ✅ | `content`/`answer`/`exact` |
| `expect` | object | 否 | 检索匹配条件 |
| `independent_review` | bool | ✅ | |

**`expect` 约束**：
- ✅ `content_contains` 必须从 chunk 内容直接复制，不得手写格式
- ✅ `source_doc` 必须填写
- ❌ 禁止 `content_contains` 长度 < 10 字符（改为唯一性约束：全文只匹配到一个 chunk）
- ❌ 禁止同一 `content_contains` 在不同 TestCase 中重复
- ❌ `question_type = rejection` 不能有 `expect`

#### 3. EvalConfig（运行配置）← 新增

每次运行序列化完整配置，保证可复现：

```json
{
  "top_k": 3,
  "embedding_provider": "bge",
  "embedding_model": "BAAI/bge-small-zh-v1.5",
  "ts_config": "simple",
  "rrf_weights": [1.0, 1.2],
  "rerank_enabled": false,
  "chunker_config": {"max_chars": 1200, "overlap": 150}
}
```

#### 4. EvalRun（一次运行）

比当前 `evaluation_runs` 表增加：`skipped_reasons`、`error_reasons`、`run_config_json`、`embedding_provider`、`git_sha`

#### 5. EvalResult（单题结果）

比当前增加：`retrieval_rank`、`error`、`question_type`（便于分层报告）

---

### 评分引擎架构

```
EvalSession
  ├── ContentMatchScorer    ← content_contains 子串匹配（Golden/Expense/Enterprise）
  ├── AnswerMatchScorer     ← answer 子串匹配（CRAG）
  └── ExactMatchScorer      ← 精确匹配（预留）
```

- 每个 Scorer 有独立单元测试
- 旧引擎（runner.py / loader.py / run_benchmark.py）与新引擎输出一致后才能切换

### 评分公式

```
Hit@K     = count(hit_at_k) / (total - skipped - expired)   ← expired 题排除
MRR       = avg(rank > 0 ? 1/rank : 0)
Rejection = correct_rejection / total_rejection
Faith     = avg(faithfulness_score)
CI 95%    = bootstrap 1000 次
```

### 指标通胀控制

PR comment 只显示 3 行：
```
✅ 检索：94.2% (Hit@3) — 与基线持平
⚠️ 生成：3/5 题忠实度待审查
📋 完整报告见：link
```

---

## 二、经 4 轮审查确认的隐患修复

### R1: 架构完整性

| 隐患 | 修复 |
|------|------|
| 缺少 EvalConfig | 每次运行序列化完整配置 |
| 缺少 SourceDoc 版本 | TestCase 加 `source_doc_version`，手动 bump |
| 审核签收流程 | `review_signoff.md` 要求 `reviewer != creator` |

### R2: 过渡期风险

| 隐患 | 修复 |
|------|------|
| 新旧引擎分数不一致 | 全量测试集验证输出一致后再切换 |
| 单人审核瓶颈 | 小团队采用 L1+L2 两级审核 |
| 旧脚本断裂 | 标记 deprecated → 3 个月后删除 |

### R3: 数据一致性

| 隐患 | 修复 |
|------|------|
| content_contains 耦合 chunker | 评测前置 `test_validity_check`，不匹配的题自动排除 |
| 计算题分数不可比 | `question_type = calculation` 不计 Hit@K，留 LLM-as-judge |

### R4: 长期维护

| 隐患 | 修复 |
|------|------|
| 测试集膨胀 | 分层运行（fast/standard/extended/full） |
| 指标通货膨胀 | PR comment 精简为 3 行 |

---

## 三、6 周执行计划

### W1：测试集版本化

- 将 `golden_qa.json` / `expense_qa.json` / `enterprise_qa.json` 迁移到目录结构（每个测试集一个子目录）
- 为每个测试集创建 `review_signoff.md` 模板
- 冻结当前版本为 v1.0（废弃旧手动修改的历史）
- 在 `cases.json` 中增加 `question_type`、`match_type`、`source_doc_version` 字段
- 验证：所有 case 字段完整，JSON Schema 校验通过

### W2：统一评分引擎

- 实现 `EvalScorer` 基类 + 3 个策略（ContentMatch / AnswerMatch / ExactMatch）
- 对现有 Golden/Expense/Enterprise/CRAG 各跑一遍新旧引擎对比
- 输出差异报告，逐条分析不一致的原因
- 验证：新旧引擎在 4 个测试集上输出完全一致

### W3：content_contains 从 chunk 提取

- 实现 `scripts/extract_content_contains.py`——入库文档 → 读 chunk 内容 → 人工选择正确答案的 chunk → 自动写入 `content_contains`
- 重建 Enterprise QA（当前 108 题 content_contains 格式不一致）
- 重建 Expense QA（从 chunk 提取，消除格式依赖）
- 新增 `test_validity_check` 前置步骤
- 验证：所有非拒答题的 content_contains 在全文索引中可匹配

### W4：CI 三层门禁

- fast：Golden QA 30 题子集 + mock 嵌入（2 分钟，阻断）
- standard：Golden QA 全量 + 真实嵌入（15 分钟，阻断）
- extended（nightly）：CRAG + Enterprise + RAGBench（30 分钟，告警）
- 回归检测：分数下降 > 2% 发 warning
- 验证：PR 触发 fast + standard，nightly 触发 extended

### W5：CRAG 英文修复 + 外部基准

- 切换到 `bge-small-en-v1.5`（384 维）
- FTS `simple` → `english`（英文词干提取）
- CRAG 数据自动下载（替换当前手动 curl）
- CRAG 全量 4409 题接入 nightly
- `english_qa.json`：删除（20 题死代码）或补全到 100 题
- 验证：CRAG 100 Hit@3 ≥ 70%

### W6：生成评测 + 报告升级

- 逐步补充 `golden_answer`（先补 Golden QA，再补其他）
- LLM-as-judge：双模型投票（DeepSeek + 备用）
- 校准集：预标注 20 题黄金评分，每次运行前验证评分一致性
- 空答案报错，禁止默认满分
- HTML 报告：置信区间 + 分层 + 失败归因 + 趋势
- 验证：校准集评分通过率 ≥ 90%

---

## 四、验收标准

| 阶段 | 通过条件 |
|------|---------|
| W1 | 所有 TestCase JSON Schema 校验通过；review_signoff 有审核人签名 |
| W2 | 新旧引擎在 4 个测试集上输出一致（允许 < 0.5% 偏差逐条备注） |
| W3 | 所有非拒答题 content_contains 在全文中可匹配；Enterprise QA 基线稳定 |
| W4 | PR 创建时自动触发 fast + standard job；nightly 触发 extended |
| W5 | CRAG 100 Hi@3 ≥ 70%；CRAG 全量在 nightly 中报告 |
| W6 | 校准集评分通过率 ≥ 90%；每次 PR 有 3 行精简报告 |

---

## 五、文档清单

| 文件 | 内容 |
|------|------|
| `docs/eval-system-overview.md` | 本文——架构 + 计划 |
| `tests/fixtures/{testset}/v1.0/review_signoff.md` | 每个测试集的审核签收 |
| `docs/eval-scorer-spec.md` | 评分引擎 API 契约 + 单元测试要求 |
| `docs/ci-pipeline-spec.md` | CI 三层门禁配置说明 |
| `docs/eval-report-format.md` | 报告输出格式规范 |
