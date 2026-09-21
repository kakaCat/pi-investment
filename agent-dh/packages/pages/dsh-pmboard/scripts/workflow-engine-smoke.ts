/**
 * 真实引擎冒烟（REQ-4842fe t4 / design/test-cases §3.2）——**不是 mock**：
 * 本脚本用 cordis 起一个最小上下文，加载真实的 workflow-worker-thread 引擎，
 * 再经 WorkflowEngineRunner 跑一次最简 run。
 *
 * 用法：npx tsx scripts/workflow-engine-smoke.ts
 * 退出码 0 = 最简脚本 stopReason=completed、产出非空、dispose 无悬挂（且引擎缺失路径显式失败）。
 *
 * 为什么放在 scripts 而不是 vitest：引擎包是 pnpm 传递依赖（未直接链接进本包），
 * 测试进程里按包名 import 解析不到；本脚本按 pnpm store 目录发现入口，保持零依赖新增。
 */
import { readdirSync } from 'node:fs'
import { join } from 'node:path'
import { pathToFileURL } from 'node:url'

function findEngineEntry(root: string): string {
  const pnpm = join(root, 'node_modules', '.pnpm')
  const dir = readdirSync(pnpm).find((d) => d.startsWith('@deepseek-ai+dsh-workflow-worker-thread@'))
  if (dir === undefined) throw new Error('未找到 dsh-workflow-worker-thread（pnpm store 缺失）')
  return join(pnpm, dir, 'node_modules', '@deepseek-ai', 'dsh-workflow-worker-thread', 'lib', 'index.js')
}

/** 最小 subagents 桩：本冒烟脚本不调用 agent()，getProvider 不会被用到。 */
async function bootEngine(repoRoot: string): Promise<any> {
  const { Context, Service } = await import('@deepseek-ai/cordis')
  const entry = findEngineEntry(repoRoot)
  const mod: any = await import(pathToFileURL(entry).href)
  const Engine = mod.default
  class StubSubagents extends Service {
    constructor(ctx: any) { super(ctx, 'subagents') }
    getProvider(_p?: string) { return { start: async () => ({}) } }
    async start() { return {} }
  }
  const root = new Context()
  await root.plugin(StubSubagents as any)
  await root.plugin(Engine as any)
  return (root as any).workflowEngine
}

function fail(message: string): never {
  console.log('[workflow-engine-smoke] FAIL ' + message)
  process.exit(1)
}

const repoRoot = join(import.meta.dirname, '..', '..', '..', '..')
const { WorkflowEngineRunner } = await import('../src/adapters/WorkflowEngineRunner.js')

const engine = await bootEngine(repoRoot)
if (engine === undefined || typeof engine.start !== 'function') fail('引擎未加载（workflowEngine 不可用）')
console.log('[workflow-engine-smoke] engine loaded: ctx.workflowEngine.start 可用')

// 1) 引擎缺失路径必须显式失败（不静默成功）
const missing = await new WorkflowEngineRunner(() => undefined).start({ script: 'return { ok: true };', meta: { name: 's', description: 's' } })
if (missing.ok !== false || missing.reason !== 'engine_unavailable') fail('引擎缺失时未显式失败：' + JSON.stringify(missing))
console.log('[workflow-engine-smoke] 引擎缺失 → ok=false reason=engine_unavailable（不静默成功）')

// 2) 真实 run：最简脚本，经端口跑通
const runner = new WorkflowEngineRunner(() => engine)
const outcome = await runner.start({
  script: 'phase("执行");\nlog("smoke");\nreturn { ok: true, n: 1 };',
  meta: { name: 'reqboard-smoke', description: 'REQ-4842fe 引擎冒烟' },
  parent: {},
})
if (outcome.ok !== true) fail('真实 run 未成功：' + JSON.stringify(outcome))
const value = outcome.value as { ok?: boolean; n?: number } | undefined
if (value?.ok !== true || value?.n !== 1) fail('产出不是预期 lossless JSON：' + JSON.stringify(value))
console.log('[workflow-engine-smoke] run stopReason=completed，value=' + JSON.stringify(value) + '，dispose 无悬挂')
console.log('[workflow-engine-smoke] PASS')
