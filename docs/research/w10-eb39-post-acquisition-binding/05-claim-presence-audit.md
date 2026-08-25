# 05 — Claim Presence / Applicability Audit (C01–C11)

## Method (frozen only)

- **Allowed:** E-B17 BP-B deterministic whitespace-normalized substring presence (`claim_texts_present_in_content`).
- **Forbidden this window:** LLM judge · NLI · fuzzy · Critic · embedding similarity · inventing a new matcher.

## Assertion vs presence

Degraded After bodies begin with the product unavailable boilerplate and then dump `[片段N]` excerpts. Substring **presence** of a gold claim inside a fragment dump does **not** prove the model **asserted** that claim as an answer.

Frozen protocol has **no** speech-act / assertion-vs-quote discriminator beyond substring presence (BP-B) and optional integrity notes.

```text
CLAIM_PRESENCE_UNRESOLVED_BY_FROZEN_PROTOCOL = YES
```

Therefore `claim_actually_asserted_in_after` is recorded as **UNDETERMINED** for every claim, with presence noted separately.

## After content shape (all C01–C11)

```text
prefix = "AI 回答服务暂时不可用，以下是最相关的文档片段供您参考。请稍后再试以获得完整回答。"
+ one or more [片段N] document excerpt lines
plan_refusal = false
llm_called_observed = false
```

## Per-claim table

| case | gold_claim_id | gold_label | substring_present (BP-B) | claim_actually_asserted_in_after | basis |
|---|---|---|---|---|---|
| C01 | `C01-fully-supported-exact::c01` | supported | YES | UNDETERMINED | text appears inside degraded fragment dump; no frozen assertion discriminator |
| C02 | `C02-supported-paraphrase-low-lexical::c01` | supported | YES | UNDETERMINED | same |
| C03 | `C03-one-unsupported-among-supported::c01` | supported | NO | UNDETERMINED | absent under BP-B presence; still not a resolved “non-assertion” speech-act rule beyond presence |
| C03 | `C03-one-unsupported-among-supported::c02` | unsupported | NO | UNDETERMINED | same |
| C04 | `C04-valid-citation-wrong-evidence::c01` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C04 | `C04-valid-citation-wrong-evidence::c02` | unsupported | NO | UNDETERMINED | absent under BP-B presence |
| C05 | `C05-known-conflict-overcertain::c01` | supported | NO | UNDETERMINED | gold text `保留30天` vs After excerpt `保留 30 天` — presence fail; no fuzzy repair allowed |
| C05 | `C05-known-conflict-overcertain::c02` | supported | NO | UNDETERMINED | same spacing class |
| C06 | `C06-required-fact-missing::c01` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C06 | `C06-required-fact-missing::c02` | unverifiable | NO | UNDETERMINED | absent under BP-B presence |
| C07 | `C07-correct-insufficiency-refusal::c01` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C08 | `C08-nonassertive-preface-supported-fact::c01` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C09 | `C09-supported-plus-unverifiable::c01` | supported | NO | UNDETERMINED | absent under BP-B presence |
| C09 | `C09-supported-plus-unverifiable::c02` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C10 | `C10-supported-multiclaim-multicitation::c01` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C10 | `C10-supported-multiclaim-multicitation::c02` | supported | YES | UNDETERMINED | fragment-quote presence only |
| C11 | `C11-citation-format-only-defect::c01` | supported | YES | UNDETERMINED | fragment-quote presence only |

### Counts

```text
gold claims on C01–C11     = 17
substring_present YES      = 11
substring_present NO       = 6
asserted resolved YES/NO   = 0 / 0  (all UNDETERMINED)
```

## Implication

This window is **not** a new scorer. Presence audit shows degraded After cannot be treated as a faithful asserted-claim surface under frozen protocol. Do not invent a matcher to force YES/NO assertion labels.
