"""W8 P1 / Gate C adversarial evidence integrity case set (deterministic).

Ground truth is frozen here. Do NOT rewrite expected_* after seeing matcher output.
Strings use Unicode escapes so this file stays ASCII-safe on all platforms.
"""

from __future__ import annotations

from app.eval.evidence_integrity.schema import EvalRelation, IntegrityCase
from app.eval.local_agent_trajectory.cases import (
    EXCERPT_2025,
    EXCERPT_POLICY,
    EXCERPT_UNRELATED,
)

# W8 P0 F2 FactGoals (historical; do not change W8 case definitions).
F2_FACT_X1 = "\u627e\u52302028\u4f4f\u5bbf\u6807\u51c6"
F2_FACT_X2 = "\u627e\u52302029\u4f4f\u5bbf\u6807\u51c6"
F2_EVIDENCE = EXCERPT_UNRELATED


def gate_c_cases() -> tuple[IntegrityCase, ...]:
    """~30 deterministic pairs covering A-L + F2 reproduction."""
    S = EvalRelation.support
    P = EvalRelation.partial
    C = EvalRelation.contradict
    IRR = EvalRelation.irrelevant

    T = {
        "a1_fact": "\u4f4f\u5bbf\u6807\u51c6\u4e3a\u6bcf\u4eba\u6bcf\u5929500\u5143\u3002",
        "a1_ev": "\u4f4f\u5bbf\u8d39\u6807\u51c6\u4e3a\u6bcf\u4eba\u6bcf\u5929500\u5143\u3002",
        "a2_fact": "\u627e\u52302025\u4f4f\u5bbf\u6807\u51c6",
        "b_fact": "\u4f4f\u5bbf\u6807\u51c6\u4e3a\u591a\u5c11\uff1f",
        "b1_ev": "\u4f4f\u5bbf\u6807\u51c6\u6309\u7167\u6709\u5173\u89c4\u5b9a\u6267\u884c\u3002",
        "b2_ev": "\u672c\u7ae0\u8ba8\u8bba\u4f4f\u5bbf\u6807\u51c6\u7ba1\u7406\u3002",
        "b3_ev": (
            "\u672c\u529e\u6cd5\u89c4\u5b9a\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6"
            "\u7531\u76f8\u5173\u90e8\u95e8\u53e6\u884c\u5236\u5b9a\u3002"
        ),
        "c1_fact": "\u6807\u51c6\u4e3a500\u5143\u3002",
        "c1_ev": "\u6807\u51c6\u4e3a300\u5143\u3002",
        "c2_ev": "\u4f4f\u5bbf\u6807\u51c6\u4e3a\u6bcf\u4eba\u6bcf\u5929800\u5143\u3002",
        "d1_fact": "\u53ef\u4ee5\u62a5\u9500\u4f4f\u5bbf\u8d39\u7528\u3002",
        "d1_ev": "\u4e0d\u53ef\u4ee5\u62a5\u9500\u4f4f\u5bbf\u8d39\u7528\u3002",
        "d2_fact": "\u5141\u8bb8\u4f7f\u7528\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6\u3002",
        "d2_ev": "\u7981\u6b62\u4f7f\u7528\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6\u3002",
        "e1_fact": "\u5317\u4eac\u5730\u533a\u4f4f\u5bbf\u6807\u51c6\u662f\u591a\u5c11\uff1f",
        "e1_ev": "\u4e0a\u6d77\u5730\u533a\u4f4f\u5bbf\u6807\u51c6\u4e3a600\u5143\u3002",
        "e2_fact": "\u627e\u5230\u7814\u53d1\u90e8\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6",
        "e2_ev": (
            "\u5e02\u573a\u90e8\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6"
            "\u4e3a\u6bcf\u4eba\u6bcf\u5929450\u5143\u3002"
        ),
        "f1_fact": "2026\u5e74\u6807\u51c6\u662f\u591a\u5c11\uff1f",
        "f1_ev": "2024\u5e74\u6807\u51c6\u4e3a500\u5143\u3002",
        "g1_fact": "\u6559\u6388\u7ea7\u4eba\u5458\u4f4f\u5bbf\u6807\u51c6\u662f\u591a\u5c11\uff1f",
        "g1_ev": "\u666e\u901a\u5de5\u4f5c\u4eba\u5458\u4f4f\u5bbf\u6807\u51c6\u4e3a500\u5143\u3002",
        "g2_fact": "\u56fd\u9645\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6\u662f\u591a\u5c11\uff1f",
        "g2_ev": (
            "\u56fd\u5185\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6"
            "\u4e3a\u6bcf\u4eba\u6bcf\u5929500\u5143\u3002"
        ),
        "h1_fact": "\u6bd4\u8f83A\u4e0eB\u7684\u4f4f\u5bbf\u6807\u51c6\u3002",
        "h1_ev": "A\u7684\u4f4f\u5bbf\u6807\u51c6\u4e3a\u6bcf\u4eba\u6bcf\u5929500\u5143\u3002",
        "h2_fact": (
            "\u786e\u8ba42025\u4e0e2026\u4f4f\u5bbf\u6807\u51c6"
            "\u5206\u522b\u662f\u591a\u5c11\u3002"
        ),
        "i1_ev": "\u6bcf\u665a\u4f4f\u5bbf\u8865\u8d34\u4e0a\u9650\u662f\u4e94\u767e\u5757\u94b1\u3002",
        "i2_fact": "\u5dee\u65c5\u53ef\u62a5\u9500\u9152\u5e97\u8d39\u7528\u3002",
        "i2_ev": (
            "\u51fa\u5dee\u671f\u95f4\u7684\u65c5\u9986\u5f00\u9500"
            "\u53ef\u4ee5\u7eb3\u5165\u62a5\u9500\u8303\u56f4\u3002"
        ),
        "j_short": "\u4f1a\u8bae\u5ba4\u9884\u5b9a\u6d41\u7a0b\u4e0e\u4f4f\u5bbf\u6807\u51c6\u65e0\u5173\u3002",
        "k1_wrong": "\u4f4f\u5bbf\u8d39\u6807\u51c6\u4e3a\u6bcf\u4eba\u6bcf\u5929300\u5143\u3002",
        "l2_ev": "\u4eca\u65e5\u98df\u5802\u83dc\u5355\uff1a\u7ea2\u70e7\u8089\u3001\u9752\u83dc\u3001\u4f8b\u6c64\u3002",
        "b4_fact": "\u5dee\u65c5\u4f4f\u5bbf\u6807\u51c6\u662f\u591a\u5c11\uff1f",
        "c3_fact": "\u627e\u52302025\u4f4f\u5bbf\u6807\u51c6\u4e3a\u6bcf\u4eba\u6bcf\u5929500\u5143",
        "c3_ev": (
            "\u5dee\u65c5\u624b\u518c\u786e\u8ba4\uff1a\u627e\u52302025\u4f4f\u5bbf\u6807\u51c6"
            "\u8c03\u6574\u4e3a\u6bcf\u4eba\u6bcf\u5929600\u5143\uff0c"
            "\u8be5\u6807\u51c6\u9002\u7528\u5728\u804c\u5458\u5de5\u3002"
        ),
    }

    cases: list[IntegrityCase] = [
        IntegrityCase(
            case_id="A1",
            category="exact_support",
            fact_goal=T["a1_fact"],
            evidence_texts=(T["a1_ev"],),
            expected_relation=S,
            reason="near-paraphrase with same numeric value",
        ),
        IntegrityCase(
            case_id="A2",
            category="exact_support",
            fact_goal=T["a2_fact"],
            evidence_texts=(EXCERPT_2025,),
            expected_relation=S,
            reason="W8-style supporting excerpt for 2025",
        ),
        IntegrityCase(
            case_id="B1",
            category="keyword_overlap",
            fact_goal=T["b_fact"],
            evidence_texts=(T["b1_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="shared terms; no concrete standard value",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="B2",
            category="keyword_overlap",
            fact_goal=T["b_fact"],
            evidence_texts=(T["b2_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="topic mention only",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="B3",
            category="keyword_overlap",
            fact_goal=F2_FACT_X1,
            evidence_texts=(T["b3_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="RELATED but does not answer the fact",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="C1",
            category="wrong_value",
            fact_goal=T["c1_fact"],
            evidence_texts=(T["c1_ev"],),
            expected_relation=C,
            acceptable_relations=(IRR,),
            reason="numeric mismatch must not support",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="C2",
            category="wrong_value",
            fact_goal=T["a1_fact"],
            evidence_texts=(T["c2_ev"],),
            expected_relation=C,
            acceptable_relations=(IRR,),
            reason="same template, different amount",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="D1",
            category="negation",
            fact_goal=T["d1_fact"],
            evidence_texts=(T["d1_ev"],),
            expected_relation=C,
            acceptable_relations=(IRR,),
            reason="explicit negation of the claim",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="D2",
            category="negation",
            fact_goal=T["d2_fact"],
            evidence_texts=(T["d2_ev"],),
            expected_relation=C,
            acceptable_relations=(IRR,),
            reason="forbid vs allow",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="E1",
            category="entity_mismatch",
            fact_goal=T["e1_fact"],
            evidence_texts=(T["e1_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="different city entity",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="E2",
            category="entity_mismatch",
            fact_goal=T["e2_fact"],
            evidence_texts=(T["e2_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="different department",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="F_temp1",
            category="temporal_mismatch",
            fact_goal=T["f1_fact"],
            evidence_texts=(T["f1_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="year mismatch",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="F_temp2",
            category="temporal_mismatch",
            fact_goal=F2_FACT_X1,
            evidence_texts=(EXCERPT_2025,),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="2025 evidence for 2028 fact",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="G1",
            category="scope_mismatch",
            fact_goal=T["g1_fact"],
            evidence_texts=(T["g1_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="role/scope mismatch",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="G2",
            category="scope_mismatch",
            fact_goal=T["g2_fact"],
            evidence_texts=(T["g2_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="domestic vs international scope",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="H1",
            category="partial_support",
            fact_goal=T["h1_fact"],
            evidence_texts=(T["h1_ev"],),
            expected_relation=P,
            acceptable_relations=(IRR,),
            reason="only one side of compare; product has partial relation",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="H2",
            category="partial_support",
            fact_goal=T["h2_fact"],
            evidence_texts=(EXCERPT_2025,),
            expected_relation=P,
            acceptable_relations=(IRR,),
            reason="covers 2025 only of a dual-year goal",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="I1",
            category="paraphrase",
            fact_goal=T["a1_fact"],
            evidence_texts=(T["i1_ev"],),
            expected_relation=S,
            reason="semantic paraphrase; lexical overlap may fail -> FN/boundary",
        ),
        IntegrityCase(
            case_id="I2",
            category="paraphrase",
            fact_goal=T["i2_fact"],
            evidence_texts=(T["i2_ev"],),
            expected_relation=S,
            reason="low surface overlap, clear equivalence",
        ),
        IntegrityCase(
            case_id="J1",
            category="distractor",
            fact_goal=T["a1_fact"],
            evidence_texts=(T["b2_ev"], T["b1_ev"], T["a1_ev"], T["j_short"]),
            expected_relation=S,
            reason="true support present among high-overlap distractors",
            notes="multi-evidence; FP if distractor alone would cover",
        ),
        IntegrityCase(
            case_id="J2",
            category="distractor",
            fact_goal=F2_FACT_X1,
            evidence_texts=(T["b2_ev"], T["b1_ev"], EXCERPT_UNRELATED),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="all distractors; none state 2028 standard",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="K1",
            category="conflict",
            fact_goal=T["a1_fact"],
            evidence_texts=(T["a1_ev"], T["k1_wrong"]),
            expected_relation=C,
            reason="conflicting values; observe supports/contradicts without resolution",
            notes="characterization only; no conflict resolver",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="K2",
            category="conflict",
            fact_goal=T["d1_fact"],
            evidence_texts=(T["d1_fact"], T["d1_ev"]),
            expected_relation=C,
            reason="affirm + negate pair; contradicts must win over supports",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="L1",
            category="no_evidence",
            fact_goal=T["a1_fact"],
            evidence_texts=(EXCERPT_POLICY,),
            expected_relation=IRR,
            reason="completely unrelated excerpt",
        ),
        IntegrityCase(
            case_id="L2",
            category="no_evidence",
            fact_goal=F2_FACT_X1,
            evidence_texts=(T["l2_ev"],),
            expected_relation=IRR,
            reason="food menu; no travel policy terms",
        ),
        IntegrityCase(
            case_id="F2_W8_REPRO",
            category="f2_repro",
            fact_goal=F2_FACT_X1,
            evidence_texts=(F2_EVIDENCE,),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason=(
                "W8 P0 F2: empty-tool mode returns EXCERPT_UNRELATED which still "
                "contains lodging-standard tokens; must NOT full-cover required FactGoal"
            ),
            secondary_fact_goal=F2_FACT_X2,
            secondary_expected=IRR,
            is_f2_repro=True,
            check_stop_propagation=True,
            notes="Preserve W8 P0 history; do not rewrite W8 fixtures",
        ),
        IntegrityCase(
            case_id="F2_W8_REPRO_X2",
            category="f2_repro",
            fact_goal=F2_FACT_X2,
            evidence_texts=(F2_EVIDENCE,),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="Same F2 evidence against X2 FactGoal alone",
            is_f2_repro=True,
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="B4",
            category="keyword_overlap",
            fact_goal=T["b4_fact"],
            evidence_texts=(T["b3_ev"],),
            expected_relation=IRR,
            acceptable_relations=(P,),
            reason="canonical RELATED!=SUPPORTED example from Gate C brief",
            check_stop_propagation=True,
        ),
        IntegrityCase(
            case_id="C3",
            category="wrong_value",
            fact_goal=T["c3_fact"],
            evidence_texts=(T["c3_ev"],),
            expected_relation=C,
            acceptable_relations=(IRR,),
            reason="same year phrase, wrong amount",
            check_stop_propagation=True,
        ),
    ]
    return tuple(cases)


CASE_BY_ID = {c.case_id: c for c in gate_c_cases()}
