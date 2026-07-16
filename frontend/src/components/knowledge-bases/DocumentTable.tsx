import { Link } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";

import { DocumentRowActions } from "@/components/knowledge-bases/DocumentRowActions";
import { DocumentStatusBadge } from "@/components/knowledge-bases/DocumentStatusBadge";
import {
  formatFileSize,
  isDocumentProcessing,
  type Document,
} from "@/lib/document-api";

function formatFileType(fileType: string): string {
  return fileType.toUpperCase();
}

function formatChunkCount(doc: Document): string {
  if (doc.status !== "completed") return "—";
  if (doc.chunk_count == null) return "—";
  return String(doc.chunk_count);
}

function formatUploadedAt(iso: string): string {
  const uploaded = new Date(iso);
  const now = new Date();
  const startOfToday = new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate(),
  );
  const startOfUploaded = new Date(
    uploaded.getFullYear(),
    uploaded.getMonth(),
    uploaded.getDate(),
  );
  const dayDiff = Math.round(
    (startOfToday.getTime() - startOfUploaded.getTime()) / 86_400_000,
  );
  if (dayDiff === 0) return "今天";
  if (dayDiff === 1) return "昨天";
  if (dayDiff < 7) return `${dayDiff} 天前`;
  if (dayDiff < 28) {
    const weeks = Math.floor(dayDiff / 7);
    return weeks === 1 ? "1 周前" : `${weeks} 周前`;
  }
  return uploaded.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function DocumentFilenameCell({ kbId, doc }: { kbId: string; doc: Document }) {
  if (isDocumentProcessing(doc.status)) {
    return (
      <span
        className="block max-w-[320px] truncate cursor-default text-muted"
        title="文档整理中，请稍后再预览"
      >
        {doc.filename}
      </span>
    );
  }

  return (
    <Link
      to={`/knowledge-bases/${kbId}/documents/${doc.id}`}
      className="block max-w-[320px] truncate text-foreground underline-offset-2 hover:text-[var(--action)] hover:underline"
      title={doc.filename}
    >
      {doc.filename}
    </Link>
  );
}

interface DocumentTableProps {
  kbId: string;
  documents: Document[];
  canManage: boolean;
  canChangeVisibility: boolean;
  pendingVisibilityId?: string | null;
  deletingDocId?: string | null;
  onRequestDelete: (doc: Document) => void;
  onRetry: (docId: string) => Promise<void>;
  onVisibilityChange?: (docId: string, visibility: "everyone" | "admin_only") => void;
}

export function DocumentTable({
  kbId,
  documents,
  canManage,
  canChangeVisibility,
  pendingVisibilityId = null,
  deletingDocId = null,
  onRequestDelete,
  onRetry,
  onVisibilityChange,
}: DocumentTableProps) {
  return (
    <table className="data-table">
      <colgroup>
        <col />{/* 文件名 - flex */}
        <col className="w-[60px]" />{/* 格式 */}
        <col className="w-[80px]" />{/* 大小 */}
        <col className="w-[70px]" />{/* 切片数 */}
        <col className="w-[80px]" />{/* 状态 */}
        <col />{/* 可见性 - 自适应 */}
        <col className="w-[80px]" />{/* 上传时间 */}
        <col className="w-[110px]" />{/* 操作 */}
      </colgroup>
      <thead>
        <tr>
          <th scope="col">文件名</th>
          <th scope="col">格式</th>
          <th scope="col" className="text-right">大小</th>
          <th scope="col" className="text-right">切片数</th>
          <th scope="col">状态</th>
          <th scope="col">可见性</th>
          <th scope="col">上传时间</th>
          <th scope="col" className="text-right">操作</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => {
          const isAdminOnly = doc.visibility === "admin_only";
          const isVisibilityPending = pendingVisibilityId === doc.id;
          return (
            <tr
              key={doc.id}
              className={`group transition-colors hover:bg-[var(--surface-2)] ${
                isAdminOnly ? "bg-[var(--warn-bg)]/40" : ""
              }`}
            >
              <td className="font-medium text-foreground">
                <DocumentFilenameCell kbId={kbId} doc={doc} />
              </td>
              <td className="font-mono text-[0.72rem] uppercase text-muted">
                {formatFileType(doc.file_type)}
              </td>
              <td className="text-right font-mono text-[0.75rem] tabular-nums text-muted">
                {formatFileSize(doc.file_size)}
              </td>
              <td className="text-right font-mono text-[0.75rem] tabular-nums text-muted">
                {formatChunkCount(doc)}
              </td>
              <td>
                <DocumentStatusBadge status={doc.status} />
              </td>
              <td>
                <span
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                    isAdminOnly
                      ? "bg-[var(--warn-bg)] text-[var(--warn)]"
                      : "bg-[var(--ok-bg)] text-[var(--ok)]"
                  }`}
                  title={
                    isAdminOnly
                      ? "仅管理员可在对话中检索到，成员看不到"
                      : "全员可见，成员可在对话中检索到"
                  }
                >
                  {isAdminOnly ? <EyeOff className="h-3 w-3" aria-hidden /> : <Eye className="h-3 w-3" aria-hidden />}
                  {isAdminOnly ? "仅管理员" : "全员"}
                </span>
                {canChangeVisibility && onVisibilityChange ? (
                  <button
                    type="button"
                    aria-label={isAdminOnly ? "改为全员可见" : "改为仅管理员可见"}
                    disabled={isVisibilityPending}
                    className="ml-1.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-[var(--action)] hover:bg-[var(--action-bg)] disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={() =>
                      onVisibilityChange(
                        doc.id,
                        isAdminOnly ? "everyone" : "admin_only",
                      )
                    }
                  >
                    {isVisibilityPending ? (
                      <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                    ) : (
                      <span>切换</span>
                    )}
                  </button>
                ) : null}
              </td>
              <td className="font-mono text-[0.72rem] text-muted">
                {formatUploadedAt(doc.created_at)}
              </td>
              <td className="text-right">
                <DocumentRowActions
                  kbId={kbId}
                  doc={doc}
                  canManage={canManage}
                  deleting={deletingDocId === doc.id}
                  onRequestDelete={onRequestDelete}
                  onRetry={onRetry}
                />
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
