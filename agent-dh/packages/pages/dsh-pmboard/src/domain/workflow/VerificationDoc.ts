/**
 * verification.md 渲染（REQ-308b9a FR-7 / AC-7.1~7.3、7.7~7.8）。
 *
 * 纯渲染：输入验收单 + 任务投影 + 文档检查结果，输出 markdown —— 零 I/O、无时间随机。
 * 「操作步骤 / 预期结果」**派生**自任务卡 acceptance（已过"怎么验"门槛）与需求级验收项，
 * 不新增人工录入字段（brainstorming 决策）。
 *
 * 消息一律走 fmt（domain 层零拼接，见 tests/message-hygiene.test.ts）。
 *
 * @module dsh-pmboard/domain/workflow/VerificationDoc
 */
import type { DocCheckResult } from './DocCompleteness.js'
import { fmt } from '../text/fmt.js'

export interface VerificationDocItem {
  id: string
  /** 业务标题（任务标题或"需求级"） */
  title: string
  /** 验收标准原文（怎么算过） */
  criterion: string
  /** 派生的操作步骤来源（任务卡 acceptance / 需求级标准） */
  howToVerify: string
  status: 'pending' | 'passed' | 'failed' | 'not_verifiable'
  opinion?: string
  /** 裁决人（验收结果表用） */
  decidedBy?: string
  /** 裁决时间（毫秒时间戳） */
  decidedAt?: number
}

export interface VerificationDocInput {
  reqId: string
  title: string
  summary: string
  sheetVersion: number
  items: readonly VerificationDocItem[]
  /** 测试报告（证据里的测试输出摘要） */
  testReport: readonly string[]
  docCheck: DocCheckResult
}

const STATUS_MARK: Readonly<Record<VerificationDocItem['status'], string>> = {
  pending: '⬜ 待验收',
  passed: '✓ 通过',
  failed: '✗ 不通过',
  not_verifiable: '⊘ 不可验收',
}

/** 毫秒时间戳 → YYYY-MM-DD HH:mm（无中文拼接，纯数字格式）。 */
function fmtTime(ms: number | undefined): string {
  if (ms === undefined || !Number.isFinite(ms)) return ''
  const d = new Date(ms)
  const p = (n: number): string => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/** acceptance 文本 → 编号操作步骤（按分号/换行拆）。 */
function toSteps(text: string): string[] {
  const parts = text.split(/[；;\n]/).map(s => s.trim()).filter(s => s.length > 0)
  return parts.length > 0 ? parts : [text.trim() || '（未填写验收标准）']
}

export function renderVerificationDoc(input: VerificationDocInput): string {
  const lines: string[] = []
  lines.push(fmt('# {reqId} 验收文档', { reqId: input.reqId }))
  lines.push('')
  lines.push(fmt('> 自动生成于 reqboard_submit(kind=verification) · 验收单 v{version}', { version: input.sheetVersion }))
  lines.push('')
  lines.push(fmt('**交付结论**：{summary}', { summary: input.summary }))
  lines.push('')
  lines.push('## 1. 验收列表')
  lines.push('')
  for (const it of input.items) {
    lines.push(fmt('### {id} · {title}', { id: it.id, title: it.title }))
    lines.push('')
    lines.push(fmt('**验收内容**：{criterion}', { criterion: it.criterion }))
    lines.push('')
    lines.push('**操作步骤**：')
    toSteps(it.howToVerify).forEach((s, i) => lines.push(fmt('{n}. {step}', { n: i + 1, step: s })))
    lines.push('')
    lines.push(fmt('**预期结果**：按上述步骤执行后满足验收标准：{how}', { how: it.howToVerify }))
    lines.push('')
    lines.push(fmt('**实际结果**：{actual}', { actual: it.opinion ?? '（待填写）' }))
    lines.push('')
    lines.push(fmt('**验收状态**：{mark}', { mark: STATUS_MARK[it.status] }))
    lines.push('')
    lines.push('---')
    lines.push('')
  }
  lines.push('## 2. 测试报告')
  lines.push('')
  if (input.testReport.length === 0) lines.push('- （未提供测试输出）')
  else for (const t of input.testReport) lines.push(fmt('- {line}', { line: t }))
  lines.push('')
  lines.push('## 3. 文档完整性检查')
  lines.push('')
  if (input.docCheck.passed) lines.push('✓ 9 类文档齐全')
  else for (const m of input.docCheck.missing) lines.push(fmt('✗ 缺失：{item}', { item: m }))
  lines.push('')
  lines.push('## 4. 验收结果')
  lines.push('')
  lines.push('| 编号 | 验收项 | 状态 | 验收人 | 验收时间 |')
  lines.push('|---|---|---|---|---|')
  for (const it of input.items) {
    lines.push(fmt('| {id} | {title} | {status} | {by} | {at} |', {
      id: it.id, title: it.title, status: STATUS_MARK[it.status],
      by: it.decidedBy ?? '', at: fmtTime(it.decidedAt),
    }))
  }
  lines.push('')
  return lines.join('\n')
}
