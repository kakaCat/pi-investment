<template>
  <div ref="chartRef" class="preview-chart" />
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import type { KlineData } from '@/types/indicator'

const props = defineProps<{
  klineData: KlineData[]
  indicatorSeries?: Record<string, (number | null)[]>
  signalSeries?: {
    buy?: (boolean | number | null)[]
    sell?: (boolean | number | null)[]
  }
  latestSignal?: 'buy' | 'sell'
  compact?: boolean
}>()

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

const formatChartDate = (value: string) => {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 10)
}

const dates = computed(() => props.klineData.map(k => formatChartDate(k.date)))

const visibleIndicatorSeries = computed(() => {
  const entries = Object.entries(props.indicatorSeries || {})
    .filter(([name]) => !['buy', 'sell'].includes(name.toLowerCase()))
  const preferredNames = ['close', 'ma_short', 'ma_long', 'ma5', 'ma10', 'ma20', 'dif', 'dea', 'macd']
  const preferred = entries.filter(([name]) => preferredNames.some(key => name.toLowerCase().includes(key)))
  return (preferred.length > 0 ? preferred : entries).slice(0, props.compact ? 2 : 4)
})

const buildOption = (): EChartsOption => {
  const ohlc = props.klineData.map(k => [k.open, k.close, k.low, k.high])
  const volumes = props.klineData.map(k => k.volume)
  const indicatorLines = visibleIndicatorSeries.value.map(([name, values]) => ({
    name,
    type: 'line' as const,
    data: values,
    smooth: true,
    lineStyle: { width: props.compact ? 1.5 : 2 },
    showSymbol: false,
    xAxisIndex: 0,
    yAxisIndex: 0
  }))
  const signalMarkers = buildSignalMarkers()
  const signalLegendNames = ['买入标记', '卖出标记']
  const legendData = props.compact
    ? signalLegendNames
    : ['K线', ...indicatorLines.map(line => line.name), ...signalLegendNames]
  const signalLegendSeries = [
    {
      name: '买入标记',
      type: 'scatter' as const,
      data: [],
      symbol: 'triangle',
      symbolSize: props.compact ? 9 : 12,
      xAxisIndex: 0,
      yAxisIndex: 0,
      itemStyle: { color: '#22c55e' },
      tooltip: { show: false },
      silent: true
    },
    {
      name: '卖出标记',
      type: 'scatter' as const,
      data: [],
      symbol: 'triangle',
      symbolRotate: 180,
      symbolSize: props.compact ? 9 : 12,
      xAxisIndex: 0,
      yAxisIndex: 0,
      itemStyle: { color: '#ef4444' },
      tooltip: { show: false },
      silent: true
    }
  ]

  return {
    backgroundColor: '#0a0a0f',
    animation: false,
    legend: {
      show: !props.compact || indicatorLines.length <= 2,
      data: legendData,
      top: props.compact ? 6 : 10,
      left: props.compact ? 8 : 16,
      textStyle: { color: '#cbd5e1', fontSize: props.compact ? 10 : 12 },
      itemWidth: props.compact ? 12 : 18,
      itemHeight: 8
    },
    grid: [
      {
        left: props.compact ? 42 : 64,
        right: props.compact ? 16 : 32,
        top: props.compact ? 34 : 48,
        bottom: props.compact ? 48 : 88,
        height: props.compact ? '58%' : '62%'
      },
      {
        left: props.compact ? 42 : 64,
        right: props.compact ? 16 : 32,
        top: props.compact ? '76%' : '78%',
        bottom: props.compact ? 20 : 34,
        height: props.compact ? '14%' : '12%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates.value,
        gridIndex: 0,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { show: false },
        splitLine: { show: false }
      },
      {
        type: 'category',
        data: dates.value,
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: {
          color: '#787b86',
          fontSize: props.compact ? 9 : 11,
          rotate: props.compact ? 25 : 0
        },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { color: '#787b86', fontSize: props.compact ? 9 : 11 },
        splitLine: { lineStyle: { color: '#1e293b', opacity: 0.35 } }
      },
      {
        type: 'value',
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { show: false },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e'
        },
        markPoint: {
          symbolSize: props.compact ? 28 : 36,
          label: {
            show: !props.compact,
            color: '#ffffff',
            fontSize: 11
          },
          data: signalMarkers
        }
      },
      ...signalLegendSeries,
      ...indicatorLines,
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex
            return ohlc[idx]?.[1] >= ohlc[idx]?.[0] ? '#ef4444' : '#22c55e'
          }
        }
      }
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(19, 23, 34, 0.95)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc' }
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 0,
        end: 100
      }
    ]
  }
}

const isSignalOn = (value: boolean | number | null | undefined) => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value !== 0
  return false
}

type SignalMarker = {
  name: string
  coord: [string, number]
  value: string
  symbol: string
  symbolRotate: number
  symbolOffset: [number, number]
  itemStyle: { color: string }
}

const buildSignalMarkers = () => {
  const markers: SignalMarker[] = []

  props.klineData.forEach((kline, index) => {
    const date = dates.value[index]

    if (isSignalOn(props.signalSeries?.buy?.[index])) {
      markers.push({
        name: '买入',
        coord: [date, kline.low],
        value: '买',
        symbol: 'triangle',
        symbolRotate: 0,
        symbolOffset: [0, props.compact ? 10 : 14],
        itemStyle: { color: '#22c55e' }
      })
    }

    if (isSignalOn(props.signalSeries?.sell?.[index])) {
      markers.push({
        name: '卖出',
        coord: [date, kline.high],
        value: '卖',
        symbol: 'triangle',
        symbolRotate: 180,
        symbolOffset: [0, props.compact ? -10 : -14],
        itemStyle: { color: '#ef4444' }
      })
    }
  })

  if (markers.length === 0 && props.latestSignal && props.klineData.length > 0) {
    const lastIndex = props.klineData.length - 1
    const latestKline = props.klineData[lastIndex]
    const isBuy = props.latestSignal === 'buy'

    markers.push({
      name: isBuy ? '买入' : '卖出',
      coord: [dates.value[lastIndex], isBuy ? latestKline.low : latestKline.high],
      value: isBuy ? '买' : '卖',
      symbol: 'triangle',
      symbolRotate: isBuy ? 0 : 180,
      symbolOffset: [0, isBuy ? (props.compact ? 10 : 14) : (props.compact ? -10 : -14)],
      itemStyle: { color: isBuy ? '#22c55e' : '#ef4444' }
    })
  }

  return markers
}

const render = () => {
  if (!chartRef.value) return
  if (chartRef.value.clientWidth === 0 || chartRef.value.clientHeight === 0) {
    window.setTimeout(render, 80)
    return
  }
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value, 'dark')
  }
  chartInstance.setOption(buildOption(), true)
}

const resize = () => chartInstance?.resize()

onMounted(() => {
  render()
  requestAnimationFrame(() => resize())
  window.setTimeout(resize, 120)
  window.addEventListener('resize', resize)
})

watch(() => [props.klineData, props.indicatorSeries, props.signalSeries, props.latestSignal, props.compact], render, { deep: true })

onUnmounted(() => {
  window.removeEventListener('resize', resize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>
