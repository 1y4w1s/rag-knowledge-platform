import { Fragment, type ReactNode } from "react";

interface SearchSnippetProps {
  html: string;
}

const MARK_OPEN_RE = /<mark\b[^>]*>/i;
const MARK_CLOSE = "</mark>";

/**
 * 把 ts_headline 输出的高亮片段安全地渲染为 React 节点。
 *
 * 仅把 <mark> 识别为高亮标签；其余内容一律作为纯文本交给 React 转义。
 * 因此彻底移除了 dangerouslySetInnerHTML，且对内容里夹带的 `<` `>` `&`
 * 也会正确转义（旧版会把它们误当成标签），比受控注入更安全。
 */
function renderHeadline(html: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let rest = html ?? "";
  let key = 0;

  while (rest.length > 0) {
    const openMatch = MARK_OPEN_RE.exec(rest);
    if (!openMatch) {
      if (rest) nodes.push(<Fragment key={key++}>{rest}</Fragment>);
      break;
    }
    const openIdx = openMatch.index;
    const before = rest.slice(0, openIdx);
    if (before) nodes.push(<Fragment key={key++}>{before}</Fragment>);

    const afterOpen = rest.slice(openIdx + openMatch[0].length);
    const closeIdx = afterOpen.indexOf(MARK_CLOSE);
    if (closeIdx === -1) {
      // 未闭合：剩余整体作为纯文本，绝不丢内容、也不当标签解析
      nodes.push(<Fragment key={key++}>{afterOpen}</Fragment>);
      break;
    }
    const inner = afterOpen.slice(0, closeIdx);
    nodes.push(
      <mark
        key={key++}
        className="rounded-sm bg-[rgba(166,139,107,0.22)] px-0.5 text-foreground"
      >
        {inner}
      </mark>,
    );
    rest = afterOpen.slice(closeIdx + MARK_CLOSE.length);
  }
  return nodes;
}

/** 渲染正文搜索 ts_headline 高亮（仅允许 <mark>，安全解析、无 dangerouslySetInnerHTML）。 */
export function SearchSnippet({ html }: SearchSnippetProps) {
  if (!html) return null;
  return (
    <span className="search-snippet text-xs leading-relaxed text-[var(--mut)]">
      {renderHeadline(html)}
    </span>
  );
}
