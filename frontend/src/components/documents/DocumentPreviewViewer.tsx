import { useMemo } from "react";
import { marked } from "marked";

interface DocumentPreviewViewerProps {
  mode: "pdf" | "text" | "markdown" | "image" | "unsupported";
  pdfSrc: string | null;
  imageSrc: string | null;
  textContent: string | null;
  filename: string;
  pageHint?: number | null;
  onLoadError?: () => void;
}

export function DocumentPreviewViewer({
  mode,
  pdfSrc,
  imageSrc,
  textContent,
  filename,
  pageHint,
  onLoadError,
}: DocumentPreviewViewerProps) {
  if (mode === "pdf") {
    return (
      <div className="preview-pdf-wrap">
        {pageHint != null && pageHint > 0 && (
          <p className="preview-page-hint">引用定位 · 第 {pageHint} 页</p>
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
            正在加载文档预览…
          </div>
        )}
      </div>
    );
  }

  if (mode === "image" && imageSrc != null) {
    return (
      <div className="flex min-h-[320px] items-center justify-center p-6">
        <img
          src={imageSrc}
          alt={filename}
          className="max-h-[calc(100vh-12rem)] max-w-full rounded-lg object-contain shadow-[var(--card-shadow)]"
        />
      </div>
    );
  }

  if (mode === "markdown" && textContent != null) {
    return <MarkdownRenderer content={textContent} />;
  }

  if (mode === "text" && textContent != null) {
    return (
      <article className="preview-text-body">
        <pre className="mx-auto w-full max-w-[760px] whitespace-pre-wrap rounded-[14px] border border-[var(--line2)] bg-[var(--paper,#fdfbf7)] p-8 font-mono text-[0.875rem] leading-[1.8] text-[var(--text,#2a221b)] shadow-[var(--card-shadow)]">
          {textContent}
        </pre>
      </article>
    );
  }

  return (
    <div className="flex min-h-[320px] items-center justify-center px-6">
      <div className="preview-unsupported">
        <div className="u-ico">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M14 3v5h5" />
            <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
            <path d="M9 13h6M9 17h4" />
          </svg>
        </div>
        <h4>暂不支持在线预览此格式</h4>
        <p>当前仅支持 PDF 与纯文本（TXT / MD）在浏览器内预览。你可下载后使用本地工具查看。</p>
      </div>
    </div>
  );
}

/** 渲染 Markdown 内容为带样式的 HTML */
function MarkdownRenderer({ content }: { content: string }) {
  const html = useMemo(() => {
    try {
      return marked.parse(content, { breaks: true, gfm: true });
    } catch {
      return `<pre class="markdown-fallback">${content}</pre>`;
    }
  }, [content]);

  return (
    <article className="preview-text-body">
      <div
        className="markdown-body mx-auto w-full max-w-[760px] rounded-[14px] border border-[var(--line2)] bg-white p-8 shadow-[var(--card-shadow)]"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </article>
  );
}
