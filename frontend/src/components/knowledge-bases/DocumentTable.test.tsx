import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import { DocumentTable } from "./DocumentTable";
import type { Document } from "@/lib/document-api";

function baseDoc(overrides: Partial<Document> = {}): Document {
  return {
    id: "doc-1",
    kb_id: "kb-1",
    filename: "scan.pdf",
    file_type: "pdf",
    file_size: 1024,
    status: "failed",
    visibility: "everyone",
    chunk_count: null,
    error_message: "OCR 引擎未安装（需 PaddleOCR），当前环境无法识别扫描件",
    processing_started_at: null,
    processing_completed_at: null,
    uploaded_by: null,
    created_at: "2026-07-21T00:00:00Z",
    updated_at: "2026-07-21T00:00:00Z",
    ...overrides,
  };
}

describe("DocumentTable B3 error_message", () => {
  test("shows truncated failure reason under status for failed docs", () => {
    render(
      <MemoryRouter>
        <DocumentTable
          kbId="kb-1"
          documents={[baseDoc()]}
          canManage={false}
          canChangeVisibility={false}
          onRequestDelete={vi.fn()}
          onRetry={vi.fn(async () => undefined)}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("失败")).toBeDefined();
    expect(
      screen.getByText("OCR 引擎未安装（需 PaddleOCR），当前环境无法识别扫描件"),
    ).toBeDefined();
  });

  test("shows progress bar and OCR detail while processing", () => {
    render(
      <MemoryRouter>
        <DocumentTable
          kbId="kb-1"
          documents={[
            baseDoc({
              status: "processing",
              error_message: null,
              processing_stage: "parsing",
              progress_percent: 25,
              progress_detail: "第 2/8 页",
            }),
          ]}
          canManage={false}
          canChangeVisibility={false}
          onRequestDelete={vi.fn()}
          onRetry={vi.fn(async () => undefined)}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("正在识别…")).toBeDefined();
    expect(screen.getByText("第 2/8 页")).toBeDefined();
    expect(screen.getByText("25%")).toBeDefined();
  });
});
