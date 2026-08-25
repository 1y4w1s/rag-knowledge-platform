# 01 — Current Capability Inventory

> Cross-validated against **code + tests + current docs**. README alone ≠ IMPLEMENTED.  
> Inventory HEAD: `f06e8d92…` · Config SSOT: `backend/app/core/config.py`

**IMPLEMENTATION_STATUS** ∈ {IMPLEMENTED, PARTIAL, EXPERIMENTAL, STUB, ABSENT, UNKNOWN}

---

## Summary counts

| Status | Count | IDs |
|--------|------:|-----|
| IMPLEMENTED | 22 | 1–7, 9–14, 16–22, 24, 28, 30–31 |
| PARTIAL | 8 | 8, 15, 23, 26*, 29, 32–34 |
| EXPERIMENTAL | 2 | 10 (default-off path), 25* eval framing |
| STUB | 2 | 25 product local-model · 27 agent multimodal |
| ABSENT | 0 | — |

\* Local-model / LM Studio: product = STUB；eval harness = IMPLEMENTED（见单项）。本表按「产品能力」归类时 local-model=STUB、LM Studio=PARTIAL（eval-only）。

**V1_0_RELEVANCE** 初判仅供 07 cut-line 输入；非最终 triage。

---

## 1. Document ingestion

| Field | Value |
|-------|--------|
| CAPABILITY | Document ingestion（upload → queue → parse/chunk/embed） |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON |
| ENTRY_POINT | `api/documents.py` → `services/documents/upload.py` → `ingestion/enqueue.py` → `process_document_ingestion` |
| EVIDENCE | Celery pipeline · OCR/zip guards · stale scan · batch re-ingest |
| TEST_COVERAGE | `test_upload_*` · `test_ingestion_golden.py` · format fixtures · zip-bomb · stale timeout |
| BENCHMARK_EVIDENCE | Ingest path embedded in retrieval golden fixtures |
| KNOWN_FAILURE | Stale queued/processing；EN embed gap re-embed；OCR page cap |
| MAINTENANCE_RISK | MEDIUM（多格式边界） |
| V1_0_RELEVANCE | V1_0_MUST |

## 2. Parsing / chunking

| Field | Value |
|-------|--------|
| CAPABILITY | Multi-format parse + structure chunk |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON（`chunk_max_chars=1200` · PDF denoise ON · table split ON） |
| ENTRY_POINT | `ingestion/parser.py` · `chunker.py` · `parser_pdf.py` · `ocr.py` |
| EVIDENCE | Structure/`heading_path` chunking in code |
| TEST_COVERAGE | `test_chunker.py` · PDF/OCR/table/xlsx/pptx · `test_ac8_docx.py` |
| BENCHMARK_EVIDENCE | Via golden ingest |
| KNOWN_FAILURE | Scanned PDF OCR；Office edge cases |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST |

## 3. Embedding

| Field | Value |
|-------|--------|
| CAPABILITY | ZH/EN embedding + route |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON · provider=`bge` · model=`bge-small-zh-v1.5` · dim=512 |
| ENTRY_POINT | `ingestion/embedder.py` · `rag/embed_route.py` |
| EVIDENCE | Local ONNX BGE；Tongyi HTTP fallback；cache |
| TEST_COVERAGE | `test_embedder_*` · `test_embed_route_b4.py` · re-embed suites |
| BENCHMARK_EVIDENCE | CI `rag-*` jobs use real emb；pytest golden often mock |
| KNOWN_FAILURE | EN gap chunks；model lock（勿随意换） |
| MAINTENANCE_RISK | HIGH if model swapped without migration/re-embed |
| V1_0_RELEVANCE | V1_0_MUST |

## 4. Vector retrieval

| Field | Value |
|-------|--------|
| CAPABILITY | pgvector recall |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON（`vector_recall_k=30`） |
| ENTRY_POINT | `rag/vector_recall.py` ← `retrieval.py` |
| EVIDENCE | Hybrid + `vector_only` fusion mode |
| TEST_COVERAGE | `test_retrieval_*` · security · workspace |
| BENCHMARK_EVIDENCE | Hit@3 golden · ablation |
| KNOWN_FAILURE | Embed-down → FTS-only degradation |
| MAINTENANCE_RISK | LOW–MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST |

## 5. BM25 / lexical retrieval

| Field | Value |
|-------|--------|
| CAPABILITY | Lexical / FTS recall |
| IMPLEMENTATION_STATUS | **IMPLEMENTED**（**PG `tsvector`/`ts_rank_cd`，非 Okapi BM25**） |
| DEFAULT_STATE | ON（`fts_recall_k=30` · `rrf_fts_weight=1.5`） |
| ENTRY_POINT | `rag/fts_recall.py` · CJK `rag/cjk.py` |
| EVIDENCE | Hybrid path；doc search API |
| TEST_COVERAGE | hybrid · multi_query · search_content · golden |
| BENCHMARK_EVIDENCE | Hit@3 contribution |
| KNOWN_FAILURE | `TS_CONFIG=simple`；CJK segmentation sensitivity |
| MAINTENANCE_RISK | MEDIUM（命名易误导「BM25」） |
| V1_0_RELEVANCE | V1_0_MUST（作为 FTS/hybrid 腿） |

## 6. Hybrid retrieval

| Field | Value |
|-------|--------|
| CAPABILITY | RRF hybrid（vector + FTS） |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON · `retrieval_fusion_mode=rrf` · `w_v=1.0` / `w_f=1.5` |
| ENTRY_POINT | `rag/rrf.py` · `retrieval.py` · planner strategy |
| EVIDENCE | Production default path |
| TEST_COVERAGE | `test_retrieval_hybrid.py` · `test_rrf_weights.py` · golden 11/11 gate |
| BENCHMARK_EVIDENCE | **CI Hit@3 gate** · enterprise/advanced CI jobs |
| KNOWN_FAILURE | Weight sweeps historically hurt Hit@3 if mis-tuned |
| MAINTENANCE_RISK | HIGH on weight/policy change（门禁） |
| V1_0_RELEVANCE | V1_0_MUST |

## 7. Reranking

| Field | Value |
|-------|--------|
| CAPABILITY | Cross-encoder / BGE rerank |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | **OFF** · `rerank_enabled=False` · `rerank_policy=off` |
| ENTRY_POINT | `rag/rerank.py` · planner `should_run_rerank` |
| EVIDENCE | Code + conditional policy |
| TEST_COVERAGE | `test_rerank.py` · `test_conditional_rerank.py` |
| BENCHMARK_EVIDENCE | Ablation；notes: full rerank can **hurt** FAQ Hit@3 |
| KNOWN_FAILURE | Fail → fall back to RRF order |
| MAINTENANCE_RISK | MEDIUM if default raised |
| V1_0_RELEVANCE | EXPERIMENT / V1_0_SHOULD（keep off） |

## 8. Query rewrite / decomposition

| Field | Value |
|-------|--------|
| CAPABILITY | Multi-query rewrite · HyDE · composite split · L4 fact decompose |
| IMPLEMENTATION_STATUS | **PARTIAL** |
| DEFAULT_STATE | rewrite/HyDE **OFF**；composite strategy ON；L4 decomp **OFF**；RAG `_decompose_if_needed` gated by `rerank_enabled` |
| ENTRY_POINT | `multi_query.py` · `hyde.py` · `generation.expand_queries` · `agent/decomposer.py` |
| EVIDENCE | Modules + flags；not production-default |
| TEST_COVERAGE | `test_multi_query.py` · `test_hyde.py` · `test_composite_query_split.py` · L4 decomposer tests |
| BENCHMARK_EVIDENCE | HyDE ablation scripts；progress: do not raise defaults |
| KNOWN_FAILURE | Degrade to static variants；L4 fact loop incomplete |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | EXPERIMENT（rewrite/HyDE）· composite = SHOULD |

## 9. Legacy Agent

| Field | Value |
|-------|--------|
| CAPABILITY | ThoroughRead / LLMPlanner sequential tool chain |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON production path · `agent_llm_planner_enabled=True` |
| ENTRY_POINT | `agent/planners.py` · `runtime.py` · `dispatch.py` · `stream.py` |
| EVIDENCE | Default factory when L3 off |
| TEST_COVERAGE | `test_agent_thorough_*` · `test_agent_a1_planner.py` · `test_agent_runtime.py` · `test_agent_golden.py` |
| BENCHMARK_EVIDENCE | Agent Golden 168（**not** PR CI job） |
| KNOWN_FAILURE | LLM plan parse fail → Thorough fallback |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST |

## 10. L3 Observation-driven Agent

| Field | Value |
|-------|--------|
| CAPABILITY | Observation loop · `NextActionPlanner` |
| IMPLEMENTATION_STATUS | **IMPLEMENTED**（experimental by design） |
| DEFAULT_STATE | **OFF** · all `agent_l3_*` False |
| ENTRY_POINT | `NextActionPlanner` · `_run_l3_next_action_loop` |
| EVIDENCE | Merged code + extensive unit tests；README Experimental |
| TEST_COVERAGE | `test_agent_l3_*.py` |
| BENCHMARK_EVIDENCE | `eval/local_agent_trajectory` · ADV/MEMORY local panels（scoped） |
| KNOWN_FAILURE | ADV ANS/CON failures；not default-enabled |
| MAINTENANCE_RISK | HIGH if default raised without dual-track regression |
| V1_0_RELEVANCE | EXPERIMENT |

## 11. Planner

| Field | Value |
|-------|--------|
| CAPABILITY | ThoroughRead · LLMPlanner · NextActionPlanner |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | Legacy planners ON；NextActionPlanner requires L3 flag |
| ENTRY_POINT | `LLMPlannerFactory` / `create_tool_planner` |
| EVIDENCE | Dual path in factory |
| TEST_COVERAGE | thorough + L3 planner + L4 hint tests |
| BENCHMARK_EVIDENCE | Trajectory / tool eval harnesses |
| KNOWN_FAILURE | L3 planner quality scoped |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | Legacy = MUST · L3 planner = EXPERIMENT |

## 12. Tool resolver / tool execution

| Field | Value |
|-------|--------|
| CAPABILITY | Tool registry · guard · resolver · execute |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | Tools execute on Agent path；`agent_l3_dynamic_tools_enabled=False`（dependents locked）· `external_tools_enabled=False` |
| ENTRY_POINT | `tool_resolver.py` · `tools/registry.py` · `runtime._execute_step` |
| EVIDENCE | 11-tool family in product Agent |
| TEST_COVERAGE | `test_agent_tools.py` · L3 tools · tool_guard · S3A/P* tests |
| BENCHMARK_EVIDENCE | `eval/tool_capability` · selection **NO_MEASURABLE_GAIN** on frozen GQ-131 |
| KNOWN_FAILURE | Local model tool selection boundary |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST（execution）· dynamic unlock = EXPERIMENT |

## 13. EvidenceState

| Field | Value |
|-------|--------|
| CAPABILITY | Evidence aggregation state in L3 |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | Structure always in L3 state；**gate** only if `agent_l3_evidence_state_enabled=True`（default False） |
| ENTRY_POINT | `agent/types.py` · `state.py` · `update_evidence_state` |
| EVIDENCE | Fields: facts/ids/contradictions/sufficient/confidence/evidence_items |
| TEST_COVERAGE | `test_agent_l3_state.py` · `test_agent_l3_evidence.py` |
| BENCHMARK_EVIDENCE | ADV Layer A evidence_state failures documented |
| KNOWN_FAILURE | Fact-level coverage algorithm **not** mature（README + code comments） |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | EXPERIMENT（structure）· hit-level sufficiency used by Stable RAG separately |

## 14. Evidence sufficiency gate

| Field | Value |
|-------|--------|
| CAPABILITY | Hit-level sufficiency + L3 stop/retrieve gate |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | RAG `check_evidence_sufficiency` available；L3 gate flag **OFF**；`agent_evidence_sufficiency_obs/strategy` **OFF** |
| ENTRY_POINT | `rag/evidence.py` · `agent/evidence_gate.py` |
| EVIDENCE | Hit count / sim / diversity thresholds |
| TEST_COVERAGE | L3 evidence · `test_evidence_strategy.py` |
| BENCHMARK_EVIDENCE | Memory C2 NO_GO；ADV evidence_state failures |
| KNOWN_FAILURE | Hit-level ≠ fact-level |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | Hit-level SHOULD · L3 gate EXPERIMENT |

## 15. FactGoal / EvidenceLedger-related

| Field | Value |
|-------|--------|
| CAPABILITY | FactGoal · EvidenceItem ledger · matcher · decomposer |
| IMPLEMENTATION_STATUS | **PARTIAL** |
| DEFAULT_STATE | All `agent_l4_*` **OFF** |
| ENTRY_POINT | `types.FactGoal` · `decomposer.py` · `matcher.py` · `fact_contracts.py` |
| EVIDENCE | Structures + flag-gated runtime；**no `EvidenceLedger` class**（ledger = `EvidenceState.evidence_items`） |
| TEST_COVERAGE | `test_agent_l4_contracts.py` · decomposer/matcher/integrity |
| BENCHMARK_EVIDENCE | `eval/evidence_integrity` |
| KNOWN_FAILURE | README still lists FactGoal as unchecked roadmap；fact-level loop incomplete |
| MAINTENANCE_RISK | HIGH（research surface） |
| V1_0_RELEVANCE | EXPERIMENT / BACKLOG |

## 16. Critic

| Field | Value |
|-------|--------|
| CAPABILITY | Claim-level critic · control-plane actions · L3 critic retrieval |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | **OFF** · `rag_critic_enabled=False` · mode=`rules` · `agent_l3_critic_retrieval_enabled=False` |
| ENTRY_POINT | `rag/critic.py` · wired in `stream.py` / `engine.py` |
| EVIDENCE | Rules/LLM modes · fail_closed default when on |
| TEST_COVERAGE | `test_critic_*` · `test_agent_l3_critic.py` · W9 suite |
| BENCHMARK_EVIDENCE | `eval/critic_capability` · W9 frozen cases；P2 protocol mismatch historically **BLOCKED** |
| KNOWN_FAILURE | Not production-default；W9 rollout **NO** |
| MAINTENANCE_RISK | HIGH |
| V1_0_RELEVANCE | EXPERIMENT |

## 17. Failure recovery / fallback

| Field | Value |
|-------|--------|
| CAPABILITY | Tool fallback · planner Thorough fallback · degradation ladder · L4 reflection/stop |
| IMPLEMENTATION_STATUS | **IMPLEMENTED**（L4 paths flag-off） |
| DEFAULT_STATE | Tool replan ON（`agent_max_tool_replans=2`）；degradation **ON**；L4 reflection/stop **OFF** |
| ENTRY_POINT | `tool_fallback.py` · `core/degradation.py` · `reflection_recovery.py` · `stop_policy.py` |
| EVIDENCE | Multi-path recovery in runtime |
| TEST_COVERAGE | tool_fallback · chat_degradation · L4 recovery/stop · W9 recovery |
| BENCHMARK_EVIDENCE | Degrade cases in Agent Golden |
| KNOWN_FAILURE | L4 recovery experimental |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST（legacy fallback + degrade）· L4 = EXPERIMENT |

## 18. Citation / provenance

| Field | Value |
|-------|--------|
| CAPABILITY | Citation build · align · resolve · redact · density |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON for answered turns；refuse → empty citations；redact/density ON |
| ENTRY_POINT | `executor.chunk_to_citation` · `citation_align.py` · `api` resolve |
| EVIDENCE | P0 product requirement |
| TEST_COVERAGE | citations · align · resolve · redact · org citation · W10 provenance contracts |
| BENCHMARK_EVIDENCE | `_run_citation.py` · W10 Formal T1 = **citation-scope** only |
| KNOWN_FAILURE | Stream candidates vs final align；W10 Formal ≠ product accuracy |
| MAINTENANCE_RISK | HIGH（P0） |
| V1_0_RELEVANCE | V1_0_MUST |

## 19. Refusal / degraded semantics

| Field | Value |
|-------|--------|
| CAPABILITY | Refuse gate · confidence tiers · LLM-down degrade |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON · `degradation_enabled=True` |
| ENTRY_POINT | `relevance.py` · `confidence_reply.py` · `degraded_answer.py` · engine refuse path |
| EVIDENCE | normal / low / refuse |
| TEST_COVERAGE | relevance · confidence · chat_degradation* · W10 E-B40 response_mode |
| BENCHMARK_EVIDENCE | Golden rejection accuracy；W10 degraded Formal binding |
| KNOWN_FAILURE | Grey-band threshold sensitivity |
| MAINTENANCE_RISK | HIGH |
| V1_0_RELEVANCE | V1_0_MUST |

## 20. Retrieval eval

| Field | Value |
|-------|--------|
| CAPABILITY | Golden Hit@3 · enterprise/advanced · ablation runners |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | CI gate ON for retrieval golden + baseline compare |
| ENTRY_POINT | `test_retrieval_golden.py` · `scripts/run_benchmark.py` · `ci_baseline_check.py` |
| EVIDENCE | AGENTS Hit@3 11/11 |
| TEST_COVERAGE | golden / fast / full · hybrid · CI rag-* jobs |
| BENCHMARK_EVIDENCE | Enterprise ~71.1% real-emb snapshot（2026-08-09）；Advanced 14/14 CI baseline |
| KNOWN_FAILURE | Mock vs real emb divergence；fast gate file not in CI list |
| MAINTENANCE_RISK | HIGH |
| V1_0_RELEVANCE | V1_0_MUST |

## 21. Agent Golden

| Field | Value |
|-------|--------|
| CAPABILITY | 168-case agent behavior golden |
| IMPLEMENTATION_STATUS | **IMPLEMENTED**（suite exists） |
| DEFAULT_STATE | Manual / local pytest；**not** in `ci.yml` job pytest list |
| ENTRY_POINT | `test_agent_golden.py` · `golden_agent_qa.json` |
| EVIDENCE | 9 categories including ADVERSARIAL |
| TEST_COVERAGE | Self |
| BENCHMARK_EVIDENCE | Documented 168；trajectory parallel suite |
| KNOWN_FAILURE | Not PR-blocking |
| MAINTENANCE_RISK | MEDIUM（drift risk if unused in CI） |
| V1_0_RELEVANCE | V1_0_SHOULD |

## 22. Adversarial eval

| Field | Value |
|-------|--------|
| CAPABILITY | Frozen 4-strata adversarial panel |
| IMPLEMENTATION_STATUS | **IMPLEMENTED**（characterized / frozen） |
| DEFAULT_STATE | Eval-only · rollout **NO** |
| ENTRY_POINT | `app/eval/adversarial_capability/` · `test_adversarial_*` |
| EVIDENCE | primary **2/4** · trials **10/20** · ANS/CON fail |
| TEST_COVERAGE | P0–P4 harness tests |
| BENCHMARK_EVIDENCE | `v1-convergence-status` · `adversarial-v1-convergence-*` |
| KNOWN_FAILURE | ANS retrieval-trigger · CON refuse≠clarify |
| MAINTENANCE_RISK | LOW if frozen；HIGH if claimed as universal |
| V1_0_RELEVANCE | V1_0_SHOULD（as known limitation evidence）· NOT product claim |

## 23. W9 Critic evaluation

| Field | Value |
|-------|--------|
| CAPABILITY | Critic offline / control-plane / semantic eval |
| IMPLEMENTATION_STATUS | **PARTIAL** |
| DEFAULT_STATE | Research/eval · runtime critic **OFF** · rollout **NO** |
| ENTRY_POINT | `test_critic_w9_*.py` · fixtures `l4_critic/w9-*` · `eval/critic_capability` |
| EVIDENCE | Contracts + frozen cases；P2 historically BLOCKED / protocol mismatch |
| TEST_COVERAGE | W9 test family（not PR CI） |
| BENCHMARK_EVIDENCE | remaining-plan / task docs |
| KNOWN_FAILURE | Measurement protocol mismatch；not Formal product gate |
| MAINTENANCE_RISK | HIGH |
| V1_0_RELEVANCE | EXPERIMENT / BACKLOG documentation |

## 24. W10 Formal infrastructure

| Field | Value |
|-------|--------|
| CAPABILITY | Showcase Formal T1 measurement / acquisition / binding protocol |
| IMPLEMENTATION_STATUS | **IMPLEMENTED**（research infra；window **CLOSED**） |
| DEFAULT_STATE | Closed · no further E-B45 |
| ENTRY_POINT | `docs/research/w10-*` · `test_w10_eb*.py` · Formal result JSON |
| EVIDENCE | T1 11/11 citation-scope · T2/T3 N/A |
| TEST_COVERAGE | Extensive W10 contract tests（not PR CI） |
| BENCHMARK_EVIDENCE | `w10-closure/` · E-B44 Formal result |
| KNOWN_FAILURE | Scope ≠ product accuracy；degraded path Formal |
| MAINTENANCE_RISK | LOW if sealed；HIGH if mis-claimed |
| V1_0_RELEVANCE | V1_0_SHOULD（claim freeze input）· NOT_NOW for new Formal runs |

## 25. Local-model support

| Field | Value |
|-------|--------|
| CAPABILITY | Product local-model profile / routing |
| IMPLEMENTATION_STATUS | **STUB**（product） |
| DEFAULT_STATE | `agent_l4_local_model_profile_enabled=False` · `l4_placeholders.py` asserts off |
| ENTRY_POINT | placeholders · config flag |
| EVIDENCE | No production CHAT_PROVIDER swap to local |
| TEST_COVERAGE | `test_local_model_profile.py`（harness） |
| BENCHMARK_EVIDENCE | Roadmap only in README |
| KNOWN_FAILURE | Not a delivered capability |
| MAINTENANCE_RISK | LOW while stub |
| V1_0_RELEVANCE | NOT_NOW |

## 26. LM Studio integration

| Field | Value |
|-------|--------|
| CAPABILITY | OpenAI-compatible local eval adapter |
| IMPLEMENTATION_STATUS | **PARTIAL**（eval harness IMPLEMENTED；product ABSENT） |
| DEFAULT_STATE | Opt-in eval · default base `http://127.0.0.1:1234/v1` |
| ENTRY_POINT | `app/eval/local_model_profile/` · consumers in trajectory/tool/memory/adv |
| EVIDENCE | Adapter + skip-without-server tests |
| TEST_COVERAGE | local_model_profile · real-revalidation opt-in |
| BENCHMARK_EVIDENCE | ADV/MEMORY/TOOL local panels |
| KNOWN_FAILURE | Requires external LM Studio；not CI |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | EXPERIMENT / NOT_NOW for product |

## 27. Multimodal support

| Field | Value |
|-------|--------|
| CAPABILITY | Agent multimodal evidence · ingest vision |
| IMPLEMENTATION_STATUS | **STUB**（agent）· **PARTIAL**（ingest VL enrich） |
| DEFAULT_STATE | `agent_l4_multimodal_evidence_enabled=False`；`tongyi_vl_model=qwen-vl-plus` for ingest |
| ENTRY_POINT | `l4_placeholders.py` · `chat_vision.py` · parser vision enrich |
| EVIDENCE | Agent path blocked by placeholder assert |
| TEST_COVERAGE | Ingest/OCR paths；no agent multimodal evidence suite |
| BENCHMARK_EVIDENCE | None for agent multimodal |
| KNOWN_FAILURE | W10 Multimodal roadmap claim in README V1 section is **stale** |
| MAINTENANCE_RISK | LOW while stub |
| V1_0_RELEVANCE | NOT_NOW |

## 28. Memory support

| Field | Value |
|-------|--------|
| CAPABILITY | Working + long-term memory · importance · summary · governance |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | `agent_memory_enabled=True`；exposure/relevance-label **OFF** |
| ENTRY_POINT | `agent/memory*.py` · model `agent_memory.py` |
| EVIDENCE | Injected into planner prompts when enabled |
| TEST_COVERAGE | `test_agent_e3_memory.py` · memory_* · V1 boundary freeze |
| BENCHMARK_EVIDENCE | L3 exposure **10/10**；L4/L5 **0/10**；C2 **NO_GO** |
| KNOWN_FAILURE | Utilization / causal benefit **not** demonstrated；do not claim productized memory intelligence |
| MAINTENANCE_RISK | HIGH for claim drift |
| V1_0_RELEVANCE | V1_0_SHOULD（infrastructure）· capability claims EXPERIMENT/BACKLOG |

## 29. Tracing / observability

| Field | Value |
|-------|--------|
| CAPABILITY | Audit · metrics · OTEL · L3 trajectory/memory exposure traces |
| IMPLEMENTATION_STATUS | **PARTIAL** |
| DEFAULT_STATE | Audit/metrics product ON paths；L3 trajectory & memory exposure traces **OFF** |
| ENTRY_POINT | `services/audit/*` · `/metrics` · agent_run/step models · exposure_trace flags |
| EVIDENCE | Prometheus + audit API；optional compose monitoring |
| TEST_COVERAGE | audit_* · rate_limit_metrics · memory exposure tests |
| BENCHMARK_EVIDENCE | N/A |
| KNOWN_FAILURE | Deep agent trajectory not default-on |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_SHOULD（audit/metrics）· deep L3 traces EXPERIMENT |

## 30. Permissions / governance

| Field | Value |
|-------|--------|
| CAPABILITY | RBAC · workspace/org scope · approval · audit · rate limit · budget/breaker |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | ON（enterprise defaults） |
| ENTRY_POINT | `core/deps.py` · org/workspace scope · `api/audit.py` · rate_limit services |
| EVIDENCE | Member read-only · kb isolation |
| TEST_COVERAGE | permissions · workspace · org · audit · rate_limit* |
| BENCHMARK_EVIDENCE | Security tests in CI A-layer |
| KNOWN_FAILURE | Some rate-limit tests historically flaky with Redis/conftest（progress backlog） |
| MAINTENANCE_RISK | HIGH |
| V1_0_RELEVANCE | V1_0_MUST |

## 31. CI

| Field | Value |
|-------|--------|
| CAPABILITY | PR CI + optional benchmark/regression workflows |
| IMPLEMENTATION_STATUS | **IMPLEMENTED** |
| DEFAULT_STATE | Blocking: `ci.yml`；benchmark cron/dispatch；regression soft/deprecated |
| ENTRY_POINT | `.github/workflows/ci.yml` · `benchmark.yml` · `regression.yml` |
| EVIDENCE | ruff · alembic-check · config-wiring · pytest A · rag golden/enterprise/advanced · baseline gate · frontend build/test |
| TEST_COVERAGE | Self |
| BENCHMARK_EVIDENCE | baseline.json gate |
| KNOWN_FAILURE | Agent Golden / ADV / W9 / W10 **not** PR-blocking |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST |

## 32. Install / deployment

| Field | Value |
|-------|--------|
| CAPABILITY | Docker Compose install + scripts |
| IMPLEMENTATION_STATUS | **PARTIAL**（docs+compose present；live reinstall **not** re-verified this window） |
| DEFAULT_STATE | Compose-first README path |
| ENTRY_POINT | `docker-compose.yml` + `docker-compose.prod.yml` · `scripts/docker-up.ps1` · `init-secrets.ps1` |
| EVIDENCE | README 快速开始 · health endpoints |
| TEST_COVERAGE | `smoke-deploy.ps1` exists；not run this window |
| BENCHMARK_EVIDENCE | N/A |
| KNOWN_FAILURE | `docker-up.ps1` vs README prod overlay inconsistency；no bare-metal first-class path |
| MAINTENANCE_RISK | MEDIUM |
| V1_0_RELEVANCE | V1_0_MUST |

## 33. Demo / UI

| Field | Value |
|-------|--------|
| CAPABILITY | Product UI + demo script |
| IMPLEMENTATION_STATUS | **PARTIAL** |
| DEFAULT_STATE | Full enterprise UI exists；canonical demo script = **stub** |
| ENTRY_POINT | `frontend/` · `/login` · KB chat · audit · evaluations |
| EVIDENCE | 19 pages · CI frontend build/test |
| TEST_COVERAGE | Frontend unit in CI lint job |
| BENCHMARK_EVIDENCE | N/A |
| KNOWN_FAILURE | `ENTERPRISE_DEMO_SCRIPT.md` stub；root `BROWSER-MODULE-ACCEPTANCE.md` **missing**（archive only） |
| MAINTENANCE_RISK | MEDIUM for release storytelling |
| V1_0_RELEVANCE | UI = MUST · canonical demo path = REQUIRED_CLOSURE candidate |

## 34. Documentation

| Field | Value |
|-------|--------|
| CAPABILITY | AGENTS · README · progress · TECH · research closures · known limitations |
| IMPLEMENTATION_STATUS | **PARTIAL** |
| DEFAULT_STATE | Rich but partially stale（README V1 roadmap W9→W10 Multimodal） |
| ENTRY_POINT | `README.md` · `docs/status/*` · `docs/research/w10-closure/` · this package |
| EVIDENCE | W10 closure sealed；v1-known-limitations present |
| TEST_COVERAGE | Doc-backed contract tests for W10 |
| BENCHMARK_EVIDENCE | Claim matrices in research |
| KNOWN_FAILURE | README claim drift；BROWSER path drift；L4 checklist vs code mismatch |
| MAINTENANCE_RISK | HIGH for v1.0 messaging |
| V1_0_RELEVANCE | V1_0_MUST（accuracy of claims） |

---

## Cross-notes

1. **「BM25」** in marketing = **PG FTS** in code — keep claim language honest.  
2. **Memory ON ≠ memory intelligence proven.**  
3. **W10 100%** = Formal T1 citation-scope on Showcase T1-only only.  
4. **Graph recall** code exists (`graph_recall_enabled=False`) — rolled back；treat as EXPERIMENT/ABSENT-from-default，not inventoried as separate MUST capability beyond item 8 adjacency.
