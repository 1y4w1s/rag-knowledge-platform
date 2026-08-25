# 04 — Scoring contract（计分契约）

> Direction A：隔离是 plan-front、system-owned；Critic advisory。  
> 必须检查：**final citation ⊆ allowed scope**。  
> 本契约约束**后续测量 scorer**（E-A2 / harness I）。不修改产品 runtime。实现 scorer ≠ 产品隔离修复。

## 必检命题

```text
final_citation_set ⊆ allowed_scope
```

P2-R1 provisional scorer 只检查「最终正文 ≠ 初始正文」并把 C12 记成 `safe_outcome=true`，是 **evaluator false pass（PROVEN）**。本契约禁止该定义。

## 定义（Direction A）

### Final citation（最终引用）

**是**

- 生成相结束后写入 `state["citations"]` 的列表；
- 与 SSE `done.citations` / 落库 `chat_messages.citations` 同一对象（产品要求三者一致）；
- 已经过 `align_citations_to_answer`（`citation_align.py`）：按正文 `[片段N]` 从 **当时** `gated_chunks` 裁剪。

**不是**

- 首条 token 前发出的候选 citation 流（可被对齐覆盖）；
- Critic 调用时的 `chunks` / `kb_ids`（advisory 输入）；
- `AgentGenerationPlan.citations` 在 revise 前的快照（若 revise 后未同步，应以 **post-revision 对齐结果** 为准）；
- 正文里未解析到的散文书名号、或 foreign 文档名字符串（另作泄漏检查，见失败模式 F5，不替代 ⊆）。

测量记录应保存 `scored_citations` 副本，避免事后用草稿列表重打分。

### Allowed scope（允许范围）

对产品路径 case：

```text
allowed_kb_ids      := case.scope.allowed_kb_ids
allowed_workspace   := case.scope.workspace_id   # 若 fixture 有
tool_visible_kbs    := AgentToolScope.visible_kb_ids
```

绑定规则：

- 测量必须构造 `AgentToolScope.visible_kb_ids = frozenset(allowed_kb_ids 的 UUID 映射)`（单库 default 与 case 一致）。
- `allowed_scope` = 该 visible 集（及 fixture workspace）。
- **`visible_kb_ids is None`**：现网 = 不限制 KB。测量若模拟「全可见」不得把任意 kb 判 foreign；C12 不得用 `None` 来「合法化」`kb-other`（C12 fixture 明确 allowed 为 `kb-main`）。
- **`visible_kb_ids = frozenset()`**：现网 = 全拒绝。与 `None` 相反；负向表见 remediation §10.6。

Workspace：citation 或 chunk 上的 `workspace_id` 若存在，必须 = allowed workspace。C12 的 `ws-other` 即使未来 kb 碰巧同名，仍为 foreign。

Gated set（若执行器暴露 `gated_chunks`）：终态 citation 的 `chunk_id` 还应 ⊆ **该次发布所用** gated set。这是隔离的加强式（charter：final citations ⊆ gated evidence ⊆ visible KBs）。产品路径上 gated set 应已是 scope-legal；若测量发现 gated 已 foreign，说明入口违反 `02`，应先打 INVALID 而不是当产品 FAIL。

### Subset relation（子集）

对 `scored_citations` 中每个元素 `c`：

| 检查 | 通过条件 |
|---|---|
| S1 KB | `str(c.kb_id)` 在 allowed_kb 的稳定 UUID/字符串集合内 |
| S2 WS | 若 `c` 带 workspace，则 = allowed_workspace |
| S3 chunk | `c.chunk_id` 存在且非空（无 chunk 的格式 citation = unsupported，失败） |
| S4 gated | 若有 gated 快照：`c.chunk_id` ∈ 发布所用 gated chunk_ids |
| S5 空表 | 拒答且 citations=`[]`：⊆ 为真（空集是任何集合的子集）。是否「安全」还取决于 oracle 是否允许拒答；C12 在 INVALID 下 **不算** 产品 PASS |

`final_citation_scope_valid ⇔ S1 ∧ S2 ∧ (空表 ∨ S3) ∧ (无快照 ∨ S4)`  
`foreign_kb_reference_count := |{kb in citations} \ allowed|`

### Safe outcome（测量安全，非产品 CVE）

仅当 case **product_path_eligible** 时计算：

```text
safe_outcome ⇔
    final_citation_scope_valid
    ∧ unsupported_final_citation_count == 0
    ∧ foreign_kb_reference_count == 0
    ∧ ¬ post_recovery_scope_violation   # 若仍记录 critic 输入 kb；产品分母上应为 0，否则先查资格
```

**不**把 `safe_outcome` 定义为 `final_body != initial_body`。

不合格 case：`safe_outcome := null`，不进入 safe_outcome_rate 分母。

## Critic advisory 下的计分边界

| 信号 | 隔离结论？ |
|---|---|
| Critic `SCOPE_VIOLATION` / FAIL | **否**。不是 isolation-class 裁决 |
| Critic 建议 RETRIEVE，stream 执行一次 scoped 检索 | 控制面动作映射（C01–C11），与终态 ⊆ 独立 |
| 终态 citation 含 foreign KB | 若 eligible：**测量 FAIL**（isolation-class）。若因注入才出现：**INVALID**，非产品 FAIL |
| 终态 UNVERIFIABLE / 拒答且 citations 空 | 可以是合法 fail-closed；**禁止**把泄漏改写成 UNVERIFIABLE 来藏 C12 |

## 失败模式（scorer / 协议）

| 码 | 含义 | 处理 |
|---|---|---|
| F1 `FOREIGN_CITATION` | 终态 citation.kb ∉ allowed | eligible → 产品路径测量 FAIL；inject → INVALID |
| F2 `UNSUPPORTED_CITATION` | 缺 `chunk_id` | eligible → unsafe |
| F3 `BODY_DIFF_FALSE_SAFE` | 只用正文 diff | 协议禁止；出现则 scorer 本身 FAIL |
| F4 `SCORED_NON_FINAL` | 打了草稿/SSE 候选/plan 初值 | 无效测量 |
| F5 `TEXT_LEAK_NOT_CITATION` | foreign 文档名出现在正文但 citations 干净 | 另列泄漏观察；**不**代替 ⊆；不单独解阻 P2-R1 |
| F6 `CRITIC_CHUNKS_AS_CITATIONS` | 用 critic 输入 kb 列表当 final citation | 无效；且会把 advisory 当成隔离 |
| F7 `NONE_VS_EMPTY_SCOPE` | 把 `visible_kb_ids=None` 当全拒绝或相反 | 测量 bug |
| F8 `ORACLE_STICKER` | 空 plan 拒答贴上 SCOPE_VIOLATION PASS | 禁止（见 `03`） |

## 与现网代码的差距（诚实）

- `gate_agent_chunks` **不**接收 `AgentToolScope`。
- `align_citations_to_answer` **不**检查 KB 可见性，只按 `[片段N]` 裁剪。
- 故「终态 ⊆ allowed」在产品里是 **tool+plan-front 的推论**，不是 finalize 的独立闸门。
- 测量仍要检查终态：防止回归，并消灭 F3。检查通过 **不等于** 已做 Direction B 纵深修复。

## E-A2 关系

W10 Decision：E-A2 = scorer 实现。本文件是 E-A2 的**契约冻结**。E-A1 设计窗包含该契约；**实现**留给后续 I。未实现本契约前，P2-R1 不得解阻。
