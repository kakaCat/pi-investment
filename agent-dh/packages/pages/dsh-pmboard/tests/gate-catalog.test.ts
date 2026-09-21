/**
 * 闸门目录一致性测试（REQ-e3b6a0 t2 / FR-10 / AC-10.1）。
 *
 * 目的不是"再测一遍常量"，而是锁住三件事：
 *  ① 闸门表五条、G0 无产物门、四道产物门与收敛前的字面量表**逐条等价**；
 *  ② GateSpec.humanOnly 与 RequirementStatus.HUMAN_ONLY_REQ_TRANSITIONS 的闸门子集一致
 *     （两处各存一份是刻意的：避免 domain/gate ↔ domain/requirement 值环，故用测试锁死）；
 *  ③ advanceTargetFor / questionCardFor 与收敛前的实现**逐条对拍**（旧实现作为 oracle 抄在本文件里）。
 *
 * @module dsh-pmboard/tests/gate-catalog
 */
import { describe, it, expect } from 'vitest'
import {
  GATE_CATALOG,
  ARTIFACT_CONFIRM_GATES,
  advanceTargetFor,
  questionCardFor,
  gateForTransition,
  gateIdForTransition,
} from '../src/domain/gate/GateCatalog.js'
import { HUMAN_ONLY_REQ_TRANSITIONS } from '../src/domain/requirement/RequirementStatus.js'
import { MAIN_REQ_STATUSES } from '../src/shared/protocol.js'

// ── 收敛前的旧实现（oracle，逐字抄自 commit 前的 AskConfirm / support）──────────
const OLD_ADVANCE_MAP: Readonly<Record<string, string>> = {
  brainstorming: 'design',
  design: 'decomposing',
  decomposing: 'implementing',
}
// 2026-09-21 用户裁定：G2 改「确认设计文档」（kind=design）、G3 改「批准拆分计划」
// （kind=decomposition，target=plan 弹框分支随之挪到 decomposing>implementing）——
// 本 oracle 同步更新为新语义的字面量基准。
function oldQuestionCard(gateKind: string | undefined, from: string, to: string): string {
  const questionByTransition: Record<string, string> = {
    'brainstorming>design': '需求文档已完成，是否确认进入设计？',
    'design>decomposing': '设计文档已完成，是否确认进入拆分？',
    'decomposing>implementing': '拆分计划已提交，是否批准落库任务卡并进入实施？',
    'accepting>archived': '验收材料已提交，是否验收通过并归档？',
  }
  const question = questionByTransition[from + '>' + to] ?? ('是否确认推进到 ' + to + '？')
  const call = gateKind === 'plan' || (from === 'decomposing' && to === 'implementing')
    ? "{ target: 'plan', question: '" + question + "' }"
    : "{ target: 'artifact', kind: '" + (gateKind ?? 'requirement') + "', question: '" + question + "' }"
  return '\n【问题卡】直接调 reqboard_ask_confirm 完成确认（用户点肯定项 → 自动落章并推进 ' + from + ' → ' + to + '）：\n  reqboard_ask_confirm(' + call + ')'
}

describe('闸门目录（GateCatalog）', () => {
  it('五道门，id 唯一，G0 无 from 无 requiredKind', () => {
    expect(GATE_CATALOG).toHaveLength(5)
    expect(new Set(GATE_CATALOG.map(g => g.id))).toEqual(new Set(['G0', 'G1', 'G2', 'G3', 'G4']))
    const g0 = GATE_CATALOG.find(g => g.id === 'G0')!
    expect(g0.from).toBeUndefined()
    expect(g0.requiredKind).toBeUndefined()
    expect(g0.verdictShape).toBe('form')
  })

  it('四道产物门与收敛前的字面量表逐条等价', () => {
    expect(ARTIFACT_CONFIRM_GATES).toEqual({
      'brainstorming>design': 'requirement',
      'design>decomposing': 'design',
      'decomposing>implementing': 'decomposition',
      'accepting>archived': 'verification',
    })
    // 表由 GATE_CATALOG 派生：产物门数 = 有 from 且有 requiredKind 的闸门数
    const derived = GATE_CATALOG.filter(g => g.from !== undefined && g.requiredKind !== undefined)
    expect(Object.keys(ARTIFACT_CONFIRM_GATES)).toHaveLength(derived.length)
  })

  it('humanOnly 与 HUMAN_ONLY_REQ_TRANSITIONS 的闸门子集一致（两份真相互锁）', () => {
    for (const g of GATE_CATALOG) {
      if (g.from === undefined) continue
      const key = g.from + '>' + g.to
      expect(g.humanOnly, key).toBe(HUMAN_ONLY_REQ_TRANSITIONS.has(key))
    }
    // 反向：**流水线确认门**类的人工专属转移都必须被某条闸门覆盖。
    // 排除两类非确认门：① 取消类（*>canceled / canceled>*）；② 回退类（to 在流水线上游，
    // 如 REQ-4842fe 新增的 implementing>design 返工回上游）——回退是恢复动作，
    // 走失败处置弹框三选，不是"向下一个节点"的确认门，故不进 GATE_CATALOG。
    const order = new Map(MAIN_REQ_STATUSES.map((s, i) => [s as string, i]))
    const gateKeys = new Set(GATE_CATALOG.filter(g => g.from).map(g => g.from + '>' + g.to))
    const isForward = (k: string): boolean => {
      const [from, to] = k.split('>')
      if (from === undefined || to === undefined) return false
      if (to === 'canceled' || from === 'canceled') return false
      return (order.get(to) ?? -1) > (order.get(from) ?? -1)
    }
    const humanGateKeys = [...HUMAN_ONLY_REQ_TRANSITIONS].filter(isForward)
    for (const k of humanGateKeys) expect(gateKeys.has(k), k).toBe(true)
  })

  it('advanceTargetFor 与旧 ADVANCE_MAP 逐条等价', () => {
    const froms = ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting', 'archived', 'canceled', 'done']
    for (const from of froms) {
      expect(advanceTargetFor(from), from).toBe(OLD_ADVANCE_MAP[from])
    }
  })

  it('questionCardFor 与旧实现逐条等价（含 fallback 与 plan 分支）', () => {
    const cases: Array<[string | undefined, string, string]> = [
      ['requirement', 'brainstorming', 'design'],
      ['plan', 'design', 'decomposing'],
      ['decomposition', 'decomposing', 'implementing'],
      ['verification', 'accepting', 'archived'],
      [undefined, 'draft', 'brainstorming'],
      ['notes', 'implementing', 'accepting'],
    ]
    for (const [kind, from, to] of cases) {
      expect(questionCardFor(kind, from, to), from + '>' + to).toBe(oldQuestionCard(kind, from, to))
    }
  })

  it('按转移键查闸门', () => {
    expect(gateIdForTransition('brainstorming', 'design')).toBe('G1')
    expect(gateIdForTransition('design', 'decomposing')).toBe('G2')
    expect(gateIdForTransition('decomposing', 'implementing')).toBe('G3')
    expect(gateIdForTransition('accepting', 'archived')).toBe('G4')
    expect(gateForTransition('draft', 'brainstorming')).toBeUndefined()
  })
})
