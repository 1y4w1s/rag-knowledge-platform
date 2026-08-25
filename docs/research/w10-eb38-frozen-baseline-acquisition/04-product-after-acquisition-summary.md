# 04 — Product After acquisition summary

## Capture path (reused · not redesigned)

```text
authorized product preparation (E-A2 execute_product_path_plan)
        ↓
prepare_agent_generation
        ↓
_stream_generation_phase   (real product stream · E-B15 drain)
        ↓
state["content"] / state["citations"]
        ↓
E-B26 Formal After Capture Record  (records/C0x.json)
```

Orchestration only: `scripts/run_frozen_product_after_acquisition.py`  
(lives in authorization workspace artifacts · **does not** mutate frozen worktree).

## Provenance summary

| Property | Observed |
|---|---|
| Product boundary entered | YES (`stream_phase_entered=true` for all C01–C11) |
| After body source | real `state["content"]` |
| Citations source | real `state["citations"]` |
| `capture_mode` (freeze enum) | `product_stream` |
| E-B15 submode | `product_stream_degraded` for all captured cases |
| `llm_called_observed` | **false** (suite-wide) |
| Synthetic / E-B6 / E-B18 / fixture-answer | **none** |
| Formal measurement flag | `false` on every record |

## Honesty gate result

Authorized backend is `none_no_llm` with `llm_called_expected=false`.

The product path **did** produce real Product After under that constraint via the
existing degraded stream branch (provider keys empty; LLM token stream forbidden).

```text
AUTHORIZED_PRODUCT_AFTER_NOT_OBTAINABLE_WITH_CURRENT_NO_LLM_PATH = NO
(i.e. After WAS obtainable · acquisition proceeded)
```

### Interpretation caution

Degraded After bodies begin with the product degraded-service notice and append
gated document excerpts. That is **honest none_no_llm Product After**, not a
claim of live-LLM answer quality. This window does **not** score T2/T3.

## Contamination check

```text
eb6-synthetic prefix          = ABSENT
author-owned claim embedding  = ABSENT
W9 fixture answer equality    = ABSENT
Critic oracle injection       = ABSENT
hand-written answer fill      = ABSENT
contamination_hits            = []
```

## Hash note

- `source_hash` / `observed_content_hash` = BP-A content-string codec  
  (`sha256:` + UTF-8 digest of observed `content`)
- `harness_after_content_hash` = E-B15 harness digest (canonical-JSON of string)  
  retained for cross-check; **not** substituted for BP-A `source_hash`

C01 and C11 may share an identical BP-A `source_hash` when degraded bodies are
byte-identical; that is recorded honestly and is **not** a binding failure.
