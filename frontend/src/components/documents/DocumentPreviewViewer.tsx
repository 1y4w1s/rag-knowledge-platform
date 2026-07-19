import { useMemo } from "react";
import { Link } from "react-router-dom";
import { marked } from "marked";
import DOMPurify from "dompurify";

interface DocumentPreviewViewerProps {
  mode: "pdf" | "text" | "markdown" | "image" | "unsupported";
  pdfSrc: string | null;
  imageSrc: string | null;
  textContent: string | null;
  filename: string;
  pageHint?: number | null;
  downloadHref?: string;
  chatHref?: string;
  onLoadError?: () => void;
}

export function DocumentPreviewViewer({
  mode,
  pdfSrc,
  imageSrc,
  textContent,
  filename,
  pageHint,
  downloadHref,
  chatHref,
  onLoadError,
}: DocumentPreviewViewerProps) {
  if (mode === "pdf") {
    return (
      <div className="preview-pdf-wrap">
        {pageHint != null && pageHint > 0 && (
          <p className="preview-page-hint">第 {pageHint} 页</p>
        )}
        {pdfSrc ? (
          <iframe
            title={`${filename} 预览`}
            src={pdfSrc}
            className="preview-pdf-frame"
            onError={onLoadError}
          />
        ) : (
          <div className="preview-pdf-loading" aria-busy="true">
            正在加载…
          </div>
        )}
      </div>
    );
  }

  if (mode === "image" && imageSrc != null) {
    return (
      <div className="preview-image-wrap">
        <img src={imageSrc} alt={filename} className="preview-image" />
      </div>
    );
  }

  if (mode === "markdown" && textContent != null) {
    return <MarkdownRenderer content={textContent} />;
  }

  if (mode === "text" && textContent != null) {
    return (
      <article className="preview-text-body">
        <pre className="preview-text-pre">{textContent}</pre>
      </article>
    );
  }

  return (
    <div className="flex min-h-[320px] items-center justify-center px-6">
      <div className="preview-unsupported">
        <h4>暂不支持在线预览</h4>
        <div className="preview-unsupported-actions">
          {downloadHref ? (
            <a className="preview-action-primary" href={downloadHref} download={filename}>
              下载原文件
            </a>
          ) : null}
          {chatHref ? (
            <Link className="preview-action-link" to={chatHref}>
              提问
            </Link>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MarkdownRenderer({ content }: { content: string }) {
  const html = useMemo(() => {
    try {
      const raw = marked.parse(content, {
        breaks: true,
        gfm: true,
        async: false,
      }) as string;
      return DOMPurify.sanitize(raw);
    } catch {
      return `<pre class="markdown-fallback">${content}</pre>`;
    }
  }, [content]);

  return (
    <article className="preview-text-body">
      <div
        className="markdown-body preview-md-body"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </article>
  );
}
