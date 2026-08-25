# 02 — Local Model Strategy (Planned)

> Development Generation Backend route.  
> **Status: PLANNED** — not installed, not pinned, not executed in this window.

## 1. Intent

```text
Goal: reduce sole dependence on external API generation for development.
Posture: Local Model First for Agent / prompt / tool experiments.
Formal Evaluation Source: still unapproved (separate role · stamp pending).
Product After capture path candidate: E-B15 harness = validated Product After capture path candidate
  (PRIMARY_CANDIDATE_SOURCE=A · selected design candidate only · not approved · ≠ Formal Evaluation Source).
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
```

Local models are a **Development Generation Backend** (and future Track B)
concern. They are **not** Narrow Formal PRIMARY Product After capture path
candidates under E-B27 freeze, and they are **not** Formal Evaluation Source.

---

## 2. Target stack (directional)

```text
Runtime:   LM Studio  (OpenAI-compatible local server)
Families:  GLM / Qwen / Llama  (or successors)
Client:    product / agent code pointing at local base_url when configured
```

Selection among GLM vs Qwen vs Llama is **not** frozen here — only the
strategy that a local runtime + open weights family is the preferred
Development Backend path.

---

## 3. Pin surface (must freeze before any comparable claim)

Before claiming “same local model” across experiments or opening a
Local Model Evaluation Track, freeze and record:

| Pin field | Why |
|---|---|
| **model file hash** | Exact weights identity (SHA-256 of GGUF/safetensors) |
| **quantization** | e.g. Q4_K_M vs Q8_0 — changes answers |
| **runtime version** | LM Studio / llama.cpp / CUDA stack version |
| **inference parameters** | temperature · top_p · max_tokens · seed · stop · context length |
| **chat template / system prompt** | Often silently changes behavior |
| **endpoint identity** | host:port · API path · model id string as served |

```text
LOCAL_MODEL_PIN_SURFACE_DEFINED = YES   (schema / checklist · this window)
LOCAL_MODEL_PINNED              = NO    (no concrete hash/version recorded)
LOCAL_MODEL_RUNTIME_CALLED      = NO
```

---

## 4. What Local First does / does not do

**Does:**

- Let developers iterate Agent tools without burning API quota.
- Survive provider outages for **engineering** work.
- Enable future Track B (capability eval) under a separate contract.

**Does not:**

- Auto-qualify as Formal Evaluation Source.
- Become Narrow Formal PRIMARY (`LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY=NO`).
- Clear `AFTER_SOURCE_APPROVED` or `E-B_FORMAL_READY`.
- Replace E-B27 candidate A (E-B15 harness validated Product After capture path candidate).
- Authorize silent substitution of formal After bodies.

---

## 5. Relation to product LLM config

Product historically uses cloud APIs (e.g. DeepSeek + 通义千问 per AGENTS).  
Local First is a **development / evaluation-extension** strategy:

```text
Product After capture path (Narrow): E-B15 harness validated candidate A
                                     · stamp pending · ≠ Formal Evaluation Source
Development Generation Backend:      Local First (LM Studio + open weights)
Optional cloud API for development:  allowed · not sole foundation
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY = NO
```

Changing product default LLM for production users is **out of scope** of
E-B28 (would need TECH/PRD + migration discipline). This doc only freezes
the **evaluation architecture** boundary.

---

## 6. Stamp

```text
LOCAL_MODEL_STRATEGY                     = PLANNED
LOCAL_MODEL_AS_NARROW_FORMAL_PRIMARY     = NO
LOCAL_MODEL_PINNED                       = NO
LOCAL_MODEL_EVAL_EXECUTED                = NO
FORMAL_SOURCE_APPROVED                   = NO
AFTER_SOURCE_APPROVED                    = NO
SOURCE_APPROVED                          = NO
E-B_FORMAL_READY                         = NO
```
