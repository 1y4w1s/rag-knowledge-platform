"""组织域：部门树与 OrgScope。"""

from app.services.org.scope import OrgScope, resolve_org_scope, resolve_org_scope_for_workspace

__all__ = ["OrgScope", "resolve_org_scope", "resolve_org_scope_for_workspace"]
