# V1.0 Release Cut Line

> Frozen release surface for Suoyin v1.0.  
> Inventory input: [`../research/v1-0-closure-inventory/`](../research/v1-0-closure-inventory/) (C0).  
> Admission rules: [`feature-admission-constitution.md`](feature-admission-constitution.md).

```text
V1_0_CUT_LINE_FROZEN              = YES
NEW_CAPABILITY_REQUIRED_FOR_V1_0  = NO
FEATURE_CONSTITUTION_FROZEN       = YES   # see constitution
COOL_IDEA_IS_NOT_RELEASE_BLOCKER  = YES
```

**Meaning of freeze:** new capabilities do not reopen v1.0. Closure work is honesty, install, demo, CI scope, defaults, docs, and claim discipline — not research expansion.

---

## Scope-creep decision rule

```text
NEW_IDEA
   │
   ▼
Is it required to satisfy an already-frozen v1.0 Definition of Done?
   │
   ├── YES → closure candidate
   │         (must cite the exact DoD / RELEASE BLOCKING item)
   │
   └── NO  → BACKLOG
             (may become FUTURE_EXPERIMENT later;
              must not block the v1.0 tag)
```

```text
COOL_IDEA_IS_NOT_RELEASE_BLOCKER = YES
```

A cool idea, new paper, new model, or new framework is **not** a release blocker.

---

## V1.0 RELEASE BLOCKING

Only these categories may block the v1.0 tag:

| # | Category | Notes |
|---|----------|--------|
| 1 | README claim truthfulness | Public claims must match C0 / W9 / W10 discipline |
| 2 | Coherent install path | Compose-first path usable; known limits documented |
| 3 | Canonical demo | Reproducible demo path (not wishlist features) |
| 4 | Core CI green / CI scope explicit | Blocking jobs green; non-blocking suites not overclaimed |
| 5 | Safe feature defaults | Experimental surfaces stay off unless validated |
| 6 | Understandable architecture documentation | Reader can locate stable vs experimental paths |
| 7 | Accurate benchmark summary | Scoped claims only (e.g. W10 T1 ≠ Agent accuracy) |
| 8 | Known limitations explicitly documented | Including Memory / ADV / TOOL residual honesty |
| 9 | W9 / W10 claim discipline | Formal scopes remain scoped; no fake PASS |
| 10 | Release / package / tag integrity | Tag contents match stated release surface |

Anything outside this list is polish or backlog unless it is shown to break one of the ten.

---

## V1.0 SHOULD（closure polish）

Allowed as closure polish — **not** new research features:

- Agent Golden usage documentation (suite exists; CI policy explicit)
- ADV / W9 / W10 evidence summary retained as honesty artifacts
- Memory **infrastructure** honest positioning (store/window ≠ intelligence proven)
- Audit / metrics documentation
- Developer ergonomics that do **not** add capability (scripts, pointers, claim repair)

These may be adjusted to repo facts. They must not silently upgrade into new research capability work (E-B45, W11, Local Model productization, etc.).

---

## NOT V1.0

Frozen out of the v1.0 tag. May live as BACKLOG / FUTURE_EXPERIMENT / SEPARATE_PROJECT_CANDIDATE. **Must not block v1.0.**

| Item | Marker |
|------|--------|
| LLM-Wiki | BACKLOG / FUTURE_EXPERIMENT |
| GraphRAG productization | BACKLOG / FUTURE_EXPERIMENT |
| Persistent Memory v2 intelligence | BACKLOG / FUTURE_EXPERIMENT |
| Multi-Agent | BACKLOG / FUTURE_EXPERIMENT |
| MCP expansion | BACKLOG / FUTURE_EXPERIMENT |
| Multimodal Agent | BACKLOG / FUTURE_EXPERIMENT |
| Evolver / self-evolving Agent | FUTURE_EXPERIMENT（Constitution Art. 8 only） |
| Economic Agent | SEPARATE_PROJECT_CANDIDATE or FUTURE_EXPERIMENT |
| Research Benchmark Track | BACKLOG / FUTURE_EXPERIMENT |
| New Local Model capability research | BACKLOG / FUTURE_EXPERIMENT |
| New model leaderboard | BACKLOG |
| New fine-tuning pipeline | BACKLOG |
| Distributed infrastructure | BACKLOG unless required by an existing RELEASE BLOCKING item |
| E-B45 / W11 research capability expansion | FORBIDDEN for v1.0 reopen |

---

## Risky-feature governance mapping（compact）

Source: C0 inventory + flags audit. **Not** a re-inventory of all 34 capabilities.

| Feature | CURRENT_STATUS | DEFAULT_STATE | EVIDENCE_LEVEL | V1_0_POSITION |
|---------|----------------|---------------|----------------|---------------|
| Legacy Agent（ThoroughRead / LLMPlanner） | IMPLEMENTED | ON（stable delivery path） | Product path + Agent Golden（not all PR-CI） | V1_0_MUST — keep as default Agent |
| L3 Observation Agent | IMPLEMENTED（experimental by design） | OFF | Scoped local / ADV panels; not default-proven | EXPERIMENT — default off |
| Critic（`rag_critic_*` / L3 critic retrieval） | IMPLEMENTED | OFF | W9 research; rollout NO | EXPERIMENT — default off |
| Memory | IMPLEMENTED（infra） | Master ON; labels/exposure OFF | L3 exposure measured; L4/L5 0/10; C2 NO_GO | SHOULD infra · **not** intelligence claim |
| Reranker | IMPLEMENTED | OFF | Ablation; full rerank can hurt FAQ Hit@3 | EXPERIMENT — do not infer default value |
| HyDE | PARTIAL / available | OFF | Ablation scripts | EXPERIMENT — do not infer default value |
| Query Rewrite | PARTIAL / available | OFF | Available; not default-proven | EXPERIMENT — do not infer default value |
| Graph（graph recall） | Code present; rolled back | OFF | Quality rollback | NOT_V1_0 productization |
| L4 structures（FactGoal / matcher / stop / reflection / …） | PARTIAL | All `agent_l4_*` OFF | Research structures; incomplete loop | EXPERIMENT / bounded claim only |
| Local Model integration | Product STUB · eval harness PARTIAL | OFF | Eval-only LM Studio path | NOT_V1_0 product capability |

---

## Explicit non-claims（carry forward）

```text
W10 Formal T1 100%  ≠  Agent accuracy 100%
W10 Formal T1 100%  ≠  RAG accuracy 100%
W10 Formal T1 100%  ≠  answer quality 100%
Memory master ON   ≠  memory intelligence validated
IMPLEMENTED        ≠  VALIDATED / DEFAULT
```

---

## Next closure windows（human-triggered only）

Suggested sequence after C1/C2 freeze (do **not** auto-start):

1. ~~V1.0-C2 — README / claim repair~~ **DONE**（with C1/C2 closure commit）  
2. Install path coherence（C3 candidate）  
3. Canonical demo  
4. CI scope honesty / remaining RELEASE BLOCKING items  

No C1.1 / C1.2 / E-B45 / W11 preparation chain.
