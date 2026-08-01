import type { ReactNode } from "react";

/**
 * 渲染发现层 snippet：仅信任自有 API 的 `<mark>`，其余文本转义。
 */
export function SearchSnippet({
  snippet,
  className,
}: {
  snippet: string;
  className?: string;
}) {
  return <span className={className}>{parseMarkedSnippet(snippet)}</span>;
}

function parseMarkedSnippet(raw: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const re = /<mark>(.*?)<\/mark>/gi;
  let last = 0;
  let match: RegExpExecArray | null;
  let key = 0;
  while ((match = re.exec(raw)) !== null) {
    if (match.index > last) {
      nodes.push(raw.slice(last, match.index));
    }
    nodes.push(
      <mark
        key={`m-${key++}`}
        className="rounded-sm bg-[var(--accent-soft,rgba(180,120,60,0.18))] text-foreground"
      >
        {match[1]}
      </mark>,
    );
    last = match.index + match[0].length;
  }
  if (last < raw.length) {
    nodes.push(raw.slice(last));
  }
  return nodes.length > 0 ? nodes : [raw];
}
