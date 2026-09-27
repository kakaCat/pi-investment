// serves: FR-5
/**
 * 工具描述 / 提示词文案契约（REQ-260927123256-196b t4 · serves: FR-5 / I-5）。
 *
 * 「缺省阻塞」是可证伪锚点：文案写不清，用户与 agent 就仍以为「弹框出现=门已放行」。
 */
import { describe, it, expect } from 'vitest'
import { ASK_CONFIRM_PROMPT } from '../src/tools/AskConfirmTool/prompt.js'
import { CONFIRM_RECEIPT_PROMPT } from '../src/tools/ConfirmReceiptTool/prompt.js'
import { defineAskConfirmTool } from '../src/tools/index.js'

describe('FR-5 文案契约', () => {
  it('ASK_CONFIRM_PROMPT 含「缺省阻塞」，并说明显式宽限 = 主动放弃阻塞', () => {
    expect(ASK_CONFIRM_PROMPT).toContain('缺省阻塞')
    expect(ASK_CONFIRM_PROMPT).toContain('主动放弃阻塞')
    expect(ASK_CONFIRM_PROMPT).toContain('reqboard_confirm_receipt')
    expect(ASK_CONFIRM_PROMPT).toContain('REQBOARD_CONFIRM_PENDING')
  })

  it('inline_grace_ms 参数 description 含「缺省」与「阻塞」', () => {
    const tool = defineAskConfirmTool({} as never) as any
    const desc: string = tool.parameters?.properties?.inline_grace_ms?.description ?? ''
    expect(desc).toContain('缺省')
    expect(desc).toContain('阻塞')
    expect(desc).toContain('主动放弃阻塞')
  })

  it('CONFIRM_RECEIPT_PROMPT 保留取回执指引，并补「被中止的挂起记录同样可凭 ticket 查询」', () => {
    expect(CONFIRM_RECEIPT_PROMPT).toContain('reqboard_confirm_receipt')
    expect(CONFIRM_RECEIPT_PROMPT).toContain('被中止')
  })
})
