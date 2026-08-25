# 04 — Formal integrity audit

## Oracle isolation

Probe: corrupt E-B41 candidate summary to `0/11` and `11/11` in memory.

```text
FORMAL_ORACLE_LEAK_RISK = NO
```

Formal aggregate unchanged — computation reads raw records only.

## Raw-input integrity

```text
RAW_INPUT_MUTATED = NO
MANIFEST_DRIFT    = NO
LLM_CALLED        = NO
```

## Canonical uniqueness

```text
CANONICAL_FORMAL_T1_RESULT_COUNT = 1
```

Active canonical: `docs/research/w10-eb44-t1-formal-measurement/formal-t1-result.json`

No collision with:
- `w10-eb2-generation-observation-result.json`
- E-B41 candidate JSON mislabeled as Formal
- Reserved E-B2 Formal observation artifacts
- Fake T2/T3 companion scores

## Measurement validity

`FORMAL_T1_MEASUREMENT_VALID = YES` when all hold:

- Formal scope v2 frozen
- Authorization valid
- Raw input immutable
- Identity binding exact
- Same-trajectory binding valid
- Candidate oracle unused
- C12 excluded before denominator
- Subset predicate recomputed from raw
- T2/T3 N/A semantics correct
- Canonical schema valid
- No LLM/API
- No input mutation
