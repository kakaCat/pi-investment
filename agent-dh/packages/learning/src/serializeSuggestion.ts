/**
 * 蒸馏建议序列化（2026-09-12，w-adb088f2）
 *
 * 缺陷：后端 analyzeExperiences 返回的建议是**对象**，工具层用 String(s) 直接转换 →
 * 建议全部变成字面量 "[object Object]"。该字面量随后经 daily_distill 灌进
 * prompt_evolver 的 suggestion.content（2026-09-11 实证污染候选内容）。
 *
 * 约定：
 *  - 字符串原样返回；
 *  - 对象按常见文本字段优先级提取（suggestion/content/text/message/…），
 *    无文本字段则 JSON.stringify（保留信息，绝不产出 "[object Object]"）；
 *  - 数组逐项序列化后用 '; ' 连接；null/undefined → ''；
 *  - 绝不返回裸 "[object Object]"（对象一律先按文本字段或 JSON 处理）。
 */

const TEXT_KEYS = [
  'suggestion', 'content', 'text', 'message', 'description',
  'insight', 'reason', 'title', 'value', 'summary',
] as const;

export function serializeSuggestion(input: unknown): string {
  if (input === null || input === undefined) return '';
  if (typeof input === 'string') return input;
  if (typeof input === 'number' || typeof input === 'boolean') return String(input);
  if (Array.isArray(input)) {
    return input.map(serializeSuggestion).filter((s) => s.length > 0).join('; ');
  }
  if (typeof input === 'object') {
    const obj = input as Record<string, unknown>;
    // 2026-09-13（w-adb088f2，第三批审阅 A9）：主字段语义 —— 按 TEXT_KEYS 优先级取
    // **第一个**非空文本字段作为建议正文。旧实现把所有命中字段用「；」拼接，
    // 会把异质字段（如 title + reason）粘成一句话，读起来像一条不存在的结论。
    for (const k of TEXT_KEYS) {
      const v = obj[k];
      if (typeof v === 'string' && v.trim().length > 0) return v.trim();
    }
    try {
      const js = JSON.stringify(input);
      return js && js !== '{}' ? js : '';
    } catch {
      return '';
    }
  }
  const s = String(input);
  return s === '[object Object]' ? '' : s;
}
