import { useCallback, useEffect, useId, useState } from "react";

import { useAuditFilterOptions } from "@/components/admin/useAuditFilterOptions";
import { SectionTitle } from "@/components/common/SectionTitle";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/Select";
import {
  downloadKbInventoryExport,
  type KbInventoryExportFormat,
} from "@/lib/kb-inventory-api";

const shell = "mx-auto max-w-[1180px] px-7 pb-16 pt-7";
const ALL_KB = "";

export function AdminKbInventoryPage() {
  const { kbOptions } = useAuditFilterOptions();
  const trashId = useId();
  const [format, setFormat] = useState<KbInventoryExportFormat>("csv");
  const [kbId, setKbId] = useState(ALL_KB);
  const [includeTrash, setIncludeTrash] = useState(false);
  const [exporting, setExporting] = useState<KbInventoryExportFormat | null>(
    null,
  );
  const [exportError, setExportError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "资产清单 · 索隐";
  }, []);

  const handleExport = useCallback(
    async (fileFormat: KbInventoryExportFormat) => {
      setExporting(fileFormat);
      setExportError(null);
      try {
        await downloadKbInventoryExport({
          format: fileFormat,
          kb_id: kbId || undefined,
          include_trash: includeTrash,
        });
      } catch (err) {
        setExportError(err instanceof Error ? err.message : "导出失败");
      } finally {
        setExporting(null);
      }
    },
    [kbId, includeTrash],
  );

  const busy = exporting !== null;
  const kbSelectOptions = [
    { value: ALL_KB, label: "全部可见资料库" },
    ...kbOptions,
  ];

  return (
    <div className={`${shell} space-y-4`}>
      <SectionTitle label="资产清单" en="INVENTORY" tone="quiet" />

      <p className="max-w-2xl text-sm text-[var(--mut)]">
        导出组织内可见资料库的<strong className="font-medium text-[var(--text)]">文档 metadata</strong>
        （文件名、库名、状态等），最多 5000 行。不含对话正文、切片正文或文件本体。
        这不是操作审计导出。
      </p>

      {exportError ? (
        <AlertBanner
          action={
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setExportError(null)}
            >
              关闭
            </Button>
          }
        >
          {exportError}
        </AlertBanner>
      ) : null}

      <section
        aria-label="导出选项"
        className="max-w-xl space-y-4 rounded-[14px] border border-[var(--line2)] bg-white/60 p-5"
      >
        <div className="space-y-1.5">
          <Label className="text-sm text-[var(--text)]">格式</Label>
          <Select
            id="kb-inventory-format"
            value={format}
            options={[
              { value: "csv", label: "CSV" },
              { value: "json", label: "JSON" },
            ]}
            onChange={(v) => setFormat(v as KbInventoryExportFormat)}
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-sm text-[var(--text)]">资料库（可选）</Label>
          <Select
            id="kb-inventory-kb"
            value={kbId}
            options={kbSelectOptions}
            onChange={setKbId}
            placeholder="全部可见资料库"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            id={trashId}
            type="checkbox"
            checked={includeTrash}
            disabled={busy}
            onChange={(e) => setIncludeTrash(e.target.checked)}
            className="h-4 w-4 rounded border-[var(--line2)] accent-[var(--action)]"
          />
          <Label htmlFor={trashId} className="text-sm text-[var(--text)]">
            包含回收站中的文档
          </Label>
        </div>

        <div className="pt-1">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={busy}
            onClick={() => void handleExport(format)}
          >
            {busy
              ? "导出中…"
              : format === "json"
                ? "下载 JSON"
                : "下载 CSV"}
          </Button>
        </div>
      </section>
    </div>
  );
}
