# Feature Lifecycle

> Status machine for features under the [Feature Admission Constitution](feature-admission-constitution.md).  
> Proposal fields → [`feature-proposal-template.md`](feature-proposal-template.md).

```text
EXPERIMENT        ≠  PRODUCT FEATURE
IMPLEMENTED       ≠  VALIDATED
OPTIONAL          ≠  DEFAULT
```

---

## State machine

```text
IDEA
  ↓
BACKLOG
  ↓
HYPOTHESIS
  ↓
EXPERIMENT
  ↓
┌─────────────┐
REJECTED   VALIDATED
              ↓
           OPTIONAL
              ↓
       DEFAULT_CANDIDATE
              ↓
           DEFAULT
```

Additional terminal / exit states:

```text
DEPRECATED
REMOVED
```

---

## State definitions

### IDEA

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | A named idea exists; may lack observed problem |
| EXIT_CRITERIA | Promoted to BACKLOG with a tracked owner, **or** discarded |
| ALLOWED_ACTION | Note / discuss / park; **no** architecture merge as product default |
| REQUIRED_EVIDENCE | None beyond a one-line description |

`OBSERVED_PROBLEM` may be `TBD` only while STATUS ≤ BACKLOG.

---

### BACKLOG

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | Idea accepted for tracking; **not** claiming it must ship |
| EXIT_CRITERIA | Problem + baseline draft ready → HYPOTHESIS; or closed as out-of-scope |
| ALLOWED_ACTION | Prioritize, defer, mark NOT_V1_0 / FUTURE_EXPERIMENT / SEPARATE_PROJECT_CANDIDATE |
| REQUIRED_EVIDENCE | At least a problem sketch **or** explicit “TBD problem → stay BACKLOG” |

If `OBSERVED_PROBLEM = TBD`:

```text
STATUS must remain ≤ BACKLOG
must not enter HYPOTHESIS / EXPERIMENT
```

---

### HYPOTHESIS

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | OBSERVED_PROBLEM filled · BASELINE named · HYPOTHESIS / metrics / costs drafted · PROMOTE_IF / REJECT_IF / REMOVE_IF present |
| EXIT_CRITERIA | Experiment plan approved → EXPERIMENT; or REJECTED / returned to BACKLOG |
| ALLOWED_ACTION | Design measurement; **no** production default change |
| REQUIRED_EVIDENCE | Proposal filled through EVALUATION_PLAN (see template) |

---

### EXPERIMENT

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | Baseline exists · falsifiable hypothesis · evaluation plan · flags default-off unless explicitly scoped lab path |
| EXIT_CRITERIA | Measured result → VALIDATED **or** REJECTED / NO_GO / NO_MEASURED_GAIN / BLOCKED |
| ALLOWED_ACTION | Implement behind flags; run eval; record RESULT; **must not** silently become DEFAULT |
| REQUIRED_EVIDENCE | Metrics vs baseline · cost observation · safety check |

```text
EXPERIMENT ≠ PRODUCT FEATURE
```

Code may exist in-tree while STATUS = EXPERIMENT. That alone does not validate.

---

### REJECTED

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | REJECT_IF met, or NO_MEASURED_GAIN / NO_GO recorded honestly |
| EXIT_CRITERIA | Terminal unless a **new** observed problem + new hypothesis reopen as BACKLOG |
| ALLOWED_ACTION | Keep evidence; disable flags; document why |
| REQUIRED_EVIDENCE | Written RESULT · FINAL_DECISION = REJECTED |

---

### VALIDATED

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | PROMOTE_IF met against baseline within ALLOWED_COST · safety constraints held |
| EXIT_CRITERIA | Ship as OPTIONAL, or park as VALIDATED-not-shipped |
| ALLOWED_ACTION | Offer as opt-in / documented optional path |
| REQUIRED_EVIDENCE | Measured gain · cost within budget · no unsafe regression |

```text
VALIDATED ≠ DEFAULT
```

---

### OPTIONAL

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | VALIDATED and intentionally available but not product default |
| EXIT_CRITERIA | Evidence + safe-default rationale → DEFAULT_CANDIDATE; or REMOVE_IF / DEPRECATED |
| ALLOWED_ACTION | Flag-gated enablement · docs · support |
| REQUIRED_EVIDENCE | Validation record retained |

```text
OPTIONAL ≠ DEFAULT
```

---

### DEFAULT_CANDIDATE

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | OPTIONAL (or VALIDATED) + measured evidence + explicit safe-default rationale |
| EXIT_CRITERIA | Governance approval → DEFAULT; or demote to OPTIONAL / REJECTED path |
| ALLOWED_ACTION | Dual-track regression planning; **not** silent default flip |
| REQUIRED_EVIDENCE | Constitution Article 9 package |

---

### DEFAULT

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | DEFAULT_CANDIDATE approved; CI / safety gates green as required by cut-line |
| EXIT_CRITERIA | REMOVE_IF / regression → DEPRECATED → REMOVED |
| ALLOWED_ACTION | Product default path |
| REQUIRED_EVIDENCE | Promotion record · rollback plan still valid |

```text
DEFAULT ≠ PERMANENT
```

---

### DEPRECATED

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | REMOVE_IF approaching, or better replacement VALIDATED |
| EXIT_CRITERIA | REMOVED, or restored only via new HYPOTHESIS (not nostalgia) |
| ALLOWED_ACTION | Warn · migrate · keep off by default |
| REQUIRED_EVIDENCE | Deprecation notice · owner |

---

### REMOVED

| Field | Definition |
|-------|------------|
| ENTRY_CRITERIA | Code/docs/config surface retired per REMOVE_IF |
| EXIT_CRITERIA | Terminal |
| ALLOWED_ACTION | Archive evidence; no silent re-enable |
| REQUIRED_EVIDENCE | Removal note · residual risk (if any) |

---

## Mapping to implementation labels

C0 inventory labels (`IMPLEMENTED` / `PARTIAL` / `EXPERIMENTAL` / `STUB`) describe **code presence**.  
Lifecycle STATUS describes **governance right to exist as product architecture**.

| Code label | Typical lifecycle ceiling without new evidence |
|------------|--------------------------------------------------|
| STUB | ≤ BACKLOG / IDEA |
| EXPERIMENTAL / PARTIAL | ≤ EXPERIMENT or OPTIONAL (flag-off) |
| IMPLEMENTED without measured gain | ≠ VALIDATED; remain EXPERIMENT / OPTIONAL |
| IMPLEMENTED + beats baseline | may reach VALIDATED → OPTIONAL → … |

---

## Example backlog markers（not activated）

| Item | Suggested marker |
|------|------------------|
| Economic Agent | `SEPARATE_PROJECT_CANDIDATE` or `FUTURE_EXPERIMENT` — **not** auto-scope for Suoyin v1.0 / v1.1 |
| Evolver | `FUTURE_EXPERIMENT` — Constitution Article 8 + future Evolver rule only |
| LLM-Wiki / Multi-Agent / MCP expansion / … | See [`v1-0-release-cut-line.md`](v1-0-release-cut-line.md) NOT_V1_0 |
