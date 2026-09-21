import { describe, it, expect } from 'vitest'
import { renderTokenTab, renderTokenPlaceholder } from '../src/client/token-info.ts'
import type { RequirementTokenView, TokenBuckets } from '../src/shared/protocol.ts'

const B = (n: number): TokenBuckets => ({ uncachedInputTokens: n, outputTokens: n * 2, cacheReadTokens: n * 10, cacheWriteTokens: 0 })

function view(over: Partial<RequirementTokenView> = {}): RequirementTokenView {
  return {
    requirementId: 'REQ-abc123',
    totals: B(10),
    byStage: [
      { stage: 'draft', buckets: B(3), executions: [] },
      { stage: 'design', executions: [] },
      { stage: 'implementing', buckets: B(7), executions: [{ taskId: 't-abc123', title: '任务甲', status: 'in_progress', delta: B(3) }] },
    ],
    degraded: false,
    ...over,
  }
}

describe('REQ-a33899 t6 · Token tab 渲染', () => {
  it('渲染五格汇总 + 折叠块 + 节点表（有快照给数字、无快照给「无快照」）', () => {
    const html = renderTokenTab(view())
    expect(html).toContain('dsh-pm-stats')
    expect(html).toContain('📊 按流程节点')
    expect(html).toContain('dsh-pm-tok-table')
    expect(html).toContain('t-abc123')
    expect(html).toContain('无快照')
    // 无快照的节点不得渲染 0
    const designRow = html.split('<tr').find(r => r.includes('设计')) ?? ''
    expect(designRow).toContain('无快照')
  })

  it('固定系统提示词：每段可展开看具体内容（pre），不可用明确标注', () => {
    const html = renderTokenTab(view({
      systemPrompt: {
        perTurnChars: 100, perTurnEstTokens: 25, turns: 0, sections: [
          { name: 'genome:rules', chars: 12, estTokens: 3, text: 'R-001 买入前确认' },
        ], contexts: [], toolsChars: 0, source: 'assembled',
      },
    }))
    expect(html).toContain('🧱 固定系统提示词')
    expect(html).toContain('dsh-pm-prompt-text')
    expect(html).toContain('R-001 买入前确认')
    expect(html).toContain('回合数不可得')

    const off = renderTokenTab(view({ systemPrompt: { perTurnChars: 0, perTurnEstTokens: 0, turns: 0, sections: [], contexts: [], toolsChars: 0, source: 'unavailable' } }))
    expect(off).toContain('不可用')
    expect(off).toContain('不猜数字')
  })

  it('注入提示词：有记录给聚合与明细，无记录给空态（不张冠李戴）', () => {
    const html = renderTokenTab(view({
      injections: {
        count: 2, chars: 1000, estTokens: 250, sharePct: 12.5,
        byStage: [{ name: 'brainstorming', chars: 400, estTokens: 100 }],
        items: [{ at: 1700000000000, stage: 'brainstorming', routeKey: 'brainstorming/light/feature', fragmentIds: ['f1'], chars: 400, estTokens: 100 }],
      },
    }))
    expect(html).toContain('💉 注入提示词')
    expect(html).toContain('brainstorming/light/feature')
    expect(html).toContain('占本需求 12.5%')

    const empty = renderTokenTab(view({ injections: { count: 0, chars: 0, estTokens: 0, byStage: [], items: [] } }))
    expect(empty).toContain('无记录')
    expect(empty).toContain('不做张冠李戴')
  })

  it('degraded=true 时口径条显式提示缺失段', () => {
    const html = renderTokenTab(view({ degraded: true }))
    expect(html).toContain('部分节点/执行无快照')
  })

  it('占位符渲染空态文本', () => {
    expect(renderTokenPlaceholder('加载中…')).toContain('加载中…')
  })
})
