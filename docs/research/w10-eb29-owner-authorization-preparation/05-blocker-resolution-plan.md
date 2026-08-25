# 05 — Blocker resolution plan

> Ordered plan to clear blockers that keep owner authorization unissued and
> acquisition entry closed.  
> **Plan only** — clears nothing in this window.

## 1. Current blocker map

| ID | Blocker | Blocks | Status (E-B29) |
|---|---|---|---|
| B-AUTH-1 | Owner stamp not issued (`authorization_status=WITHHELD`) | `SOURCE_APPROVED` / `AFTER_SOURCE_APPROVED` | **OPEN** |
| B-AUTH-2 | Concrete `source_identity` / `after_source` string not frozen | Honest APPROVED stamp | **OPEN** |
| B-AUTH-3 | `capture_mode` not frozen (template only) | Stamp APPROVED · acquisition entry | **OPEN** |
| B-AUTH-4 | `model_backend_identity` + `run_identity` + `base_sha` not frozen | Stamp match · acquisition entry | **OPEN** |
| B-AUTH-5 | After-source identity checklist incomplete (02) | Identity complete | **OPEN** |
| B-ACQ-1 | `ACQUISITION_EXECUTION_READY=NO` (depends on B-AUTH-*) | Acquisition execution | **OPEN** (correct) |
| B-FORMAL-* | Formal entry residuals (B2′ · AG-5 · S2 · A4 · reserved write) | Formal Observation | **OUT OF SCOPE** for acquisition auth prep |

Inherited non-approval (must stay until human clears B-AUTH-*):

```text
SOURCE_APPROVED             = NO
AFTER_SOURCE_APPROVED       = NO
ACQUISITION_EXECUTION_READY = NO
E-B_FORMAL_READY            = NO
```

Already cleared as **design** inputs (not approvals):

```text
PRIMARY_CANDIDATE_SOURCE         = A
SOURCE_MODEL_SEPARATION_DESIGNED = YES
OWNER_AUTHORIZATION_DESIGNED     = YES   (this window)
```

## 2. Recommended clearance order

```text
Step 1  Fill capture-mode freeze template (03) → CAPTURE_MODE_FROZEN=YES
        + freeze model_backend_identity / run_identity pattern / base_sha plan

Step 2  Complete after-source identity checklist (02)
        → concrete source_identity chosen

Step 3  Human owner issues stamp (01) with authorization_status=APPROVED
        → SOURCE_APPROVED=YES · AFTER_SOURCE_APPROVED=YES
        (still NOT formal ready)

Step 4  Re-evaluate acquisition entry gate (04)
        → only then may ACQUISITION_EXECUTION_READY flip to YES

Step 5  (Separate window) Acquisition execution
        → capture records · formal_measurement=false
        → still NOT formal observation

Step 6  (Later) Gold rebound + formal entry clearance (B-FORMAL-*)
        → dedicated unlock for E-B_FORMAL_READY / observation
```

```text
DO NOT skip to Step 5/6 from Step 1–3 incomplete.
DO NOT clear B-FORMAL-* inside an acquisition authorization window.
DO NOT treat Step 3 as completed observation.
```

## 3. Per-blocker resolution recipe

### B-AUTH-1 — Stamp issuance

| | |
|---|---|
| Owner | Human project owner |
| Input | Filled 01 fields + frozen 03 + complete 02 |
| Output | Stamp artifact · `authorization_status=APPROVED` |
| Does not | Flip `E-B_FORMAL_READY` · start acquisition · run LLM |

### B-AUTH-2 / B-AUTH-5 — Source identity

| | |
|---|---|
| Owner | Owner + research freeze window |
| Input | Named `after_source` · path id A · suite/cases policy |
| Output | Identity checklist all checked |
| Does not | Generate After to invent a name |

### B-AUTH-3 — Capture mode freeze

| | |
|---|---|
| Owner | Human freeze window using `03` |
| Input | Exact mode id · Narrow exclusions held |
| Output | `CAPTURE_MODE_FROZEN=YES` |
| Does not | Call A4 / LM Studio / API |

### B-AUTH-4 — Run / sha / model freeze

| | |
|---|---|
| Owner | Same freeze window as mode (recommended) |
| Input | Exact strings matching future capture records |
| Output | Fields ready for stamp match |
| Does not | Pretend a past smoke run is the formal suite |

### B-ACQ-1 — Acquisition entry

| | |
|---|---|
| Owner | Gate re-eval after B-AUTH-1…5 clear |
| Input | `04` conjunction |
| Output | `ACQUISITION_EXECUTION_READY=YES` **or** remain NO |
| Does not | Auto-open because designs exist |

### B-FORMAL-* — Formal residuals

| | |
|---|---|
| Owner | Formal authorization / observation windows |
| Note | Tracked in E-B23/E-B24; **not** cleared by E-B29 |
| Rule | Approval of After source ≠ formal unlock |

## 4. Stop conditions / vetoes

Any of the following **re-opens** blockers even after a premature YES:

```text
- stamp.auto_derived = true
- capture_mode silent smoke→formal
- synthetic / E-B18 body used as Product After
- Development Backend run claimed as Formal After
- Narrow scope violated (A4 / S2-as-T1–T3) without scope revision
- stamp fields mismatch acquisition records
- attempt to flip E-B_FORMAL_READY inside acquisition window
```

## 5. Explicit non-goals (this window)

```text
DO NOT clear B-AUTH-1…5.
DO NOT issue stamp.
DO NOT freeze capture mode.
DO NOT execute acquisition.
DO NOT clear B2′ / AG-5 / S2 / A4.
DO NOT write formal / reserved result.
DO NOT modify backend/app.
```

## 6. Stamp

```text
BLOCKER_RESOLUTION_PLAN_DESIGNED = YES
BLOCKERS_CLEARED_THIS_WINDOW      = NONE
OWNER_AUTHORIZATION_DESIGNED      = YES
OWNER_AUTHORIZATION_ISSUED        = NO
SOURCE_APPROVED                   = NO
AFTER_SOURCE_APPROVED             = NO
ACQUISITION_EXECUTION_READY       = NO
E-B_FORMAL_READY                  = NO
FORMAL_OBSERVATION                = NOT_STARTED

NEXT = Step 1–3 (mode+identity freeze → human stamp)
       — still not acquisition; still not formal
```
