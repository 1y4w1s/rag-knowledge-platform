# 03 — Forbidden claims verify

> Confirm hard non-claims survive E-B6–E-B9b and remain binding for any future formal window.

## Verdict

| Forbidden claim class | Still preserved? |
|---|---|
| Critic capability claim | **YES** |
| E-A5 reuse as generation PASS | **YES** |
| Generation quality proven before execution | **YES** |
| P2-R1 unblock | **YES** |

---

## 1. No Critic capability claim

| Control | Evidence |
|---|---|
| E-B1 / E-B2 forbidden claims | `Critic validated` / oracle capability banned |
| E-B6 smoke `measurement_claims.asserted` | ⊆ `{generation observation artifact produced}` |
| E-B9a | Rejects `expected_action` / `oracle_cases` / critic score keys |
| E-B9b | Same Critic oracle key reject + W9 suite identity reject |

**Invariant:** generation observation ≠ Critic observation. Critic fixtures remain slot providers, never generation gold.

---

## 2. No E-A5 reuse

| Control | Evidence |
|---|---|
| Distinct `observation_point` | E-A5 `plan_construction_citations` ≠ E-B `generation_final_content_and_citations` |
| Validator | E-A5 shapes rejected by E-B2/E-B6 |
| Write guard | E-B6 protects `w10-ea4-formal-window-result.json` from overwrite |
| Progress language | E-A5 11/11 must not be rewritten as generation PASS |

**Invariant:** plan-construction citation scope ≠ post-generation observation.

---

## 3. No generation quality proven before execution

| Control | Evidence |
|---|---|
| E-B2 allowed claim | Only `generation observation artifact produced` |
| Forbidden phrases | `generation quality proven` / `grounding proven` |
| E-B6 | `measurement_valid=false` on synthetic; grounding `NOT_OBSERVED` |
| E-B9a/9b | Schema examples explicitly `NOT_ANNOTATED_GOLD` / `NOT_FORMAL_MEASUREMENT` |
| E-B10 | Gate remains **NO** → no formal run occurred this window |

**Invariant:** contracts, constructs, and isomorphic wiring **do not** prove answer quality.

---

## 4. No P2-R1 unblock

| Control | Evidence |
|---|---|
| Envelope fields | `p2_r1_status=BLOCKED` ∧ `does_not_unblock_p2_r1=true` required |
| E-B0–E-B2 inheritance | Still in force |
| E-B6 / E-B9 modules | Do not call product Critic ON / P2-R1 clearance paths |

**Invariant:** E-B track cannot and must not claim P2-R1 unblocked.

---

## 5. Additional preserved non-claims（sanity）

Still forbidden to imply from E-B readiness docs:

- Hit@3 11/11 ⇒ generation PASS
- Multimodal vertical slice unlocked
- Critic default ON / production rollout
- Schema-example empty-gate / claim-gold rows = measured denominators
- `E_B_EMPTY_GATE_CONTRACT_READY=YES` ⇒ `E-B_FORMAL_READY=YES`

---

## 6. Allowed language for this review window

May write:

```text
W10 E-B10 generation observation final readiness review complete
E-B_FORMAL_READY = NO
```

May note: executor RESOLVED; claim-gold/empty-gate **contracts** frozen; formal observation **not** authorized.

Must not write:

- 「四靶正式观测已就绪 / 可开跑」
- 「generation quality / grounding proven」
- 「Critic validated」
- 「E-A5 11/11 covers generation」
- 「P2-R1 unblocked」
