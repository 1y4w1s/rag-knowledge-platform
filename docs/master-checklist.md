# 睿阁 RAG 系统 · 全量交付清单（最终版）

> 生成: 2026-07-19 · 废弃所有旧计划文档（remaining-issues-plan.md、fix-plan.md、final-plan-v3.md）
> 当前状态：全部已知问题已排查，剩余待做项在末尾

---

## 评测基线（已完成）

| 测试集 | 类型 | 题数 | Hit@3 | MRR | Faithfulness |
|--------|------|------|-------|-----|-------------|
| Golden QA | 自建中文（9 领域 L1-L4） | 109 | **95.5%** | — | **89%**（50/90 题） |
| Expense QA | 自建中文（断言校准后） | 105 | **~91%** | — | — |
| Enterprise QA | 自建中文（测试集校准后） | 108 | **~25%** | — | — |
| Real Docs | 真实中文文档（外部验证） | 30 | **70%** | — | — |
| CRAG English | 外部英文 Wikipedia | 100 | **26%** ✅ 诚实基线 | — | — |
| Citation Accuracy | 对话 SSE 事件 | 5 轮 | **100%** | — | — |
| 并发压测 | health | 50 req/s | P50 **834ms** | — | — |

注：Enterprise QA 原始宣称 98% 因短值/重复 content_contains 假阳性，修复后为诚实基线约 25%。CRAG 原 19%（中文模型）→ 26%（bge-small-en）。

---

## 已完成工作（全量）

### 检索 & 嵌入
- BGE-small-zh 512-dim via fastembed ONNX CPU，9ms/query
- 三组完整模型消融
- 零外部依赖：无阿里云 API，无 GPT，无 GPU
- RRF 权重消融：w_f=1.2 最优
- **英文嵌入**：bge-small-en-v1.5 384-dim，语言检测自动切换列
- **CRAG 修复**：19% → 26%（切换英文模型）

### 切片
- 结构优先：heading-path 追踪，按 section 边界分割
- min_chars=400，max_chars=1200，overlap=150
- Parent-Child 结构

### 生成
- SYSTEM_PROMPT 强制引用 + 安全防御注入
- Citation SSE 事件
- 无依据拒答 + verify_answer 自验证
- 多轮对话 contextualize_query + compress_history

### 评测体系重建
- **测试集版本化**：3 个测试集迁移到 v1.0 目录 + JSON Schema + review_signoff
- **统一评分引擎**：ContentMatchScorer + AnswerMatchScorer + ExactMatchScorer（15 单元测试）
- **W3 chunk 提取**：Enterprise QA 108 题 content_contains 全部从实际 chunk 提取
- **W4 CI 门禁**：rag-benchmark job（真实嵌入 + HF 镜像 + 模型缓存 + 基线对比 2% 门禁）
- **W5 英文嵌入**：migration 035 + bge_en + 语言检测 + 双列检索
- **W6 生成评测**：322 题 golden_answer + 20 题校准集 + Judge 流程
- **诚实基线**：README 已更新

---

## 未完成（推迟到下次）

| 优先级 | 项 | 工作量 | 说明 |
|--------|----|--------|------|
| **P1** | 新评分引擎正式切换 | 半天 | 当前 CI 仍用旧引擎 |
| **P1** | CRAG 4409 全量接入 nightly | 半小时 | run_crag.py 已就绪 |
| **P2** | 校准集接入 Judge pipeline | 半小时 | verify_calibration 已实现 |
| **P2** | 清理脚本挂 cron | 10 分钟 | cleanup_eval_runs.py 已就绪 |
| **P3** | Docker 多阶段构建 | 1 天 | 减小镜像体积 |
| **P3** | 多跳检索（RAPTOR/Self-RAG） | 实验性 | 需要先有客户场景 |

---

## 最终 README 基线表（诚实版）

```
| 测试集 | 类型 | 题数 | Hit@3 | 说明 |
|--------|------|------|-------|------|
| Golden QA | 自建中文 | 109 | 95.5% | 含20拒答题独立报告 |
| Expense QA | 自建中文 | 105 | 91.1% | 数字格式已对齐 |
| Enterprise QA | 自建中文 | 108 | ~25% | 诚实基线，修复短值/重复后 |
| Real Docs | 真实中文文档 | 30 | 70% | 样本较小 |
| CRAG English | 外部英文 Wikipedia | 100 | 26% | bge-small-en-v1.5 |
| Faithfulness | 生成忠实度 | — | — | 待 LLM-as-judge 评估 |
```
