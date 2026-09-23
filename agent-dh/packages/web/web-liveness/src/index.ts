/**
 * @pi-investment/web-liveness · host 半。
 *
 * 三件事：
 * 1. client 半的载体（浏览器端活性对齐：/plugins/events 的 graph.rev 比对 →
 *    停机横幅 / 自动刷新 / 开机自检，全部在 `src/client/`）。
 * 2. `quick_restart` 工具（RFC 016，2026-09-23）：agent 的轻量重启入口。
 *    只编排不实现——spawn `scripts/quick-restart.sh`（detached），由它委托
 *    scripts/stop.sh + start.sh（重启唯一入口）完成杀与起。
 *    与 lifecycle 的 self_restart 分工：本工具不动 git、不回滚，发版场景仍走 self_restart。
 * 3. 工作快照 + 续跑（RFC 016 增补，2026-09-24）：quick_restart 断线前把
 *    「还在工作的窗口」（Agent.status === 'running'）记入 state/quick-restart-resume.json，
 *    重启后 host 启动时逐窗 followup 续跑消息（窗口未存活则等 agent/created，30 分钟超时；
 *    条目超 24h 未投递按死信丢弃）。不写 lifecycle 的 pending-resume.json——
 *    那套绑定 git 检查点/回滚/self_finalize 语义，互不干扰。
 *
 * @module @pi-investment/web-liveness
 */
import { spawn } from 'node:child_process'
import { existsSync, readFileSync, statSync, writeFileSync, renameSync } from 'node:fs'
import { join } from 'node:path'
import type { Context } from '@deepseek-ai/cordis'
import { defineTool } from '@deepseek-ai/dsh-tools'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import {
  LOCK_FRESH_MS,
  MIN_INTERVAL_MS,
  PRE_KILL_DELAY_S,
  isLockFresh,
  quickRestartAllowed,
} from './guard.js'
import {
  RESUME_WAIT_MS,
  partitionResumeEntries,
  renderResumeMessage,
  selectBusyAgentIds,
  type ResumeFile,
} from './resume.js'

export const name = 'web-liveness'

/** 页面插件无静态 inject 的惯例：(ctx as any).inject(...) 惰性注入（genome/dsh-pmboard 同款）。 */
type InjectableContext = Context & { inject?: (services: string[], cb: (c: any) => void) => void }

interface WebLivenessConfig {
  /** agent-dh 根目录（缺省 = 进程 cwd，本实例进程 cwd 即 agent-dh，契约见部署文档）。 */
  agentDhRoot?: string
}

export function apply(ctx: Context, config?: WebLivenessConfig): void {
  ctx.logger(name).info('web-liveness host applied (client: liveness watch; tool: quick_restart + resume)')

  const agentDhRoot = config?.agentDhRoot ?? process.cwd()
  const stateDir = join(agentDhRoot, '.dsh-data', 'state')
  const script = join(agentDhRoot, 'scripts', 'quick-restart.sh')
  const requestFile = join(stateDir, 'quick-restart-request.json')
  const resultFile = join(stateDir, 'quick-restart-result.json')
  const resumeFile = join(stateDir, 'quick-restart-resume.json')
  const resumeDoneFile = join(stateDir, 'quick-restart-resume.done.json')
  const lockFile = join(stateDir, 'restarting.lock')
  const log = ctx.logger(name)

  const readJson = (path: string): Record<string, unknown> | undefined => {
    try {
      return JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>
    } catch {
      return undefined
    }
  }

  /** 原子写 JSON（temp + rename），防半文件。 */
  const writeJson = (path: string, value: unknown): void => {
    const tmp = `${path}.tmp.${process.pid}`
    writeFileSync(tmp, JSON.stringify(value, null, 2))
    renameSync(tmp, path)
  }

  const mtimeOf = (path: string): number | undefined => {
    try {
      return statSync(path).mtimeMs
    } catch {
      return undefined
    }
  }

  // tools + agents 一起注入：注册 quick_restart（execute 里要枚举活窗口做快照），
  // 并装 boot 续跑投递（重启后把快照里的窗口逐个叫醒）。
  ;(ctx as InjectableContext).inject?.(['tools', 'agents'], (c) => {
    // ── boot 续跑：读 quick-restart-resume.json，逐窗投递 ──────────────────
    const resumeData = readJson(resumeFile) as ResumeFile | undefined
    if (resumeData && Array.isArray(resumeData.sessions) && resumeData.sessions.length > 0) {
      const { active, expired } = partitionResumeEntries(resumeData.sessions, Date.now())
      if (expired.length > 0) {
        log.warn(`resume: ${expired.length} 条快照已过期（>${24}h），按死信丢弃：${expired.map((e) => e?.agentId ?? '?').join(',')}`)
      }
      if (active.length > 0) {
        const reason = String(resumeData.reason ?? '（未记录）')
        const text = renderResumeMessage(reason)
        // 剩余待投递集合；每条投递成功后落盘，全空后 rename .done（幂等：崩溃重进继续投剩下的）
        const remaining = new Map(active.map((e) => [e.agentId, e]))
        const persist = (): void => {
          if (remaining.size === 0) {
            try { renameSync(resumeFile, resumeDoneFile) } catch { /* 尽力而为 */ }
          } else {
            writeJson(resumeFile, { ...resumeData, sessions: [...remaining.values()] })
          }
        }
        const deliver = (agent: any): boolean => {
          const id = String(agent?.id)
          if (!remaining.has(id)) return false
          try {
            agent.followup(createUserMessage({
              content: [{ type: 'text', text }],
              source: { kind: 'plugin', plugin: 'web-liveness' },
            }))
          } catch (e) {
            log.warn(`resume: followup ${id} 失败（保留下轮再投）：${String(e)}`)
            return false
          }
          remaining.delete(id)
          persist()
          log.info(`resume: 续跑消息已投递 ${id}`)
          return true
        }
        // ① 已存活的窗口立即投递
        for (const entry of active) {
          try { deliver(c.agents.get(entry.agentId)) } catch { /* get 失败按未存活处理 */ }
        }
        // ② 未存活的（Web 会话等用户回来才恢复）等 agent/created，30 分钟超时
        if (remaining.size > 0) {
          const dispose = ctx.on('agent/created', ({ agent }: any) => {
            deliver(agent)
            if (remaining.size === 0) { dispose(); clearTimeout(timer) }
          })
          const timer = setTimeout(() => {
            dispose()
            log.warn(`resume: ${RESUME_WAIT_MS / 60000} 分钟等待超时，${remaining.size} 个窗口未出现，留待下次启动重投：${[...remaining.keys()].join(',')}`)
            persist()
          }, RESUME_WAIT_MS)
          timer.unref?.()
        }
      } else {
        // 全是死信：直接归档，不再投递
        try { renameSync(resumeFile, resumeDoneFile) } catch { /* 尽力而为 */ }
      }
    }

    // ── quick_restart 工具 ─────────────────────────────────────────────────
    c.tools.register(defineTool({
      name: 'quick_restart',
      description:
        '用于：轻量重启 agent-dh 服务（让改动生效、状态异常自救）。' +
        '例如：页面/连接状态异常需要干净重启，或改了 tsx 直载的插件源码需要重新加载。' +
        `调用时自动快照「还在工作的窗口」，约 ${PRE_KILL_DELAY_S} 秒后断线重启，~15 秒后恢复，` +
        '重启后这些窗口会收到续跑消息继续工作，所有页面会自动刷新（web-liveness）。' +
        '注意：① 先把要对用户说的话说完，本工具必须是本轮最后一个动作——断线会杀死未完成的回复；' +
        '② 本工具不动 git、不建检查点、不回滚——改代码发版（要验证合并）请用 self_restart；' +
        '③ 有 5 分钟限流，且 self_restart 进行中会被拒绝。',
      parameters: {
        reason: { type: 'string', description: '重启原因（会写进 state/quick-restart-request.json 审计）', required: true },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            scheduled: { type: 'boolean', description: '是否已安排重启' },
            message: { type: 'string', description: '结果说明（含快照窗口数、上次重启结果或被拒原因）' },
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

        // 工作快照：断线前记下「还在工作的窗口」，重启后由本插件逐窗注入续跑消息。
        // 只认 status==='running'（idle 窗口的 inbox 排队是持久化的，重启不丢）。
        // 调用者自己必然在列——它正在执行本工具。
        const reason = String(args.reason)
        let busyIds: string[] = []
        try {
          busyIds = selectBusyAgentIds(c.agents.roots())
        } catch (e) {
          log.warn(`quick_restart: 快照枚举失败（按空清单继续，不阻塞重启）：${String(e)}`)
        }
        writeJson(resumeFile, {
          reason,
          at: now,
          sessions: busyIds.map((agentId) => ({ agentId, status: 'running', at: now })),
        } satisfies ResumeFile)

        // 记录请求（原子写），供限流与审计
        writeJson(requestFile, { reason, requestedAt: now })

        // spawn detached 重启器：本进程 10 秒后就会被它杀死，必须脱壳
        const child = spawn('bash', [script, reason], {
          detached: true,
          stdio: 'ignore',
          cwd: agentDhRoot,
        })
        child.unref()
        log.info(`quick_restart scheduled: reason=${reason} restarter pid=${child.pid} busy=${busyIds.join(',') || '(无)'}`)

        const lastResult = readJson(resultFile)
        const lastResultLine = lastResult
          ? `上次重启结果：${String(lastResult.status)}（${String(lastResult.at)}）${lastResult.status === 'failed' ? `——${String(lastResult.detail)}` : ''}`
          : '（无历史重启记录）'
        return {
          scheduled: true,
          message:
            `已安排：服务将在约 ${PRE_KILL_DELAY_S} 秒后断线重启（重启器 pid=${child.pid}），~15 秒后恢复，` +
            `页面会自动刷新。已快照 ${busyIds.length} 个在工作的窗口（${busyIds.join('、') || '无'}），` +
            `重启后它们会收到续跑消息。${lastResultLine}`,
        } as any
      },
    } as any))
  })
}
