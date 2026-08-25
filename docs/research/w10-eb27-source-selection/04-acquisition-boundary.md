# 04 — Acquisition boundary

> Freezes what a **future** Product After acquisition execution window may and
> may not do.  
> This window does **not** execute acquisition.

## 1. Core separation

```text
Acquisition execution  ≠  Formal Observation
Capture records        ≠  Formal scores / reserved result
Source candidate (E-B27) ≠ Owner-approved After (stamp)
```

Even after acquisition eventually runs (later window), formal gates stay
locked unless a **dedicated** formal unlock window flips them.

## 2. Allowed (future acquisition execution)

Once E-B26 checklist is honestly green **and** owner stamp issued for the
selected source (still future work):

| Allowed action | Note |
|---|---|
| **Capture Product After** | C01–C11 Formal After Capture Records per E-B26 `02` schema |
| **Generate capture records** | Fields: content · citations · llm_called · capture_mode · hashes · identities |
| **Calculate source hashes** | BP-A content-string codec from observed `content` (`source_hash` / `observed_content_hash`) |
| Record C12 as INELIGIBLE | Not claim After denom |
| Keep `formal_measurement=false` on acquisition artifacts | Acquisition ≠ formal result |
| Recompute hashes for integrity | Reject synthetic substitution |

Assumes PRIMARY candidate **A** unless a later **planning** window revises
selection (not silent mid-execution swap).

## 3. Forbidden (acquisition execution and all prior windows)

| Forbidden | Why |
|---|---|
| **Formal score** (T1/T2/T3 rates as formal) | Formal Observation only |
| **Reserved result** / `w10-eb2-generation-observation-result.json` formal write | Reserved write gate |
| **`E-B_FORMAL_READY` flip** | Dedicated unlock only |
| `MAY_ENTER_FORMAL_OBSERVATION_WINDOW=YES` | Full formal entry checklist |
| Treat capture as formal denom approval without stamp match | Honesty / E-B24 |
| Call LM Studio / API / open A4 under Narrow without scope revision | Narrow freeze |
| Promote E-B18 synthetic bodies into Product After | Contamination |
| Modify `backend/app` as “capture shortcut” without plan | Out of research window class |
| Auto-derive owner stamp from pytest green | Owner agency required |

## 4. Gate freeze during / after acquisition (until formal unlock)

```text
E-B_FORMAL_READY                    = NO
MAY_ENTER_FORMAL_OBSERVATION_WINDOW = NO
FORMAL_OBSERVATION                  = NOT_STARTED
RESERVED_RESULT                     = ABSENT
AFTER_SOURCE_APPROVED               = YES only if stamp issued (separate)
```

```text
Acquisition complete ⇏ Formal Observation ready
Gold rebound BOUND    ⇏ E-B_FORMAL_READY
```

## 5. Relation to E-B27 candidate

```text
E-B27 selects PRIMARY_CANDIDATE_SOURCE = A (design)
Future acquisition (if authorized) captures under that stamped source
Future formal observation (if unlocked) scores from authorized After
```

This file does not authorize either future step.

## 6. Stamp

```text
ACQUISITION_BOUNDARY_FROZEN     = YES
ACQUISITION_EXECUTION_READY     = NO
ACQUISITION_EXECUTED            = NO
E-B_FORMAL_READY                = NO
FORMAL_OBSERVATION              = NOT_STARTED
```
