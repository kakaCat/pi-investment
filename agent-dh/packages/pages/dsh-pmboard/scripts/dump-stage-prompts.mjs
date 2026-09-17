#!/usr/bin/env node
/**
 * P1 注入基线快照（REQ-422af1 t7）—— 六节点 × light/heavy 的 resolveStagePrompt 结果逐字落盘。
 *
 * 与 P0 快照的关系：
 *   - tests/fixtures/stage-prompts-baseline.json 是 **P0 冻结快照**（t1 从 StagePromptSpec 常量直取，
 *     逐字、不 trim），它是"P0 零行为变更"的历史对照物，P1 起不再更新、也不再被等价断言引用；
 *   - 本脚本产出 **P1 基线** tests/fixtures/stage-prompts-baseline-p1.json：
 *     六节点 light/heavy 的注入文本（含 overrides 与 common/iron-rules），供
 *     tests/prompt-baseline.test.ts 做回归锁（P1 起文本按设计允许变化，变化必须显式更新本快照）。
 *
 * 口径：逐字（不 trim、不改空白/换行）。
 * 用法：node scripts/dump-stage-prompts.mjs
 * 幂等：连跑两次输出逐字节一致（diff 为空）。
 */
import { writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { tsImport } from 'tsx/esm/api'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')

const mod = await tsImport(join(root, 'src/domain/prompt/index.ts'), import.meta.url)
const { resolveStagePrompt, PROMPT_STAGES, DIFFICULTIES } = mod
if (!Array.isArray(PROMPT_STAGES) || !Array.isArray(DIFFICULTIES)) {
  throw new Error('dump-stage-prompts: 未能从 domain/prompt 读到 PROMPT_STAGES / DIFFICULTIES')
}

const snapshot = {}
for (const stage of PROMPT_STAGES) {
  for (const difficulty of DIFFICULTIES) {
    const key = stage + '/' + difficulty
    const text = resolveStagePrompt({ stage, difficulty }).text
    if (typeof text !== 'string' || text.length === 0) {
      throw new Error('dump-stage-prompts: ' + key + ' 注入文本为空——拒绝写出残缺快照')
    }
    snapshot[key] = text
  }
}

const json = JSON.stringify(snapshot, null, 2) + '\n'
const target = join(root, 'tests/fixtures/stage-prompts-baseline-p1.json')
writeFileSync(target, json, 'utf8')
console.log('[dump-stage-prompts] wrote ' + target)
console.log('[dump-stage-prompts] keys=' + Object.keys(snapshot).length + ' bytes=' + json.length)
