"""Agent 确定性 Planner（thorough 多步 · edit FAQ · 非 LLM ReAct）。

D1：ThoroughReadPlanner 多步只读（search → excerpt → 复杂题二次 search）。
D2：精准内按题型控深度——简单 1 步、标准 2 步、复杂 ≤3；不自动升档。
"""

from __future__ import annotations

import json
import re
from enum import Enum
from collections.abc import Collection
from typing import Any
from uuid import UUID

from app.services.agent.tool_resolver import (
    INDEPENDENT_TOOL_SPECS,
    ToolResolver,
    ToolSpec,
)
from app.services.agent.tools.registry import (
    ALL_AGENT_TOOL_NAMES,
    AgentToolName,
    READ_ONLY_TOOL_NAMES,
    ReadOnlyToolName,
)
from app.services.agent.tools.search_documents import (
    SearchDocumentsItem,
    SearchDocumentsOutput,
)
from app.services.agent.tools.semantic_search import (
    SemanticSearchHit,
    SemanticSearchOutput,
)
from app.services.agent.types import (
    AgentActionKind,
    AgentDecision,
    AgentState,
    AgentStepRecord,
    DecisionParseResult,
    ObservationSummary,
    ParseResult,
    ToolCallPlan,
    ToolFailure,
    ValidatedDecision,
    ValidatedPlan,
)
from app.services.rag.critic import CriticRetrievalGap

_EDIT_FAQ_DRAFT_NAME_BASE_MAX = 40
_EDIT_FAQ_DRAFT_TITLE_MAX = 40

# D2：简单档字数上限（去空白）；超过则至少标准深度
_SIMPLE_MAX_LEN = 40

# 复杂题启发式（D2 收紧）：对比 / 并列 / 多问点 / 明确「如何计算」/ 假种场景
# 不含单独的「请问」「怎么」「如何」——避免短事实问误升第 3 步
_COMPLEX_QUERY = re.compile(
    r"以及|同时|对比|分别|是否|各是多少|还是|并且|"
    r"如何计算|和.+假",
)
_QUESTION_MARK = re.compile(r"[？?]")
_NOISE_PERSONA = re.compile(
    r"员工小[王李张赵]|某(?:销售岗位)?员工|某部门|"
    r"请问根据手册[，,]?|根据手册[，,]?",
)


class QueryDepth(str, Enum):
    """精准模式内多步深度（D2 · ThoroughEntryPolicy）。"""

    simple = "simple"
    standard = "standard"
    complex = "complex"


def _slugify(text: str, max_len: int) -> str:
    """query → 安全文件名 base（保留 CJK/字母/数字/_ · 其余变 _ · 截断）。"""
    kept = re.sub(r"[^\w\u4e00-\u9fff]+", "_", text.strip(), flags=re.UNICODE)
    kept = re.sub(r"_+", "_", kept).strip("_")
    return (kept or "FAQ")[:max_len]


def collect_search_hits(
    prior_steps: tuple[AgentStepRecord, ...],
) -> list[SemanticSearchHit]:
    """汇总 prior 中 semantic_search 命中的片段。"""
    hits: list[SemanticSearchHit] = []
    for rec in prior_steps:
        if (
            rec.tool_name == ReadOnlyToolName.semantic_search.value
            and rec.ok
            and isinstance(rec.data, SemanticSearchOutput)
        ):
            hits.extend(rec.data.hits)
    return hits


def best_hit(hits: list[SemanticSearchHit]) -> SemanticSearchHit | None:
    if not hits:
        return None
    return max(hits, key=lambda h: h.score)


def _compact_len(query: str) -> int:
    return len(re.sub(r"\s+", "", query.strip()))


def _question_segments(query: str) -> list[str]:
    return [p.strip() for p in re.split(r"[？?。！!]", query) if p.strip()]


def _has_multi_question(query: str) -> bool:
    """同一 message ≥2 个问号 → 多问点（值得二次收窄）。"""
    return len(_QUESTION_MARK.findall(query)) >= 2


def is_complex_query(query: str) -> bool:
    """复杂特征：并列/对比/多问点等（D2 · 不含单靠请问/怎么）。"""
    return bool(_COMPLEX_QUERY.search(query)) or _has_multi_question(query)


def query_depth(query: str) -> QueryDepth:
    """ThoroughEntryPolicy：简单 / 标准 / 复杂。"""
    q = query.strip()
    if not q:
        return QueryDepth.simple
    if is_complex_query(q):
        return QueryDepth.complex
    if len(_question_segments(q)) <= 1 and _compact_len(q) <= _SIMPLE_MAX_LEN:
        return QueryDepth.simple
    return QueryDepth.standard


def refine_query(query: str) -> str | None:
    """去场景噪声 + 取末段问点；与原问相同或空则返回 None（跳过二次检索）。"""
    cleaned = _NOISE_PERSONA.sub("", query).strip()
    parts = [p.strip() for p in re.split(r"[？?。！!]", cleaned) if p.strip()]
    focus = parts[-1] if parts else cleaned
    focus = re.sub(r"\s+", " ", focus).strip()[:80]
    if not focus or focus == query.strip():
        return None
    return focus


def _search_args(query: str, default_kb_id: UUID | None) -> dict[str, Any]:
    args: dict[str, Any] = {"query": query}
    if default_kb_id is not None:
        args["kb_ids"] = [str(default_kb_id)]
    return args


class ThoroughReadPlanner:
    """D1+D2 · 精准模式：确定性多步只读（非 LLM）。

    - 第 1 步：semantic_search
    - 简单档有命中：停（不硬凑 excerpt）
    - 标准 / 复杂：第 2 步 get_chunk_excerpt(Top-1)
    - 复杂且预算允许：第 3 步 semantic_search(收窄 query)
    - 无命中：仅 1 步结束（交给 G3-E6 拒答）
    """

    def __init__(self, query: str, *, default_kb_id: UUID | None = None) -> None:
        self._query = query.strip()
        self._default_kb_id = default_kb_id
        self._depth = query_depth(self._query)
        self._search_done = False
        self._excerpt_done = False
        self._refine_done = False

    @property
    def depth(self) -> QueryDepth:
        return self._depth

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index
        if not self._query:
            return None

        if not self._search_done:
            self._search_done = True
            return ToolCallPlan(
                tool_name=ReadOnlyToolName.semantic_search.value,
                args=_search_args(self._query, self._default_kb_id),
            )

        hits = collect_search_hits(prior_steps)
        if not hits:
            return None

        # D2：简单题有命中也 1 步停，不浪费 excerpt / refine
        if self._depth == QueryDepth.simple:
            return None

        if not self._excerpt_done:
            best = best_hit(hits)
            if best is not None and steps_used < max_steps:
                self._excerpt_done = True
                return ToolCallPlan(
                    tool_name=ReadOnlyToolName.get_chunk_excerpt.value,
                    args={"chunk_id": str(best.chunk_id)},
                )
            return None

        if (
            not self._refine_done
            and self._depth == QueryDepth.complex
        ):
            self._refine_done = True
            focus = refine_query(self._query)
            if focus is not None and steps_used < max_steps:
                return ToolCallPlan(
                    tool_name=ReadOnlyToolName.semantic_search.value,
                    args=_search_args(focus, self._default_kb_id),
                )
        return None


# --- G4 · 编辑模式 Planner ---------------------------------------------------


def _build_draft_args(
    query: str,
    default_kb_id: UUID | None,
    prior_steps: tuple[AgentStepRecord, ...],
) -> dict[str, Any]:
    """末步 generate_faq_draft 入参：由搜索命中推导依据 / 目标库 / 文件名。"""
    hits = collect_search_hits(prior_steps)
    source_chunk_ids = [str(h.chunk_id) for h in hits]
    if default_kb_id is not None:
        kb_id = default_kb_id
    elif hits:
        kb_id = hits[0].kb_id
    else:
        kb_id = None
    base = _slugify(query, _EDIT_FAQ_DRAFT_NAME_BASE_MAX)
    return {
        "kb_id": str(kb_id) if kb_id is not None else None,
        "filename": f"{base}.md",
        "source_chunk_ids": source_chunk_ids,
        "title": (query.strip() or "FAQ")[:_EDIT_FAQ_DRAFT_TITLE_MAX],
    }


class EditFaqDraftPlanner:
    """G4-2.1 · 编辑模式 Planner：只读步 + 末步 generate_faq_draft（≤3 步）。"""

    def __init__(self, query: str, *, default_kb_id: UUID | None = None) -> None:
        self._query = query.strip()
        self._default_kb_id = default_kb_id
        self._search_done = False
        self._excerpt_done = False
        self._draft_done = False

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index
        if not self._search_done:
            self._search_done = True
            return ToolCallPlan(
                tool_name=ReadOnlyToolName.semantic_search.value,
                args=_search_args(self._query, self._default_kb_id),
            )
        if not self._excerpt_done:
            best = best_hit(collect_search_hits(prior_steps))
            if best is not None and (steps_used + 1) < max_steps:
                self._excerpt_done = True
                return ToolCallPlan(
                    tool_name=ReadOnlyToolName.get_chunk_excerpt.value,
                    args={"chunk_id": str(best.chunk_id)},
                )
        if not self._draft_done:
            self._draft_done = True
            return ToolCallPlan(
                tool_name=AgentToolName.generate_faq_draft.value,
                args=_build_draft_args(
                    self._query, self._default_kb_id, prior_steps
                ),
            )
        return None


# L3-W7：Critic 失败后至多 1 次定向再检索（与 agent 步预算对齐）
CRITIC_RETRIEVAL_MAX = 1


def plan_critic_directed_retrieval(
    gap: CriticRetrievalGap | None,
    *,
    steps_used: int,
    max_steps: int,
    default_kb_id: UUID | None = None,
    already_used: int = 0,
    enabled: bool | None = None,
) -> AgentDecision | None:
    """手册 §7 / M7：CriticRetrievalGap → 限预算 semantic_search Decision。

    flag 关 / 无缺口 / 已用尽补检次数 / steps_used ≥ max_steps → None（调用方走原 fail 策略）。
    """
    from app.core.config import settings

    if enabled is None:
        enabled = settings.agent_l3_critic_retrieval_enabled
    if not enabled or gap is None:
        return None
    query = (gap.suggested_query or "").strip()
    if not query:
        return None
    if already_used >= CRITIC_RETRIEVAL_MAX:
        return None
    if steps_used >= max_steps:
        return None
    return AgentDecision(
        action=AgentActionKind.tool,
        tool_name=ReadOnlyToolName.semantic_search.value,
        args=_search_args(query, default_kb_id),
        reason_code="critic_directed_retrieve",
    )


def create_tool_planner(
    message: str, *, default_kb_id: UUID | None = None
) -> ThoroughReadPlanner | LLMPlanner | NextActionPlanner:
    """改造：从直接返回 ThoroughReadPlanner → 通过 LLMPlannerFactory 路由。

    签名保持兼容（返回类型仍符合 ToolPlanner Protocol；L3 flag 开时为 NextActionPlanner）。
    """
    return LLMPlannerFactory.create(message, default_kb_id=default_kb_id)


def create_edit_tool_planner(
    query: str, *, default_kb_id: UUID | None = None
) -> EditFaqDraftPlanner:
    """工厂：构造编辑模式 planner。"""
    return EditFaqDraftPlanner(query, default_kb_id=default_kb_id)


# 兼容旧测试名：一步即停 planner（仅测试 / 对照用，生产不再使用）
class SemanticSearchPlanner:
    """已弃用：一步 semantic_search。保留供边界对照测试。"""

    def __init__(self, query: str) -> None:
        self._query = query.strip()
        self._done = False

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index, steps_used, max_steps, prior_steps
        if self._done or not self._query:
            return None
        self._done = True
        return ToolCallPlan(tool_name="semantic_search", args={"query": self._query})


# --- G5 · 文档操作模式 Planner -------------------------------------------------

_VERB_DELETE = re.compile(r"删|删除|移除|清掉|去掉|废弃|永久删除")
_VERB_RESTORE = re.compile(r"恢复|还原|复原|找回")

# B 路径自动识别（fast 模式意图路由 · 情景 4-7）
_VERB_CREATE = re.compile(r"新建|创建|起草|建个|写一份|写个|生成.*草稿|录入|新增")
# 创建类意图须带文档名词，避免「新建一个任务」误触发
_DOC_NOUN = re.compile(
    r"文档|草稿|知识库|资料|手册|制度|规范|报告|纪要|说明|指引|政策|"
    r"条款|合同|预案|方案|问答|faq|md|pdf|docx?|pptx?|xlsx?"
)
# 疑问句拦截（情景 6）：含问号/吗/怎么/如何/能否/可以吗/是否/是不是/可否/为何/为什么 → 不触发
_QUESTION = re.compile(
    r"[？?]|吗\s*[？?]?$|怎么|如何|能否|可以吗|是否|是不是|可否|为何|为什么"
)
# 文档名守卫：剔除纯语气/代词，避免「把这个删了」等无具体文档名的误触发
_GENERIC_NAME = re.compile(
    r"^(一下|一个|一些|这个|那个|它|它们|那些|这份|该|此|那个文档|"
    r"这个文档|文档|文件|内容|记录|对话|消息|数据|东西|资料|一个文档)$"
)


class WriteIntent:
    """B 路径写意图（确定性 · 非 LLM）。"""

    __slots__ = ("operation", "query")

    def __init__(self, *, operation: str, query: str) -> None:
        self.operation = operation  # "delete" | "restore" | "create"
        self.query = query


def _detect_write_op(query: str) -> str | None:
    """确定性操作识别（G5）：删/恢复动词白名单；无匹配 → None（不触发写流程）。"""
    if _VERB_DELETE.search(query):
        return "delete"
    if _VERB_RESTORE.search(query):
        return "restore"
    return None


def detect_write_intent(message: str) -> WriteIntent | None:
    """B 路径入口（fast 模式）：识别自然语言文档写意图。

    顺序硬规则（情景 4-7）：
    1. 空消息 → None；
    2. 疑问句（含问号/吗/怎么/如何…）→ None（不触发，交普通问答）；
    3. 删除/恢复动词命中 → 取文档名，须 ≥2 字且非纯语气代词，否则 None；
    4. 创建动词 + 文档名词同时命中 → "create"（复用 edit 流）；
    5. 其余 → None（普通问答）。
    """
    q = (message or "").strip()
    if not q:
        return None
    if _QUESTION.search(q):
        return None

    op = _detect_write_op(q)
    if op is None and _VERB_CREATE.search(q) and _DOC_NOUN.search(q):
        op = "create"
    if op is None:
        return None

    name = _extract_document_name(q)
    if op in ("delete", "restore"):
        if len(name) < 2 or _GENERIC_NAME.match(name):
            return None
    elif op == "create":
        # 创建无须解析目标文档；但须含文档名词（已在上方校验），且抽取名非纯语气
        if len(name) < 2 and not _DOC_NOUN.search(q):
            return None
    return WriteIntent(operation=op, query=q)


def _extract_document_name(query: str) -> str:
    """从自然语言里去操作动词与语气词，保留文档名线索。

    多级清理（避免贪婪 `.*` 误吞文档名，且能拒绝「把这个删了」等无具体文档名的命令）：
    1. 循环去除首部语气/指代词（帮我把 / 请 / 把 / 这个 …）；
    2. 去除首部动词（删除 / 恢复 …）；
    3. 去除尾部动词短语（…删掉 / …创建… ）；
    4. 去除尾部语气词（了/吧/啊…）；
    5. 去除残留主语/意愿词（我/要/想/它…）与残留动词。
    """
    name = query.strip()
    lead_particle = re.compile(r"^(帮我|请|把|将|这个|那个|那份|该|一下)\s*")
    lead_verb = re.compile(
        r"^(删(除|掉)?|移除|清掉|去掉|废弃|永久删除|恢复|还原|复原|找回|"
        r"新建|创建|起草|录入|新增|写)\s*"
    )
    trail_verb = re.compile(
        r"\s*(删(除|掉)?|移除|清掉|去掉|废弃|永久删除|恢复|还原|复原|找回|"
        r"新建.*|创建.*|起草.*|录入.*|新增.*|写.*)$"
    )
    trail_particle = re.compile(r"\s*[了啊吧哦呢呀]?\s*$")
    filler = re.compile(r"我|你|他|她|它|们|要|想|需|准备|打算|去|给|让|帮")
    residual_verb = re.compile(
        r"删(除|掉)?|移除|清掉|去掉|废弃|永久删除|恢复|还原|复原|找回|"
        r"新建|创建|起草|录入|新增|写"
    )
    for _ in range(4):
        new = lead_particle.sub("", name)
        if new == name:
            break
        name = new
    name = lead_verb.sub("", name)
    name = trail_verb.sub("", name)
    name = trail_particle.sub("", name)
    name = filler.sub("", name)
    name = residual_verb.sub("", name)
    return name.strip(" 。，,、.！!？?").strip()


class DocumentWritePlanner:
    """G5 · 文档操作模式 Planner：解析操作(删/恢复) + 文档名 → 末步 run_*_document(commit=False) 提案。

    - 第 1 步：search_documents(filename) 解析目标文档（返回 document_id/kb_id）
    - 第 2 步（末步）：run_delete_document / run_restore_document(commit=False) → 结构化提案
      （不建 pending；pending 由前端确认后 POST submit 创建）
    - 候选多篇（B 路径歧义 · 情景 5）→ 置 `ambiguous=True`，上层发 `clarify` 事件交用户点选
    - 操作/文档无法解析（0 候选）→ 不触发（planner 返回 None，交上层发 refusal）
    """

    def __init__(self, query: str, *, default_kb_id: UUID | None = None) -> None:
        self._query = query.strip()
        self._default_kb_id = default_kb_id
        self._op = _detect_write_op(self._query)
        self._search_done = False
        self._write_done = False
        self._candidates: list[SearchDocumentsItem] = []
        self._ambiguous = False

    @property
    def ambiguous(self) -> bool:
        """候选多于 1 篇 → 需歧义澄清（情景 5）。"""
        return self._ambiguous

    @property
    def candidates(self) -> list[SearchDocumentsItem]:
        return self._candidates

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
    ) -> ToolCallPlan | None:
        del query, step_index
        if self._op is None:
            return None
        if not self._search_done:
            self._search_done = True
            name = _extract_document_name(self._query)
            return ToolCallPlan(
                tool_name=ReadOnlyToolName.search_documents.value,
                args={"query": name, "mode": "filename"},
            )
        if not self._write_done:
            self._write_done = True
            candidates = self._collect_candidates(prior_steps)
            self._candidates = candidates
            if not candidates:
                return None  # 0 候选 → refusal（doc_not_found）
            if len(candidates) > 1:
                self._ambiguous = True  # 多篇 → 上层发 clarify
                return None
            picked = candidates[0]
            tool = (
                AgentToolName.delete_document
                if self._op == "delete"
                else AgentToolName.restore_document
            )
            return ToolCallPlan(
                tool_name=tool.value,
                args={
                    "kb_id": str(picked.kb_id),
                    "document_id": str(picked.document_id),
                    "commit": False,
                },
            )
        return None

    def _collect_candidates(
        self, prior_steps: tuple[AgentStepRecord, ...]
    ) -> list[SearchDocumentsItem]:
        """汇总 search_documents 命中（按 default_kb_id 过滤 + document_id 去重）。"""
        items: list[SearchDocumentsItem] = []
        seen: set[UUID] = set()
        for rec in prior_steps:
            if (
                rec.tool_name == ReadOnlyToolName.search_documents.value
                and rec.ok
                and isinstance(rec.data, SearchDocumentsOutput)
            ):
                for item in rec.data.items:
                    # 库内模式（default_kb_id 已设）只接受该库文档（G5-E19 同 G4-E19）
                    if (
                        self._default_kb_id is None
                        or item.kb_id == self._default_kb_id
                    ) and item.document_id not in seen:
                        seen.add(item.document_id)
                        items.append(item)
        return items


def create_document_write_planner(
    query: str, *, default_kb_id: UUID | None = None
) -> DocumentWritePlanner:
    """工厂：构造文档操作模式 planner。"""
    return DocumentWritePlanner(query, default_kb_id=default_kb_id)


# =============================================================================
# A-M1 · LLM 规则混合 Planner
# =============================================================================


# LLM planner 只暴露可独立调用的只读 tool（legacy 路径；L3 动态面见 ToolResolver）
_INDEPENDENT_TOOL_NAMES: tuple[str, ...] = tuple(s.name for s in INDEPENDENT_TOOL_SPECS)

# 兼容：旧 schema/描述仍供 SafetyFrame.all_tool_specs（legacy LLMPlanner）
_TOOL_PARAM_SCHEMAS: dict[str, dict[str, Any]] = {
    s.name: s.parameters for s in INDEPENDENT_TOOL_SPECS
}
_TOOL_DESCRIPTIONS: dict[str, str] = {
    s.name: s.description for s in INDEPENDENT_TOOL_SPECS
}


def _build_tool_descriptions(tool_specs: list[ToolSpec]) -> str:
    """将 tool 规格列表转为 LLM prompt 中的人类可读描述。"""
    # E4：防御性过滤 — 外部工具关闭时剔除 web_search（sql_query 已下线）
    from app.core.config import settings
    if not settings.external_tools_enabled:
        tool_specs = [ts for ts in tool_specs if ts.name != "web_search"]
    lines: list[str] = []
    for spec in tool_specs:
        params = spec.parameters
        props = params.get("properties", {})
        required = params.get("required", [])
        param_parts: list[str] = []
        for pname, pmeta in props.items():
            pdesc = pmeta.get("description", pname)
            if pname in required:
                param_parts.append(f"  - {pname}（必填）：{pdesc}")
            else:
                param_parts.append(f"  - {pname}（可选）：{pdesc}")
        lines.append(f"- {spec.name}：{spec.description}")
        lines.extend(param_parts)
    return "\n".join(lines)


def _build_planner_prompt(
    tool_descriptions: str,
    *,
    max_steps: int = 5,
) -> str:
    """构建 LLM planner 的 system prompt。"""
    return (
        "你是一个检索规划助手。你的任务是根据用户的问题，选择最合适的检索工具组合，"
        "按执行顺序输出。\n\n"
        "可用工具：\n"
        f"{tool_descriptions}\n\n"
        "规则：\n"
        "1. 输出必须是 JSON 数组，每个元素包含 tool_name 和 args 字段\n"
        "2. tool_name 必须从上面列出的工具中选择\n"
        "3. args 中的参数必须与工具的参数描述一致\n"
        "4. 按执行顺序排列工具\n"
        f"5. 最多 {max_steps} 步\n\n"
        "输出格式示例：\n"
        '[{"tool_name": "semantic_search", "args": {"query": "考勤制度"}},\n'
        ' {"tool_name": "search_documents", "args": {"query": "请假流程"}}]\n\n'
        "只输出 JSON，不要额外解释。"
    )


def _tool_exists(tool_name: str, registry: frozenset[str]) -> bool:
    """检查 tool 名是否在注册表中。"""
    return tool_name in registry


def _validate_tool_args(tool_name: str, args: dict[str, Any]) -> str | None:
    """校验 tool 参数的最小必需字段；不通过返回错误描述，通过返回 None。"""
    if tool_name in ("semantic_search", "search_documents"):
        if not args.get("query"):
            return f"{tool_name} 缺少必需参数 query"
    elif tool_name == "get_chunk_excerpt":
        if not args.get("chunk_id"):
            return "get_chunk_excerpt 缺少必需参数 chunk_id"
    elif tool_name == "grep_in_document":
        if not args.get("document_id") or not args.get("pattern"):
            return "grep_in_document 缺少必需参数 document_id 或 pattern"
    elif tool_name == "compare_chunks":
        ids = args.get("chunk_ids")
        if not isinstance(ids, list) or len(ids) < 2:
            return "compare_chunks 缺少必需参数 chunk_ids（至少2个）"
    return None


def parse_and_validate(
    llm_raw: str,
    tool_registry: frozenset[str],
) -> ParseResult:
    """解析 LLM 返回的 JSON → 校验（纯函数，无 I/O）。

    校验顺序：
    1. 能否 parse 为 JSON
    2. 是否是 list（tool 序列）
    3. 是否是 dict（单步，自动包装为 list）
    4. 每个 step 必须有 tool_name 字段（str 类型）
    5. 每个 step 必须有 args 字段（dict 类型）
    6. tool_name ∈ tool_registry
    7. 参数最小必需字段校验（tool-specific）

    失败返回 ParseResult(ok=False, error=具体原因)；
    成功返回 ParseResult(ok=True, plan=[...])。
    """
    if not llm_raw or not llm_raw.strip():
        return ParseResult(ok=False, error="empty_output", llm_raw=llm_raw)

    raw = llm_raw.strip()
    # 尝试提取 JSON（LLM 可能用 ```json ... ``` 包裹）
    if raw.startswith("```"):
        # 提取第一个 ``` 和最后一个 ``` 之间的内容
        start = raw.find("\n")
        end = raw.rfind("```")
        if start != -1 and end != -1 and end > start:
            raw = raw[start:end].strip()
        else:
            raw = raw.strip("`").strip()
    # 移除可能的语言标记
    if raw.startswith("json"):
        raw = raw[4:].strip()
    # 移除首尾的 ``` 残留
    raw = raw.strip("`").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return ParseResult(ok=False, error="parse_error", llm_raw=llm_raw)

    # 单步 dict → 自动包装为 list
    if isinstance(parsed, dict):
        parsed = [parsed]
    elif not isinstance(parsed, list):
        return ParseResult(ok=False, error="parse_error", llm_raw=llm_raw)

    plan: list[ToolCallPlan] = []
    for step in parsed:
        if not isinstance(step, dict):
            return ParseResult(ok=False, error="parse_error", llm_raw=llm_raw)
        tool_name = step.get("tool_name")
        if not isinstance(tool_name, str):
            return ParseResult(ok=False, error="parse_error", llm_raw=llm_raw)
        args = step.get("args")
        if not isinstance(args, dict):
            return ParseResult(ok=False, error="parse_error", llm_raw=llm_raw)

        if not _tool_exists(tool_name, tool_registry):
            return ParseResult(ok=False, error="tool_not_found", llm_raw=llm_raw)

        arg_err = _validate_tool_args(tool_name, args)
        if arg_err is not None:
            return ParseResult(ok=False, error="parse_error", llm_raw=llm_raw)

        plan.append(ToolCallPlan(tool_name=tool_name, args=args))

    if not plan:
        return ParseResult(ok=False, error="empty_output", llm_raw=llm_raw)

    return ParseResult(ok=True, plan=plan, llm_raw=llm_raw)


class SafetyFrame:
    """规则安全框架。

    职责：
    1. 规则分类（复用 query_depth）— 决定是否值得走 LLM
    2. tool 白名单校验 — 拒绝越权/写 tool
    3. 降级判定 — 边界条件回到 ThoroughReadPlanner
    """

    def __init__(
        self,
        query: str,
        *,
        default_kb_id: UUID | None = None,
    ) -> None:
        self._query = query.strip()
        self._default_kb_id = default_kb_id
        self._depth = query_depth(self._query)

    @property
    def depth(self) -> QueryDepth:
        """规则分类结果：simple / standard / complex。"""
        return self._depth

    @property
    def should_use_llm_planner(self) -> bool:
        """判定：是否值得走 LLM planner。

        条件（同时满足）：
        1. depth 不是 simple（简单问题规则已足够）
        2. AGENT_LLM_PLANNER_ENABLED == true
        3. query 非空且长度合理（≤500 字，防止 token 浪费）
        """
        from app.core.config import settings

        if self._depth == QueryDepth.simple:
            return False
        if not settings.agent_llm_planner_enabled:
            return False
        if not self._query or len(self._query) > 500:
            return False
        return True

    def validate(
        self,
        parsed: ParseResult,
    ) -> ValidatedPlan:
        """对 parse 后的 tool 序列执行安全校验。

        检查项（顺序裁定）：
        1. plan 非空
        2. 每个 tool 名存在于 ALL_AGENT_TOOL_NAMES 中
        3. 没有写 tool
        4. 步数 ≤ max_steps（默认 5 步）
        5. 外部工具关闭时拒绝 web_search（E4 · 防御 prompt injection）
        """
        violations: list[str] = []

        if not parsed.ok or not parsed.plan:
            return ValidatedPlan(ok=False, violations=["plan is empty or invalid"])

        plan = parsed.plan
        if len(plan) > 5:
            violations.append(f"step count {len(plan)} exceeds max 5")

        # E4：外部工具关闭时拒绝越权调用
        from app.core.config import settings
        external_disabled = not settings.external_tools_enabled

        for step in plan:
            if not _tool_exists(step.tool_name, ALL_AGENT_TOOL_NAMES):
                violations.append(f"tool '{step.tool_name}' not in registry")
            if self._is_write_tool(step.tool_name):
                violations.append(f"write tool '{step.tool_name}' not allowed")
            if external_disabled and step.tool_name == "web_search":
                violations.append(f"external tool '{step.tool_name}' disabled by config")

        if violations:
            return ValidatedPlan(ok=False, violations=violations)

        return ValidatedPlan(ok=True, plan=plan)

    def validate_decision(
        self,
        decision: AgentDecision,
        state: AgentState,
        *,
        available_tools: frozenset[str] | None = None,
    ) -> ValidatedDecision:
        """L3：对单步 AgentDecision 做安全校验。

        检查项（顺序裁定）：
        1. action ∈ tool/finish/clarify/refuse
        2. tool：tool_name 存在、非写 tool、外部工具关时拒 web_search、参数最小字段
        3. 若传入 available_tools：tool 必须在当前解锁面内（dependent 未解锁则拒）
        4. finish/clarify/refuse：不得带可执行 tool_name（忽略空）
        5. 超预算（steps_used >= max_steps）不得再选 tool
        """
        violations: list[str] = []

        if decision.action == AgentActionKind.tool:
            if not decision.tool_name:
                violations.append("tool action missing tool_name")
            else:
                if not _tool_exists(decision.tool_name, ALL_AGENT_TOOL_NAMES):
                    violations.append(f"tool '{decision.tool_name}' not in registry")
                if self._is_write_tool(decision.tool_name):
                    violations.append(f"write tool '{decision.tool_name}' not allowed")
                from app.core.config import settings

                if (
                    not settings.external_tools_enabled
                    and decision.tool_name == "web_search"
                ):
                    violations.append(
                        f"external tool '{decision.tool_name}' disabled by config"
                    )
                if (
                    available_tools is not None
                    and decision.tool_name not in available_tools
                ):
                    violations.append(
                        f"tool '{decision.tool_name}' not currently available"
                    )
                arg_err = _validate_tool_args(decision.tool_name, decision.args or {})
                if arg_err is not None:
                    violations.append(arg_err)
            if state.steps_used >= state.max_steps:
                violations.append(
                    f"budget exhausted: steps_used={state.steps_used} >= max_steps={state.max_steps}"
                )
        elif decision.action in (
            AgentActionKind.finish,
            AgentActionKind.clarify,
            AgentActionKind.refuse,
        ):
            if decision.tool_name:
                violations.append(
                    f"{decision.action.value} must not include tool_name"
                )
        else:
            violations.append(f"unknown action '{decision.action}'")

        if violations:
            return ValidatedDecision(ok=False, violations=violations)
        return ValidatedDecision(ok=True, decision=decision)

    @staticmethod
    def _is_write_tool(tool_name: str) -> bool:
        """写 tool 判定：不在 READ_ONLY_TOOL_NAMES 集合中的均为写 tool。"""
        return tool_name not in READ_ONLY_TOOL_NAMES

    def all_tool_specs(self) -> list[ToolSpec]:
        """返回 LLM 可见的 tool 规格列表（仅独立可调用的只读 tool）。"""
        specs: list[ToolSpec] = []
        for name in _INDEPENDENT_TOOL_NAMES:
            desc = _TOOL_DESCRIPTIONS.get(name, name)
            params = _TOOL_PARAM_SCHEMAS.get(name, {"type": "object", "properties": {}})
            specs.append(ToolSpec(name=name, description=desc, parameters=params))
        return specs


class LLMPlanner:
    """LLM 规则混合 Planner：规则框架兜底 + LLM 自主选择 tool 序列。

    - 由工厂函数创建（不走 __init__ 直接调用）
    - 实现 ToolPlanner Protocol，与 run_react_loop 兼容
    - **不接收 db / run_id / actor_user_id 等运行时上下文**
    - 降级时仅存 fallback_reason + last_llm_raw，审计由 stream 侧 outcome 后补发
    """

    def __init__(
        self,
        query: str,
        *,
        safety_frame: SafetyFrame,
        tool_specs: list[ToolSpec],
        default_kb_id: UUID | None = None,
        memory_context: str = "",
    ) -> None:
        self._query = query.strip()
        self._safety_frame = safety_frame
        self._tool_specs = tool_specs
        self._default_kb_id = default_kb_id
        self._memory_context = memory_context

        # 首次 LLM 调用的缓存
        self._cached_plan: ParseResult | None = None
        # 内部 plan 消费游标：等价替换/重规划步插入后仍按缓存顺序消费
        self._plan_cursor = 0
        # G1：最近一次工具失败上下文（仅用于提示重规划 prompt，不写审计）
        self._failure_context: ToolFailure | None = None
        # 降级属性：仅存储，不写 audit（审计由 stream 侧补发）
        self.fallback_reason: str | None = None
        self.last_llm_raw: str | None = None
        # 内部 fallback planner
        self._fallback_planner: ThoroughReadPlanner | None = None
        self._is_fallback: bool = False

    @property
    def depth(self) -> QueryDepth:
        """返回当前 query 的规则分类深度（代理到 SafetyFrame）。"""
        return self._safety_frame.depth

    @property
    def default_kb_id(self) -> UUID | None:
        """暴露给 _planner_with_retrieval_query 等外部逻辑读取。"""
        return self._default_kb_id

    def _reset_plan(self) -> None:
        """统一清空 LLM 计划缓存与消费游标（E2 重写 / G1 重规划共用）。"""
        self._cached_plan = None
        self._plan_cursor = 0

    async def next_tool_call(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
        stage: str = "plan",
    ) -> ToolCallPlan | None:
        """LLM Planner 版本的 next_tool_call。

        内部流程：
        1. 第一步：调用 LLM 生成 tool 序列（仅一次，结果缓存）
        2. 对每一步 ToolCallPlan，若 tool 是 KB 域且 args 中无 kb_ids，自动注入 default_kb_id
        3. 后续步：依次消费缓存的 tool 序列
        4. 序列耗尽或 LLM 返回空：返回 None 结束
        """
        if self._cached_plan is None:  # 第一步：调用 LLM
            # runtime E2 low_recall 直接置 None 重规划时，同步复位消费游标
            self._plan_cursor = 0
            self._exposure_step_id = str(step_index)
            result = await self._call_llm_for_plan(
                query,
                context={},
                stage=stage,
            )
            self._cached_plan = result
            if not result.ok:
                # 内部降级：创建 ThoroughReadPlanner 实例接管
                self._fallback_planner = ThoroughReadPlanner(
                    self._query,
                    default_kb_id=self._default_kb_id,
                )
                self._is_fallback = True
                # 不在此处调 audit——没有 db/run_id/actor_user_id
                # 仅存属性供 stream 侧补发审计
                self.fallback_reason = result.error
                self.last_llm_raw = result.llm_raw

        if self._is_fallback:
            return await self._fallback_planner.next_tool_call(
                query=query,
                step_index=step_index,
                steps_used=steps_used,
                max_steps=max_steps,
                prior_steps=prior_steps,
            )

        # 正常路径：按内部 cursor 消费缓存的 plan（替换/重规划步不占缓存索引）
        if self._cached_plan and self._cached_plan.plan:
            if self._plan_cursor < len(self._cached_plan.plan):
                plan = self._cached_plan.plan[self._plan_cursor]
                self._plan_cursor += 1
                plan = self._maybe_inject_kb(plan)
                return plan

        return None

    async def replan_after_failure(
        self,
        *,
        query: str,
        step_index: int,
        steps_used: int,
        max_steps: int,
        prior_steps: tuple[AgentStepRecord, ...],
        failure: ToolFailure,
    ) -> ToolCallPlan | None:
        """G1：携带失败上下文重新规划；新计划首步与失败步同工具同 args 时返回 None。"""
        self._failure_context = failure
        self._reset_plan()
        plan = await self.next_tool_call(
            query=query,
            step_index=step_index,
            steps_used=steps_used,
            max_steps=max_steps,
            prior_steps=prior_steps,
            stage="replan",
        )
        if plan is None:
            return None
        if prior_steps:
            failed = prior_steps[-1]
            if plan.tool_name == failed.tool_name and plan.args == failed.args:
                return None
        return plan

    async def _call_llm_for_plan(
        self,
        query: str,
        context: dict[str, Any],
        *,
        stage: str = "plan",
    ) -> ParseResult:
        """核心 LLM 调用：构建 prompt → 调 complete_chat_with_usage → 解析 & 校验。

        真实 provider usage 优先计入 usage 指标；缺失时回落到 guard 估算指标。
        """
        from app.core.config import settings
        from app.services.rag.chat_llm import (
            ChatUsage,
            complete_chat_with_usage as llm_complete_with_usage,
            has_available_chat_provider_key,
        )
        from app.services.agent.tools.guard import estimate_planner_tokens
        from app.services.observability.metrics_registry import (
            inc_agent_llm_planner_call,
            inc_agent_llm_planner_usage,
        )

        _ = context  # 保留参数供未来扩展（如 conversation history）

        if not has_available_chat_provider_key():
            # 双无 key：跳过无效 mock 调用，直接走既有 fallback（无调用即无 failed 计数）
            return ParseResult(ok=False, error="no_key")

        prompt = ""
        llm_raw: str | None = None
        usage: ChatUsage | None = None

        def _emit(result_ok: bool) -> None:
            if usage is not None and usage.has_value:
                # 真实 usage 优先：估算指标不再重复累计，缺失时作为兜底
                inc_agent_llm_planner_call(
                    stage,
                    "ok" if result_ok else "failed",
                )
                inc_agent_llm_planner_usage(stage, usage)
                return
            est = estimate_planner_tokens(prompt, llm_raw or "")
            inc_agent_llm_planner_call(
                stage,
                "ok" if result_ok else "failed",
                prompt_tokens=est.prompt_tokens,
                response_tokens=est.response_tokens,
            )

        try:
            tool_descriptions = _build_tool_descriptions(self._tool_specs)
            system_prompt = _build_planner_prompt(tool_descriptions, max_steps=5)

            # 如果需要用独立模型
            if settings.agent_llm_planner_model:
                # 用独立模型调 complete_chat_with_usage——目前固定用 env provider，
                # 独立模型选型待后续扩展；此处先统一走默认 provider
                pass

            from app.services.agent.memory_relevance_label import build_planner_memory_block

            memory_block = build_planner_memory_block(self._memory_context)
            from app.eval.memory_capability.exposure_event import MemoryExposureChannel
            from app.services.agent.memory_exposure import emit_memory_exposure_at_prompt_boundary

            emit_memory_exposure_at_prompt_boundary(
                memory_block=memory_block,
                channel=MemoryExposureChannel.llm_planner,
                run_id=getattr(self, "_exposure_run_id", None),
                step_id=getattr(self, "_exposure_step_id", None),
                records=getattr(self, "_memory_exposure_records", None) or (),
            )
            failure_block = ""
            if self._failure_context is not None:
                failure_block = (
                    f"\n\n注意：上一轮工具调用失败：{self._failure_context.tool_name}"
                    f"（{self._failure_context.summary}）。\n"
                    "请选择其他工具或修正参数，不要重复相同调用；\n"
                    "若确实无合适工具，返回空 JSON 数组结束规划。"
                )
            prompt = f"{system_prompt}{memory_block}\n\n用户问题：{query}{failure_block}"
            llm_raw, usage = await llm_complete_with_usage(
                [{"role": "user", "content": prompt}]
            )

            if not llm_raw or not llm_raw.strip():
                _emit(False)
                return ParseResult(ok=False, error="empty_output", llm_raw=llm_raw)

            result = parse_and_validate(
                llm_raw,
                tool_registry=ALL_AGENT_TOOL_NAMES,
            )
            if not result.ok:
                _emit(False)
                return result

            validated = self._safety_frame.validate(result)
            if not validated.ok:
                _emit(False)
                return ParseResult(
                    ok=False,
                    error="safety_violation",
                    llm_raw=llm_raw,
                )

            # 对 KB 域 tool 注入 default_kb_id
            validated = self._inject_kb_ids(validated)

            _emit(True)
            return ParseResult(ok=True, plan=validated.plan, llm_raw=llm_raw)

        except Exception as exc:
            _emit(False)
            return ParseResult(
                ok=False,
                error="llm_error",
                llm_raw=str(exc),
            )

    def _inject_kb_ids(self, validated: ValidatedPlan) -> ValidatedPlan:
        """对 semantic_search / search_documents 注入 default_kb_id → args['kb_ids']。

        与 _search_args() 同逻辑：若 LLM 产出 args 中无 kb_ids，
        且 self._default_kb_id 有值，则补入，防止检索退化成搜全库。
        """
        if not validated.ok or not validated.plan or self._default_kb_id is None:
            return validated

        kb_id_str = str(self._default_kb_id)
        patched: list[ToolCallPlan] = []
        for step in validated.plan:
            if step.tool_name in ("semantic_search", "search_documents"):
                args = dict(step.args)
                if "kb_ids" not in args:
                    args["kb_ids"] = [kb_id_str]
                patched.append(
                    ToolCallPlan(tool_name=step.tool_name, args=args)
                )
            else:
                patched.append(step)

        return ValidatedPlan(ok=True, plan=patched)

    def _maybe_inject_kb(self, plan: ToolCallPlan) -> ToolCallPlan:
        """对单步 plan 做 kb_id 注入（确保消费侧每步都覆盖）。"""
        if self._default_kb_id is None:
            return plan
        if plan.tool_name not in ("semantic_search", "search_documents"):
            return plan
        if "kb_ids" in plan.args:
            return plan
        args = dict(plan.args)
        args["kb_ids"] = [str(self._default_kb_id)]
        return ToolCallPlan(tool_name=plan.tool_name, args=args)


class LLMPlannerFactory:
    """根据规则条件路由到 NextActionPlanner / LLMPlanner / ThoroughReadPlanner。

    路由逻辑（L3-W2）：
    1. `agent_l3_next_action_enabled` 且非 simple → NextActionPlanner
    2. 简单问题 / 关 LLM 开关 / 超长 → ThoroughReadPlanner
    3. 否则 → LLMPlanner（legacy 回滚）
    """

    @staticmethod
    def create(
        query: str,
        *,
        default_kb_id: UUID | None = None,
        memory_context: str = "",
    ) -> ThoroughReadPlanner | LLMPlanner | NextActionPlanner:
        """根据规则路由；flag 关时行为与改造前一致。"""
        safety_frame = SafetyFrame(query, default_kb_id=default_kb_id)
        from app.core.config import settings

        if settings.agent_l3_next_action_enabled:
            q = query.strip()
            if (
                safety_frame.depth == QueryDepth.simple
                or not q
                or len(q) > 500
            ):
                return ThoroughReadPlanner(query, default_kb_id=default_kb_id)
            tool_specs = _l3_tool_specs(safety_frame)
            return NextActionPlanner(
                query,
                safety_frame=safety_frame,
                tool_specs=tool_specs,
                default_kb_id=default_kb_id,
                memory_context=memory_context,
            )

        if not safety_frame.should_use_llm_planner:
            return ThoroughReadPlanner(query, default_kb_id=default_kb_id)

        tool_specs = safety_frame.all_tool_specs()
        # E4：外部工具开关 — 关闭时剔除 web_search（sql_query 已下线）
        if not settings.external_tools_enabled:
            tool_specs = [ts for ts in tool_specs if ts.name != "web_search"]
        return LLMPlanner(
            query,
            safety_frame=safety_frame,
            tool_specs=tool_specs,
            default_kb_id=default_kb_id,
            memory_context=memory_context,
        )


def _l3_tool_specs(safety_frame: SafetyFrame) -> list[ToolSpec]:
    """W4：构造时种子为独立只读面；逐步解锁由 decide_next → ToolResolver。"""
    from app.core.config import settings

    del safety_frame
    specs = list(INDEPENDENT_TOOL_SPECS)
    if not settings.external_tools_enabled:
        specs = [s for s in specs if s.name != "web_search"]
    return specs


def _strip_llm_json_fence(llm_raw: str) -> str:
    """去掉 ```json … ``` 包裹，与 parse_and_validate 同口径。"""
    raw = llm_raw.strip()
    if raw.startswith("```"):
        start = raw.find("\n")
        end = raw.rfind("```")
        if start != -1 and end != -1 and end > start:
            raw = raw[start:end].strip()
        else:
            raw = raw.strip("`").strip()
    if raw.startswith("json"):
        raw = raw[4:].strip()
    return raw.strip("`").strip()


def _tool_name_missing_or_null(parsed: dict[str, Any]) -> bool:
    if "tool_name" not in parsed:
        return True
    return parsed.get("tool_name") is None


def _apply_duplicate_consistent_canonicalization(
    parsed: dict[str, Any],
    exposed_tool_names: frozenset[str],
) -> bool:
    """Repair TOOL_NAME_AS_ACTION when action duplicates an exposed tool name.

    Only when tool_name is missing/null or exactly equals action. Mutates ``parsed``
    in place. Returns True if canonicalization was applied.
    """
    action_raw = parsed.get("action")
    if not isinstance(action_raw, str):
        return False
    if action_raw not in exposed_tool_names:
        return False

    if _tool_name_missing_or_null(parsed):
        parsed["action"] = "tool"
        parsed["tool_name"] = action_raw
        return True

    existing = parsed.get("tool_name")
    if isinstance(existing, str) and existing == action_raw:
        parsed["action"] = "tool"
        return True

    return False


def parse_agent_decision(
    llm_raw: str,
    *,
    exposed_tool_names: Collection[str] | None = None,
) -> DecisionParseResult:
    """解析 LLM 返回的**单对象** JSON → AgentDecision（纯函数，无 I/O）。

    与 parse_and_validate（序列）相对：禁止 list；只接受 dict。
    未知字段忽略；非法 action / 缺字段 → ok=False。
    """
    if not llm_raw or not llm_raw.strip():
        return DecisionParseResult(ok=False, error="empty_output", llm_raw=llm_raw)

    try:
        parsed = json.loads(_strip_llm_json_fence(llm_raw))
    except json.JSONDecodeError:
        return DecisionParseResult(ok=False, error="parse_error", llm_raw=llm_raw)

    if isinstance(parsed, list):
        return DecisionParseResult(ok=False, error="not_single_object", llm_raw=llm_raw)
    if not isinstance(parsed, dict):
        return DecisionParseResult(ok=False, error="parse_error", llm_raw=llm_raw)

    canonicalization_applied = False
    if exposed_tool_names is not None:
        exposed = frozenset(exposed_tool_names)
        canonicalization_applied = _apply_duplicate_consistent_canonicalization(
            parsed, exposed
        )

    action_raw = parsed.get("action")
    if not isinstance(action_raw, str):
        return DecisionParseResult(
            ok=False,
            error="invalid_action",
            llm_raw=llm_raw,
            canonicalization_applied=canonicalization_applied,
        )
    try:
        action = AgentActionKind(action_raw)
    except ValueError:
        return DecisionParseResult(
            ok=False,
            error="invalid_action",
            llm_raw=llm_raw,
            canonicalization_applied=canonicalization_applied,
        )

    tool_name = parsed.get("tool_name")
    if tool_name is not None and not isinstance(tool_name, str):
        return DecisionParseResult(
            ok=False,
            error="parse_error",
            llm_raw=llm_raw,
            canonicalization_applied=canonicalization_applied,
        )

    args = parsed.get("args", {})
    if args is None:
        args = {}
    if not isinstance(args, dict):
        return DecisionParseResult(
            ok=False,
            error="parse_error",
            llm_raw=llm_raw,
            canonicalization_applied=canonicalization_applied,
        )

    reason_code = parsed.get("reason_code", "")
    if reason_code is None:
        reason_code = ""
    if not isinstance(reason_code, str):
        return DecisionParseResult(
            ok=False,
            error="parse_error",
            llm_raw=llm_raw,
            canonicalization_applied=canonicalization_applied,
        )

    user_message = parsed.get("user_message")
    if user_message is not None and not isinstance(user_message, str):
        return DecisionParseResult(
            ok=False,
            error="parse_error",
            llm_raw=llm_raw,
            canonicalization_applied=canonicalization_applied,
        )

    if action == AgentActionKind.tool:
        if not tool_name:
            return DecisionParseResult(
                ok=False,
                error="missing_tool_name",
                llm_raw=llm_raw,
                canonicalization_applied=canonicalization_applied,
            )
        arg_err = _validate_tool_args(tool_name, args)
        if arg_err is not None:
            return DecisionParseResult(
                ok=False,
                error="invalid_args",
                llm_raw=llm_raw,
                canonicalization_applied=canonicalization_applied,
            )
    else:
        # finish / clarify / refuse：不携带可执行 tool
        tool_name = None
        args = {}

    return DecisionParseResult(
        ok=True,
        decision=AgentDecision(
            action=action,
            tool_name=tool_name,
            args=args,
            reason_code=reason_code,
            user_message=user_message,
        ),
        llm_raw=llm_raw,
        canonicalization_applied=canonicalization_applied,
    )


def _build_next_action_prompt(
    tool_descriptions: str,
    summary: ObservationSummary,
) -> str:
    """L3 prompt：状态摘要 + 当前可用工具；禁止自由文本 CoT。"""
    missing = ", ".join(summary.missing_facts) if summary.missing_facts else "(none)"
    covered = ", ".join(summary.covered_facts) if summary.covered_facts else "(none)"
    conflicted = (
        ", ".join(summary.conflicted_facts) if summary.conflicted_facts else "(none)"
    )
    docs = ", ".join(summary.doc_names) if summary.doc_names else "(none)"
    scores = ", ".join(f"{s:.3f}" for s in summary.top_scores) if summary.top_scores else "(none)"
    has_advisory = bool(summary.preferred_tool_hint) or summary.task_contract_satisfied
    advisory_rule = (
        "- preferred_tool_hint / task_contract_satisfied 仅为 advisory，"
        "不得当作强制 override；模型仍须产出合法 AgentDecision；\n"
        if has_advisory
        else ""
    )
    advisory_lines: list[str] = []
    if summary.preferred_tool_hint:
        advisory_lines.append(
            f"- preferred_tool_hint (advisory only, not a forced override): "
            f"{summary.preferred_tool_hint}"
            f" [intent={summary.preferred_tool_intent or 'n/a'};"
            f" reason={summary.preferred_tool_reason or 'n/a'}]"
        )
    if summary.task_contract_satisfied:
        advisory_lines.append(
            "- task_contract_satisfied (advisory): true — "
            "tool-native observation meets migrated task contract; "
            "you may choose a legal terminal (finish/refuse/clarify); "
            "this is NOT force_finish and does not bypass StopPolicy"
        )
    advisory_tail = (
        ("\n" + "\n".join(advisory_lines)) if advisory_lines else ""
    )
    return (
        "你是只读知识检索 Agent 的下一步决策器。"
        "目标：根据当前证据状态，只选择「一个」下一动作。\n\n"
        "允许动作：\n"
        "1) tool：调用一个当前可用工具\n"
        "2) finish：证据已足够回答\n"
        "3) clarify：用户问题存在必须由用户消除的歧义\n"
        "4) refuse：在剩余预算/权限内无法形成可支持回答的证据\n\n"
        "硬规则：\n"
        "- 不得调用未列出的工具；\n"
        "- 不得调用写工具；\n"
        "- 若 missing_facts 非空且仍有有效检索路径，不得 finish；\n"
        "- 若 conflicted_facts 非空，不得 finish（应 refuse 或 clarify）；\n"
        "- 不重复完全相同的失败调用；\n"
        f"{advisory_rule}"
        "- 不输出自由文本推理，只输出结构化 decision 与 reason_code。\n\n"
        f"可用工具：\n{tool_descriptions}\n\n"
        "当前观察摘要（无正文）：\n"
        f"- original_query: {summary.original_query}\n"
        f"- active_query: {summary.active_query}\n"
        f"- steps_used/max_steps: {summary.steps_used}/{summary.max_steps}\n"
        f"- last_tool/ok: {summary.last_tool}/{summary.last_ok}\n"
        f"- last_summary: {summary.last_summary}\n"
        f"- doc_names: {docs}\n"
        f"- top_scores: {scores}\n"
        f"- evidence_sufficient: {summary.evidence_sufficient}\n"
        f"- confidence: {summary.confidence}\n"
        f"- covered_facts: {covered}\n"
        f"- missing_facts: {missing}\n"
        f"- conflicted_facts: {conflicted}\n"
        f"- last_failure: {summary.last_failure_kind} / {summary.last_failure_summary}\n"
        f"- reflection_count: {summary.reflection_count}"
        f"{advisory_tail}\n\n"
        "只输出一个 JSON 对象，格式示例：\n"
        '{"action":"tool","tool_name":"semantic_search",'
        '"args":{"query":"..."},"reason_code":"initial_retrieval"}\n'
        "或 "
        '{"action":"finish","reason_code":"evidence_sufficient"}'
    )


class NextActionPlanner:
    """L3 Observation-driven Planner：每步 decide_next(state) → 单步 AgentDecision。

    - **无** `_cached_plan` / `_plan_cursor`（禁止一次排完再游标消费）
    - 不实现 ToolPlanner.next_tool_call（由 runtime `_run_l3_next_action_loop` 消费）
    - LLM 失败 / 校验失败 → refuse（显式动作，不用 None 猜语义）
    """

    def __init__(
        self,
        query: str,
        *,
        safety_frame: SafetyFrame,
        tool_specs: list[ToolSpec],
        default_kb_id: UUID | None = None,
        memory_context: str = "",
    ) -> None:
        self._query = query.strip()
        self._safety_frame = safety_frame
        self._tool_specs = tool_specs
        self._default_kb_id = default_kb_id
        self._memory_context = memory_context
        self._planner_calls = 0
        self.fallback_reason: str | None = None
        self.last_llm_raw: str | None = None

    @property
    def depth(self) -> QueryDepth:
        return self._safety_frame.depth

    @property
    def default_kb_id(self) -> UUID | None:
        return self._default_kb_id

    def _available_tools(self, state: AgentState) -> list[ToolSpec]:
        """按 AgentState + agent_l3_dynamic_tools_enabled 解锁 dependent tools。"""
        from app.core.config import settings

        return ToolResolver.resolve(
            state,
            dynamic_enabled=settings.agent_l3_dynamic_tools_enabled,
            external_tools_enabled=settings.external_tools_enabled,
        )

    def _max_planner_calls(self, state: AgentState) -> int:
        from app.core.config import settings

        configured = settings.agent_l3_max_planner_calls
        if configured and configured > 0:
            return configured
        return state.max_steps

    async def decide_next(self, state: AgentState) -> AgentDecision:
        """Observation → 单步 AgentDecision（每次重新规划，无缓存序列）。"""
        from app.core.config import settings
        from app.services.agent.evidence_gate import (
            apply_evidence_stop_retrieve,
            maybe_finish_from_evidence,
        )
        from app.services.agent.state import summarize_state_for_planner

        if self._planner_calls >= self._max_planner_calls(state):
            return AgentDecision(
                action=AgentActionKind.refuse,
                reason_code="budget_exhausted",
            )
        if state.steps_used >= state.max_steps:
            return AgentDecision(
                action=AgentActionKind.refuse,
                reason_code="budget_exhausted",
            )

        # L3-W5：EvidenceState.sufficient → 短路 finish（默认关）
        early_finish = maybe_finish_from_evidence(state)
        if early_finish is not None:
            return early_finish

        available = self._available_tools(state)
        available_names = frozenset(s.name for s in available)
        summary = summarize_state_for_planner(state)
        # L4-W5：flag 门控注入 missing / conflicted（默认关；不接 Stop runtime）
        from app.services.agent.planner_fact_hints import apply_observation_fact_hints

        summary = apply_observation_fact_hints(summary, state.evidence)
        self._exposure_step_id = str(state.steps_used)
        # TOOL P3：S2/T2 advisory hints（默认关；不 override Decision / StopPolicy）
        from app.services.agent.tool_guidance_hints import apply_tool_guidance_hints

        summary = apply_tool_guidance_hints(summary, state, available_names)
        parsed = await self._call_llm(summary, available)
        self._planner_calls += 1

        if not parsed.ok or parsed.decision is None:
            self.fallback_reason = parsed.error
            self.last_llm_raw = parsed.llm_raw
            return AgentDecision(
                action=AgentActionKind.refuse,
                reason_code=parsed.error or "parse_error",
            )

        validated = self._safety_frame.validate_decision(
            parsed.decision,
            state,
            available_tools=available_names,
        )
        if not validated.ok or validated.decision is None:
            self.fallback_reason = "safety_violation"
            self.last_llm_raw = parsed.llm_raw
            return AgentDecision(
                action=AgentActionKind.refuse,
                reason_code="safety_violation",
            )

        decision = validated.decision
        # L3-W5：不足时拦截过早 finish → retrieve；充分时强制 finish
        if settings.agent_l3_evidence_state_enabled:
            decision = apply_evidence_stop_retrieve(state, decision, enabled=True)
        if decision.action == AgentActionKind.tool:
            decision = self._maybe_inject_kb(decision)
        return decision

    def _maybe_inject_kb(self, decision: AgentDecision) -> AgentDecision:
        if self._default_kb_id is None or not decision.tool_name:
            return decision
        if decision.tool_name not in ("semantic_search", "search_documents"):
            return decision
        if "kb_ids" in decision.args:
            return decision
        args = dict(decision.args)
        args["kb_ids"] = [str(self._default_kb_id)]
        return AgentDecision(
            action=decision.action,
            tool_name=decision.tool_name,
            args=args,
            reason_code=decision.reason_code,
            user_message=decision.user_message,
        )

    async def _call_llm(
        self,
        summary: ObservationSummary,
        tool_specs: list[ToolSpec],
    ) -> DecisionParseResult:
        from app.services.rag.chat_llm import (
            complete_chat_with_usage as llm_complete_with_usage,
            has_available_chat_provider_key,
        )

        if not has_available_chat_provider_key():
            return DecisionParseResult(ok=False, error="no_key")

        tool_descriptions = _build_tool_descriptions(tool_specs)
        system_prompt = _build_next_action_prompt(tool_descriptions, summary)
        from app.services.agent.memory_relevance_label import build_planner_memory_block

        memory_block = build_planner_memory_block(self._memory_context)
        from app.eval.memory_capability.exposure_event import MemoryExposureChannel
        from app.services.agent.memory_exposure import emit_memory_exposure_at_prompt_boundary

        emit_memory_exposure_at_prompt_boundary(
            memory_block=memory_block,
            channel=MemoryExposureChannel.next_action_planner,
            run_id=getattr(self, "_exposure_run_id", None),
            step_id=getattr(self, "_exposure_step_id", None),
            records=getattr(self, "_memory_exposure_records", None) or (),
        )
        prompt = f"{system_prompt}{memory_block}"

        try:
            llm_raw, _usage = await llm_complete_with_usage(
                [{"role": "user", "content": prompt}]
            )
        except Exception as exc:
            return DecisionParseResult(ok=False, error="llm_error", llm_raw=str(exc))

        if not llm_raw or not llm_raw.strip():
            return DecisionParseResult(
                ok=False, error="empty_output", llm_raw=llm_raw
            )
        exposed = frozenset(s.name for s in tool_specs)
        return parse_agent_decision(llm_raw, exposed_tool_names=exposed)
