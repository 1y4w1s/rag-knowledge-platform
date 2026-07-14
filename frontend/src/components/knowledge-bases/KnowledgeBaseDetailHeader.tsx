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
    <header className="mb-[18px] flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 className="font-serif text-[1.05rem] font-semibold tracking-[0.02em] text-foreground">
          {kb.name}
        </h2>
        {kb.description ? (
          <p className="mt-1 text-[0.78rem] text-muted">{kb.description}</p>
        ) : (
          <p className="mt-1 text-[0.78rem] text-muted">管理文档与入库状态</p>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {uploadAllowed ? (
          <Button type="button" variant="outline" size="sm" onClick={onEdit}>
            编辑
          </Button>
        ) : (
          <MemberWriteBlockedButton
            variant="outline"
            size="sm"
            onBlocked={onMemberWriteBlocked}
          >
            编辑
          </MemberWriteBlockedButton>
        )}
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
        {chatAllowed ? (
          <Button asChild size="sm">
            <Link to={`/knowledge-bases/${kbId}/chat`}>开始对话</Link>
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
