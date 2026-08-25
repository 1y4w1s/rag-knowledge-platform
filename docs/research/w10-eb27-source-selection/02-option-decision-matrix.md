# 02 — Option decision matrix

> Re-scores E-B26 Options A–D against E-B27 criteria.  
> Matrix only — winner rationale lives in `03`.

## 1. Option roster (unchanged from E-B26)

| ID | Name |
|---|---|
| **A** | E-B15 product stream harness |
| **B** | LM Studio local model |
| **C** | API model |
| **D** | Future authorized production path |

## 2. Decision matrix

| Dimension | **A** E-B15 harness | **B** LM Studio local | **C** API model | **D** Future authorized prod |
|---|---|---|---|---|
| **source identity** | Informal harness today; **can** mint named formal `after_source` on Scheme A product stream | Absent; needs `lm_studio_local_<model>_<rev>` | Absent; needs `api_<provider>_<model>_<rev>` | Absent today; strongest **if** export exists later |
| **capture mode** | Scheme A stream (`product_stream_refusal` / `product_stream_degraded` / …); needs **owner-declared** Narrow mode (non-smoke upgrade) | Local model gen (A4-adjacent); off-product risk if bypasses `_stream_generation_phase` | Cloud/HTTP API gen (A4); product stream preferred if ever authorized | Prod/staging product generation; mode must still be declared |
| **llm_called** | `false` in current no-LLM modes (honest) | `true` (must) | `true` (must) | Matches reality (usually `true`) |
| **reproducibility** | **HIGH** (deterministic degraded/refusal) | **MED–LOW** (model file · seed · LM Studio rev) | **LOW–MED** (provider nondeterminism) | **MED–LOW** unless deploy/model pinned |
| **BP-A compatibility** | Bindable after capture + AG-5 rebound; live×E-B12B **INCOMPATIBLE now** | Bindable after capture+rebound | Bindable after capture+rebound | Bindable after capture+rebound |
| **Narrow scope compatibility** | **IN** (no A4 required for current modes) | **OUT** (A4-class / live LLM under E-B24 freeze) | **OUT** (A4 excluded) | **CONDITIONAL** — only if declared mode stays non-A4 under Narrow; else needs scope revision |
| **implementation effort** | **LOW** — harness substrate exists (`PRODUCT_AFTER_CAPTURE_HARNESS_READY`) | **MED–HIGH** — env freeze + product-path proof | **MED–HIGH** — keys · spend · product-path proof | **HIGH** — export pipeline · ops · auth |
| **risks** | Informal→formal silent upgrade; claiming LLM faithfulness while `llm_called=false`; unrebounded gold | Narrow scope contradiction; off-product path; reproducibility drift | Narrow A4 contradiction; $ + nondeterminism; key leakage | Approving absent source; prod≠suite pin; highest ops |

### 2.1 Criteria bands (E-B27 weights applied)

| Criterion (weight ↓) | A | B | C | D |
|---|---|---|---|---|
| formal eligibility (Narrow) | **HIGH** potential later · **NO now** | **OUT** | **OUT** | **MED** potential later · **NO now** (source absent) |
| reproducibility | **HIGH** | **MED–LOW** | **LOW–MED** | **MED–LOW** |
| source identity / provenance | **MED** (stampable path) | **LOW** | **LOW** | **HIGH** if extant · **OUT** today |
| hash binding compatibility | **HIGH** (after rebound) | **HIGH** (after rebound) | **HIGH** (after rebound) | **HIGH** (after rebound) |
| capture feasibility | **HIGH** | **MED** | **MED** | **LOW** (not extant) |
| owner authorization difficulty | **MED** (freeze mode/identity + stamp) | **HIGH** (+ scope revise) | **HIGH** (+ scope revise) | **HIGH** (absent + ops) |
| maintenance burden | **LOW** | **MED** | **MED** | **HIGH** |
| cost | **LOW** | Local compute | API $ | Highest ops |

## 3. Hard veto summary

```text
B → OUT for Narrow PRIMARY (A4-adjacent live LLM)
C → OUT for Narrow PRIMARY (A4 excluded)
D → not stampable now (source absent); keep as future path only
A → only remaining in-scope PRIMARY candidate under frozen Narrow
```

```text
E-B18 synthetic / author-owned pack = FORBIDDEN as acquisition option
  (tests-only · contamination if used as Product After)
```

## 4. Honesty notes

- Pytest green on E-B15 / E-B18 / E-B20 / E-B22 ≠ source approval.
- `llm_called=false` on A is honest for no-LLM modes; it does **not** claim
  live-model product faithfulness.
- Selecting A as **candidate** does not clear B2′ / AG-5 / unrebounded gold.

## 5. Stamp

```text
OPTION_DECISION_MATRIX_COMPLETE = YES
PRIMARY_PICK_IN_THIS_FILE       = NO   (see 03)
AFTER_SOURCE_APPROVED           = NO
E-B_FORMAL_READY                = NO
```
