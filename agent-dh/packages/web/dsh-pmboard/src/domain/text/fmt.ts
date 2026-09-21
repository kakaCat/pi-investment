/**
 * 具名占位符格式化（REQ-47939a 返工：专门解决"字符串拼接"）。用 `{name}` 占位，替代
 * `'需求 ' + id + ' 当前处于 ' + status + '，不在验收态'` 这种拼接。
 *
 * 为什么值得抽出来（用户验收意见直接指出）：
 *   ① 拼接式消息**读不出整句**——翻译/审阅/改口径都要在引号与变量之间来回拼；
 *   ② 变量顺序与重复由人维护，改一处漏一处（'a'+x+'b'+x 这种重复拼接尤其危险）；
 *   ③ 缺变量时拼接会静默产出 "需求 undefined 当前处于 …" 这种**看似正常**的脏消息——
 *      而 fmt 缺变量**直接抛错**，把"没生效"变成可见失败（对齐 standards 的诚实失败）。
 *
 * @module dsh-pmboard/domain/text/fmt
 */
import { REQBOARD_ERROR_CODES, domainError } from '../errors.js'

/** 截断到 max 字符（超出加省略号）。用于**弹框题干**等有硬性长度约束的场合。 */
export function clip(text: string, max: number): string {
  return text.length <= max ? text : text.slice(0, Math.max(0, max - 1)) + '…'
}

/** 变量值（消息里只允许这两种标量，避免把对象塞进用户可见文案）。 */
export type FmtVars = Record<string, string | number>

/**
 * 具名占位符替换：`fmt('需求 {id} 当前处于 {status}，不在验收态', { id, status })`。
 * 缺失变量 → 抛 `invalid_input`（宁可报错，也不要产出 "undefined" 脏文案）。
 * 多传变量不报错（调用方可能复用同一套变量）。
 */
export function fmt(template: string, vars: FmtVars): string {
  return template.replace(/\{(\w+)\}/g, (_m, name: string) => {
    const value = vars[name]
    if (value === undefined) {
      // 本文件是格式化器自身，故用模板串而不用 fmt（避免自我递归）
      throw domainError(REQBOARD_ERROR_CODES.invalidInput, `fmt 缺少变量 {${name}}：${template}`)
    }
    return String(value)
  })
}
