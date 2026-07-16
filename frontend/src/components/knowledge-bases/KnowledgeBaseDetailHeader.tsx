import { Link } from "react-router-dom";
import { Upload } from "lucide-react";

import { DocumentUploadButton } from "@/components/knowledge-bases/DocumentUploadButton";
import { MemberWriteBlockedButton } from "@/components/knowledge-bases/MemberWriteBlockedButton";
import { Button } from "@/components/ui/button";
import type { KnowledgeBase } from "@/lib/knowledge-base-api";

type KnowledgeBaseDetailHeaderProps = {
  kb: KnowledgeBase;
  kbId: string;
  uploadAllowed: boolean;
  chatAllowed?: boolean;
  uploading: boolean;
  onEdit: () => void;
  onUpload: (files: File[]) => void;
  onMemberWriteBlocked: () => void;
  onChatBlocked?: () => void;
};

export function KnowledgeBaseDetailHeader({
  kb,
  kbId,
  uploadAllowed,
  chatAllowed = true,
  uploading,
  onEdit,
  onUpload,
  onMemberWriteBlocked,
  onChatBlocked,
}: KnowledgeBaseDetailHeaderProps) {
  return (
    <header className="mb-7 border-b border-[var(--line2)] pb-5 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 flex-1">
        <Link
          to="/knowledge-bases"
          className="inline-flex items-center gap-1 text-[0.72rem] text-muted hover:text-foreground transition-colors"
        >
          <span aria-hidden>←</span> 返回资料库
        </Link>
        <h1 className="mt-2 font-serif text-[1.5rem] font-semibold text-foreground leading-tight">
          {kb.name}
        </h1>
        {kb.description ? (
          <p className="mt-1.5 text-[0.82rem] text-muted">{kb.description}</p>
        ) : (
          <p className="mt-1.5 text-[0.82rem] text-muted">管理文档与入库状态</p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 shrink-0">
        {uploadAllowed ? (
          <DocumentUploadButton uploading={uploading} onFilesSelected={onUpload} />
        ) : (
          <MemberWriteBlockedButton
            variant="outline"
            size="sm"
            onBlocked={onMemberWriteBlocked}
          >
            <Upload className="h-3.5 w-3.5" aria-hidden />
            上传文档
          </MemberWriteBlockedButton>
        )}
        {uploadAllowed ? (
          <Button type="button" variant="ghost" size="sm" onClick={onEdit}>
            编辑
          </Button>
        ) : (
          <MemberWriteBlockedButton
            variant="ghost"
            size="sm"
            onBlocked={onMemberWriteBlocked}
          >
            编辑
          </MemberWriteBlockedButton>
        )}
        {chatAllowed ? (
          <Button asChild size="sm" variant="brand">
            <Link to={`/knowledge-bases/${kbId}/chat`}>开始对话 →</Link>
          </Button>
        ) : (
          <Button
            type="button"
            size="sm"
            className="cursor-not-allowed opacity-60"
            onClick={onChatBlocked}
          >
            开始对话
          </Button>
        )}
      </div>
    </header>
  );
}
