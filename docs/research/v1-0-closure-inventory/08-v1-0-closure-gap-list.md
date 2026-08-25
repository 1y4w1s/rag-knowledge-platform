# 08 — V1.0 Closure Gap List + Scope-Creep Guard

> Only gaps that could block an honest v1.0 release narrative.  
> Research wishlist ≠ blocker.

Severity: `BLOCKER` · `REQUIRED_CLOSURE` · `OPTIONAL_POLISH` · `NOT_V1_0`

---

## Gap list

| ID | Gap | Severity | Why |
|----|-----|----------|-----|
| G1 | README V1 status **STALE**（W9→W10 Multimodal next；old SHA；post-W10 reality） | **REQUIRED_CLOSURE** | Public claim drift after W10_CLOSED |
| G2 | Memory labeled **Stable** without utilization caveat in Core Capabilities table | **REQUIRED_CLOSURE** | Overclaim vs C2 NO_GO |
| G3 | Canonical **demo path GAP**（stub script + missing root BROWSER acceptance） | **REQUIRED_CLOSURE** | Release/interview readiness |
| G4 | Install path **PARTIAL**（compose OK；script/overlay drift；live smoke not re-verified） | **REQUIRED_CLOSURE** | New-user path honesty |
| G5 | L4 roadmap checkboxes **UNDERSTATED/STALE** vs PARTIAL code | **OPTIONAL_POLISH** | Confuses triage；not runtime break |
| G6 | Agent Golden / ADV / W9 **not PR-CI blocking** | **OPTIONAL_POLISH** or policy decision | OK if v1.0 claims don't require them as gates |
| G7 | Rate-limit test flakiness residual（historical） | **OPTIONAL_POLISH** | Not proven currently red this window |
| G8 | “BM25” naming vs PG FTS | **OPTIONAL_POLISH** | Honesty polish |
| G9 | LLM-Wiki / Graph product / Evolver / Memory v2 / Multi-Agent / MCP / Multimodal agent / Local default chat / Research Benchmark / E-B45 | **NOT_V1_0** | Explicitly out；not hard deps of current honest claims |
| G10 | W10 Formal T1 100% misread as Agent/RAG accuracy | **REQUIRED_CLOSURE**（messaging） | Must remain scoped in all public text |

### Exact closure blockers（candidate）

```text
EXACT_CLOSURE_BLOCKERS =
  G1 README V1/status freshness
  G2 Memory claim honesty
  G3 Canonical demo / BROWSER pointer
  G4 Install path consistency + documented known limits
  G10 Formal claim scope discipline in public docs
```

No evidence in this window that **CI is currently red** on master — CI redness not listed as proven BLOCKER（would become BLOCKER if observed red）.

---

## Scope-Creep Guard

```text
NEW_CAPABILITY_REQUIRED_FOR_V1_0 = NO
```

### Why NO

If YES were claimed, the required question is:

> “不新增这个能力，哪个**已有** v1.0 claim 无法成立？”

Candidate temptations and why they fail the test:

| Temptation | Existing claim that would break without it? | Verdict |
|------------|-----------------------------------------------|---------|
| Ship L3 by default | None — README already Experimental off | NO |
| Ship Critic | None — default off | NO |
| Multimodal agent | None — still STUB；stale roadmap not a claim to preserve | NO |
| Local model default | None — README Roadmap | NO |
| Graph / MCP / Multi-Agent | Explicitly “What Suoyin Is Not” | NO |
| New Formal / E-B45 | W10 closed；would invent new claim surface | NO |
| Memory utilization v2 | Would **create** new claim；current honest claim is exposure-only | NO |

**Closure needs documentation / demo / claim alignment — not new capability code.**

---

## Allowed next windows（after human review）

1. Feature Triage 2026 using this inventory  
2. README / progress claim freeze（docs only）  
3. Demo path / BROWSER pointer repair（docs or thin script）  
4. Install overlay consistency（docs/scripts only）  

**Forbidden auto-start:** capability implementation · scorer · Local Model experiment · E-B45 / W11.
