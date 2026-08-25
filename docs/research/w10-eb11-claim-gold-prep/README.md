# W10 E-B11 Lane A — Claim Gold Preparation

> **Type:** preparation only  
> **Date:** 2026-08-24  
> **Does not:** LLM / LM Studio · formal generation · reserved formal result · fake annotations · auto-label · Lane B empty-gate implementation · `backend/app` edits

## Gate

```text
E_B_CLAIM_GOLD_PREP_READY = YES
E_B_CLAIM_GOLD_ANNOTATED = NO
E-B_FORMAL_READY = NO
```

## Deliverables

| Item | Path | Status |
|---|---|---|
| Formal gold **reserved** path | `backend/tests/fixtures/l4_critic/w10-eb-generation-claim-gold-v1.json` | **Absent** (intentional) |
| Annotation placeholder | `…/w10-eb-generation-claim-gold-v1.annotation-prep.json` | Present |
| Placeholder schema | `…/w10-eb-generation-claim-gold-v1.annotation-prep.schema.json` | Present |
| Prep module + E-B9a validator integration | `backend/tests/w10_eb11_claim_gold_prep.py` | Present |
| E-B9a gold schema (upstream) | `…/w10-eb-generation-claim-gold-v1.schema.json` | Unchanged |

## What this clears / does not clear

| Condition | Effect |
|---|---|
| E-B4 C3 annotated claim gold | **Still open** — placeholder ≠ annotated ledger |
| B3′ annotated gold missing | **Still BLOCKING** |
| `E-B_FORMAL_READY` | Remains **NO** |

## Lane B shared touchpoint

Both lanes use `backend/tests/fixtures/l4_critic/`. Lane A writes only `w10-eb-generation-claim-gold-*` prep artifacts. Do not edit `w10-eb-empty-gate-*` from Lane A.

## Verify

```powershell
cd backend
$env:JWT_SECRET='1362b8353e8306574369454872b0fb2a'
$env:DEEPSEEK_API_KEY=''
.\.venv\Scripts\python.exe -m pytest tests/test_w10_eb11_claim_gold_prep.py tests/test_w10_eb_generation_claim_gold_contract.py -q
```

## Stop

Prep complete for Lane A. No formal measurement authorization. No fake annotations.
