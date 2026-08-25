# 07 — V1.0 Candidate Cut Line（INTERNAL）

> **INTERNAL CANDIDATE only** · not final Feature Triage · not freeze.  
> Rule: do not promote because “cool”.

Categories: `V1_0_MUST` · `V1_0_SHOULD` · `EXPERIMENT` · `BACKLOG` · `NOT_NOW`

---

## V1_0_MUST（candidate）

| Capability | Why |
|------------|-----|
| Document ingestion | Core product loop |
| Parsing / chunking | Core |
| Embedding（BGE default） | Core |
| Vector + FTS + Hybrid RRF | Core retrieval |
| Citation / provenance | P0 AGENTS底线 |
| Refusal / degraded semantics | P0 / honesty |
| Legacy Agent（Thorough/LLMPlanner） | Default agent path already shipped |
| Tool execution（non-dynamic baseline） | Agent usefulness |
| Failure recovery / degradation ladder | Enterprise resilience |
| Permissions / governance / audit | Enterprise P0 |
| Retrieval eval + Hit@3 CI gate | Quality gate |
| CI（blocking surface） | Release hygiene |
| Install/deploy path（honest docs） | Release hygiene |
| Documentation claim accuracy | Release hygiene |
| Product UI（KB + cited chat + admin） | Deliverable surface |

## V1_0_SHOULD（candidate）

| Capability | Why |
|------------|-----|
| Agent Golden suite as documented regression（even if not yet CI-blocking） | Behavior safety net |
| ADV / known-limitations as frozen honesty artifacts | Prevent overclaim |
| W10 Formal claim freeze retained in docs | Scope discipline |
| Memory **infrastructure**（store/window）with **honest** claims | Already default ON |
| Observability：audit + `/metrics` + health | Ops |
| Canonical demo path + BROWSER acceptance pointer repair | Release storytelling |
| Composite query split（already on via planner） | Stable RAG aid |
| Clause route（already on） | Stable RAG aid |

## EXPERIMENT（keep off by default）

| Capability | Why |
|------------|-----|
| L3 Observation Agent | Implemented；rollout NO |
| L3 dynamic tools / evidence gate / critic retrieval / trajectory | Flag-off |
| Critic（`rag_critic_*`） | Flag-off；W9 not productized |
| Rerank / query rewrite / HyDE | Measured risk / off |
| Graph recall | Rolled back |
| L4 FactGoal decomposer / matcher / stop / reflection | Flag-off；incomplete loop |
| LM Studio / local-model eval harness | Measurement only |
| Memory relevance labels / exposure productization | Labels off；C2 NO_GO |

## BACKLOG（post cut-line / research）

| Item | Note |
|------|------|
| Fact-level evidence coverage loop | README next-stage |
| Critic protocol repair / productization | W9 residual |
| ADV ANS/CON remediation | DEFER |
| Tool selection remediation on local models | CLOSED_FOR_V1_0 remediation STOP |
| Memory utilization / causal benefit | C2 NO_GO |
| Agent Golden → CI gate decision | Process，not new capability |
| Bare-metal install polish | Docs |

## NOT_NOW（must not enter v1.0 cut）

| Item | Note |
|------|------|
| LLM-Wiki | Explicit future |
| GraphRAG productization | Default off · rolled back |
| Evolver | Not in product claims |
| Persistent Memory v2 / “memory intelligence” | Utilization unproven |
| Multi-Agent | Out of scope |
| MCP expansion | Post-V1.0 backlog |
| Multimodal agent evidence | STUB |
| Local Model as default chat backend | Roadmap only |
| Research Benchmark / new Formal campaigns | W10 sealed |
| E-B45 / W11 research capability | Forbidden by W10 closure |
| New scorer / protocol change | Forbidden this phase |

---

## Candidate “v1.0 product sentence”（internal）

> Suoyin v1.0 is an **evaluation-gated Hybrid RAG** system with **mandatory citations/refusal**, **enterprise governance**, and a **default Legacy Agent path**; Observation-driven L3/Critic/L4/local-multimodal remain **experimental and off**.

Anything stronger requires Feature Triage evidence upgrades — not this inventory.
