# 睿阁 RAG 数据诚实性 · 事后复盘（Postmortem）

> 日期: 2026-07-19
> 触发: 全量审计发现评测体系系统性高估系统真实能力
> 结论: 四层问题叠加，每一层都在让数字变得更好看

---

## 时间线

1. **自建测试集阶段**：创建 Golden/Expense/Enterprise QA，content_contains 从 chunk 提取，拒答题计入 Hit@K
2. **"校准"阶段**：Expense QA 修断言格式 41%→92%，Enterprise QA 循环校准 56%→98%
3. **CI 建设阶段**：benchmark.yml 默认 mock_embedding=true，regression.yml 硬编码 mock，conftest.py autouse fixture 强制 mock
4. **CRAG 测试阶段**：测出 19%，标记为"诚实基线"而非"系统严重缺陷"
5. **审计发现**：2026-07-19 全面审计发现 CI 从未用真实嵌入、评分 6 个 bug、Enterprise QA 虚高 18pp

## 根因分析

### 第一层：测试集设计（利益冲突）
- 出题人 = 评分人 = 验收人
- content_contains 从检索源提取 → 循环验证
- 拒答题计入 Hit@K → 免费分
- 断言格式不匹配文档 → 修断言不修系统

### 第二层：无外部队考
- CRAG 19% 被接受为"诚实基线"而非告警信号
- RAGBench/MIRAGE 加载器代码存在但从未跑过
- LLM-as-Judge 用同一模型分解+验证

### 第三层：CI 门禁形同虚设
- benchmark.yml 默认 mock_embedding=true
- regression.yml 硬编码 RAG_REAL_EMBEDDING=0
- conftest.py autouse fixture 强制全 mock
- test_retrieval_golden.py 用 SHA256 哈希伪向量

### 第四层：组织文化
- "演示能过就行" → 数字优先于真相
- 没有人问"这些 95% 真的代表系统好吗？"
- CRAG 19% → "诚实基线" 而非 "我们完蛋了"

## 修复计划

### P0（已执行）
- ✅ 跑出所有测试集的真实嵌入基线
- ✅ 修复 runner.py 6 个评分 bug
- ✅ 记录 docs/real-baseline-2026-07-19.md

### P1（待实施）
- 改 README 诚实基线
- 修复 embedder.py 静默 mock 降级→显式告警
- CI 加 RAG_REAL_EMBEDDING=1 job

### P2（待实施）
- 重建 Enterprise QA content_contains
- Golden QA 去重 + 拒答题独立报告
- Expense QA 精确匹配替代格式依赖

## 教训

1. **自建测试集必须配有独立审核** 或外部标准集作为对照
2. **CI 门禁必须使用真实嵌入**，否则门禁不捍卫 RAG 质量
3. **校准必须先校准评测本身**，再校准系统
4. **外部队考不应被选择性忽略**——低分是高优先级的告警，不是"诚实基线"
