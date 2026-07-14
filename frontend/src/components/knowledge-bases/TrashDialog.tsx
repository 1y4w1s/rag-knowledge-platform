import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  listTrash,
  restoreDocument,
  permanentlyDeleteDocument,
  type Document,
} from "@/lib/document-api";

interface TrashDialogProps {
  kbId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onRefresh: () => void;
}

export function TrashDialog({ kbId, open, onOpenChange, onRefresh }: TrashDialogProps) {
  const [items, setItems] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listTrash(kbId));
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  async function handleRestore(docId: string) {
    await restoreDocument(kbId, docId);
    await load();
    onRefresh();
  }

  async function handlePermanentDelete(docId: string) {
    if (!confirm("确定永久删除？此操作不可恢复。")) return;
    await permanentlyDeleteDocument(kbId, docId);
    await load();
    onRefresh();
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="max-h-[70vh] w-full max-w-lg overflow-y-auto rounded-xl bg-background p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-serif text-lg font-semibold">回收站</h3>
          <button
            type="button"
            className="text-sm text-muted-foreground hover:text-foreground"
            onClick={() => onOpenChange(false)}
          >
            关闭
          </button>
        </div>

        {loading ? (
          <p className="text-sm text-muted-foreground">加载中…</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">回收站为空</p>
        ) : (
          <div className="space-y-2">
            {items.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-md border border-border px-3 py-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{doc.filename}</p>
                  {doc.deleted_at && (
                    <p className="text-xs text-muted-foreground">
                      删除于 {new Date(doc.deleted_at).toLocaleDateString("zh-CN")}
                    </p>
                  )}
                </div>
                <div className="ml-2 flex shrink-0 gap-1">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void handleRestore(doc.id)}
                  >
                    恢复
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="text-red-600 hover:bg-red-50"
                    onClick={() => void handlePermanentDelete(doc.id)}
                  >
                    永久删除
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
