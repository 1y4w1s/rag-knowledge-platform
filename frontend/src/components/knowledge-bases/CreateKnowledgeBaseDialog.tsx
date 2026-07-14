import { useEffect, useId, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { StoredUser } from "@/lib/auth-storage";
import {
  buildKbAffiliationOptions,
  canSelectCompanyPublicKb,
  formatAffiliationOptionLabel,
  resolveCurrentDepartmentAffiliation,
  type KbAffiliationMode,
} from "@/lib/kb-affiliation-options";
import {
  createKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge-base-api";
import { fetchOrgUnits } from "@/lib/org-units-api";
import type { WorkspaceId } from "@/lib/workspace-storage";

interface CreateKnowledgeBaseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (kb: KnowledgeBase) => void;
  workspace: WorkspaceId;
  departmentId: string | null;
  user: StoredUser | null;
}

export function CreateKnowledgeBaseDialog({
  open,
  onOpenChange,
  onCreated,
  workspace,
  departmentId,
  user,
}: CreateKnowledgeBaseDialogProps) {
  const titleId = useId();
  const isTeamWorkspace = workspace !== "personal";
  const showAffiliation = isTeamWorkspace && Boolean(user);

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [affiliationMode, setAffiliationMode] = useState<KbAffiliationMode>("current");
  const [specificUnitId, setSpecificUnitId] = useState("");
  const [unitOptions, setUnitOptions] = useState<
    ReturnType<typeof buildKbAffiliationOptions>
  >([]);
  const [unitsLoading, setUnitsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const currentDepartmentId = useMemo(
    () => resolveCurrentDepartmentAffiliation(departmentId),
    [departmentId],
  );
  const canSelectPublic = user ? canSelectCompanyPublicKb(user) : false;

  useEffect(() => {
    if (!open) {
      setName("");
      setDescription("");
      setAffiliationMode("current");
      setSpecificUnitId("");
      setError(null);
      setSubmitting(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open || !showAffiliation || !user) return;
    let cancelled = false;
    setUnitsLoading(true);
    void fetchOrgUnits()
      .then((units) => {
        if (cancelled) return;
        const options = buildKbAffiliationOptions(units, user);
        setUnitOptions(options);
        setSpecificUnitId((prev) => prev || options[0]?.unitId || "");
      })
      .catch(() => {
        if (!cancelled) setUnitOptions([]);
      })
      .finally(() => {
        if (!cancelled) setUnitsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, showAffiliation, user]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onOpenChange]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setError("请填写资料库名称");
      return;
    }

    if (showAffiliation && affiliationMode === "current" && !currentDepartmentId) {
      setError("当前为全公司视图，请选择具体归属部门");
      return;
    }
    if (showAffiliation && affiliationMode === "specific" && !specificUnitId) {
      setError("请选择归属部门");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const payload: Parameters<typeof createKnowledgeBase>[0] = {
        name: trimmedName,
        description: description.trim() || undefined,
        workspace,
        departmentId: isTeamWorkspace ? departmentId : null,
      };

      if (showAffiliation) {
        if (affiliationMode === "public") {
          payload.org_unit_id = null;
        } else if (affiliationMode === "specific") {
          payload.org_unit_id = specificUnitId;
        }
      }

      const created = await createKnowledgeBase(payload);
      onOpenChange(false);
      onCreated(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => onOpenChange(false)}
    >
      <div className="absolute inset-0 bg-black/30" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-xl border border-[var(--line2)] bg-white p-6 shadow-md"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={titleId}
          className="font-serif text-lg font-semibold tracking-[0.02em] text-foreground"
        >
          新建资料库
        </h2>
        <p className="mt-1 text-sm text-muted">
          为文档集合命名，后续可上传文件并开启 RAG 对话。
        </p>

        <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
          <div>
            <Label htmlFor="kb-name">名称</Label>
            <Input
              id="kb-name"
              value={name}
              maxLength={255}
              placeholder="例如：员工手册 2026"
              autoFocus
              onChange={(e) => setName(e.target.value)}
              aria-invalid={Boolean(error && !name.trim())}
            />
          </div>
          <div>
            <Label htmlFor="kb-desc">描述（可选）</Label>
            <textarea
              id="kb-desc"
              value={description}
              maxLength={5000}
              rows={3}
              placeholder="简要说明该资料库用途"
              onChange={(e) => setDescription(e.target.value)}
              className="flex w-full resize-none rounded-md border border-zinc-200 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </div>

          {showAffiliation && (
            <fieldset className="space-y-2">
              <legend className="text-sm font-medium text-foreground">归属</legend>
              <label className="flex cursor-pointer items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="kb-affiliation"
                  className="mt-0.5"
                  checked={affiliationMode === "current"}
                  disabled={!currentDepartmentId}
                  onChange={() => setAffiliationMode("current")}
                />
                <span>
                  当前部门
                  {!currentDepartmentId && (
                    <span className="block text-xs text-muted">
                      全公司视图下不可用，请选下方指定部门
                    </span>
                  )}
                </span>
              </label>
              {canSelectPublic && (
                <label className="flex cursor-pointer items-center gap-2 text-sm">
                  <input
                    type="radio"
                    name="kb-affiliation"
                    checked={affiliationMode === "public"}
                    onChange={() => setAffiliationMode("public")}
                  />
                  <span>公司公共（全公司可见）</span>
                </label>
              )}
              <label className="flex cursor-pointer items-start gap-2 text-sm">
                <input
                  type="radio"
                  name="kb-affiliation"
                  className="mt-0.5"
                  checked={affiliationMode === "specific"}
                  onChange={() => setAffiliationMode("specific")}
                />
                <span className="flex-1">
                  指定部门
                  {affiliationMode === "specific" && (
                    <select
                      id="kb-affiliation-unit"
                      value={specificUnitId}
                      disabled={unitsLoading || unitOptions.length === 0}
                      onChange={(e) => setSpecificUnitId(e.target.value)}
                      className="mt-2 flex w-full rounded-md border border-zinc-200 bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
                    >
                      {unitOptions.map((option) => (
                        <option key={option.unitId} value={option.unitId}>
                          {formatAffiliationOptionLabel(option)}
                        </option>
                      ))}
                    </select>
                  )}
                </span>
              </label>
            </fieldset>
          )}

          {error && (
            <p role="alert" className="form-field-err text-sm">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-2 pt-1">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={submitting}
              onClick={() => onOpenChange(false)}
            >
              取消
            </Button>
            <Button type="submit" size="sm" disabled={submitting}>
              {submitting ? "创建中…" : "创建"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
