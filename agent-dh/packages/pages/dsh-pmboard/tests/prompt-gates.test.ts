/**
 * 提示词六条门禁（REQ-422af1 t5）—— 每条都必须能变红（本仓铁律：只测成功路径等于没测）。
 *
 * 1 覆盖完整   6×2×6 解析非空 + ⑤ 铁律层存在且每次并入
 * 2 工具名一致 注入文本里的 reqboard_* ⊆ 实际注册集合（扫描器与 tests/stage-prompts.test.ts 同源）
 * 3 预算上限   默认预算 ≤ DEFAULT_PROMPT_BUDGET；极小预算返回结构化超限而非静默裁保底
 * 4 孤岛与唯一 id 唯一；每个分片至少被一条路由命中
 * 5 链声明完整 每节点有链声明（含「下一步：」），next ∈ 状态机合法后继
 * 6 源/产物同步 fragments 源与 generated 产物逐字节一致（调 check 脚本）
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, existsSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  FRAGMENT_LIBRARY,
  resolveStagePrompt,
  PROMPT_STAGES,
  DIFFICULTIES,
  CATEGORIES,
  STAGE_CHAIN,
  isLegalNext,
  DEFAULT_PROMPT_BUDGET,
} from '../src/domain/prompt/index.js'

const SRC = fileURLToPath(new URL('../src', import.meta.url))
const PKG_ROOT = fileURLToPath(new URL('..', import.meta.url))

/** 实际注册的工具名：静态扫 src/tools 下的 name: 'reqboard_x'（与运行时注册同源）。 */
function registeredNames(): Set<string> {
  const names = new Set<string>()
  for (const dir of readdirSync(join(SRC, 'tools'), { withFileTypes: true })) {
    if (!dir.isDirectory()) continue
    for (const f of readdirSync(join(SRC, 'tools', dir.name))) {
      if (!f.endsWith('.ts')) continue
      const text = readFileSync(join(SRC, 'tools', dir.name, f), 'utf8')
      for (const m of text.matchAll(/name:\s*'(reqboard_[a-z_]+)'/g)) names.add(m[1]!)
    }
  }
  return names
}

/** 全量请求空间（6 × 2 × 6）的解析结果。 */
function allResolutions() {
  const out = []
  for (const stage of PROMPT_STAGES) {
    for (const difficulty of DIFFICULTIES) {
      for (const category of CATEGORIES) {
        out.push({ stage, difficulty, category, resolved: resolveStagePrompt({ stage, difficulty, category }) })
      }
    }
  }
  return out
}

describe('门禁 1 覆盖完整：任意 (stage,difficulty,category) 解析非空；⑤ 铁律层存在', () => {
  it('6×2×6 全部解析出非空 text（0 例空串）', () => {
    const empty = allResolutions().filter((r) => r.resolved.text.length === 0)
      .map((r) => r.stage + '/' + r.difficulty + '/' + r.category)
    expect(empty, '以下组合解析为空串：\n' + empty.join('\n')).toEqual([])
  })

  it('⑤ 全局铁律分片存在，且每次解析都并入 fragmentIds', () => {
    const globalIds = FRAGMENT_LIBRARY.filter((f) => f.stage === '*' && f.difficulty === '*' && f.category === '*').map((f) => f.id)
    expect(globalIds, '⑤ 铁律层缺失（须至少一个 (*,*,*) 分片）').toContain('common/iron-rules')
    const missing = allResolutions().filter((r) => !globalIds.every((id) => r.resolved.fragmentIds.includes(id)))
      .map((r) => r.stage + '/' + r.difficulty + '/' + r.category)
    expect(missing, '以下组合未并入 ⑤ 铁律：\n' + missing.join('\n')).toEqual([])
  })
})

describe('门禁 2 工具名一致：注入文本里的 reqboard_* ⊆ 注册集合', () => {
  it('所有解析文本提到的 reqboard_* 工具都已注册', () => {
    const registered = registeredNames()
    expect(registered.size, '扫描到的注册工具数应 ≥9（防扫描器失效而假绿）').toBeGreaterThanOrEqual(9)
    const bad: string[] = []
    for (const r of allResolutions()) {
      for (const name of r.resolved.text.matchAll(/reqboard_[a-z_]+/g)) {
        if (!registered.has(name[0])) bad.push(r.resolved.routeKey + ' → ' + name[0])
      }
    }
    expect(bad, '注入文本提到不存在的工具（改名后文本没跟上）：\n' + bad.join('\n')).toEqual([])
  })

  it('链声明的交棒工具也都在注册集合内', () => {
    const registered = registeredNames()
    const bad = PROMPT_STAGES.filter((s) => !registered.has(STAGE_CHAIN[s].tool)).map((s) => s + ' → ' + STAGE_CHAIN[s].tool)
    expect(bad, '链声明引用了不存在的工具：\n' + bad.join('\n')).toEqual([])
  })
})

describe('门禁 3 预算上限：注入 ≤ 预算；连保底超限则结构化报超限', () => {
  it('默认预算下全部组合 charCount ≤ ' + DEFAULT_PROMPT_BUDGET, () => {
    const over = allResolutions().filter((r) => r.resolved.charCount > DEFAULT_PROMPT_BUDGET || r.resolved.overBudget !== undefined)
      .map((r) => r.resolved.routeKey + '=' + r.resolved.charCount)
    expect(over, '超出默认预算：\n' + over.join('\n')).toEqual([])
  })

  it('预算极小时返回结构化 overBudget（floor 仍在 fragmentIds，不静默裁保底）', () => {
    const r = resolveStagePrompt({ stage: 'brainstorming', budget: 5 })
    expect(r.overBudget, '极小预算必须报结构化超限而不是静默裁掉保底').toBeDefined()
    expect(r.overBudget?.reason).toBe('floor-exceeds-budget')
    // P1：缺省难度的节点内容 = brainstorming/light（floor），与 ⑤ common/iron-rules 一并保留
    expect(r.fragmentIds).toContain('brainstorming/light')
    expect(r.fragmentIds).toContain('common/iron-rules')
    expect(r.text.length).toBeGreaterThan(0)
  })
})

describe('门禁 4 孤岛与唯一', () => {
  it('分片 id 唯一', () => {
    const ids = FRAGMENT_LIBRARY.map((f) => f.id)
    const dup = ids.filter((id, i) => ids.indexOf(id) !== i)
    expect(dup, '重复的分片 id：\n' + dup.join('\n')).toEqual([])
  })

  it('每个分片至少被一条路由命中（无孤岛/死提示词）', () => {
    const hit = new Set<string>()
    for (const r of allResolutions()) for (const id of r.resolved.fragmentIds) hit.add(id)
    const islands = FRAGMENT_LIBRARY.filter((f) => !hit.has(f.id)).map((f) => f.id)
    expect(islands, '以下分片没有任何路由命中（孤岛）：\n' + islands.join('\n')).toEqual([])
  })
})

describe('门禁 5 链声明完整：每节点有「下一步」且 next ∈ 状态机合法后继', () => {
  it('每个节点都有链声明，label 含「下一步：」', () => {
    const bad = PROMPT_STAGES.filter((s) => {
      const step = STAGE_CHAIN[s]
      return step === undefined || !step.label.includes('下一步：')
    })
    expect(bad, '以下节点缺链声明（或 label 不含「下一步：」）：\n' + bad.join('\n')).toEqual([])
  })

  it('next 是状态机合法后继（终态必须无后继）', () => {
    const bad = PROMPT_STAGES.filter((s) => !isLegalNext(s, STAGE_CHAIN[s].next))
      .map((s) => s + ' → ' + String(STAGE_CHAIN[s].next))
    expect(bad, '以下链声明的 next 不是合法后继：\n' + bad.join('\n')).toEqual([])
  })

  it('分片文本若已写「下一步：」，其声明必须与链表一致（P1 物化后的防漂移）', () => {
    const bad: string[] = []
    for (const stage of PROMPT_STAGES) {
      const text = resolveStagePrompt({ stage }).text
      const declared = STAGE_CHAIN[stage]
      if (text.includes('下一步：') && !text.includes(declared.label)) {
        bad.push(stage + '：文本里的「下一步」与 STAGE_CHAIN 不一致')
      }
    }
    expect(bad, bad.join('\n')).toEqual([])
  })
})

describe('门禁 6 源/产物同步：fragments 源与 generated 产物一致', () => {
  it('check-prompt-fragments.mjs 退出码为 0', () => {
    const res = spawnSync(process.execPath, [join(PKG_ROOT, 'scripts/check-prompt-fragments.mjs')], {
      cwd: PKG_ROOT, encoding: 'utf8', timeout: 30_000,
    })
    expect(res.status, (res.stdout ?? '') + (res.stderr ?? '')).toBe(0)
  })

  it('产物文件存在且导出了 GENERATED_FRAGMENTS', () => {
    const p = join(SRC, 'domain/prompt/generated/fragments.ts')
    expect(existsSync(p)).toBe(true)
    expect(readFileSync(p, 'utf8')).toContain('GENERATED_FRAGMENTS')
  })
})
