# 03 — E-B38 C01–C11 response-mode classification

Source: E-B38 acquisition records · classifier: `w10_eb40_response_mode_gate_v1`.
No NLP. No preset expectation enforcement beyond deterministic rules.

| case_id | response_mode | classification_signal | llm_called | capture_submode |
|---|---|---|---|---|
| C01-fully-supported-exact | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C02-supported-paraphrase-low-lexical | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C03-one-unsupported-among-supported | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C04-valid-citation-wrong-evidence | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C05-known-conflict-overcertain | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C06-required-fact-missing | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C07-correct-insufficiency-refusal | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C08-nonassertive-preface-supported-fact | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C09-supported-plus-unverifiable | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C10-supported-multiclaim-multicitation | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |
| C11-citation-format-only-defect | DEGRADED | capture_path_submode=product_stream_degraded | false | product_stream_degraded |

```text
degraded_count = 11
degraded_rate  = 11/11
ANSWER_count   = 0
REFUSAL_count  = 0
```

All-DEGRADED is a **legal** outcome. Not rewritten to ANSWER to obtain a T2/T3 denominator.
