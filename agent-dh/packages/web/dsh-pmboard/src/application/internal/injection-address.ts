/**
 * 注入段装配（REQ-260922213356-4a45 T-2 / design S-4、I-4）。
 *
 * 三/四处注入点**必须**共用本函数（禁止各写一份拼接）：
 * 空集 → 返回入参 resolved 本身（引用相等，保证 FR-4 逐字节兼容）；
 * 非空 → 折入 text 与 charCount（留痕记账含地址段，FR-8），其余字段原样保留。
 *
 * @module dsh-pmboard/application/internal/injection-address
 */
import type { ResolvedPrompt } from '../../domain/prompt/index.js'
import { renderAddressSection } from '../../domain/template/index.js'
import type { AddressSectionInput } from '../../domain/template/types.js'

export function augmentResolvedPrompt(resolved: ResolvedPrompt, input: AddressSectionInput): ResolvedPrompt {
  const section = renderAddressSection(input)
  if (section.length === 0) return resolved
  const text = resolved.text + '\n\n' + section
  return { ...resolved, text, charCount: resolved.text.length + section.length + 2 }
}
