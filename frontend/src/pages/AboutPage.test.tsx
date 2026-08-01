import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const mockAuth = vi.fn();
const mockWorkspace = vi.fn();
const mockDepartment = vi.fn();
const mockFetchStats = vi.fn();

vi.mock("@/lib/auth-context", () => ({
  useAuth: () => mockAuth(),
}));

vi.mock("@/lib/workspace-context", () => ({
  useWorkspace: () => mockWorkspace(),
}));

vi.mock("@/lib/department-context", () => ({
  useDepartment: () => mockDepartment(),
}));

vi.mock("@/lib/dashboard-api", () => ({
  fetchDashboardStats: (...args: unknown[]) => mockFetchStats(...args),
}));

import { AboutPage } from "@/pages/AboutPage";

function renderAbout() {
  return render(
    <MemoryRouter>
      <AboutPage />
    </MemoryRouter>,
  );
}

describe("AboutPage", () => {
  beforeEach(() => {
    mockAuth.mockReturnValue({ isOrgAdmin: false, user: null });
    mockWorkspace.mockReturnValue({
      isTeamWorkspace: false,
      workspace: "personal",
      generation: 1,
      getGeneration: () => 1,
    });
    mockDepartment.mockReturnValue({
      departmentId: null,
      generation: 1,
      getGeneration: () => 1,
    });
    mockFetchStats.mockReset();
  });

  it("shows core sections for member / personal", () => {
    renderAbout();
    expect(screen.getByText("产品简介")).toBeTruthy();
    expect(screen.getByText("版本信息")).toBeTruthy();
    expect(screen.getByText("使用帮助")).toBeTruthy();
    expect(screen.getByText(/换大主题时，建议点「新对话」另开/)).toBeTruthy();
    expect(screen.getByText("隐私与安全")).toBeTruthy();
    expect(screen.getByText("内网部署摘要")).toBeTruthy();
    expect(screen.getByText(/不承诺/)).toBeTruthy();
    expect(screen.getAllByText(/仅存服务端/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "账号设置" })).toBeTruthy();
    expect(screen.queryByTestId("about-ops")).toBeNull();
    expect(screen.queryByText("操作审计日志")).toBeNull();
    expect(screen.queryByText("知识库资产清单")).toBeNull();
    expect(screen.queryByText("docs/DEPLOY.md")).toBeNull();
    expect(mockFetchStats).not.toHaveBeenCalled();
  });

  it("hides ops when team member is not org admin", () => {
    mockAuth.mockReturnValue({ isOrgAdmin: false, user: { org_id: "o1" } });
    mockWorkspace.mockReturnValue({
      isTeamWorkspace: true,
      workspace: "o1",
      generation: 1,
      getGeneration: () => 1,
    });
    renderAbout();
    expect(screen.queryByTestId("about-ops")).toBeNull();
    expect(mockFetchStats).not.toHaveBeenCalled();
  });

  it("shows ops and cost estimate for team org admin", async () => {
    mockAuth.mockReturnValue({ isOrgAdmin: true, user: { org_id: "o1" } });
    mockWorkspace.mockReturnValue({
      isTeamWorkspace: true,
      workspace: "o1",
      generation: 1,
      getGeneration: () => 1,
    });
    mockFetchStats.mockResolvedValue({
      usage_7d_user_questions: 3,
      usage_7d_assistant_replies: 3,
      estimated_api_cost_cny_7d: 0.06,
      cost_estimate_note: "粗估",
      chat_retention_days: 30,
      rate_limit_backend: "redis",
      citation_redact_enabled: true,
      llm_context_redact_enabled: false,
      kb_quota_max_bytes: 10 * 1024 ** 3,
    });
    renderAbout();
    expect(screen.getByTestId("about-ops")).toBeTruthy();
    expect(screen.getByRole("link", { name: "操作审计日志" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "知识库资产清单" })).toBeTruthy();
    expect(screen.getByText(/≠ 审计导出/)).toBeTruthy();
    expect(screen.getByTestId("about-audit-retention")).toBeTruthy();
    expect(screen.getByText(/永留（无 TTL）/)).toBeTruthy();
    expect(screen.getByText("docs/DEPLOY.md")).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-M10-backup-runbook.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-duty-triplet-runbook.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-M13-format-matrix.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-h1-grafana-alert-runbook.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-llm-egress-runbook.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-secret-rotation-runbook.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-high-sensitivity-posture.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/nw66-dependency-cve-research.md"),
    ).toBeTruthy();
    expect(screen.getByTestId("about-ops-boundary")).toBeTruthy();
    expect(screen.getByText(/≠ 开 Cookie I/)).toBeTruthy();
    expect(screen.getByText("docs/tasks/eval-M4-cost-model.md")).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-thumbs-down-golden-runbook.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-M11-quarterly-check.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-maintenance-calendar.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/nw2b-ruler-alignment.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-security-posture-questionnaire.md"),
    ).toBeTruthy();
    expect(
      screen.getByText("docs/tasks/eval-ops-intranet-delivery-acceptance.md"),
    ).toBeTruthy();
    expect(screen.getByTestId("about-thumbs-down-export-hint")).toBeTruthy();
    expect(
      screen.getByText("python scripts/export_thumbs_down_candidates.py"),
    ).toBeTruthy();
    expect(screen.getByText(/导出 ≠ 进门禁/)).toBeTruthy();
    expect(screen.getByText(/不一键写入、不自动改检索/)).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByTestId("about-chat-retention")).toBeTruthy();
      expect(screen.getByTestId("about-ops-flags")).toBeTruthy();
      expect(screen.getByTestId("about-cost-estimate")).toBeTruthy();
    });
    expect(screen.getByText(/30 天/)).toBeTruthy();
    expect(screen.getByText(/值班第四条/)).toBeTruthy();
    expect(screen.getByText(/≠ 审计永留/)).toBeTruthy();
    expect(screen.getByText(/\bredis\b/)).toBeTruthy();
    expect(screen.getByText(/引用脱敏/)).toBeTruthy();
    expect(screen.getByText(/送模 scrub/)).toBeTruthy();
    expect(screen.getByText(/总库配额/)).toBeTruthy();
    expect(screen.getByText(/开（10 GiB）/)).toBeTruthy();
    expect(screen.getByText(/¥0\.06/)).toBeTruthy();
    expect(mockFetchStats).toHaveBeenCalled();
  });

  it("shows retention disabled copy when days is zero", async () => {
    mockAuth.mockReturnValue({ isOrgAdmin: true, user: { org_id: "o1" } });
    mockWorkspace.mockReturnValue({
      isTeamWorkspace: true,
      workspace: "o1",
      generation: 1,
      getGeneration: () => 1,
    });
    mockFetchStats.mockResolvedValue({
      chat_retention_days: 0,
      rate_limit_backend: "memory",
      citation_redact_enabled: false,
      llm_context_redact_enabled: true,
      kb_quota_max_bytes: 0,
      estimated_api_cost_cny_7d: null,
      cost_estimate_note: null,
    });
    renderAbout();
    await waitFor(() => {
      expect(screen.getByTestId("about-chat-retention")).toBeTruthy();
      expect(screen.getByTestId("about-ops-flags")).toBeTruthy();
    });
    expect(screen.getByText(/关闭（CHAT_RETENTION_DAYS=0）/)).toBeTruthy();
    expect(screen.getByText(/\bmemory\b/)).toBeTruthy();
    expect(screen.getByText(/关闭（KB_QUOTA_MAX_BYTES=0）/)).toBeTruthy();
  });

  it("hides ops for org admin in personal workspace", () => {
    mockAuth.mockReturnValue({ isOrgAdmin: true, user: { org_id: "o1" } });
    mockWorkspace.mockReturnValue({
      isTeamWorkspace: false,
      workspace: "personal",
      generation: 1,
      getGeneration: () => 1,
    });
    renderAbout();
    expect(screen.queryByTestId("about-ops")).toBeNull();
    expect(mockFetchStats).not.toHaveBeenCalled();
  });
});
