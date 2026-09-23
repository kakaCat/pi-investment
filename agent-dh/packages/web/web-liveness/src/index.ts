/**
 * @pi-investment/web-liveness · host 半。
 *
 * 两件事：
 * 1. client 半的载体（浏览器端活性对齐：/plugins/events 的 graph.rev 比对 →
 *    停机横幅 / 自动刷新 / 开机自检，全部在 `src/client/`）。
 * 2. `quick_restart` 工具（RFC 016，2026-09-23）：agent 的轻量重启入口。
 *    只编排不实现——spawn `scripts/quick-restart.sh`（detached），由它委托
 *    scripts/stop.sh + start.sh（重启唯一入口）完成杀与起。
 *    与 lifecycle 的 self_restart 分工：本工具不动 git、不回滚、不续跑，
 *    发版场景仍走 self_restart。
 *
 * @module @pi-investment/web-liveness
 */
import { spawn } from 'node:child_process'
import { existsSync, readFileSync, statSync, writeFileSync, renameSync } from 'node:fs'
import { join } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import {
  LOCK_FRESH_MS,
  MIN_INTERVAL_MS,
  PRE_KILL_DELAY_S,
  isLockFresh,
  quickRestartAllowed,
} from './guard.js'

export const name = 'web-liveness'

/** 页面插件无静态 inject 的惯例：(ctx as any).inject(...) 惰性注入（genome/dsh-pmboard 同款）。 */
type InjectableContext = Context & { inject?: (services: string[], cb: (c: any) => void) => void }

interface WebLivenessConfig {
  /** agent-dh 根目录（缺省 = 进程 cwd，本实例进程 cwd 即 agent-dh，契约见部署文档）。 */
  agentDhRoot?: string
}

export function apply(ctx: Context, config?: WebLivenessConfig): void {
  ctx.logger(name).info('web-liveness host applied (client: liveness watch; tool: quick_restart)')

  const agentDhRoot = config?.agentDhRoot ?? process.cwd()
  const stateDir = join(agentDhRoot, '.dsh-data', 'state')
  const script = join(agentDhRoot, 'scripts', 'quick-restart.sh')
  const requestFile = join(stateDir, 'quick-restart-request.json')
  const resultFile = join(stateDir, 'quick-restart-result.json')
  const lockFile = join(stateDir, 'restarting.lock')
  const log = ctx.logger(name)

  const readJson = (path: string): Record<string, unknown> | undefined => {
    try {
      return JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>
    } catch {
      return undefined
    }
  }

  const mtimeOf = (path: string): number | undefined => {
    try {
      return statSync(path).mtimeMs
    } catch {
      return undefined
    }
  }

  ;(ctx as InjectableContext).inject?.(['tools'], (c) => {
    c.tools.register(defineTool({
      name: 'quick_restart',
      description:
        '用于：轻量重启 agent-dh 服务（让改动生效、状态异常自救）。' +
        '例如：页面/连接状态异常需要干净重启，或改了 tsx 直载的插件源码需要重新加载。' +
        `调用后约 ${PRE_KILL_DELAY_S} 秒服务断线重启，~15 秒后恢复，所有页面会自动刷新（web-liveness）。` +
        '注意：① 先把要对用户说的话说完，本工具必须是本轮最后一个动作——断线会杀死未完成的回复；' +
        '② 本工具不动 git、不建检查点、不回滚、不续跑——改代码发版（要验证合并）请用 self_restart；' +
        '③ 有 5 分钟限流，且 self_restart 进行中会被拒绝。',
      parameters: {
        reason: { type: 'string', description: '重启原因（会写进 state/quick-restart-request.json 审计）', required: true },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            scheduled: { type: 'boolean', description: '是否已安排重启' },
            message: { type: 'string', description: '结果说明（含上次重启结果或被拒原因）' },
          },
          additionalProperties: false,
        },
        render: (_args: any, value: any) => [{ type: 'text', text: (value as { message?: string }).message ?? JSON.stringify(value) }],
      },
      timeoutMs: 10_000,
      execute: async (args: any) => {
        const now = Date.now()

        // 护栏 1：self_restart 进行中 → 避让
        if (isLockFresh(mtimeOf(lockFile), now)) {
          return {
            scheduled: false,
            message: `拒绝：self_restart 正在进行（restarting.lock 在 ${LOCK_FRESH_MS / 60000} 分钟内被触碰）。等它完成或锁过期后再试。`,
          } as any
        }

        // 护栏 2：限流
        const lastRequest = readJson(requestFile)
        const lastAt = typeof lastRequest?.requestedAt === 'number' ? lastRequest.requestedAt : undefined
        if (!quickRestartAllowed(lastAt, now, MIN_INTERVAL_MS)) {
          const waitS = Math.ceil((MIN_INTERVAL_MS - (now - (lastAt ?? 0))) / 1000)
          return {
            scheduled: false,
            message: `拒绝：距上次 quick_restart 不足 ${MIN_INTERVAL_MS / 60000} 分钟，请再等 ${waitS} 秒。轻量重启不是心跳——连续需要重启说明有别的问题，先排查。`,
          } as any
        }

        if (!existsSync(script)) {
          return { scheduled: false, message: `拒绝：重启器不存在（${script}），部署不完整，勿重试。` } as any
        }

        // 记录请求（原子写），供限流与审计
        const tmp = `${requestFile}.tmp.${process.pid}`
        writeFileSync(tmp, JSON.stringify({ reason: String(args.reason), requestedAt: now }, null, 2))
        renameSync(tmp, requestFile)

        // spawn detached 重启器：本进程 10 秒后就会被它杀死，必须脱壳
        const child = spawn('bash', [script, String(args.reason)], {
          detached: true,
          stdio: 'ignore',
          cwd: agentDhRoot,
        })
        child.unref()
        log.info(`quick_restart scheduled: reason=${String(args.reason)} restarter pid=${child.pid}`)

        const lastResult = readJson(resultFile)
        const lastResultLine = lastResult
          ? `上次重启结果：${String(lastResult.status)}（${String(lastResult.at)}）${lastResult.status === 'failed' ? `——${String(lastResult.detail)}` : ''}`
          : '（无历史重启记录）'
        return {
          scheduled: true,
          message:
            `已安排：服务将在约 ${PRE_KILL_DELAY_S} 秒后断线重启（重启器 pid=${child.pid}），~15 秒后恢复，` +
            `页面会自动刷新。${lastResultLine}`,
        } as any
      },
    } as any))
  })
}
