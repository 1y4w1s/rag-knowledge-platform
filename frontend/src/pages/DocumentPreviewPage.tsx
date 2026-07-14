import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { DocumentMetaPanel } from "@/components/documents/DocumentMetaPanel";
import { DocumentPreviewViewer } from "@/components/documents/DocumentPreviewViewer";
import { PreviewPageToolbar } from "@/components/documents/PreviewPageToolbar";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import {
  fetchDocument,
  fetchDocumentPreview,
  isPdfPreview,
  isTextPreview,
  SOURCE_DOCUMENT_DELETED_MSG,
  type Document,
} from "@/lib/document-api";
import { fetchKnowledgeBase, type KnowledgeBase } from "@/lib/knowledge-base-api";
import { buildPreviewBreadcrumb } from "@/lib/breadcrumb-links";
import { persistRecentKbId } from "@/lib/use-sidebar-chat-kb-id";
import { useWorkspace } from "@/lib/workspace-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";

type PreviewMode = "pdf" | "text" | "unsupported";

const PREVIEW_SHELL =
  "-m-6 flex h-[calc(100vh-3.25rem)] flex-col overflow-hidden";

function parsePageHint(hash: string): number | null {
  const match = hash.match(/^#page=(\d+)$/);
  if (!match) return null;
  const page = Number(match[1]);
  return page > 0 ? page : null;
}

function PreviewSkeleton() {
  return (
    <div className={PREVIEW_SHELL}>
      <div className="preview-toolbar animate-pulse bg-white/50" />
      <div className="preview-split min-h-0 flex-1">
        <div className="preview-main animate-pulse bg-white/60" />
        <aside className="preview-side">
          <div className="preview-side-card h-64 animate-pulse bg-white/60" />
        </aside>
      </div>
    </div>
  );
}

export function DocumentPreviewPage() {
  const { id, docId } = useParams<{ id: string; docId: string }>();
  const location = useLocation();
  const { workspace } = useWorkspace();
  const { setOverride } = useShellBreadcrumb();
  const pageHint = parsePageHint(location.hash);

  const [kb, setKb] = useState<KnowledgeBase | null>(null);
  const [document, setDocument] = useState<Document | null>(null);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("unsupported");
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const blobUrlRef = useRef<string | null>(null);
  const loadIdRef = useRef(0);

  const revokeBlobUrl = useCallback(() => {
    if (blobUrlRef.current) {
      URL.revokeObjectURL(blobUrlRef.current);
      blobUrlRef.current = null;
    }
    setBlobUrl(null);
  }, []);

  const loadPage = useCallback(async () => {
    if (!id || !docId) return;
    const loadId = ++loadIdRef.current;

    setLoading(true);
    setError(null);
    revokeBlobUrl();
    setTextContent(null);
    setPreviewMode("unsupported");

    try {
      const [kbData, docData] = await Promise.all([
        fetchKnowledgeBase(id),
        fetchDocument(id, docId),
      ]);
      if (loadId !== loadIdRef.current) return;
      setKb(kbData);
      setDocument(docData);
      persistRecentKbId(id, workspace);
      globalThis.document.title = `睿阁 · ${docData.filename}`;
      const metaDescription = globalThis.document.querySelector('meta[name="description"]') as HTMLMetaElement | null;
      if (metaDescription) {
        metaDescription.content = `在线预览 ${docData.filename} 的内容与元数据。`;
      }
      setOverride(buildPreviewBreadcrumb(id, kbData, docData));

      const { blob, contentType } = await fetchDocumentPreview(id, docId);
      if (loadId !== loadIdRef.current) return;

      if (isPdfPreview(docData.file_type, contentType)) {
        const url = URL.createObjectURL(blob);
        blobUrlRef.current = url;
        setBlobUrl(url);
        setPreviewMode("pdf");
        return;
      }

      if (isTextPreview(docData.file_type, contentType)) {
        setTextContent(await blob.text());
        setPreviewMode("text");
        return;
      }

      setPreviewMode("unsupported");
    } catch (err) {
      if (loadId !== loadIdRef.current) return;
      setKb(null);
      setDocument(null);
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      if (loadId === loadIdRef.current) {
        setLoading(false);
      }
    }
  }, [docId, id, workspace, revokeBlobUrl, setOverride]);

  useEffect(() => {
    void loadPage();
    return () => {
      loadIdRef.current += 1;
      setOverride(null);
      globalThis.document.title = "睿阁";
      revokeBlobUrl();
    };
  }, [loadPage, revokeBlobUrl, setOverride]);

  if (!id || !docId) {
    return (
      <AlertBanner className="rounded-lg">无效的文档地址</AlertBanner>
    );
  }

  if (loading) {
    return <PreviewSkeleton />;
  }

  if (error || !document || !kb) {
    return (
      <AlertBanner
        action={
          <>
            <Button type="button" variant="outline" size="sm" onClick={loadPage}>
              重试
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to={`/knowledge-bases/${id}`}>返回资料库</Link>
            </Button>
          </>
        }
      >
        {error ?? SOURCE_DOCUMENT_DELETED_MSG}
      </AlertBanner>
    );
  }

  return (
    <div className={PREVIEW_SHELL}>
      <PreviewPageToolbar
        kbId={id}
        kbName={kb.name}
        filename={document.filename}
      />
      <div className="preview-split min-h-0 flex-1">
        <div className="preview-main">
          <DocumentPreviewViewer
            mode={previewMode}
            blobUrl={blobUrl}
            textContent={textContent}
            filename={document.filename}
            pageHint={pageHint}
          />
        </div>
        <DocumentMetaPanel kbId={id} document={document} />
      </div>
    </div>
  );
}
