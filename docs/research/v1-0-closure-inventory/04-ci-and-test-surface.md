# 04 — CI and Test Surface Inventory

> Workflows under `.github/workflows/` · Judgment only · **no CI optimization this window**.

## Workflows

| Workflow | Trigger | Role |
|----------|---------|------|
| `ci.yml` | push/PR → `master` | **Primary blocking CI** |
| `benchmark.yml` | `workflow_dispatch` + Sunday cron | Long / cost-sensitive · not PR gate |
| `regression.yml` | RAG-path PRs + dispatch | **Deprecated** · soft (`continue-on-error`) |

---

## `ci.yml` jobs

| Job | Suite / command | Scope | Mock/real | Ext deps | Blocking | Runtime cost |
|-----|-----------------|-------|-----------|----------|:--------:|--------------|
| `test` | ruff · alembic up/down · pytest A-layer + `test_retrieval_golden.py` + hybrid/rerank/chunker/ingest | unit+integration+golden | mostly **mock** emb | Postgres pgvector | YES | medium |
| `alembic-check` | `alembic upgrade` + `alembic check` | migration formal drift | N/A | Postgres | YES | low |
| `config-wiring` | `test_config_wiring.py` | contract | N/A | none | YES | low |
| `rag-golden` | `run_benchmark.py --dataset golden_qa` + scorer | golden retrieval | **real** emb | Postgres · HF mirror · optional keys | YES | medium–high |
| `rag-enterprise` | enterprise_qa | enterprise retrieval | real emb | same | YES | medium–high |
| `rag-advanced` | advanced_qa | advanced retrieval | real emb | same | YES | medium |
| `benchmark-gate` | `ci_baseline_check.py` vs `baseline.json` | formal baseline | artifacts | none | YES | low |
| `lint` | ruff backend · frontend `npm ci/build/test` | lint+FE unit | N/A | Node 22 | YES | medium |

### Explicitly **not** in PR pytest job list

| Suite | Present in repo? | PR blocking? |
|-------|------------------|:------------:|
| Agent Golden (`test_agent_golden.py`) | YES | **NO** |
| Adversarial harness | YES | **NO** |
| W9 Critic tests | YES | **NO** |
| W10 Formal tests | YES | **NO** |
| `test_retrieval_golden_fast.py` | YES | **NO**（docstring says Fast Gate；CI uses full golden file） |

Note: `collect-only` may still import many modules；execution of Agent/ADV/W9/W10 suites is not the PR gate.

---

## Suite taxonomy

| Kind | Examples | PR CI? |
|------|----------|:------:|
| unit | chunker · config wiring · many agent unit | partial |
| integration | auth · upload · chat · security | yes（subset） |
| golden | `test_retrieval_golden.py` · CI rag-* | yes |
| adversarial | `eval/adversarial_capability` · `test_adversarial_*` | no |
| formal | W10 E-B* Formal / acquisition contracts | no |
| local-model | LM Studio adapters · real-revalidation | no（opt-in） |
| optional/manual | Agent Golden 168 · ablation · CRAG nightly | no / cron |

---

## Eval surfaces（non-CI or soft）

| Surface | Evidence | Blocking? |
|---------|----------|:---------:|
| Retrieval Hit@3 11/11 | AGENTS + `test_retrieval_golden` + CI | YES |
| Enterprise / Advanced | CI jobs + baseline | YES |
| Agent Golden 168 | `golden_agent_qa.json` | NO |
| ADV frozen 2/4 · 10/20 | v1-convergence docs | NO |
| W9 Critic | fixtures + tests；rollout NO | NO |
| W10 Formal T1 | closure package · MEASURED | NO（research sealed） |
| Memory C1/C2 | eval package · C2 NO_GO | NO |
| Tool selection S2/S3A | eval · NO_MEASURABLE_GAIN | NO |

---

## Judgment

```text
V1_0_CI_COVERAGE = PARTIAL
```

**Why PARTIAL（not SUFFICIENT / not UNKNOWN）:**

- Retrieval + migrate + config + FE build are solidly gated.
- Agent behavior / ADV / Critic / Formal are **repo-present** but **not** PR-blocking.
- That is acceptable for “Stable RAG v1.0” if claims stay retrieval/governance-centered；**insufficient** if v1.0 claims imply Agent Golden / ADV / Critic are CI-proven.

**Do not optimize CI in this window.**
