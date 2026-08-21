"""L4 W7+/W10 flag 占位接线（仅引用、默认 False；满足 config-wiring）。

contradiction 由 ``reflection_recovery`` 真实引用；本文件只占 local GLM / multimodal。
禁止在此抬默认或接 runtime。
"""

from __future__ import annotations

from app.core.config import settings

# AST 扫描认 settings.<field>；合入期必须恒为 False。
assert settings.agent_l4_local_model_profile_enabled is False
assert settings.agent_l4_multimodal_evidence_enabled is False
