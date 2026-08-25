# 04 — CI and Test Surface Inventory

> Updated by **V1.0-C5** (CI scope & release-gate audit).  
> Canonical contract: [`../../project/v1-0-release-cut-line.md`](../../project/v1-0-release-cut-line.md) §「V1.0 CI Contract」.

## Workflows

| Workflow | Trigger | Role |
|----------|---------|------|
| `ci.yml` | push/PR → `master` | **Primary PR-blocking CI**（Tier 1） |
| `benchmark.yml` | `workflow_dispatch` + Sunday cron | Long / cost-sensitive · **Tier 2** · not PR gate |
| `regression.yml` | `workflow_dispatch` only | **Deprecated soft** · removed from PR triggers（C5） |

---

## `ci.yml` jobs（post-C5）

| Job | Suite / command | Scope | Mock/real | Ext deps | Blocking | Runtime cost |
|-----|-----------------|-------|-----------|----------|:--------:|--------------|
| `test` | ruff · alembic up/down · A-layer pytest · `test_retrieval_golden.py` · hybrid/rerank/chunker/ingest · **`test_c4_ingestion_loop_isolation.py`** | unit+integration+golden+C4 | mostly **mock** emb | Postgres pgvector | YES | medium |
| `alembic-check` | `alembic upgrade` + `alembic check` | migration formal drift | N/A | Postgres | YES | low |
| `config-wiring` | `test_config_wiring.py` + **`test_v1_0_safe_defaults.py`** | contract + defaults OFF | N/A | none | YES | low |
| `rag-golden` | `run_benchmark.py --dataset golden_qa --skip-entity-extract` + scorer | golden retrieval | **local BGE** | Postgres · HF mirror | YES | medium–high |
| `rag-enterprise` | enterprise_qa `--skip-entity-extract` | enterprise retrieval | local BGE | same | YES | medium–high |
| `rag-advanced` | advanced_qa `--skip-entity-extract` | advanced retrieval | local BGE | same | YES | medium |
| `benchmark-gate` | `ci_baseline_check.py` vs `backend/tests/benchmark/baseline.json` | formal baseline · **hard fail on missing/unparseable gate output** | artifacts | none | YES | low |
| `lint` | ruff backend · frontend `npm ci/build/test` | lint+FE unit | N/A | Node 22 | YES | medium |

### Explicitly **not** in PR pytest job list

| Suite | Present in repo? | Classification |
|-------|------------------|----------------|
| Agent Golden (`test_agent_golden.py`) | YES | **RELEASE_ONLY / MANUAL** |
| Adversarial harness | YES | **RESEARCH_ARCHIVE** |
| W9 Critic tests | YES | **RESEARCH_ARCHIVE** |
| W10 Formal tests | YES | **RESEARCH_ARCHIVE** |
| Canonical demo | YES（`scripts/demo.ps1`） | **MANUAL_ONLY** |
| `test_retrieval_golden_fast.py` | YES | **NO**（docstring Fast Gate；CI uses full golden file） |

Note: `collect-only` may still import many modules；**execution** of Agent/ADV/W9/W10 suites is not the PR gate.

---

## Retrieval Hit@3 gate（verified）

| Aspect | Fact |
|--------|------|
| Case count | **11** classic gate IDs（GQ-1…GQ-12，fixture 缺 GQ-9） |
| Metric | Hit@3（`HIT_K=3`） |
| PR pytest path | `test` job → `tests/test_retrieval_golden.py` · **mock** embeddings · **blocks PR** |
| PR real-emb path | `rag-golden` + `benchmark-gate` · local BGE · baseline `hit_at_k=0.955` · `drop_fail_pp=0.02` · `absolute_min=0.90` |
| External paid LLM | **Not required**（entity extract skipped in rag-*） |
| Fixtures | Frozen under `backend/tests/fixtures/` · do not edit to greenwash |

---

## Suite taxonomy

| Kind | Examples | PR CI? |
|------|----------|:------:|
| unit | chunker · config wiring · safe defaults | yes |
| integration | auth · upload · chat · security · **C4 ingest loop** | yes（subset） |
| golden | `test_retrieval_golden.py` · CI rag-* | yes |
| adversarial | `eval/adversarial_capability` · `test_adversarial_*` | no |
| formal | W10 E-B* Formal / acquisition contracts | no |
| local-model | LM Studio adapters · real-revalidation | no（opt-in） |
| optional/manual | Agent Golden 168 · ablation · CRAG nightly · demo.ps1 | no / cron / manual |

---

## Eval surfaces

| Surface | Evidence | Blocking? |
|---------|----------|:---------:|
| Retrieval Hit@3 11/11 | AGENTS + `test_retrieval_golden` + CI | YES |
| Enterprise / Advanced | CI jobs + baseline | YES |
| C4 ingestion loop isolation | `test_c4_ingestion_loop_isolation.py` in `test` job | YES |
| Safe defaults OFF | `test_v1_0_safe_defaults.py` | YES |
| Agent Golden 168 | `golden_agent_qa.json` | NO |
| ADV frozen 2/4 · 10/20 | v1-convergence docs | NO |
| W9 Critic | fixtures + tests；rollout NO | NO |
| W10 Formal T1 | closure package · MEASURED | NO（research sealed） |
| Canonical demo | `scripts/demo.ps1` · live provider | NO（manual） |

---

## Judgment（post-C5）

```text
V1_0_CI_COVERAGE = SUFFICIENT_FOR_STABLE_RAG_V1_0
```

**Why sufficient（for Stable RAG v1.0）:**

- Retrieval + migrate + config + safe defaults + C4 ingest isolation + FE build are gated.
- Agent / ADV / Critic / Formal remain **repo-present** and **explicitly non-PR** — claims must not imply otherwise.
- Paid DeepSeek / Tongyi / LM Studio are **not** required for PR CI（local BGE + mock pytest paths）.
- PR CI is **not** completely offline: BGE model artifact availability may require the configured Hugging Face mirror/cache — do not drop the real retrieval gate to eliminate that.
