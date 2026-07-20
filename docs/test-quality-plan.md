# 睿阁评测体系 · 测试集质量优化计划

> 基于 2026-07-20 人工审核发现。共 16 个问题，分为 3 个优先级。

---

## 问题清单

### 🔴 P0：立即修（影响基本可用性）

| # | 问题 | 数据集 | 影响 |
|---|------|--------|------|
| 1 | **标准答案与文档事实不符**（产品定价混淆、功能张冠李戴、关键信息遗漏） | Golden/Expense/Enterprise | golden_answer 不可用于生成评测 |
| 2 | **测试用例字段逻辑矛盾**（expect_rejection=true 但有详尽 golden_answer） | 部分用例 | 拒答题的 golden_answer 应为固定文案 |
| 3 | **测试用例大量重复，评测权重失衡** | Golden QA | 同主题的多道题共用同一 content_contains |

### 🟡 P1：本周修（影响评测可信度）

| # | 问题 | 数据集 | 影响 |
|---|------|--------|------|
| 4 | **文档与测试用例对应关系断裂**（引用的源文档在知识库中不存在） | Enterprise QA | 检索目标缺失 |
| 5 | **同一文档内部标准冲突**（如市内交通费标准前后不一） | Expense QA | 答案不唯一 |
| 6 | **golden_answer 格式不统一**（部分直接回答无引用来源） | 全部 | 不便于人工审核 |
| 7 | **Golden QA difficulty 机器映射未经人工审核** | Golden QA | 分层报告不可信 |
| 8 | **Expense QA 仍格式敏感**（~92% 实际是格式对齐，真实 41%） | Expense QA | 分数虚高 51pp |
| 9 | **Golden QA 混入 2 道英文题**（GQ-4/GQ-10，拖慢 CI 2 分钟） | Golden QA | CI 效率 |
| 10 | **GQ-103 query="钱" 无测试价值** | Golden QA | 测试质量低 |

### 🟢 P2：后续优化（提升区分度）

| # | 问题 | 数据集 | 影响 |
|---|------|--------|------|
| 11 | **部分测试问题表述模糊，答案不唯一** | 全部 | 评分标准不明确 |
| 12 | **缺乏多文档冲突、跨文档推理、表格计算、时效性及对抗性场景** | 全部 | 测试覆盖不足 |
| 13 | **缺少对非文本内容（Mermaid 流程图、图表）的解析测试** | Golden QA | 格式覆盖不足 |
| 14 | **拒答题测试过于简单，缺乏微妙"无法回答"场景** | Golden QA | 拒答区分度不足 |
| 15 | **Enterprise QA source_doc 格式不统一**（数组/字符串混用） | Enterprise QA | 加载器兼容性风险 |
| 16 | **校准集 20 题全是直通题，无幻觉/部分匹配检测** | 校准集 | 不能发现 Judge 降级 |

---

## 修复方案

### P0-1：标准答案人工审核

**当前**：322 题 golden_answer 全部由 DeepSeek 生成，0 题人工审核。

**修复**：
- 对 Golden QA 109 题，逐题对照 `golden_handbook.md` 审核 golden_answer
- 对 Expense QA 105 题，逐题对照 `expense_policy.md` 审核
- 对 Enterprise QA 108 题，逐题对照 6 份 `acme_*.md` 审核
- 发现错误：修正答案或标记 `golden_answer_needs_review: true`
- 每审完 20 题保存一次

**工作量**：3 天（人工）

### P0-2：拒答题 golden_answer 规范化

**当前**：部分 `expect_rejection=true` 的题，golden_answer 写了详尽回答。

**修复**：
- 全量扫描 3 个测试集，找出 `expect_rejection=true` 但 `golden_answer` 内容过长的题
- 统一改为：`"该问题在文档中无相关信息，应拒绝回答。"`
- 在 JSON Schema 中加校验规则：`expect_rejection=true → golden_answer 长度 < 30 或等于固定文案`

**工作量**：1 小时

### P0-3：重复 content_contains 去重

**当前**：27 组 content_contains 在多道题中重复出现。

**修复**：
- Golden QA：对每个重复值，保留最匹配的题，其余 26 题替换为文档唯一片段
- Expense QA：同上
- Enterprise QA：已在 W3 chunk 提取中处理，仅余 2 组

**工作量**：2 小时

### P1-4：源文档引用修复

**当前**：Enterprise QA 部分 `source_docs` 引用不存在的文档名。

**修复**：
- 逐题验证 `source_docs` 字段，与实际文件 `acme_*.md` 匹配
- 不匹配的题标注 `source_doc_mismatch: true`
- 在 benchmark 脚本中添加校验：`source_docs` 指向的文件必须存在

**工作量**：1 小时

### P1-5：内部冲突标注

**当前**：Expense QA 中市内交通费存在两个不同标准。

**修复**：
- 标注冲突位置为 `ambiguous: true` + 说明文档哪段有冲突
- LLM-as-judge 评估时，接受任一答案为正确

**工作量**：30 分钟

### P1-6：golden_answer 格式统一

**当前**：格式不统一，有的带引用有的不带。

**修复**：
- 定义标准格式：
  ```
  [答案] [来源：文档名, 第X章]
  ```
- 对现有 golden_answer 做格式化处理
- 后续生成时用统一模板

**工作量**：1 小时

### P1-7：difficulty 人工复审

**当前**：109 题 difficulty 是机器映射的（数值→L1-L4）。

**修复**：
- 定义 L1-L4 统一标准文件 `docs/difficulty-standard.md`
- 对 Golden QA 109 题逐题人工重新标注
- Expense QA 和 Enterprise QA 统一用新标准

**工作量**：2 小时

### P1-8：Expense QA 格式无关化

**当前**：~92% 是格式对齐的结果，真实基线 41%。

**修复**：
- 对 content_contains 做数值标准化：`1,000` → `1000`，`壹仟` → `1000`
- 生成标准化版本 `expense_qa_normalized.json`
- 在报告中同时报告原始分数（41%）和标准化分数（~90%）

**工作量**：2 小时

### P1-9：移除无用英文题

**修复**：
- GQ-4/GQ-10 从 Golden QA 移除
- 加入到单独的中英混合测试集中

**工作量**：15 分钟

### P1-10：GQ-103 优化

**修复**：
- query 改为明确的查询（如"年终奖的发放时间是什么？"）
- 或改为 `expect_rejection=true`（单字查询应拒答）

**工作量**：5 分钟

### P2-11~16：场景扩展

**修复**：
- P2-11：模糊问题标注 `ambiguous: true`，允许容错匹配
- P2-12：新建 10 道跨文档推理题 + 5 道表格计算题 + 5 道时效性题
- P2-13：从 golden_handbook.md 的 Mermaid 图中提取文本问题
- P2-14：新建 5 道"微妙无法回答"题（如"张三年假有几天？"——文档只有部门级政策，无个人数据）
- P2-15：统一 `source_docs` 为数组格式 `["acme_XX.md"]`
- P2-16：校准集新增 5 道幻觉检测 + 5 道部分匹配题

**工作量**：3 天

---

## 执行路径

```
第一轮（P0，今天）：
  ├── P0-2：拒答题 golden_answer 规范化（自动脚本）
  ├── P0-3：重复 content_contains 去重（人工逐题）
  └── P1-9、P1-10：删 GQ-4/GQ-10 + 修 GQ-103

第二轮（P0+P1，本周）：
  ├── P0-1：golden_answer 人工审核（分批，你审 + 我改）
  ├── P1-4：源文档引用修复
  ├── P1-5：内部冲突标注
  ├── P1-6：golden_answer 格式统一
  ├── P1-7：difficulty 人工复审
  └── P1-8：Expense QA 格式无关化

第三轮（P2，下周）：
  └── P2-11~16：场景扩展
```

---

## 当前状态

| 步骤 | 状态 |
|------|------|
| P0 规划 | ✅ 本文件 |
| P0 实施 | ⏳ |
| P1 实施 | ⏳ |
| P2 实施 | ⏳ |
