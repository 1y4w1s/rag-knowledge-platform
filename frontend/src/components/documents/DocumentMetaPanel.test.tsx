import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { DocumentMetaPanel } from "./DocumentMetaPanel";
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
    error_message: null,
    processing_started_at: null,
    processing_completed_at: null,
    uploaded_by: null,
    created_at: "2026-07-21T00:00:00Z",
    updated_at: "2026-07-21T00:00:00Z",
    ...overrides,
  };
}

describe("DocumentMetaPanel B3 error_message", () => {
  test("shows failure reason when failed with error_message", () => {
    render(
      <MemoryRouter>
        <DocumentMetaPanel
          kbId="kb-1"
          document={baseDoc({
            error_message: "OCR 引擎未安装（需 PaddleOCR），当前环境无法识别扫描件",
          })}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText("失败原因")).toBeDefined();
    expect(
      screen.getByText("OCR 引擎未安装（需 PaddleOCR），当前环境无法识别扫描件"),
    ).toBeDefined();
  });

  test("hides failure reason when completed", () => {
    render(
      <MemoryRouter>
        <DocumentMetaPanel
          kbId="kb-1"
          document={baseDoc({
            status: "completed",
            chunk_count: 3,
            error_message: null,
          })}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByText("失败原因")).toBeNull();
  });
});
