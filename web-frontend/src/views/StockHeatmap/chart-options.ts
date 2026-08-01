/** 热力图 treemap option 构建（纯函数，spec §5.2 视觉编码） */
import type { EChartsOption } from 'echarts'
import type { HeatmapIndustry, HeatmapResponse, HeatmapStock } from '@/types'
import { judgePoolEvent, judgeSignal } from './verdict'

export interface HeatmapOverlays {
  signals: boolean
  pool: boolean
  industry: boolean
}

export interface BuildHeatmapOptionParams {
  data: HeatmapResponse
  overlays: HeatmapOverlays
}

const STANCE_BORDER: Record<string, string> = {
  bullish: '#d4a017',   // 金框 = 看好
  bearish: '#888888',   // 灰框 = 回避
  neutral: '#555555',
}

/** 红涨绿跌发散色（±10% 封顶取深浅）；池外股票低饱和灰化 */
export function changeColor(pct: number, inScope = true): string {
  const t = Math.min(Math.abs(pct), 10) / 10
  if (!inScope) {
    return pct >= 0 ? 'rgba(192, 57, 43, 0.18)' : 'rgba(39, 174, 96, 0.18)'
  }
  const alpha = 0.3 + 0.7 * t
  return pct >= 0 ? `rgba(192, 57, 43, ${alpha})` : `rgba(39, 174, 96, ${alpha})`
}

function latestSignal(stock: HeatmapStock) {
  return stock.signals?.length ? stock.signals[stock.signals.length - 1] : undefined
}

function stockLabel(stock: HeatmapStock, overlays: HeatmapOverlays): string {
  let label = `${stock.name}\n${stock.changePct > 0 ? '+' : ''}${stock.changePct}%`
  if (!stock.inScope) return label
  if (overlays.signals) {
    const sig = latestSignal(stock)
    if (sig) label += sig.type === 'buy' ? ' ▲' : ' ▼'
  }
  if (overlays.pool && stock.poolEvents?.length) {
    label += stock.poolEvents[stock.poolEvents.length - 1].action === 'add' ? ' ●' : ' ○'
  }
  return label
}

function buildStockNode(stock: HeatmapStock, overlays: HeatmapOverlays) {
  const sig = overlays.signals && stock.inScope ? latestSignal(stock) : undefined
  const sigVerdict = sig ? judgeSignal(sig.type, stock.changePct) : 'none'
  const poolVerdict = overlays.pool && stock.poolEvents?.length
    ? judgePoolEvent(stock.poolEvents[stock.poolEvents.length - 1].action, stock.changePct)
    : 'none'
  return {
    name: stockLabel(stock, overlays),
    value: Math.max(stock.marketCap, 1),
    symbol: stock.symbol,
    raw: stock,
    verdicts: { signal: sigVerdict, pool: poolVerdict },
    itemStyle: {
      color: changeColor(stock.changePct, stock.inScope),
      borderColor: sigVerdict === 'right' || poolVerdict === 'right'
        ? '#ffffff'
        : sigVerdict === 'wrong' || poolVerdict === 'wrong'
          ? '#111111'
          : 'rgba(255,255,255,0.4)',
      borderWidth: stock.inScope && (sig || stock.poolEvents?.length) ? 3 : 1,
    },
  }
}

function buildIndustryNode(ind: HeatmapIndustry, overlays: HeatmapOverlays) {
  return {
    name: `${ind.name} ${ind.changePct > 0 ? '+' : ''}${ind.changePct}%`,
    value: ind.stocks.reduce((sum, s) => sum + Math.max(s.marketCap, 1), 0),
    itemStyle: {
      borderColor: overlays.industry ? STANCE_BORDER[ind.agentStance] : '#555555',
      borderWidth: overlays.industry && ind.agentStance !== 'neutral' ? 3 : 1,
      gapWidth: 2,
    },
    children: ind.stocks.map((s) => buildStockNode(s, overlays)),
  }
}

export function buildHeatmapOption({ data, overlays }: BuildHeatmapOptionParams): EChartsOption {
  return {
    animation: false,
    tooltip: {
      formatter: (info: any) => {
        const stock = info?.data?.raw as HeatmapStock | undefined
        if (!stock) return String(info?.name ?? '')
        const lines = [
          `<b>${stock.name} (${stock.symbol})</b>`,
          `验证窗涨跌: ${stock.changePct > 0 ? '+' : ''}${stock.changePct}%`,
          `市值: ${(stock.marketCap / 1e8).toFixed(1)} 亿`,
        ]
        if (stock.startDate && stock.endDate) {
          lines.push(`计算区间: ${stock.startDate} → ${stock.endDate}`)
        }
        if (stock.inScope) {
          stock.signals?.forEach((s) =>
            lines.push(`信号: ${s.type === 'buy' ? '买入' : '卖出'} @ ${s.date} (${s.strategy ?? '-'}) → ${judgeSignal(s.type, stock.changePct) === 'right' ? '✅对' : judgeSignal(s.type, stock.changePct) === 'wrong' ? '❌错' : '—'}`))
          stock.poolEvents?.forEach((e) =>
            lines.push(`池事件: ${e.action === 'add' ? '调入' : '调出'}「${e.pool}」@ ${e.date} → ${judgePoolEvent(e.action, stock.changePct) === 'right' ? '✅对' : judgePoolEvent(e.action, stock.changePct) === 'wrong' ? '❌错' : '—'}`))
        } else {
          lines.push('<i>池外参照</i>')
        }
        return lines.join('<br/>')
      },
    },
    series: [{
      type: 'treemap',
      roam: false,
      nodeClick: false,
      breadcrumb: { show: false },
      width: '100%',
      height: '100%',
      label: { show: true, fontSize: 11, color: '#fff' },
      upperLabel: { show: true, height: 22, color: '#333', fontWeight: 'bold' },
      data: data.industries.map((ind) => buildIndustryNode(ind, overlays)),
    }],
  }
}
