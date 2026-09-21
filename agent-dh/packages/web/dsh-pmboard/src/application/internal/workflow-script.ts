/**
 * 子卡 workflow 脚本生成与**契约门禁**（REQ-4842fe t4 / FR-4）。
 *
 * 为什么需要门禁：本仓被修正的两处历史错误（`ctx.subagent(...)` 与
 * `ctx.tools.workflow(...)`）都源于对引擎 API 面的假设——脚本跑在 worker 线程的
 * node:vm 里，**只注入五个 hook**（agent / parallel / pipeline / phase / log），
 * 没有 ctx、没有 subagent、不能调工具。契约错了要等真跑一次才炸；门禁把它提前到
 * **生成阶段**（对齐 design/workflow-engine-contract §4「生成立即校验」）。
 *
 * 边界（诚实声明）：本门禁是**构建期绊线**，不是沙箱——引擎本身已在 vm 里执行，
 * 真正的隔离由引擎负责（worker-thread README「Trust expectations」）。门禁只保证
 * "生成器不会产出用错 API 的脚本"。
 *
 * @module dsh-pmboard/application/internal/workflow-script
 */
import { fmt } from '../../domain/text/fmt.js'

/** 引擎注入脚本的**全部** hook（唯一事实源；生成器只允许用其中子集）。 */
export const WORKFLOW_HOOKS = ['agent', 'parallel', 'pipeline', 'phase', 'log'] as const
export type WorkflowHook = (typeof WORKFLOW_HOOKS)[number]

function contractError(message: string): Error {
  return Object.assign(new Error(fmt('workflow 脚本契约不通过：{message}', { message })), { code: 'workflow_script_contract' })
}

/**
 * 去字符串/模板字面量：契约只约束**可执行的代码**，不应被 prompt 文本里的
 * 示例（如父卡实施方案里引用的工具名）误伤。
 */
export function stripStringLiterals(src: string): string {
  return src
    .replace(/`(?:\\[\s\S]|[^`\\])*`/g, '``')
    .replace(/'(?:\\[\s\S]|[^'\\])*'/g, "''")
    .replace(/"(?:\\[\s\S]|[^"\\])*"/g, '""')
}

/** 禁止出现在脚本代码里的宿主/工具面（每条都对应一个真实踩坑）。 */
const FORBIDDEN: ReadonlyArray<{ re: RegExp; why: string }> = [
  { re: /\bctx\b/, why: '脚本内没有 ctx 全局（vm 只注入五个 hook）' },
  { re: /\bsubagent\b/, why: '引擎没有 subagent 函数（正确写法是 agent()）' },
  { re: /\bworkflow\s*\(/, why: '引擎不支持嵌套 run（没有 workflow hook）' },
  { re: /\brequire\s*\(/, why: 'worker 环境不提供 require' },
  { re: /\bimport\s*\(/, why: '脚本是纯 JS 体，不支持动态 import' },
  { re: /\bprocess\b/, why: 'worker 环境不继承 process（不要交凭据给脚本）' },
  { re: /\bglobalThis\b/, why: '宿主全局不可达' },
  { re: /\beval\s*\(|\bnew\s+Function\b/, why: '禁止动态求值' },
  { re: /\b[a-z][a-z0-9]*_[a-z0-9_]+\s*\(/, why: '疑似工具名调用（脚本不能调工具，状态变更在宿主侧）' },
]

/**
 * 静态契约校验：脚本非空、不含宿主/工具面 token。不通过抛
 * code=workflow_script_contract（生成阶段即失败，不带着错脚本去下单）。
 */
export function assertScriptContract(script: string): void {
  if (typeof script !== 'string' || script.trim().length === 0) throw contractError('脚本为空')
  const code = stripStringLiterals(script)
  for (const f of FORBIDDEN) {
    if (f.re.test(code)) throw contractError(f.why)
  }
}

/** 脚本实际使用的 hook（子集；测试断言"只含白名单"用）。 */
export function usedHooks(script: string): WorkflowHook[] {
  const code = stripStringLiterals(script)
  return WORKFLOW_HOOKS.filter((h) => new RegExp('\\b' + h + '\\s*\\(').test(code))
}

/** 子卡脚本输入（父卡上下文由调用方拼进 prompt，脚本本身只负责干活 + 返回 JSON）。 */
export interface SubtaskScriptInput {
  stageKind: string
  /** 阶段中文名（plog/log 文案用）。 */
  stageLabel: string
  /** 交给子代理的完整提示词（含父卡实施方案 + 本卡验收标准）。 */
  prompt: string
}

/**
 * 生成一张子卡的脚本：`phase()` 分组 + `log()` 留痕 + `agent()` 干活 + `return` 纯 JSON。
 * 产出即过契约门禁（不通过抛错，调用方拿不到脚本）。
 */
export function generateSubtaskScript(input: SubtaskScriptInput): string {
  const prompt = typeof input.prompt === 'string' ? input.prompt : ''
  const script = [
    'phase("执行");',
    'log(' + JSON.stringify(fmt('子卡 {kind} 开工：{label}', { kind: input.stageKind, label: input.stageLabel })) + ');',
    'const out = await agent(' + JSON.stringify(prompt) + ');',
    'return { ok: out !== null, output: out };',
  ].join('\n')
  assertScriptContract(script)
  return script
}
