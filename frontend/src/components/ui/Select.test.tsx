import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Select, type SelectOption } from "./Select";

const OPTIONS: SelectOption[] = [
  { value: "", label: "全部" },
  { value: "a", label: "动作 A" },
  { value: "b", label: "动作 B" },
];

describe("Select", () => {
  it("renders the selected option label", () => {
    render(<Select id="f" value="a" options={OPTIONS} onChange={vi.fn()} />);
    expect(screen.getByText("动作 A")).toBeDefined();
  });

  it("renders the placeholder when value has no matching option", () => {
    render(
      <Select id="f" value="x" options={OPTIONS} onChange={vi.fn()} placeholder="请选择" />,
    );
    expect(screen.getByText("请选择")).toBeDefined();
  });

  it("exposes listbox semantics on the trigger", () => {
    render(<Select id="f" value="" options={OPTIONS} onChange={vi.fn()} />);
    const trigger = screen.getByRole("button");
    expect(trigger.getAttribute("aria-haspopup")).toBe("listbox");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    const opts = screen.getAllByRole("option");
    expect(opts.length).toBe(OPTIONS.length);
  });

  it("opens the menu and selects an option by click", () => {
    const onChange = vi.fn();
    render(<Select id="f" value="" options={OPTIONS} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "全部" }));
    expect(screen.getByRole("listbox")).toBeDefined();
    fireEvent.click(screen.getByText("动作 B"));
    expect(onChange).toHaveBeenCalledWith("b");
  });

  it("selects an option via keyboard", () => {
    const onChange = vi.fn();
    render(<Select id="f" value="" options={OPTIONS} onChange={onChange} />);
    const trigger = screen.getByRole("button");
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    fireEvent.keyDown(trigger, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("closes the menu on Escape", () => {
    render(<Select id="f" value="" options={OPTIONS} onChange={vi.fn()} />);
    const trigger = screen.getByRole("button");
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    fireEvent.keyDown(trigger, { key: "Escape" });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
  });
});
