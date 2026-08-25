# 05 — Impact review（E-B2 / case_count / suite）

> Decide contract impact **before** implementation. Does not revise E-B2 files in this window.

## 1. Questions

| # | Question |
|---|---|
| Q1 | E-B2 schema / contract 是否需要修订？ |
| Q2 | `case_count` 是否变化？ |
| Q3 | 是否需要 **new suite**？ |

---

## 2. Artifact layers（先拆开）

| Layer | Identity today | Holds |
|---|---|---|
| **L-Obs** Observation envelope | E-B2 `w10_eb2_generation_observation_v1` | After slots、targets、eligibility_summary |
| **L-Gold** Claim ledger | **Absent**；拟 `w10_eb_generation_claim_gold_v1` | T2/T3 命题金标 |
| **L-Empty** Empty-gate cases | **Absent**；拟独立 fixture | T4 空闸分母材料 |
| **L-Critic12** W9 frozen | `w9_critic_frozen_12` / 12 cases | Critic 输入槽；**≠** 四靶金标已齐 |

Ground truth 落地 = L-Gold + L-Empty；**不等于**自动改写 L-Obs，但 Full formal 若要声明 T4 空闸 / T2–T3，必须让 L-Obs 合同能诚实引用它们。

---

## 3. Q1 — Does E-B2 schema need revision?

### 3.1 Claim ledger alone

| Change | Need E-B2 revision? |
|---|---|
| 新增独立 claim gold JSON + test-only validator | **No**（旁路协议） |
| Observation 结果绑定 `content_sha256` ↔ ledger | **Optional soft**：可在不改 frozen const 的前提下由 runner 外置校验 |
| 在 E-B2 envelope **内**新增必填 `claim_gold_ref` | **Yes**（升版字段）——**非必须**；本构造 **不要求** 首版把 ledger 内嵌进 E-B2 |

**决议 A：** Claim ledger = **独立协议工件**。E-B2 v1 常量可暂不改；实现窗用外置绑定校验清除 C3。若未来要 envelope 内一等公民引用，另开 **E-B2.1** 字段修订窗。

### 3.2 Empty-gate in the *same* formal observation artifact

若 Full formal 的单一 `FORMAL_OBSERVATION_RESULT` 要包含 empty-gate 案：

| Frozen today | Conflict |
|---|---|
| `suite_id=w9_critic_frozen_12` | 空闸案不是 Critic 冻结 12 成员 |
| `case_count=12` | 加入 ≥1 空闸 ⇒ 计数与成员集合变化 |
| `eligibility_summary.frozen_cases=12` | 同上 |
| `per_case_observation.length == case_count` | 必须同步 |

**决议 B：** 把 empty-gate 写进 **同一** E-B2 v1 信封且保持上述常量 = **非法**。必须修订合同或使用新 suite 信封（见 §5）。

### 3.3 Narrow formal without empty-gate / without T2–T3

| Scope | E-B2 revision needed? |
|---|---|
| `targets_measured ⊆ {T1}` on frozen 12 slots | **No**（仍受 E-B7：合成不可升格 formal 等残余） |
| T2/T3 on C01–C11 After + 外置 ledger | **No** schema const change；需 ledger 文件 |
| T4 `empty_gate_refuse_ok` in Full | **Yes**（suite/count 合同） |

---

## 4. Q2 — Does `case_count` change?

| Scenario | `case_count` |
|---|---|
| Stay on suite `w9_critic_frozen_12` only | **Remains 12** |
| Merge empty-gate into one suite envelope | **Must change**（12+N，N≥1）并改 `suite_id` / eligibility_summary |
| Dual-suite formal（推荐） | 每个信封各自 `case_count`：12 与 N；**禁止**把 12 静默变成 13 却沿用旧 suite_id |

**决议 C：** 不存在「`case_count` 仍写 12、却宣称已测 empty-gate」的合法状态。

---

## 5. Q3 — Is a new suite required?

### Options

| Option | Description | Pros | Cons | Verdict |
|---|---|---|---|---|
| **S0. Pretend 12 includes empty** | 改 C04/C07 语义或硬塞第 13 案不改 id | — | 破坏冻结 Critic 套件；测错层 | **Forbidden** |
| **S1. In-place E-B2 bump** | 新 `protocol_version` / `suite_id`（如 `w10_eb_generation_obs_suite_v2`），`case_count=12+N`，成员 = Critic12 槽 + empty ids | 单一正式结果文件 | 混杂 Critic 槽位套件与 generation 分母叙事；修订面大 | **Allowed backup** |
| **S2. Companion empty suite（推荐）** | 新 suite：`w10_eb_empty_gate_v1`，`case_count=N`；W9×12 信封保持 E-B2 v1；Full formal = 组合报告或双信封 | 不污染 `w9_critic_frozen_12` 含义；T4 分母清晰 | 需定义「Full formal 如何引用双 suite」 | **Primary** |
| **S3. Research harness only** | empty fixture 只跑旁路 pytest，不进 formal envelope | 最快接线 | **不能**清除 Full `E-B_FORMAL_READY` 的 C4 | **Interim only** |

### 决议 D（钉死）

```text
Primary: S2 — new companion suite for empty-gate
Backup:  S1 — single bumped generation suite (explicit rename; never silent 12→13)
Forbidden: S0
Interim: S3 does not clear Full formal C4
```

推荐身份（实现窗冻结字面）：

| Suite | `suite_id` | `case_count` | Purpose |
|---|---|---|---|
| Existing | `w9_critic_frozen_12` | `12` | After 槽位复用 W9 ids（T1/T2/T3 候选）；**不含** empty-gate |
| New | `w10_eb_empty_gate_v1` | `N`（建议 2） | 仅 T4 `empty_gate_refuse_ok` 分母 |

Full formal readiness 叙事改为：

```text
Full E-B formal = E-B2 envelope(s) covering required targets
  ∧ claim gold bound for any T2/T3 measured
  ∧ empty-gate suite present if empty_gate_refuse_ok measured
```

---

## 6. Impact matrix（摘要）

| Deliverable | New suite? | `case_count` change on W9 suite? | E-B2 v1 const revision? |
|---|---|---|---|
| Claim ledger file + validator | No | No | No（外置） |
| Empty-gate fixture only（harness） | Fixture yes / formal suite maybe later | No | No（但不清 C4 formal） |
| Empty-gate in Full formal（S2） | **Yes** | No（W9 保持 12） | **Yes** — 需允许第二 suite / 组合引用（新合同窗） |
| Empty-gate merge（S1） | Replace suite id | **Yes**（12+N） | **Yes** |

**对「是否需要修订 E-B2」的总答：**

- **仅清 C3（claim gold）：** 可不改 E-B2 常量。  
- **要清 C4 并进入 Full formal：** **必须** 合同窗（S2 或 S1），不能假装 v1 的 12 已含空闸。

---

## 7. Recommended implementation sequence（建议，非本窗执行）

1. **E-B9a** — Claim gold ledger schema + empty JSON skeleton + validator（零标注或仅 synthetic 样例行；零 LLM；不写 formal result）  
2. **E-B9b** — Empty-gate fixture + `w10_eb_empty_gate_v1` suite contract（或 E-B2.1 组合引用）  
3. 标注窗 / 授权模型 After 窗 — 绑定真实 hash（清 B2′ + C3 标注）  
4. 仅当 C1–C5 全满足 → 再谈 `E-B_FORMAL_READY`

本窗 **不**打开步骤 3/4。

---

## 8. Gate reminder

```text
E-B_FORMAL_READY = NO
```

| Blocker | After E-B8 |
|---|---|
| B3 claim gold missing | Construct **designed**；file still **missing** |
| B4 empty-gate missing | Construct **designed**；fixture still **missing**；suite strategy = **S2** |
| B2′ formal After | Unchanged residual |

---

## 9. Verdict

| Question | Answer |
|---|---|
| E-B2 schema revision? | **Not for ledger alone**；**Yes before Full formal includes empty-gate** |
| `case_count` changes? | W9 suite stays 12；empty suite has its own N；merged suite would be 12+N under new id |
| New suite required? | **Yes（S2 primary）** for honest T4 empty-gate formal denominator |
| Formal observation opened? | **No** |
