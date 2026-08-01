"""审计日志导出序列化（NW-32）。仅 metadata，无对话正文列。"""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Literal

from app.schemas.audit_log import AuditLogResponse

EXPORT_MAX_ROWS = 5000
ExportFormat = Literal["csv", "json"]

# 导出列 = 列表可见字段；不含 content / body / question / answer
CSV_COLUMNS = (
    "id",
    "created_at",
    "action",
    "actor_user_id",
    "actor_email",
    "resource_type",
    "resource_id",
    "kb_id",
    "kb_name",
    "ip",
    "details",
)


def _details_json(details: dict[str, Any] | None) -> str:
    if not details:
        return ""
    return json.dumps(details, ensure_ascii=False, separators=(",", ":"))


def _row_dict(item: AuditLogResponse) -> dict[str, str]:
    return {
        "id": str(item.id),
        "created_at": item.created_at.isoformat(),
        "action": item.action,
        "actor_user_id": str(item.actor_user_id) if item.actor_user_id else "",
        "actor_email": item.actor_email or "",
        "resource_type": item.resource_type or "",
        "resource_id": str(item.resource_id) if item.resource_id else "",
        "kb_id": str(item.kb_id) if item.kb_id else "",
        "kb_name": item.kb_name or "",
        "ip": item.ip or "",
        "details": _details_json(item.details),
    }


def render_audit_csv(items: list[AuditLogResponse]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for item in items:
        writer.writerow(_row_dict(item))
    return buf.getvalue()


def render_audit_json(
    items: list[AuditLogResponse],
    *,
    total_matched: int,
    truncated: bool,
    export_limit: int,
) -> str:
    payload = {
        "kind": "audit_logs_export",
        "format": "json",
        "total_matched": total_matched,
        "exported": len(items),
        "export_limit": export_limit,
        "truncated": truncated,
        "items": [
            {
                "id": str(item.id),
                "created_at": item.created_at.isoformat(),
                "action": item.action,
                "actor_user_id": (
                    str(item.actor_user_id) if item.actor_user_id else None
                ),
                "actor_email": item.actor_email,
                "resource_type": item.resource_type,
                "resource_id": (
                    str(item.resource_id) if item.resource_id else None
                ),
                "kb_id": str(item.kb_id) if item.kb_id else None,
                "kb_name": item.kb_name,
                "ip": item.ip,
                "details": item.details,
            }
            for item in items
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
