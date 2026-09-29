/**
 * RegenerateTool（工具名 reqboard_task_regenerate）——子卡链**再生成（补链）**+ 只读诊断
 * （卡片层契约 2026-09-28）。
 *
 * 契约用途：一张**意图=chain 却没有子卡链**的卡（历史非自动链需求 / 链只落了一半 / autoRun 事后才开）
 * 无法靠重跑开工补救（expandSubtasks 有子卡即整体跳过）。本工具补这条写路径：
 *   dry_run 缺省 true → 只输出每张顶层卡的链体检（expected/existing/missing），不写台账；
 *   dry_run:false + task_id + reason → 真补缺失阶段（已有子卡含 done 一律不动）。
 * solo 卡（stages: [] 显式无链）一律跳过并回执说明——"不需子卡"与"未生成"必须分开。
 *
 * @module dsh-pmboard/tools/RegenerateTool
 */
import { defineTool } from '@deepseek-ai/dsh-tools'
import { LIMITS } from '../../domain/limits.js'
import type { UseCaseDeps } from '../../application/ports.js'
import { executeRegenerateChain } from '../../application/use-cases/RegenerateChain.js'
import { assertNoPendingConfirm } from '../../application/internal/support.js'
import { fmt } from '../../domain/text/fmt.js'
import { renderSmart } from '../shared.js'

const summarize = (v: unknown): string => {
  const o = (v ?? {}) as Record<string, unknown>
  if (o['success'] !== true) return fmt('子卡链再生成未成功：{error}', { error: String(o['error'] ?? '') })
  const mode = o['dry_run'] === true ? '只读诊断' : '已补链'
  return fmt('子卡链{mode}（{req}）：扫描 {n} 张顶层卡，本次补子卡 {k} 张', {
    mode,
    req: String(o['requirement_id'] ?? ''),
    n: String(o['scanned'] ?? 0),
    k: String(o['created_total'] ?? 0),
  })
}

export function defineRegenerateTool(deps: UseCaseDeps) {
  return defineTool({
    name: 'reqboard_task_regenerate',
    description: [
      '用于：给「意图=chain 却缺子卡链」的父卡**再生成（补链）**，或只读诊断链是否完整。',
      'dry_run 缺省 true：只回执每个顶层卡的链体检（chain_status=solo/missing/partial/complete + expected/existing/missing），不写台账；',
      'dry_run:false 必须同时传 task_id 与 reason：只补**缺失阶段**，已有子卡（含 done）一律不动，且不做批量写；',
      'solo 卡（stages: [] 显式无链）跳过并回执说明；done/取消的卡不追溯生链。',
      '为什么需要它：懒展开只在开工那一次且被 req.autoRun 门住、有子卡即整体跳过——缺链的卡没有第二次机会。',
    ].join(''),
    parameters: {
      task_id: { type: 'string', description: '父卡 id（t-xxxxxx）；dry_run:false 时必填（一次只补一张）' },
      requirement_id: { type: 'string', description: '需求 id（REQ-xxxxxx）；不传则按 task_id 反查，或取本窗口绑定需求' },
      dry_run: { type: 'boolean', description: 'true（默认）=只读诊断；false=真补链（须同时传 task_id 与 reason）' },
      reason: { type: 'string', description: '补链理由（dry_run:false 必填；写入父卡 comment 留痕）' },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: {
          success: { type: 'boolean' },
          requirement_id: { type: 'string' },
          dry_run: { type: 'boolean' },
          applied: { type: 'boolean' },
          scanned: { type: 'number', description: '扫描到的顶层卡数' },
          created_total: { type: 'number', description: '本次新建子卡数' },
          candidates: {
            type: 'array',
            items: {
              type: 'object',
              additionalProperties: false,
              properties: {
                task_id: { type: 'string' },
                title: { type: 'string' },
                status: { type: 'string' },
                chain_status: { type: 'string', description: 'solo=显式无链 / missing=链未生成 / partial=缺段 / complete=完整' },
                expected: { type: 'array', items: { type: 'string' } },
                existing: { type: 'array', items: { type: 'string' } },
                missing: { type: 'array', items: { type: 'string' } },
                created: { type: 'array', items: { type: 'string' } },
                note: { type: 'string' },
              },
            },
          },
          error: { type: 'string' },
          code: { type: 'string' },
        },
      },
      render: renderSmart(summarize),
    },
    timeoutMs: LIMITS.timeoutWriteMs,
    async execute(args: unknown, exec: unknown): Promise<Record<string, unknown>> {
      assertNoPendingConfirm(deps, deps.session.windowKey(exec))
      return (await executeRegenerateChain(deps, args, exec)) as Record<string, unknown>
    },
  } as any)
}
