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

## V1.0 CI Contract（C5 · canonical）

> Authoritative answer to: *If a PR breaks a V1.0 release-critical behavior, will CI detect and block it?*  
> Inventory detail: [`../research/v1-0-closure-inventory/04-ci-and-test-surface.md`](../research/v1-0-closure-inventory/04-ci-and-test-surface.md).

### Tier model

| Tier | Role | Paid LLM? | Blocks PR? |
|------|------|-----------|:----------:|
| **1 — PR BLOCKING** | Fast / deterministic / local-BGE or mock | **NO** | **YES** |
| **2 — RELEASE CHECK** | Slower reproducible (CRAG nightly, full benchmark dispatch) | optional | NO |
| **3 — RESEARCH / MANUAL** | Stochastic / Formal / provider-dependent / historical | often | NO |

### What blocks PR（Tier 1）

Workflow: [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)

| Surface | Command / job | Notes |
|---------|---------------|-------|
| Import / collect | `pytest --collect-only` | 0 collection errors |
| Lint | `ruff check` · frontend `npm ci && npm run build && npm test` | `lint` + `test` jobs |
| Migrations | `alembic upgrade/downgrade` · `alembic check` | empty autogenerate diff |
| Config wiring | `tests/test_config_wiring.py` | dead config / env bypass |
| Safe defaults | `tests/test_v1_0_safe_defaults.py` | L3/L4/Critic/rerank/HyDE/rewrite/graph **OFF** |
| Core API A-layer | listed pytest files in `test` job | auth / citations / upload / search / … |
| Ingestion + **C4 loop isolation** | ingest golden + `test_c4_ingestion_loop_isolation.py` | Celery thread-pool event-loop bug |
| Retrieval Hit@3 **11/11** | `tests/test_retrieval_golden.py`（GQ-1…12 minus GQ-9） | **mock** embeddings · PR hard gate |
| Retrieval baseline | `rag-golden` / `rag-enterprise` / `rag-advanced` → `benchmark-gate` | **local BGE** · `--skip-entity-extract` · vs `backend/tests/benchmark/baseline.json` |

### What is release-only / manual（Tier 2–3）

| Surface | Classification | Why |
|---------|----------------|-----|
| Agent Golden（168） | **RELEASE_ONLY / MANUAL** | suite exists; not PR cost/noise budget |
| ADV adversarial panels | **RESEARCH_ARCHIVE** | frozen CHARACTERIZED evidence; rollout NO |
| W9 Critic | **RESEARCH_ARCHIVE** | Formal/research; default OFF; not PR gate |
| W10 Formal T1/T2/T3 | **RESEARCH_ARCHIVE** | sealed historical Formal scope; ≠ Agent/RAG accuracy |
| Canonical demo (`scripts/demo.ps1`) | **MANUAL_ONLY** | live DeepSeek + running stack; not PR CI |
| CRAG nightly / full | **RELEASE_ONLY**（informational） | `benchmark.yml` schedule/dispatch |
| Deprecated `regression.yml` | **MANUAL_ONLY** | dispatch only; soft; not PR |

```text
V1_0_CI_COVERAGE           = SUFFICIENT_FOR_STABLE_RAG_V1_0
PR_GATE_DETERMINISTIC      = YES   # no paid LLM required for PR
PAID_PROVIDER_REQUIRED_FOR_PR_CI = NO
```

**Determinism note:** PR CI is **paid-LLM independent** and uses deterministic / local-model retrieval evaluation. It is **not** claimed completely offline — model artifact availability may require the configured Hugging Face mirror/cache (`HF_ENDPOINT`, BGE download). Do not weaken Hit@3 / baseline gates merely to eliminate that dependency.

---

## Next closure windows（human-triggered only）

Suggested sequence after C1–C5 (do **not** auto-start):

1. ~~V1.0-C2 — README / claim repair~~ **DONE**  
2. ~~Install path coherence（C3）~~ **DONE**  
3. ~~Canonical demo（C4）~~ **DONE**  
4. ~~CI scope honesty（C5）~~ **DONE**（closure commit）  
5. Safe-defaults / remaining RELEASE BLOCKING polish（C6 candidate）· **not** auto-start  

No C1.1 / C1.2 / E-B45 / W11 preparation chain.
