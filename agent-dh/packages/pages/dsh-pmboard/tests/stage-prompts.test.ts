/**
 * stage-prompts.ts 阶段提示词常量单测（REQ-31e11f t5）。
 * 覆盖：五份常量非空且含关键纪律词、StagePromptKey 全覆盖、
 * capture.ts systemPrompt 组装注入（boundSectionText）、跳过阶段不注入。
 */
import { describe, it, expect } from 'vitest'
import { STAGE_PROMPTS, stagePromptFor } from '../src/domain/stage/StagePromptSpec.js'
import { boundSectionText } from '../src/application/internal/capture-section.js'
import { ALL_STAGE_PROMPT_KEYS, emptyLedger, type ReqboardLedger, type RequirementRecord } from '../src/shared/protocol.js'
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { join } from 'node:path'

const W = 'session-abc-123'

function req(over: Partial<RequirementRecord>): RequirementRecord {
  return {
    id: 'REQ-000001', title: 't', description: '', status: 'draft', blocked: false,
    version: 1, createdAt: 1, updatedAt: 1,
    ...over,
  } as RequirementRecord
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
  /** 注入文本里出现的 reqboard_* 名字（排除注释行，避免把说明文字当违规）。 */
  function referenced(text: string): string[] {
    return [...text.matchAll(/reqboard_[a-z_]+/g)].map(m => m[0])
  }

  it('阶段纪律文本（会被注入）只提到已注册的工具', () => {
    const registered = registeredNames()
    expect(registered.size, '扫描到的注册工具数应 ≥9（防扫描器失效而假绿）').toBeGreaterThanOrEqual(9)
    const bad: string[] = []
    for (const [key, prompt] of Object.entries(STAGE_PROMPTS)) {
      for (const name of referenced(prompt)) {
        if (!registered.has(name)) bad.push(key + ' → ' + name)
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

describe('STAGE_PROMPTS 常量表', () => {
  it('五份常量非空且含关键纪律词', () => {
    for (const key of ALL_STAGE_PROMPT_KEYS) {
      const prompt = STAGE_PROMPTS[key]
      expect(prompt, key).toBeTruthy()
      expect(prompt.length, key).toBeGreaterThan(50)
      expect(prompt, key).toContain('REQ-31e11f stage-prompts')
    }
    // brainstorming（t18 superpowers 方法论）：一次一个问题 / 方案对比 / 分节 / HARD-GATE
    expect(STAGE_PROMPTS.brainstorming).toContain('一次一个问题')
    expect(STAGE_PROMPTS.brainstorming).toContain('2-3 个方案对比')
    expect(STAGE_PROMPTS.brainstorming).toContain('分节呈现设计')
    expect(STAGE_PROMPTS.brainstorming).toContain('HARD-GATE')
    expect(STAGE_PROMPTS.brainstorming).toContain('探索项目上下文')
    expect(STAGE_PROMPTS.brainstorming).toContain('范围评估先行')
    // planning（t18 W7 代码层面设计 / 一套文档 / 不含 DAG）
    expect(STAGE_PROMPTS.planning).toContain('改表')
    expect(STAGE_PROMPTS.planning).toContain('框架选型')
    expect(STAGE_PROMPTS.planning).toContain('提交前自查')
    expect(STAGE_PROMPTS.planning).toContain('测试用例')
    expect(STAGE_PROMPTS.planning).toContain('不产出最终任务 DAG')
    // decomposing（t18 新增）：变更盘点 / 任务卡四要素 / 确认门
    expect(STAGE_PROMPTS.decomposing).toContain('变更盘点')
    expect(STAGE_PROMPTS.decomposing).toContain('任务卡四要素')
    expect(STAGE_PROMPTS.decomposing).toContain('reqboard_ask_confirm')
    // implementing（t18 文档驱动 + 验收文档）
    expect(STAGE_PROMPTS.implementing).toContain('实施文档')
    expect(STAGE_PROMPTS.implementing).toContain('reqboard_task_report')
    expect(STAGE_PROMPTS.implementing).toContain('新窗口或 subagent')
    expect(STAGE_PROMPTS.implementing).toContain('验收文档')
    // accepting（t18 逐项验收单 + 断点续验）
    expect(STAGE_PROMPTS.accepting).toContain('证据先行')
    expect(STAGE_PROMPTS.accepting).toContain('功能正常')
    expect(STAGE_PROMPTS.accepting).toContain('逐项')
    expect(STAGE_PROMPTS.accepting).toContain('断点续验')
    // archived：按分类核对 / ARCHIVE_DOC_RULES
    expect(STAGE_PROMPTS.archived).toContain('按分类核对文档清单')
    expect(STAGE_PROMPTS.archived).toContain('ARCHIVE_DOC_RULES')
  })

  // ── REQ-2e9473 t08：落章型确认一律指向 reqboard_ask_confirm（措辞锁定，防回退）──
  it('落章型确认纪律均指向 reqboard_ask_confirm（普通征询仍可用 ask_user_question）', () => {
    for (const key of ['brainstorming', 'planning', 'implementing', 'accepting'] as const) {
      expect(STAGE_PROMPTS[key], key).toContain('reqboard_ask_confirm')
    }
    // archived 的"取舍拍板"是普通征询，仍用 ask_user_question
    expect(STAGE_PROMPTS.archived).toContain('ask_user_question')
  })

  it('brainstorming 含产物登记 + 弹框确认指引（ask_confirm 原子化）', () => {
    // 13→9 收敛后入口改名为 reqboard_submit(kind=…)——此处曾**钉死旧工具名**，导致改名后提示词与工具面
    // 长期不一致（agent 会照纪律去调不存在的工具）。教训：断言"调用了哪个入口"时，要跟注册表对齐。
    expect(STAGE_PROMPTS.brainstorming).toContain('reqboard_submit(kind=requirement)')
    expect(STAGE_PROMPTS.brainstorming).toContain('reqboard_ask_confirm')
    expect(STAGE_PROMPTS.brainstorming).toContain('kind=requirement')
  })

  it('planning 含计划批准弹框指引（ask_confirm 与看板双通道）', () => {
    expect(STAGE_PROMPTS.planning).toContain('reqboard_ask_confirm')
    expect(STAGE_PROMPTS.planning).toContain('target=plan')
    expect(STAGE_PROMPTS.planning).toContain('批准计划')
  })

  it('accepting 含验收确认弹框指引', () => {
    expect(STAGE_PROMPTS.accepting).toContain('reqboard_ask_confirm')
    expect(STAGE_PROMPTS.accepting).toContain('kind=verification')
  })

  it('archived 说明归档已自动完成、本阶段是材料补齐（REQ-9f4a44）', () => {
    expect(STAGE_PROMPTS.archived).toContain('归档已自动完成')
    expect(STAGE_PROMPTS.archived).toContain('reqboard_submit(kind=archive)')
  })

  it('StagePromptKey 全覆盖（ALL_STAGE_PROMPT_KEYS 每个键都有非空常量）', () => {
    for (const key of ALL_STAGE_PROMPT_KEYS) {
      expect(STAGE_PROMPTS[key], key).toBeDefined()
      expect(typeof STAGE_PROMPTS[key], key).toBe('string')
      expect(STAGE_PROMPTS[key].length, key).toBeGreaterThan(0)
    }
    // 反向：STAGE_PROMPTS 的键集合与 ALL_STAGE_PROMPT_KEYS 一致
    const keys = Object.keys(STAGE_PROMPTS).sort()
    expect(keys).toEqual([...ALL_STAGE_PROMPT_KEYS].sort())
  })

  it('stagePromptFor 取值与直接索引一致', () => {
    for (const key of ALL_STAGE_PROMPT_KEYS) {
      expect(stagePromptFor(key)).toBe(STAGE_PROMPTS[key])
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
    expect(text).toContain(STAGE_PROMPTS.brainstorming)
    expect(text).toContain('一次一个问题')
  })

  it('bound 窗口处于 planning → 注入 planning 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'planning', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(STAGE_PROMPTS.planning)
    expect(text).toContain('提交前自查')
  })

  it('bound 窗口处于 implementing → 注入 implementing 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'implementing', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(STAGE_PROMPTS.implementing)
    expect(text).toContain('reqboard_task_report')
  })

  it('bound 窗口处于 accepting → 注入 accepting 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'accepting', category: 'feature' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(STAGE_PROMPTS.accepting)
    expect(text).toContain('证据先行')
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
    expect(text).not.toContain(STAGE_PROMPTS.brainstorming)
    expect(text).not.toContain('一次一个问题')
  })

  it('spike 分类跳过 planning → 不注入 planning 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'planning', category: 'spike' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).not.toContain(STAGE_PROMPTS.planning)
    expect(text).not.toContain('提交前自查')
  })

  it('spike 分类处于 implementing（未跳过）→ 注入 implementing 提示词', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: W, status: 'implementing', category: 'spike' })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain(STAGE_PROMPTS.implementing)
  })

  it('feature 分类 open 阶段均注入（archived 除外，经 capture-hook 事件注入）', () => {
    for (const status of ['brainstorming', 'planning', 'implementing', 'accepting'] as const) {
      const l: ReqboardLedger = {
        ...emptyLedger(),
        requirements: [req({ sourceSessionId: W, status, category: 'feature' })],
      }
      const text = boundSectionText(l, { agent: { id: W } })
      expect(text, status).toContain(STAGE_PROMPTS[status])
    }
  })
})
