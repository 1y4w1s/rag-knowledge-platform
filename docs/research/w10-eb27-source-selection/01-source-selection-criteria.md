# 01 — Source selection criteria

> Defines **how** to choose a Narrow Formal Product After acquisition source.
> Criteria + weights only. **No option selected in this file.**

## 1. Purpose

Turn E-B26’s four-option analysis into a repeatable selection rule for the
**first** Narrow Formal Product After path — still design-level, still not
owner approval.

```text
Selection (design) ≠ Authorization (owner stamp)
Selection (design) ≠ Acquisition execution
Selection (design) ≠ Formal Observation
```

## 2. Mandatory criteria

| Criterion | Question | Pass shape for Narrow Formal |
|---|---|---|
| **formal eligibility** | Could this source ever satisfy E-B24 four-condition contract **under current Narrow freeze** (A4 excluded · S2-as-T1–T3 excluded · BP-A · C01–C11)? | Must be **in-scope potential**; out-of-Narrow sources fail regardless of quality |
| **source identity** | Can a named `after_source` / provenance id be declared without synthetic relabel? | Named product-path identity possible; not E-B18 author-owned |
| **reproducibility** | Can C01–C11 be re-run to identical or declared-bounded bodies? | Prefer deterministic / pinned no-LLM modes for first Narrow |
| **capture feasibility** | Can capture be done with existing harness / path without inventing a new product surface in this wave? | Prefer extant E-B15 substrate over greenfield |
| **cost** | Ops, keys, time, infra for one Narrow suite | Prefer low for first observation |
| **maintenance burden** | Ongoing pin cost (model files, API drift, env freeze, deploy pins) | Prefer low pin surface |
| **hash binding compatibility** | Can BP-A `observed_content_hash` / rebound gold bind cleanly after capture? | Content-string codec bindable; no fake hash copy |
| **owner authorization difficulty** | How hard is an honest owner stamp (identity · mode · model · base_sha · run)? | Prefer stampable-with-existing-evidence over “approve absent future path” |

Contract reference (E-B24 / E-B25): formal After needs **all** of  
`source identity ∧ hash binding (BP-A) ∧ capture mode ∧ no synthetic contamination`  
**plus** owner stamp. E-B25: **no** current source is approved.

## 3. Weight order (frozen for E-B27)

Strict priority (higher beats lower when conflicts arise):

```text
1. formal eligibility          (Narrow-in-scope potential)
2. reproducibility             (suite replay honesty)
3. source identity / provenance
4. hash binding compatibility
5. capture feasibility
6. owner authorization difficulty   (lower difficulty preferred)
7. maintenance burden               (lower preferred)
8. cost                             (lower preferred)
```

Mnemonic (user-aligned):

```text
formal eligibility > reproducibility > provenance > cost
```

`hash binding`, `capture feasibility`, `owner authorization difficulty`, and
`maintenance burden` sit between provenance and cost as secondary but
mandatory scored axes (see matrix in `02`).

### 3.1 Hard vetoes (weight-independent)

| Veto | Effect |
|---|---|
| Contradicts Narrow freeze (A4 live LLM / S2-as-T1–T3 After) | **Disqualify** for PRIMARY Narrow candidate |
| Requires synthetic / E-B18 body as Product After | **Disqualify** |
| Source absent (cannot stamp what does not exist) | **Cannot be approved now**; may remain “future” only |
| Forces `llm_called` honesty conflict under declared mode | **Disqualify** until mode/scope revised |

## 4. Scoring guide (ordinal)

| Band | Meaning |
|---|---|
| **HIGH** | Strong fit for Narrow first Product After |
| **MED** | Usable with pins / extra work / scope caveats |
| **LOW** | Weak fit |
| **OUT** | Hard veto / out of Narrow / absent |

Bands are qualitative. This window does **not** invent numeric scores that
could be mistaken for formal rates.

## 5. Explicit non-goals (this file)

```text
DO NOT pick Option A/B/C/D here.
DO NOT issue owner stamp.
DO NOT flip AFTER_SOURCE_APPROVED.
DO NOT start acquisition execution.
```

## 6. Stamp

```text
SOURCE_SELECTION_CRITERIA_DEFINED = YES
OPTION_SELECTED                   = (see 03 · not this file)
AFTER_SOURCE_APPROVED             = NO
E-B_FORMAL_READY                  = NO
```
