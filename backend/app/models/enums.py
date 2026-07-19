"""领域枚举（与 Alembic PostgreSQL ENUM 一致）。"""

from enum import Enum


class AccountType(str, Enum):
    personal = "personal"
    enterprise = "enterprise"


class OrgRole(str, Enum):
    admin = "admin"
    member = "member"


class DocumentStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class MessageRole(str, Enum):
    user = "user"
    assistant = "assistant"


class ThreadKind(str, Enum):
    knowledge_base = "knowledge_base"
    workspace = "workspace"


class ThreadStatus(str, Enum):
    active = "active"
    archived = "archived"


class UnitRole(str, Enum):
    unit_admin = "unit_admin"
    unit_member = "unit_member"


class GranteeType(str, Enum):
    org_unit = "org_unit"
    company = "company"


class GrantPermission(str, Enum):
    read = "read"
    write = "write"


class AgentMode(str, Enum):
    """Agent 对话模式（G3/G4 · API fast|thorough|edit；fast 不创建 agent_run）。"""

    fast = "fast"
    thorough = "thorough"
    edit = "edit"


class AgentRunMode(str, Enum):
    """agent_runs.mode 落库值（G3 thorough · G4 edit）。"""

    thorough = "thorough"
    edit = "edit"


class AgentRunStatus(str, Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    capped = "capped"


class AgentStepStatus(str, Enum):
    running = "running"
    done = "done"
    error = "error"


class ApprovalKind(str, Enum):
    """agent_approvals.kind（G4-min 仅 adopt_faq）。"""

    adopt_faq = "adopt_faq"


class ApprovalStatus(str, Enum):
    """agent_approvals.status（G4-0.1）。"""

    pending = "pending"
    adopted = "adopted"
    cancelled = "cancelled"
    expired = "expired"


class DocumentVisibility(str, Enum):
    """文档可见性（文档级权限）。"""

    everyone = "everyone"
    admin_only = "admin_only"
