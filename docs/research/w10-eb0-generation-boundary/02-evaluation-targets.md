# 02 — Evaluation targets（四靶分类）

> 每靶只分类，不实施。标签：`not_yet_measured` · `blocked_on` · `candidate_metric`。  
> 候选指标供 **E-B1 契约** 引用；**不是**本窗或 E-B1 的执行命令。

产品锚点（需求，非测量）：[`docs/PRD.md`](../../PRD.md) §2.1 — 每条 AI 回复必须有引用（文档名 + 位置 + 片段）；无依据须明确拒答、禁止无引用胡编。

---

## 1. Unsupported claims（无依据断言）

| 项 | 内容 |
|---|---|
| **产品含义** | 正文出现知识库未支持的事实性命题（胡编 / 张冠李戴） |
| **L0 是否已测** | **否** |
| **分类** | `not_yet_measured` |
| **blocked_on** | （1）生成正文观察点；（2）claim 切分与金标，**不能**复用 E-A2 的 `unsupported_final_citation_count`（那是缺 `chunk_id`）；（3）冻结 12 是 Critic/claim-status 套件，C03 名称 ≠ 已测「正文无依据」 |
| **candidate_metric** | 在声明的 claim 集合上：`unsupported_claim_count`、`unsupported_rate = unsupported / asserted_claims`；分母不含拒答空正文。可选二级：foreign 文档名出现在正文（E-A1 F5）——**观察项**，不替代接地 |
| **L0 易混淆点** | E-A5 C03 `scope_compliance_pass=true` 只说明 **plan 引用** scope-safe |

## 2. Citation preservation（引用保全）

| 项 | 内容 |
|---|---|
| **产品含义** | 生成+对齐之后，用户看到的引用仍对应本次 gated 证据，且与正文标记一致；不丢合法引用、不把未使用片段伪装成「用过」（过引）除非走 keep-all 策略 |
| **L0 是否已测** | **否**（只测了生成前 `gen_plan.citations ⊆ scope`） |
| **分类** | `not_yet_measured` |
| **blocked_on** | `_stream_generation_phase` 或同构「假正文 → `align_citations_to_answer`」执行器；keep-all vs shrink 必须**分桶**计分，否则漏标假绿 |
| **candidate_metric** | `plan_ids`、`final_ids`；`preservation_recall = \|final ∩ plan\| / \|plan\|`（keep-all 桶预期 ≈1 但 **不得**当 grounding PASS）；`overcite_rate` 仅在 **有合法 `[片段N]`** 桶计算（TECH §5.12：有标记时过引目标为 0）；非法下标丢弃计数 |
| **L0 易混淆点** | 11/11 plan scope ≠ 引用在回答里被用到 |

## 3. Answer grounding（答案接地）

| 项 | 内容 |
|---|---|
| **产品含义** | 回答中的可核验命题能在 gated excerpt（文档名+位置+片段）中定位；答辩可指着引用证明出处（PRD §2.1） |
| **L0 是否已测** | **否** |
| **分类** | `not_yet_measured` |
| **blocked_on** | L1 草稿；金标或评审规程；**禁止**用 Hit@3 11/11 代替（`test_retrieval_golden.py` 只打检索） |
| **candidate_metric** | 命题级 `grounded_rate`；或答案–引用对齐（每条 final citation 是否在正文被提及 / 每条断言是否映射到至少一条 citation）。**不**把 eval-L1 Critic EXACT 当第一靶（P3-R1 超时；Critic 默认关） |
| **L0 易混淆点** | Prompt 只含 gated chunks（L0 准入）≠ 模型只根据它们说话 |

## 4. Refusal behavior（拒答行为）

| 项 | 内容 |
|---|---|
| **产品含义** | 无依据 → 明确「未找到」类拒答、**无**胡编引用列表；有依据 → 不因测量超时或 Critic advisory 单独拒答（runtime-policy / E-A1） |
| **L0 是否已测** | **部分代码存在、本窗测量为零** |
| **分类** | `not_yet_measured`（正式窗）+ 机制 `candidate_metric` 可先在零 LLM 下用空 gated fixture 测 **L0 闸**（那是 L0 回归，**不是** L1 生成质量） |
| **blocked_on** | 冻结 12 **无** eligible 空检索案；C07 不能当「应拒」金标（E-A5 `plan_refusal=false`） |
| **candidate_metric** | `empty_gate_refuse_ok`（refusal 正文 + `citations=[]`）；`false_refuse_rate`（有 gated 仍固定拒答）；`refuse_with_citations` 视为协议失败（与 PRD「无依据禁止无引用胡编」相反的另一种病：无依据却带着 chips） |
| **L0 易混淆点** | `safe_outcome=True` 对空 citation 在 E-A1 S5 下可以成立（空集 ⊆）；若窗口把 E-A2 `safe_outcome` 当成「正确拒答」，会 **假绿**（E-A3 已警告） |

---

## 与检索门禁的边界

| 已证明（检索） | 未证明（生成） |
|---|---|
| Golden Hit@3：相关 chunk 是否进 Top-3 | 模型是否用这些 chunk 回答 |
| mock 嵌入下的排序回归 | 真实 chat 模型 faithfulness |
| 拒答 **检索题**（golden 含 refuse 类题时测的是检索是否该空） | 生成相是否遵守拒答话术与空 citation |

W10 生成平面评测 **不得**把 `pytest tests/test_retrieval_golden.py` 当作 L1 DoD。动检索仍须过该门禁；那是另一条线。
