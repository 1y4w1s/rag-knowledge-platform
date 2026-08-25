# 01 — Formal Source vs Development Model Boundary

> Freezes two non-interchangeable concepts.  
> Mislabeling either side is an authorization / honesty veto.

## 1. Two concepts (frozen)

### Formal Evaluation Source

```text
Purpose:
  Product After Capture
  Binding (BP-A)
  T2 / T3 measurement
  Formal / reserved observation artifacts
```

**Hard requirements (all must hold before formal denom use):**

| Requirement | Meaning |
|---|---|
| **identity** | Named `after_source` + `model_identity` + `capture_mode` frozen |
| **reproducibility** | Declared config + base_sha / run_identity; replay honesty |
| **provenance** | Body path auditable (product stream / owner-authorized export) |
| **authorization** | Owner stamp → `AFTER_SOURCE_APPROVED=YES` (currently **NO**) |

Formal Evaluation Source is **not** “whatever model the developer used last week.”
Formal Evaluation Source is **not** the E-B15 harness itself
(harness = validated Product After capture path candidate until stamped).

### Development Generation Backend

```text
Purpose:
  Daily development
  Agent capability iteration
  Prompt / tool / retrieval experiments
  Informal smoke / harness green checks
```

**Allowed surfaces (non-exhaustive):**

- LM Studio (local OpenAI-compatible endpoint)
- Local LLM weights (GLM / Qwen / Llama / …)
- Cloud API models (DeepSeek / Qwen API / …)
- Deterministic no-LLM harness modes (refusal / degraded)

**Does not require** formal provenance stamp.  
**Must not** silently become Formal Evaluation Source.

---

## 2. Non-substitution rule (hard)

```text
Development Generation Backend  ⇏  Formal Evaluation Source
Formal Evaluation Source        ⇏  "the only model we develop against"
```

| Pattern | Verdict |
|---|---|
| Score formal T2/T3 on LM Studio / API Ad-hoc runs | **VETO** |
| Cite Agent experiment answers as Product After | **VETO** |
| Treat E-B15 harness as Formal Evaluation Source without stamp | **VETO** |
| Upgrade E-B15 informal capture → formal without stamp | **VETO** |
| Treat DeepSeek API price change as Formal Evaluation Source change | Separate concern; Formal needs explicit re-auth |
| Use local model for prompt tuning while Product After candidacy stays on A | **ALLOWED** (intended) |
| Later open Track B (Local Model Capability Eval) under new contract | **ALLOWED** (future · not now) |

---

## 3. Mapping to E-B27 Options

```text
E-B15 harness  ≠  Formal Evaluation Source
E-B15 harness  =  validated Product After capture path candidate
```

| E-B27 Option | Product After capture-path role | Development Generation Backend |
|---|---|---|
| **A** E-B15 harness | **PRIMARY candidate** = validated Product After capture path candidate (not Formal Evaluation Source; not approved) | Yes (esp. no-LLM modes) |
| **B** LM Studio | OUT for Narrow PRIMARY candidacy | **Yes · Local First preferred** |
| **C** API model | OUT for Narrow PRIMARY candidacy | Yes · not sole foundation |
| **D** Future prod export | Deferred candidacy | Ops path when extant |
| E-B18 synthetic | **Forbidden** as Product After | Codec / binding hygiene only |

**Formal Evaluation Source** remains a separate role: only an
owner-authorized, identity-frozen Product After denom — currently
`FORMAL_SOURCE_APPROVED=NO` / `AFTER_SOURCE_APPROVED=NO`.

---

## 4. Project long-term posture

```text
Product goal ≠ lock forever to one cloud API model.
Past: DeepSeek API used in product path.
External variables: pricing · availability · rate limits · provider policy.
Therefore:
  Development Generation Backend MUST support Local Model First.
  Formal Evaluation Source MUST keep provenance / reproducibility / authorization.
```

Separation protects both:

1. **Maintainability** — engineering can move to local stacks without rewriting Formal history.
2. **Credibility** — Formal rates stay bound to an authorized, named source.

---

## 5. Claims / non-claims (this document)

| Claims (correct) | Does **not** claim (forbidden / wrong semantics) |
|---|---|
| Boundary designed and frozen | Any Formal Evaluation Source is approved |
| Candidate A = validated Product After capture path candidate | ~~E-B15 harness = Formal Evaluation Source~~ (false) |
| Local First is Development strategy | LM Studio is Formal After / Local eval executing |
| | Acquisition / Formal Observation may start |

## 6. Stamp

```text
FORMAL_VS_DEV_BOUNDARY_DEFINED = YES
FORMAL_SOURCE_APPROVED         = NO
AFTER_SOURCE_APPROVED          = NO
E-B_FORMAL_READY               = NO
```
