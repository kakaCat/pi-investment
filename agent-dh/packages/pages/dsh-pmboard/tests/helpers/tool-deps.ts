/**
 * 旧工具入口兼容壳（REQ-47939a t8）：13 个旧工厂名 → 收敛后的 9 个新工具壳 + 旧依赖
 * （ReqboardToolDeps）到 UseCaseDeps 的适配。**保留本文件只为让既有测试的 import 路径在
 * 收口（t9 删 host/ 与旧测试改写）之前仍可用**；运行时（src/index.ts）已直接装配新工具。
 *
 * 零行为变更：适配器（SessionProbeAdapter/FileDocRepository/RandomIdFactory）搬运了搬迁前
 * 的同款实现（认证文案、fs 口径、ID 格式一致）；4 个 submit 旧工厂把 kind 注入新工具。
 *
 * REQ-47939a t9：原 src/host/agent-tools.ts 是**只给测试用**的旧工具入口兼容壳（13 个旧工厂名
 * + 旧依赖 ReqboardToolDeps → UseCaseDeps 的适配）；host/ 收口时它没有再进生产层，落到
 * tests/helpers/（测试夹具，不属于 src 分层）。工厂实现全部为薄转发，行为与搬迁前逐字一致。
 *
 * @module dsh-pmboard/tests/helpers/tool-deps
 */
import { mkdtempSync, realpathSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import type { ToolTraceEntry, RecentUserMsg } from '../../src/adapters/SessionProbeAdapter.js'
import { SessionProbeAdapter } from '../../src/adapters/SessionProbeAdapter.js'
import { FileDocRepository } from '../../src/adapters/FileDocRepository.js'
import { RandomIdFactory } from '../../src/adapters/RandomIdFactory.js'
import { UserQuestionsAdapter } from '../../src/adapters/UserQuestionsAdapter.js'
import type { UseCaseDeps } from '../../src/application/ports.js'
import type { JsonLedgerRepository } from '../../src/adapters/JsonLedgerRepository.js'
import {
  defineCreateTool as createTool,
  defineCaptureTool as captureTool,
  defineStatusTool as statusTool,
  defineMoveTool as moveTool,
  defineDecomposeTool as decomposeTool,
  defineTaskMoveTool as taskMoveTool,
  defineTaskReportTool as taskReportTool,
  defineSubmitTool as submitTool,
  defineAskConfirmTool as askConfirmTool,
  defineAcceptSheetTool as acceptSheetTool,
} from '../../src/tools/index.js'

/** 工具依赖：store 强依赖；agents/sessionProjections 为惰性服务访问器（缺失 → 认证降级）。 */
export interface ReqboardToolDeps {
  store: JsonLedgerRepository
  now: () => number
  /** 当前 agents 服务（unavailable → undefined）。 */
  agents?: () => unknown
  /** 当前 sessionProjections 服务（unavailable → undefined）。 */
  sessionProjections?: () => unknown
  /** 工具痕迹表（REQ-2e9473 t05/t06）：done 凭证门判定开工以来有无真实工具动作。可选。 */
  toolTrace?: Map<string, ToolTraceEntry[]>
  /** done 批量关闭节流窗口（毫秒，默认 60000；测试可注入 0 关闭）。 */
  doneThrottleMs?: number
  /**
   * 文档根（可选）。不传则用**进程级临时目录**（见 testWorkspaceRoot）。
   *
   * 为什么必须有默认值：FileDocRepository 不传 root 就按 process.cwd() 解析 docs/，
   * 而测试进程的 cwd 正是包目录 —— 于是任何"忘了隔离"的用例都会把需求文档写进仓库。
   * 实测代价：跑一次全量测试多出 44 个文件；历史上有 8717 个这样的产物被提交进仓库。
   * 安全默认值不依赖调用方记得传参。
   */
  workspaceRoot?: string
  /** userQuestions 弹框服务（REQ-2e9473 t07 ask_confirm；缺失 → ask_confirm 降级 fallback=board）。 */
  userQuestions?: () => unknown
  /** 最近用户消息缓冲（REQ-2e9473 t10 文字确认核验；缺失 → 核验降级放行并在返回中注明）。 */
  recentUserMsgs?: Map<string, RecentUserMsg[]>
}

/**
 * 测试用的默认文档根（惰性创建，一个 worker 进程一份）。
 * 存在的唯一目的：让"忘了传 workspaceRoot"的用例写到 /tmp，而不是写进仓库。
 */
let wsRootCache: string | undefined
function testWorkspaceRoot(): string {
  if (wsRootCache === undefined) wsRootCache = mkdtempSync(join(tmpdir(), 'pmboard-ws-'))
  return wsRootCache
}

/**
 * 解析本次测试的文档根（安全兜底）：
 *   - 显式传了 workspaceRoot → 用它；
 *   - cwd 是**包目录**（= 没隔离）→ 用进程级临时目录兜底，绝不写进仓库；
 *   - 其余 cwd（测试自己 chdir 到了临时目录）→ 照旧用 cwd，保持既有语义。
 */
function resolveWorkspaceRoot(explicit: string | undefined): string {
  if (explicit !== undefined) return explicit
  // 必须用 realpath 比较：macOS 上 tmpdir() 给 /var/...，而 chdir 后 process.cwd() 是
  // /private/var/...（/var 是软链）——直接字符串比较会判成"不在临时目录"而误兜底。
  const real = (p: string): string => {
    try { return realpathSync(p).replace(/\\/g, '/') } catch { return p.replace(/\\/g, '/') }
  }
  const cwd = real(process.cwd())
  const tmp = real(tmpdir()).replace(/\/+$/, '')
  // 只有"测试自己 chdir 到的临时目录"才沿用 cwd；**仓库内任何目录一律兜底到临时根**。
  // 只判"是不是包目录"不够：从 agent-dh 目录跑测试时，产物会写进真实的 agent-dh/docs/requirements/
  // （实测：一次误从仓库根跑，污染了 120+ 个文件）。
  return cwd === tmp || cwd.startsWith(tmp + '/') ? process.cwd() : testWorkspaceRoot()
}

/**
 * 在当前解析出的测试文档根写占位文件（REQ-2d1c74 FR-5：plan/archive 提交起要求
 * 登记路径真实落盘——存量夹具的 'p.md' / 'docs/requirements/<REQ>/plan.md' 等
 * 占位路径需要有文件才能过 assertArtifactOpenable）。按调用时的 cwd 解析根，
 * 故 chdir 到临时目录的测试文件会写进各自目录，绝不写进仓库。
 */
export function stubDocFile(relPath: string, root?: string, content = '# 占位（测试夹具落盘）\n'): void {
  const abs = join(root ?? resolveWorkspaceRoot(undefined), relPath)
  mkdirSync(dirname(abs), { recursive: true })
  writeFileSync(abs, content)
}

/** 旧 deps → 用例依赖（适配器即 t5 落地的端口实现）。 */
function toUseCaseDeps(deps: ReqboardToolDeps): UseCaseDeps {
  // 注意：doneThrottleMs 用 getter 活读——既有测试在工具构造后才把节流改成 0
  // （tests/decompose-tools.test.ts:329/439），快照会改变行为。
  const uc: UseCaseDeps = {
    repo: deps.store,
    docs: new FileDocRepository({ workspaceRoot: resolveWorkspaceRoot(deps.workspaceRoot) }),
    clock: { now: deps.now },
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({
      ...(deps.toolTrace !== undefined ? { toolTrace: deps.toolTrace } : {}),
      ...(deps.recentUserMsgs !== undefined ? { recentUserMsgs: deps.recentUserMsgs } : {}),
      ...(deps.agents !== undefined ? { agents: deps.agents } : {}),
      ...(deps.sessionProjections !== undefined ? { sessionProjections: deps.sessionProjections } : {}),
      now: deps.now,
    }),
    questions: new UserQuestionsAdapter(() => deps.userQuestions?.()),
  }
  Object.defineProperty(uc, 'doneThrottleMs', { get: () => deps.doneThrottleMs, enumerable: true, configurable: true })
  return uc
}

/** submit 旧工厂 → 新 reqboard_submit（注入 kind，参数/返回体与旧工具逐一对应）。 */
function submitWrapper(kind: string, deps: ReqboardToolDeps) {
  const tool = submitTool(toUseCaseDeps(deps)) as unknown as { execute: (a: unknown, e: unknown) => unknown }
  return {
    ...tool,
    execute: (args: unknown, exec: unknown) => tool.execute({ ...(args as Record<string, unknown> ?? {}), kind }, exec),
  }
}

export function defineCreateTool(deps: ReqboardToolDeps) { return createTool(toUseCaseDeps(deps)) }
export function defineCaptureTool(deps: ReqboardToolDeps) { return captureTool(toUseCaseDeps(deps)) }
export function defineStatusTool(deps: ReqboardToolDeps) { return statusTool(toUseCaseDeps(deps)) }
export function defineMoveTool(deps: ReqboardToolDeps) { return moveTool(toUseCaseDeps(deps)) }
export function defineDecomposeTool(deps: ReqboardToolDeps) { return decomposeTool(toUseCaseDeps(deps)) }
export function defineTaskMoveTool(deps: ReqboardToolDeps) { return taskMoveTool(toUseCaseDeps(deps)) }
export function defineTaskReportTool(deps: ReqboardToolDeps) { return taskReportTool(toUseCaseDeps(deps)) }
export function defineAskConfirmTool(deps: ReqboardToolDeps) { return askConfirmTool(toUseCaseDeps(deps)) }
export function defineConfirmArtifactTool(deps: ReqboardToolDeps) { return askConfirmTool(toUseCaseDeps(deps)) }
export function defineAcceptSheetTool(deps: ReqboardToolDeps) { return acceptSheetTool(toUseCaseDeps(deps)) }
export function defineRequirementSubmitTool(deps: ReqboardToolDeps) { return submitWrapper('requirement', deps) }
export function definePlanSubmitTool(deps: ReqboardToolDeps) { return submitWrapper('plan', deps) }
export function defineVerifySubmitTool(deps: ReqboardToolDeps) { return submitWrapper('verification', deps) }
export function defineArchiveSubmitTool(deps: ReqboardToolDeps) { return submitWrapper('archive', deps) }
