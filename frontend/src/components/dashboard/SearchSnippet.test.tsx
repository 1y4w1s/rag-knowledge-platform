import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchSnippet } from "./SearchSnippet";

describe("SearchSnippet (safe parser, no dangerouslySetInnerHTML)", () => {
  it("renders plain text when there is no <mark>", () => {
    const { container } = render(<SearchSnippet html="普通的一段搜索摘要" />);
    expect(screen.getByText("普通的一段搜索摘要")).toBeTruthy();
    expect(container.querySelector("mark")).toBeNull();
  });

  it("renders a single highlight as a <mark> with the highlight class", () => {
    const { container } = render(<SearchSnippet html="这是 <mark>匹配词</mark> 的摘要" />);
    const mark = container.querySelector("mark");
    expect(mark).not.toBeNull();
    expect(mark?.textContent).toBe("匹配词");
    expect(mark?.className).toContain("bg-[rgba(166,139,107,0.22)]");
  });

  it("renders multiple highlights", () => {
    const { container } = render(
      <SearchSnippet html="<mark>苹果</mark> 和 <mark>香蕉</mark> 都出现了" />,
    );
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(2);
    expect(marks[0].textContent).toBe("苹果");
    expect(marks[1].textContent).toBe("香蕉");
  });

  it("escapes embedded HTML in the snippet text (no XSS surface)", () => {
    const { container } = render(
      <SearchSnippet html='前面 <script>alert("xss")</script> 后面 <mark>命中</mark>' />,
    );
    // 危险标签被当作纯文本，而不是真实 DOM 节点
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain('<script>alert("xss")</script>');
    // 仅有一个真实的高亮 mark
    const marks = container.querySelectorAll("mark");
    expect(marks.length).toBe(1);
    expect(marks[0].textContent).toBe("命中");
    // 命中词正常出现在末尾
    expect(container.textContent).toContain("命中");
  });

  it("tolerates an unclosed <mark> without crashing or dropping text", () => {
    const { container } = render(<SearchSnippet html="开头 <mark>未闭合高亮" />);
    // 未闭合部分整体作为文本保留，不产生真实 mark 节点
    expect(container.querySelector("mark")).toBeNull();
    expect(container.textContent).toBe("开头 未闭合高亮");
  });

  it("renders nothing for empty input", () => {
    const { container } = render(<SearchSnippet html="" />);
    expect(container.firstChild).toBeNull();
  });
});
