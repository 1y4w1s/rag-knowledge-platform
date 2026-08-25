# 03 — Case feasibility（W9 frozen 12）

> Classify only. **Do not create fixtures.** Do not annotate claims.

## 1. Materials

| Material | Path |
|---|---|
| Frozen suite | `backend/tests/fixtures/l4_critic/w9-critic-cases.json`（`protocol=w9_critic_model_inputs_v1`） |
| L0 formal | `backend/tests/fixtures/l4_critic/w10-ea4-formal-window-result.json` |
| E-B1 eligibility | `docs/research/w10-eb1-generation-observation-protocol/04-case-eligibility.md` |
| E-B3 suite audit | `docs/research/w10-eb3-generation-observation-readiness/03-suite-eligibility-audit.md` |
| E-B4 empty-gate design | `docs/research/w10-eb4-generation-observation-construct-repair/04-t4-empty-gate-fixture.md` |

本窗静态复算：`cases` = **12**；每案均有非空 `evidence`；字段含 `query` / `answer` / `citations` / `evidence` / `scope` / `deterministic_context`。

---

## 2. Classification legend

| Class | Meaning |
|---|---|
| **SUITABLE_FOR_FUTURE_GEN_OBS** | L0 eligible；未来 After 执行器可跑；**当前无 After 快照** |
| **MISSING_REQUIRED_OBS_DATA** | 可进 run，但缺 T2/T3/T4 金标或 After 工件 |
| **REQUIRES_NEW_FIXTURE** | 冻结套件无法提供该靶分母；须新 research fixture（本窗不建） |
| **INELIGIBLE** | 不得进产品 generation observation 分母 |

一张案可同时有「suitable run」与「missing gold」。

---

## 3. Per-case table

| case_id | L0 | Future After run | Class (primary) | Notes |
|---|---|---|---|---|
| C01-fully-supported-exact | eligible | yes | **SUITABLE** + MISSING After/T2/T3 gold | evidence=1；非空闸 |
| C02-supported-paraphrase-low-lexical | eligible | yes | **SUITABLE** + MISSING | 同上 |
| C03-one-unsupported-among-supported | eligible | yes | **SUITABLE** + MISSING | 案名 ≠ T2 已测 |
| C04-valid-citation-wrong-evidence | eligible | yes | **SUITABLE** + MISSING | Critic REFUSE ≠ empty-gate |
| C05-known-conflict-overcertain | eligible | yes | **SUITABLE** + MISSING | evidence=2 |
| C06-required-fact-missing | eligible | yes | **SUITABLE** + MISSING | Critic RETRIEVE ≠ 空闸 |
| C07-correct-insufficiency-refusal | eligible | yes | **SUITABLE** + MISSING | evidence=1；`plan_refusal=false`；**不顶** T4 空闸 |
| C08-nonassertive-preface-supported-fact | eligible | yes | **SUITABLE** + MISSING | |
| C09-supported-plus-unverifiable | eligible | yes | **SUITABLE** + MISSING | |
| C10-supported-multiclaim-multicitation | eligible | yes | **SUITABLE** + MISSING | multiclaim 利于未来 T2/T3 标注，仍无 ledger |
| C11-citation-format-only-defect | eligible | yes | **SUITABLE** + MISSING | fixture `[1]` 非法；误用 fixture 正文对齐 → keep-all 假象 |
| C12-out-of-scope-provenance | **invalid** | **no** | **INELIGIBLE** | `INVALID_FOR_PRODUCT_PATH_EXECUTION` |

---

## 4. Target-level feasibility

| Target | Frozen 12 support for E-B5? | Gap |
|---|---|---|
| **T1** final citation scope / align bucket | **Yes as run candidates**（C01–C11） | Need executor + After（或同构）快照；fixture answer **不可**当 After |
| **T2** unsupported claims | Run yes；**gold no** | Independent claim ledger（见 `04`） |
| **T3** grounding | Run yes；**gold no** | Same ledger + G1∧G2 |
| **T4** `empty_gate_refuse_ok` | **No** | **REQUIRES_NEW_FIXTURE**（E-B4 设计）；C04/C07 不可替代 |
| **T4** `false_refuse_rate` | 理论可在 C01–C11 真实 After 上观察 | 今日无 After；E-B5 零 LLM 同构不声称此指标 |

---

## 5. Explicit non-substitutes

| Tempting reuse | Why rejected |
|---|---|
| W9 `answer` / `citations` as After | Critic inputs |
| C07 as empty-gate | Non-empty evidence；semantic insufficiency script |
| C04 Critic REFUSE | Control-plane oracle |
| C12 as refuse-ok | Out-of-scope invalid，非空闸 |
| Hit@3 golden empties | Retrieval gate suite，非 W10 After |

---

## 6. E-B5 implication

| E-B5 scope（窄） | Case need |
|---|---|
| Executor + isomorphic T1 on C01–C11 | **Enough** — 冻结 12 已可作 L0/L1 run 输入 |
| Full T4 empty-gate | **Blocked on new fixture**（非 E-B5 必做项；E-B4 备选 E-B5b） |
| T2/T3 scoring | **Blocked on claim ledger**（可后置于 After 产出窗） |

---

## 7. Verdict

| Bucket | Count |
|---|---|
| SUITABLE_FOR_FUTURE_GEN_OBS (C01–C11) | **11** |
| INELIGIBLE (C12) | **1** |
| Currently holding After / T2–T4 gold | **0** |
| REQUIRES_NEW_FIXTURE（empty-gate） | **≥1 research case**（未创建） |

**不阻塞 E-B5 窄窗实现。** 阻塞 Full formal 的案数据缺口仍在（继承 E-B3/E-B4）。
