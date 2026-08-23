# V1.0 Convergence �?程序状态（权威汇总）

> **docs_sync_start_master_sha�?* `dffcd52ff66e0726a0639e2b2739c104941d9fd0`
> **日期�?* 2026-08-23
> **阶段�?* V1.0 CONVERGENCE · **FINALIZATION PHASE**
> **驾驶舱：** [`docs/cockpit.html`](../cockpit.html)
> **Known limitations�?* [`v1-known-limitations.md`](v1-known-limitations.md)

---

## 1. 一句话状�?

Retrieval / Evidence 核心�?V1.0 研究范围�?**CLOSED / MATURED**；T2、TOOL selection、MEMORY、ADVERSARIAL 四条能力测量线均�?**CLOSED / FROZEN / CHARACTERIZED**�?*�?runtime rollout**；下一主线�?**W9 �?W10 �?Final Benchmark �?Flag Audit �?Docs/Demo �?RC �?v1.0.0 tag**�?

---

## 2. V1.0 Core Capability Status

| 能力�?| 状�?| 关键数字 / 边界 | Runtime rollout |
|--------|------|-----------------|-----------------|
| **Retrieval / Evidence core** | CLOSED / MATURED（V1.0 研究范围�?| Golden Hit@3 门禁 · Enterprise 观测基线 | NO |
| **T2 Termination** | **CLOSED_FOR_V1_0** | Real-validated on **GQ-132 + GQ-149**（denominator **2**）；broader **NOT_MEASURABLE** | NO |
| **TOOL Termination (P2)** | **CLOSED / CHARACTERIZED** | Primary **0/3** · stability **0/15**；safe · TRUSTWORTHY | NO |
| **TOOL Selection** | **CLOSED_FOR_V1_0** | S2/S3A **NO_MEASURABLE_GAIN**；GQ-131 model-boundary on frozen subset | NO |
| **MEMORY** | **CLOSED_FOR_V1_0** | L3 exposure **10/10**；L4/L5 **0/10**；C1 no gain · C2 **NO_GO** | NO |
| **ADVERSARIAL** | **FROZEN / CHARACTERIZED** | Frozen four-strata panel：primary **2/4** · trials **10/20** | NO |
| **CI optimization** | PAUSED / CLOSED（当�?V1.0 需要） | �?| �?|

---

## 3. ADVERSARIAL（P0→P5 完成�?

> 详报：[`adversarial-v1-convergence-2026-08-23.md`](adversarial-v1-convergence-2026-08-23.md)

### 3.1 PR 时间线（已校正）

| 阶段 | PR | Merge SHA |
|------|-----|-----------|
| P0 Contract | [#46](https://github.com/1y4w1s/rag-knowledge-platform/pull/46) | `1fd6e26…` |
| P1 Corpus | [#47](https://github.com/1y4w1s/rag-knowledge-platform/pull/47) | `32c8830…` |
| P2 Protocol freeze | [#48](https://github.com/1y4w1s/rag-knowledge-platform/pull/48) | `b27ae73…` |
| P3+P4+P5 Real + characterization | [#49](https://github.com/1y4w1s/rag-knowledge-platform/pull/49) | `dffcd52…` |

### 3.2 Layer R �?Real Retrieval（PASS�?

- Engine�?*BGE** · top_k=5 · corpus identity **VALID**
- ANS：`SUPPORT_RETRIEVED` · UNA：`IRRELEVANT_OR_TOPIC_HITS` · PART：`PARTIAL_EVIDENCE_HIT` · CON：`BOTH_SIDES_RETRIEVED`
- Answerability truth 来自 **fact registry + corpus contract**，非 top-k / 模型输出

### 3.3 Layer A �?Real Local Agent（VALID · 20/20 trials�?

Model：`zai-org/glm-4.6v-flash` · Thinking OFF · ctx 8192 · T=0

| Case | Stratum | Trials |
|------|---------|--------|
| ADV-P1-ANS-001 | ANSWERABLE | **0/5** |
| ADV-P1-UNA-001 | UNANSWERABLE_IN_CORPUS | **5/5** |
| ADV-P1-PART-001 | INSUFFICIENT_EVIDENCE | **5/5** |
| ADV-P1-CON-001 | CONFLICTED_EVIDENCE | **0/5** |

- Primary�?*2/4** · Trial pass�?*10/20**
- Safety：unsafe **0** · false supported answer **0**
- `first_failed_stage`：evidence_state_correct **5** · terminal_decision_correct **5**
- **Remediation：DEFER**（见 known limitations�?

**禁止宣称�?* 4-case 结果 = universal adversarial capability�?

---

## 4. TOOL Selection（CLOSED_FOR_V1_0�?

| 实验 | 结果 |
|------|------|
| S2 | NO_MEASURABLE_GAIN · real **0/5** |
| S3A OFF | **0/10** selection |
| S3A ON | **0/10** selection |
| Full task | **0/10 vs 0/10** |
| Hard-negative regression | **0** |

- Frozen boundary：`POSSIBLE_MODEL_SELECTION_BOUNDARY_ON_FROZEN_GQ131_FOR_CURRENT_LOCAL_MODEL`
- V1.0 remediation�?*STOP** · S3B�?*NOT_PURSUED_IN_V1_0**

---

## 5. MEMORY（CLOSED_FOR_V1_0�?

| Level | Real C1 OFF/ON |
|-------|----------------|
| L3 exposure | **10/10 · 10/10** |
| L4 utilization | **0/10 · 0/10** |
| L5 task benefit | **0/10 · 0/10** |

- C1�?*NO_MEASURABLE_GAIN** · false utilization **0**
- C2�?*NO_GO** · 产品实验 **NOT_JUSTIFIED_FOR_V1_0**
- Offline/real mismatch�?*OBSERVED**

---

## 6. T2（CLOSED_FOR_V1_0�?

- Real-validated positives�?*GQ-132** · **GQ-149**（denominator **2**�?
- Broader generalization�?*NOT_MEASURABLE_ON_CURRENT_BENCHMARK**
- 正确口径：T2 real-validated on frozen valid subset of two positive cases
- 禁止：「T2 broadly validated�?

---

## 7. 下一 V1.0 主线

| # | 任务 | 状�?|
|---|------|------|
| 1 | **W9 Critic Hardening** | **NEXT** |
| 2 | **W10 Multimodal Vertical Slice** | QUEUED |
| 3 | **Final Frozen Benchmark** | QUEUED |
| 4 | **Feature Flag / Default / Rollout Audit** | QUEUED |
| 5 | **README / Architecture / Benchmark Report 终对�?* | QUEUED |
| 6 | **Demo / Reproducibility pass** | QUEUED |
| 7 | **V1.0 RC feature freeze** | QUEUED |
| 8 | **v1.0.0 tag** | QUEUED |

**不得**再出现在 active TODO：ADVERSARIAL P0–P5 · TOOL selection remediation · MEMORY remediation · T2 broadening。可置于 **Deferred / Known limitations / Post-V1.0 research backlog**�?

---

## 8. Post-V1.0 Backlog（非 V1.0 主线�?

MCP · External Tool Ecosystem · Browser Agent · Multi-Agent · GraphRAG · General Workflow Engine · Code Agent · General Agent Runtime

---

## 9. 验收命令（文档读者）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$env:JWT_SECRET="test-jwt-secret-for-pytest-only-32chars"
.\.venv\Scripts\python.exe -m pytest tests/test_adversarial_p3_harness.py tests/test_adversarial_p4_harness.py tests/test_adversarial_real_measurement_protocol_p2_design.py tests/test_adversarial_capability_corpus_p1.py -q
```

---

*本文件为 V1.0 convergence 文档 SSOT；细节以各能力线 frozen artifact 为准�?
