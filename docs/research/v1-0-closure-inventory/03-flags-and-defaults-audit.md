# 03 — Flags and Defaults Audit

> Source: `backend/app/core/config.py`（Settings defaults）· README Experimental section  
> **本窗未修改任何 flag。**

## Goal

明确 **v1.0 默认行为** 是什么：Stable Hybrid RAG + Legacy Agent + citations/refusal + governance + memory master ON；实验面 OFF。

---

## Inventory（primary flags）

| FLAG | DEFAULT | OWNER（code area） | CAPABILITY | SAFE_TO_ENABLE_BY_DEFAULT? | DOCUMENTED? | TESTED? |
|------|---------|--------------------|------------|:---:|:---:|:---:|
| `retrieval_fusion_mode` | `rrf` | rag/retrieval | Hybrid | YES（current） | YES | YES |
| `rrf_vector_weight` / `rrf_fts_weight` | `1.0` / `1.5` | rag/rrf | Hybrid | YES（gated） | YES | YES |
| `rerank_enabled` | `False` | rag/rerank | Rerank | **NO**（can hurt Hit@3） | YES | YES |
| `rerank_policy` | `off` | rag/planner | Rerank | NO | YES | YES |
| `query_rewrite_enabled` | `False` | rag/multi_query | Rewrite | NO（until re-measured） | YES | YES |
| `query_rewrite_policy` | `off` | same | Rewrite | NO | YES | YES |
| `hyde_enabled` | `False` | rag/hyde | HyDE | NO | YES | YES |
| `graph_recall_enabled` | `False` | rag | Graph recall | **NO**（quality rollback） | YES | LIMITED |
| `clause_route_enabled` | `True` | rag/planner | Clause route | YES（current） | LIMITED | YES |
| `self_verify_enabled` | `False` | rag | Post-gen verify | NO（extra LLM cost） | LIMITED | LIMITED |
| `rag_critic_enabled` | `False` | rag/critic | Critic | **NO** | YES | YES |
| `rag_critic_mode` | `rules` | rag/critic | Critic | N/A while master off | YES | YES |
| `rag_critic_on_fail` | `fail_closed` | rag/critic | Critic | Prefer fail_closed if ever on | YES | YES |
| `agent_llm_planner_enabled` | `True` | agent/planners | Legacy Agent | YES（current default path） | YES | YES |
| `agent_l3_next_action_enabled` | `False` | agent | L3 | **NO** | YES | YES |
| `agent_l3_dynamic_tools_enabled` | `False` | agent | ToolResolver deps | **NO** | YES | YES |
| `agent_l3_evidence_state_enabled` | `False` | agent | Evidence gate | **NO** | YES | YES |
| `agent_l3_trajectory_trace_enabled` | `False` | agent | Trace | YES as observability（low risk） | YES | YES |
| `agent_l3_critic_retrieval_enabled` | `False` | agent | Critic retrieval | **NO** | YES | YES |
| `agent_l4_fact_decomposition_enabled` | `False` | agent | FactGoal decomp | **NO** | PARTIAL | YES |
| `agent_l4_evidence_matcher_enabled` | `False` | agent | Matcher | **NO** | PARTIAL | YES |
| `agent_l4_contradiction_enabled` | `False` | agent | Contradiction | **NO** | PARTIAL | YES |
| `agent_l4_stop_policy_enabled` | `False` | agent | Stop policy | **NO** | PARTIAL | YES |
| `agent_l4_reflection_recovery_enabled` | `False` | agent | Recovery | **NO** | PARTIAL | YES |
| `agent_l4_local_model_profile_enabled` | `False` | agent | Local model | **NO** | YES（roadmap） | LIMITED |
| `agent_l4_multimodal_evidence_enabled` | `False` | agent | Multimodal | **NO** | YES | STUB assert |
| `agent_l4_tool_*_hint / contrastive` | `False` | agent | Tool hints | **NO** | LIMITED | YES |
| `agent_evidence_sufficiency_obs` | `False` | agent | Obs only | YES（log-only） | LIMITED | LIMITED |
| `agent_evidence_strategy_enabled` | `False` | agent | Strategy | **NO** | LIMITED | YES |
| `agent_decompose_drift_recovery` | `False` | agent | Drift | **NO** | LIMITED | YES |
| `agent_memory_enabled` | **`True`** | agent/memory | Memory | **CONDITIONAL** — infra OK；do not claim utilization productized | YES | YES |
| `agent_memory_exposure_trace_enabled` | `False` | agent | Trace | YES（obs） | YES | YES |
| `agent_memory_relevance_label_enabled` | `False` | agent | Labels | **NO**（not rollout） | YES | YES |
| `external_tools_enabled` | `False` | agent | External tools | **NO** | LIMITED | LIMITED |
| `degradation_enabled` | `True` | core | Degrade | YES | YES | YES |
| `citation_redact_enabled` | `True` | rag | Citation | YES | YES | YES |
| `citation_density_check_enabled` | `True` | rag | Citation | YES | YES | YES |
| `ocr_enabled` | `True` | ingestion | OCR | YES（with page cap） | YES | YES |
| `pdf_layout_denoise_enabled` | `True` | ingestion | Parse | YES | LIMITED | YES |
| `table_chunk_split_enabled` | `True` | ingestion | Chunk | YES | YES | YES |

---

## Default product behavior（v1.0 candidate narrative）

```text
ON:
  Hybrid RRF retrieval
  Citations + refuse + degradation
  Legacy ThoroughRead / LLMPlanner Agent
  Memory infrastructure (master switch)
  RBAC / audit / rate limit / workspace isolation
  OCR + structure chunking + BGE embed

OFF:
  L3 NextAction loop
  L3 dynamic dependent tools
  L3 evidence-state gate / critic retrieval / trajectory trace
  Critic (rag_critic_*)
  Rerank / query rewrite / HyDE / graph recall
  All agent_l4_* including local-model + multimodal evidence
  Memory relevance labels / exposure trace
  External tools
```

---

## Safety assessment

### Overall: experimental runtime flags

**SAFE** — high-risk experimental surfaces default **OFF**.

### Special case: Memory master ON

| Question | Answer |
|----------|--------|
| Security isolation risk from flag alone? | No evidence of cross-KB leak from memory flag itself（governance still applies） |
| Claim risk? | **YES** — easy to overclaim “memory capability” while C1 utilization = 0/10 · C2 NO_GO |
| SAFE_TO_ENABLE_BY_DEFAULT? | **CONDITIONAL YES** for working/long-term store；**NO** for “memory intelligence / causal benefit” marketing |

### Special case: Critic / L3 / L4

Raising any of these to default without dual-track regression = **NOT SAFE**.

---

## Verdict

```text
DEFAULT_FLAGS_SAFE_FOR_V1_0_EXPERIMENT_SURFACE = YES
MEMORY_MASTER_ON_CLAIM_CAUTION               = REQUIRED
NO_FLAG_CHANGES_IN_THIS_WINDOW               = YES
```
