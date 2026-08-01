/**
 * NW-10 I-2：评测模式默认展开 SVG 面板（非强制催评）。
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { MessageFeedback } from "@/components/chat/MessageFeedback";

vi.mock("@/lib/feedback-api", () => ({
  getMessageFeedback: vi.fn(async () => null),
  submitFeedback: vi.fn(),
  deleteFeedback: vi.fn(),
}));

describe("MessageFeedback evalMode", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("expands thumbs panel when evalMode is on", async () => {
    render(
      <MessageFeedback
        messageId="m1"
        content="正常回答"
        citations={[{ source_status: "available" }]}
        evalMode
      />,
    );
    await waitFor(() => {
      expect(screen.getByTestId("feedback-thumbs")).toBeTruthy();
    });
    expect(screen.getByTestId("feedback-up")).toBeTruthy();
    expect(screen.getByTestId("feedback-down")).toBeTruthy();
  });

  it("keeps thumbs hidden for normal answers without evalMode", () => {
    render(
      <MessageFeedback
        messageId="m1"
        content="正常回答"
        citations={[{ source_status: "available" }]}
      />,
    );
    expect(screen.queryByTestId("feedback-thumbs")).toBeNull();
    expect(screen.getByTestId("feedback-more-btn")).toBeTruthy();
  });
});
