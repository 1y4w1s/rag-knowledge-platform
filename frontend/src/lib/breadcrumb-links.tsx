import { Link } from "react-router-dom";

import type { Document } from "@/lib/document-api";
import type { KnowledgeBase } from "@/lib/knowledge-base-api";

const crumbNavClass = "flex flex-wrap items-center gap-1";

export function buildKbDetailBreadcrumb(kbName: string) {
  return (
    <nav aria-label="breadcrumb" className={crumbNavClass}>
      <Link to="/knowledge-bases" className="crumb-link">
        资料库
      </Link>
      <span className="text-muted">/</span>
      <b>{kbName}</b>
    </nav>
  );
}

export function buildChatBreadcrumb(kbId: string, kbName: string) {
  return (
    <nav aria-label="breadcrumb" className={crumbNavClass}>
      <span className="text-muted">对话</span>
      <span className="text-muted">/</span>
      <Link to={`/knowledge-bases/${kbId}`} className="crumb-link">
        {kbName}
      </Link>
    </nav>
  );
}

export function buildPreviewBreadcrumb(
  kbId: string,
  kb: KnowledgeBase,
  document: Document,
) {
  return (
    <nav aria-label="breadcrumb" className={crumbNavClass}>
      <Link to="/knowledge-bases" className="crumb-link">
        资料库
      </Link>
      <span className="text-muted">/</span>
      <Link to={`/knowledge-bases/${kbId}`} className="crumb-link">
        {kb.name}
      </Link>
      <span className="text-muted">/</span>
      <b>{document.filename}</b>
    </nav>
  );
}
