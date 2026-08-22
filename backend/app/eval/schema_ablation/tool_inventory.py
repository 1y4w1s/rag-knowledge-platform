"""Frozen tool inventory snapshot for W8 P7 ablation (from product contract)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.services.agent.tool_resolver import INDEPENDENT_TOOL_SPECS
from app.services.agent.tools.registry import ALL_AGENT_TOOL_NAMES

TOOL_INVENTORY_SOURCE = "app.services.agent.tool_resolver.INDEPENDENT_TOOL_SPECS"


@dataclass(frozen=True, slots=True)
class ToolInventorySnapshot:
    allowed_tool_names: frozenset[str]
    all_agent_tool_names: frozenset[str]
    out_of_scope_examples: frozenset[str]
    inventory_source: str
    inventory_sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed_tool_names": sorted(self.allowed_tool_names),
            "all_agent_tool_names": sorted(self.all_agent_tool_names),
            "out_of_scope_examples": sorted(self.out_of_scope_examples),
            "tool_inventory_source": self.inventory_source,
            "inventory_sha256": self.inventory_sha256,
        }


def _inventory_hash(names: frozenset[str]) -> str:
    payload = json.dumps(sorted(names), separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def frozen_tool_inventory(*, external_tools_enabled: bool = False) -> ToolInventorySnapshot:
    """Independent read-only tools exposed at planner step 0 (W8 P5 benchmark scope).

    W8 P5 Golden capability runs with default product flags; external web_search
    is excluded when ``external_tools_enabled`` is False (benchmark hygiene).
    Dependent tools (get_chunk_excerpt, grep_in_document, compare_chunks) require
    state unlock and are **out of scope** for the default exposure set.
    """
    specs = list(INDEPENDENT_TOOL_SPECS)
    if not external_tools_enabled:
        specs = [s for s in specs if s.name != "web_search"]
    allowed = frozenset(s.name for s in specs)
    dependent = frozenset({"get_chunk_excerpt", "grep_in_document", "compare_chunks"})
    return ToolInventorySnapshot(
        allowed_tool_names=allowed,
        all_agent_tool_names=ALL_AGENT_TOOL_NAMES,
        out_of_scope_examples=dependent,
        inventory_source=TOOL_INVENTORY_SOURCE,
        inventory_sha256=_inventory_hash(allowed),
    )
