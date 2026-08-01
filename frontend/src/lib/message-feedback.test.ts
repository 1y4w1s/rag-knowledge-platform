import { describe, expect, it } from "vitest";

import {
  FEEDBACK_PROMPT_REFUSE,
  FEEDBACK_PROMPT_STALE,
  NO_CONTEXT_REPLY_EN,
  NO_CONTEXT_REPLY_ZH,
  areAllCitationsUnavailable,
  canUseFeedbackEvalMode,
  isEvalQueryParam,
  isFeedbackEvalModeActive,
  isRefuseAnswer,
  lightFeedbackPromptLabel,
  shouldShowLightFeedbackPrompt,
} from "@/lib/message-feedback";

describe("message-feedback helpers", () => {
  it("detects refuse answers by exact fixed copy", () => {
    expect(isRefuseAnswer(NO_CONTEXT_REPLY_ZH, 0)).toBe(true);
    expect(isRefuseAnswer(NO_CONTEXT_REPLY_EN, 0)).toBe(true);
    expect(isRefuseAnswer("知识库中未找到相关内容", 0)).toBe(false);
    expect(isRefuseAnswer(NO_CONTEXT_REPLY_ZH, 1)).toBe(false);
  });

  it("detects all-unavailable citations", () => {
    expect(
      areAllCitationsUnavailable([
        { source_status: "document_deleted" },
        { source_status: "chunk_stale" },
      ]),
    ).toBe(true);
    expect(
      areAllCitationsUnavailable([
        { source_status: "document_deleted" },
        { source_status: "available" },
      ]),
    ).toBe(false);
    expect(areAllCitationsUnavailable([])).toBe(false);
  });

  it("shows light prompt only for refuse/all-gray with message id", () => {
    expect(
      shouldShowLightFeedbackPrompt({
        messageId: "m1",
        content: NO_CONTEXT_REPLY_ZH,
        citations: [],
      }),
    ).toBe(true);
    expect(
      shouldShowLightFeedbackPrompt({
        content: NO_CONTEXT_REPLY_ZH,
        citations: [],
      }),
    ).toBe(false);
    expect(
      shouldShowLightFeedbackPrompt({
        streaming: true,
        messageId: "m1",
        content: NO_CONTEXT_REPLY_ZH,
        citations: [],
      }),
    ).toBe(false);
    expect(
      shouldShowLightFeedbackPrompt({
        messageId: "m1",
        content: "正常回答带引用",
        citations: [{ source_status: "available" }],
      }),
    ).toBe(false);
  });

  it("picks refuse vs stale label", () => {
    expect(
      lightFeedbackPromptLabel({
        content: NO_CONTEXT_REPLY_ZH,
        citations: [],
      }),
    ).toBe(FEEDBACK_PROMPT_REFUSE);
    expect(
      lightFeedbackPromptLabel({
        content: "旧答",
        citations: [{ source_status: "source_inaccessible" }],
      }),
    ).toBe(FEEDBACK_PROMPT_STALE);
  });

  it("parses ?eval=1 only", () => {
    expect(isEvalQueryParam("?eval=1")).toBe(true);
    expect(isEvalQueryParam("eval=1&q=hi")).toBe(true);
    expect(isEvalQueryParam(new URLSearchParams("eval=1"))).toBe(true);
    expect(isEvalQueryParam("?eval=true")).toBe(false);
    expect(isEvalQueryParam("?eval=0")).toBe(false);
    expect(isEvalQueryParam("")).toBe(false);
    expect(isEvalQueryParam(null)).toBe(false);
  });

  it("gates eval role: personal/admin/owner yes, member no", () => {
    expect(
      canUseFeedbackEvalMode({
        account_type: "personal",
        org_role: null,
      }),
    ).toBe(true);
    expect(
      canUseFeedbackEvalMode({
        account_type: "enterprise",
        org_role: "admin",
      }),
    ).toBe(true);
    expect(
      canUseFeedbackEvalMode({
        account_type: "enterprise",
        org_role: "member",
        is_owner: true,
      }),
    ).toBe(true);
    expect(
      canUseFeedbackEvalMode({
        account_type: "enterprise",
        org_role: "member",
      }),
    ).toBe(false);
    expect(canUseFeedbackEvalMode(null)).toBe(false);
  });

  it("activates eval only when URL and role both pass", () => {
    const admin = {
      account_type: "enterprise" as const,
      org_role: "admin" as const,
    };
    const member = {
      account_type: "enterprise" as const,
      org_role: "member" as const,
    };
    expect(isFeedbackEvalModeActive({ search: "?eval=1", user: admin })).toBe(
      true,
    );
    expect(isFeedbackEvalModeActive({ search: "?eval=1", user: member })).toBe(
      false,
    );
    expect(isFeedbackEvalModeActive({ search: "", user: admin })).toBe(false);
  });
});
