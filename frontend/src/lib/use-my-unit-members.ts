import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import {
  fetchOrganizationMembers,
  type OrganizationMember,
} from "@/lib/organization-api";
import { filterManagedUnitOptions } from "@/lib/org-permissions";
import {
  addUnitMember,
  fetchDepartmentPickerUnits,
  fetchUnitMembers,
  removeUnitMember,
  updateUnitMember,
  type OrgUnit,
  type OrgUnitMember,
  type UnitRole,
} from "@/lib/org-units-api";

/** NW-24 U1：仅托管节点成员 CRUD（不碰树 / 不拉全量 org-units）。 */
export function useMyUnitMembers() {
  const { user } = useAuth();
  const adminIdsKey = (user?.unit_admin_unit_ids ?? []).join(",");

  const [managedUnits, setManagedUnits] = useState<OrgUnit[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [members, setMembers] = useState<OrgUnitMember[]>([]);
  const [roster, setRoster] = useState<OrganizationMember[]>([]);

  const [loading, setLoading] = useState(true);
  const [membersLoading, setMembersLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const [addMemberOpen, setAddMemberOpen] = useState(false);
  const [addingMember, setAddingMember] = useState(false);
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [removingUserId, setRemovingUserId] = useState<string | null>(null);

  const selectedUnit = useMemo(
    () => managedUnits.find((u) => u.id === selectedId) ?? null,
    [managedUnits, selectedId],
  );

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
      const [pickerUnits, rosterItems] = await Promise.all([
        fetchDepartmentPickerUnits(),
        fetchOrganizationMembers(),
      ]);
      const adminIds = adminIdsKey ? adminIdsKey.split(",") : [];
      const managed = filterManagedUnitOptions(pickerUnits, adminIds);
      setManagedUnits(managed);
      setRoster(rosterItems);
      setSelectedId((prev) => {
        if (prev && managed.some((u) => u.id === prev)) return prev;
        return managed[0]?.id ?? null;
      });
      if (managed.length === 0) {
        setError("未找到可管理的部门节点");
      }
    } catch (err) {
      setManagedUnits([]);
      setRoster([]);
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [adminIdsKey]);

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
      await loadMembers(selectedId);
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
      await loadMembers(selectedId);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "移出失败");
    } finally {
      setRemovingUserId(null);
    }
  }

  return {
    managedUnits,
    selectedId,
    selectedUnit,
    members,
    roster,
    loading,
    membersLoading,
    error,
    actionError,
    addMemberOpen,
    addingMember,
    updatingUserId,
    removingUserId,
    setSelectedId,
    setActionError,
    setAddMemberOpen,
    loadAll,
    handleAddMember,
    handleSetRole,
    handleSetPrimary,
    handleRemoveMember,
  };
}
