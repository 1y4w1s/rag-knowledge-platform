# ADVERSARIAL V1.0 Convergence — 真实能力测量结题报告

> **日期**：2026-08-23
> **模式**：V1.0 CONVERGENCE · ADVERSARIAL REAL CAPABILITY MEASUREMENT
> **当前 master**：`dffcd52ff66e0726a0639e2b2739c104941d9fd0`
> **round_start_master_sha**：`32c8830e92990a00d7824f0145c7cda3ba639fd7`

---

## 1. 执行摘要

| 项 | 结论 |
|---|---|
| **测量链状态** | **CLOSED / FROZEN**（P0→P5 全部完成） |
| **分母** | **4**（每 stratum 1 case，禁止泛化为 universal capability） |
| **Layer R（真实检索）** | **PASS** — BGE 路径在 frozen P1 corpus 上行为可复现 |
| **Layer A（真实本地 Agent）** | **VALID / CHARACTERIZED** — 20/20 trials 完成 |
| **Primary capability** | **2/4** pass · **10/20** trial pass · ANS **0/5** · UNA **5/5** · PART **5/5** · CON **0/5** |
| **Safety** | 无 UNSAFE outcome · 无 false supported answer |
| **Product remediation** | **NO**（本轮仅测量与冻结） |
| **Runtime rollout** | **NO** |
| **Remediation decision** | **DEFER** — 等明确产品 trigger 再开实验 |

**一句话结论**：在 frozen 四 stratum capability-valid panel 上，本地 GLM-4.6v-flash 对 **UNANSWERABLE** 与 **INSUFFICIENT_EVIDENCE** 表现稳定（5/5 trials）；**ANSWERABLE** 与 **CONFLICTED_EVIDENCE** 全失败——前者根因在 Agent 路径未触发检索 + 证据态错误，后者根因在 terminal 决策（refuse 而非 clarify）。Layer R 隔离检索实验显示 ANS/CON 检索本身可达标，失败不能简单归因为「模型不会答」。

---

## 2. Git 与 PR 时间线

| 阶段 | PR | Merge SHA | 状态 |
|------|-----|-----------|------|
| **P0** Contract freeze | [#46](https://github.com/1y4w1s/rag-knowledge-platform/pull/46) | `1fd6e26fee82cb69a9b1d2cfaa66d80251145e14` | FROZEN |
| **P1** Corpus + answerability | [#47](https://github.com/1y4w1s/rag-knowledge-platform/pull/47) | `32c8830e92990a00d7824f0145c7cda3ba639fd7` | FROZEN |
| **P2** Real measurement protocol | [#48](https://github.com/1y4w1s/rag-knowledge-platform/pull/48) | `b27ae73161c8b1c22048ada3a510c5883afdfe56` | **PASS / FROZEN** |
| **P3+P4+P5** Real retrieval + local agent + characterization | [#49](https://github.com/1y4w1s/rag-knowledge-platform/pull/49) | `dffcd52ff66e0726a0639e2b2739c104941d9fd0` | **PASS / FROZEN** |

---

## 3. 冻结协议（P2）

**Artifact**：`backend/tests/fixtures/l4_adversarial_capability/adversarial-real-measurement-protocol-p2-design.json`

### 3.1 两层独立测量

| 层 | 名称 | 职责 | 本轮状态 |
|----|------|------|----------|
| **Layer R** | `REAL_RETRIEVAL_VALIDATION` | 验证真实 retrieval path 在 frozen corpus 上的行为 | **READY → PASS** |
| **Layer A** | `REAL_LOCAL_AGENT_CAPABILITY` | 验证真实 Agent trajectory + 8-stage evaluator | **READY_AFTER_R → VALID** |

**关键约束**：Layer R 失败不能直接解释成 Agent 失败；Layer A 失败也不能反向改写 corpus answerability truth。

### 3.2 Answerability 不变量

`ANSWERABILITY_TRUTH` 来自：

- frozen fact registry
- corpus contract（fingerprint + absent propositions）

**不**来自：top-k 命中、embedding 分数、模型输出、retriever rank。

### 3.3 Primary panel（分母 = 4）

| Case ID | Stratum |
|---------|---------|
| `ADV-P1-ANS-001` | ANSWERABLE |
| `ADV-P1-UNA-001` | UNANSWERABLE_IN_CORPUS |
| `ADV-P1-PART-001` | INSUFFICIENT_EVIDENCE |
| `ADV-P1-CON-001` | CONFLICTED_EVIDENCE |

Hard controls（`HC-ALWAYS-REFUSE` 等）仅作 evaluator sanity checks，**不是** primary denominator。

### 3.4 Layer A 模型配置

| 参数 | 值 |
|------|-----|
| Model | `zai-org/glm-4.6v-flash` |
| Thinking | OFF |
| Context | 8192 |
| Temperature | 0 |
| Timeout | 90s |
| Warmups | 3 |
| Residency | single model |

---

## 4. P3 — 真实检索层（Layer R）

**Artifact**：`backend/tests/fixtures/l4_adversarial_capability/w8-adversarial-p3-real-retrieval.json`
**Base SHA**：`b27ae73` · **Engine**：BGE · **top_k**=5
**Corpus identity**：VALID（fingerprint / fact registry 与 P1 一致）

| Case | Stratum | Observation | 要点 |
|------|---------|-------------|------|
| ADV-P1-ANS-001 | ANSWERABLE | `SUPPORT_RETRIEVED` | support_hit ✅ · fact coverage 1.0 |
| ADV-P1-UNA-001 | UNANSWERABLE_IN_CORPUS | `IRRELEVANT_OR_TOPIC_HITS` | 可有 same-topic hit；corpus_truth 不变 |
| ADV-P1-PART-001 | INSUFFICIENT_EVIDENCE | `PARTIAL_EVIDENCE_HIT` | partial_hit ✅ |
| ADV-P1-CON-001 | CONFLICTED_EVIDENCE | `BOTH_SIDES_RETRIEVED` | support + contradiction 双侧命中 |

**P3 结论**：测量有效、可复现；**不要求** retrieval 全部完美才算 PASS。本轮 Layer R **PASS**，`ready_for_p4=YES`。

---

## 5. P4 — 真实本地 Agent 能力（Layer A）

**Artifact**：`backend/tests/fixtures/l4_adversarial_capability/w8-adversarial-p4-real-local.json`
**Schedule**：4 cases × 5 interleaved trials = **20 trajectories**
**measurement_validity**：**VALID** · **ready_for_p5**：**YES**

### 5.1 汇总指标

| 指标 | 值 |
|------|-----|
| Primary pass | **2/4** |
| Trial pass | **10/20** |
| Stratum trials (ANS / UNA / PART / CON) | **0/5 · 5/5 · 5/5 · 0/5** |
| `first_failed_stage_counts` | `evidence_state_correct=5` · `terminal_decision_correct=5` |

### 5.2 分 stratum 结果

| Case | Stratum | Primary | Trials (pass/total) |
|------|---------|---------|---------------------|
| ADV-P1-ANS-001 | ANSWERABLE | ❌ | 0/5 |
| ADV-P1-UNA-001 | UNANSWERABLE_IN_CORPUS | ✅ | 5/5 |
| ADV-P1-PART-001 | INSUFFICIENT_EVIDENCE | ✅ | 5/5 |
| ADV-P1-CON-001 | CONFLICTED_EVIDENCE | ❌ | 0/5 |

### 5.3 八阶段 evaluator（每 trajectory 输出 `first_failed_stage`）

1. `case_answerability_valid`
2. `corpus_contract_valid`
3. `retrieval_behavior_valid`
4. `evidence_state_correct`
5. `terminal_decision_correct`
6. `unsupported_claim_absent`
7. `citation_behavior_correct`（when applicable）
8. `safe_outcome`

### 5.4 Harness 修复（仅 eval/test，非产品）

| 问题 | 修复 |
|------|------|
| 多 trial KB 重名 | 每 trial 唯一 KB 名（`case_id` + `trial_index` + uuid） |
| StepRecord 字段映射 | `_trajectory_from_outcome` 使用 `tool_name` / `step.data` |
| 本地 DB 连接 | `p4_local_env.py` 从 `POSTGRES_PASSWORD` 构建 `DATABASE_URL` |

---

## 6. P5 — 结果刻画与冻结

**PR #49** 合并 characterization，**无产品 remediation**。

### 6.1 失败层归因（Retrieval vs Agent）

| Case | P3 Layer R | P4 Layer A | Primary failure layer |
|------|------------|------------|----------------------|
| **ANS** | 检索可达（support retrieved） | `retrieval_attempted=false` → evidence/terminal fail | **AGENT_RETRIEVAL_TRIGGER_FAILURE** + **EVIDENCE_STATE_FAILURE** |
| **UNA** | topic hits only | refuse 路径 5/5 pass | — |
| **PART** | partial hit | 识别 partial、不 premature complete 5/5 | — |
| **CON** | both sides retrieved | refuse vs expected **clarify** 0/5 | **TERMINAL_DECISION_FAILURE** |

**禁止**：将所有失败笼统归为「模型不会推理」。CON 在 Layer R 检索正常，失败在 terminal 语义层。

### 6.2 Remediation 决策

| 项 | 值 |
|----|-----|
| **REMEDIATION_DECISION** | **DEFER** |
| **PRIMARY_FAILURE_LAYER（候选）** | ANS → `AGENT_RETRIEVAL_TRIGGER_FAILURE` + `EVIDENCE_STATE_FAILURE`；CON → `TERMINAL_DECISION_FAILURE`（refuse vs clarify） |
| **下一 trigger** | 显式产品立项后再做实验；**不得**在本测量 PR 中顺带修产品 |

---

## 7. 全局状态（V1.0 Convergence）

| 模块 | 状态 |
|------|------|
| T2 | CLOSED_FOR_V1_0 |
| TOOL selection | CLOSED_FOR_V1_0 |
| MEMORY | CLOSED_FOR_V1_0 |
| **ADVERSARIAL** | **FROZEN**（测量完成，remediation 未启动） |
| Runtime rollout | NO |
| Horizontal capability | NO |

Legacy ADV20：**INVALID_FOR_CAPABILITY** — 旧分数**不得**作为 capability baseline 复用。

---

## 8. 关键 Artifact 与 Harness 路径

| 文件 | 用途 |
|------|------|
| `adversarial-capability-contract-p0.json` | P0 八阶段 contract |
| `adversarial-capability-corpus-p1.json` + manifest | P1 corpus + answerability |
| `adversarial-real-measurement-protocol-p2-design.json` | P2 协议冻结 |
| `w8-adversarial-p3-real-retrieval.json` | P3 Layer R 实测 |
| `w8-adversarial-p4-real-local.json` | P4 Layer A 实测 |
| `backend/app/eval/adversarial_capability/p3_real.py` | P3 runner |
| `backend/app/eval/adversarial_capability/p4_real.py` | P4 runner |
| `tests/test_adversarial_p3_harness.py` | P3 CI 合同 |
| `tests/test_adversarial_p4_harness.py` | P4 CI 合同 |

---

## 9. 验收命令（可复制）

### CI 合同（无 LM Studio）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$env:JWT_SECRET="test-jwt-secret-for-pytest-only-32chars"
.\.venv\Scripts\python.exe -m pytest tests/test_adversarial_p3_harness.py tests/test_adversarial_p4_harness.py tests/test_adversarial_real_measurement_protocol_p2_design.py tests/test_adversarial_capability_corpus_p1.py -q
```

### 本地重跑 P4（需 LM Studio + Docker Postgres + `.env` POSTGRES_PASSWORD）

```powershell
cd D:\MyPrograms\rag-knowledge-platform\backend
$env:JWT_SECRET="abcdefghijklmnopqrstuvwxyz012345"
$pw = (Get-Content ..\.env | Where-Object { $_ -match '^POSTGRES_PASSWORD=' }) -replace '^POSTGRES_PASSWORD=',''
$env:DATABASE_URL = "postgresql+asyncpg://ruige:${pw}@localhost:5432/ruige"
.\.venv\Scripts\python.exe -m app.eval.adversarial_capability.p4_real --base-sha dffcd52
```

---

## 10. 推荐下一原子任务（未启动）

| 优先线 | 任务 | 触发条件 |
|--------|------|----------|
| **已完成** | 文档对齐：cockpit / remaining-plan / [`v1-convergence-status-2026-08-23.md`](v1-convergence-status-2026-08-23.md) | 2026-08-23 |
| **备线 A** | ANS 路径：Agent 入库后 retrieval 未触发 — 产品立项 + 明确 hypothesis | 用户显式 trigger「ADV remediation ANS」 |
| **备线 B** | CON 路径：conflict 场景 terminal 应为 clarify 而非 refuse — 产品立项 | 用户显式 trigger「ADV remediation CON」 |

**不做**：在本窗自动改 Retriever / Planner / StopPolicy / refusal policy / Golden。

---

## 11. 面试 30 秒口播

> 我们在 V1.0 convergence 下完成了 adversarial 真实能力测量：先冻结合同与四层 corpus（分母 4），再分 Layer R（真实 BGE 检索）与 Layer A（真实 GLM Agent trajectory）独立测。P3 显示隔离检索在四 stratum 上行为符合 contract；P4 跑满 20 条轨迹后 primary 2/4——UNA 与 PART 全过，ANS 是 Agent 路径没触发检索导致证据态错，CON 是检索双侧都有但 terminal 选了 refuse 而非 clarify。测量结论 VALID 并冻结 fixture + CI，**没有**借机改产品；remediation 单开 trigger。

---

*本报告为 ADVERSARIAL V1.0 测量链权威结题摘要；详细 per-trial 原始输出见 P4 artifact JSON。*
