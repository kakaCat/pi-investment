/**
 * 业务工具定制卡片 · 数据契约与纯函数（REQ-c48f99 t1 / FR-1、FR-4）。
 *
 * 本文件零依赖（不 import react），使 host 侧 vitest 可直接单测；
 * BizRow / 卡片组件（rows/*.ts）才允许引入 react。
 *
 * 核心不变式：
 *  - parseArgs/resultJson 对任何输入不 throw，失败返回 undefined（FR-4 兜底前提）；
 *  - summarize 返回 null 的唯一合法含义 = 交 fallbackRow；
 *  - 折叠行摘要单行（多行会被 GenericToolCard 首行截断语义破坏）。
 * @module dsh-pmboard/client/toolviews/shared
 */

// ---------------------------------------------------------------------------
// block 数据形态（会话事件投影，只读）
// ---------------------------------------------------------------------------

/** 运行中的工具调用（未结算）。 */
export interface RunningBlock {
  callId: string
  name?: string
  argsRaw?: string
  parentCallId?: string
}

/** 已结算的工具结果节点。 */
export interface SettledBlock {
  kind: 'tool-result'
  callId: string
  parentCallId?: string
  call?: { name?: string; argsRaw?: string }
  content?: Array<{ type?: string; text?: string }>
  isError?: boolean
  error?: { name?: string; code?: string }
  meta?: unknown
}

export type ToolBlock = RunningBlock | SettledBlock

export function isSettled(block: ToolBlock): block is SettledBlock {
  return 'kind' in block && (block as SettledBlock).kind === 'tool-result'
}

/** 取 argsRaw：结算态在 call.argsRaw，运行态在 argsRaw。 */
export function argsRawOf(block: ToolBlock): string {
  return (isSettled(block) ? block.call?.argsRaw : block.argsRaw) ?? ''
}

// ---------------------------------------------------------------------------
// 解析纯函数（不 throw 契约）
// ---------------------------------------------------------------------------

/**
 * 解析 argsRaw 为参数对象。半截 JSON（流式）、非对象 JSON、非法输入
 * 一律返回 undefined（FR-4：调用方据此走 fallbackRow，禁止 throw）。
 */
export function parseArgs(argsRaw: string): Record<string, unknown> | undefined {
  if (typeof argsRaw !== 'string' || argsRaw.trim() === '') return undefined
  try {
    const parsed: unknown = JSON.parse(argsRaw)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return undefined
    return parsed as Record<string, unknown>
  } catch {
    return undefined
  }
}

/** 拼接结果文本（content 里全部 text 段）。 */
export function resultText(block: ToolBlock): string {
  if (!isSettled(block)) return ''
  const parts: string[] = []
  for (const seg of block.content ?? []) {
    if (seg?.type === 'text' && typeof seg.text === 'string') parts.push(seg.text)
  }
  return parts.join('\n')
}

/** 把结果文本解析为 JSON 对象；失败返回 undefined（不 throw）。
 * 兼容 renderSmart 形态（首行摘要 + 空行 + JSON 明细）：整段解析失败时，
 * 取第一个空行之后的部分再试一次。 */
export function resultJson(block: ToolBlock): Record<string, unknown> | undefined {
  const text = resultText(block).trim()
  if (text === '') return undefined
  const tryParse = (s: string): Record<string, unknown> | undefined => {
    try {
      const parsed: unknown = JSON.parse(s)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return undefined
      return parsed as Record<string, unknown>
    } catch {
      return undefined
    }
  }
  const whole = tryParse(text)
  if (whole !== undefined) return whole
  const split = text.indexOf('\n\n')
  if (split === -1) return undefined
  return tryParse(text.slice(split + 2).trim())
}

/** 结果的人话首行：renderSmart 形态取首行摘要；纯 JSON 形态取空串。 */
export function resultHeadline(block: ToolBlock): string {
  const text = resultText(block).trim()
  if (text === '' || text.startsWith('{') || text.startsWith('[')) return ''
  return firstLine(text)
}

export function firstLine(text: string): string {
  const nl = text.indexOf('\n')
  return nl === -1 ? text : text.slice(0, nl)
}

/** 取字符串字段（空串视为无）。 */
export function strOf(obj: Record<string, unknown> | undefined, key: string): string | undefined {
  const v = obj?.[key]
  return typeof v === 'string' && v !== '' ? v : undefined
}

/** 取数字字段。 */
export function numOf(obj: Record<string, unknown> | undefined, key: string): number | undefined {
  const v = obj?.[key]
  return typeof v === 'number' && Number.isFinite(v) ? v : undefined
}

// ---------------------------------------------------------------------------
// 中文映射表（FR-2；未知枚举值兜底原文显示，不做中文猜测）
// ---------------------------------------------------------------------------

export const TASK_MOVE_TO: Readonly<Record<string, string>> = {
  in_progress: '开工',
  testing: '送测',
  integrating: '联调',
  in_review: '送审',
  done: '完工',
  todo: '退回',
  canceled: '取消',
}

export const SUBMIT_KIND: Readonly<Record<string, string>> = {
  requirement: '需求文档',
  plan: '拆分计划（旧版）', // 与 stage-panel ARTIFACT_KIND_LABELS 一致：plan 退役，拆分计划由 decomposition 承载
  verification: '验收材料',
  archive: '归档材料',
}

export const AUDIT_ACTION: Readonly<Record<string, string>> = {
  record: '留痕',
  evaluate: '评估',
}

export const WATCH_ACTION: Readonly<Record<string, string>> = {
  create: '新建',
  enable: '启用',
  disable: '禁用',
  delete: '删除',
}

export const TRADE_ACTION: Readonly<Record<string, string>> = {
  BUY: '买入',
  SELL: '卖出',
}

/** 查映射表；未命中返回原文（空原文返回 undefined）。 */
export function cnLabel(map: Readonly<Record<string, string>>, key: string | undefined): string | undefined {
  if (key === undefined || key === '') return undefined
  return map[key] ?? key
}

// ---------------------------------------------------------------------------
// 卡片摘要契约（FR-2/FR-3）
// ---------------------------------------------------------------------------

/** 卡片摘要：icon + 折叠行文案 + 展开体字段对。 */
export interface CardSummary {
  icon: string
  /** 折叠行单行文案（≤120 字符，禁止多行）。 */
  line: string
  /** 展开体字段（FR-3 结构化展示）。 */
  details?: Array<[string, string]>
  /** true = 错误态（红 icon 语义由调用方处理）。 */
  isError?: boolean
}

/**
 * 卡片 summarize 函数签名。返回 null 的唯一合法含义 = 交 fallbackRow（FR-4）。
 * args/result 均可能为 undefined（半截 JSON / 非 JSON 结果）。
 */
export type CardSummarize = (
  args: Record<string, unknown> | undefined,
  result: Record<string, unknown> | undefined,
  block: ToolBlock,
) => CardSummary | null

// ---------------------------------------------------------------------------
// fallbackRow 契约（FR-4：keyed 命中替换通用行，解析失败必须自行兜底）
// ---------------------------------------------------------------------------

export interface FallbackModel {
  toolName: string
  /** args 侧一行：第一个字符串参数值的首行；无则 callId。 */
  argLine: string
  /** 输出首行（可能为空）。 */
  outputLine: string
  isError: boolean
}

/** 由 block 推导兜底模型；任何输入都返回可渲染结构（永不 throw / 永不 null）。 */
export function fallbackModel(toolName: string, block: ToolBlock): FallbackModel {
  const args = parseArgs(argsRawOf(block))
  let argLine = ''
  if (args !== undefined) {
    for (const v of Object.values(args)) {
      if (typeof v === 'string' && v !== '') {
        argLine = firstLine(v)
        break
      }
    }
  }
  if (argLine === '') argLine = block.callId ?? ''
  const out = resultText(block)
  const isErr = isSettled(block) && block.isError === true
  return {
    toolName,
    argLine: argLine.slice(0, 120),
    outputLine: firstLine(out).slice(0, 200),
    isError: isErr,
  }
}
