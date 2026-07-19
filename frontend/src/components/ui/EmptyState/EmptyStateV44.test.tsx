import "@testing-library/jest-dom/vitest";
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyStateV44 } from "./EmptyStateV44";
import { ASK_SCENE } from "./scenes";

describe("EmptyStateV44", () => {
  it("renders all step icons with outline stroke and no black fill", () => {
    render(<EmptyStateV44 scene={ASK_SCENE} />);
    const stepHeaders = document.querySelectorAll(".empty-step-h");
    expect(stepHeaders.length).toBe(ASK_SCENE.steps.length);

    stepHeaders.forEach((header, i) => {
      const svg = header.querySelector("svg");
      expect(svg).toBeInTheDocument();
      expect(svg).toHaveClass("ico");
      const path = svg?.querySelector("path");
      expect(path).toHaveAttribute("fill", "none");
      expect(path).toHaveAttribute("stroke", "currentColor");
      expect(path).toHaveAttribute("stroke-width", "1.8");
      expect(header).toHaveTextContent(ASK_SCENE.steps[i].title);
    });
  });

  it("renders hero CTA buttons with icons", () => {
    render(<EmptyStateV44 scene={ASK_SCENE} />);
    const buttons = document.querySelectorAll(".empty-hero .actions .dash-btn");
    expect(buttons.length).toBe(3);
    buttons.forEach((btn) => {
      const svg = btn.querySelector("svg");
      expect(svg).toBeInTheDocument();
      const path = svg?.querySelector("path");
      expect(path).toHaveAttribute("fill", "none");
    });
  });
});
