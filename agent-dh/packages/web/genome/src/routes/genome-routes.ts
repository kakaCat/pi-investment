// @pi-investment/dashboard-genome · 路由薄层
// /dashboard/api/genome：200 {success,true,data:GenomeData}（client 半同源 fetch，只读聚合）。
// /dashboard/api/genome/explain?module=<id>&item=<id>：条目级 AI 讲解——把「请讲解某一条」投递给
//   在线 investor agent（ctx.agents.roots() → followup，参照 lifecycle deliverReminder 投递范式）。
//   module=sections（item: constitution|principles|rules|lessons）/ consistency（item: C1|C2|C3）/
//   candidates（item: 候选 id）。讲解由 agent 生成并回复到其会话，本接口同步只返回投递结果。
//   无 agents 服务/无在线 agent → 4xx，前端示错；host 内部异常 → 500 {success:false,error}。

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

const SEC_NAMES: Record<string, string> = {
  constitution: '交易宪法', principles: '决策原则', rules: '操作规则', lessons: '经验教训',
}

/**
 * 各模块条目级讲解元数据。kind=条目类型中文名（提示 400 文案用）。
 * 讲解已条目化（每个 段卡 / 哨兵行 / 候选卡 一个按钮），不再支持整区讲解。
 */
const MODULES: Record<string, { title: string; kind: string; focus: string }> = {
  sections: {
    title: '② 段状态矩阵', kind: '基因组段',
    focus: '该段的定位与层级（宪法锁定 / 可进化）、当前版本、段全文要点与最近一次变更（谁在何时以何理由改了什么）。回答：这套提示词这一段现在长什么样、为什么这么写。',
  },
  consistency: {
    title: '③ 一致性诊断', kind: '一致性哨兵',
    focus: 'F1 哨兵 C1/C2/C3 之一：核验登记与实际落库是否一致，当前有无异常项、异常意味着什么、该怎么处置。回答：候选与正式版会不会打架、gate 裁决有没有案可据。',
  },
  candidates: {
    title: '④ 候选生命周期流水线', kind: '规则候选',
    focus: '这条规则改进候选：改的是哪一段、在哪个版本登记、观察期进度、结构健康检查、下一步由 validation_gate 裁决转正或回滚。回答：这条正在试运行的规则在观察什么、何时出结果、卡没卡住。',
  },
}

/** 枚举条目模块的合法 item（candidates 为动态 id，单独校验）。 */
const ENUM_ITEMS: Record<string, string[]> = {
  sections: ['constitution', 'principles', 'rules', 'lessons'],
  consistency: ['C1', 'C2', 'C3'],
}

function itemDisplayName(module: string, item: string, d: GenomeData): string {
  if (module === 'sections') return SEC_NAMES[item] ?? item
  if (module === 'consistency') {
    const iss = d.consistency.issues.find((i) => i.id === item)
    return iss ? `${iss.id} ${iss.label}` : item
  }
  return `候选 ${item}`
}

function cut(s: string | undefined, n: number): string {
  if (!s) return ''
  return s.length > n ? `${s.slice(0, n)}…` : s
}

/** 按 模块+条目 裁剪聚合快照为紧凑文本（agent 讲解时引用，标注来源=本看板聚合，含 fetchedAt 时点）。 */
function snapshotFor(module: string, item: string, d: GenomeData): string {
  if (module === 'sections') {
    const s = d.sections.find((x) => x.id === item)
    if (s === undefined) return '（未找到该段）'
    const lc = s.lastChange
    const lcLine = lc
      ? `；最近变更：${lc.genomeVersion ?? ''} ${lc.type ?? 'update'}${lc.ts ? ` @${lc.ts}` : ''}${lc.reason ? ` —— ${cut(lc.reason, 90)}` : ''}`
      : '；最近变更：无记录'
    const content = (s.content ?? '').replace(/\s+/g, ' ').trim()
    return [
      `段「${SEC_NAMES[s.id] ?? s.id}」v${s.version}${s.class === 'constitution' ? '（宪法层·锁定）' : '（可进化）'}，全文 ${s.content?.length ?? 0} 字${lcLine}`,
      `全文开头：${cut(content, 220) || '（空）'}`,
    ].join('\n')
  }
  if (module === 'consistency') {
    const i = d.consistency.issues.find((x) => x.id === item)
    if (i === undefined) return '（未找到该哨兵）'
    const rows = i.items.length > 0
      ? i.items.slice(0, 3).map((it) => `  - ${[it.genomeVersion ? `g${it.genomeVersion}` : '', it.section ? (SEC_NAMES[it.section] ?? it.section) : '', it.sectionVersion !== undefined ? `v${it.sectionVersion}` : '', it.ts ?? '', cut(it.reason, 80)].filter(Boolean).join(' · ')}`).join('\n')
      : '  无异常项'
    return `哨兵 ${i.id}「${i.label}」：${i.description}\n核验时点 ${d.consistency.checkedAt}，当前 ${i.items.length === 0 ? '✅ 通过' : `❌ ${i.items.length} 项异常`}：\n${rows}`
  }
  if (module === 'candidates') {
    const c = d.candidates.find((x) => x.id === item)
    if (c === undefined) return '（未找到该候选）'
    const hc = c.healthCheck
      ? `结构健康 ${hcPassedText(c.healthCheck.passed)}${c.healthCheck.sizeDelta !== undefined ? `（diff ${c.healthCheck.sizeDelta} 字符）` : ''}${c.healthCheck.checkedAt ? ` @${c.healthCheck.checkedAt}` : ''}`
      : ''
    const statusLine = c.due ? '已过观察期·待 gate 裁决' : (c.remainingDays !== undefined && c.remainingDays >= 0 ? `观察中·余 ${c.remainingDays} 天` : String(c.status))
    return [
      `候选 ${c.id}：${SEC_NAMES[c.section] ?? c.section} ${c.genomeVersion} v${c.sectionVersion}，状态 ${statusLine}${c.mutationType ? `（类型 ${c.mutationType}）` : ''}`,
      `观察期：${c.createdAt ?? ''} → ${c.observeUntil ?? ''}${c.progress !== undefined ? `（进度 ${Math.round(c.progress * 100)}%）` : ''}`,
      hc,
      c.note ? `note：${cut(c.note, 160)}` : '',
    ].filter(Boolean).join('\n')
  }
  return ''
}

function hcPassedText(passed: boolean): string {
  return passed ? '✅' : '❌'
}

/** explain handler：agentsService 由 host apply 侧 ctx.inject(['agents']) 惰性注入后传入（未就绪时 handler 返回 409）。 */
export function createExplainHandler(agentsService: unknown, aggregator: GenomeAggregationService) {
  return async (req: IncomingMessage, res: ServerResponse): Promise<void> => {
    try {
      const url = new URL(req.url ?? '', 'http://localhost')
      const module = url.searchParams.get('module') ?? ''
      const item = url.searchParams.get('item') ?? ''
      const mod = MODULES[module]
      if (mod === undefined) {
        json(res, 400, { success: false, error: `未知模块「${module}」；可选：${Object.keys(MODULES).join(' / ')}` })
        return
      }
      if (item === '') {
        json(res, 400, {
          success: false,
          error: `讲解已下放到具体条目：请点击「${mod.title}」里 ${mod.kind} 行上的「🤖」，AI 会讲解那一条（讲解出现在会话）。`,
        })
        return
      }

      // 条目合法性：candidates 动态校验（需数据），sections/consistency 枚举校验（静态）
      let data: GenomeData
      if (module === 'candidates') {
        data = await aggregator.fetchGenomeData()
        if (!data.candidates.some((c) => c.id === item)) {
          json(res, 404, { success: false, error: `未知候选「${item}」：刷新看板确认该候选仍存在` })
          return
        }
      } else {
        const allowed = ENUM_ITEMS[module] ?? []
        if (!allowed.includes(item)) {
          json(res, 404, { success: false, error: `未知条目「${item}」（模块 ${module} 可选：${allowed.join(' / ')}）` })
          return
        }
        data = await aggregator.fetchGenomeData()
      }

      const name = itemDisplayName(module, item, data)

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

      const text = [
        `【看板 AI 讲解请求】你在「自主进化」看板（dashboard-genome），用户点了「${mod.title}」中「${name}」这一条${mod.kind}旁边的「🤖 讲解」，请直接面向用户讲解**这一条**（不要泛泛讲整个看板）。`,
        '',
        '请输出 120-250 字的讲解，覆盖：',
        '1. 这一条是什么（结合下方快照，用产品用户听得懂的话）',
        '2. 它解决什么问题 / 为什么出现在看板',
        '3. 它在规则进化链路（genome_update(stage=candidate) → 观察期 → validation_gate 裁决 → genome_promote / genome_rollback）中的位置，当前状态怎么解读',
        '4. 快照中若含异常/待办，点明含义并给出建议下一步；正常则讲它如何保障一致性/可追溯',
        '',
        '引用具体数字时标注来源=「自主进化看板聚合快照」及其时点。直接输出讲解正文，不要复述本指令。',
        '',
        `—— 条目：${name}（${module} · ${item}）`,
        `—— 定位：${mod.focus}`,
        `—— 当前快照（dashboard-genome 聚合，fetchedAt ${data.fetchedAt}）：`,
        snapshotFor(module, item, data),
      ].join('\n')

      const target = online as { id?: unknown; followup?: (msg: unknown) => unknown }
      target.followup?.(createUserMessage({
        content: [{ type: 'text', text }],
        source: { kind: 'plugin', plugin: 'dashboard-genome' },
      }))
      json(res, 200, {
        success: true,
        data: { delivered: true, target: String(target.id ?? ''), module, item, title: `「${name}」讲解` },
      })
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      json(res, 500, { success: false, error: msg })
    }
  }
}
