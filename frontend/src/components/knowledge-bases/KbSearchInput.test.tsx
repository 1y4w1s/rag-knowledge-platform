import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import { KbSearchInput } from "@/components/knowledge-bases/KbSearchInput";

describe("KbSearchInput", () => {
  it("renders input with search icon", () => {
    render(
      <KbSearchInput
        id="kb-search"
        value=""
        placeholder="搜索资料库…"
        onChange={() => {}}
      />,
    );

    const input = screen.getByLabelText("搜索资料库…") as HTMLInputElement;
    expect(input).toBeDefined();
    expect(input.value).toBe("");
  });

  it("calls onChange when typing", () => {
    const onChange = vi.fn();
    render(
      <KbSearchInput
        id="kb-search"
        value=""
        placeholder="搜索资料库…"
        onChange={onChange}
      />,
    );

    const input = screen.getByLabelText("搜索资料库…");
    fireEvent.change(input, { target: { value: "产品" } });
    expect(onChange).toHaveBeenCalledWith("产品");
  });

  it("shows clear button when value is non-empty and clears on click", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <KbSearchInput
        id="kb-search"
        value=""
        placeholder="搜索资料库…"
        onChange={onChange}
      />,
    );

    expect(screen.queryByLabelText("清除搜索")).toBeNull();

    rerender(
      <KbSearchInput
        id="kb-search"
        value="产品"
        placeholder="搜索资料库…"
        onChange={onChange}
      />,
    );

    const clearBtn = screen.getByLabelText("清除搜索");
    expect(clearBtn).toBeDefined();

    fireEvent.click(clearBtn);
    expect(onChange).toHaveBeenCalledWith("");
  });
});
