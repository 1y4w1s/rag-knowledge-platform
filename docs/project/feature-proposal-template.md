# Feature Proposal Template

> Fill one copy per Feature Proposal.  
> Authority: [Feature Admission Constitution](feature-admission-constitution.md) · states: [feature-lifecycle.md](feature-lifecycle.md).

**Rules**

- If `OBSERVED_PROBLEM = TBD` → `STATUS` must be `IDEA` or `BACKLOG` only.
- Do not enter `HYPOTHESIS` / `EXPERIMENT` without problem, baseline, and falsifiable metrics.
- `IMPLEMENTED` in code is not a RESULT.

---

## Proposal

```yaml
FEATURE: ""
STATUS: IDEA | BACKLOG | HYPOTHESIS | EXPERIMENT | VALIDATED | OPTIONAL | DEFAULT_CANDIDATE | DEFAULT | REJECTED | DEPRECATED | REMOVED
TARGET_RELEASE: ""   # e.g. v1.0 | v1.1 | post-v1.0 | SEPARATE_PROJECT_CANDIDATE | FUTURE_EXPERIMENT

OBSERVED_PROBLEM: ""   # or TBD (forces STATUS ≤ BACKLOG)
PROBLEM_EVIDENCE: ""   # benchmark / regression / user / ops / known-limitation ID

BASELINE: ""
  # What the system does/scores/costs WITHOUT this feature

HYPOTHESIS: ""
TARGET_METRICS: []
EXPECTED_GAIN: ""
ALLOWED_COST: ""
  # latency / compute / memory / token / index / ops / maintenance / failure surface / safety

SAFETY_CONSTRAINTS: ""
IMPLEMENTATION_SCOPE: ""
  # files/flags only; no silent default promotion

PROMOTE_IF: ""
REJECT_IF: ""
REMOVE_IF: ""

EVALUATION_PLAN: ""
ROLLBACK_PLAN: ""
MAINTENANCE_OWNER: ""

RESULT: ""   # fill after experiment; may be REJECTED / NO_GO / NOT_APPLICABLE / BLOCKED / NO_MEASURED_GAIN
FINAL_DECISION: ""   # PROMOTE | REJECT | HOLD | DEPRECATE | REMOVE | BACKLOG
```

---

## Markdown form（same fields）

### FEATURE

_Name_

### STATUS

_Lifecycle state_

### TARGET_RELEASE

_e.g. v1.0 / post-v1.0 / FUTURE_EXPERIMENT / SEPARATE_PROJECT_CANDIDATE_

### OBSERVED_PROBLEM

_What breaks or hurts today? Use `TBD` only if STATUS ≤ BACKLOG._

### PROBLEM_EVIDENCE

_Link to benchmark failure, regression, user report, production/research limitation, or known-limitation ID._

### BASELINE

_Current behavior and numbers without the feature._

### HYPOTHESIS

_Falsifiable claim._

### TARGET_METRICS

_Named metrics._

### EXPECTED_GAIN

_Magnitude._

### ALLOWED_COST

_Hard ceilings (latency, spend, complexity, safety = 0 regression, etc.)._

### SAFETY_CONSTRAINTS

_What must not regress._

### IMPLEMENTATION_SCOPE

_Code/flags/docs in scope; defaults stay off unless already DEFAULT._

### PROMOTE_IF

_Exact promotion gate._

### REJECT_IF

_Exact rejection gate._

### REMOVE_IF

_When to tear out after ship/optional._

### EVALUATION_PLAN

_How measured; evaluator independence (Constitution Art. 8)._

### ROLLBACK_PLAN

_How to disable / revert._

### MAINTENANCE_OWNER

_Who carries the long-term cost._

### RESULT

_Post-experiment honest outcome._

### FINAL_DECISION

_PROMOTE / REJECT / HOLD / DEPRECATE / REMOVE / BACKLOG_

---

## Minimal IDEA stub（allowed）

```yaml
FEATURE: "Economic Agent"
STATUS: BACKLOG
TARGET_RELEASE: SEPARATE_PROJECT_CANDIDATE   # or FUTURE_EXPERIMENT
OBSERVED_PROBLEM: TBD
PROBLEM_EVIDENCE: TBD
BASELINE: TBD
HYPOTHESIS: TBD
# All experiment fields remain TBD until OBSERVED_PROBLEM is real.
FINAL_DECISION: HOLD
```

Do not treat the stub above as Suoyin v1.0 / v1.1 automatic scope.
