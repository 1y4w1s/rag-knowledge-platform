"""审计服务（Plan-3E-1）。"""

from app.services.audit.log import get_audit_log, write_audit_log

__all__ = ["get_audit_log", "write_audit_log"]
