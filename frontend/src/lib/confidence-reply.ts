/** E3：低置信度确定性话术（须与 backend confidence_reply.py 字符串一致）。 */

export const PARTIAL_DISCLAIMER_ZH =
  "以下回答仅依据部分相关片段，可能无法完整覆盖您的问题；若不符预期，建议换更具体的问法（如条款号、岗位或文档名）。";

export const PARTIAL_DISCLAIMER_EN =
  "This answer is based on partially matching passages and may not fully cover your question. If it looks off, try a more specific phrasing (e.g. clause number, role, or document name).";

/** 气泡下短提示（正文已含完整 disclaimer 前缀） */
export const PARTIAL_ANSWER_NOTICE =
  "依据偏弱：以下为部分相关片段上的回答；不符时可换更具体问法。";

export function hasPartialAnswerDisclaimer(content: string): boolean {
  const text = content.trimStart();
  return (
    text.startsWith(PARTIAL_DISCLAIMER_ZH) ||
    text.startsWith(PARTIAL_DISCLAIMER_EN)
  );
}
