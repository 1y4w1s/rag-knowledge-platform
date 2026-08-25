# 02 — Implementation vs Evidence Matrix

> Rule: **code exists ≠ capability effective**.  
> Columns: IMPLEMENTED? · TESTED? · EVALUATED? · FORMALLY_PROVEN? · DEFAULT_ENABLED?

Legend for FORMALLY_PROVEN:

| Value | Meaning |
|-------|---------|
| YES | Product CI / frozen Formal claim covers it |
| SCOPED | Proven only on named frozen scope |
| LIMITED | Offline/unit/eval exists; not Formal product claim |
| NO | Not proven / blocked / N/A |
| N/A | Not applicable |

---

## Matrix

| # | Capability | IMPLEMENTED? | TESTED? | EVALUATED? | FORMALLY_PROVEN? | DEFAULT_ENABLED? |
|---|------------|:---:|:---:|:---:|:---:|:---:|
| 1 | Document ingestion | YES | YES | LIMITED | LIMITED（via golden ingest） | YES |
| 2 | Parsing / chunking | YES | YES | LIMITED | LIMITED | YES |
| 3 | Embedding | YES | YES | YES（CI real-emb jobs） | LIMITED | YES |
| 4 | Vector retrieval | YES | YES | YES | SCOPED（Hit@3 gate） | YES |
| 5 | Lexical FTS | YES | YES | YES | SCOPED（Hit@3） | YES |
| 6 | Hybrid RRF | YES | YES | YES | SCOPED（Hit@3 11/11） | YES |
| 7 | Reranking | YES | YES | YES（ablation；can hurt） | NO（not default） | **NO** |
| 8 | Query rewrite / HyDE / decomp | PARTIAL | YES | LIMITED | NO | **NO**（composite strategy yes） |
| 9 | Legacy Agent | YES | YES | YES（Agent Golden） | LIMITED（not PR CI） | YES |
| 10 | L3 Observation Agent | YES | YES | YES（trajectory/ADV/MEMORY panels） | SCOPED / LIMITED | **NO** |
| 11 | Planner（all） | YES | YES | LIMITED | LIMITED | Legacy YES · L3 NO |
| 12 | Tool resolver / execution | YES | YES | YES | SCOPED（tool selection **no gain**） | YES（dynamic unlock NO） |
| 13 | EvidenceState | YES | YES | LIMITED | NO（fact-level incomplete） | Structure YES · gate **NO** |
| 14 | Evidence sufficiency gate | YES | YES | LIMITED | NO | L3 gate **NO** |
| 15 | FactGoal / ledger structs | PARTIAL | YES | LIMITED | NO | **NO** |
| 16 | Critic | YES | YES | PARTIAL（W9） | NO | **NO** |
| 17 | Failure recovery / fallback | YES | YES | LIMITED | LIMITED | Legacy YES · L4 NO |
| 18 | Citation / provenance | YES | YES | YES | **SCOPED YES**（W10 T1 citation-scope Formal） | YES |
| 19 | Refusal / degraded | YES | YES | YES | SCOPED（golden reject + W10 response_mode） | YES |
| 20 | Retrieval eval | YES | YES | YES | YES（CI gate） | YES（CI） |
| 21 | Agent Golden | YES | YES | YES | LIMITED（not CI-blocking） | N/A（suite） |
| 22 | Adversarial eval | YES | YES | YES | SCOPED（2/4 · 10/20） | N/A · rollout NO |
| 23 | W9 Critic evaluation | PARTIAL | YES | PARTIAL | NO | N/A · rollout NO |
| 24 | W10 Formal infra | YES | YES | YES | **SCOPED YES**（T1 only） | N/A（closed） |
| 25 | Local-model product | STUB | LIMITED | NO | NO | **NO** |
| 26 | LM Studio eval | YES（harness） | YES（opt-in） | YES（local panels） | SCOPED | **NO**（product） |
| 27 | Multimodal agent | STUB | NO | NO | NO | **NO** |
| 28 | Memory | YES | YES | YES | SCOPED（exposure 10/10；util **NO**） | **YES**（master） |
| 29 | Tracing / observability | PARTIAL | YES | LIMITED | LIMITED | Audit YES · deep traces NO |
| 30 | Permissions / governance | YES | YES | LIMITED | LIMITED（A-layer security） | YES |
| 31 | CI | YES | YES | N/A | YES（self） | YES |
| 32 | Install / deployment | PARTIAL | LIMITED | NO（this window） | NO | N/A |
| 33 | Demo / UI | PARTIAL | LIMITED（FE unit） | NO | NO | UI YES · demo path NO |
| 34 | Documentation | PARTIAL | LIMITED | N/A | SCOPED（W10 claim freeze） | N/A |

---

## Highlighted mismatches（存在但证据不足 / 易误读）

### A. Implemented + default ON, but **not** “proven intelligent”

| Item | Risk |
|------|------|
| **Memory** (`agent_memory_enabled=True`) | Exposure proven；semantic utilization / causal benefit **NOT_DEMONSTRATED** · C2 NO_GO |
| **Legacy Agent tools** | Execution works；local tool-selection gain **NO** on frozen GQ-131 |

### B. Implemented + default OFF — code ≠ shipped behavior

| Item | Note |
|------|------|
| L3 Agent / Evidence gate / Critic / rerank / HyDE / rewrite / graph / L4 | Safe defaults；do not market as default product behavior |

### C. Evaluated but **not** Formally product-proven

| Item | Note |
|------|------|
| Agent Golden 168 | Exists；**not** PR CI gate |
| ADV 2/4 | Characterized · not universal adversarial claim |
| W9 Critic | Partial / historically blocked protocol |
| W10 Formal T1 100% | **Only** citation-scope on Showcase T1-only Formal |

### D. README / checklist drift vs code

| Claim surface | Reality |
|---------------|---------|
| README L4 FactGoal unchecked | Structures + flag-gated code **exist**（PARTIAL） |
| README “下一主线 W9→W10 Multimodal” | W10 **CLOSED**；Multimodal agent still STUB |
| “BM25” wording | PG FTS |

---

## Worked example: L3 Agent

```text
IMPLEMENTED      = YES
TESTED           = YES
EVALUATED        = YES（trajectory / ADV / MEMORY panels）
FORMALLY_PROVEN  = limited / scoped（not Formal product accuracy；not default）
DEFAULT_ENABLED  = NO
```

## Worked example: Citation（product + Formal）

```text
IMPLEMENTED      = YES
TESTED           = YES
EVALUATED        = YES
FORMALLY_PROVEN  = SCOPED YES（W10 T1 citation-scope Formal only）
DEFAULT_ENABLED  = YES（answered turns）
```

Do **not** expand Formal T1 into “answer quality = 100%”.
