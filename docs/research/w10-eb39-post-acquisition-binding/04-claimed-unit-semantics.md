# 04 — Frozen claimed-unit semantics

## Question

Does “claimed units are gold `asserted_claims`” mean:

- **A.** each gold claim must actually appear as an assertion in final After content, or  
- **B.** the gold ledger itself is the scorer’s claimed-unit universe even if After never asserted that claim?

## Evidence (frozen contracts — not guessed)

### 1. E-B16 `01` §3.2 / §4.2 — ledger-only segmentation

```text
Formal segmentation authority = ledger.
After content is the observed body under evaluation;
atomic claims are not re-discovered at score time.
EXTRACTION_FORMAL = LEDGER_ONLY
```

Mapping step 3: **Use `asserted_claims` as the claim set**.

### 2. E-B16 `02` §1.1 / §2.1 — matching + T2 formula

```text
for claim in asserted_claims:
  identity = claim.claim_id
  label    = claim.label          # gold only
unsupported_rate = |{c ∈ asserted : label=unsupported}| / |asserted|
Denominator = Ledger asserted_claims after exclude_refusal_boilerplate
Labels = Only from gold; scorer never re-labels
```

### 3. E-B19 contract schema / README

```text
Denom = gold asserted_claims
Labels only from gold
claim_identity = claim_id
no_fuzzy / no_nli / no_llm_judge
```

Status `NOT_APPLICABLE` when denom 0 / BP-C — **not** when After fails to assert a gold row.

### 4. Presence is a **binding integrity** concern, not a redefinition of the universe

| Layer | Role |
|---|---|
| Scorer formula universe | Gold `asserted_claims` (**B**) |
| BP-B body integrity | each `claim.text` locatable in After (E-B17 `claim_texts_present_in_content`) |
| BP-A product path | gold rebound `kind=observed_after` + content-string hash; E-B16: claims **re-annotated for that body** |
| E-B16 recommended optional integrity | `claim.text ⊆ After` else Invalid |

So: formulas implement **GOLD_LEDGER_UNIVERSE**. Product-faithfulness honesty depends on binding/re-annotation making that universe correspond to what After actually asserted — which is **not** automatically true for unrebounded E-B12B × degraded After.

## Verdict

```text
CLAIM_UNIT_SEMANTICS = GOLD_LEDGER_UNIVERSE
```

Not `ACTUAL_AFTER_ASSERTION_REQUIRED` at formula layer.  
Not `AMBIGUOUS` for the formula question — evidence is explicit.
