"""L4 W6+ flag 占位接线（P0 仅引用、默认 False；满足 config-wiring）。

不实现 contradiction / local GLM / multimodal；禁止在此抬默认或接 runtime。
"""

from __future__ import annotations

from app.core.config import settings

# AST 扫描认 settings.<field>；P0 合入期三枚必须恒为 False。
assert settings.agent_l4_contradiction_enabled is False
assert settings.agent_l4_local_model_profile_enabled is False
assert settings.agent_l4_multimodal_evidence_enabled is False
