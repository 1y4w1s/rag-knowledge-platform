# 02 — Formal observation scope (intended first window)

> Defines the **exact** first formal window that would be allowed **if and only if** `E-B_FORMAL_READY` flips YES.  
> **This window does not authorize execution.** Current authorization = **NONE**.

---

## 0. Current authorization

```text
AUTHORIZED_FORMAL_OBSERVATION_WINDOW = NONE
```

Until exact blockers in `04-final-gate.md` clear:

- No `_stream_generation_phase` formal run
- No reserved `FORMAL_OBSERVATION_RESULT` with `measurement_valid=true`
- No dual-suite formal combo write
- No annotation-as-measurement shortcut

---

## 1. Intended first **Full** formal window（目标态 · 未授权）

### 1.1 Targets

| Target | In first Full window? | Denominator source |
|---|---|---|
| **T1** Final citation scope preservation | **Yes** | After `state["citations"]` vs plan/gated scope on eligible W9 slots |
| **T2** Unsupported claim observation | **Yes** | After `state["content"]` + independent claim gold |
| **T3** Answer grounding observation | **Yes** | After content+citations + claim gold (G1∧G2) |
| **T4** `empty_gate_refuse_ok` only | **Yes** | Companion empty-gate suite（not `false_refuse_rate` expansion） |

**Explicitly out of first Full window:**

- T4 `false_refuse_rate` / `refuse_with_citations` product KPI packaging（可观察字段可留空，不得当首窗 PASS 叙事）
- Critic EXACT / oracle capability
- Hit@3 / retrieval scores as generation PASS
- Multimodal / DiD / P2-R1 unblock

### 1.2 Suites

| Suite | `suite_id` | `case_count` | Role |
|---|---|---|---|
| Primary observation slots | `w9_critic_frozen_12` | `12` | T1/T2/T3 After slots；C12 → `INELIGIBLE` |
| Companion empty-gate | `w10_eb_empty_gate_v1` | `2` | **Only** T4 `empty_gate_refuse_ok` |

**Forbidden suite mutations:**

- Silent `12 → 13` under `w9_critic_frozen_12`
- Relabel C04/C07 as empty-gate gold
- Merge empty ids into E-B2 v1 without new contract version / S1 rename

Full formal packaging = **S2 dual-suite**（E-B8 决议 D）：W9 envelope **plus** empty-gate suite；不得假装单一 `case_count=12` 已含空闸。

### 1.3 Artifacts

| Artifact | Kind / identity | Role in first Full window |
|---|---|---|
| Observation envelope(s) | `artifact_kind=FORMAL_OBSERVATION_RESULT` · protocol `w10_eb2_generation_observation_v1`（及未来 combo 引用合同） | Primary measurement write |
| Claim gold ledger | `CLAIM_GOLD_LEDGER` · `w10_eb_generation_claim_gold_v1` | External T2/T3 gold；hash-bound |
| Empty-gate cases | Real `w10-eb-empty-gate-cases.json` under suite `w10_eb_empty_gate_v1` | T4 denominator material |
| E-A5 result | `w10-ea4-formal-window-result.json` | **Read-only parent pointer only**；不得覆写 / 不得当 generation PASS |

**Must remain absent / untouched unless explicitly in scope:**

- P2-R3 formal result files
- Critic capability contract as gold
- Schema-example-only empty/gold files presented as measured denominators

### 1.4 Claims allowed

**Only** after a successful authorized formal run may progress assert:

```text
generation observation artifact produced
```

Optionally with honest footnotes:

- `targets_measured` exact set
- `measurement_valid` true/false per protocol
- `llm_called` matching reality
- `p2_r1_status=BLOCKED`

**Never** from first Full window:

- Critic capability claim
- E-A5 reuse as generation PASS
- generation quality proven / grounding proven
- P2-R1 unblocked

---

## 2. Optional **Narrow** first formal window（另门禁 · 仍未授权）

If owner later wants a smaller first run:

| Field | Allowed narrow scope |
|---|---|
| Gate symbol | `E-B_NARROW_FORMAL_READY`（≠ Full） |
| `targets_measured` | ⊆ `{T1}` only |
| Suites | `w9_critic_frozen_12` only（no empty-gate claim） |
| After source | Product stream After **or** owner-written unlock of isomorphic formal（must rewrite E-B6 locks） |
| Claim gold / empty suite | **Not required** iff T2/T3/T4 explicitly excluded in artifact |
| Progress title | Must say `narrow / T1-only` |

**Today:** `E-B_NARROW_FORMAL_READY = NO`（合成路径硬锁 `measurement_valid=false`；无 owner 书面解锁）。

---

## 3. What is *not* a formal window

| Activity | Formal? |
|---|---|
| E-B6 isomorphic smoke | No |
| E-B9a schema example ledger | No |
| E-B9b schema example suite | No |
| Human annotation of claim gold | Pre-formal denominator prep |
| Creating real empty-gate cases JSON | Pre-formal denominator prep |
| pytest contract tests | Hygiene only |

---

## 4. Authorization rule

```text
IF E-B_FORMAL_READY == YES
  THEN authorize next window = Full formal observation execution
       (targets/suites/artifacts/claims = §1)
ELSE
  AUTHORIZED_FORMAL_OBSERVATION_WINDOW = NONE
  next window = clearance of exact blockers only
```

本 E-B10 窗落在 **ELSE**：只定义范围，不授权执行。
