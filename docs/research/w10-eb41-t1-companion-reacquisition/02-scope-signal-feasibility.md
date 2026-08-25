# 02 — Scope signal feasibility

## Question

Does frozen product path expose `gen_plan.gated_chunks` such that external
orchestration can persist it **without** modifying `backend/app`?

## Probe (frozen worktree @ `3ce0e75…`)

```text
AgentGenerationPlan fields include gated_chunks     = YES
execute_product_path_plan returns gen_plan          = YES
gen_plan.gated_chunks readable after prepare        = YES
drain_product_generation_phase yields state[citations]
  on same trajectory                                = YES
requires_backend_app_change                         = NO
```

C01 smoke (same trajectory):

```text
gated_ids = [75fc4898-c04a-51af-921e-101ab5133e2b]
cite_ids  = [75fc4898-c04a-51af-921e-101ab5133e2b]
subset    = True
llm       = false (force_zero_llm)
```

## Verdict

```text
T1_GATED_SCOPE_SIGNAL_AVAILABLE = YES
T1_COMPANION_REACQUISITION_BLOCKED = (none)
```

Capture method: external script calls

1. `execute_product_path_plan` → read `gen_plan.gated_chunks`
2. `drain_product_generation_phase` → read `state[citations]` / `state[content]`

Same trajectory; no inference from final citations; no gold/E-B18 scope.
