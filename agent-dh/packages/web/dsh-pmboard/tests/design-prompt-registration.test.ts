/**
 * 设计阶段提示词写明登记命令（REQ-260924213231-b1c4 T-8 · serves: FR-5）
 *
 * 验收口径（design/test-cases.md TC-10 / TC-17）：
 *  - TC-10 回归：解析 design/light 与 design/heavy（含六种类型档路由壳），注入文本必须含
 *    登记命令 `reqboard_submit(kind=design)` + 触发者说明 + 「不要猜 kind」；且**不含**
 *    「落盘即产物 / 目录自动发现登记」旧断言——事故根因正是提示词宣称登记自动发生
 *    （req-2cd3 复盘：agent 据此认为不用调工具，工具面其实没有入口）。
 *  - TC-17 故障注入回归：本次只改提示词文本，G2 的拆分内容硬门禁不得因此放宽——
 *    design/*.md 含 depends_on 表头仍被 `design_contains_decomposition` 拒。
 */
import { describe, it, expect } from 'vitest'
import {
  resolveStagePrompt,
  FRAGMENT_LIBRARY,
  CATEGORIES,
  DIFFICULTIES,
} from '../src/domain/prompt/index.js'
import { checkDesignDecompositionGate } from '../src/application/internal/design-gates.js'

const COMMAND = 'reqboard_submit(kind=design)'
const TRIGGER = 'agent 自己'
/** 旧断言（事故源）：登记被写成"落盘即发生/由目录自动发现"，agent 遂不调工具。 */
const STALE_CLAIMS = ['落盘即产物', '目录自动发现登记']

function overrideText(id: string): string {
  const f = FRAGMENT_LIBRARY.find((x) => x.id === id)
  if (f === undefined) throw new Error('找不到分片：' + id)
  return f.text
}

describe('TC-10 设计提示词写明登记命令与触发者（design/light 与 design/heavy）', () => {
  for (const difficulty of DIFFICULTIES) {
    it('design/' + difficulty + ' 注入文本含 ' + COMMAND + '、触发者与「不要猜 kind」', () => {
      const text = resolveStagePrompt({ stage: 'design', difficulty }).text
      expect(text).toContain(COMMAND)
      expect(text, '要写明由谁触发登记（本窗口 agent 自己，不是等人/等目录）').toContain(TRIGGER)
      expect(text, '要明说不要猜 kind').toContain('不要猜 kind')
    })

    it('design/' + difficulty + ' 注入文本不含旧断言（' + STALE_CLAIMS.join(' / ') + '）', () => {
      const text = resolveStagePrompt({ stage: 'design', difficulty }).text
      for (const stale of STALE_CLAIMS) {
        expect(text, 'design/' + difficulty + ' 仍含旧断言「' + stale + '」').not.toContain(stale)
      }
    })

    it('design/' + difficulty + '/overrides 分片是命令的承载处（防只改正文/只改注释）', () => {
      const id = 'design/' + difficulty + '/overrides'
      const text = overrideText(id)
      expect(text).toContain(COMMAND)
      expect(text).toContain(TRIGGER)
      expect(text).toContain('不要猜 kind')
      for (const stale of STALE_CLAIMS) expect(text, id + ' 仍含旧断言「' + stale + '」').not.toContain(stale)
    })
  }

  it('六种类型档 × 两档难度的路由壳都带上登记命令（不是只在缺省档生效）', () => {
    const missing: string[] = []
    for (const difficulty of DIFFICULTIES) {
      for (const category of CATEGORIES) {
        const r = resolveStagePrompt({ stage: 'design', difficulty, category })
        const key = difficulty + '/' + category
        if (!r.fragmentIds.includes('design/' + difficulty + '/overrides')) missing.push(key + ' 未含 overrides 分片')
        if (!r.text.includes(COMMAND)) missing.push(key + ' 文本缺 ' + COMMAND)
      }
    }
    expect(missing, '以下类型档路由未带上登记说明：\n' + missing.join('\n')).toEqual([])
  })

  it('登记命令是 reqboard_submit 的 design 种类（不是别的阶段种类）', () => {
    for (const difficulty of DIFFICULTIES) {
      const text = overrideText('design/' + difficulty + '/overrides')
      // 「不要猜 kind」的正面依据：只有 design 是登记种类，其余四类属别的阶段产物。
      const otherKinds = ['requirement', 'plan', 'verification', 'archive']
      for (const k of otherKinds) {
        expect(text, '提示词应点名「' + k + '」属别的阶段产物（不要猜）').toContain(k)
      }
    }
  })
})

describe('TC-17 故障注入回归：提示词改动不放松拆分内容硬门禁', () => {
  const REQ = 'REQ-t8t170'
  const DESIGN_DIR = 'docs/requirements/' + REQ + '/design'

  function fakeDocs(files: Record<string, string>) {
    return {
      exists: (p: string) => files[p] !== undefined,
      read: async (p: string) => files[p],
      list: (d: string) => Object.keys(files)
        .filter((p) => p.startsWith(d + '/'))
        .map((p) => ({ name: p.slice(d.length + 1), isFile: true })),
    }
  }

  it('design/*.md 含 depends_on 表头 → 仍被 design_contains_decomposition 拒', async () => {
    const docs = fakeDocs({
      [DESIGN_DIR + '/architecture.md']: '# 架构\n\n| key | title | depends_on |\n|---|---|---|\n| t1 | 甲 | — |\n',
    })
    const failure = await checkDesignDecompositionGate(docs as never, { id: REQ } as never)
    expect(failure?.code).toBe('design_contains_decomposition')
    expect(failure?.gaps?.join(' ')).toContain('depends_on')
  })

  it('干净设计文档（散文提及 depends_on）→ 放行（门禁不误伤）', async () => {
    const docs = fakeDocs({
      [DESIGN_DIR + '/architecture.md']: '# 架构\n\n依赖关系用 depends_on 概念描述，非任务表。\n',
    })
    expect(await checkDesignDecompositionGate(docs as never, { id: REQ } as never)).toBeUndefined()
  })
})
