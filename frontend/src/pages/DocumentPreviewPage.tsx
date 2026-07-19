import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { DocumentMetaPanel } from "@/components/documents/DocumentMetaPanel";
import { DocumentPreviewViewer } from "@/components/documents/DocumentPreviewViewer";
import { PreviewPageToolbar } from "@/components/documents/PreviewPageToolbar";
import { AlertBanner } from "@/components/ui/AlertBanner";
import { Button } from "@/components/ui/button";
import {
  buildDocumentPreviewUrl,
  fetchDocument,
  fetchDocumentPreview,
  isImagePreview,
  isTextPreview,
  SOURCE_DOCUMENT_DELETED_MSG,
  type Document,
} from "@/lib/document-api";
import { fetchKnowledgeBase, type KnowledgeBase } from "@/lib/knowledge-base-api";
import { buildPreviewBreadcrumb } from "@/lib/breadcrumb-links";
import { persistRecentKbId } from "@/lib/use-sidebar-chat-kb-id";
import { useWorkspace } from "@/lib/workspace-context";
import { useShellBreadcrumb } from "@/lib/shell-breadcrumb";

type PreviewMode = "pdf" | "text" | "markdown" | "image" | "unsupported";

const PREVIEW_SHELL = "full-bleed";

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
  const [textContent, setTextContent] = useState<string | null>(null);
  const [pdfSrc, setPdfSrc] = useState<string | null>(null);
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadIdRef = useRef(0);

  const loadPage = useCallback(async () => {
    if (!id || !docId) return;
    const loadId = ++loadIdRef.current;

    setLoading(true);
    setError(null);
    setTextContent(null);
    setPdfSrc(null);
    setImageSrc(null);
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

      if (docData.file_type === "pdf") {
        // PDF 走同源 iframe 直链（query token 后端鉴权），不用 blob —— Chrome 拒绝 iframe 嵌入 blob URL
        if (loadId !== loadIdRef.current) return;
        setPdfSrc(buildDocumentPreviewUrl(id, docId));
        setPreviewMode("pdf");
        return;
      }

      const { blob, contentType } = await fetchDocumentPreview(id, docId);
      if (loadId !== loadIdRef.current) return;

      if (isTextPreview(docData.file_type, contentType)) {
        const text = await blob.text();
        setTextContent(text);
        if (docData.file_type === "md") {
          setPreviewMode("markdown");
        } else {
          setPreviewMode("text");
        }
        return;
      }

      if (isImagePreview(docData.file_type)) {
        if (loadId !== loadIdRef.current) return;
        setImageSrc(URL.createObjectURL(blob));
        setPreviewMode("image");
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
  }, [docId, id, workspace, setOverride]);

  useEffect(() => {
    void loadPage();
    return () => {
      // 释放图片 blob URL
      if (imageSrc?.startsWith("blob:")) {
        URL.revokeObjectURL(imageSrc);
      }
      loadIdRef.current += 1;
      setOverride(null);
      globalThis.document.title = "睿阁";
    };
  }, [loadPage, setOverride]);

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
        fileType={document.file_type}
      />
      <div className="preview-split min-h-0 flex-1">
        <div className="preview-main">
          <DocumentPreviewViewer
            mode={previewMode}
            pdfSrc={pdfSrc}
            imageSrc={imageSrc}
            textContent={textContent}
            filename={document.filename}
            pageHint={pageHint}
            downloadHref={buildDocumentPreviewUrl(id, docId)}
            chatHref={`/knowledge-bases/${id}/chat`}
            onLoadError={() => setError("PDF 加载失败，请重试")}
          />
        </div>
        <DocumentMetaPanel
          kbId={id}
          document={document}
          showDownload={previewMode === "unsupported"}
        />
      </div>
    </div>
  );
}
