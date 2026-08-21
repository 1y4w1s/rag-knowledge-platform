"""手册 §6.3 推荐 case 的 rubric 目录（acceptable-set）。"""

from __future__ import annotations

from app.services.agent.types import AgentActionKind

from tests.agent_trajectory.schemas import AcceptableAction, TrajectoryCase

_SEARCH = AcceptableAction(
    action=AgentActionKind.tool,
    tool_name="semantic_search",
)
_FINISH = AcceptableAction(action=AgentActionKind.finish)
_CLARIFY = AcceptableAction(action=AgentActionKind.clarify)
_REFUSE = AcceptableAction(action=AgentActionKind.refuse)
_EXCERPT = AcceptableAction(
    action=AgentActionKind.tool,
    tool_name="get_chunk_excerpt",
)


STOP_NOW = TrajectoryCase(
    case_id="L3T-stop-now",
    category="stop_now",
    description="证据已足够时应 finish；继续检索算冗余",
    acceptable_by_step={
        0: (_SEARCH,),
        1: (_FINISH,),
    },
    acceptable_terminals=(AgentActionKind.finish,),
    max_steps_soft=1,
)

MISSING_FACT = TrajectoryCase(
    case_id="L3T-missing-fact",
    category="missing_fact",
    description="首轮证据不足必须再检，不得早停 finish",
    acceptable_by_step={
        0: (_SEARCH,),
        1: (_SEARCH,),  # 再检（含 gate 改写的 retrieve）
        2: (_FINISH, _SEARCH),  # 允许多轮后再停
    },
    acceptable_terminals=(AgentActionKind.finish, AgentActionKind.refuse),
    max_steps_soft=3,
)

DEPENDENT_ID = TrajectoryCase(
    case_id="L3T-dependent-id",
    category="dependent_id",
    description="须先检索拿到 chunk_id，再 get_chunk_excerpt",
    acceptable_by_step={
        0: (_SEARCH,),
        1: (_EXCERPT, _SEARCH),  # excerpt 优先；再搜也可接受
        2: (_FINISH, _EXCERPT),
    },
    acceptable_terminals=(AgentActionKind.finish,),
    max_steps_soft=3,
)

CLARIFY = TrajectoryCase(
    case_id="L3T-clarify",
    category="clarify",
    description="歧义指代须显式 clarify",
    acceptable_by_step={
        0: (_CLARIFY, _SEARCH),  # 可先搜再澄清，但终态须 clarify
    },
    acceptable_terminals=(AgentActionKind.clarify,),
)

BUDGET_CAP = TrajectoryCase(
    case_id="L3T-budget-cap",
    category="budget_cap",
    description="预算尽且证据不足 → refuse/partial，不得死循环 tool",
    acceptable_by_step={
        0: (_SEARCH,),
        1: (_SEARCH, _REFUSE),
        2: (_REFUSE,),
    },
    acceptable_terminals=(AgentActionKind.refuse,),
    max_steps_soft=3,
)

LOW_RECALL = TrajectoryCase(
    case_id="L3T-low-recall",
    category="low_recall",
    description="首检空/低召回后允许 rewrite 再检",
    acceptable_by_step={
        0: (_SEARCH,),
        1: (_SEARCH,),  # rewrite / second search
        2: (_FINISH, _REFUSE, _SEARCH),
    },
    acceptable_terminals=(AgentActionKind.finish, AgentActionKind.refuse),
    max_steps_soft=3,
)

ALL_CASES: tuple[TrajectoryCase, ...] = (
    STOP_NOW,
    MISSING_FACT,
    DEPENDENT_ID,
    CLARIFY,
    BUDGET_CAP,
    LOW_RECALL,
)
