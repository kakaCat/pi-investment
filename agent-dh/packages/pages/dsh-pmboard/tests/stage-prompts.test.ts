/**
 * 阶段提示词单测（REQ-31e11f t5；REQ-422af1 t7 迁移）。
 *
 * t7 迁移说明：P0 期本文件 import 兼容视图 `STAGE_PROMPTS` / `stagePromptFor`（P0 判决 a：
 * 冻结测试不动），P1 起断言全部迁到唯一取词入口 `resolveStagePrompt`，兼容壳已删除。
 * 覆盖：注入文本工具名一致门禁、六节点 light/heavy 要素、文案措辞锁定、
 * capture.ts systemPrompt 组装注入（boundSectionText）、跳过阶段不注入。
 */
import { describe, it, expect } from 'vitest'
import {
  resolveStagePrompt,
  PROMPT_STAGES,
  DIFFICULTIES,
  STAGE_CHAIN,
  type Difficulty,
  type PromptStage,
} from '../src/domain/prompt/index.js'
import { boundSectionText } from '../src/application/internal/capture-section.js'
import { ALL_STAGE_PROMPT_KEYS, emptyLedger, type ReqboardLedger, type RequirementRecord } from '../src/shared/protocol.js'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const W = 'session-abc-123'

/** 生产注入点用缺省难度（light）；此处同口径取文本用于对照。 */
function lightText(stage: PromptStage, difficulty: Difficulty = 'light'): string {
  return resolveStagePrompt({ stage, difficulty }).text
}

function req(over: Partial<RequirementRecord>): RequirementRecord {
  return {
    id: 'REQ-000001', title: 't', description: '', status: 'draft', blocked: false,
    version: 1, createdAt: 1, updatedAt: 1,
    ...over,
  } as RequirementRecord
}

/** 每节点 heavy 必须命中的"heavy 独有要素"关键词（逐字来自 vendor 原文 / 自写完整档）。 */
const HEAVY_ELEMENTS: Readonly<Record<PromptStage, readonly string[]>> = {
  brainstorming: ['Three Paths', 'YAGNI', 'Red Flags', 'Spike', 'Bounded', 'Architectural'],
  design: ['设计文档集', '接口与数据契约先定死', '不写任务表'], // 2026-09-21：design 改自写档（只写设计文档）
  decomposing: ['变更盘点', '批次与依赖', '边界校验'],
  implementing: ['Load plan, review critically', 'When to Stop and Ask for Help'],
  accepting: ['The Iron Law', 'Rationalization Prevention'],
  archived: ['Present Options', 'Common Rationalizations'],
}

/** 每节点 heavy 必须含的本仓工具化措辞（overrides / 自写档）。 */
const REQ_SPECIFIC: Readonly<Record<PromptStage, readonly string[]>> = {
  brainstorming: ['reqboard_ask_confirm', 'requirement.md', 'artifact_not_confirmed'],
  // REQ-2d1c74 FR-4：设计阶段旧指令（submit 计划/批准计划）已清除——设计只写设计文档，
  // 确认设计文档（kind=design 成组落章）后进拆分；计划类指令挪到 decomposing 档（见下 170 行区）。
  design: ['reqboard_ask_confirm(target=artifact, kind=design)', 'reqboard_ask_confirm'],
  decomposing: ['reqboard_decompose', 'reqboard_ask_confirm'],
  implementing: ['reqboard_task_report', 'reqboard_task_move'],
  accepting: ['reqboard_submit(kind=verification)', 'reqboard_accept_sheet'],
  archived: ['ARCHIVE_DOC_RULES', 'reqboard_submit(kind=archive)'],
}

/**
 * 注入文本 × 工具注册表一致性门禁（REQ-47939a 补）。
 *
 * 事故：13→9 收敛把 4 个 submit 合并为 `reqboard_submit(kind=…)`、`confirm_artifact` 并入
 * `reqboard_ask_confirm`，但**真正会被注入给 agent 的阶段纪律文本**仍写着旧名——文档同步了、
 * 注入文本漏了，于是 agent 照纪律执行会去调不存在的工具。且旧断言恰好把旧名钉死，改名时毫无提示。
 *
 * 本门禁把"文本里提到的工具"与"实际注册的工具"对起来：任何一处不一致即红。
 */
describe('注入文本里的工具名必须都在注册集合内', () => {
  const SRC = fileURLToPath(new URL('../src', import.meta.url))
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
  /** 注入文本里出现的 reqboard_* 名字。 */
  function referenced(text: string): string[] {
    return [...text.matchAll(/reqboard_[a-z_]+/g)].map(m => m[0])
  }

  it('六节点 light/heavy 的注入文本只提到已注册的工具', () => {
    const registered = registeredNames()
    expect(registered.size, '扫描到的注册工具数应 ≥9（防扫描器失效而假绿）').toBeGreaterThanOrEqual(9)
    const bad: string[] = []
    for (const stage of PROMPT_STAGES) {
      for (const difficulty of DIFFICULTIES) {
        const prompt = resolveStagePrompt({ stage, difficulty }).text
        for (const name of referenced(prompt)) {
          if (!registered.has(name)) bad.push(stage + '/' + difficulty + ' → ' + name)
        }
      }
    }
    expect(bad, '提示词提到的工具不存在（改名后文本没跟上）：\n' + bad.join('\n')).toEqual([])
  })

  it('捕获引导段源码里的工具名同样只指向已注册工具', () => {
    const registered = registeredNames()
    const text = readFileSync(join(SRC, 'application/internal/capture-section.ts'), 'utf8')
    const bad: string[] = []
    for (const line of text.split('\n')) {
      const t = line.trim()
      if (t.startsWith('*') || t.startsWith('//')) continue
      for (const name of referenced(line)) if (!registered.has(name)) bad.push(name + '  ← ' + t.slice(0, 60))
    }
    expect(bad, '捕获引导段引用了不存在的工具：\n' + bad.join('\n')).toEqual([])
  })
})

describe('六节点 light/heavy 要素（REQ-422af1 t7）', () => {
  for (const stage of PROMPT_STAGES) {
    it(stage + ' light 非空且含链声明「下一步：」', () => {
      const light = resolveStagePrompt({ stage, difficulty: 'light' }).text
      expect(light.length).toBeGreaterThan(50)
      expect(light).toContain('下一步：')
      expect(light, 'light 的「下一步」必须与 STAGE_CHAIN 一致').toContain(STAGE_CHAIN[stage].label)
    })

    it(stage + ' heavy 命中 heavy 独有要素关键词', () => {
      const heavy = resolveStagePrompt({ stage, difficulty: 'heavy' }).text
      for (const kw of HEAVY_ELEMENTS[stage]) {
        expect(heavy, stage + ' heavy 缺要素「' + kw + '」').toContain(kw)
      }
    })

    it(stage + ' heavy 含本仓工具化措辞', () => {
      const heavy = resolveStagePrompt({ stage, difficulty: 'heavy' }).text
      for (const kw of REQ_SPECIFIC[stage]) {
        expect(heavy, stage + ' heavy 缺本仓措辞「' + kw + '」').toContain(kw)
      }
    })
  }

  // ── REQ-2e9473 t08 / REQ-422af1 t7：落章型确认一律指向 reqboard_ask_confirm（措辞锁定，防回退）──
  it('落章型确认纪律均指向 reqboard_ask_confirm（普通征询仍可用 ask_user_question）', () => {
    for (const stage of ['brainstorming', 'design', 'implementing', 'accepting'] as const) {
      for (const difficulty of DIFFICULTIES) {
        expect(resolveStagePrompt({ stage, difficulty }).text, stage + '/' + difficulty)
          .toContain('reqboard_ask_confirm')
      }
    }
    // archived 的"取舍拍板"是普通征询，仍用 ask_user_question（light 档给出）
    expect(resolveStagePrompt({ stage: 'archived', difficulty: 'light' }).text).toContain('ask_user_question')
  })

  it('brainstorming 含产物登记 + 弹框确认指引（ask_confirm 原子化）', () => {
    // 13→9 收敛后入口改名为 reqboard_submit(kind=…)——此处曾**钉死旧工具名**，导致改名后提示词与工具面
    // 长期不一致（agent 会照纪律去调不存在的工具）。教训：断言"调用了哪个入口"时，要跟注册表对齐。
    for (const difficulty of DIFFICULTIES) {
      const text = resolveStagePrompt({ stage: 'brainstorming', difficulty }).text
      expect(text).toContain('reqboard_submit(kind=requirement)')
      expect(text).toContain('reqboard_ask_confirm')
      expect(text).toContain('kind=requirement')
    }
  })

  it('design 含设计文档确认弹框指引；拆分计划批准指引在 decomposing（2026-09-21 裁定）', () => {
    const text = resolveStagePrompt({ stage: 'design', difficulty: 'heavy' }).text
    expect(text).toContain('reqboard_ask_confirm')
    expect(text).toContain('kind=design')
    expect(resolveStagePrompt({ stage: 'design', difficulty: 'light' }).text).toContain('kind=design')
    // 批准拆分计划（target=plan）的指引已随计划挪到拆分阶段
    expect(resolveStagePrompt({ stage: 'decomposing', difficulty: 'light' }).text).toContain('target=plan')
    expect(resolveStagePrompt({ stage: 'decomposing', difficulty: 'heavy' }).text).toContain('target=plan')
  })

  it('accepting 含验收确认弹框指引', () => {
    const text = resolveStagePrompt({ stage: 'accepting', difficulty: 'heavy' }).text
    expect(text).toContain('reqboard_ask_confirm')
    expect(text).toContain('kind=verification')
  })

  it('archived 说明归档已自动完成、本阶段是材料补齐（REQ-9f4a44）', () => {
    const text = resolveStagePrompt({ stage: 'archived', difficulty: 'heavy' }).text
    expect(text).toContain('归档')
    expect(text).toContain('reqboard_submit(kind=archive)')
  })

  it('StagePromptKey 全覆盖（ALL_STAGE_PROMPT_KEYS 每个键都有非空注入）', () => {
    expect([...ALL_STAGE_PROMPT_KEYS].sort()).toEqual([...PROMPT_STAGES].sort())
    for (const key of ALL_STAGE_PROMPT_KEYS) {
      expect(resolveStagePrompt({ stage: key }).text.length, key).toBeGreaterThan(0)
    }
  })
})

describe('capture.ts systemPrompt 组装注入', () => {
  it('bound 窗口处于 brainstorming → 注入 brainstorming 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'brainstorming', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain('REQ-000001')
    expect(text).toContain('brainstorming')
    expect(text).toContain(lightText('brainstorming'))
  })

  it('bound 窗口处于 design → 注入 design 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'design', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(lightText('design'))
  })

  it('bound 窗口处于 implementing → 注入 implementing 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'implementing', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(lightText('implementing'))
    expect(text).toContain('reqboard_task_report')
  })

  it('bound 窗口处于 accepting → 注入 accepting 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'accepting', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(lightText('accepting'))
    expect(text).toContain('验收')
  })

  it('archived 需求不算 open → boundSectionText 返回空（归档提示词经 capture-hook 事件注入）', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'archived', category: 'feature' })],
    }
    // archived 不是 open 状态 → boundSectionText 不注入（零噪音）
    expect(boundSectionText(l, { agent: { id: W } })).toBe('')
  })

  it('未绑定窗口 → 空段（零噪音）', () => {
    expect(boundSectionText(emptyLedger(), { agent: { id: W } })).toBe('')
  })

  it('已结束需求（done）不算绑定 → 空段', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'done' })],
    }
    expect(boundSectionText(l, { agent: { id: W } })).toBe('')
  })
})

describe('分类档案跳过阶段不注入', () => {
  it('bug 分类跳过 brainstorming → 不注入 brainstorming 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'brainstorming', category: 'bug' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    // bug 分类的 stages 不含 brainstorming → 不注入提示词
    expect(text).not.toContain(lightText('brainstorming'))
  })

  it('spike 分类跳过 design → 不注入 design 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'design', category: 'spike' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).not.toContain(lightText('design'))
  })

  it('spike 分类处于 implementing（未跳过）→ 注入 implementing 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'implementing', category: 'spike' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    // REQ-422af1 t8：注入文本按 category 分化（spike 带 spike 类型档），
    // 故此处对照"同 category 的解析结果"——lightText 的缺省 category 是 feature。
    expect(text).toContain(resolveStagePrompt({ stage: 'implementing', category: 'spike' }).text)
  })

  it('feature 分类 open 阶段均注入（archived 除外，经 capture-hook 事件注入）', () => {
    for (const status of ['brainstorming', 'design', 'implementing', 'accepting'] as const) {
      const l: ReqboardLedger = {
        ...emptyLedger(),
        requirements: [req({ sourceSessionId: W, status, category: 'feature' })],
      }
      const text = boundSectionText(l, { agent: { id: W } })
      expect(text, status).toContain(lightText(status))
    }
  })
})
