import { Link } from "react-router-dom";

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
        className="cursor-default text-muted"
        title="文档整理中，请稍后再预览"
      >
        {doc.filename}
      </span>
    );
  }

  return (
    <Link
      to={`/knowledge-bases/${kbId}/documents/${doc.id}`}
      className="text-foreground underline-offset-2 hover:text-[var(--action)] hover:underline"
    >
      {doc.filename}
    </Link>
  );
}

interface DocumentTableProps {
  kbId: string;
  documents: Document[];
  canManage: boolean;
  deletingDocId?: string | null;
  onRequestDelete: (doc: Document) => void;
  onRetry: (docId: string) => Promise<void>;
}

export function DocumentTable({
  kbId,
  documents,
  canManage,
  deletingDocId = null,
  onRequestDelete,
  onRetry,
}: DocumentTableProps) {
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th scope="col">文件名</th>
          <th scope="col">格式</th>
          <th scope="col">大小</th>
          <th scope="col">切片数</th>
          <th scope="col">状态</th>
          <th scope="col">上传时间</th>
          <th scope="col">操作</th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr
            key={doc.id}
            className="transition-colors hover:bg-[rgba(245,242,237,0.35)]"
          >
            <td className="font-medium text-foreground">
              <DocumentFilenameCell kbId={kbId} doc={doc} />
            </td>
            <td className="text-muted">{formatFileType(doc.file_type)}</td>
            <td className="text-muted">{formatFileSize(doc.file_size)}</td>
            <td className="text-muted">{formatChunkCount(doc)}</td>
            <td>
              <DocumentStatusBadge status={doc.status} />
            </td>
            <td className="text-muted">{formatUploadedAt(doc.created_at)}</td>
            <td>
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
        ))}
      </tbody>
    </table>
  );
}
