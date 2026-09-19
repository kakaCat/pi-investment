/**
 * 裁剪标记的假阳性回归（REQ-d3e61a T-5 实测发现）。
 *
 * 条款定义行里**枚举**候选状态（含「本轮不做」四个字）不是裁剪声明；当成裁剪会让
 * 「最该标红的那条」永远标不出红。
 */
import { describe, expect, it } from 'vitest'
import { parseDocument, extractSkippedClauses } from '../src/application/internal/content-gates.js'

describe('extractSkippedClauses：括号里的枚举不算裁剪', () => {
  it('定义行枚举四态（含「本轮不做」）→ **不算**裁剪', () => {
    const md = [
      '# REQ-x 样例',
      '',
      '## 6. 功能点',
      '',
      '**FR-3 需求侧接收标记**：需求功能点自身带接收状态（已被任务接收 / 已完成+证据 / 本轮不做 / **未被接收（红）**），随卡的生命周期自动更新。',
      '- AC1：取消某张卡的交付后，该功能点回落为「未被接收（红）」。',
      '',
      '**FR-9 幂等**：重复调用不动。',
      '',
    ].join('\n')
    expect(extractSkippedClauses(parseDocument(md))).toEqual([])
  })

  it('括号外的裁剪声明仍然被认（不能把功能一起修掉）', () => {
    const md = [
      '# REQ-x 样例',
      '',
      '**FR-7 导出**：本轮不做（数据源未就绪，下轮补）。',
      '',
    ].join('\n')
    expect(extractSkippedClauses(parseDocument(md))).toEqual(['FR-7'])
  })

  it('紧随 2 行的裁剪说明仍被认', () => {
    const md = ['**FR-8 迁移**：待评估。', '- 本轮裁剪：存量数据不齐', ''].join('\n')
    expect(extractSkippedClauses(parseDocument(md))).toEqual(['FR-8'])
  })
})
