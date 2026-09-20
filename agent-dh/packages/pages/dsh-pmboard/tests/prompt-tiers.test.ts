/**
 * t7 验收：六节点 light/heavy 分片（REQ-422af1 t7）。
 *
 * 断言（逐条对应 t7 验收口径）：
 *   ① 六节点 light 与 heavy 解析出的文本**不同**（难度轴生效）；
 *   ② 每节点 light 的 charCount < heavy 的 charCount；
 *   ③ brainstorming/heavy 与 vendor 原文**逐字一致**（byte-level，含空白换行）；
 *   ④ 其余 4 个 vendor 主 skill 的 heavy 镜像同样逐字一致（防漂移）；
 *   ⑤ light **不含** heavy 独有要素关键词（省 token 的来源）；
 *   ⑥ 注入顺序固定三段：vendor 原文 → overrides（floor）→ common/iron-rules；
 *   ⑦ heavy 主 skill 原文不裁（预算极小时 floor 仍保留、结构化报超限）；
 *   ⑧ decomposing 例外：superpowers 无对应 skill，heavy 为自写档。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'
import {
  resolveStagePrompt,
  FRAGMENT_LIBRARY,
  PROMPT_STAGES,
  STAGE_CHAIN,
  type Fragment,
  type PromptStage,
} from '../src/domain/prompt/index.js'

const SRC = fileURLToPath(new URL('../src', import.meta.url))
const VENDOR_DIR = join(SRC, 'domain/prompt/vendor/superpowers')
const FRAGMENTS_DIR = join(SRC, 'domain/prompt/fragments')

/** heavy 主 skill 的唯一映射（与 scripts/inline-prompt-fragments.mjs 的 VENDOR_MAIN_SKILLS 同源）。 */
const VENDOR_MAIN_SKILLS: Readonly<Record<string, string>> = {
  brainstorming: 'brainstorming',
  // 2026-09-21 用户裁定：design 移除（设计阶段只写设计文档，heavy 为自写档）
  implementing: 'executing-plans',
  accepting: 'verification-before-completion',
  archived: 'finishing-a-development-branch',
}

/** 每节点 heavy 独有要素关键词（逐字来自 vendor 原文 / 自写完整档）。 */
const HEAVY_ONLY: Readonly<Record<PromptStage, readonly string[]>> = {
  brainstorming: ['Three Paths', 'YAGNI', 'Red Flags', 'Spike', 'Bounded', 'Architectural'],
  design: ['设计文档集', '接口与数据契约先定死', '不写任务表'],
  decomposing: ['变更盘点', '批次与依赖', '边界校验'],
  implementing: ['Load plan, review critically', 'When to Stop and Ask for Help'],
  accepting: ['The Iron Law', 'Rationalization Prevention'],
  archived: ['Present Options', 'Common Rationalizations'],
}

function fragmentById(id: string): Fragment {
  const f = FRAGMENT_LIBRARY.find((x) => x.id === id)
  if (f === undefined) throw new Error('找不到分片：' + id)
  return f
}

function vendorText(skill: string): string {
  return readFileSync(join(VENDOR_DIR, skill, 'SKILL.md'), 'utf8')
}

describe('t7 链声明物化：每个节点的 light 与 heavy 都含与 STAGE_CHAIN 一致的交棒行', () => {
  for (const stage of PROMPT_STAGES) {
    it(stage + '：light/heavy 的「下一步」与 STAGE_CHAIN 逐字一致', () => {
      const label = STAGE_CHAIN[stage].label
      for (const difficulty of ['light', 'heavy'] as const) {
        const text = resolveStagePrompt({ stage, difficulty }).text
        expect(text, stage + '/' + difficulty + ' 缺链声明').toContain('下一步：')
        expect(text, stage + '/' + difficulty + ' 的链声明与 STAGE_CHAIN 不一致').toContain(label)
      }
    })
  }
})

describe('t7 ① 六节点 light/heavy 分化', () => {
  for (const stage of PROMPT_STAGES) {
    it(stage + '：light 与 heavy 解析出的文本不同', () => {
      const light = resolveStagePrompt({ stage, difficulty: 'light' }).text
      const heavy = resolveStagePrompt({ stage, difficulty: 'heavy' }).text
      expect(light).not.toBe(heavy)
      expect(light.length).toBeGreaterThan(0)
      expect(heavy.length).toBeGreaterThan(light.length)
    })

    it(stage + '：light charCount < heavy charCount', () => {
      const light = resolveStagePrompt({ stage, difficulty: 'light' })
      const heavy = resolveStagePrompt({ stage, difficulty: 'heavy' })
      expect(light.charCount, stage).toBeLessThan(heavy.charCount)
      // light 档设计上限 2500 字符（fragments.md §8）
      expect(light.charCount, stage + ' light 超 2500 字符上限').toBeLessThanOrEqual(2500)
    })
  }
})

describe('t7 ③ brainstorming/heavy 与 vendor 原文逐字一致（byte-level）', () => {
  it('分片 brainstorming/heavy 的文本 === vendor 原文（含空白换行，逐字节）', () => {
    const vendor = vendorText('brainstorming')
    const fragment = fragmentById('brainstorming/heavy')
    expect(fragment.text).toBe(vendor)
    expect(fragment.text.length).toBe(vendor.length)
    expect(Buffer.compare(Buffer.from(fragment.text, 'utf8'), Buffer.from(vendor, 'utf8'))).toBe(0)
    // 来源锚点（对照结论 §0：origin/main b36e082 该文件 250 行 / 15,456 字节）
    expect(Buffer.byteLength(vendor, 'utf8')).toBe(15456)
    expect(vendor.split('\n').length - 1).toBe(250)
  })

  it('brainstorming/heavy 解析文本以 vendor 原文为前缀（原文在前，overrides 在后）', () => {
    const vendor = vendorText('brainstorming')
    const resolved = resolveStagePrompt({ stage: 'brainstorming', difficulty: 'heavy' }).text
    expect(resolved.startsWith(vendor)).toBe(true)
    expect(resolved.length).toBeGreaterThan(vendor.length)
  })
})

describe('t7 ④ heavy 主 skill 镜像逐字一致（其余 4 节点）', () => {
  for (const [stage, skill] of Object.entries(VENDOR_MAIN_SKILLS)) {
    it(stage + '/heavy === vendor/' + skill + '/SKILL.md', () => {
      const vendor = vendorText(skill)
      expect(fragmentById(stage + '/heavy').text).toBe(vendor)
      expect(Buffer.compare(Buffer.from(fragmentById(stage + '/heavy').text, 'utf8'), Buffer.from(vendor, 'utf8'))).toBe(0)
    })
  }

  it('vendor 目录的 ATTRIBUTION.md 记录 repo / tag / commit / MIT / 抓取时点', () => {
    const p = join(VENDOR_DIR, 'ATTRIBUTION.md')
    expect(existsSync(p), 'ATTRIBUTION.md 缺失').toBe(true)
    const text = readFileSync(p, 'utf8')
    expect(text).toContain('https://github.com/obra/superpowers.git')
    expect(text).toContain('v6.3.0')
    expect(text).toContain('b36e0829c6d0140e93cfef2ca599b1b07d4a7797')
    expect(text).toContain('MIT')
    expect(text).toContain('抓取时点')
  })
})

describe('t7 ⑤ light 不含 heavy 独有要素关键词', () => {
  for (const stage of PROMPT_STAGES) {
    it(stage + '：light 不含 heavy 独有要素，且 heavy 确实含（关键词集有效）', () => {
      const light = resolveStagePrompt({ stage, difficulty: 'light' }).text
      const heavy = resolveStagePrompt({ stage, difficulty: 'heavy' }).text
      for (const kw of HEAVY_ONLY[stage]) {
        expect(heavy, stage + ' heavy 应含「' + kw + '」').toContain(kw)
        expect(light, stage + ' light 不应含 heavy 独有要素「' + kw + '」').not.toContain(kw)
      }
    })
  }
})

describe('t7 ⑥ 注入顺序固定三段：vendor 原文 → overrides → common/iron-rules', () => {
  for (const stage of Object.keys(VENDOR_MAIN_SKILLS) as PromptStage[]) {
    it(stage + '：heavy → overrides → iron-rules 的 fragmentIds 顺序正确', () => {
      const r = resolveStagePrompt({ stage, difficulty: 'heavy' })
      const iHeavy = r.fragmentIds.indexOf(stage + '/heavy')
      const iOver = r.fragmentIds.indexOf(stage + '/heavy/overrides')
      const iIron = r.fragmentIds.indexOf('common/iron-rules')
      expect(iHeavy, stage + ' 缺 heavy').toBeGreaterThanOrEqual(0)
      expect(iOver, stage + ' 缺 overrides').toBeGreaterThan(iHeavy)
      expect(iIron, stage + ' 缺 common/iron-rules（或未排最后）').toBeGreaterThan(iOver)
      // overrides 首行声明"覆盖上文"（原文在前、本仓接线在后）
      expect(fragmentById(stage + '/heavy/overrides').text).toContain('覆盖上文')
    })
  }

  it('light：节点内容在前、common/iron-rules 在后', () => {
    for (const stage of PROMPT_STAGES) {
      const r = resolveStagePrompt({ stage, difficulty: 'light' })
      expect(r.fragmentIds[r.fragmentIds.length - 1], stage).toBe('common/iron-rules')
    }
  })
})

describe('t7 ⑦ heavy 主 skill 原文不裁（预算极小时 floor 保留 + 结构化超限）', () => {
  it('极小预算下 brainstorming/heavy 的原文仍在 fragmentIds，且返回 overBudget', () => {
    const r = resolveStagePrompt({ stage: 'brainstorming', difficulty: 'heavy', budget: 5 })
    expect(r.fragmentIds).toContain('brainstorming/heavy')
    expect(r.fragmentIds).toContain('brainstorming/heavy/overrides')
    expect(r.fragmentIds).toContain('common/iron-rules')
    expect(r.overBudget?.reason).toBe('floor-exceeds-budget')
    expect(r.text.startsWith(vendorText('brainstorming'))).toBe(true)
  })

  it('全部 light/heavy 的节点内容与铁律都是 floor（永不裁）', () => {
    const nonFloor: string[] = []
    for (const f of FRAGMENT_LIBRARY) {
      const isNodeVoice = /^(light|heavy)$/.test(f.id.split('/').pop() ?? '')
        || f.id.endsWith('/overrides')
        || f.id === 'common/iron-rules'
      if (isNodeVoice && f.priority !== 'floor') nonFloor.push(f.id)
    }
    expect(nonFloor, '以下分片应为 floor（不可裁）：\n' + nonFloor.join('\n')).toEqual([])
  })
})

describe('t7 ⑧ decomposing 例外：superpowers 无对应 skill，heavy 自写', () => {
  it('decomposing 不在 vendor 映射里，且其 heavy 含自写完整档要素', () => {
    expect(Object.keys(VENDOR_MAIN_SKILLS)).not.toContain('decomposing')
    const heavy = fragmentById('decomposing/heavy')
    expect(heavy.text).toContain('变更盘点')
    expect(heavy.text).toContain('薄卡拒落')
    // 与任何 vendor 原文都不相同（不是 vendor 拷贝）
    for (const skill of Object.values(VENDOR_MAIN_SKILLS)) {
      expect(heavy.text).not.toBe(vendorText(skill))
    }
  })

  it('六节点各有 light.md 与 heavy.md 源文件（decomposing 的 heavy 为自写）', () => {
    for (const stage of PROMPT_STAGES) {
      expect(existsSync(join(FRAGMENTS_DIR, stage, 'light.md')), stage + '/light.md').toBe(true)
      expect(existsSync(join(FRAGMENTS_DIR, stage, 'heavy.md')), stage + '/heavy.md').toBe(true)
    }
  })
})
