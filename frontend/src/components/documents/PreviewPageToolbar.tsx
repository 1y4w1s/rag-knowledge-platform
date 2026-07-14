import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";

interface PreviewPageToolbarProps {
  kbId: string;
  kbName: string;
  filename: string;
}

export function PreviewPageToolbar({
  kbId,
  kbName,
  filename,
}: PreviewPageToolbarProps) {
  return (
    <div className="preview-toolbar">
      <Link
        to={`/knowledge-bases/${kbId}`}
        className="preview-back-link"
      >
        <ChevronLeft size={15} strokeWidth={1.8} aria-hidden="true" />
        返回资料库
      </Link>
      <span className="hidden text-muted sm:inline">·</span>
      <span className="hidden truncate text-muted sm:inline">{kbName}</span>
      <span className="ml-auto max-w-[min(420px,50%)] truncate text-[0.8125rem] font-medium text-foreground">
        {filename}
      </span>
    </div>
  );
}
