import { Link } from "react-router-dom";

import { DocumentStatusBadge } from "@/components/knowledge-bases/DocumentStatusBadge";
import {
  buildDocumentPreviewUrl,
  formatFileSize,
  type Document,
} from "@/lib/document-api";

interface DocumentMetaPanelProps {
  kbId: string;
  document: Document;
  showDownload?: boolean;
}

export function DocumentMetaPanel({
  kbId,
  document,
  showDownload = false,
}: DocumentMetaPanelProps) {
  const chunkLabel =
    document.chunk_count != null ? `${document.chunk_count} 切片` : "—";
  const downloadHref = buildDocumentPreviewUrl(kbId, document.id);

  return (
    <aside className="preview-side">
      <div className="preview-side-card">
        <h3 className="preview-side-title">文档信息</h3>
        <dl className="preview-meta-list">
          <div className="preview-meta-row">
            <dt>文件名</dt>
            <dd className="break-all">{document.filename}</dd>
          </div>
          <div className="preview-meta-row">
            <dt>大小</dt>
            <dd>
              {formatFileSize(document.file_size)} · {chunkLabel}
            </dd>
          </div>
          <div className="preview-meta-row">
            <dt>格式</dt>
            <dd>{document.file_type.toUpperCase()}</dd>
          </div>
          <div className="preview-meta-row">
            <dt>状态</dt>
            <dd>
              <DocumentStatusBadge
                status={document.status}
                processingStage={document.processing_stage}
                progressDetail={document.progress_detail}
              />
              {document.status === "processing" &&
              document.progress_percent != null &&
              document.progress_percent < 100 ? (
                <p className="mt-1 text-xs text-muted">
                  进度 {document.progress_percent}%
                  {document.progress_detail
                    ? ` · ${document.progress_detail}`
                    : ""}
                </p>
              ) : null}
            </dd>
          </div>
          {document.status === "failed" && document.error_message ? (
            <div className="preview-meta-row">
              <dt>失败原因</dt>
              <dd className="whitespace-pre-wrap text-[0.8125rem] leading-relaxed text-muted">
                {document.error_message}
              </dd>
            </div>
          ) : null}
        </dl>
        <div className="preview-side-actions">
          <Link
            to={`/knowledge-bases/${kbId}/chat`}
            className="preview-action-link"
          >
            提问 →
          </Link>
          {showDownload ? (
            <a
              className="preview-action-secondary"
              href={downloadHref}
              download={document.filename}
            >
              下载原文件
            </a>
          ) : null}
        </div>
      </div>
    </aside>
  );
}
