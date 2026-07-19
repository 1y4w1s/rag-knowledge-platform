import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  CHUNK_STALE_LABEL,
  formatCitationLabel,
  previewPathForCitation,
  resolveCitation,
  SOURCE_DELETED_LABEL,
  SOURCE_INACCESSIBLE_LABEL,
  type Citation,
  type CitationLabelMode,
  type CitationSourceStatus,
} from "@/lib/chat-api";
import { useDepartment } from "@/lib/department-context";
import { useWorkspace } from "@/lib/workspace-context";

interface CitationPreviewProps {
  kbId: string;
  citation: Citation;
  scopeMode?: CitationLabelMode;
}

function previewTitle(citation: Citation): string {
  const locParts: string[] = [];
  if (citation.section_title) locParts.push(citation.section_title);
  if (citation.page != null) locParts.push(`第${citation.page}页`);
  if (locParts.length > 0) {
    return `${citation.doc_name} · ${locParts.join(" · ")}`;
  }
  return citation.doc_name;
}

function statusBanner(status: CitationSourceStatus): string | null {
  if (status === "document_deleted") return SOURCE_DELETED_LABEL;
  if (status === "chunk_stale") return CHUNK_STALE_LABEL;
  if (status === "source_inaccessible") return SOURCE_INACCESSIBLE_LABEL;
  return null;
}

function initialSourceStatus(citation: Citation): CitationSourceStatus {
  if (
    citation.source_status &&
    citation.source_status !== "available"
  ) {
    return citation.source_status;
  }
  return "available";
}

function needsResolve(citation: Citation): boolean {
  return (
    citation.source_status == null || citation.source_status === "available"
  );
}

export function CitationPreview({
  kbId,
  citation,
  scopeMode = "kb",
}: CitationPreviewProps) {
  const { workspace, isTeamWorkspace } = useWorkspace();
  const { departmentId } = useDepartment();
  const chatScope = {
    workspace,
    departmentId: isTeamWorkspace ? departmentId : null,
  };

  const [sourceStatus, setSourceStatus] = useState<CitationSourceStatus>(
    initialSourceStatus(citation),
  );
  const [resolving, setResolving] = useState(needsResolve(citation));

  useEffect(() => {
    if (!needsResolve(citation)) {
      setSourceStatus(initialSourceStatus(citation));
      setResolving(false);
      return;
    }

    let cancelled = false;
    setResolving(true);

    void resolveCitation(
      kbId,
      citation.document_id,
      citation.chunk_id,
      chatScope,
    )
      .then((result) => {
        if (!cancelled) {
          setSourceStatus(result.source_status);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSourceStatus("document_deleted");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setResolving(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [kbId, citation.document_id, citation.chunk_id, citation.source_status, chatScope.departmentId, chatScope.workspace]);

  const banner = statusBanner(sourceStatus);
  const canOpenOriginal =
    !resolving && sourceStatus === "available";
  const labelMode = scopeMode;

  return (
    <div className="cite-preview">
      <strong>预览 · {previewTitle(citation)}</strong>
      {banner && (
        <p className="mt-2 text-[0.72rem] font-medium text-[var(--status-err-text)]">
          {banner}
        </p>
      )}
      <p className="mt-1.5">{citation.excerpt}</p>
      {canOpenOriginal && (
        <Link
          to={previewPathForCitation(kbId, citation)}
          className="mt-2 inline-block text-[0.72rem] text-accent hover:underline"
        >
          查看原文 →
        </Link>
      )}
      {!resolving && sourceStatus === "chunk_stale" && (
        <Link
          to={`/knowledge-bases/${kbId}/documents/${citation.document_id}`}
          className="mt-2 inline-block text-[0.72rem] text-accent hover:underline"
        >
          查看当前文档 · {formatCitationLabel(citation, labelMode)}
        </Link>
      )}
    </div>
  );
}

export {
  CHUNK_STALE_LABEL,
  SOURCE_DELETED_LABEL,
  SOURCE_INACCESSIBLE_LABEL,
};
