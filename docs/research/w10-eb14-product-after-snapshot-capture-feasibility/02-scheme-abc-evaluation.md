# 02 — Scheme A / B / C evaluation

> Product After capture options. No implementation. No formal run.

## Definitions

| Scheme | Meaning |
|---|---|
| **A** | Test-only wrapper/harness drains real `_stream_generation_phase` and reads `state` |
| **B** | Add observation hook inside `backend/app`（minimal product patch） |
| **C** | Keep status quo — claim product After **cannot** be captured without intrusion |

---

## Scheme A — test-only stream harness

### How

Extend E-B6（or sibling module under `backend/tests/`）with a second capture mode:

```text
E-A2 prepare (product plan) → drain `_stream_generation_phase` → state After
```

Submodes（all tests-only；choose per target honesty）:

| Submode | LLM? | Honest for | Notes |
|---|---|---|---|
| A1 refusal drain | No | T4 / refuse After | Needs empty-gate plan；material already REAL_ELIGIBLE |
| A2 dual-no-key degraded | No | Mechanism / wiring via stream | ≠ chat faithfulness |
| A3 author-owned token patch | No real provider | Stream+align mechanics | Must not silent-use W9 `answer` |
| A4 live product LLM | Yes | T2/T3 product faithfulness | **Out of E-B14；需 owner 授权模型窗** |

### Evaluation

| Criterion | Assessment |
|---|---|
| Breaks experiment boundary? | **No** if: tests-only · honest `capture_mode`/`llm_called` · no formal flip · no P2-R1 inject |
| Needs `backend/app` modify? | **No** |
| Impacts P2-R1? | **No** if separate from `execute_frozen_case`；reuse **P2-R2 production_path** shape only，keep C12 INELIGIBLE |
| Can become formal evidence? | **Yes, conditionally** — after owner unlock + reserved write auth；today E-B2 freeze requires `llm_called=false`，故 formal 首批宜 A1/A2/A3；A4 另需 contract thaw |

### Residual for A alone

- Harness not implemented yet（E-B6 skips stream）  
- Gold ↔ After hash rebind for T2/T3  
- Formal write / `E-B_FORMAL_READY` still locked  
- A4 unauthorized in this track  

---

## Scheme B — observation hook in `backend/app`

### How（hypothetical）

e.g. callback / event after `state["content"]`/`citations` write，or side-channel dump before `done`.

### Evaluation

| Criterion | Assessment |
|---|---|
| Breaks experiment boundary? | **Yes** — product instrumented for eval；「产品 path」主张被污染 |
| Needs `backend/app` modify? | **Yes**（违反本轨「不改 runtime」） |
| Impacts P2-R1? | **Risk** — 任何生成相旁路可能混淆 control-plane / harness 归因 |
| Can become formal evidence? | **Weak / dispreferred** — 证明的是「挂了 hook 的产品」而非现网默认路径；不如 A 的直调同一函数 |

### Why not needed

Capture point **already exists**：mutable `state` + public（tests 已 import）`_stream_generation_phase`。Hook 不增加诚实度，只增加产品表面积。

**Reject for E-B After clearance.**

---

## Scheme C — status quo = impossible without intrusion

| Criterion | Assessment |
|---|---|
| Factually correct? | **No** — A proves capture is feasible without `backend/app` |
| Breaks experiment boundary? | N/A（inaction） |
| Needs `backend/app`? | N/A |
| Impacts P2-R1? | None |
| Formal evidence? | **Cannot clear B2′** — leaves product stream After absent |

**Reject as strategy.** Status quo explains *current* B2′ residual（E-B6 故意不调 stream），不是能力上限。

---

## Comparison matrix

| | A test harness | B app hook | C status quo |
|---|---|---|---|
| Capture product stream After? | **Yes** | Yes（redundant） | **No**（by choice） |
| `backend/app` change | No | Yes | No |
| Experiment boundary | Intact if labeled | Broken / polluted | Intact but stuck |
| P2-R1 safe | Yes if no inject | Risky | Neutral |
| Formal evidence potential | Conditional YES | Dispreferred | No |
| Clears B2′ alone? | Not until impl + unlock + write | No | No |

---

## Forbidden conflations

| Conflation | Why wrong |
|---|---|
| A3 patched tokens ≡ live product LLM After | Mechanism ≠ faithfulness |
| A2 degraded ≡ chat quality | Degradation body |
| E-B6 isomorphic ≡ Scheme A | Isomorphic never calls stream |
| Implementing A ⇒ `E-B_FORMAL_READY=YES` | Capture harness ≠ formal gate |
| Using P2-R1 inject to “get After faster” | H1 harness failure class |
