/**
 * 「🪙 Token」tab 渲染（REQ-a33899 t6）。
 *
 * 纯渲染：给定 /requirements/:id/token 的响应返回 HTML 字符串，不取数、不写、不碰 DOM。
 * 信息层级（对齐 design/ui.md §1）：常显汇总卡 + 四个折叠块——按流程节点 / 🧱 固定系统提示词 /
 * 💉 注入提示词 / ℹ️ 口径说明。固定提示词与注入提示词每段/每条可展开看**具体内容**。
 *
 * 纪律：所有用户可见文本经 esc() 转义；缺失语义是「无快照 / 不可用」，**绝不渲染 0 冒充**。
 *
 * @module dsh-pmboard/client/token-info
 */
import { esc } from './html.js'
import {
  fmtCny,
  fmtTokens,
  totalTokens,
  type InjectionCost,
  type PromptPartCost,
  type RequirementTokenStageRow,
  type RequirementTokenView,
  type SystemPromptCost,
  type TokenBuckets,
  type TokenExecutionRow,
  type TokenSnapshot,
} from '../shared/protocol.ts'
import { fmtTime } from './render/dom-utils.ts'

const STAGE_LABEL: Record<string, string> = {
  draft: '📝 立项',
  brainstorming: '🔍 需求分析',
  design: '🧩 设计',
  decomposing: '🪓 拆分',
  implementing: '🔨 实施',
  accepting: '✅ 验收',
  archived: '📦 归档',
  done: '✅ 完成', // legacy 过渡态：done 但未 archived（2026-09-21 前误标为「验收」，与 accepting 撞名）
}

function stageLabel(stage: string): string {
  return STAGE_LABEL[stage] ?? stage
}

/** 快照的一行摘要（悬停 title 用）。 */
function snapshotHint(snap: TokenSnapshot | undefined): string {
  if (snap === undefined) return '无快照'
  if (snap.source === 'unavailable') return '无快照（当时未取到会话投影）'
  return `未缓存输入 ${fmtTokens(snap.totals.uncachedInputTokens)} · 输出 ${fmtTokens(snap.totals.outputTokens)} · 缓存读 ${fmtTokens(snap.totals.cacheReadTokens)}`
}

/** 一行五格汇总卡。 */
function renderSummary(view: RequirementTokenView): string {
  const b: TokenBuckets = view.totals
  return `<div class="dsh-pm-stats">
      <div class="dsh-pm-stat" title="Σ 各节点：节点有快照用节点差值；节点无快照时用其任务执行差值兜底"><div class="dsh-pm-stat-label">总 Token</div><div class="dsh-pm-stat-value">${esc(fmtTokens(totalTokens(b)))}</div></div>
      <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">未缓存输入</div><div class="dsh-pm-stat-value">${esc(fmtTokens(b.uncachedInputTokens))}</div></div>
      <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">输出</div><div class="dsh-pm-stat-value">${esc(fmtTokens(b.outputTokens))}</div></div>
      <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">缓存读</div><div class="dsh-pm-stat-value">${esc(fmtTokens(b.cacheReadTokens))}</div></div>
      <div class="dsh-pm-stat"><div class="dsh-pm-stat-label">费用估算</div><div class="dsh-pm-stat-value">${esc(fmtCny(view.costEstimateCny))}</div></div>
    </div>`
}

function renderCallout(view: RequirementTokenView): string {
  const degraded = view.degraded
    ? ' 部分节点/执行无快照（人从看板点按钮推进或投影不可得），缺失段不计入合计。'
    : ''
  return `<div class="dsh-pm-callout">口径：按执行该节点/任务的会话累计值差值统计，可能含同会话其他工作的消耗；费用与字符折算 token 均为**估算**；缺失显示「无快照」，不补 0。${degraded}</div>`
}

/** 按流程节点表（含任务执行下钻）。 */
function renderStages(view: RequirementTokenView): string {
  const total = totalTokens(view.totals)
  const rows = view.byStage.map((row: RequirementTokenStageRow) => {
    const label = stageLabel(row.stage)
    if (row.buckets === undefined) {
      // 节点无快照（如功能上线前创建的需求）：节点行如实标「无快照」，
      // 但**任务执行下钻仍要渲染**——否则「有执行差值却被节点行吞掉」= 数据不可见。
      const hasSubNoSnap = row.executions.length > 0
      const subsNoSnap = row.executions.map((e: TokenExecutionRow) => `<tr class="dsh-pm-tok-sub" data-parent-stage="${esc(row.stage)}">`
        + `<td colspan="7" title="${esc(snapshotHint(e.start))} → ${esc(snapshotHint(e.end))}">${esc(e.taskId)} ${esc(e.title)}`
        + `<span class="dsh-pm-tok-sub-num">${e.delta !== undefined ? esc(fmtTokens(totalTokens(e.delta))) : '无快照'}</span></td></tr>`).join('')
      return `<tr class="dsh-pm-tok-node"${hasSubNoSnap ? ' data-action="toggle-token-node"' : ''} data-stage="${esc(row.stage)}">`
        + `<td>${esc(label)}${hasSubNoSnap ? ' <span class="dsh-pm-tok-more">▼ 点开</span>' : ''}</td>`
        + `<td class="dsh-pm-nosnap">无快照</td><td class="dsh-pm-nosnap">—</td><td class="dsh-pm-nosnap">—</td>`
        + `<td class="dsh-pm-nosnap">—</td><td class="dsh-pm-nosnap">—</td><td class="dsh-pm-nosnap">—</td></tr>` + subsNoSnap
    }
    const t = totalTokens(row.buckets)
    const pct = total > 0 ? Math.round((t / total) * 100) : 0
    const hasSub = row.executions.length > 0
    const head = `<tr class="dsh-pm-tok-node"${hasSub ? ' data-action="toggle-token-node"' : ''} data-stage="${esc(row.stage)}">`
      + `<td>${esc(label)}${hasSub ? ' <span class="dsh-pm-tok-more">▼ 点开</span>' : ''}</td>`
      + `<td>${esc(fmtTokens(t))}</td>`
      + `<td>${esc(fmtTokens(row.buckets.uncachedInputTokens))}</td>`
      + `<td>${esc(fmtTokens(row.buckets.outputTokens))}</td>`
      + `<td>${esc(fmtTokens(row.buckets.cacheReadTokens))}</td>`
      + `<td>${esc(fmtCny(undefined))}</td>`
      + `<td><span class="dsh-pm-bar"><i style="width:${pct}%"></i></span> ${pct}%</td></tr>`
    const subs = row.executions.map(e => `<tr class="dsh-pm-tok-sub" data-parent-stage="${esc(row.stage)}">`
      + `<td colspan="7" title="${esc(snapshotHint(e.start))} → ${esc(snapshotHint(e.end))}">${esc(e.taskId)} ${esc(e.title)}`
      + `<span class="dsh-pm-tok-sub-num">${e.delta !== undefined ? esc(fmtTokens(totalTokens(e.delta))) : '无快照'}</span></td></tr>`).join('')
    return head + subs
  }).join('')
  return `<details class="dsh-pm-fold" open>
      <summary>📊 按流程节点<span class="dsh-pm-fold-count">7 个节点 · 合计 ${esc(fmtTokens(total))}</span></summary>
      <div class="dsh-pm-fold-body">
        <table class="dsh-pm-tok-table">
          <thead><tr><th>节点</th><th>Token</th><th>未缓存输入</th><th>输出</th><th>缓存读</th><th>费用</th><th>占比</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
        <div class="dsh-pm-note">点节点行展开该阶段任务明细；「无快照」= 推进时未取到会话快照（如实标注，不补 0）。</div>
      </div>
    </details>`
}

/** 一段/一条提示词的二级折叠（可展开看具体内容）。 */
function renderPromptPart(part: PromptPartCost, title?: string): string {
  const head = title !== undefined ? esc(title) : esc(part.name)
  const meta = `${esc(String(part.chars))} 字符 · ${esc(fmtTokens(part.estTokens))}`
  const body = part.text !== undefined && part.text.length > 0
    ? `<pre class="dsh-pm-prompt-text">${esc(part.text)}</pre>`
    : '<div class="dsh-pm-note">（本条目不含正文）</div>'
  return `<details class="dsh-pm-prompt"><summary><span class="dsh-pm-prompt-name">${head}</span>`
    + `<span class="dsh-pm-prompt-meta">${meta}</span></summary>${body}</details>`
}

function renderSystemPrompt(cost: SystemPromptCost | undefined): string {
  if (cost === undefined || cost.source === 'unavailable') {
    return `<details class="dsh-pm-fold"><summary>🧱 固定系统提示词<span class="dsh-pm-fold-count">不可用</span></summary>`
      + `<div class="dsh-pm-fold-body"><div class="dsh-pm-empty">系统提示词装配服务不可得，未取到（不猜数字）。</div></div></details>`
  }
  const cumulative = cost.cumulativeEstTokens !== undefined
    ? `累计 ≈ ${esc(fmtTokens(cost.cumulativeEstTokens))}`
    : '累计：回合数不可得'
  const body = [...cost.sections, ...cost.contexts].map(p => renderPromptPart(p)).join('')
  const tools = cost.toolsChars > 0
    ? `<div class="dsh-pm-note">工具 schema 文字化成本：${esc(String(cost.toolsChars))} 字符 · ${esc(fmtTokens(Math.ceil(cost.toolsChars / 4)))}（估算）</div>`
    : ''
  return `<details class="dsh-pm-fold"><summary>🧱 固定系统提示词<span class="dsh-pm-fold-count">每回合 ≈ ${esc(fmtTokens(cost.perTurnEstTokens))}</span></summary>`
    + `<div class="dsh-pm-fold-body">`
    + `<div class="dsh-pm-sum"><span>本次装配：<b>${esc(String(cost.perTurnChars))}</b> 字符</span>`
    + `<span>每回合 ≈ <b>${esc(fmtTokens(cost.perTurnEstTokens))}</b> tokens</span>`
    + `<span>回合数：<b>${esc(String(cost.turns))}</b></span><span>${cumulative}</span>`
    + `<span>来源：systemPrompt.assemble（实时，估算）</span></div>`
    + `<div class="dsh-pm-note">点开每一段可看**具体提示词内容**（只读）。</div>${body}${tools}</div></details>`
}

function renderInjections(cost: InjectionCost | undefined): string {
  if (cost === undefined || cost.count === 0) {
    return `<details class="dsh-pm-fold"><summary>💉 注入提示词<span class="dsh-pm-fold-count">无记录</span></summary>`
      + `<div class="dsh-pm-fold-body"><div class="dsh-pm-empty">本需求窗口暂无注入留痕（或无可匹配窗口，不做张冠李戴的归因）。</div></div></details>`
  }
  const share = cost.sharePct !== undefined ? ` · 占本需求 ${esc(String(cost.sharePct))}%` : ''
  const bars = cost.byStage.map((s) => {
    const max = Math.max(...cost.byStage.map(x => x.estTokens), 1)
    const w = Math.round((s.estTokens / max) * 100)
    return `<div class="dsh-pm-impact-row"><span class="dsh-pm-impact-name">${esc(stageLabel(s.name))}</span>`
      + `<span class="dsh-pm-impact-bar"><i style="width:${w}%"></i></span>`
      + `<span class="dsh-pm-impact-val">${esc(fmtTokens(s.estTokens))}</span></div>`
  }).join('')
  const items = cost.items.map(it => `<details class="dsh-pm-prompt"><summary>`
    + `<span class="dsh-pm-prompt-name">${esc(fmtTime(it.at))} · ${esc(it.routeKey)}</span>`
    + `<span class="dsh-pm-prompt-meta">${esc(String(it.chars))} 字符 · ${esc(fmtTokens(it.estTokens))}</span></summary>`
    + `<div class="dsh-pm-note">命中片段：${esc(it.fragmentIds.join(', ')) || '—'}</div></details>`).join('')
  return `<details class="dsh-pm-fold"><summary>💉 注入提示词<span class="dsh-pm-fold-count">${esc(String(cost.count))} 次 · ${esc(fmtTokens(cost.estTokens))}（估算）${share}</span></summary>`
    + `<div class="dsh-pm-fold-body">`
    + `<div class="dsh-pm-sum"><span>注入次数：<b>${esc(String(cost.count))}</b></span>`
    + `<span>累计字符：<b>${esc(String(cost.chars))}</b></span>`
    + `<span>估算 Token：<b>${esc(fmtTokens(cost.estTokens))}</b></span>${share}</div>`
    + bars + '<div class="dsh-pm-note">明细（点开看每次注入的命中片段）：</div>' + items + '</div></details>'
}

/** 整块渲染。 */
export function renderTokenTab(view: RequirementTokenView): string {
  return renderSummary(view) + renderCallout(view) + renderStages(view)
    + renderSystemPrompt(view.systemPrompt) + renderInjections(view.injections)
}

/** 加载中 / 失败的空态（不报错、不留白）。 */
export function renderTokenPlaceholder(text: string): string {
  return `<div class="dsh-pm-empty">${esc(text)}</div>`
}
