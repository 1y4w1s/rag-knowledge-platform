import { z } from "zod";

// ── Citation ──────────────────────────────────────────

export const CitationSourceStatusSchema = z.enum([
  "available",
  "document_deleted",
  "chunk_stale",
  "source_inaccessible",
]);

export const CitationSchema = z.object({
  chunk_id: z.string().min(1),
  document_id: z.string().min(1),
  doc_name: z.string().min(1),
  page: z.number().int().nullable(),
  section_title: z.string().nullable(),
  excerpt: z.string().min(1),
  kb_id: z.string().nullable().optional(),
  kb_name: z.string().nullable().optional(),
  source_status: CitationSourceStatusSchema.nullable().optional(),
});

// ── SSE payloads ─────────────────────────────────────

export const ChatDonePayloadSchema = z.object({
  message_id: z.string().min(1),
  citations: z.array(CitationSchema),
  agent_run_id: z.string().nullable().optional(),
  approval_id: z.string().nullable().optional(),
  approval_status: z.string().nullable().optional(),
});

export const ApprovalRequiredPayloadSchema = z.object({
  approval_id: z.string().min(1),
  draft_type: z.string(),
  filename: z.string().min(1),
  kb_id: z.string().min(1),
  kb_name: z.string().min(1),
  draft_preview: z.string(),
  citations: z.array(CitationSchema),
  can_adopt: z.boolean(),
});

export const ApprovalStateSchema = z.object({
  approval_id: z.string().min(1),
  filename: z.string().min(1),
  kb_name: z.string().min(1),
  draft_preview: z.string(),
  citations: z.array(CitationSchema),
  can_adopt: z.boolean(),
  status: z.enum(["pending", "adopted", "cancelled"]),
});

// ── G5 · 文档操作提案预览（SSE proposal_preview） ────

export const ProposalPreviewPayloadSchema = z.object({
  operation: z.enum(["delete", "restore"]),
  document_id: z.string().min(1),
  kb_id: z.string().min(1),
  filename: z.string().min(1),
  kb_name: z.string().min(1),
  impact: z.string(),
  conflict: z.string().nullable(),
  run_id: z.string().min(1),
  can_adopt: z.boolean(),
  /** B 路径（fast 模式自动识别）需两次点击确认 */
  double_confirm: z.boolean().optional().default(false),
});

// ── G5 · 歧义澄清（SSE clarify · 情景 5） ────

export const ClarifyOptionSchema = z.object({
  document_id: z.string().min(1),
  filename: z.string().min(1),
  kb_id: z.string().min(1),
});

export const ClarifyPayloadSchema = z.object({
  operation: z.enum(["delete", "restore"]),
  run_id: z.string().min(1),
  options: z.array(ClarifyOptionSchema).min(1),
});

// ── History / Messages ───────────────────────────────

export const HistoryMessageSchema = z.object({
  id: z.string().min(1),
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  citations: z.array(CitationSchema).nullable(),
  approval_id: z.string().nullable().optional(),
  approval_status: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: z.string(),
});

export const ChatMessagesResponseSchema = z.object({
  messages: z.array(HistoryMessageSchema),
});

// ── REST responses ────────────────────────────────────

export const CitationResolveResultSchema = z.object({
  document_id: z.string().min(1),
  chunk_id: z.string().min(1),
  source_status: CitationSourceStatusSchema,
  doc_name: z.string().nullable(),
});

// ── SSE sub-payloads (tool events) ────────────────────

export const ToolStartPayloadSchema = z.object({
  step: z.number().int(),
  tool: z.string(),
  args_summary: z.string(),
});

export const ToolResultPayloadSchema = z.object({
  step: z.number().int(),
  tool: z.string(),
  ok: z.boolean(),
  summary: z.string(),
  latency_ms: z.number().int(),
  capped: z.boolean().optional(),
});

export const AgentBudgetPayloadSchema = z.object({
  steps_used: z.number().int(),
  max_steps: z.number().int(),
  capped: z.boolean(),
});
