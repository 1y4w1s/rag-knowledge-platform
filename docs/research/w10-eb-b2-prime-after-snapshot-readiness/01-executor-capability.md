# 01 — E-B6 After executor capability

> Static review of `backend/tests/w10_eb6_generation_observation_executor.py` only.

## Verdict

| Capability | Status |
|---|---|
| Test-only After capture exists | **YES** |
| Zero-LLM isomorphic path (prepare → author body → real align) | **YES** |
| Product `_stream_generation_phase` wired | **NO** |
| Reserved formal write / `measurement_valid=true` | **HARD-LOCKED OFF** |
| Suitable as Full formal After source today | **NO** |

---

## 1. What E-B6 can do today

| Surface | Behavior |
|---|---|
| `observe_case` / `run_isomorphic_observation_suite` | E-A2 `execute_product_path_plan` → `capture_isomorphic_after` |
| `capture_isomorphic_after` | Author-owned `[eb6-synthetic:…]` body → `align_citations_to_answer` → fill `state["content"]` / `state["citations"]` |
| `AfterObservationSnapshot` | Before plan hash + after content/citations hashes + refusal/grounding status |
| `to_per_case_observation` | Maps into E-B2 `per_case_observation` slots |
| `build_smoke_observation_artifact` | Valid E-B2 envelope; **always** `measurement_valid=false` |
| `write_observation_artifact` | Non-reserved path only; refuses `measurement_valid=true` and reserved filename |

### Suite coverage

| Case class | After behavior |
|---|---|
| C01–C11 eligible | Non-null After content + citations（同构）；`targets_measured` smoke ⊆ `{T1}` |
| C12 | `INELIGIBLE`；`after_content` / `after_citations` remain `null`（不伪造） |
| Empty-gate suite `w10_eb_empty_gate_v1` | **Not in E-B6 runner**（仍绑 `w9_critic_frozen_12`） |

### Honesty locks（仍生效）

| Lock | Effect |
|---|---|
| `llm_called` | Forced `false` on isomorphic path |
| Fixture answer reuse | `_assert_not_fixture_answer` |
| `grounding_observation_status` | Eligible = `NOT_OBSERVED`（不假装 T2/T3） |
| Reserved `w10-eb2-generation-observation-result.json` | Write refused |
| Smoke invalid reason | `OTHER_PROTOCOL_BREAK` |

---

## 2. What E-B6 deliberately does *not* do

| Missing for B2′ clear | Why it matters |
|---|---|
| Call `_stream_generation_phase` | No **product** generation终态 snapshot |
| Owner-unlocked isomorphic formal | Cannot persist `measurement_valid=true` |
| Bind After body to claim-gold `content_sha256` | E-B6 body ≠ E-B12B `synthetic_authored` claim-text payload |
| Empty-gate After producer | T4 After not produced by this executor |
| `run_formal_observation` | Formal suite runner still absent |

---

## 3. Relation to E-B4 C1 vs C2

| Cond | Meaning | E-B6 impact |
|---|---|---|
| **C1** Executor exists | Cleared since E-B6 | **Still Met** |
| **C2** After snapshots obtainable for **formal** denominator | Requires honest终态 + authorized persistence | **Still Open residual（B2′）** |

C1 ≠ C2. 执行器存在只证明接线；正式分母仍缺产品/授权 After。
