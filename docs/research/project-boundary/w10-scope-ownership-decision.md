# W10 Scope Ownership Decision — Plan-Front vs Finalize/Critic Depth

> **Type:** research ownership decision only  
> **Not:** implementation plan, API spec, flag freeze, PR, merge, runtime change, or model call  
> **Date:** 2026-08-24  
> **Naming note:** “W10” here = **post-W9 Agent evolution boundary**. It does **not** authorize `docs/remaining-plan.md` “W10 Multimodal Vertical Slice,” Wave-2 F5 multimodal, or Critic runtime rollout.

---

## Evidence tiers (mandatory)

| Tier | Meaning | How readers must treat it |
|---|---|---|
| **PROVEN** | Demonstrated with frozen artifacts, logs, merged product tests, or program SSOT | May ground the ownership recommendation |
| **EXPERIMENTAL** | Tried or partially shown; incomplete eligibility, no quality score, or probe-only | May inform design; must not ship as default product claim |
| **SPECULATIVE** | Hypothesis / inference without solid evidence | Research only; needs its own protocol before I |

Claims below are tagged. Prefer tables over prose when deciding “what to research next / what not to code.”

---

## Decision question

**Who owns the scope / provenance invariant for the next Agent evolution step?**

| Direction | Short name | Ownership statement |
|---|---|---|
| **A** | **Plan-front intelligence** | Scope (and plan eligibility) is an **`AgentGenerationPlan` front invariant**: real `AgentToolScope` + plan construction admit only legal evidence; measurement and product both treat illegal plans as **out of product path** (or reject at construction). Intelligence / hardening invests **before** generate / revise. |
| **B** | **Finalize/Critic depth** | Scope / provenance is a **defense-in-depth invariant** at recovery merge, finalize gate, and/or Critic interfaces (`CriticScopeContext`, re-auth of `gated_chunks`). Intelligence / hardening invests **after** (or around) draft generation. |

This is the R0 gate named in [`w10-boundary-review.md`](w10-boundary-review.md) §4 / §6, grounded in [`w9-critic-p2-r1-next-remediation-analysis.md`](../../tasks/rag/w9-critic-p2-r1-next-remediation-analysis.md) §7.

---

## Sources consulted

| Path | Role |
|---|---|
| [`w10-boundary-review.md`](w10-boundary-review.md) | Post-W9 may/must-not boundary; R0 = A vs B |
| [`../../tasks/rag/w9-critic-p2-r1-next-remediation-analysis.md`](../../tasks/rag/w9-critic-p2-r1-next-remediation-analysis.md) | C12 BLOCKED; A/B options; H1–H4 |
| [`../resource-constrained-agent-runtime/capability-ownership.md`](../resource-constrained-agent-runtime/capability-ownership.md) | Scope = **system-owned** Runtime L0 |
| [`../resource-constrained-agent-runtime/README.md`](../resource-constrained-agent-runtime/README.md) | Runtime L0/L1/L2; eval L1 ≠ interactive |
| [`../local-agent-runtime-design/README.md`](../local-agent-runtime-design/README.md) | Local envelope; single-flight; no sync Critic |
| [`../local-model-runtime/REPORT.md`](../local-model-runtime/REPORT.md) | E1 latency / sync Critic **NO** |
| `docs/status/progress.md` / `docs/remaining-plan.md` | P2-R1 BLOCKED; rollout **NO**; next unique = ownership |

---

## Current state (evidence-separated)

### PROVEN

| Claim | Evidence |
|---|---|
| Control Plane validated: Critic **advisory**; `_stream_generation_phase` sole action/recommendation owner; offline CP consumes frozen `CriticResult` without a model | W9 P1 PASS; W9 P2 offline product |
| `rules_v1` revision executor closed for C11 (method-gate fix) | W9 P2b |
| Local semantic Critic under **60 s / mt512 / retry=NONE / Thinking OFF**: **7/7 TIMEOUT** → eval L1 `MODEL_CAPABILITY_FAIL`, `PARTIAL` | `w9_p3_r1_real_local_run.log`; P3-R0.1 construct |
| Sync semantic Critic ≤60 s as default SLA: **NO** | R1 + E1 recommendation |
| Resource-constrained host: ~9.4B Q4 ≈7.95 GB on 8 GB VRAM; free RAM/VRAM often &lt;1 GB; extreme latency variance | E1 Phase 0–2 |
| P2-R1 **BLOCKED** / `MEASUREMENT_PROTOCOL_MISMATCH`; C12 not product-path-valid | Independent review; remediation-analysis |
| C12 primary: harness injected foreign chunks into internal `_stream_generation_phase` / mocked tool dispatch (**H1 CONFIRMED_PRIMARY**) | remediation-analysis §3, §6 |
| Scope isolation is **system-owned** (Runtime L0); never “critic-class” | capability-ownership.md |
| W10 boundary review completed; product C12 patch **before** owner decision forbidden | w10-boundary-review §3 |

### EXPERIMENTAL

| Claim | Evidence / limit |
|---|---|
| Recovery merge / finalize lack defense-in-depth scope re-auth when plan already polluted (**H2 CONFIRMED_SECONDARY**) | Probe under **illegal internal** input only; production reachability **not** shown |
| Product Critic / chunk interfaces lack provenance fields demanded by frozen C12 oracle (**H3 contract gap**) | Interface observation; not a scored product bug |
| Async Critic latency-usable @ 180–300 s (single-flight, warm) | E1 completions ~75–145 s; **no** semantic quality score |
| Short LLM planner on degraded slot ~116 s | E1; not a product default path |

### SPECULATIVE

| Claim | Why speculative |
|---|---|
| Async semantic Critic improves answer quality (H2 quality arm) | Latency only measured; R1 scored **0** L1 outputs |
| Runtime L0/L1/L2 charter reduces hang rate (H1/H3/H4) | Design only until protocol experiments |
| C12 is a production-reachable isolation bug | Primary evidence is harness bypass |
| Plan-front “intelligence” (LLM planner) improves thorough RAG on this host | Contradicted as **default** by E1 bottleneck; ThoroughRead already preferred |
| Finalize/Critic **semantic** depth (LLM Critic) unblocks V1.0 gates | Sync path **PROVEN** infeasible; quality unproven |

---

## Direction A — Plan-front intelligence

### Definition (this decision)

**Primary meaning (C12 / P2-R1):** Treat legal scope as a **front invariant of plan construction**. Fix **measurement eligibility** so C12 (and peers) exercise real `AgentToolScope` + `prepare_agent_generation` / production plan construction; scorer checks **final citation ⊆ allowed scope**. Product code changes are **not** required to unblock honest measurement—unless a later product bug is shown on the real path.

**Secondary meaning (Agent evolution):** Prefer investing “intelligence” **up-front** as **deterministic plan quality** (ThoroughRead, step budgets, scope admit) rather than more model stages later. **Not** “enable LLM planner by default” on the starved local slot.

### 1. Capability gain

| Aspect | Tier | Assessment |
|---|---|---|
| Restores honest P2-R1 / C12 eligibility narrative | **PROVEN** need; A is the matching fix class | Unblocks program sequencing without inventing a production isolation story |
| Improves production isolation vs today’s real path | **SPECULATIVE** for A alone | Production already rejects forbidden KB at tools / plan reload; A does not claim a new runtime capability |
| Agent “smarter plans” via LLM planner | **SPECULATIVE** / **EXPERIMENTAL** cost | E1: planner-like work competes with generate; default thorough path should stay ThoroughRead (**PROVEN** preference in charter) |
| Control-plane leverage | **PROVEN** alignment | Offline CP + L0 rules already work without GLM |

**Net capability gain for next Agent step:** **measurement integrity + correct ownership story** (high program value), **not** a new semantic model capability.

### 2. Reliability impact

| Aspect | Tier | Assessment |
|---|---|---|
| Avoids coding a “security fix” for a harness-only fault | **PROVEN** risk avoided | Measurement/product conflation trap (boundary review §5) |
| Interactive hang rate | **PROVEN** neutral-to-positive | No extra sync GLM Critic/planner stages |
| If misread as “ship LLM planner front” | **PROVEN** reliability harm | Inline planner × N + gen on same slot = E1/R1 failure mode |

**Net reliability:** **Favorable** when A stays measurement / deterministic plan-front; **hostile** if A is reinterpreted as LLM plan-front.

### 3. Local model feasibility

| Aspect | Tier | Assessment |
|---|---|---|
| A (eligibility / plan construction / scorer) | **PROVEN** feasible without local GLM | Scope tools + SQL already exist |
| A-as-LLM-planner | **PROVEN** poor default on measured host | Degraded planner ~116 s; VRAM starved |

**Net:** Plan-front **system** work is local-model-feasible; plan-front **model** work is not a sensible next invest.

### 4. Evaluation difficulty

| Aspect | Tier | Assessment |
|---|---|---|
| Re-eligible C12 / scorer final-citation scope | **EXPERIMENTAL** → tractable | Clear stop rules already written (remediation §7 A, §10 item 9) |
| Oracle mapping if product path never admits foreign plan | **EXPERIMENTAL** | May remain `INVALID_FOR_PRODUCT_PATH_EXECUTION` without lying |
| Avoids needing Critic provenance fields for this gate | **PROVEN** simplification | Contract gap (H3) can stay deferred |

**Net:** Evaluation is **harder than a green checkbox**, but **easier than B’s interface expansion**, and does not depend on semantic Critic scores.

### 5. Alignment with current architecture

| Aspect | Tier | Assessment |
|---|---|---|
| Scope = system-owned L0 | **PROVEN** match | capability-ownership.md |
| Critic remains advisory | **PROVEN** match | Does not make Critic the isolation owner |
| Runtime L0 Safety Plane first | **PROVEN** match | Charter / local-agent-runtime-design |
| Does not require sync eval L1 | **PROVEN** match | R1/E1 |

**Net:** **Strong alignment** with validated Control Plane and resource-constrained charter.

---

## Direction B — Finalize/Critic depth

### Definition (this decision)

**Primary meaning (C12 / P2-R1):** Treat scope/provenance as **defense-in-depth** at recovery merge / finalize / Critic: re-filter `gated_chunks` with real `AgentToolScope` before merge; optionally introduce `CriticScopeContext` and provenance on chunks/results; fail closed when scope cannot be proven.

**Secondary meaning (Agent evolution):** Deepen Finalize/Critic (rules depth, semantic Critic, revision loops) as the next intelligence investment.

### 1. Capability gain

| Aspect | Tier | Assessment |
|---|---|---|
| Closes secondary probe gap (polluted plan → foreign citations survive merge) | **EXPERIMENTAL** | Real code path under illegal input; production reachability unknown |
| Expresses frozen C12 oracle provenance in product interfaces | **EXPERIMENTAL** contract | H3 gap is real; B is the class of fix that could close it |
| Semantic Critic depth (LLM claim-status) | **PROVEN** sync fail; quality **SPECULATIVE** | Must not be the B “next step” on local host |
| Broader Critic as publish gate | **PROVEN** forbidden | Advisory invariant; rollout NO |

**Net capability gain:** **Defense-in-depth isolation** (narrow) is plausible; **semantic Critic depth** is not a proven capability unlock.

### 2. Reliability impact

| Aspect | Tier | Assessment |
|---|---|---|
| Narrow merge re-filter (no new model) | **EXPERIMENTAL** / likely reliability-positive if carefully scoped | Fail-closed when no verifiable evidence; must preserve `visible_kb_ids=None` semantics (remediation §9) |
| Surface area: finalize, stream recovery, critic adapters, all generate entrances | **PROVEN** process risk | remediation §7 B: not a one-line patch; needs Sol-level narrow review |
| Semantic / async Critic as interactive depth | **PROVEN** reliability harm if sync; async unknown hang/queue risk | R1 7/7; E1 sync NO |

**Net reliability:** Narrow deterministic B-filter **may** help; **Critic-depth-as-model** **hurts** interactive reliability on current hardware.

### 3. Local model feasibility

| Aspect | Tier | Assessment |
|---|---|---|
| Deterministic scope re-filter at merge | **PROVEN** feasible without GLM | Same as other L0 gates |
| CriticScopeContext plumbing | **EXPERIMENTAL** engineering cost; model-independent | Interface/contract work |
| LLM Critic depth locally | **PROVEN** infeasible as sync SLA | Use only offline/async research protocols later |

**Net:** Local-feasible **only** for deterministic finalize/merge depth—not for semantic Critic depth.

### 4. Evaluation difficulty

| Aspect | Tier | Assessment |
|---|---|---|
| Negative regression list is long and precise | **EXPERIMENTAL** but well-specified | remediation §10 (9 items) |
| Distinguishing harness probe vs production reachability | **PROVEN** hard requirement | Easy to over-claim “isolation fixed” |
| Oracle vs adapter mapping still required | **EXPERIMENTAL** | H3 may force contract freeze before fair score |
| Semantic Critic eval | **PROVEN** hard under 60 s; longer timeout = new protocol | Must not reuse R1 reserved JSON casually |

**Net:** Evaluation is **harder** than A for program unblock; risk of **false security narrative** is higher.

### 5. Alignment with current architecture

| Aspect | Tier | Assessment |
|---|---|---|
| Isolation should remain abort-class, not critic-class | **PROVEN** tension if B puts isolation “into Critic” | capability-ownership: never convert leak to `UNVERIFIABLE` / critic FAIL |
| Defense-in-depth at merge/finalize (system L0) | **EXPERIMENTAL** alignment | Acceptable **if** owned by system finalize/recovery, **not** by LLM Critic |
| Expanding Critic interface toward provenance | **EXPERIMENTAL** | Aligns with oracle; expands blast radius |
| Resource-constrained charter (L2 async only) | **PROVEN** misalignment if B means sync semantic depth | |

**Net:** **Conditional alignment**—only the **system-owned finalize/merge** slice of B aligns; **Critic-as-isolation-owner** and **local semantic depth** misalign.

---

## Comparative matrix

| Criterion | A Plan-front | B Finalize/Critic depth | Prefer |
|---|---|---|---|
| **1. Capability gain** | Unblocks honest measurement; little new runtime magic | Possible DiD isolation; semantic depth unproven | **A** (program capability) |
| **2. Reliability impact** | Neutral/positive if deterministic; bad if LLM planner | Narrow filter possibly +; model Critic − | **A** |
| **3. Local model feasibility** | No GLM required for primary A | DiD filter OK; semantic Critic sync **NO** | **A** (and narrow non-model B later) |
| **4. Evaluation difficulty** | Eligibility + final citation scope checks | Long regressions + reachability proof + contract | **A** |
| **5. Architecture alignment** | Matches L0 system scope + advisory Critic | Aligns only if system finalize owns DiD; not Critic/LLM | **A** |

---

## Decision

### Recommended next research direction

**Choose Direction A — Plan-front (system) ownership** as the **next research / measurement direction**.

**Ownership freeze (decision text):**

1. **Scope / provenance for Agent admissibility is owned at plan-front:** real `AgentToolScope` + production plan construction. Illegal `gated_chunks` injected past that boundary are **not** a valid product-path Critic/isolation failure.
2. **Isolation remains system-owned Runtime L0**, not Critic-owned and not model-owned.
3. **Critic stays advisory**; finalize/publish ownership stays with `_stream_generation_phase` / Control Plane invariants already **PROVEN** in W9 P1.
4. **“Plan-front intelligence” for evolution** means **deterministic plan quality and eligibility**, not default local LLM planner.

**Immediate follow-on research (still no product I unless a later plan opens it):**

- Measurement-adapter / eligibility repair design for C12 under real scope + plan construction.  
- Safe-outcome scorer must check **final citation scope**, not body-diff alone (**EXPERIMENTAL** → implementable in a dedicated measurement window).  
- If oracle cannot map without changing frozen semantics → keep C12 `INVALID_FOR_PRODUCT_PATH_EXECUTION` / P2-R1 BLOCKED with an honest reason (**PROVEN** stop rule already).

### Deferred directions

| Direction | Tier of deferral | Why deferred now |
|---|---|---|
| **B product DiD** (recovery merge re-filter / CriticScopeContext) | **EXPERIMENTAL** residual | Secondary probe only; needs Sol-level narrow review; must not precede A’s eligibility honesty |
| **B-as-semantic Critic depth** (local LLM Critic sync or default ON) | **PROVEN** reject as product next | R1/E1; rollout NO |
| **LLM plan-front** as default thorough path | **PROVEN** reject as default | Contended GPU; E1 planner cost |
| Multimodal “W10 Vertical Slice” | **PROVEN** program order | remaining-plan after W9 Critic gates |
| Async/offline semantic quality protocol | **SPECULATIVE** quality / **EXPERIMENTAL** latency | Optional after A; new protocol ≠ R1 overwrite |
| Queue/Redis/new Critic APIs from charter | **SPECULATIVE** | E2 non-implementation; needs separate plan |
| Wave 2+ payment / public SaaS / HTTPS | **PROVEN** AGENTS ban | Out of scope |

### Required future experiments

Ordered; each needs its own research or measurement window. **None** are authorized as Implement by this document.

| Id | Experiment | Tier of motivation | Falsifies / decides | Must not |
|---|---|---|---|---|
| **E-A1** | Rebuild C12 (and peer) eligibility via real `AgentToolScope` + plan construction; document oracle mapping or `INVALID_FOR_PRODUCT_PATH_EXECUTION` | **PROVEN** program gate | Whether P2-R1 can leave BLOCKED honestly | Silent oracle edits; claim product PASS from old harness |
| **E-A2** | Scorer: final citations ⊆ allowed KB/workspace (and gated set) | **EXPERIMENTAL** → required for A | Ends body-diff false `safe_outcome` | Treat scorer-only as product isolation fix |
| **E-B0** | **Read-only** Sol-level narrow architecture review: is DiD merge re-filter still wanted after E-A1? | **EXPERIMENTAL** residual | Go/no-go for later B I | Patch stream/finalize “while reviewing” |
| **E-B1** (only if E-B0 yes) | Controlled probe: can production path ever admit polluted `gated_chunks` without harness injection? | **SPECULATIVE** reachability | Whether B I is security-necessary | Using harness-only failure as CVE narrative |
| **E-R2** | Docs protocol freeze: single-flight / health cache / TTFT–idle watchdog / non-stream JSON for L2 | **EXPERIMENTAL** E1 | Ops research only | Shipping as product SLO |
| **E-L2** | New long-timeout offline semantic Critic protocol (declare timeout; quality rubric) | **SPECULATIVE** H2 | Whether async L2 adds annotation value | Overwrite R1 reserved JSON; score as interactive PASS |
| **E-H1** | Hang-rate / P0-legal outcome: L0-first vs inline planner+critic, **same** model | **SPECULATIVE** charter H1 | System+small-model thesis | Using eval L1 PASS as metric |

---

## What this decision is not

- **Not** authorization to implement A or B in `backend/app`.  
- **Not** a P2-R1 PASS.  
- **Not** Critic rollout ON.  
- **Not** multimodal W10 coding.  
- **Not** a claim that GLM can or cannot judge claim-status given more time.

---

## One-pager for the next window

| Do next (research / measurement design) | Do not |
|---|---|
| Treat **A** as chosen ownership for scope admissibility | Implement B merge filter or CriticScopeContext now |
| Design E-A1 / E-A2 protocols with explicit DoD | Enable sync local semantic Critic ≤60 s |
| Keep Critic advisory; isolation system-owned | Make Critic the isolation owner |
| Defer B to E-B0 after A eligibility is honest | Start multimodal / final benchmark ahead of W9 gates |
| Keep LLM planner / LLM Critic defaults OFF | Co-load second 7–9B; charter→code leap |

---

## Stop

This file is the **W10 scope ownership decision** (research only).

- **No** implementation plan, runtime change, model call, PR, or merge is authorized here.  
- **Next window** should open a **measurement / eligibility protocol** window (E-A1 design or plan) citing this decision—or an explicit docs-only E-R2 protocol freeze—**one** atomic task only.

**Stop.** Implementation waits for a separate confirmed plan window.
