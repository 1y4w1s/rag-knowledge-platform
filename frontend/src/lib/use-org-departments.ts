import { useCallback, useEffect, useMemo, useState } from "react";

import {
  fetchOrganizationMembers,
  fetchOrganizationSettings,
  type OrganizationMember,
} from "@/lib/organization-api";
import { buildDepartmentTree } from "@/lib/org-unit-tree";
import {
  addUnitMember,
  createOrgUnit,
  deleteOrgUnit,
  ensureOrgUnitRoot,
  fetchOrgUnits,
  fetchUnitMembers,
  removeUnitMember,
  updateOrgUnitName,
  updateUnitMember,
  type OrgUnit,
  type OrgUnitMember,
  type UnitRole,
} from "@/lib/org-units-api";
import { useDepartment } from "@/lib/department-context";

export function useOrgDepartments() {
  const { invalidateDepartmentPicker } = useDepartment();
  const [orgName, setOrgName] = useState("公司");
  const [units, setUnits] = useState<OrgUnit[]>([]);
  const [roster, setRoster] = useState<OrganizationMember[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [members, setMembers] = useState<OrgUnitMember[]>([]);

  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [removingUserId, setRemovingUserId] = useState<string | null>(null);

  const [createDialog, setCreateDialog] = useState<{
    open: boolean;
    parentId: string | null;
    title: string;
    description: string;
  }>({ open: false, parentId: null, title: "", description: "" });
  const [addMemberOpen, setAddMemberOpen] = useState(false);

  const { root, byId } = useMemo(() => buildDepartmentTree(units), [units]);
  const selectedUnit = selectedId ? (byId.get(selectedId)?.unit ?? null) : null;
  const isRootSelected = selectedUnit?.parent_id === null;

  const reloadUnits = useCallback(async () => {
    const items = await fetchOrgUnits();
    setUnits(items);
    return items;
  }, []);

  const loadMembers = useCallback(async (unitId: string) => {
    setMembersLoading(true);
    try {
      const items = await fetchUnitMembers(unitId);
      setMembers(items);
    } catch (err) {
      setMembers([]);
      setActionError(err instanceof Error ? err.message : "成员加载失败");
    } finally {
      setMembersLoading(false);
    }
  }, []);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [settings, items, rosterItems] = await Promise.all([
        fetchOrganizationSettings(),
        fetchOrgUnits(),
        fetchOrganizationMembers(),
      ]);
      setOrgName(settings.name);
      setUnits(items);
      setRoster(rosterItems);
      const tree = buildDepartmentTree(items);
      const rootId = tree.root?.unit.id ?? null;
      setSelectedId((prev) => {
        if (prev && tree.byId.has(prev)) return prev;
        return rootId;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  useEffect(() => {
    if (!selectedId) {
      setMembers([]);
      return;
    }
    void loadMembers(selectedId);
  }, [selectedId, loadMembers]);

  async function openCreateTopLevel() {
    if (root) {
      setCreateDialog({
        open: true,
        parentId: root.unit.id,
        title: "新建一级部门",
        description: "一级部门将挂在公司根节点下。",
      });
      return;
    }
    // 根节点不存在时先创建
    try {
      const newRoot = await ensureOrgUnitRoot();
      const items = await reloadUnits();
      const tree = buildDepartmentTree(items);
      setCreateDialog({
        open: true,
        parentId: newRoot.id,
        title: "新建一级部门",
        description: "一级部门将挂在公司根节点下。",
      });
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "创建根部门失败");
    }
  }

  function openCreateChild() {
    if (!selectedUnit) return;
    setCreateDialog({
      open: true,
      parentId: selectedUnit.id,
      title: "新建子部门",
      description: `在「${selectedUnit.name}」下创建子部门。`,
    });
  }

  async function handleCreate(name: string) {
    if (!createDialog.parentId) return;
    setCreating(true);
    setActionError(null);
    try {
      const created = await createOrgUnit(name, createDialog.parentId);
      await reloadUnits();
      invalidateDepartmentPicker();
      setSelectedId(created.id);
      setCreateDialog((prev) => ({ ...prev, open: false }));
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  }

  async function handleRename(name: string) {
    if (!selectedUnit) return;
    setRenaming(true);
    setActionError(null);
    try {
      await updateOrgUnitName(selectedUnit.id, name);
      await reloadUnits();
      invalidateDepartmentPicker();
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "重命名失败");
    } finally {
      setRenaming(false);
    }
  }

  async function handleDelete() {
    if (!selectedUnit) return;
    setDeleting(true);
    setActionError(null);
    try {
      const parentId = selectedUnit.parent_id;
      await deleteOrgUnit(selectedUnit.id);
      const items = await reloadUnits();
      invalidateDepartmentPicker();
      const tree = buildDepartmentTree(items);
      if (parentId && tree.byId.has(parentId)) {
        setSelectedId(parentId);
      } else {
        setSelectedId(tree.root?.unit.id ?? null);
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  }

  async function handleAddMember(payload: {
    user_id: string;
    role: UnitRole;
    is_primary: boolean;
  }) {
    if (!selectedId) return;
    setAddingMember(true);
    setActionError(null);
    try {
      await addUnitMember(selectedId, payload);
      setAddMemberOpen(false);
      await Promise.all([reloadUnits(), loadMembers(selectedId)]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "添加失败");
    } finally {
      setAddingMember(false);
    }
  }

  async function handleSetRole(member: OrgUnitMember, role: UnitRole) {
    if (!selectedId) return;
    setUpdatingUserId(member.user_id);
    setActionError(null);
    try {
      await updateUnitMember(selectedId, member.user_id, { role });
      await loadMembers(selectedId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "角色更新失败");
    } finally {
      setUpdatingUserId(null);
    }
  }

  async function handleSetPrimary(member: OrgUnitMember) {
    if (!selectedId) return;
    setUpdatingUserId(member.user_id);
    setActionError(null);
    try {
      await updateUnitMember(selectedId, member.user_id, { is_primary: true });
      await loadMembers(selectedId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "主部门设置失败");
    } finally {
      setUpdatingUserId(null);
    }
  }

  async function handleRemoveMember(member: OrgUnitMember) {
    if (!selectedId) return;
    setRemovingUserId(member.user_id);
    setActionError(null);
    try {
      await removeUnitMember(selectedId, member.user_id);
      await Promise.all([reloadUnits(), loadMembers(selectedId)]);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "移出失败");
    } finally {
      setRemovingUserId(null);
    }
  }

  return {
    orgName,
    root,
    selectedId,
    selectedUnit,
    isRootSelected,
    members,
    roster,
    loading,
    membersLoading,
    error,
    actionError,
    creating,
    renaming,
    deleting,
    addingMember,
    updatingUserId,
    removingUserId,
    createDialog,
    addMemberOpen,
    setSelectedId,
    setActionError,
    setCreateDialog,
    setAddMemberOpen,
    loadAll,
    openCreateTopLevel,
    openCreateChild,
    handleCreate,
    handleRename,
    handleDelete,
    handleAddMember,
    handleSetRole,
    handleSetPrimary,
    handleRemoveMember,
  };
}
