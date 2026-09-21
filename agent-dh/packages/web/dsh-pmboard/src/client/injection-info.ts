/**
 * 「本次注入了什么」只读信息块（REQ-422af1 t11，INV-6 的看板可见面）。
 *
 * 纯渲染：给定留痕条目返回 HTML 字符串，不取数、不写、不碰 DOM。
 * 字段与留痕**一一对应**（当前节点 / routeKey / 命中层级 / 片段数量 / 字符数 / 时间），
 * 不新增派生字段；无留痕时渲染「尚无记录」而不是空白或报错。
 *
 * 纪律：所有用户可见文本经 esc() 转义后拼进 HTML（注入文本里出现 `<script>` 也只当字面量）；
 * 用户可见文案用模板字符串表达（对齐本仓消息卫生门禁的"拼接式消息只降不升"棘轮）。
 *
 * @module dsh-pmboard/client/injection-info
 */
import { esc } from './html.js'
import { STATUS_LABELS, fmtTime } from './render/dom-utils.ts'

/** 一条注入留痕（= 服务端 InjectionLogEntry 的只读投影；客户端不 import host 模块）。 */
export interface InjectionInfoEntry {
  at: number
  windowKey: string
  stage: string
  difficulty: string
  category: string
  routeKey: string
  hitLevel: string
  fragmentIds: string[]
  charCount: number
  trimmed: string[]
}

/** 只读接口响应（/injection-log）。 */
export interface InjectionInfoResponse {
  entries: InjectionInfoEntry[]
  total: number
  available: boolean
  window: string | null
}

/**
 * 该需求是否值得回查注入留痕：无来源窗口（人工建卡）→ 没有"本次注入"可言，
 * 保持「尚无记录」空态，**不拿全量留痕冒充本需求的注入**（R-013 数据诚实）。
 */
export function hasInjectionWindow(sourceSessionId: string | undefined): boolean {
  return sourceSessionId !== undefined && sourceSessionId.length > 0
}

/** 节点中文名（与看板其余处同源：STATUS_LABELS）；未知 stage 原样显示，不编造。 */
function stageLabel(stage: string): string {
  return (STATUS_LABELS as Record<string, string>)[stage] ?? stage
}

/** 片段的只读投影（防脏数据把渲染打崩：非数组按空计）。 */
function fragmentIds(entry: InjectionInfoEntry): string[] {
  return Array.isArray(entry.fragmentIds) ? entry.fragmentIds : []
}

/** 单条留痕一行（六个字段各一个 span，data-* 供样式/测试选择）。 */
function renderRow(entry: InjectionInfoEntry): string {
  const ids = fragmentIds(entry)
  return `<div class="dsh-pm-injection-row" data-stage="${esc(entry.stage)}">
      <span class="dsh-pm-injection-node" title="当前节点">当前节点：${esc(stageLabel(entry.stage))}</span>
      <span class="dsh-pm-injection-route" title="routeKey">routeKey：${esc(entry.routeKey)}</span>
      <span class="dsh-pm-injection-hit" title="命中层级">命中层级：${esc(entry.hitLevel)}</span>
      <span class="dsh-pm-injection-frags" title="${esc(ids.join(', '))}">片段数量：${ids.length}</span>
      <span class="dsh-pm-injection-chars" title="字符数">字符数：${esc(entry.charCount)}</span>
      <span class="dsh-pm-injection-time" title="时间">时间：${esc(fmtTime(entry.at))}</span>
    </div>`
}

/**
 * 渲染只读信息块。entries 为写入顺序（旧→新，与服务端一致）；展示最近一条在最上面。
 * 空数组 → 「尚无记录」（明确的空态，不是空白、也不是错误）。
 */
export function renderInjectionInfo(entries: readonly InjectionInfoEntry[]): string {
  if (entries.length === 0) {
    return '<div class="dsh-pm-injection-info"><div class="dsh-pm-empty">尚无记录</div></div>'
  }
  const rows = entries.slice().reverse().map(renderRow).join('')
  return `<div class="dsh-pm-injection-info" data-count="${entries.length}">
      <div class="dsh-pm-injection-info-head">本次注入（最近 ${entries.length} 条）</div>
      ${rows}
    </div>`
}
