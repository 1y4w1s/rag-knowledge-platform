"""V1.0 PR gate: experimental / risky feature defaults must stay OFF.

Locks the cut-line safe-default surface (RELEASE BLOCKING #5).
Does not exercise experimental runtimes — only Settings defaults.
"""

from __future__ import annotations

from app.core.config import settings


def test_v1_0_experimental_surfaces_default_off() -> None:
    assert settings.rag_critic_enabled is False
    assert settings.self_verify_enabled is False
    assert settings.hyde_enabled is False
    assert settings.rerank_enabled is False
    assert settings.rerank_policy == "off"
    assert settings.query_rewrite_enabled is False
    assert settings.query_rewrite_policy == "off"
    assert settings.graph_recall_enabled is False

    assert settings.agent_l3_next_action_enabled is False
    assert settings.agent_l3_dynamic_tools_enabled is False
    assert settings.agent_l3_evidence_state_enabled is False
    assert settings.agent_l3_trajectory_trace_enabled is False
    assert settings.agent_l3_critic_retrieval_enabled is False

    assert settings.agent_l4_fact_decomposition_enabled is False
    assert settings.agent_l4_evidence_matcher_enabled is False
    assert settings.agent_l4_contradiction_enabled is False
    assert settings.agent_l4_stop_policy_enabled is False
    assert settings.agent_l4_reflection_recovery_enabled is False
    assert settings.agent_l4_local_model_profile_enabled is False
    assert settings.agent_l4_multimodal_evidence_enabled is False
    assert settings.agent_l4_tool_preferred_hint_enabled is False
    assert settings.agent_l4_task_satisfied_hint_enabled is False
    assert settings.agent_l4_tool_contrastive_selection_enabled is False

    # Memory infra may be ON; productized utilization / exposure labels stay OFF.
    assert settings.agent_memory_exposure_trace_enabled is False
    assert settings.agent_memory_relevance_label_enabled is False
