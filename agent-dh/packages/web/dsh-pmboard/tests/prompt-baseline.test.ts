/**
 * P1 注入基线回归（REQ-422af1 t7）—— 六节点 light/heavy 的解析结果必须与 **P1 基线快照**逐字一致。
 *
 * 旧快照如何处理（t7 明示，见汇报）：
 *   - tests/fixtures/stage-prompts-baseline.json（P0 冻结快照）**保留不动**——它是 "P0 零行为变更"
 *     的历史对照物（当时 STAGE_PROMPTS 常量直取文本）；P1 起注入文本按设计变化（light/heavy 分化 +
 *     铁律正文 + 链声明物化），故它不再作为等价断言对象，本测试改锁 **P1 基线**。
 *   - P1 基线由 scripts/dump-stage-prompts.mjs 产出（tests/fixtures/stage-prompts-baseline-p1.json），
 *     文本按设计演进时**显式重跑该脚本**更新，diff 即变更留痕。
 *
 * 对照物：P1 基线 6 节点 × 2 难度 = 12 键，逐字（含空白与换行）。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolveStagePrompt, PROMPT_STAGES, DIFFICULTIES } from '../src/domain/prompt/index.js'

const p1Baseline = JSON.parse(
  readFileSync(fileURLToPath(new URL('./fixtures/stage-prompts-baseline-p1.json', import.meta.url)), 'utf8'),
) as Record<string, string>

/** 首个差异位置（逐字比对失败时给出可复核的坐标，而不是一句 not equal）。 */
function firstDiff(a: string, b: string): string {
  const n = Math.min(a.length, b.length)
  for (let i = 0; i < n; i++) {
    if (a[i] !== b[i]) return 'offset ' + i + ' expected=' + JSON.stringify(b[i]) + ' actual=' + JSON.stringify(a[i])
  }
  return a.length === b.length ? 'equal' : 'length a=' + a.length + ' b=' + b.length
}

describe('P1 基线：六节点 light/heavy 解析结果逐字一致', () => {
  it('P1 基线含 6 节点 × 2 难度 = 12 键', () => {
    const expected = PROMPT_STAGES.flatMap((s) => DIFFICULTIES.map((d) => s + '/' + d)).sort()
    expect(Object.keys(p1Baseline).sort()).toEqual(expected)
  })

  for (const stage of PROMPT_STAGES) {
    for (const difficulty of DIFFICULTIES) {
      it(stage + '/' + difficulty + ' 与 P1 基线逐字一致（含空白与换行）', () => {
        const key = stage + '/' + difficulty
        const resolved = resolveStagePrompt({ stage, difficulty })
        expect(firstDiff(resolved.text, p1Baseline[key] ?? ''), 'diff ' + key).toBe('equal')
        expect(resolved.text).toBe(p1Baseline[key])
      })
    }
  }

  it('六节点 light 与 heavy 解析出的文本彼此不同（难度轴已生效）', () => {
    const same = PROMPT_STAGES.filter((s) => resolveStagePrompt({ stage: s, difficulty: 'light' }).text
      === resolveStagePrompt({ stage: s, difficulty: 'heavy' }).text)
    expect(same, '以下节点 light/heavy 未分化：\n' + same.join('\n')).toEqual([])
  })

  it('P0 历史快照仍在且未被覆盖（6 个 stage key，字样为 P0 常量直取文本）', () => {
    const p0Path = fileURLToPath(new URL('./fixtures/stage-prompts-baseline.json', import.meta.url))
    expect(existsSync(p0Path), 'P0 快照是历史对照物，不得删除').toBe(true)
    const p0 = JSON.parse(readFileSync(p0Path, 'utf8')) as Record<string, string>
    expect(Object.keys(p0).sort()).toEqual([...PROMPT_STAGES].sort())
    // P0 文本含「REQ-31e11f stage-prompts」印记；P1 的分片文本不含该印记（证明两者确为不同代基线）
    for (const stage of PROMPT_STAGES) {
      expect(p0[stage], stage).toContain('REQ-31e11f stage-prompts')
    }
  })
})
