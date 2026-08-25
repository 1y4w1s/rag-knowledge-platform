# Feature Admission Constitution

> Canonical governance contract for Suoyin / 索隐.  
> **One constitution only.** Sibling artifacts: [`feature-lifecycle.md`](feature-lifecycle.md) · [`feature-proposal-template.md`](feature-proposal-template.md) · [`v1-0-release-cut-line.md`](v1-0-release-cut-line.md).

```text
FEATURE_CONSTITUTION_FROZEN = YES
```

This document answers: **by what right may a new feature enter Suoyin architecture?**  
It is not a research window, not an implementation plan, and not a freeze protocol forest.

---

## Preamble

```text
A feature has no right to become architecture until it beats the baseline.
Implementation is not evidence of value.
```

Status ladders used elsewhere in the repo:

```text
IMPLEMENTED  ≠  VALIDATED
VALIDATED    ≠  DEFAULT
DEFAULT      ≠  PERMANENT
```

---

## Article 1 — Problem Before Feature

Any new Feature must bind to an **OBSERVED_PROBLEM**.

Allowed sources (at least one):

- benchmark failure
- regression
- user pain
- production or research limitation
- maintenance failure
- explicit capability gap already admitted in known limitations / cut-line

Forbidden entry reasons alone:

- a new paper
- community trend
- competitor has it
- framework supports it
- “looks more Agentic”
- “the code is already written”

If there is no observed problem:

```text
STATUS = BACKLOG
```

---

## Article 2 — Baseline Before Implementation

Before any Feature Experiment starts, a clear **BASELINE** must exist.

The experiment must answer:

> Without this Feature, what does the current system do / score / cost?

Without baseline:

```text
must not enter EXPERIMENT
```

---

## Article 3 — Falsifiable Hypothesis

Every Feature Experiment must declare:

| Field | Meaning |
|-------|---------|
| HYPOTHESIS | What will improve, and why |
| TARGET_METRIC | Named measurable |
| EXPECTED_GAIN | Magnitude (e.g. multi-hop accuracy +5pp) |
| ALLOWED_COST | Bounds (e.g. latency ≤ +25%, unsafe regression = 0) |

The hypothesis must be **falsifiable**. An experiment that cannot produce REJECTED / NO_MEASURED_GAIN is not an experiment.

---

## Article 4 — Implementation Is Not Evidence

Frozen:

```text
IMPLEMENTED  ≠  VALIDATED
VALIDATED    ≠  DEFAULT
DEFAULT      ≠  PERMANENT
```

Core rule (unchanged semantics):

> A feature has no right to become architecture until it beats the baseline.  
> Implementation is not evidence of value.

---

## Article 5 — Explicit Promotion / Rejection

Every Feature Proposal must pre-declare:

| Gate | Purpose |
|------|---------|
| PROMOTE_IF | When it may advance toward OPTIONAL / DEFAULT_CANDIDATE |
| REJECT_IF | When the experiment fails and must stop |
| REMOVE_IF | When a shipped optional/default must be torn out |

A proposal that only describes how to add a feature, with no rejection / removal criteria, is incomplete.

---

## Article 6 — Cost Is Part of Capability

Feature evaluation must not look at accuracy alone.

According to feature type, consider at least:

- latency
- compute
- memory
- token / API cost
- index cost
- operational complexity
- maintenance burden
- failure surface
- safety regression

Forbidden pattern:

```text
accuracy +0.5%  traded for  maintenance ×5  →  called an improvement
```

---

## Article 7 — Release Cut Line Has Priority

Once the current milestone Cut Line is frozen (see [`v1-0-release-cut-line.md`](v1-0-release-cut-line.md)):

A new Feature may enter the milestone **only if**:

> Without this feature, an already-approved Definition of Done cannot be satisfied.

If no concrete DoD can be cited:

```text
→ BACKLOG
```

Forbidden reopen triggers:

- new model release
- new paper
- new framework
- new idea

---

## Article 8 — Evaluator Independence

Any adaptive / auto-optimizing / future Evolver-class capability **must not be its own sole judge**.

A Feature must not modify, to raise its own score:

- Golden Dataset
- Success Criteria
- Safety Constraints
- Promotion Policy

If evaluators themselves need versioned change, that is a **separate governance event**, not part of the Feature experiment under evaluation.

---

## Article 9 — Default-Off for Unproven Complexity

For capabilities that are:

- EXPERIMENTAL
- PARTIAL
- not causally validated

Default must **not** auto-promote to default-on merely because implementation exists.

To enter **DEFAULT_CANDIDATE** requires:

```text
measured evidence
+
safe default rationale
```

---

## Article 10 — Honest Failure Is a Valid Result

Formal experiment conclusions may be:

- REJECTED
- NO_GO
- NOT_APPLICABLE
- BLOCKED
- NO_MEASURED_GAIN

Forbidden cosmetics:

- fake PASS
- zero-denominator “perfect”
- hidden exclusion
- retrospective metric change
- deleting failed cases to look complete

---

## Future rule — Autonomous / Evolver systems（principle only）

Do not implement Evolver here. Minimum future-compatible boundary:

**MAY modify** (within authorized experiment scope):

- agent implementation
- prompts
- retrieval strategies
- memory strategies
- workflow
- tools
- planner / critic configuration
- bounded parameters

**MAY NOT autonomously redefine**:

- mission
- evaluator
- success criteria
- safety constraints
- budget ceiling
- authorization boundary
- promotion policy

…unless a separate human / governance approval event explicitly authorizes that change.

---

## Related

- Lifecycle states → [`feature-lifecycle.md`](feature-lifecycle.md)
- Proposal form → [`feature-proposal-template.md`](feature-proposal-template.md)
- v1.0 freeze → [`v1-0-release-cut-line.md`](v1-0-release-cut-line.md)
- Capability inventory (C0) → [`../research/v1-0-closure-inventory/`](../research/v1-0-closure-inventory/)
