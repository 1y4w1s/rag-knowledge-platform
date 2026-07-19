import { useCallback, useEffect, useMemo, useState } from "react";
import { Share2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { StoredUser } from "@/lib/auth-storage";
import { isCompanyAdmin } from "@/lib/department-align";
import {
  createKbGrant,
  deleteKbGrant,
  fetchKbGrants,
  formatGrantPermissionLabel,
  type KbGrant,
  type GranteeType,
} from "@/lib/kb-grants-api";
import type { KnowledgeBase } from "@/lib/knowledge-base-api";
import { buildDepartmentTree } from "@/lib/org-unit-tree";
import { fetchOrgUnits, type OrgUnit } from "@/lib/org-units-api";

type GrantTargetMode = "company" | "org_unit";

interface KnowledgeBaseGrantsPanelProps {
  kb: KnowledgeBase;
  kbId: string;
  user: StoredUser;
  onToast: (message: string) => void;
}

function asUnitList(value: OrgUnit[] | null | undefined): OrgUnit[] {
  return Array.isArray(value) ? value : [];
}

function asGrantList(value: KbGrant[] | null | undefined): KbGrant[] {
  return Array.isArray(value) ? value : [];
}

function formatGrantTargetLabel(
  grant: KbGrant,
  unitNameById: Map<string, string>,
): string {
  if (grant.grantee_type === "company") return "全公司";
  if (!grant.grantee_id) return "未知部门";
  return unitNameById.get(grant.grantee_id) ?? "未知部门";
}

export function KnowledgeBaseGrantsPanel({
  kb,
  kbId,
  user,
  onToast,
}: KnowledgeBaseGrantsPanelProps) {
  const [open, setOpen] = useState(false);
  const [grants, setGrants] = useState<KbGrant[]>([]);
  const [units, setUnits] = useState<OrgUnit[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [targetMode, setTargetMode] = useState<GrantTargetMode>("company");
  const [targetUnitId, setTargetUnitId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const isPublicKb = kb.org_unit_id === null;
  const canGrantCompany = isCompanyAdmin(user) && !isPublicKb;
  const safeUnits = asUnitList(units);
  const safeGrants = asGrantList(grants);

  const unitNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const unit of safeUnits) map.set(unit.id, unit.name);
    return map;
  }, [safeUnits]);

  const departmentOptions = useMemo(() => {
    const { root } = buildDepartmentTree(safeUnits);
    if (!root) return [] as { id: string; label: string }[];

    const options: { id: string; label: string }[] = [];
    const walk = (node: ReturnType<typeof buildDepartmentTree>["root"], depth: number) => {
      if (!node) return;
      options.push({
        id: node.unit.id,
        label: `${"　".repeat(depth)}${node.unit.name}`,
      });
      node.children.forEach((child) => walk(child, depth + 1));
    };
    walk(root, 0);
    return options;
  }, [safeUnits]);

  const existingTargets = useMemo(() => {
    const keys = new Set<string>();
    for (const grant of safeGrants) {
      keys.add(
        grant.grantee_type === "company"
          ? "company:"
          : `org_unit:${grant.grantee_id ?? ""}`,
      );
    }
    return keys;
  }, [safeGrants]);

  const loadGrants = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [grantItems, orgUnits] = await Promise.all([
        fetchKbGrants(kbId),
        fetchOrgUnits(),
      ]);
      setGrants(asGrantList(grantItems));
      setUnits(asUnitList(orgUnits));
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "加载共享设置失败");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    if (!open) return;
    void loadGrants();
  }, [open, loadGrants]);

  useEffect(() => {
    if (!canGrantCompany && targetMode === "company") {
      setTargetMode("org_unit");
    }
  }, [canGrantCompany, targetMode]);

  useEffect(() => {
    if (targetMode === "org_unit" && !targetUnitId && departmentOptions.length > 0) {
      const firstAvailable = departmentOptions.find(
        (option) => !existingTargets.has(`org_unit:${option.id}`),
      );
      setTargetUnitId(firstAvailable?.id ?? departmentOptions[0].id);
    }
  }, [targetMode, targetUnitId, departmentOptions, existingTargets]);

  async function handleAddGrant(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const granteeType: GranteeType =
      targetMode === "company" ? "company" : "org_unit";

    if (granteeType === "org_unit" && !targetUnitId) {
      setFormError("请选择目标部门");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createKbGrant(kbId, {
        grantee_type: granteeType,
        grantee_id: granteeType === "org_unit" ? targetUnitId : null,
        permission: "read",
      });
      setGrants((prev) => [...asGrantList(prev), created]);
      onToast("已添加共享");
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "添加失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevoke(grantId: string) {
    setRevokingId(grantId);
    try {
      await deleteKbGrant(kbId, grantId);
      setGrants((prev) => asGrantList(prev).filter((item) => item.id !== grantId));
      onToast("已撤销共享");
    } catch (err) {
      onToast(err instanceof Error ? err.message : "撤销失败");
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <section className="kb-grants-panel mb-5">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 py-2.5 text-left transition-colors hover:text-foreground"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Share2 className="h-4 w-4 text-[color:var(--mut-warm)]" aria-hidden />
          跨部门共享
        </span>
        <span className="text-xs text-muted">
          {open ? "收起" : "展开"}
        </span>
      </button>

      {open && (
        <div className="border-t border-[color:var(--line2)] py-4">
          <p className="text-xs text-[color:var(--mut-warm)]">
            将本资料库开放给其他部门或全公司只读访问。撤销后，对方部门成员将无法在列表与对话中检索该库。
          </p>

          {isPublicKb && (
            <p className="mt-3 rounded-md border border-[color:var(--line2)] bg-[color:color-mix(in_srgb,var(--ubg)_55%,transparent)] px-3 py-2 text-xs text-muted">
              公司公共资料库已全员可见，无需再添加「全公司」共享。
            </p>
          )}

          {loading && (
            <p className="mt-4 text-sm text-muted">加载共享记录…</p>
          )}

          {loadError && (
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <p role="alert" className="text-sm text-destructive">
                {loadError}
              </p>
              <Button type="button" variant="outline" size="sm" onClick={() => void loadGrants()}>
                重试
              </Button>
            </div>
          )}

          {!loading && !loadError && (
            <>
              {safeGrants.length === 0 ? (
                <p className="mt-4 text-sm text-muted">尚未共享给其他部门。</p>
              ) : (
                <ul className="mt-4 divide-y divide-[color:var(--line2)] rounded-md border border-[color:var(--line2)]">
                  {safeGrants.map((grant) => (
                    <li
                      key={grant.id}
                      className="flex flex-wrap items-center justify-between gap-2 px-3 py-2.5 text-sm"
                    >
                      <div>
                        <span className="font-medium text-foreground">
                          {formatGrantTargetLabel(grant, unitNameById)}
                        </span>
                        <span className="ml-2 text-xs text-muted">
                          {formatGrantPermissionLabel(grant.permission)}
                        </span>
                      </div>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        disabled={revokingId === grant.id}
                        onClick={() => void handleRevoke(grant.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                        {revokingId === grant.id ? "撤销中…" : "撤销"}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}

              <form className="mt-5 space-y-3 border-t border-[color:var(--line2)] pt-4" onSubmit={handleAddGrant}>
                <p className="text-xs font-medium text-foreground">添加共享</p>

                <fieldset className="space-y-2">
                  {canGrantCompany && (
                    <label className="flex cursor-pointer items-center gap-2 text-sm">
                      <input
                        type="radio"
                        name="grant-target"
                        checked={targetMode === "company"}
                        disabled={existingTargets.has("company:")}
                        onChange={() => setTargetMode("company")}
                      />
                      <span>全公司（只读）</span>
                    </label>
                  )}
                  <label className="flex cursor-pointer items-start gap-2 text-sm">
                    <input
                      type="radio"
                      name="grant-target"
                      className="mt-0.5"
                      checked={targetMode === "org_unit"}
                      onChange={() => setTargetMode("org_unit")}
                    />
                    <span className="flex-1">
                      指定部门（只读）
                      {targetMode === "org_unit" && (
                        <select
                          value={targetUnitId}
                          disabled={departmentOptions.length === 0}
                          onChange={(e) => setTargetUnitId(e.target.value)}
                          className="settings-field-input mt-2 h-9 w-full"
                        >
                          {departmentOptions.map((option) => (
                            <option
                              key={option.id}
                              value={option.id}
                              disabled={existingTargets.has(`org_unit:${option.id}`)}
                            >
                              {option.label}
                              {existingTargets.has(`org_unit:${option.id}`) ? "（已共享）" : ""}
                            </option>
                          ))}
                        </select>
                      )}
                    </span>
                  </label>
                </fieldset>

                {!canGrantCompany && targetMode === "company" && (
                  <p className="text-xs text-muted">请选择要共享的目标部门。</p>
                )}

                {formError && (
                  <p role="alert" className="form-field-err text-sm">
                    {formError}
                  </p>
                )}

                <div className="flex justify-end">
                  <Button type="submit" size="sm" disabled={submitting}>
                    {submitting ? "添加中…" : "添加共享"}
                  </Button>
                </div>
              </form>
            </>
          )}
        </div>
      )}
    </section>
  );
}
