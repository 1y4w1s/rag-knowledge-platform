# V1.0 Known Limitations（能力边界）

> **master @** `8a72c53f83a0e285effb5b40526d9a01e13dd3f9` · 2026-08-23
> 收敛状态 → [`v1-convergence-status-2026-08-23.md`](v1-convergence-status-2026-08-23.md)
> ADVERSARIAL 详报 → [`adversarial-v1-convergence-2026-08-23.md`](adversarial-v1-convergence-2026-08-23.md)

本文档记录 **frozen subset / 已冻结能力线 / 当前 benchmark** 上的已知边界；**不得**推导 universal capability claim。

---

## 1. TOOL · GQ-131（选择边界）

| 项 | 值 |
|---|---|
| **范围** | S2 / S3A 冻结子集 · 模型 `zai-org/glm-4.6v-flash` |
| **工具** | 仅测 `semantic_search`；contract 基线 `search_documents` |
| **S2** | NO_MEASURABLE_GAIN · real **0/5** |
| **S3A** | OFF **0/10** · ON **0/10** selection · full task **0/10 vs 0/10** |
| **边界标签** | `POSSIBLE_MODEL_SELECTION_BOUNDARY_ON_FROZEN_GQ131_FOR_CURRENT_LOCAL_MODEL` |
| **禁止表述** | 「GLM universally 不会选工具」类全称 |
| **Remediation** | **STOP**（V1.0）· S3B **NOT_PURSUED** |
| **Runtime rollout** | **NO** |

---

## 2. MEMORY · GA-9 / GA-10（C1 无增益）

| 项 | 值 |
|---|---|
| **L3 exposure** | **PROVEN 10/10**（OFF/ON 均 10/10） |
| **L4 semantic utilization** | **NOT_DEMONSTRATED** · OFF/ON **0/10 · 0/10** |
| **L5 causal task benefit** | **NOT_DEMONSTRATED** · OFF/ON **0/10 · 0/10** |
| **C1 结论** | NO_MEASURABLE_GAIN |
| **False utilization** | **0** |
| **Offline / real mismatch** | **OBSERVED** |
| **C2** | **NO_GO** · 产品化 **NOT_JUSTIFIED_FOR_V1_0** |
| **禁止表述** | 「memory 已产品化」「GLM 已会用 memory」「memory capability 已 > 0」 |
| **允许表述** | 在 frozen GA-9/GA-10 上 **exposure 成立**；semantic utilization 与 causal benefit **未成立** |
| **Remediation** | **DEFER** |
| **Runtime rollout** | **NO** |

---

## 3. ADV · ANSWERABLE（ADV-P1-ANS-001）

| 项 | 值 |
|---|---|
| **Layer R** | support evidence **已检索**（`SUPPORT_RETRIEVED`） |
| **Layer A** | `retrieval_attempted=false` → **EvidenceState 错误** → terminal 未达标 |
| **P4 trials** | **0/5** pass |
| **失败层** | `AGENT_RETRIEVAL_TRIGGER_FAILURE` / `AGENT_RETRIEVAL_PATH_FAILURE` + `EVIDENCE_STATE_FAILURE` |
| **禁止** | 归因 `RETRIEVAL_FAILURE`（因 Layer R BGE 路径已达标） |
| **Remediation** | **DEFER**（Agent ingest / retrieval 触发） |
| **Runtime rollout** | **NO** |

---

## 4. ADV · CONFLICTED_EVIDENCE（ADV-P1-CON-001）

| 项 | 值 |
|---|---|
| **Layer R** | support + contradiction **均已检索** |
| **Layer A** | 实际 **refuse** · 期望 **clarify** |
| **P4 trials** | **0/5** pass |
| **Primary failure** | `TERMINAL_DECISION_FAILURE` |
| **禁止表述** | 「模型不会处理冲突」 |
| **允许表述** | 在 frozen conflict case 上，Agent 选择 refuse 而非 contract 期望的 clarify terminal |
| **Remediation** | **DEFER**（conflict terminal 策略） |
| **Runtime rollout** | **NO** |

---

## 5. T2 · 终止策略（Termination）

| 项 | 值 |
|---|---|
| **Real-validated positive subset** | GQ-132 · GQ-149（**denominator = 2**） |
| **Broader generalization** | **NOT_MEASURABLE_ON_CURRENT_BENCHMARK** |
| **禁止表述** | 「T2 broadly validated」 |
| **允许表述** | T2 在 frozen valid subset（2 positive cases）上 real-validated |
| **Remediation** | **CLOSED_FOR_V1_0** |
| **Runtime rollout** | **NO** |

---

## 6. Legacy ADV20

| 项 | 值 |
|---|---|
| **状态** | `INVALID_FOR_CAPABILITY` |
| **P0 审计** | Valid-as-is **0** · Migratable **18** · Invalid **2** |
| **当前 real denominator** | **4**（非 18） |
| **禁止** | 将 18 migrated cases 当作 18 real capability cases；不得用 ADV20 作为 baseline |

---

## 7. 声明

- **Capability experiment merged ≠ runtime rollout** — 所有 L3/L4/agent 相关 flag 保持 **OFF**
- **Post-V1.0 backlog** 不得列入 V1.0 承诺：MCP · Browser Agent · Multi-Agent · GraphRAG · Workflow Engine · Code Agent · General Agent Runtime
