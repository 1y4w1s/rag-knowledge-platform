# 06 — README Claim Audit

> **禁止本窗重写 README。** 只标记 claim 状态。  
> Source: root `README.md` @ inventory time（W10 closed；HEAD `f06e8d92…`）

Status ∈ {SUPPORTED, OVERSTATED, STALE, UNDERSTATED, UNVERIFIED}

---

## Tagline / positioning

| Claim | Mark | Notes |
|-------|------|-------|
| “evaluation-driven, evidence-grounded Agentic RAG platform” | **SUPPORTED** with caution | Evaluation-driven = true for retrieval；Agentic = true as capability surface；default path is Stable RAG + Legacy Agent, L3 experimental |
| “Don't make the model do what the system can do better.” | **SUPPORTED** | Design philosophy；not a measurable KPI |
| “不是向量库接 LLM 的 RAG Demo” | **SUPPORTED** | Ingestion + hybrid + citations + governance + agent + eval present |

---

## Core Capabilities table

| Claim | Mark | Notes |
|-------|------|-------|
| Hybrid FTS + pgvector + RRF `w_v=1.0 / w_f=1.5` Stable | **SUPPORTED** | Defaults match config |
| 中英嵌入双列 Stable | **SUPPORTED** | Route + dims；EN gap tooling exists |
| Conditional rerank / rewrite / HyDE / Graph Experimental default off | **SUPPORTED** | Flags False；graph rolled back |
| Citation + confidence normal/low/refuse Stable | **SUPPORTED** | P0 path |
| ThoroughRead / LLM Planner + tools + recovery + write approval Stable | **SUPPORTED** | Default Agent path |
| Observation-driven NextActionPlanner（L3） Experimental off | **SUPPORTED** | |
| ToolResolver Experimental off | **SUPPORTED** | |
| EvidenceState + stop/retrieve gate Experimental（结构已有） | **SUPPORTED** | Gate flag off；fact-level incomplete correctly caveated nearby |
| Trajectory evaluation Experimental | **SUPPORTED** | Suite exists；not CI gate |
| Critic → directed re-retrieval Experimental off | **SUPPORTED** | |
| RBAC / Approval / Audit / budget / breaker / rate limit Stable | **SUPPORTED** | |
| Memory Working + long-term + importance / summary **Stable** | **OVERSTATED** | Infra IMPLEMENTED + default ON；**utilization/causal benefit NOT proven** · C2 NO_GO — “Stable” reads stronger than evidence |
| Local-first small-model amplification Roadmap | **SUPPORTED** | Explicitly roadmap |

---

## Architecture / L3 narrative

| Claim | Mark | Notes |
|-------|------|-------|
| L3 Observation loop description | **SUPPORTED** | Matches code when flags on |
| Experimental flags list default False | **SUPPORTED** | Matches config |
| EvidenceState fact-level not closed | **SUPPORTED** | Honest |

---

## Evaluation numbers

| Claim | Mark | Notes |
|-------|------|-------|
| Retrieval Golden Hit@3 **11/11** CI gate | **SUPPORTED** | AGENTS + CI |
| Golden full 109 / 135 passed note | **UNVERIFIED** this window | Not re-run；historically documented |
| Enterprise 60% mock / 71.1% real-emb 2026-08-09 | **SUPPORTED** as dated snapshot | Must keep date；not universal |
| Advanced 14/14 | **SUPPORTED** as CI baseline claim | |
| Latency P95 numbers 2026-07-22 | **STALE/UNVERIFIED** | Dated；not remeasured here |
| Agent Golden **168** | **SUPPORTED**（suite size） | Easy OVERSTATED if implied CI-gated |
| Local LLM matrix TBD | **SUPPORTED** | Honest roadmap |

---

## “What Suoyin Is Not” / philosophy

| Claim | Mark | Notes |
|-------|------|-------|
| Not large-scale production-validated commercial SaaS | **SUPPORTED** | Honest |
| Not Graph/MCP noun demo | **SUPPORTED** | graph default off |
| Continuously evaluated Agentic RAG… | **SUPPORTED** with scope | Continuous for retrieval CI；Agent/ADV not continuous PR gates |

---

## Roadmap checkboxes

| Claim | Mark | Notes |
|-------|------|-------|
| L3 items mostly checked | **SUPPORTED** | Code present；rollout checkbox correctly open |
| L4 FactGoal / fact coverage unchecked | **UNDERSTATED** / **STALE** | Structures + flag-gated modules **exist**；unchecked implies absent — better “partial / experimental off” |
| Local LLM benchmark unchecked | **SUPPORTED** | Still roadmap |

---

## Stable RAG design table

| Claim | Mark | Notes |
|-------|------|-------|
| RRF weights / rerank off / refuse tiers / graph off | **SUPPORTED** | |
| “BM25” elsewhere vs FTS | If README says BM25 loosely → **OVERSTATED** naming；table correctly says FTS | Prefer FTS wording |

---

## Quick start / deploy

| Claim | Mark | Notes |
|-------|------|-------|
| Compose prod up path | **SUPPORTED** | Files exist |
| `/health` database ok | **SUPPORTED** as intended contract | Not live-probed this window → operational UNVERIFIED |
| Experimental flags default off | **SUPPORTED** | Memory master ON is separate（documented elsewhere） |

---

## V1.0 status block（2026-08-23）

| Claim | Mark | Notes |
|-------|------|-------|
| Runtime rollout：**NO** | **SUPPORTED** | Matches known-limitations |
| T2/TOOL/MEMORY CLOSED_FOR_V1_0 · ADV FROZEN 2/4 · 10/20 | **SUPPORTED** | |
| 下一主线：W9 Critic → **W10 Multimodal** → Final Benchmark → RC | **STALE** | W10 Formal window **CLOSED**（citation Formal，非 Multimodal delivery）；Multimodal agent still STUB；next phase is **V1_0_CLOSURE** |
| master `dffcd52` pin | **STALE** | HEAD moved（W10 closure `f06e8d92…`） |

---

## High-priority corrections needed（for later windows）

1. **STALE** V1.0 “下一主线 / Multimodal / SHA pin”  
2. **OVERSTATED** Memory row as unqualified “Stable” product intelligence  
3. **UNDERSTATED/STALE** L4 FactGoal checklist vs existing PARTIAL code  
4. Guard Agent Golden / W10 100% from being read as universal quality  

**No README rewrite in this window.**
