# W10 E-B43 — Target-Scoped Formal Contract v2

> Versioned **successor** to E-B42.  
> Does **not** rewrite E-B21 / E-B24 / E-B42 historical conclusions.  
> Does **not** run Formal Measurement · write Formal result · call LLM · modify `backend/app`.

## Verdict

```text
READY_FOR_T1_FORMAL_MEASUREMENT
```

## Core repair

E-B42 found `FORMAL_TARGET_SCOPE_SEMANTICS=AMBIGUOUS`.  
E-B43 adds **`w10_eb43_formal_target_scope_v2`**: an explicit frozen `formal_measurement_scope` so Showcase Narrow may legally measure **T1 only**, with T2/T3 = `NOT_APPLICABLE` (E-B40 DEGRADED basis).

## Documents

| File | Content |
|---|---|
| [`01-eb42-provenance.md`](01-eb42-provenance.md) | E-B42 commit stamp |
| [`02-historical-vs-v2.md`](02-historical-vs-v2.md) | Semantic separation |
| [`03-formal-measurement-scope.md`](03-formal-measurement-scope.md) | Frozen T1-only scope |
| [`04-na-readiness-writer.md`](04-na-readiness-writer.md) | N/A · TARGET_FORMAL_READY · writer |
| [`05-gate-matrix.md`](05-gate-matrix.md) | Entry gates |
| [`06-eb43-verdict.md`](06-eb43-verdict.md) | Stamp + stop |

## Hard locks this window

```text
DO NOT run Formal T1 scorer / Formal Measurement
DO NOT write reserved Formal result
DO NOT start FORMAL_OBSERVATION
DO NOT flip historical E-B_FORMAL_READY
DO NOT claim T1 = 100% (measurement not executed)
DO NOT expand scope to A4 / S2 denom / Local Model / Research Benchmark
DO NOT modify backend/app or E-B21/E-B22 modules
```
