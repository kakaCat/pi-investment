/**
 * Overflow Patterns Library
 *
 * 参考 openclaw docs/concepts/compaction.md 和腾讯 offload 代码
 * 匹配 LLM provider 的上下文溢出错误，触发压缩重试
 */

/**
 * LLM Provider 上下文溢出错误模式
 *
 * 来源：
 * - OpenClaw compaction.md
 * - 腾讯 offload 代码
 * - Anthropic/OpenAI/Gemini/Ollama 官方文档
 */
export const OVERFLOW_ERROR_PATTERNS = [
  // Anthropic
  /request_too_large/i,
  /prompt is too long/i,
  /max_tokens.*exceeds/i,

  // OpenAI
  /context[_ ]length[_ ]exceeded/i,
  /maximum context length/i,
  /tokens.*exceed.*maximum/i,
  /input is too long for the model/i,

  // AWS Bedrock
  /input token count exceeds the maximum number of input tokens/i,
  /input exceeds the maximum number of tokens/i,

  // Google Gemini
  /token limit exceeded/i,
  /request size exceeds limit/i,

  // Ollama
  /ollama error:.*context length exceeded/i,
  /context window.*exceeded/i,

  // 通用模式
  /too many tokens/i,
  /context window full/i,
  /context size.*too large/i,
  /input.*too long/i,
  /maximum.*tokens.*exceeded/i,
  /token count.*exceeds/i,
  /context.*overflow/i,
  /prompt.*too long/i,
  /request.*too large/i,
];

/**
 * 检查错误是否为上下文溢出错误
 *
 * @param error - 错误对象或消息字符串
 * @returns 是否匹配溢出模式
 */
export function isOverflowError(error: unknown): boolean {
  const errorMessage = error instanceof Error
    ? error.message
    : String(error);

  return OVERFLOW_ERROR_PATTERNS.some(pattern => pattern.test(errorMessage));
}

/**
 * 提取匹配的溢出错误模式（用于日志）
 *
 * @param error - 错误对象或消息字符串
 * @returns 匹配的模式描述，如果未匹配则返回 null
 */
export function getMatchedPattern(error: unknown): string | null {
  const errorMessage = error instanceof Error
    ? error.message
    : String(error);

  const matchedPattern = OVERFLOW_ERROR_PATTERNS.find(pattern =>
    pattern.test(errorMessage)
  );

  return matchedPattern ? matchedPattern.source : null;
}

/**
 * 格式化溢出错误信息（用于日志）
 *
 * @param error - 错误对象
 * @param attemptCount - 重试次数
 * @returns 格式化的错误信息
 */
export function formatOverflowError(error: unknown, attemptCount: number): string {
  const errorMessage = error instanceof Error
    ? error.message
    : String(error);

  const pattern = getMatchedPattern(error);
  const patternInfo = pattern ? ` (matched: ${pattern})` : '';

  return `🗜️  Context overflow detected${patternInfo}, attempt ${attemptCount}: ${errorMessage.slice(0, 200)}`;
}
