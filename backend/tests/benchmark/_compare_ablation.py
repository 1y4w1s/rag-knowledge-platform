import json
off = json.load(open("/tmp/baseline-hyde-off.json"))
on = json.load(open("/tmp/baseline-hyde-on.json"))
print(f"HYDE OFF: {off['summary']['faithfulness_avg']:.4f}  ({off['total_questions']} questions)")
print(f"HYDE ON:  {on['summary']['faithfulness_avg']:.4f}  ({on['total_questions']} questions)")
print()
print(f"{'Diff':>8} {'Question':<40} {'OFF':>6} {'ON':>6}")
print("-" * 66)
for i, (qo, qn) in enumerate(zip(off["questions"], on["questions"])):
    diff = qn["faithfulness"] - qo["faithfulness"]
    marker = "+" if diff > 0 else ""
    print(f"{marker}{diff:+.2f}  {qo['question'][:38]:<38} {qo['faithfulness']:.3f} {qn['faithfulness']:.3f}")
