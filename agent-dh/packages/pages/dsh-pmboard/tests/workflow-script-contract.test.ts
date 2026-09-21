/**
 * workflow 脚本契约门禁 + 端口适配器单测（REQ-4842fe t4）——对应 design/test-cases.md §3.1/§8.4/§9。
 *
 * 口径纪律：**禁止字符串包含式断言代替契约断言**（旧 tests/reqboard-task-execute.test.ts
 * 只断言"含有 ctx.subagent"就该失败——那是反面教材）。本文件断言的是 hook 白名单全集、
 * 禁止 token 的实际拒绝行为与适配器的三态翻译。
 * 真实引擎冒烟见 scripts/workflow-engine-smoke.ts（证据留 t12）。
 */
import { describe, it, expect } from 'vitest'
import {
  WORKFLOW_HOOKS,
  assertScriptContract,
  generateSubtaskScript,
  usedHooks,
} from '../src/application/internal/workflow-script.js'
import { WorkflowEngineRunner, type WorkflowEngineLike, type WorkflowRunLike } from '../src/adapters/WorkflowEngineRunner.js'

const codeOf = (fn: () => void): string | undefined => {
  try { fn(); return undefined } catch (err) { return (err as { code?: string }).code }
}

describe('脚本契约门禁（3.1 / 9.2）', () => {
  it('hook 白名单全集 = agent/parallel/pipeline/phase/log（五个别名都在，别的都不在）', () => {
    expect([...WORKFLOW_HOOKS]).toEqual(['agent', 'parallel', 'pipeline', 'phase', 'log'])
  })

  it('生成器产出只用白名单 hook，且必含 agent/phase/log', () => {
    const script = generateSubtaskScript({ stageKind: 'dev', stageLabel: '研发', prompt: '改 x.ts 并跑测试' })
    const hooks = usedHooks(script)
    expect(hooks.filter(h => !(WORKFLOW_HOOKS as readonly string[]).includes(h))).toEqual([])
    expect(hooks).toContain('agent')
    expect(hooks).toContain('phase')
    expect(hooks).toContain('log')
    expect(() => assertScriptContract(script)).not.toThrow()
  })

  it('含 ctx.subagent 的脚本在生成阶段即被门禁拒绝（历史事故 A）', () => {
    const bad = 'const out = await ctx.subagent({ prompt: "干活" }); return { ok: out !== null };'
    expect(codeOf(() => assertScriptContract(bad))).toBe('workflow_script_contract')
    try { assertScriptContract(bad) } catch (err) { expect((err as Error).message).toContain('ctx') }
  })

  it('含 ctx.tools.workflow 的脚本被拒（历史事故 B：依赖被禁工具）', () => {
    expect(codeOf(() => assertScriptContract('const r = await ctx.tools.workflow({});'))).toBe('workflow_script_contract')
  })

  it('工具名调用（reqboard_task_move(...)）被拒', () => {
    expect(codeOf(() => assertScriptContract('await reqboard_task_move({ task_id: "t-1" });'))).toBe('workflow_script_contract')
  })

  it('空脚本被拒（宁可不跑，也不空跑）', () => {
    expect(codeOf(() => assertScriptContract(''))).toBe('workflow_script_contract')
    expect(codeOf(() => assertScriptContract('   '))).toBe('workflow_script_contract')
  })

  it('误伤防护：prompt 文本里的示例不算违规（只扫可执行代码）', () => {
    // 父卡实施方案里若引用 ctx.subagent( 作为反例文本，包在字符串里就不该被判违规。
    const script = generateSubtaskScript({ stageKind: 'review', stageLabel: '复核', prompt: '反例：不要写 ctx.subagent(...) 调用；也不要调 reqboard_task_move(x)。' })
    expect(() => assertScriptContract(script)).not.toThrow()
  })
})

describe('WorkflowEngineRunner 三态翻译（3.3 / 9.3）', () => {
  const runOf = (result: Promise<{ value?: unknown; stopReason?: string; error?: string }>, onDispose?: () => void): WorkflowRunLike => ({
    result,
    dispose: async () => { onDispose?.() },
  })
  const engineOf = (run: WorkflowRunLike): WorkflowEngineLike => ({ start: () => run })

  it('引擎缺失 → ok:false / engine_unavailable（不静默成功）', async () => {
    const outcome = await new WorkflowEngineRunner(() => undefined).start({ script: 'return {};', meta: { name: 'x', description: 'x' } })
    expect(outcome).toEqual({ ok: false, reason: 'engine_unavailable' })
  })

  it('start 同步抛错 → ok:false / start_failed', async () => {
    const engine: WorkflowEngineLike = { start: () => { throw new Error('SCRIPT_PARSE') } }
    const outcome = await new WorkflowEngineRunner(() => engine).start({ script: 'x', meta: { name: 'x', description: 'x' } })
    expect(outcome.ok).toBe(false)
    expect(outcome.reason).toContain('SCRIPT_PARSE')
  })

  it('stopReason=error → ok:false 且 dispose 仍被调用（不泄漏 worker）', async () => {
    let disposed = 0
    const engine = engineOf(runOf(Promise.resolve({ stopReason: 'error', error: 'boom' }), () => { disposed += 1 }))
    const outcome = await new WorkflowEngineRunner(() => engine).start({ script: 'return {};', meta: { name: 'x', description: 'x' } })
    expect(outcome.ok).toBe(false)
    expect(outcome.reason).toContain('error')
    expect(disposed).toBe(1)
  })

  it('stopReason=completed → ok:true 且透传 lossless JSON 产出', async () => {
    let disposed = 0
    const engine = engineOf(runOf(Promise.resolve({ stopReason: 'completed', value: { ok: true, n: 1 } }), () => { disposed += 1 }))
    const outcome = await new WorkflowEngineRunner(() => engine).start({ script: 'return {};', meta: { name: 'x', description: 'x' } })
    expect(outcome).toEqual({ ok: true, value: { ok: true, n: 1 } })
    expect(disposed).toBe(1)
  })
})
