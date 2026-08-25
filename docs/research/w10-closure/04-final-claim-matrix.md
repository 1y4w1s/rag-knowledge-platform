# 04 — Canonical W10 Claim Matrix

| CLAIM | STATUS | EVIDENCE | SCOPE | FORBIDDEN_OVERCLAIM |
|---|---|---|---|---|
| T1 citation-scope compliance | **PROVEN** | E-B44 Formal result · `formal-t1-result.json` · 11/11 · commit `6bf35b6` | Authorized Showcase T1-only Formal scope `w10_showcase_t1_only_v1` · C01–C11 · frozen Product After + companion gated scope | “W10 accuracy = 100%” · “Agent quality = 100%” · “RAG correctness = 100%” |
| T2 unsupported-assertion rate | **NOT_APPLICABLE** | E-B38 all DEGRADED · E-B40 response-mode gate · E-B43/E-B44 N/A writer | Showcase Narrow under current Product After | Treat N/A as PASS / FAIL / 0% unsupported / 100% quality |
| T3 grounding rate | **NOT_APPLICABLE** | Same as T2 | Same as T2 | Treat N/A as PASS / FAIL / 100% grounded |
| Frozen baseline + authorization provenance reconstructible | **PROVEN** | E-B35b · E-B36 · E-B37 | Showcase Owner-APPROVED freeze | Production deployment reproducibility |
| Real Product After acquisition completable | **PROVEN** | E-B38 acquisition | Frozen baseline worktree · C01–C11 | Production-scale capture / live LLM After |
| Source / After provenance bindable | **PROVEN** | E-B38–E-B39 | Authorized source `suoyin_local_research_product_after_v1` | Unbounded cross-env provenance |
| Synthetic contamination blockable | **PROVEN** | Freeze anti-contamination · E-B18/E-B24 vetoes · E-B39 binding refusal | Formal Product After path | All synthetic research fixtures forever unused |
| DEGRADED response identifiable | **PROVEN** | E-B40 classification | E-B38 Product After C01–C11 | “Model refused correctly” as quality claim |
| DEGRADED not counted as T2/T3 perfect | **PROVEN** | E-B40 gate closed perfect-score path | T2/T3 claim-quality denominator | N/A = good answer quality |
| Same-trajectory gated scope + citations capturable | **PROVEN** | E-B41 companion | Same frozen baseline / parent run family | Formal T1 without E-B44 recomputation |
| Formal candidate Isolated from Formal oracle | **PROVEN** | E-B42 integrity rules · E-B44 leak audit | Formal T1 writer | Candidate 11/11 = Formal |
| T1 Formal raw recomputation | **PROVEN** | E-B44 | Scope v2 T1-only | Full Formal Observation {T1,T2,T3} complete |
| Live LLM answer quality | **NOT_MEASURED** | — | — | Infer from DEGRADED After or T1 100% |
| Local model capability | **NOT_MEASURED** | `formal_model_identity=DEFER_TO_BENCHMARK_TRACK` | — | Showcase freeze = local model bench |
| Critic semantic capability | **NOT_PROVEN** | — | — | T1 citation ⊆ scope proves Critic semantics |
| A4 live LLM capability | **NOT_PROVEN** | — | — | — |
| LM Studio capability | **NOT_PROVEN** | — | — | — |
| Production availability | **NOT_PROVEN** | — | — | Research baseline = prod ready |
| Production-scale performance | **NOT_PROVEN** | — | — | — |
| Paper-grade reproducibility | **NOT_PROVEN** | dependency snapshot unpinned | — | — |
| Dependency-complete environment pin | **NOT_PROVEN** | `EXPLICITLY_UNPINNED_SHOWCASE` | — | — |
| Research Benchmark claims | **NOT_PROVEN** | — | — | W10 Formal T1 = Research Benchmark |

## Status vocabulary (frozen)

```text
PROVEN          = measured or protocol-proven under declared scope
NOT_APPLICABLE  = excluded from denominator by authorized gate (≠ PASS/FAIL)
NOT_MEASURED    = in-scope conceptually but no Formal measurement executed
NOT_PROVEN      = not established by W10 evidence chain
```
