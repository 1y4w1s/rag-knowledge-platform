# 08 — Scorer applicability gaps & empty/perfect pathology

## Empty / perfect pathology check

### What frozen protocol already prevents

E-B19 / E-B8: `|asserted_claims| == 0` → T2/T3 `NOT_APPLICABLE` with explicit reason  
`asserted_claims empty → NOT_APPLICABLE (not 0.0/1.0 PASS)`.

So **empty ledger denom** does **not** silently become perfect.

### What remains dangerous for degraded After

| Scenario | Risk |
|---|---|
| Force-score unrebounded E-B12B gold against degraded After | Scorer treats gold rows as asserted units (`GOLD_LEDGER_UNIVERSE`) even when After only dumps fragments → **fictional assertions** scored as `OBSERVED_SLOT` |
| Hash-only rebound without re-annotating claims for degraded body | Same pathology: labels/denom from old gold, body is unavailable boilerplate |
| Misread `NOT_APPLICABLE` / skipped cases as “quality good” | Reporting honesty failure |

```text
NO_ASSERTION / DEGRADED RESPONSE must not silently become T2=perfect or T3=perfect
```

Frozen protocol defines empty-ledger N/A, but **does not** define a complete degraded-After → no-assertion routing into that N/A path when gold still has 17 claims.

```text
SCORER_APPLICABILITY_GAP = YES
```

This is a **measurement-protocol gap**, not a model failure.

## Other protocol gaps surfaced by E-B38 real After

1. **BP taxonomy gap:** `product_stream_degraded` is neither completed BP-A nor BP-C under frozen defs → **UNCLASSIFIED**.  
2. **Assertion semantics gap:** substring presence ≠ assertion; no frozen discriminator.  
3. **Hash codec divergence:** E-B38 BP-A `observed_content_hash` = raw UTF-8; E-B17 gate digest from `after_content` = canonical-JSON. Rebound must pick one codec explicitly.  
4. **Pool identity gap:** gold `E1`/`E2` ≠ product UUID `chunk_id`s.  
5. **T1 scope material gap:** final citations captured; plan/gated scope not persisted on acquisition records.  
6. **Forbidden shortcut:** E-B18 author-owned claim-text embedding must not be used as substitute real After.

## Honest stop

```text
BLOCKED_PENDING_PROTOCOL_REPAIR = YES
```

Do not enlarge Formal denominator. Do not reclassify degraded as ordinary answer. Do not add fuzzy/NLI in this window.
