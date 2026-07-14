"""Agent tool scope — visible_kb_ids 求交与越权 deny（G3-1.1）。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable
from uuid import UUID

FORBIDDEN_KB_SUMMARY = "无权限"


class ToolDenialReason(str, Enum):
    forbidden_kb = "forbidden_kb"


@dataclass(frozen=True, slots=True)
class ToolDenial:
    """Tool 因 scope 拒绝执行（G3-E2 · 不抛 500）。"""

    reason: ToolDenialReason
    summary: str = FORBIDDEN_KB_SUMMARY
    forbidden_kb_ids: frozenset[UUID] = frozenset()


@dataclass(frozen=True, slots=True)
class KbScope:
    """经 scope 校验后的 kb 集合；None 表示搜全部 visible。"""

    kb_ids: frozenset[UUID] | None


@dataclass(frozen=True, slots=True)
class AgentToolScope:
    """注入每个 tool 的运行时上下文（JWT + workspace/department 解析结果）。"""

    visible_kb_ids: frozenset[UUID] | None = None
    default_kb_id: UUID | None = None

    def is_kb_visible(self, kb_id: UUID) -> bool:
        if self.visible_kb_ids is None:
            return True
        return kb_id in self.visible_kb_ids

    def require_kb_visible(self, kb_id: UUID) -> ToolDenial | None:
        """单库校验；不可见返回 ToolDenial。"""
        if self.is_kb_visible(kb_id):
            return None
        return ToolDenial(
            reason=ToolDenialReason.forbidden_kb,
            forbidden_kb_ids=frozenset({kb_id}),
        )

    def resolve_target_kb_for_edit(
        self, requested_kb_id: UUID | None
    ) -> UUID | ToolDenial:
        """编辑模式写 tool 的目标 kb 解析（G4-1.1）。

        - 库内 edit（default_kb_id 已设）：强制截断到路径 kb，不信模型传的 kb_id（G4-E19）。
        - /ask 模式（无 default）：校验 requested_kb_id ∈ visible，越权则 deny（G4-E10）。
        """
        if self.default_kb_id is not None:
            denial = self.require_kb_visible(self.default_kb_id)
            if denial is not None:
                return denial
            return self.default_kb_id
        if requested_kb_id is None:
            return ToolDenial(
                reason=ToolDenialReason.forbidden_kb,
                summary="缺少 kb_id",
            )
        denial = self.require_kb_visible(requested_kb_id)
        if denial is not None:
            return denial
        return requested_kb_id

    def _forbidden_in(self, requested: Iterable[UUID]) -> frozenset[UUID]:
        if self.visible_kb_ids is None:
            return frozenset()
        return frozenset(kb_id for kb_id in requested if kb_id not in self.visible_kb_ids)

    def resolve_kb_ids(
        self,
        requested: list[UUID] | None,
    ) -> KbScope | ToolDenial:
        """kb_ids 非空时与 visible_kb_ids 求交；含越权 id 则 deny（G3-E2）。"""
        if requested:
            forbidden = self._forbidden_in(requested)
            if forbidden:
                return ToolDenial(
                    reason=ToolDenialReason.forbidden_kb,
                    forbidden_kb_ids=forbidden,
                )
            return KbScope(kb_ids=frozenset(requested))

        if self.default_kb_id is not None:
            denial = self.require_kb_visible(self.default_kb_id)
            if denial is not None:
                return denial
            return KbScope(kb_ids=frozenset({self.default_kb_id}))

        if self.visible_kb_ids is not None and not self.visible_kb_ids:
            return KbScope(kb_ids=frozenset())

        return KbScope(kb_ids=None)
