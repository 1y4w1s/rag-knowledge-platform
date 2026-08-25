# W10 Boundary Review — Post-W9 Implementation Boundary

> **Type:** research boundary review only  
> **Not:** implementation plan, API spec, flag freeze, PR, merge, or runtime change  
> **Date:** 2026-08-24  
> **Scope:** Define what the **next phase after W9 Critic** may implement vs must not, using explicit evidence tiers  
> **Naming note:** “W10” here = **post-W9 phase boundary**. It is **not** an authorization to start `docs/remaining-plan.md` item “W10 Multimodal Vertical Slice,” and **not** Wave-2 F5 multimodal (AGENTS / PRD Wave 2+).

---

## Evidence tiers (mandatory)

| Tier | Meaning | How implementers must treat it |
|---|---|---|
| **PROVEN** | Demonstrated with frozen artifacts, logs, or merged product tests from W9 / existing system | May ground product or measurement decisions |
| **EXPERIMENTAL** | Tried or partially shown; incomplete eligibility, no quality score, or charter-only | May inform design; must not ship as default product claim |
| **SPECULATIVE** | Hypothesis / inference without solid evidence | Research only; needs its own protocol before I |

Every major claim below is tagged. Prefer the table rows over prose when deciding “may code / must not.”

---

## Sources consulted (W9 + program context)

### W9 P2 measurement lessons

| Path | Role |
|---|---|
| `docs/status/progress.md` (§ W9 P2-R1 / P2 provisional / P1) | Program SSOT: P2-R1 **BLOCKED**; P1 **PASS**; gates |
| `docs/remaining-plan.md` (§ W9 最终门禁更正) | P2-R1 BLOCKED → next unique atomic = ownership review |
| `docs/tasks/rag/w9-critic-p2-r1-next-remediation-analysis.md` | C12 harness vs product-path; ownership options A/B |
| `docs/tasks/rag/w9-critic-p2-offline-product-implementation.md` | Offline product experiment; C11 `PARTIAL` lesson |
| `docs/tasks/rag/w9-critic-p2b-c11-remediation-implementation.md` | C11 `rules_v1` revision executor closed (P2b) |
| `backend/tests/fixtures/l4_critic/w9-critic-p2-r1-independent-review.json` | Independent review correction artifact (referenced) |

### W9 P3-R1 formal result

| Path | Role |
|---|---|
| `backend/tmp/w9_p3_r1_real_local_run.log` | Real run: 7/7 TIMEOUT @ ~60.4 s; `MODEL_CAPABILITY_FAIL`; `P3_R1_STATE=PARTIAL` |
| `backend/tests/fixtures/l4_critic/w9-critic-p3-r1-real-local-semantic.schema.json` | Formal contract (reserved result JSON **absent** on branch) |
| `docs/tasks/rag/w9-critic-p3-semantic-construct-refreeze.md` | P3-R0.1 L0/L1/L2/L3 construct; timeout-in-denominator |
| `docs/research/local-agent-runtime-design/analysis.md` | R1 field table + interpretation |

### W9 P3-E1 runtime exploration

| Path | Role |
|---|---|
| `docs/research/local-model-runtime/REPORT.md` | Authoritative E1 report (latency / TTFT / tok/s / bottleneck) |
| `docs/research/local-model-runtime/README.md` | E1 index + link to E2 |

### W9 P3-E2 architecture charter

| Path | Role |
|---|---|
| `docs/research/resource-constrained-agent-runtime/README.md` | Charter index + program caveat |
| `docs/research/resource-constrained-agent-runtime/limitations.md` | Single-loop failure modes |
| `docs/research/resource-constrained-agent-runtime/architecture.md` | Runtime L0 / L1 / L2 planes |
| `docs/research/resource-constrained-agent-runtime/capability-ownership.md` | System vs model vs hybrid |
| `docs/research/resource-constrained-agent-runtime/runtime-policy.md` | Sync / async budgets; publish vs measure |
| `docs/research/resource-constrained-agent-runtime/hypotheses.md` | H1–H3 (**SPECULATIVE**) |
| `docs/research/local-agent-runtime-design/README.md` | E2 design companion index |
| `docs/research/local-agent-runtime-design/{analysis,architecture,latency-budget,model-routing,failure-handling,comparison}.md` | Numbers, routing, failure policy |

### Direction context (skim)

| Path | Role |
|---|---|
| `AGENTS.md` | P0 product floor; Wave 2+ bans; Hit@3 / alembic gates |
| `docs/status/progress.md` | V1.0 closed lines; active W9 gates |
| `docs/remaining-plan.md` | V1.0 mainline order vs deferred |

---

## 1. Current proven capabilities

| Capability | Tier | Evidence | Boundary implication |
|---|---|---|---|
| Critic is **advisory**; `_stream_generation_phase` is sole action/recommendation owner | **PROVEN** | W9 P1 PASS (`docs/status/progress.md`) | Do not make LLM Critic the publish owner |
| Critic ON → buffer draft; only publish/persist final candidate; citation regen before critic | **PROVEN** | W9 P1 | Keep final-boundary invariants in any later I |
| Critic retrieval/revision/deadline failures enter steps / `critic_actions` / EvidenceState / audit | **PROVEN** | W9 P1 | Accounting must remain if Critic path expands |
| Offline control-plane can consume frozen `CriticResult` without calling a model | **PROVEN** | W9 P2 offline product (`w9-critic-p2-offline-product-implementation.md`) | Measurement ≠ model intelligence |
| `rules_v1` `REVISE_FROM_EXISTING_EVIDENCE` is executable by the outer revision path (post method-gate fix) | **PROVEN** | W9 P2b C11 remediation | Method must not mask action semantics again |
| Deterministic Critic / citation-align / ThoroughRead / hybrid retrieve + SQL scope are usable without local GLM | **PROVEN** | P3-R0.1 L0; charter “what still gets right”; existing product | Prefer these on constrained hardware |
| P0: cited answers or explicit refuse; `kb_id`/workspace isolation; Member read-only + chat | **PROVEN** | AGENTS / PRD; W9 keeps rollout **NO** but does not repeal P0 | Never trade P0 for local-model demos |
| Under **60 s / mt512 / retry=NONE / Thinking OFF**, local `glm-4.6v-flash` semantic Critic: **7/7 TIMEOUT** → eval L1 `MODEL_CAPABILITY_FAIL`, state `PARTIAL` | **PROVEN** | `w9_p3_r1_real_local_run.log`; analysis.md | Sync 60 s semantic Critic is a **timeout generator**, not a quality gate on the measured host |
| Timeout / parse-fail stay **in** L1 denominator; L0 recovery must not upgrade L1 | **PROVEN** | P3-R0.1 construct | Do not invent “measurement invalid” to hide timeouts |
| Host class: 9.4B Q4 ≈7.95 GB on 8 GB VRAM; free VRAM/RAM often &lt;1 GB; latency variance extreme | **PROVEN** | E1 Phase 0–2 REPORT | Do not design co-resident second 7–9B or concurrent Agent gens as default |
| Sync semantic Critic ≤60 s as default SLA: **NO** | **PROVEN** (feasibility) | E1 recommendation + R1 pattern | Product must not enable this as interactive gate |
| P2-R1 independent review: **BLOCKED** / `MEASUREMENT_PROTOCOL_MISMATCH`; C12 not product-path-valid | **PROVEN** (measurement status) | progress.md; remediation-analysis; independent-review JSON | Cannot claim full P2-R1 PASS; cannot start P3 **product** claims from this status |

**Explicit non-proofs (do not upgrade):**

| Claim | Why not PROVEN |
|---|---|
| GLM can / cannot judge claim-status given more time | R1 timed out before scored output; E1 did not score |
| C12 is a production-reachable isolation bug | Independent review: harness injected foreign chunks; primary = harness bypass |
| Async Critic improves semantic quality | E1 only showed **latency completion** at 180–300 s (**EXPERIMENTAL**) |
| Runtime L0/L1/L2 charter improves hang rate | Design only (**SPECULATIVE** until H1–H3 tested) |

---

## 2. Current hypotheses only

| Id | Claim | Tier | Source | Falsification note |
|---|---|---|---|---|
| H1 | Fixed small model + stronger deterministic Runtime L0 → more P0-legal outcomes, fewer hangs | **SPECULATIVE** | `resource-constrained-agent-runtime/hypotheses.md` | Must not use eval L1 PASS as metric |
| H2 | Async semantic verification (180–300 s) improves annotation quality without raising interactive hang rate | **SPECULATIVE** | same | R1 scored **0** L1 outputs; quality unmeasured |
| H3 | System + small model beats isolated small-model loop on P0 × usefulness × latency-to-safe-outcome | **SPECULATIVE** | same | Same model size both arms |
| H4 | Single-flight + health cache reduces E1-class multi-minute stalls vs `parallel=4` overlap | **SPECULATIVE** | hypotheses.md (optional) | Needs ops protocol experiment |
| H5 | Non-stream JSON for L2 beats stream after killed-stream degradation | **SPECULATIVE** | hypotheses.md; E1-B secondary | E1 shows stream fragility, not A/B proof |
| C12-defense | Recovery merge / finalize lacks defense-in-depth scope re-auth when plan is already polluted | **EXPERIMENTAL** (probe under illegal internal input) | P2-R1 remediation-analysis §4–5 | Not proven production-reachable; ownership undecided |
| CriticScopeContext | Product needs explicit scope/provenance on critic/chunk interfaces to match frozen C12 oracle | **EXPERIMENTAL** (contract gap observed) | remediation-analysis §5 | Architecture review required before I |
| Async Critic latency-usable @ 180–300 s, single-flight, warm model | **EXPERIMENTAL** | E1 Phase 2 / role matrix | Completions observed ~75–145 s; **not** semantic score; fragile under RAM/VRAM pressure |
| Health-gated local generate + cloud failover / `refuse_degraded` | **SPECULATIVE** (policy) | E2 runtime-policy / architecture | Numbers mix measured envelopes + labeled inference |
| Multimodal vertical slice as immediate coding next | **SPECULATIVE** relative to W9 gates | remaining-plan mainline item 2 | Program currently gates on P2-R1 ownership first |

---

## 3. Features that should NOT be implemented yet

| Feature / change | Tier of “why not” | Reason |
|---|---|---|
| Runtime rollout of local / LLM Critic defaults ON | **PROVEN** gate | progress / remaining-plan: rollout **NO** |
| Treat sync semantic Critic @ ≤60 s as product SLA or interactive publish gate | **PROVEN** | R1 7/7 TIMEOUT; E1 sync Critic **NO** |
| Product remediation of C12 (recovery merge / CriticScopeContext) **before** scope/provenance **owner** decision | **PROVEN** program stop | remaining-plan: next unique task = read-only ownership review |
| Claim full P2-R1 PASS or start anti-degenerate / P3 **product** remediation from provisional 11/12 | **PROVEN** | Independent review BLOCKED; C12 invalid for product path |
| Write / overwrite `w9-critic-p3-r1-real-local-semantic.json` casually; re-run R1 disguised as E1 | **PROVEN** hygiene | E1/E2 non-goals; reserved JSON absent by design |
| Second 7–9B GGUF (or GPU embedder) co-resident with GLM on 8 GB laptop class | **PROVEN** envelope | E1 Phase 0; charter limitations |
| Inline LLM planner × N + generate + semantic Critic on same starved slot as default thorough path | **PROVEN** bottleneck + **EXPERIMENTAL** planner latency | E1 short planner ~116 s degraded; R1 critic timeouts |
| Score L0 recovery / L2–L3 PASS as eval L1 PASS; drop timeouts from denominator | **PROVEN** construct | P3-R0.1 `HIDDEN_RECOVERY_CANNOT_UPGRADE_L1` |
| Refuse citation-safe in-scope answers **only** because eval L1 timed out | **PROVEN** policy separation | E2 runtime-policy / failure-handling |
| Queue/Redis/new Critic APIs / flag default flips “from the charter” | **SPECULATIVE** → forbidden as I | E2 README: not an implementation window |
| Wave 2+: payment /积分 / F5 multimodal / public SaaS HTTPS as this phase | **PROVEN** AGENTS ban | Out of V1 enterprise default path |
| MEMORY distill / second memory agent on GPU; TOOL selection remediation; ADV P0–P5 re-open | **PROVEN** closed / NO_GO | progress: CLOSED_FOR_V1_0 / DEFER; charter warns |
| Multimodal “W10 Vertical Slice” coding while W9 P2-R1 ownership unresolved | **PROVEN** gate conflict | remaining-plan W9 最终门禁优先于 multimodal item |
| Best-of-N / retry amplification on formal semantic Critic | **PROVEN** protocol | R1 `retry_policy=NONE`; E2 async policy |

---

## 4. Features worth implementing next

Ordered for **boundary clarity**, not as a coding checklist. Any I window still needs its own plan after confirmation.

| Priority | Candidate | Tier | Why “worth” | Precondition |
|---|---|---|---|---|
| **0 (gate)** | Narrow **read-only** architecture review: scope/provenance invariant owned by **plan-front** (A) vs **finalize/critic depth** (B) | **PROVEN** next unique task | Unblocks honest P2-R1 / remediation sequencing | Docs/review only; no product patch in that window |
| **1** | If A: measurement-adapter / eligibility repair so C12 uses real `AgentToolScope` + plan construction; safe scorer checks final citation scope | **EXPERIMENTAL** → implementable after review | Fixes protocol mismatch without pretending product failed | Owner chooses A; separate measurement window |
| **1′** | If B: minimal defense-in-depth filter of `gated_chunks` against real scope before recovery merge (+ contract for provenance) | **EXPERIMENTAL** | Closes secondary probe gap | Owner chooses B; Sol-level narrow review already called out; negative regression list in remediation-analysis §10 |
| **2** | Docs-only **protocol freeze**: single-flight mutex, health cache, TTFT/idle-chunk watchdog, non-stream JSON for L2 | **EXPERIMENTAL** (E1 motivates) / design | Reduces E1-class stalls before any I | Still research; no LM Studio config commit as product |
| **3** | Keep / harden **Runtime L0** path: ThoroughRead + hybrid retrieve + `rules_v1` + citation boundary (no new GLM stages) | **PROVEN** value | Reliability without model size | Default flags stay OFF for LLM extras unless explicit product trigger |
| **4 (later research)** | Offline / async eval of claim-status with **declared** long timeout (new protocol ≠ silent R1 reuse) | **SPECULATIVE** quality; **EXPERIMENTAL** latency | Only way to test H2 | Separate research window; do not block chat publish |
| **5 (program later)** | After W9 gates clear: Flag/Default/Rollout Audit → Final Frozen Benchmark → Docs/Demo → RC | **PROVEN** remaining-plan order | V1.0 finalization | Not ahead of P2-R1 ownership |
| **Defer** | Multimodal vertical slice | Roadmap item | Explicitly **after** W9 Critic hardening in remaining-plan | Do not steal the W9 gate window |

**Not “worth implementing next” as product:** local sync Critic, GPU second model, MEMORY L4/L5 product claims, TOOL selection rework.

---

## 5. Research risks

| Risk | Tier | If ignored |
|---|---|---|
| **Measurement / product conflation** — treat harness C12 failure as production isolation bug | **PROVEN** trap | Wrong remediation; false security story |
| **Latency / intelligence conflation** — treat E1 “completed in 145 s” as semantic Critic PASS | **PROVEN** trap | Fake capability claims; bad rollout |
| **Healthy-band SLA** — ship assuming Critic-like 3.5–11.6 s | **PROVEN** variance | Production hangs under ordinary desktop load |
| **Hidden L1 upgrade** — L0-safe publish scored as L1 PASS | **PROVEN** construct risk | Corrupt capability narrative |
| **Charter → code leap** — implement queues/flags from E2 without plan + P2-R1 owner | **SPECULATIVE** process risk | Scope creep; WIP violations |
| **VRAM starvation cascade** — stream hang → kill → subsequent 60 s timeouts | **PROVEN** E1-B | Interactive path death spiral |
| **Contract gap** — freeze C12 oracle requiring provenance Critic cannot express | **EXPERIMENTAL** | Endless BLOCKED or dishonest oracle edits |
| **Program order skip** — start multimodal / final benchmark while Critic gates BLOCKED | **PROVEN** process | Undermines V1.0 credibility |
| **Cloud TTFT SLO applied to local GLM** | **PROVEN** mismatch | TECH NW-55 is cloud DeepSeek, not E1 host |

---

## 6. Recommended roadmap

### Phase framing

```
W9 P1 PASS ──► W9 P2 offline / P2b C11 ──► W9 P2-R1 BLOCKED (C12 eligibility)
                      │
                      ▼
         ★ NEXT: ownership review (A vs B) — docs only
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
     A: harness/eligibility    B: defense-in-depth product
        repair + rescore          fix (narrow I after plan)
          │                       │
          └───────────┬───────────┘
                      ▼
         Optional: mutex/health/watchdog protocol freeze (docs)
                      ▼
         Optional: async/offline semantic protocol (research ≠ R1 overwrite)
                      ▼
         Only then: consider P3 product claims / anti-degenerate / rollout audit
                      ▼
         remaining-plan: Multimodal slice → Final benchmark → RC → v1.0.0
```

### Recommended sequence (boundary, not tickets)

| Step | Work type | Tier basis | Stop if |
|---|---|---|---|
| **R0** | Scope/provenance **owner** decision (A vs B) | **PROVEN** required | Skipped or mixed with coding |
| **R1a / I1a** | Measurement eligibility + scorer (if A) | After R0 | Changes frozen P0 oracle silently |
| **I1b** | Minimal scope re-filter on recovery (if B) | After R0 + narrow plan | Broad Critic redesign / Golden churn |
| **R2** | Single-flight / health / watchdog **docs freeze** | **EXPERIMENTAL** E1 | Treated as shipped SLO |
| **R3** | New long-timeout semantic protocol (optional) | **SPECULATIVE** H2 | Pretends to amend R1 reserved JSON |
| **G** | Re-open P3 product / rollout / multimodal only when W9 gates allow | Program SSOT | Any earlier |

### Default posture until R0 completes

- **Runtime rollout:** NO  
- **Default LLM Critic / LLM planner:** stay OFF  
- **Interactive path:** L0 deterministic + retrieve + (cloud or skipped local gen); **no** sync 60 s semantic Critic  
- **Eval L1 @ 60 s:** historical FAIL observation remains valid under that contract  

---

## Boundary one-pager (for implementers)

| May do (after proper plan window) | Must not do (this phase) |
|---|---|
| Decide A vs B ownership in a review window | Patch C12 product code “while deciding” |
| Fix harness eligibility / safe scorer if A | Claim P2-R1 PASS from 11 valid cases |
| Narrow defense-in-depth scope filter if B | Enable sync local semantic Critic ≤60 s |
| Docs-only mutex/health/watchdog protocol | Ship Redis/queue/API from charter alone |
| Keep strengthening L0 rules/citation/isolation tests | Co-load second big GGUF; Wave 2+ features |
| Separate research protocol for long-timeout semantics | Overwrite R1 artifact; score timeouts out of denom |

---

## Stop here / next window

This file is a **research boundary review only**.

- **No** implementation plan that starts coding belongs in this document’s follow-through.  
- **No** `backend/app` changes, runtime flag flips, model calls, PRs, or merges are authorized by this review.  
- **Next window** must be a **separate plan (or explicit ownership-review) window** that cites this boundary, picks **one** atomic next task (recommended: R0 owner decision A vs B), and states DoD before any Implement window opens.

**Stop.** Implementation waits for that separate plan window.
