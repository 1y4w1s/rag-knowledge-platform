# Claim gold — per-case annotation checklist

> Use **before submitting each case**.  
> This checklist does not create gold files or run models.

Copy for every `case_id`:

```text
case_id: ____________________

Before submitting this case:
[ ] claim is atomic
[ ] label is evidence-based
[ ] supported has evidence ids
[ ] no oracle fields
[ ] no answer-derived judgement
```

## Checklist detail

| Item | Pass condition |
|---|---|
| **claim is atomic** | Each `claim_text` is one independently decidable fact; multi-fact sentences were split (see guide §4). |
| **label is evidence-based** | `supported` / `unsupported` / `unverifiable` decided only from gated `evidence_chunks`, not from confidence, citation markers, or world knowledge guesses. |
| **supported has evidence ids** | If `label = supported`, `supporting_evidence_ids` is non-empty and every id is in this case’s pool. |
| **no oracle fields** | Payload has no Critic / oracle keys (`expected_action`, `oracle_cases`, `critic_*`, `llm_judge`, `auto_label`, `label_source`, …). |
| **no answer-derived judgement** | Label was not taken from fixture/model `answer`; answer was not treated as truth. Claim text may come from content under review, but judgement is vs evidence. |

## Optional notes row

```text
annotation_notes (optional): ____________________
```

## Gate reminder

```text
E_B12A_ANNOTATION_GUIDE_READY = YES
E_B_FORMAL_READY = NO
```

Do not flip formal ready after checklist completion.
