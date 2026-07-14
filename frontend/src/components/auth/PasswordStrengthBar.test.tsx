import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PasswordStrengthBar } from "./PasswordStrengthBar";

describe("PasswordStrengthBar", () => {
  it("renders nothing when password is empty", () => {
    const { container } = render(<PasswordStrengthBar password="" />);
    expect(container.firstChild).toBeNull();
  });

  it("renders a meter with 3 segments for a non-empty password", () => {
    const { container } = render(<PasswordStrengthBar password="short" />);
    const meter = container.querySelector('[role="meter"]');
    expect(meter).toBeTruthy();
    expect(meter?.querySelectorAll("span")).toHaveLength(3);
  });

  it("uses the danger (err) token for a weak password", () => {
    render(<PasswordStrengthBar password="short" />);
    const label = screen.getByText(/弱/);
    expect(label.className).toContain("status-err-text");
  });

  it("uses the ok (green) token for a strong password", () => {
    render(<PasswordStrengthBar password="Password123!" />);
    const label = screen.getByText(/强/);
    expect(label.className).toContain("status-ok-text");
  });

  it("reflects the strength level via aria-valuenow", () => {
    const { container, rerender } = render(<PasswordStrengthBar password="short" />);
    expect(container.querySelector('[role="meter"]')?.getAttribute("aria-valuenow")).toBe("1");
    rerender(<PasswordStrengthBar password="Password123!" />);
    expect(container.querySelector('[role="meter"]')?.getAttribute("aria-valuenow")).toBe("3");
  });
});
