/**
 * 前端本地化兜底层。
 *
 * 后端为兼容英文提问，会在「无相关依据」等固定场景返回英文话术；
 * 在中文 UI 下需统一替换为中文，避免英文串直接暴露给中文用户。
 *
 * 设计原则（呼应产品「克制」基调）：
 * - 仅对已知英文串做「精确 / 前缀」匹配，绝不误伤用户真实的英文回答或合法 detail。
 * - 不引入完整 i18n 框架，只守住对话页最可能泄漏的少数固定文案。
 */

const ASSISTANT_TEXT_MAP: ReadonlyArray<readonly [RegExp, string]> = [
  [
    /^No relevant content was found in the knowledge base to answer your question\.?\s*$/i,
    "未在资料库中找到相关内容，无法根据文档回答您的问题。",
  ],
];

/** 把后端可能返回的英文助手文本替换为中文（仅匹配已知固定话术）。 */
export function localizeAssistantText(text: string): string {
  if (!text) return text;
  for (const [pattern, replacement] of ASSISTANT_TEXT_MAP) {
    if (pattern.test(text.trim())) return replacement;
  }
  return text;
}

const BACKEND_ERROR_MAP: ReadonlyArray<readonly [RegExp, string]> = [
  [/^Rate limit exceeded/i, "请求过于频繁，请稍后再试"],
  [/^Quota exceeded/i, "额度已用尽，请稍后或联系管理员"],
  [/^Request timed out/i, "请求超时，请稍后重试"],
  [/^Connection (to|error)/i, "服务连接异常，请稍后重试"],
  [/^Internal server error/i, "服务内部错误，请稍后重试"],
  [/^Context length exceeded/i, "内容超出模型长度上限，请精简后重试"],
  [/^Invalid API key/i, "模型服务密钥无效，请联系管理员"],
  [/^Model .* not available/i, "模型服务暂不可用，请稍后重试"],
  [/^Knowledge base .* not found/i, "资料库不存在"],
  [/^No active workspace/i, "当前没有可用工作区，请先选择或创建"],
];

/** 把后端错误 detail 中的常见英文短语替换为中文（未知串原样返回）。 */
export function localizeBackendError(detail: string | null): string | null {
  if (!detail) return detail;
  for (const [pattern, replacement] of BACKEND_ERROR_MAP) {
    if (pattern.test(detail.trim())) return replacement;
  }
  return detail;
}
