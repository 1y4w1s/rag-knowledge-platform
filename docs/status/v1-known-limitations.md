# V1.0 Known Limitations（Canonical）

> **Canonical** release limitations surface.  
> Baseline HEAD: `3289f65` · Updated for **V1.0-C6** (2026-08-25).  
> Research capability residuals (TOOL / MEMORY / ADV detail) remain below and in dated convergence docs.  
> Architecture → [`../architecture.md`](../architecture.md) · Evidence → [`../benchmark-summary.md`](../benchmark-summary.md).

```text
Limitation documented  ≠  automatic RC blocker
RELEASE_ACCEPTED     = accepted for v1.0 tag honesty
RC_BLOCKER           = must clear before Release Candidate freeze
```

---

## Severity legend

| Severity | Meaning |
|----------|---------|
| **RELEASE_ACCEPTED** | True today; allowed on v1.0 with honest docs |
| **OPERATIONAL** | Ops / env / provider constraint; not a missing feature |
| **EXPERIMENTAL** | Default-off / research surface; not product maturity debt |
| **POST_V1_0** | Explicitly out of cut line |
| **RC_BLOCKER** | Blocks Release Candidate / tag integrity |

---

## Product / install / ops limitations

| # | Limitation | Verified? | Severity |
|---|------------|:---------:|----------|
| L1 | Clean-room install verified on **Windows + Docker Desktop** (C3). | YES (README + C3 path) | **RELEASE_ACCEPTED** |
| L2 | **macOS / Linux** compose path expected usable; **not** clean-room re-verified in C3. | YES | **RELEASE_ACCEPTED** |
| L3 | Canonical demo (`scripts/demo.ps1`) requires a **live chat provider** key (DeepSeek or Tongyi). | YES | **OPERATIONAL** |
| L4 | Provider / circuit-breaker may yield `/health` **degraded** and chat unavailable until recovery. | YES | **OPERATIONAL** |
| L5 | Ingestion is **serialized per Celery worker process** (thread-pool event-loop isolation fix). Multi-file uploads queue behind the lock; not a silent parallel ingest guarantee. | YES (`test_c4_ingestion_loop_isolation.py`) | **RELEASE_ACCEPTED** |
| L6 | **Local generation** (LM Studio / product local-model profile) is **not** a validated v1.0 product capability (STUB / eval-only). | YES (config + Cut Line) | **POST_V1_0** |
| L7 | **Agent Golden (168)** is **not** PR-blocking (RELEASE_ONLY / MANUAL). | YES (C5 CI contract) | **RELEASE_ACCEPTED** |
| L8 | **ADV / W9 / W10** research evidence is **not** production proof; Formal/ADV panels are CHARACTERIZED / ARCHIVE. | YES | **EXPERIMENTAL** / honesty |
| L9 | **L3 / Critic / L4** experimental and **DEFAULT OFF**; Critic runtime rollout **NO**. | YES (`config.py` + safe-defaults test) | **EXPERIMENTAL** |
| L10 | **Memory infrastructure ≠ demonstrated intelligence** (L3 exposure measured; L4/L5 0/10; C2 NO_GO). | YES | **RELEASE_ACCEPTED** |
| L11 | **GraphRAG** not productized; graph recall rolled back / OFF. | YES | **POST_V1_0** |
| L12 | **Multi-Agent / MCP / Evolver** not v1.0. | YES (Cut Line) | **POST_V1_0** |
| L13 | PR CI may require **HF mirror / BGE model artifact** availability (paid-LLM independent, not fully offline). | YES (C5) | **OPERATIONAL** |
| L14 | **No** production SLA / load / scale claim. | YES | **RELEASE_ACCEPTED** |

### RC blocker scan（C6）

After C1–C6 documentation/install/demo/CI honesty work:

| Candidate | Status |
|-----------|--------|
| Unsupported public capability claim | Cleared by C2 + this package |
| Broken install narrative | Cleared by C3 |
| Missing canonical demo | Cleared by C4 |
| CI overclaim / missing stable RAG gates | Cleared by C5 |
| Missing architecture / benchmark / limitations docs | Cleared by **C6** |
| W9/W10 claim inflation | Discipline preserved |
| Release **tag** contents / signing / package integrity | **RC_ONLY** (belongs to Release Candidate freeze — not another closure-dev window) |

```text
V1_0_DOCUMENTATION_RC_BLOCKERS_REMAIN = 0
```

---

## Research capability residuals（frozen honesty）

> Dated research SSOT also: [`v1-convergence-status-2026-08-23.md`](v1-convergence-status-2026-08-23.md) · ADV detail [`adversarial-v1-convergence-2026-08-23.md`](adversarial-v1-convergence-2026-08-23.md).  
> These are **RELEASE_ACCEPTED** honesty constraints, not prompts to reopen research for v1.0.

### 1. TOOL · GQ-131（selection boundary）

| 项 | 值 |
|---|---|
| **范围** | S2 / S3A 冻结子集 · 模型 `zai-org/glm-4.6v-flash` |
| **S2** | NO_MEASURABLE_GAIN · real **0/5** |
| **S3A** | OFF **0/10** · ON **0/10** selection |
| **边界标签** | `POSSIBLE_MODEL_SELECTION_BOUNDARY_ON_FROZEN_GQ131_FOR_CURRENT_LOCAL_MODEL` |
| **禁止表述** | 「GLM universally 不会选工具」 |
| **Runtime rollout** | **NO** |
| **Severity** | **RELEASE_ACCEPTED** |

### 2. MEMORY · GA-9 / GA-10（C1 无增益）

| 项 | 值 |
|---|---|
| **L3 exposure** | **PROVEN 10/10** |
| **L4 semantic utilization** | **NOT_DEMONSTRATED** · **0/10** |
| **L5 causal task benefit** | **NOT_DEMONSTRATED** · **0/10** |
| **C2** | **NO_GO** · **NOT_JUSTIFIED_FOR_V1_0** |
| **禁止表述** | 「memory 已产品化 / intelligence 已验证」 |
| **Severity** | **RELEASE_ACCEPTED** |

### 3. ADV · ANSWERABLE（ADV-P1-ANS-001）

| 项 | 值 |
|---|---|
| Layer R | support evidence retrieved |
| Layer A | Agent retrieval trigger / EvidenceState path failure · P4 **0/5** |
| Remediation | **DEFER** · rollout **NO** |
| **Severity** | **RELEASE_ACCEPTED** |

### 4. ADV · CONFLICTED_EVIDENCE（ADV-P1-CON-001）

| 项 | 值 |
|---|---|
| Layer A | actual **refuse** vs expected **clarify** · P4 **0/5** |
| Primary failure | `TERMINAL_DECISION_FAILURE` |
| Remediation | **DEFER** · rollout **NO** |
| **Severity** | **RELEASE_ACCEPTED** |

### 5. T2 · Termination

| 项 | 值 |
|---|---|
| Real-validated positive subset | GQ-132 · GQ-149（denominator = **2**） |
| Broader generalization | **NOT_MEASURABLE_ON_CURRENT_BENCHMARK** |
| **Severity** | **RELEASE_ACCEPTED** |

### 6. Legacy ADV20

| 项 | 值 |
|---|---|
| 状态 | `INVALID_FOR_CAPABILITY` |
| 当前 real denominator | **4**（非 18） |
| **Severity** | **RELEASE_ACCEPTED**（do not cite ADV20 as baseline） |

### 7. W10 Formal scope limits

See [`../research/w10-closure/05-known-limitations.md`](../research/w10-closure/05-known-limitations.md): Showcase Formal dependency unpinned · Product After DEGRADED · T2/T3 N/A · not production pin.

**Severity:** **RELEASE_ACCEPTED** / research honesty.

---

## Explicit non-claims

```text
W10 Formal T1 100%  ≠  Agent / RAG / answer accuracy 100%
Memory master ON   ≠  memory intelligence validated
Agent Golden exists ≠  PR CI Agent quality gate
ADV 2/4 · 10/20     ≠  universal adversarial robustness
C4 demo PASS        ≠  general accuracy
CI green            ≠  production SLA
```

### Post-V1.0 backlog（must not block tag）

MCP · Browser Agent · Multi-Agent · GraphRAG productization · Workflow Engine · Code Agent · General Agent Runtime · Evolver · LLM-Wiki · Memory v2 intelligence · Local-model product capability · E-B45 / W11 research reopen.

---

## Related

- [`../project/v1-0-release-cut-line.md`](../project/v1-0-release-cut-line.md)  
- [`../project/feature-admission-constitution.md`](../project/feature-admission-constitution.md)  
- [`../benchmark-summary.md`](../benchmark-summary.md)  
- [`../architecture.md`](../architecture.md)  
