import type { EChartsOption } from 'echarts'
import type { KLineData, TradingSignal } from '@/types/models'

const UP_COLOR = '#ef5350'
const DOWN_COLOR = '#26a69a'
const PANEL_BG = '#0f141d'
const GRID_LINE = 'rgba(143,156,179,0.16)'

interface BuildKLineChartOptionParams {
  data: KLineData[]
  signals: TradingSignal[]
  showVolume: boolean
}

export function calculateMovingAverage(data: KLineData[], dayCount: number): Array<number | null> {
  return data.map((_, index) => {
    if (index < dayCount - 1) return null
    const sum = data
      .slice(index - dayCount + 1, index + 1)
      .reduce((total, item) => total + item.close, 0)
    return Number((sum / dayCount).toFixed(2))
  })
}

function formatAmount(value: number): string {
  if (value >= 100000000) return `${(value / 100000000).toFixed(2)}亿`
  if (value >= 10000) return `${(value / 10000).toFixed(2)}万`
  return value.toFixed(0)
}

function pickVolumeValue(item: KLineData): number {
  return item.volume > 0 ? item.volume : item.amount
}

function volumeSeriesName(data: KLineData[]): string {
  return data.some(item => item.volume > 0) ? '成交量' : '成交额'
}

function signalDate(signal: TradingSignal): string {
  return (signal.createdAt || (signal as any).time || '').split(' ')[0]
}

function shortDate(date: string): string {
  if (date.includes(' ')) return date.slice(5, 16)
  return date.slice(5, 10)
}

function signalOrderLabel(signal: TradingSignal, order: number): string {
  return `${signal.type === 'buy' ? '买' : '卖'}${order}`
}

function buildSignalMarks(data: KLineData[], signals: TradingSignal[]) {
  const dates = data.map(item => item.date)
  let buyOrder = 0
  let sellOrder = 0

  return signals
    .map(signal => {
      const index = dates.indexOf(signalDate(signal))
      const price = signal.price ?? signal.triggerPrice
      if (index < 0 || typeof price !== 'number') return null

      const isBuy = signal.type === 'buy'
      const order = isBuy ? ++buyOrder : ++sellOrder
      const date = signalDate(signal)
      return {
        name: isBuy ? '买入' : '卖出',
        coord: [index, price],
        value: signalOrderLabel(signal, order),
        tradeDate: date,
        tradePrice: price,
        symbol: 'triangle',
        symbolSize: 18,
        symbolRotate: isBuy ? 0 : 180,
        itemStyle: { color: isBuy ? DOWN_COLOR : UP_COLOR },
        label: {
          show: true,
          formatter: (params: any) => {
            const marker = params.data ?? params
            return marker.value
          },
          position: isBuy ? 'bottom' : 'top',
          color: '#ffffff',
          fontSize: 10,
          fontWeight: 700,
          lineHeight: 13,
          backgroundColor: isBuy ? 'rgba(38, 166, 154, 0.92)' : 'rgba(239, 83, 80, 0.92)',
          borderRadius: 3,
          padding: [3, 5]
        }
      }
    })
    .filter(Boolean)
}

function buildHoldingBands(signals: TradingSignal[]) {
  const ordered = [...signals]
    .filter(signal => signalDate(signal))
    .sort((a, b) => signalDate(a).localeCompare(signalDate(b)))
  const bands = []
  let entryDate: string | null = null

  for (const signal of ordered) {
    if (signal.type === 'buy' && !entryDate) {
      entryDate = signalDate(signal)
    } else if (signal.type === 'sell' && entryDate) {
      bands.push([{ xAxis: entryDate }, { xAxis: signalDate(signal) }])
      entryDate = null
    }
  }

  return bands
}

function buildTradeReferenceLines(signals: TradingSignal[]) {
  let buyOrder = 0
  let sellOrder = 0

  return signals
    .filter(signal => signalDate(signal))
    .map(signal => {
      const isBuy = signal.type === 'buy'
      const order = isBuy ? ++buyOrder : ++sellOrder
      const label = signalOrderLabel(signal, order)
      const date = signalDate(signal)

      return {
        name: label,
        xAxis: date,
        lineStyle: {
          color: isBuy ? 'rgba(38, 166, 154, 0.46)' : 'rgba(239, 83, 80, 0.46)',
          width: 1,
          type: 'dashed'
        },
        label: {
          show: true,
          formatter: shortDate(date),
          color: '#dce5f4',
          fontSize: 10,
          lineHeight: 13,
          backgroundColor: 'rgba(15, 20, 29, 0.86)',
          borderRadius: 3,
          padding: [3, 5]
        }
      }
    })
}

export function buildKLineChartOption(params: BuildKLineChartOptionParams): EChartsOption {
  const { data, signals, showVolume } = params
  const dates = data.map(item => item.date)
  const klineData = data.map(item => [item.open, item.close, item.low, item.high])
  const volumeData = data.map(pickVolumeValue)
  const latest = data[data.length - 1]
  const volumeName = volumeSeriesName(data)
  const tradeReferenceLines = buildTradeReferenceLines(signals)
  const latestLine = latest
    ? {
        yAxis: latest.close,
        lineStyle: { color: '#7182a8', type: 'dashed', width: 1 },
        label: {
          color: '#dce5f4',
          backgroundColor: '#263147',
          borderRadius: 4,
          padding: [3, 7],
          formatter: '最新 {c}'
        }
      }
    : undefined

  return {
    backgroundColor: PANEL_BG,
    animation: false,
    color: ['#4f7cff', '#e5b454', '#7182a8'],
    legend: {
      show: false
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#8e9bb0', opacity: 0.65 },
        lineStyle: { color: '#738096', width: 1, type: 'dashed' },
        label: {
          color: '#f8fafc',
          backgroundColor: '#263147',
          borderColor: '#3b4a64',
          borderWidth: 1,
          padding: [4, 7]
        }
      },
      borderWidth: 1,
      borderColor: '#2f3b51',
      backgroundColor: 'rgba(15, 20, 29, 0.96)',
      padding: 12,
      textStyle: { color: '#dce5f4', fontSize: 12 },
      extraCssText: 'box-shadow:0 12px 32px rgba(0,0,0,.35);border-radius:7px;',
      formatter: (items: any) => {
        const dataIndex = items[0].dataIndex
        const item = data[dataIndex]
        const up = item.close >= item.open
        const tone = up ? UP_COLOR : DOWN_COLOR
        const change = item.close - item.open

        const matchedSignal = signals.find(signal => signalDate(signal) === item.date)
        const signalHtml = matchedSignal
          ? `<div style="margin-top:8px;padding-top:8px;border-top:1px solid #273142;color:${matchedSignal.type === 'buy' ? DOWN_COLOR : UP_COLOR};font-weight:700">${matchedSignal.type === 'buy' ? '买入信号' : '卖出信号'} ${(((matchedSignal as any).confidence ?? 0) * 100).toFixed(0)}%</div>`
          : ''

        return `
          <div style="min-width:190px">
            <div style="display:flex;justify-content:space-between;margin-bottom:8px">
              <b>${item.date}</b>
              <span style="color:${tone};font-weight:700">${change >= 0 ? '+' : ''}${change.toFixed(2)}</span>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px 14px">
              <span style="color:#8c99ad">开盘 <b style="color:#dce5f4">${item.open.toFixed(2)}</b></span>
              <span style="color:#8c99ad">收盘 <b style="color:${tone}">${item.close.toFixed(2)}</b></span>
              <span style="color:#8c99ad">最高 <b style="color:#ff7772">${item.high.toFixed(2)}</b></span>
              <span style="color:#8c99ad">最低 <b style="color:#42d8b2">${item.low.toFixed(2)}</b></span>
            </div>
            <div style="margin-top:8px;padding-top:8px;border-top:1px solid #273142;color:#8c99ad">
              ${volumeName} <b style="color:#dce5f4">${formatAmount(pickVolumeValue(item))}</b>
            </div>
            ${signalHtml}
          </div>
        `
      }
    },
    axisPointer: {
      link: [{ xAxisIndex: [0, 1] }]
    },
    grid: [
      {
        left: 18,
        right: 70,
        top: 18,
        height: showVolume ? '64%' : '78%'
      },
      {
        left: 18,
        right: 70,
        top: '74%',
        height: showVolume ? '15%' : 0
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#2b3648' } },
        axisTick: { show: false },
        axisLabel: {
          color: '#7d899d',
          margin: 12,
          hideOverlap: true,
          showMinLabel: true,
          showMaxLabel: true,
          formatter: (value: string) => value.slice(5)
        },
        splitLine: {
          show: true,
          lineStyle: { color: 'rgba(143,156,179,0.10)' }
        },
        min: 'dataMin',
        max: 'dataMax'
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: true,
        axisLine: { lineStyle: { color: '#2b3648' } },
        axisTick: { show: false },
        axisLabel: { color: '#7d899d', margin: 10, hideOverlap: true },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      }
    ],
    yAxis: [
      {
        scale: true,
        position: 'right',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#9aa7ba',
          formatter: (value: number) => Number(value).toFixed(2),
          margin: 12
        },
        splitLine: {
          show: true,
          lineStyle: { color: GRID_LINE }
        },
        splitArea: { show: false }
      },
      {
        scale: true,
        gridIndex: 1,
        position: 'right',
        splitNumber: 2,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: '#7d899d',
          formatter: (value: number) => formatAmount(value)
        },
        splitLine: {
          show: showVolume,
          lineStyle: { color: 'rgba(143,156,179,0.12)' }
        }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 0,
        end: 100,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true
      },
      {
        type: 'slider',
        xAxisIndex: [0, 1],
        bottom: 12,
        height: 28,
        start: 0,
        end: 100,
        borderColor: '#2b3648',
        backgroundColor: '#111927',
        fillerColor: 'rgba(79,124,255,0.22)',
        handleStyle: { color: '#d8e0ef', borderColor: '#d8e0ef' },
        moveHandleStyle: { color: '#4f7cff' },
        textStyle: { color: '#7d899d' },
        dataBackground: {
          lineStyle: { color: '#687794' },
          areaStyle: { color: '#263147' }
        },
        selectedDataBackground: {
          lineStyle: { color: '#9fb1d6' },
          areaStyle: { color: '#314264' }
        }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        barWidth: '58%',
        itemStyle: {
          color: UP_COLOR,
          color0: DOWN_COLOR,
          borderColor: '#ff6b66',
          borderColor0: '#35c8b7',
          borderWidth: 1.2
        },
        markPoint: {
          data: buildSignalMarks(data, signals)
        },
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(34, 197, 94, 0.08)' },
          data: buildHoldingBands(signals)
        },
        markLine: latest
          ? {
              symbol: 'none',
              silent: true,
              data: latestLine ? [...tradeReferenceLines, latestLine] : tradeReferenceLines
            }
          : undefined
      } as any,
      {
        name: 'MA5',
        type: 'line',
        data: calculateMovingAverage(data, 5),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.8, color: '#4f7cff' }
      },
      {
        name: 'MA10',
        type: 'line',
        data: calculateMovingAverage(data, 10),
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1.8, color: '#e5b454' }
      },
      {
        name: volumeName,
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumeData,
        barWidth: '58%',
        itemStyle: {
          color: (chartParams: any) => {
            const item = data[chartParams.dataIndex]
            return item.close >= item.open ? 'rgba(239,83,80,0.58)' : 'rgba(38,166,154,0.58)'
          }
        }
      }
    ]
  }
}
