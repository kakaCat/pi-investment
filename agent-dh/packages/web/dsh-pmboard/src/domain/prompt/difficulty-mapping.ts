/**
 * 难度取词映射（REQ-e3b6a0 t6 / FR-4 / NFR-4）——把立项三问的**四档**接进取词的**两档**。
 *
 * 为什么必须有这一层：需求台账里的 `promptDifficulty`（simple/standard/advanced/expert）此前
 * **只存不用**——取词入口 `resolveStagePrompt` 只认 `light|heavy`，于是"我明明选了 expert"
 * 的需求照样被注入轻档模板（实证：本需求自己在 brainstorming 阶段被注入了轻档）。
 *
 * 映射（单调，不跳档）：
 *
 *     simple  ┐
 *             ├──▶ light
 *     standard┘
 *     advanced┐
 *             ├──▶ heavy
 *     expert  ┘
 *
 * **冲突取重不取轻**：声明档位与"由需求文本推断的档位"不一致时，取 heavier——宁可多给纪律，
 * 不可少给（少给 = 该走的闸门没走）。
 *
 * 分层：domain 最内层，零 import（不引 shared，故入参收 `string`；与 shared 的 PromptDifficulty
 * 枚举一致性由 tests/difficulty-mapping.test.ts 用真实枚举值锁死）。
 *
 * @module dsh-pmboard/domain/prompt/difficulty-mapping
 */
import { fmt } from '../text/fmt.js'
import type { Difficulty } from './types.js'

/** 声明档位 → 取词档位；未声明或无法识别 → undefined（交给文本推断，不静默回落 light）。 */
export function difficultyFromDeclaredPrompt(declared: string | undefined): Difficulty | undefined {
  if (declared === 'simple' || declared === 'standard') return 'light'
  if (declared === 'advanced' || declared === 'expert') return 'heavy'
  return undefined
}

/** 取重不取轻：两者都给时必须取 heavy。 */
export function heavierDifficulty(a: Difficulty, b: Difficulty): Difficulty {
  return a === 'heavy' || b === 'heavy' ? 'heavy' : 'light'
}

/** 一行可读的映射说明（进注入留痕的 difficultyReasons）。 */
export function describeDeclaredDifficulty(declared: string, mapped: Difficulty): string {
  return fmt('声明难度 {declared} → 取词档 {mapped}', { declared, mapped })
}
