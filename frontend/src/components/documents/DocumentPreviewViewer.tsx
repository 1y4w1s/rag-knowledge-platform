interface DocumentPreviewViewerProps {
  mode: "pdf" | "text" | "unsupported";
  blobUrl: string | null;
  textContent: string | null;
  filename: string;
  pageHint?: number | null;
}

export function DocumentPreviewViewer({
  mode,
  blobUrl,
  textContent,
  filename,
  pageHint,
}: DocumentPreviewViewerProps) {
  if (mode === "pdf") {
    return (
      <div className="preview-pdf-wrap">
        {pageHint != null && pageHint > 0 && (
          <p className="preview-page-hint">引用定位 · 第 {pageHint} 页</p>
        )}
        {blobUrl ? (
          <iframe
            title={`${filename} 预览`}
            src={blobUrl}
            className="preview-pdf-frame"
          />
        ) : (
          <div className="preview-pdf-loading" aria-busy="true">
            正在加载文档预览…
          </div>
        )}
      </div>
    );
  }

  if (mode === "text" && textContent != null) {
    return (
      <article className="preview-text-body">
        <pre className="w-full whitespace-pre-wrap rounded-lg border border-[var(--line2)] bg-white p-7 font-mono text-[0.8125rem] leading-relaxed text-[var(--mut-warm)] shadow-sm">
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
