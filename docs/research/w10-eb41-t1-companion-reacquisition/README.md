# W10 E-B41 — T1 Companion Reacquisition on Frozen Baseline

> Companion only: persist `gen_plan.gated_chunks` + same-trajectory final citations  
> so T1 can judge `final citations ⊆ authorized gated scope`.  
> **Not** Formal T1 · **Not** T2/T3 · **Not** Formal Observation.

## Inherited state

```text
frozen evaluation base_sha = 3ce0e75f06d35aecaaccd245dd3a234b1c6f79a6
parent_acquisition_run     = w10_showcase_narrow_eb38_20260825T085526Z
E-B38 ACQUISITION_VALID    = YES
E-B40 RESPONSE_MODE_GATE   = YES · DEGRADED C01–C11
T2/T3 EB38 applicability   = NOT_APPLICABLE
E-B_FORMAL_READY           = NO
```

## This window

```text
T1_COMPANION_REACQUISITION_EXECUTED = YES
T1_COMPANION_CAPTURE_VALID          = YES
T1_REAL_AFTER_INPUT_READY           = YES
T1_CANDIDATE (not Formal)           = 11/11 COMPLIANT
WAITING_FOR_T1_FORMAL_READINESS_REVIEW
```

## Artifacts

| File | Purpose |
|---|---|
| `01-frozen-worktree-preflight.md` | Detached worktree HEAD + clean |
| `02-scope-signal-feasibility.md` | `gated_chunks` externally capturable |
| `03-t1-companion-run-manifest.md` | Run identity + suite counts |
| `04-t1-companion-binding.md` | Same-trajectory binding |
| `05-t1-candidate-evaluation.md` | Candidate subset results |
| `06-eb41-verdict.md` | Gate matrix + stop |
| `records/C01.json` … `C11.json` | Machine-readable companion records |
| `records/C12.INELIGIBLE.json` | C12 excluded |
| `companion-run-manifest.json` | Suite manifest |
| `t1-candidate-evaluation.json` | Candidate summary (not Formal) |
| `scripts/run_t1_companion_reacquisition.py` | External orchestration |

## Tests / modules

- `backend/tests/w10_eb41_t1_companion.py`
- `backend/tests/test_w10_eb41_t1_companion_reacquisition.py`

```text
pytest backend/tests/test_w10_eb41_t1_companion_reacquisition.py -q
```
