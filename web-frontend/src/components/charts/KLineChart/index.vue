<template>
  <div ref="chartRef" class="kline-chart" :style="{ width: width, height: height }"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import type { KLineData, TradingSignal } from '@/types/models'
import { buildKLineChartOption } from './chart-options'

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

  const option = buildKLineChartOption({
    data: props.data,
    signals: props.signals,
    showVolume: props.showVolume
  })

  chartInstance.setOption(option, true)
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
