# V1.0 Known Limitations（冻结口径）

> **master @** `dffcd52ff66e0726a0639e2b2739c104941d9fd0`�?026-08-23�?
> 权威状态汇�?�?[`v1-convergence-status-2026-08-23.md`](v1-convergence-status-2026-08-23.md)
> ADVERSARIAL 详报 �?[`adversarial-v1-convergence-2026-08-23.md`](adversarial-v1-convergence-2026-08-23.md)

以下均为 **frozen subset / 当前本地模型 / 当前 benchmark** 下的测量结论�?*不得**泛化�?universal capability claim�?

---

## 1. TOOL · GQ-131（工具选择�?

| �?| �?|
|---|---|
| **范围** | S2 / S3A 冻结实验 · 本地 `zai-org/glm-4.6v-flash` |
| **现象** | 持久�?`semantic_search`，contract 期望 `search_documents` |
| **S2** | NO_MEASURABLE_GAIN · real **0/5** |
| **S3A** | OFF **0/10** · ON **0/10** selection · full task **0/10 vs 0/10** |
| **边界标签** | `POSSIBLE_MODEL_SELECTION_BOUNDARY_ON_FROZEN_GQ131_FOR_CURRENT_LOCAL_MODEL` |
| **禁止宣称** | 「GLM  universally 不会选工具�?|
| **Remediation** | **STOP**（V1.0）�?S3B **NOT_PURSUED** |
| **Runtime rollout** | **NO** |

---

## 2. MEMORY · GA-9 / GA-10（C1 真实对照�?

| �?| �?|
|---|---|
| **L3 exposure** | **PROVEN 10/10**（OFF/ON 均为 10/10�?|
| **L4 semantic utilization** | **NOT_DEMONSTRATED** · OFF/ON **0/10 · 0/10** |
| **L5 causal task benefit** | **NOT_DEMONSTRATED** · OFF/ON **0/10 · 0/10** |
| **C1 结论** | NO_MEASURABLE_GAIN |
| **False utilization** | **0** |
| **Offline / real mismatch** | **OBSERVED** |
| **C2** | **NO_GO** · 产品实验 **NOT_JUSTIFIED_FOR_V1_0** |
| **禁止宣称** | 「memory 完全无效」「GLM 不能�?memory」「memory capability 恒为 0�?|
| **正确口径** | �?frozen GA-9/GA-10 上，**exposure 已证**，semantic utilization �?causal benefit **未证** |
| **Remediation** | **DEFER** |
| **Runtime rollout** | **NO** |

---

## 3. ADV · ANSWERABLE（ADV-P1-ANS-001�?

| �?| �?|
|---|---|
| **Layer R** | support evidence **可检�?*（`SUPPORT_RETRIEVED`�?|
| **Layer A** | `retrieval_attempted=false` �?**EvidenceState 错误** �?terminal 下游失败 |
| **P4 trials** | **0/5** pass |
| **首选措�?* | `AGENT_RETRIEVAL_TRIGGER_FAILURE` / `AGENT_RETRIEVAL_PATH_FAILURE` + `EVIDENCE_STATE_FAILURE` |
| **避免** | 单独�?`RETRIEVAL_FAILURE`（易�?Layer R BGE 检索混淆） |
| **Remediation** | **DEFER**（Agent ingest / retrieval 触发链） |
| **Runtime rollout** | **NO** |

---

## 4. ADV · CONFLICTED_EVIDENCE（ADV-P1-CON-001�?

| �?| �?|
|---|---|
| **Layer R** | support + contradiction **双侧检索命�?* |
| **Layer A** | 实际 **refuse** · 期望 **clarify** |
| **P4 trials** | **0/5** pass |
| **Primary failure** | `TERMINAL_DECISION_FAILURE` |
| **禁止宣称** | 「模型无法推理冲突�?|
| **正确口径** | 检索已捕获双侧，Agent 选了 refuse 而非 contract 期望�?clarify terminal |
| **Remediation** | **DEFER**（conflict terminal 语义�?|
| **Runtime rollout** | **NO** |

---

## 5. T2 · 终止能力（Termination�?

| �?| �?|
|---|---|
| **Real-validated positive subset** | GQ-132 · GQ-149�?*denominator = 2**�?|
| **Broader generalization** | **NOT_MEASURABLE_ON_CURRENT_BENCHMARK** |
| **禁止宣称** | 「T2 broadly validated�?|
| **正确口径** | T2 �?frozen valid subset�? positive cases）上 real-validated |
| **Remediation** | **CLOSED_FOR_V1_0** |
| **Runtime rollout** | **NO** |

---

## 6. Legacy ADV20

| �?| �?|
|---|---|
| **状�?* | `INVALID_FOR_CAPABILITY` |
| **P0 迁移** | Valid-as-is **0** · Migratable **18** · Invalid **2** |
| **当前 real denominator** | **4**（非 18�?|
| **禁止** | �?18 migrated cases 等同�?18 real capability cases；复用旧 ADV20 分数�?baseline |

---

## 7. 全局

- **Capability experiment merged �?runtime rollout** �?所�?L3/L4/agent 实验 flag 默认 **OFF**
- **Post-V1.0 backlog**（不得误�?V1.0 主线）：MCP · Browser Agent · Multi-Agent · GraphRAG · Workflow Engine · Code Agent · General Agent Runtime
