<template>
  <div ref="chartRef" class="kline-chart" :style="{ width: width, height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import type { KLineData, TradingSignal } from '@/types/models'

interface Props {
  data: KLineData[]
  signals?: TradingSignal[]
  width?: string
  height?: string
  showVolume?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  signals: () => [],
  width: '100%',
  height: '500px',
  showVolume: true
})

const chartRef = ref<HTMLDivElement>()
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value)
  updateChart()
}

const updateChart = () => {
  if (!chartInstance || !props.data.length) return

  const dates = props.data.map(item => item.date)
  const klineData = props.data.map(item => [item.open, item.close, item.low, item.high])
  const volumes = props.data.map(item => item.volume)

  // 处理买卖信号标记
  const buySignals = props.signals
    .filter(s => s.type === 'buy')
    .map(s => {
      const index = dates.indexOf(s.createdAt.split(' ')[0])
      return {
        name: 'buy',
        coord: [index, s.price],
        value: s.confidence.toFixed(2),
        symbol: 'arrow',
        symbolSize: 15,
        symbolRotate: 0,
        itemStyle: { color: '#52c41a' },
        label: {
          show: true,
          formatter: `买入\n{c}`,
          position: 'bottom' as const,
          color: '#52c41a',
          fontSize: 12
        }
      }
    })

  const sellSignals = props.signals
    .filter(s => s.type === 'sell')
    .map(s => {
      const index = dates.indexOf(s.createdAt.split(' ')[0])
      return {
        name: 'sell',
        coord: [index, s.price],
        value: s.confidence.toFixed(2),
        symbol: 'arrow',
        symbolSize: 15,
        symbolRotate: 180,
        itemStyle: { color: '#f5222d' },
        label: {
          show: true,
          formatter: `卖出\n{c}`,
          position: 'top' as const,
          color: '#f5222d',
          fontSize: 12
        }
      }
    })

  const option: EChartsOption = {
    animation: false,
    legend: {
      bottom: 10,
      left: 'center',
      data: ['K线', '成交量']
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      borderWidth: 1,
      borderColor: '#ccc',
      padding: 10,
      textStyle: {
        color: '#000'
      },
      formatter: (params: any) => {
        const dataIndex = params[0].dataIndex
        const kline = props.data[dataIndex]
        const signal = props.signals.find(s => s.createdAt.split(' ')[0] === kline.date)

        let html = `
          <div style="font-size: 14px;">
            <div style="margin-bottom: 8px; font-weight: bold;">${kline.date}</div>
            <div>开盘: ${kline.open.toFixed(2)}</div>
            <div>收盘: ${kline.close.toFixed(2)}</div>
            <div>最高: ${kline.high.toFixed(2)}</div>
            <div>最低: ${kline.low.toFixed(2)}</div>
            <div>成交量: ${(kline.volume / 10000).toFixed(2)}万</div>
        `

        if (signal) {
          html += `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid #eee;">
              <div style="color: ${signal.type === 'buy' ? '#52c41a' : '#f5222d'}; font-weight: bold;">
                ${signal.type === 'buy' ? '买入信号' : '卖出信号'}
              </div>
              <div>置信度: ${(signal.confidence * 100).toFixed(1)}%</div>
              <div>价格: ${signal.price.toFixed(2)}</div>
              ${signal.reasons.length > 0 ? `<div style="margin-top: 4px;">原因:</div>` : ''}
              ${signal.reasons.map((r: string) => `<div style="margin-left: 8px;">• ${r}</div>`).join('')}
            </div>
          `
        }

        html += '</div>'
        return html
      }
    },
    axisPointer: {
      link: [{ xAxisIndex: 'all' }],
      label: {
        backgroundColor: '#777'
      }
    },
    grid: [
      {
        left: '10%',
        right: '8%',
        top: '5%',
        height: props.showVolume ? '50%' : '70%'
      },
      {
        left: '10%',
        right: '8%',
        top: '65%',
        height: '16%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
        axisPointer: {
          z: 100
        }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true
        }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 80,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        top: '85%',
        start: 80,
        end: 100
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a'
        },
        markPoint: {
          data: [...buySignals, ...sellSignals]
        }
      } as any,
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: (params: any) => {
            const dataIndex = params.dataIndex
            const kline = props.data[dataIndex]
            return kline.close >= kline.open ? '#ef5350' : '#26a69a'
          }
        }
      }
    ]
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => [props.data, props.signals], () => {
  nextTick(() => {
    updateChart()
  })
}, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
})
</script>

<style scoped>
.kline-chart {
  width: 100%;
  height: 100%;
}
</style>
