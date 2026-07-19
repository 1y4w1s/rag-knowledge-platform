import { useEffect, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  updateKnowledgeBase,
  type KnowledgeBase,
} from "@/lib/knowledge-base-api";

interface EditKnowledgeBaseDialogProps {
  kb: KnowledgeBase | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUpdated: (updated: KnowledgeBase) => void;
}

function isNameConflictMessage(message: string): boolean {
  return message.includes("名称");
}

export function EditKnowledgeBaseDialog({
  kb,
  open,
  onOpenChange,
  onUpdated,
}: EditKnowledgeBaseDialogProps) {
  const titleId = useId();
  const nameErrorId = useId();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open && kb) {
      setName(kb.name);
      setDescription(kb.description ?? "");
      setNameError(null);
      setFormError(null);
      setSubmitting(false);
    }
  }, [open, kb]);

  useEffect(() => {
    if (!open) {
      setNameError(null);
      setFormError(null);
      setSubmitting(false);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !submitting) onOpenChange(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onOpenChange, submitting]);

  if (!open || !kb) return null;

  const editingKb = kb;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setNameError("请填写资料库名称");
      setFormError(null);
      return;
    }

    setSubmitting(true);
    setNameError(null);
    setFormError(null);
    try {
      const updated = await updateKnowledgeBase(editingKb.id, {
        name: trimmedName,
        description: description.trim(),
      });
      onOpenChange(false);
      onUpdated(updated);
    } catch (err) {
      const message = err instanceof Error ? err.message : "保存失败";
      if (isNameConflictMessage(message)) {
        setNameError(message);
      } else {
        setFormError(message);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="presentation"
      onClick={() => {
        if (!submitting) onOpenChange(false);
      }}
    >
      <div className="absolute inset-0 bg-black/30" aria-hidden />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative z-10 w-full max-w-md rounded-2xl border border-[var(--line2)] bg-[var(--bg)] p-6 shadow-[var(--card-shadow)]"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id={titleId}
          className="font-serif text-lg font-semibold text-foreground"
        >
          编辑资料库
        </h2>
        <p className="mt-1 text-sm text-muted">
          修改名称或描述；保存后列表、详情与对话顶栏将同步更新。
        </p>

        <form className="mt-5 space-y-4" onSubmit={handleSubmit}>
          <div>
            <Label htmlFor={`${titleId}-name`}>名称</Label>
            <Input
              id={`${titleId}-name`}
              value={name}
              maxLength={255}
              placeholder="例如：员工手册 2026"
              autoFocus
              aria-invalid={Boolean(nameError)}
              aria-describedby={nameError ? nameErrorId : undefined}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError(null);
              }}
            />
            {nameError && (
              <p id={nameErrorId} role="alert" className="form-field-err mt-1.5 text-sm">
                {nameError}
              </p>
            )}
          </div>
          <div>
            <Label htmlFor={`${titleId}-desc`}>描述（可选）</Label>
            <textarea
              id={`${titleId}-desc`}
              value={description}
              maxLength={5000}
              rows={3}
              placeholder="简要说明该资料库用途；留空则恢复默认说明"
              onChange={(e) => setDescription(e.target.value)}
              className="flex w-full resize-none rounded-md border border-line2 bg-surface px-3 py-2 text-sm text-foreground placeholder:text-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            />
          </div>

          {formError && (
            <p role="alert" className="form-field-err text-sm">
              {formError}
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
              {submitting ? "保存中…" : "保存"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
