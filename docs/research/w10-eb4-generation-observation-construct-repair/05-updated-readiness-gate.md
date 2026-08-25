# 05 — Updated readiness gate

> Binary gate definition after construct repair design.  
> **This window does not flip the gate to YES.**

## Gate status today

```text
E-B_FORMAL_READY = NO
```

理由：本窗只交付构造；B1–B4 的 **落地工件**仍缺（executor 代码、After 快照、claim gold 文件、empty-gate fixture / 合同修订）。

---

## 1. Vocabulary

| Symbol | Meaning |
|---|---|
| `E-B_FORMAL_READY` | 是否允许开启 **正式** generation observation 执行窗并写出 `artifact_kind=FORMAL_OBSERVATION_RESULT` |
| Full formal | `targets_measured` 意图覆盖 E-B1 四靶（T1–T4，含 `empty_gate_refuse_ok`） |
| Narrow formal | `targets_measured` **诚实子集**（例如仅 T1）；仍须满足该子集的条件 |

E-B2 允许的对外声称仍仅：

```text
generation observation artifact produced
```

禁止：`generation quality proven` / `grounding proven` / `Critic validated`。

---

## 2. Exact conditions for `E-B_FORMAL_READY = YES`（Full formal）

下列 **全部** 为真时，且仅当全部为真，全四靶正式窗才可标 YES：

### C1 — After-window executor exists

- [ ] Test-only（或约定模块）提供正式观测执行入口（对标 `run_formal_window`）  
- [ ] Eligible 路径经 `prepare_agent_generation` → `_stream_generation_phase` **或** `01` 允许的诚实同构 After 写入  
- [ ] C12 → `INELIGIBLE` / 不进分母  
- [ ] 不调用 `execute_frozen_case`；不复用 P2-R3 runner 身份  
- [ ] 产出通过 E-B2 `validate_reserved_artifact`（正式 kind）

### C2 — After snapshots obtainable

- [ ] 分母案可写出非 null 的 `final_content_observation` 与 `final_citations`（拒答案 citations 可为 `[]`）  
- [ ] 来源遵守 `01`；**禁止** W9 fixture `answer`/`citations` 回填  
- [ ] `observation_point` 仍为 `generation_final_content_and_citations`  
- [ ] `llm_called` 与真实是否调模型一致  

### C3 — Independent claim gold for T2/T3

- [ ] 存在独立 claim gold 规程 + ledger（见 `02`/`03`）  
- [ ] 每个 T2/T3 分母案的 After 正文 hash 与金标绑定  
- [ ] **零** Critic oracle 键；E-B2 禁键仍失败关闭  
- [ ] T3 grounded 采用 G1∧G2（或 artifact 脚注写明的冻结规则）  

### C4 — T4 empty-gate denominator

- [ ] 至少一条 eligible empty-gate research case（见 `04`）  
- [ ] 经产品 prepare 可得 `gen_plan.refusal=true`  
- [ ] 合同层已处理与 `suite_id=w9_critic_frozen_12` / `case_count=12` 的关系（**修订 E-B2 合同**或 **分 suite 引用**二选一，且文档钉死）  
- [ ] C04/C07 **未**被标为 `empty_gate_refuse_ok` 金标  

### C5 — Envelope / claim / control-plane hygiene

- [ ] E-A5 artifact 仍不能通过 E-B2 validator  
- [ ] `p2_r1_status=BLOCKED` ∧ `does_not_unblock_p2_r1=true`  
- [ ] `measurement_claims.asserted` ⊆ allowed  
- [ ] 进度文案不把 E-A5 11/11 与 generation observation 合并  

**Full YES ⇒ C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5。**

---

## 3. Exact conditions for narrow-window YES（可选）

若 owner 明确只要 **窄正式窗**，可另标：

```text
E-B_NARROW_FORMAL_READY = YES
```

**当且仅当：**

| Required | Note |
|---|---|
| C1 | Executor 存在 |
| C2 | After 快照可写 |
| C5 | 信封卫生 |
| `targets_measured` ⊆ 可支撑集合 | 例：`["T1"]` 仅同构 align；**不得**暗含 T2/T3/T4 空闸 |
| 缺金标/空闸靶显式排除 | artifact `invalid_reasons` / notes 诚实 |

**窄窗 YES ≠ Full `E-B_FORMAL_READY`。**  
进度与 PR 标题必须写「narrow / T1-only」等限定，禁止写成「E-B 四靶正式观测已就绪」。

E-B3 思想实验已指出：即便仅 T1，今日仍缺 C1/C2 → 窄窗今日亦为 NO。

---

## 4. Mapping: E-B3 blockers → clearance

| Blocker | Cleared when | Cleared in E-B4? |
|---|---|---|
| B1 No After executor | C1 | **No**（仅设计） |
| B2 No After snapshots | C2 | **No** |
| B3 T2/T3 claim gold | C3 | **No**（策略已选：独立人工 ledger） |
| B4 T4 empty-gate case | C4 | **No**（fixture 仅设计） |

---

## 5. What must remain true even after YES

| Invariant | Remains |
|---|---|
| Direction A ownership | plan-front L0 |
| Critic advisory | 不得当隔离主人 / 生成金标 |
| P2-R1 | BLOCKED |
| E-A5 meaning | plan-construction citation scope only |
| Forbidden product claims | quality / grounding / Critic validated |

YES 只许可：**开正式 observation 执行并落 E-B2 信封结果**。  
不许可：Critic 默认 ON、P2-R1 解阻、Multimodal、把结果写成 PRD §2.1 已产品验收完毕。

---

## 6. Recommended next windows（仅建议；本窗不执行）

**推荐（1）：** W10 E-B5 — After-window observation executor（test-only）  
严格只做：按 `01` 实现最小 executor + 零 LLM 同构 T1 路径；不写正式结果（或仅 schema smoke）；不改 `backend/app`；不建 empty fixture。

**备选（一句）：** W10 E-B5b — Empty-gate fixture + E-B2 suite contract revision（若 owner 优先 T4 分母）。

Claim gold ledger 实施可紧随首个能产出 After（或合成正文）的窗，作为独立原子任务。

---

## 7. Stop

```text
E-B_FORMAL_READY = NO
```

构造修复设计完成。禁止以本目录为「可开跑」依据。
