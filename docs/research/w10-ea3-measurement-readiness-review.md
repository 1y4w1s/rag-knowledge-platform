# W10 E-A3 — Measurement Readiness Review

> **Type:** research review only (no code, no runtime, no LLM, no P2-R1 rerun)  
> **Date:** 2026-08-24  
> **Product:** 索隐  
> **Question:** Is the W10 Direction-A measurement framework ready to open a **new formal evaluation window**?  
> **This file does not:** change product behavior, unblock P2-R1, rewrite frozen oracles, or claim a product PASS.

**Evidence labels (mandatory):**

| Label | Meaning |
|---|---|
| **PROVEN** | Implemented and tested, or frozen in docs/artifacts (cite paths) |
| **REMAINING** | Requires a formal eval window / batch run / additional execution coverage |
| **NOT SOLVED** | Requires a new contract or product/program decision |

---

## 0. Pointers (authoritative sources)

| Role | Path |
|---|---|
| Scope ownership (Direction A) | `docs/research/project-boundary/w10-scope-ownership-decision.md` |
| Post-W9 boundary | `docs/research/project-boundary/w10-boundary-review.md` |
| E-A1 protocol | `docs/research/w10-ea1-scope-eligibility/` (`README.md`, `01`–`05`) |
| E-A2 harness | `backend/tests/w10_ea2_scope_eligibility.py` |
| E-A2 tests | `backend/tests/test_w10_ea2_scope_eligibility.py` |
| W9 frozen cases | `backend/tests/fixtures/l4_critic/w9-critic-cases.json` |
| W9 frozen oracle | `backend/tests/fixtures/l4_critic/w9-critic-capability-contract.json` |
| W9 frozen critic reports | `backend/tests/fixtures/l4_critic/w9-critic-p2-injected-reports.json` |
| P2-R1 independent review (BLOCKED) | `backend/tests/fixtures/l4_critic/w9-critic-p2-r1-independent-review.json` |
| Forbidden inject path (historical) | `backend/tests/w9_critic_p2_r1_harness.py` (`execute_frozen_case`) |
| Prior product-path exploration (not E-A1 SSOT) | `backend/tests/w9_critic_p2_r2_protocol.py`, `w9_critic_p2_r3_formal_runner.py` |
| Progress SSOT | `docs/status/progress.md` (P2-R1 still **BLOCKED**) |

---

## 1. Executive conclusion

**Verdict: CONDITIONAL — ready only for a narrow, zero-LLM formal window bound to E-A2; not ready for a P2-R1-unblocking or generation-final / Critic-oracle formal window.**

| Intended formal window | Go / no-go |
|---|---|
| **Narrow E-A2 window:** static eligibility on the frozen 12; C12 refused before plan; C01–C11 isomorphic `AgentToolScope` + `prepare_agent_generation`; citation-scope scorer; reserved suite artifact; **no LLM**; **P2-R1 remains BLOCKED** | **CONDITIONAL GO** if blockers in §7 (batch runner + reserved artifact + protocol-binding + honesty of “plan citations ≠ generation-final”) are closed *in that window’s plan* |
| **Broad window:** score C12 on product path; 12/12 PASS; unblock P2-R1; treat inject/probe as product FAIL; Critic action mapping; `state["citations"]` after `_stream_generation_phase` | **NO-GO** |
| **Reuse P2-R1 `execute_frozen_case` or treat P2-R3 formal runner as E-A1 SSOT** | **NO-GO** |

**Criteria that must all be true before even the narrow window is “measurement-valid”:**

1. Runner identity is **E-A2** (`PROTOCOL_VERSION = w10_ea2_scope_eligibility_v1`), not P2-R1 inject and not P2-R3 as silent substitute.  
2. C12 stays `INVALID_FOR_PRODUCT_PATH_EXECUTION` / out of `pass_rate` denominator.  
3. Scorer never uses body-diff as `safe_outcome` (E-A1 `04` F3).  
4. Frozen cases/oracle files are **not** silently edited.  
5. Artifact records eligibility, executor path, allowed scope, scored citations.  
6. Claims distinguish **plan-construction citations** from **generation-final citations**.  
7. P2-R1 classification remains `MEASUREMENT_PROTOCOL_MISMATCH` / BLOCKED.

This review **did not** execute pytest, eval, or models. Unit-test *existence* is **PROVEN** in source; CI green for E-A2 is **REMAINING**.

---

## 2. What “formal evaluation window” means here

E-A1 (`05-dod-checklist.md`) authorized a later **measurement harness I** (now E-A2), explicitly **not** P2-R1 unblock. W10 Decision experiment **E-A2** is the scorer for `final citations ⊆ allowed scope`.

A **formal** window (contrast: W9 P3 reserved result schema; W9 P2-R3 `FORMAL_FROZEN_ELIGIBLE_PRODUCT_PATH_RERUN`) additionally needs:

- a named protocol version and reserved result path  
- complete frozen-suite enumeration (12/12 classified; eligible executed or honestly refused)  
- measurement-validity vs product-capability separation  
- stop rules against 11/11 → 12/12 extrapolation (E-A1 T2)

E-A2 today is a **deterministic adapter + unit tests**. It is **not** yet a reserved formal-run artifact.

---

## 3. Dimension 1 — Executor correctness

### 3.1 What E-A2 implements

`execute_product_path_plan` (`backend/tests/w10_ea2_scope_eligibility.py`):

1. `classify_case_eligibility` first.  
2. If ineligible (C12): `executor_path=refused_ineligible`, no plan, no scope instance.  
3. If eligible: real `AgentToolScope(visible_kb_ids=frozenset(stable_uuid(allowed_kb)))` — **not** `MagicMock`.  
4. Synthesize `AgentStepRecord` hits from **scoped** frozen evidence only (`build_scoped_step_records`).  
5. Monkeypatch `finalize._load_retrieved_chunks` (no live DB).  
6. Call production `prepare_agent_generation` (`backend/app/services/agent/finalize.py`).  
7. Assert every `gated_chunks[].kb_id` ∈ allowed UUID set.  
8. **Does not** call `execute_frozen_case` / inject `gated_chunks=initial_chunks`.

Tests: `test_product_path_executor_uses_real_scope_and_prepare` (C01 only), `test_c12_executor_refuses_before_plan`.

### 3.2 Alignment with E-A1 `01` / `02` E1

E-A1 allows **either** real `run_react_loop` tool dispatch **or** an isomorphic `steps → prepare_agent_generation` path. E-A2 takes the isomorphic branch.

| Check | Status | Label |
|---|---|---|
| Forbidden inject path not used for product denom | Code + tests refuse C12; inject entry forces invalid even for C01 | **PROVEN** |
| Real `AgentToolScope` type constructed for eligible cases | `build_agent_tool_scope`; C01 test asserts `isinstance(..., AgentToolScope)` | **PROVEN** |
| Plan members from scoped steps only | Guard loop on `gen_plan.gated_chunks` | **PROVEN** |
| Live `run_react_loop` + `resolve_kb_ids` deny | Not called; scope object is **not** passed into `prepare_agent_generation` (API has no `tool_scope`) | **REMAINING** (if window claims tool-layer deny) |
| True thorough order: scoped retrieval then plan | Steps are fixture-synthesized, not tool-dispatched | **REMAINING** (validity: isomorphic, not live retrieval) |
| `_stream_generation_phase` / `align_citations_to_answer` / `state["citations"]` | Not invoked | **REMAINING** for any “generation-final citation” claim |
| Default scored list = `gen_plan.citations` | `artifact_from_execution` | **PROVEN** as current behavior; **NOT SOLVED** vs E-A1 `04` definition of final citation if the window pretends these are post-generate `state["citations"]` |
| Executor coverage C02–C11 | Only C01 async executor test | **REMAINING** |
| Dual stack: P2-R2 `execute_production_path_case` still generates with mocked tokens + critic | Still present; **must not** be the W10 formal runner unless explicitly scoped | **PROVEN** coexistence; **REMAINING** to bind the new window |

**Executor finding:** Correct for **plan-front admission** measurement. Incomplete for **product thorough generation-final** measurement. Opening a formal window that *names* E-A1 `01` step 5–6 without extending the executor would be a protocol mismatch of the same family as P2-R1 (wrong observation point).

---

## 4. Dimension 2 — Eligibility classification

### 4.1 Static algorithm vs E-A1 `02` / `03`

`classify_case_eligibility`:

| Fixture pattern | Classification | Matches protocol? |
|---|---|---|
| Inject / MagicMock planned entry | `INVALID_FOR_PRODUCT_PATH_EXECUTION`, out of denom | Yes |
| scoped empty ∧ foreign non-empty (C12) | INVALID, `UNMAPPED_UNDER_DIRECTION_A`, `PRODUCT_PATH_ELIGIBILITY_PRECONDITION` | Yes |
| foreign empty ∧ scoped non-empty (C01–C11) | eligible, in denom | Yes |
| mixed scoped+foreign | INVALID (no such W9 case today) | Yes (future-proof) |
| both empty | eligible “refusal channel” | Protocol allows; **no such case in frozen 12** |

Frozen evidence (`w9-critic-cases.json`): C01–C11 `provenance=current_run_retrieval`, `ws-main` / `kb-main`; C12 only `ws-other` / `kb-other` / `foreign_workspace_fixture`. **PROVEN** by fixture grep; classifier tests **PROVEN** in `test_w10_ea2_scope_eligibility.py`.

### 4.2 Gaps

| Gap | Label |
|---|---|
| Eligibility is model-free (E-A1 T12) | **PROVEN** |
| C12 never in `pass_rate` (`aggregate_pass_rate`, `c12_in_denominator`) | **PROVEN** in unit tests with in-memory artifacts |
| P2-R3 `classify_case_eligibility` hardcodes C12 as `DEFENSE_IN_DEPTH_PROBE` + `MEASUREMENT_PROTOCOL_INVALID` — parallel vocabulary, not E-A1 string `INVALID_FOR_PRODUCT_PATH_EXECUTION` | **PROVEN** dual taxonomy; **NOT SOLVED** which string a *program* artifact must emit unless the new window freezes E-A2 strings |
| Capability contract still has C12 `in_capability_denominator: true` | **PROVEN** in `w9-critic-capability-contract.json`; **NOT SOLVED** (E-A1: do not silently edit; 11-vs-12 suite decision is a program decision) |
| Suite-level formal run of `enumerate_frozen_eligibility` written to reserved JSON | **REMAINING** |

**Eligibility finding:** Classification rules for the current 12 are **PROVEN** at unit-test granularity. They are sufficient to *start* a formal window that only re-records this split. They do **not** make C12 product-path-scorable.

---

## 5. Dimension 3 — Scorer completeness

E-A1 `04` required proposition: `final_citation_set ⊆ allowed_scope`. P2-R1 body-diff `safe_outcome` is forbidden (F3) — **PROVEN** false-pass in independent review (`w9-critic-p2-r1-independent-review.json`: `safe_outcome_false_pass_count: 1`).

### 5.1 Implemented (`score_final_citations`)

| Contract item | E-A2 | Tests | Label |
|---|---|---|---|
| S1 KB ∈ allowed ids or UUIDs | Yes | Foreign UUID → `FOREIGN_CITATION` | **PROVEN** |
| S2 workspace if present | Yes | No dedicated WS-fail unit test | **PROVEN** in code; **REMAINING** test |
| S3 empty `chunk_id` → unsupported | Yes | Missing chunk_id test | **PROVEN** |
| S4 gated set when snapshot provided | Yes | No dedicated gated-fail unit test | **PROVEN** in code; **REMAINING** test |
| S5 empty list ⊆ allowed | Yes | Empty + ineligible → `safe_outcome is None`; empty + eligible → True | **PROVEN** |
| F3 body-diff not used | `del initial_content, final_content`; `body_diff_used_for_safety=False` | Contrast vs `provisional_body_diff_safe_outcome` | **PROVEN** |
| Ineligible → `safe_outcome is None` | Yes | C12 test | **PROVEN** |
| `post_recovery_scope_violation` (E-A1 safe_outcome ∧ P2-R2 scorer) | **Absent** (no generation/critic calls) | — | **REMAINING** if window includes recovery; **N/A** for plan-only window |
| F5 text leak (foreign name in body, clean citations) | Not scored | — | **REMAINING** (nice-to-have observation; E-A1: does not replace ⊆) |
| F6 critic chunks scored as citations | No critic path | — | **REMAINING** if generation/critic added |
| F7 `None` vs `frozenset()` scope | C12 cannot use `None` to legalize `kb-other` in `build_agent_tool_scope` (always allowed UUIDs) | No explicit F7 test | **REMAINING** as negative unit |
| F8 oracle sticker (empty plan → SCOPE_VIOLATION PASS) | Scorer does not map critic actions at all | — | **PROVEN** non-mapping; **NOT SOLVED** if someone scores C12 critic oracle on this path |
| Missing `kb_id` but present `chunk_id` | S1 skipped (`kb_token is None`) | Untested | **REMAINING** (possible false ⊆) |
| Product citation shape | `workspace_chunk_to_citation` has `kb_id`, **no** `workspace_id` (`executor.py`) | S2 inert on real plan citations | **PROVEN** shape gap |
| Critic/control-plane oracle (C01–C11 expected_action) | Not in E-A2 scorer | Covered historically by P2-R1/R3 CP, not E-A2 | **REMAINING** for CP formal rerun; **out of E-A2 charter** if window is scope-only |

E-A1 eligible `safe_outcome` also required `unsupported==0`, `foreign==0`, `¬ post_recovery_scope_violation`. E-A2 sets `safe_outcome = scope_ok` when eligible, where `scope_ok` already folds S1–S4 counts. Recovery flag is the missing conjunct.

**Scorer finding:** **PROVEN** complete for **plan/static citation-scope** and for killing F3. **Not complete** for E-A1’s full “generation-final + recovery” safety definition. Eligible empty citations ⇒ `safe_outcome=True` without checking whether the frozen oracle allows refusal (E-A1 S5 caveat) — **NOT SOLVED** as an oracle-policy issue if the window treats E-A2 `safe_outcome` as critic-capability PASS.

---

## 6. Dimension 4 — Artifact requirements

### 6.1 Per-case (E-A2)

`ARTIFACT_FIELDS`: `case_id`, `eligibility`, `classification`, `executor_path`, `final_citations`, `allowed_scope`, `scorer_result`. Extra: `protocol_version`, `plan_refusal`, `gated_chunk_ids`. `validate_artifact_schema` only checks **key presence**, not types/enums/executor allowlist.

**PROVEN:** `test_artifact_schema_contains_required_fields`; C01/C12 artifact round-trip in executor tests.

### 6.2 Suite-level formal artifact (missing vs W9 P3 / P2-R3)

W9 P3: reserved filename + schema module that **must not** write the result until the formal run (`w9_critic_p3_r1_artifact_schema.py`).  
W9 P2-R3: `FORMAL_ARTIFACT_NAME = w9-critic-p2-r3-full-product-rerun.json`, protocol `w9_critic_p2_r3_formal_product_rerun_v1`.

W10 E-A2: **no** reserved `w10-ea2-*.json` schema, **no** batch writer, **no** `base_sha` / `run_id` / `measurement_validity` envelope, **no** allowlist preventing overwrite of P2-R1 independent review.

| Requirement | Status |
|---|---|
| Per-case field set for adapter tests | **PROVEN** |
| Reserved formal result path + “do not write until formal window” | **REMAINING** |
| Completeness gate: 12 classified, C12 invalid counted, denom=11 | Logic **PROVEN** in `aggregate_pass_rate`; suite file **REMAINING** |
| Probe vs product artifact isolation (E-A1 D6) | E-A2 has no probe runner (good); P2-R1/R2 probe still exists | **PROVEN** separation in E-A2; **REMAINING** operational discipline |
| Independent-review-class metrics (`unsafe_accept`, anti-degenerate) | Not in E-A2 | **REMAINING** (not required for narrow scope window) |

**Artifact finding:** Unit-level artifacts are ready. **A formal evaluation window is not artifact-ready** until a reserved suite JSON contract exists. That contract can be *authored in the eval window’s plan*, but it is a **blocker** for calling any in-memory pytest “the formal result.”

---

## 7. Dimension 5 — Remaining validity threats (E-A1 T1–T12)

| ID | Threat | After E-A2 | Label |
|---|---|---|---|
| T1 | Harness vs product path | Inject banned for denom; isomorphic steps still not live tools | **PROVEN** mitigated for H1; **REMAINING** residual (synthetic steps) |
| T2 | 11/11 extrapolation | Invalid count kept in aggregator | **PROVEN** in code; **REMAINING** in any human/progress write-up |
| T3 | Oracle sticker | C12 not scored as CP PASS | **PROVEN** in eligibility; **NOT SOLVED** if C12 oracle is remapped without a contract window |
| T4 | Body diff | Forbidden in E-A2 scorer | **PROVEN** |
| T5 | Non-final citations | Default score is **plan** citations | **REMAINING** if labeled “final”; honest plan-front label **mitigates** |
| T6 | None vs empty scope | No F7 unit | **REMAINING** |
| T7 | H2 as CVE | E-A2 does not run polluted-plan probe | **PROVEN** not claimed; E-B0/E-B1 still **NOT SOLVED** reachability |
| T8 | H3 as product bug | C12 stays unmapped | **PROVEN** stop rule; interface gap **NOT SOLVED** (Direction B deferred) |
| T9 | Measure then patch product | E-A2 is tests-only (`backend/app` untouched by design) | **PROVEN** for this harness; **REMAINING** process (D10) |
| T10 | Protocol as unblock | E-A1 README nails BLOCKED; progress.md still BLOCKED | **PROVEN** docs; **REMAINING** if a formal window’s summary is copied as PASS |
| T11 | Golden/Hit@3 as C12 peers | Protocol forbids; E-A2 loads only W9 critic suite | **PROVEN** |
| T12 | LLM for eligibility | Static classifier | **PROVEN** |
| **New T13** | Wrong runner (P2-R3 / P2-R1) used as W10 formal eval | Two stacks coexist | **REMAINING** (binding required) |
| **New T14** | `safe_outcome` on empty plan citations read as critic PASS | S5 vs oracle | **NOT SOLVED** scoring policy if mixed with CP metrics |

H2 (merge re-auth under illegal plan) remains **EXPERIMENTAL** / probe-only per W10 Decision. A new formal **product** window must not promote it.

---

## 8. Dimension 6 — Are existing W9 frozen cases sufficient?

**For the narrow E-A2 window: yes, as the unique frozen 12-case suite, with C12 as honest INVALID.**

| Use | Sufficient? | Label |
|---|---|---|
| Static 11 eligible + 1 foreign-only invalid | Yes; no mixed-evidence peer | **PROVEN** |
| C01–C11 original critic oracles remain the CP keys | Yes per E-A1 `03`; E-A2 does not consume them | **PROVEN** (docs); **REMAINING** (if CP rerun desired, use those oracles + a CP executor, not E-A2 alone) |
| C12 product-path score vs `RETRIEVE_MISSING_EVIDENCE` + `SCOPE_VIOLATION` | No — M1–M4 / Direction A world mismatch | **NOT SOLVED** (needs new product-path oracle **or** program decision to freeze 11-case suite) |
| Live scope deny / empty plan from `AgentToolScope` | Fixture cannot admit legal plan without changing C12 evidence | **NOT SOLVED** by cases; by design |
| Generation-final ⊆ after critic recovery | Frozen answers/citations are **critic-input** snapshots, not SSE done lists | **REMAINING** (would need execution, not new cases, if isomorphic gen is added) |
| Isolation regression with mixed in-scope + foreign evidence | No such frozen case | **NOT SOLVED** (do not invent; E-A1: none today) |
| Unblock P2-R1 (12 honest product-path observations) | E-A1 `05`: either new C12 oracle or explicit 11-case program decision | **NOT SOLVED** |

Capability contract still lists C12 `in_capability_denominator: true` while measurement denom is 11. That tension is **NOT SOLVED** and is exactly why P2-R1 stays BLOCKED even if 11/11 scope checks go green.

W9 P2-R1 independent review already recorded `product_path_valid_case_count: 11` and H1 CONFIRMED_PRIMARY. E-A2 **implements** that narrative; it does not add a 12th scorable product case.

---

## 9. Go / no-go recommendation

### 9.1 Open a **narrow** formal eval window? **CONDITIONAL GO**

Open it **only** if the window plan states all of:

- Protocol: `w10_ea2_scope_eligibility_v1` (E-A1 + E-A2).  
- Zero LLM, zero `backend/app` change, no P2-R1 rerun of `execute_frozen_case`.  
- Deliverable: reserved suite artifact (new filename, not overwriting `w9-critic-p2-r1-independent-review.json` or P3 reserved files).  
- Metrics: frozen=12, invalid=1 (C12), denom=11, `c12_in_denominator=false`.  
- Observation point: **plan-construction citations / gated_chunks**, explicitly **not** generation-final unless executor is extended in a later window.  
- P2-R1 remains BLOCKED; 11/11 scope-safe ≠ 12/12 product PASS.  
- Do not call P2-R3 `w9_critic_p2_r3_formal_runner` the W10 result.

**If those bindings are refused, verdict is NO-GO.**

### 9.2 Open a **broad** formal eval (P2-R1 successor / C12 product FAIL/PASS)? **NO-GO**

Blockers are **NOT SOLVED** (C12 oracle mapping, 12-case denom policy) plus **REMAINING** generation-final executor.

---

## 10. Blockers vs nice-to-haves

### Blockers (narrow window)

1. **No reserved suite-level formal artifact schema/path** (cannot treat pytest as the formal record).  
2. **No E-A2 batch/formal runner** enumerating all 12 and writing the reserved file.  
3. **Protocol binding:** forbid P2-R1 inject and forbid silent use of P2-R3 as W10 SSOT.  
4. **Honesty clause** in the artifact: scored citations are plan-gate outputs unless generation is added.  
5. **P2-R1 BLOCKED must remain** in the result envelope (`measurement_does_not_unblock_p2_r1: true` or equivalent).

### Blockers (broad / unblock window) — do **not** open

6. **C12 oracle unmapped under Direction A** (**NOT SOLVED**).  
7. **Program decision** on 12-case vs 11-case frozen capability denom vs contract `in_capability_denominator` (**NOT SOLVED**).  
8. **Generation-final + recovery scorer** (`state["citations"]`, F5/F6, `post_recovery_scope_violation`) (**REMAINING**).  
9. **Live `resolve_kb_ids` deny** if claiming production tool isolation rather than isomorphic plan admission (**REMAINING**).

### Nice-to-haves (do not block narrow GO)

- Unit tests: C02–C11 executor smoke, S2/S4 failures, F7, missing `kb_id`.  
- Stronger `validate_artifact_schema` (types, executor allowlist, C12 refused path).  
- F5 text-leak observation column.  
- Explicit CI job name for `test_w10_ea2_scope_eligibility.py` (this review did not inspect CI YAML exhaustively; hookup is **REMAINING**).  
- Mixed-evidence peer case (would be a **new fixture freeze**, not a nice-to-have of the current suite).

---

## 11. What is already PROVEN (do not re-research)

- Direction A ownership freeze: plan-front, Critic advisory, isolation system-owned L0 (`w10-scope-ownership-decision.md`).  
- P2-R1 BLOCKED / H1 harness injection primary (`w9-critic-p2-r1-independent-review.json`, `progress.md`).  
- E-A1 protocol complete as design (`w10-ea1-scope-eligibility/`, DoD checkboxes are design-delivery, not eval-green).  
- E-A2 adapter implements static eligibility, isomorphic plan executor, ⊆ scorer, C12 refuse, F3 rejection (`w10_ea2_scope_eligibility.py` + tests).  
- Frozen 12-case identity and C12 foreign-only shape (`w9-critic-cases.json`).

---

## 12. Stop

This review is complete. **No code, runtime, LLM, or P2-R1 rerun.** Next authorized step is a **separate** window: either (a) narrow E-A2 formal-run plan that closes §10 blockers 1–5, or (b) an explicit C12 **contract** freeze if product-path scoring is required — not a product isolation patch, and not P2-R1 PASS.
