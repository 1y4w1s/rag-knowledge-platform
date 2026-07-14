import { useEffect, useMemo, useState } from "react";

import { useAuth } from "@/lib/auth-context";
import {
  buildDepartmentPickerModel,
  type DepartmentPickerModel,
} from "@/lib/department-picker-tree";
import { fetchDepartmentPickerUnits, type OrgUnit } from "@/lib/org-units-api";
import { useDepartment } from "@/lib/department-context";
import { useOrganizationName } from "@/lib/use-organization-name";
import { useWorkspace } from "@/lib/workspace-context";

export function useDepartmentPicker(): {
  model: DepartmentPickerModel;
  units: OrgUnit[];
  unitsById: Map<string, OrgUnit>;
  orgName: string;
  loading: boolean;
  error: string | null;
} {
  const { user } = useAuth();
  const { isTeamWorkspace } = useWorkspace();
  const { pickerGeneration } = useDepartment();
  const { name: orgName } = useOrganizationName();
  const [units, setUnits] = useState<OrgUnit[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isTeamWorkspace || !user?.org_id) {
      setUnits([]);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    void fetchDepartmentPickerUnits()
      .then((items) => {
        if (!cancelled) setUnits(items);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setUnits([]);
          setError(err instanceof Error ? err.message : "部门加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isTeamWorkspace, user?.org_id, user?.unit_ids?.join(","), pickerGeneration]);

  const unitsById = useMemo(
    () => new Map(units.map((unit) => [unit.id, unit])),
    [units],
  );

  const model = useMemo(
    () =>
      user
        ? buildDepartmentPickerModel(units, user)
        : {
            root: null,
            byId: new Map(),
            selectableIds: new Set<string>(),
            showAllScopeOption: false,
          },
    [units, user],
  );

  return {
    model,
    units,
    unitsById,
    orgName: orgName || "公司",
    loading,
    error,
  };
}
