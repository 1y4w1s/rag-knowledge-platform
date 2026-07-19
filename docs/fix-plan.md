# 睿阁缺陷修复计划（可补项全量）

> 基于 `docs/deep-assessment.md` 的缺陷分析，按难度排序。

---

## A组：快速修复（< 1小时）

| # | 缺陷 | 修复方案 | 预计时间 |
|---|------|----------|----------|
| A1 | 句子边界覆盖不全 | 补省略号 `……`、破折号 `——`、英文冒号 `:` 到 SENTENCE_END 正则 | 10min |
| A2 | rerank 消融空白 | 运行 benchmark 对比 rerank_on vs rerank_off | 30min |
| A3 | 测试脚本清理 | 删除 `tests/benchmark/tests/_*.py` 中除 `_generate_*` 外的脚本 | 10min |
| A4 | Faithfulness Judge prompt 优化 | 创建独立的 Judge prompt，不共享生成时的 system prompt | 30min |

## B组：半天级

| # | 缺陷 | 修复方案 | 预计时间 |
|---|------|----------|----------|
| B1 | 英文泛化验证 | 创建 `english_qa.json`，用 CRAG snippet 做 20 题+翻译测试 | 4h |
| B2 | 引用 post-processing | LLM 输出后检查 [片段N] 有效性，无效时追加引用标注 | 4h |
| B3 | 评测入口统一 | 将 Faithfulness + Citation 评测集成到 `run_benchmark.py --mode full` | 4h |
| B4 | CI pipeline 验证 | 本地运行 CI 的 test 步骤，确认 pytest 和 alembic 可跑通 | 2h |
| B5 | Forget Password 页面 | 前端创建重置密码表单 + 验证流程 | 4h |

## C组：1天级

| # | 缺陷 | 修复方案 | 预计时间 |
|---|------|----------|----------|
| C1 | 跨页断裂 | 切片器增加 transition 检测：如果连续两个 block 的 page_number 不同，在切分点强制分割 | 1d |
| C2 | 缓存一致性 | 文档更新/删除时调用 cache.invalidate() 清除相关查询缓存 | 1d |
| C3 | Docker 多阶段构建 | 构建阶段用 python:3.11-slim，运行阶段复制编译产物 | 1d |

---

## 执行顺序

```
Day 1: A1 → A2 → A3 → A4 → B4  （快速修复 + CI确认）
Day 2: B1 → B3                  （英文测试集 + 评测入口）
Day 3: B2 → B5                  （引用验证 + 重置密码页）
Day 4: C1 → C2 → C3             （能力项）
```
