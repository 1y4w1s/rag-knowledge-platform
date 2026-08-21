"""L3-W6 Trajectory Eval（评测层 · 不替换 test_agent_golden）。

分层：
- deterministic planner contract（state → decide_next 契约）
- mock-LLM trajectory（脚本/假 LLM 逐步决策）
- 真实模型抽样：本包预留，本窗不接

评分原则：acceptable actions / outcome，禁止唯一 exact path。
"""

from tests.agent_trajectory.schemas import (
    AcceptableAction,
    TrajectoryCase,
    TrajectoryScore,
)
from tests.agent_trajectory.scorer import score_trajectory, summarize_scores

__all__ = [
    "AcceptableAction",
    "TrajectoryCase",
    "TrajectoryScore",
    "score_trajectory",
    "summarize_scores",
]
