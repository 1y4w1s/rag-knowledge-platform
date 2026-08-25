# 04 — Formal gate

> Binary gate only. No formal observation execution in this window.

## Gate

```text
E-B_FORMAL_READY = NO
```

**If YES were true:** 本文件只会写「下一任务 = 正式 observation 执行」，并禁止本窗代跑。  
**实际为 NO：** 下列为 **exact blockers only**。

Companion（非本窗翻转目标，仅澄清）：

```text
E-B_NARROW_FORMAL_READY = NO
```

理由：同构 T1 接线已通，但 E-B6 硬锁 `measurement_valid=false` 且拒绝 reserved formal 写入；按「合成正文不得成为正式证据」不翻转窄正式门禁。窄窗若未来要 YES，须 owner 书面授权「T1-only isomorphic formal」并另开执行窗改写锁，而非本复核自动翻绿。

---

## Exact blockers（Full formal）

### B3 — T2 / T3 independent claim gold missing — **BLOCKING**

- 无 `w10-eb-generation-claim-gold-v1.json`（或等价独立 ledger）
- 无与 After / synthetic hash 绑定的人工命题标注
- Critic `oracle_cases` / `expected_action` 仍禁止充当金标

清除条件（E-B4 C3）：独立 claim gold 规程 + ledger 文件 + hash 绑定 + 零 Critic oracle 键。

### B4 — T4 empty-gate fixture missing — **BLOCKING**

- 无 eligible empty-gate research case fixture
- 冻结 12 不能提供 `empty_gate_refuse_ok` 分母
- 若引入 empty 案，须同时修订 E-B2 `suite_id` / `case_count=12` 合同关系

清除条件（E-B4 C4）：≥1 empty-gate research case + prepare 可得 `refusal=true` + 合同修订钉死 + C04/C07 不伪标 empty-gate。

### B2′ — Formal / product After snapshots incomplete — **PARTIALLY_RESOLVED residual**

同构 After 可捕获，但：

- 无 reserved `FORMAL_OBSERVATION_RESULT` 正式落盘
- 无产品 `_stream_generation_phase` After
- 合成快照被执行器禁止升格为 `measurement_valid=true`

对 **Full** 四靶正式窗，此残余仍阻止「已具备正式分母快照」的声称。  
（B1 执行器本身已 **RESOLVED**，不再列入 exact blockers。）

---

## What is *not* a blocker（勿误列入）

| Item | Why not |
|---|---|
| After-window executor 缺失 | E-B6 已落地（RESOLVED） |
| E-B2 schema / isolation | 仍绿（见 `03`） |
| E-A5 11/11 | 错误观察点；不得当 E-B PASS |
| P2-R1 BLOCKED | 期望态 |
| E-B6 未接通授权 LLM | Full formal 可后置于 owner 授权模型窗；当前 exact blockers 是 gold + empty-gate（+ formal 快照升格） |

---

## Condition matrix (E-B4)

| Cond | Needed for Full YES | Status after E-B7 |
|---|---|---|
| C1 Executor | Yes | Met（test-only isomorphic） |
| C2 After snapshots | Yes | Partial |
| C3 Claim gold | Yes | **Open** |
| C4 Empty-gate | Yes | **Open** |
| C5 Hygiene | Yes | Met |

**Full YES ⇒ C1∧C2∧C3∧C4∧C5 = false.**

---

## Stop

```text
E-B_FORMAL_READY = NO
```

禁止以本目录为「可开跑正式 generation observation」依据。本窗不执行、不写 reserved 结果、不调 LLM。
