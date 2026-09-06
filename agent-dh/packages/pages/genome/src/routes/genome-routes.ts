// @pi-investment/dashboard-genome · 路由薄层
// /dashboard/api/genome：200 {success,true,data:GenomeData}（client 半同源 fetch，只读聚合）。
// /dashboard/api/genome/explain?module=<id>：AI 讲解——把「请讲解某区域」投递给在线 investor
//   agent（ctx.agents.roots() → followup，参照 lifecycle deliverReminder 投递范式）。讲解由 agent
//   生成并回复到其会话，本接口同步只返回投递结果。无 agents 服务/无在线 agent → 4xx，前端示错。
// host 内部异常 → 500 {success:false,error}，前端降级横幅。

import type { IncomingMessage, ServerResponse } from 'node:http'
import { createUserMessage } from '@deepseek-ai/dsh-llm'
import { GenomeAggregationService } from '../services/genome-aggregation.js'
import type { GenomeData } from '../types/index.js'

function json(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body)
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  })
  res.end(text)
}

export function createGenomeHandler(aggregator: GenomeAggregationService) {
  return async (_req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const data = await aggregator.fetchGenomeData()
      json(res, 200, { success: true, data })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      json(res, 500, { success: false, error: msg })
    }
  }
}

/** 各看板区域的讲解元数据（标题/一句话定位 + 讲解要点），模块 id 与 client view.ts 的 data-explain-module 一致。 */
const MODULES: Record<string, { title: string; focus: string }> = {
  sections: {
    title: '② 段状态矩阵',
    focus: '4 个基因组段的版本号、层级（宪法锁定 / 可进化）、段全文与最近一次变更（谁在何时以何理由改了什么）。回答：这套提示词现在长什么样、规则文本在不在。',
  },
  consistency: {
    title: '③ 一致性诊断',
    focus: 'F1 哨兵一致性核验 C1/C2/C3：登记状态与实际落库是否一致（版本链、候选登记、落库对应）。回答：候选与正式版会不会打架、gate 裁决有没有案可据。',
  },
  candidates: {
    title: '④ 候选生命周期流水线',
    focus: '规则改进从登记（genome_update candidate 观察版）→ 观察期（进度）→ validation_gate 裁决（promote 转正 / rollback 回滚）的全流程，含结构健康检查与待裁决标记。回答：什么规则正在试运行、何时出结果、卡没卡住。',
  },
  timeline: {
    title: '⑤ 谱系时间线',
    focus: '基因组版本演进史（update / promote / rollback），每条含段、版本、stage、git commit 与理由。回答：这套提示词是怎么一步一步进化到今天的、每次改动留没留痕。',
  },
}

/** 按模块裁剪聚合快照为紧凑文本（agent 讲解时引用，标注来源=本看板聚合，含 fetchedAt 时点）。 */
function snapshotFor(module: string, d: GenomeData): string {
  const secLine = d.sections
    .map((s) => `${s.id} v${s.version}${s.class === 'constitution' ? '(锁定)' : '(可进化)'}`)
    .join('、')
  const cons = d.consistency
  const issueLine = cons.healthy
    ? '全部通过'
    : cons.issues.filter((i) => i.items.length > 0).map((i) => `${i.id} ${i.items.length} 项`).join('、')
  const counts: Record<string, number> = {}
  for (const c of d.candidates) counts[c.status] = (counts[c.status] ?? 0) + 1
  const due = d.candidates.filter((c) => c.due).length
  const candLine = Object.entries(counts)
    .map(([k, v]) => `${k} ${v}`)
    .join('、') + (due > 0 ? `；其中待裁决 ${due}` : '')
  const histLine = d.history.length > 0
    ? `最近 ${Math.min(3, d.history.length)} 条：${d.history.slice(0, 3).map((h) => `${h.genomeVersion} ${h.section} v${h.sectionVersion} ${h.type}${h.stage ? `(${h.stage})` : ''}`).join(' | ')}`
    : '空'
  switch (module) {
    case 'sections':
      return `基因组 ${d.genomeVersion}（最近更新 ${d.updatedAt}）\n段：${secLine}`
    case 'consistency':
      return `核验时点 ${cons.checkedAt} → ${issueLine}\n` + (!cons.healthy
        ? cons.issues.filter((i) => i.items.length > 0).map((i) => `${i.id} ${i.label}：${i.description}`).join('\n')
        : 'C1/C2/C3 无异常项')
    case 'candidates':
      return `候选共 ${d.candidates.length} 条：${candLine}`
    case 'timeline':
      return `谱系共 ${d.history.length} 条；${histLine}`
    default:
      return `基因组 ${d.genomeVersion}；段：${secLine}；一致性：${issueLine}；候选：${candLine}`
  }
}

/** explain handler：agentsService 由 host apply 侧 ctx.inject(['agents']) 惰性注入后传入（未就绪时 handler 返回 409）。 */
export function createExplainHandler(agentsService: unknown, aggregator: GenomeAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const url = new URL(req.url ?? '', 'http://localhost')
      const module = url.searchParams.get('module') ?? ''
      const mod = MODULES[module]
      if (mod === undefined) {
        json(res, 400, { success: false, error: `未知模块「${module}」；可选：${Object.keys(MODULES).join(' / ')}` })
        return
      }

      // 找在线 agent（优先 investor 前缀，退而求其次任意有 followup 的 root）
      const agents = agentsService as { roots?: () => unknown[] } | null | undefined
      const roots = typeof agents?.roots === 'function' ? agents.roots() : []
      const online = roots.find((a) => {
        const o = a as { id?: unknown; followup?: unknown }
        return typeof o?.followup === 'function' && String(o.id).startsWith('investor')
      }) ?? roots.find((a) => {
        const o = a as { followup?: unknown }
        return typeof o?.followup === 'function'
      })
      if (online === undefined) {
        json(res, 409, { success: false, error: '暂无在线 AI 会话可接收讲解：请确认 investor 主窗口在线后重试' })
        return
      }

      const data = await aggregator.fetchGenomeData()
      const text = [
        `【看板 AI 讲解请求】你在「自主进化」看板（dashboard-genome）的「${mod.title}」区域，用户点了「🤖 讲解」。请直接面向用户讲解这一块。`,
        '',
        '请输出 150-300 字的讲解，覆盖：',
        `1. 这个区域展示什么内容（数据来自 genome.json / candidates.json / C1-C3 一致性核验，均为本地基因组文件聚合）`,
        '2. 它解决什么问题（用户在回答哪类疑问）',
        '3. 它在规则进化链路中的位置与作用（与 genome_update(stage=candidate)、validation_gate 裁决、genome_promote / genome_rollback 的关系）',
        '4. 结合当前实时状态的解读（快照见下；引用具体数字时标注来源=「自主进化看板聚合快照」及其时点）',
        '',
        '直接输出讲解正文，面向产品用户、清晰友好，不要复述本指令。',
        '',
        `—— 模块定位：${mod.focus}`,
        `—— 当前快照（dashboard-genome 聚合，fetchedAt ${data.fetchedAt}）：`,
        snapshotFor(module, data),
      ].join('\n')

      const target = online as { id?: unknown; followup?: (msg: unknown) => unknown }
      target.followup?.(createUserMessage({
        content: [{ type: 'text', text }],
        source: { kind: 'plugin', plugin: 'dashboard-genome' },
      }))
      json(res, 200, { success: true, data: { delivered: true, target: String(target.id ?? ''), module, title: mod.title } })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      json(res, 500, { success: false, error: msg })
    }
  }
}
