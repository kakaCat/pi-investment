/**
 * toolviews 数据契约单测（REQ-c48f99 t1 / FR-1、FR-4、FR-5）。
 * 锁定：parseArgs 不 throw 契约、中文映射覆盖、renderSmart 首行语义、fallbackModel 永不 null。
 */
import { describe, it, expect } from 'vitest'
import {
  parseArgs, resultText, resultJson, firstLine,
  TASK_MOVE_TO, AUDIT_ACTION, WATCH_ACTION, TRADE_ACTION,
  cnLabel, fallbackModel, isSettled,
  type ToolBlock, type SettledBlock,
} from '../src/client/toolviews/shared.ts'
import { artifactKindLabel } from '../src/shared/artifact-labels.js'
import { renderSmart, renderJson } from '../src/tools/shared.js'

describe('parseArgs（FR-4 不 throw 契约）', () => {
  it('完整 JSON 对象 → 解析成功', () => {
    expect(parseArgs('{"task_id":"t-abc","to":"done"}')).toEqual({ task_id: 't-abc', to: 'done' })
  })
  it('半截 JSON（流式）→ undefined', () => {
    expect(parseArgs('{"task_id":"t-abc","to":"do')).toBeUndefined()
  })
  it('非对象 JSON（数组/字符串/数字）→ undefined', () => {
    expect(parseArgs('[1,2,3]')).toBeUndefined()
    expect(parseArgs('"hello"')).toBeUndefined()
    expect(parseArgs('42')).toBeUndefined()
  })
  it('空串/空白 → undefined', () => {
    expect(parseArgs('')).toBeUndefined()
    expect(parseArgs('   ')).toBeUndefined()
  })
})

describe('resultText / resultJson', () => {
  const settled: SettledBlock = {
    kind: 'tool-result',
    callId: 'c1',
    call: { name: 'reqboard_status', argsRaw: '{}' },
    content: [{ type: 'text', text: '{"bound":false,"open_count":0}' }],
    isError: false,
  }
  it('拼接 text 段', () => {
    expect(resultText(settled)).toBe('{"bound":false,"open_count":0}')
  })
  it('resultJson 解析对象；非 JSON → undefined', () => {
    expect(resultJson(settled)).toEqual({ bound: false, open_count: 0 })
    const bad: SettledBlock = { ...settled, content: [{ type: 'text', text: 'not json at all' }] }
    expect(resultJson(bad)).toBeUndefined()
  })
  it('运行态 block 无结果', () => {
    const running: ToolBlock = { callId: 'c2', argsRaw: '{}' }
    expect(isSettled(running)).toBe(false)
    expect(resultText(running)).toBe('')
  })
})

describe('中文映射表（FR-2 覆盖）', () => {
  it('task_move 7 个 to 值全覆盖', () => {
    for (const to of ['todo', 'in_progress', 'integrating', 'testing', 'in_review', 'done', 'canceled']) {
      expect(TASK_MOVE_TO[to], '缺映射: ' + to).toBeTruthy()
    }
  })
  it('submit 4 类（收敛至唯一事实源，design/decomposition/task_detail 自动补齐）/ audit 2 类 / watch 4 类 / trade 2 类', () => {
    // REQ-260922182638-0777：submit 种类中文名唯一事实源 = shared/artifact-labels.ts
    for (const [kind, label] of [
      ['requirement', '需求文档'], ['plan', '拆分计划（旧版）'], ['verification', '验收材料'], ['archive', '归档材料'],
      ['design', '设计文档'], ['decomposition', '拆分计划'], ['task_detail', '任务卡'],
    ] as const) {
      expect(artifactKindLabel(kind), '缺映射: ' + kind).toBe(label)
    }
    expect(Object.keys(AUDIT_ACTION)).toHaveLength(2)
    expect(Object.keys(WATCH_ACTION)).toHaveLength(4)
    expect(Object.keys(TRADE_ACTION)).toHaveLength(2)
  })
  it('未知枚举兜底原文，空值返回 undefined', () => {
    expect(cnLabel(TASK_MOVE_TO, 'paused')).toBe('paused')
    expect(cnLabel(TASK_MOVE_TO, '')).toBeUndefined()
    expect(cnLabel(TASK_MOVE_TO, undefined)).toBeUndefined()
  })
})

describe('renderSmart（FR-5 首行语义）', () => {
  const value = { success: true, task_id: 't-b0b327', from: 'todo', to: 'in_progress' }
  it('首行 = 摘要单行，非 { 开头，≤120 字符', () => {
    const out = renderSmart(() => '✅ t-b0b327 开工（todo → in_progress）')(undefined, value)
    const text = out[0].text
    const head = firstLine(text)
    expect(head).toBe('✅ t-b0b327 开工（todo → in_progress）')
    expect(head.startsWith('{')).toBe(false)
    expect(head.length).toBeLessThanOrEqual(120)
  })
  it('多行摘要被截为单行；超长摘要截 120', () => {
    const out = renderSmart(() => '第一行\n第二行')(undefined, value)
    expect(firstLine(out[0].text)).toBe('第一行')
    const long = renderSmart(() => 'x'.repeat(200))(undefined, value)
    expect(firstLine(long[0].text).length).toBe(120)
  })
  it('JSON 明细仍在摘要之后（renderJson 兼容形态）', () => {
    const out = renderSmart(() => '摘要')(undefined, value)
    expect(out[0].text).toContain('\n\n')
    expect(out[0].text).toContain('"task_id": "t-b0b327"')
  })
  it('renderJson 保留未改（兼容）', () => {
    const out = renderJson(undefined, value)
    expect(out[0].text.startsWith('{')).toBe(true)
  })
})

describe('fallbackModel（FR-4 永不 null / 永不 throw）', () => {
  it('正常：取第一个字符串参数首行', () => {
    const block: ToolBlock = { callId: 'c1', argsRaw: '{"task_id":"t-abc","to":"done"}' }
    const m = fallbackModel('reqboard_task_move', block)
    expect(m.toolName).toBe('reqboard_task_move')
    expect(m.argLine).toBe('t-abc')
    expect(m.isError).toBe(false)
  })
  it('畸形 argsRaw：回落 callId，不 throw', () => {
    const block: ToolBlock = { callId: 'c2', argsRaw: '{"broken":' }
    const m = fallbackModel('reqboard_status', block)
    expect(m.argLine).toBe('c2')
  })
  it('错误态：isError=true，输出首行为错误摘要', () => {
    const block: SettledBlock = {
      kind: 'tool-result', callId: 'c3', call: { argsRaw: '{}' },
      content: [{ type: 'text', text: '任务不存在 t-xxx' }],
      isError: true, error: { name: 'Error', code: 'not_found' },
    }
    const m = fallbackModel('reqboard_task_move', block)
    expect(m.isError).toBe(true)
    expect(m.outputLine).toBe('任务不存在 t-xxx')
  })
})
