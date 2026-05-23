import { ref, onMounted, onUnmounted } from 'vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

/**
 * ECharts 图表组合式函数
 */
export function useChart(options?: {
  theme?: 'light' | 'dark'
  autoResize?: boolean
}) {
  const chartRef = ref<HTMLElement>()
  const chartInstance = ref<echarts.ECharts>()
  const loading = ref(false)

  // 初始化图表
  const initChart = () => {
    if (!chartRef.value) return

    chartInstance.value = echarts.init(chartRef.value, options?.theme || 'light')

    // 自动调整大小
    if (options?.autoResize !== false) {
      window.addEventListener('resize', handleResize)
    }
  }

  // 设置图表配置
  const setOption = (option: EChartsOption, notMerge = false) => {
    if (!chartInstance.value) return
    chartInstance.value.setOption(option, notMerge)
  }

  // 显示加载动画
  const showLoading = () => {
    loading.value = true
    chartInstance.value?.showLoading()
  }

  // 隐藏加载动画
  const hideLoading = () => {
    loading.value = false
    chartInstance.value?.hideLoading()
  }

  // 调整大小
  const resize = () => {
    chartInstance.value?.resize()
  }

  // 处理窗口大小变化
  const handleResize = () => {
    resize()
  }

  // 清空图表
  const clear = () => {
    chartInstance.value?.clear()
  }

  // 销毁图表
  const dispose = () => {
    if (chartInstance.value) {
      chartInstance.value.dispose()
      chartInstance.value = undefined
    }
    window.removeEventListener('resize', handleResize)
  }

  // 获取图表实例
  const getInstance = () => chartInstance.value

  onMounted(() => {
    initChart()
  })

  onUnmounted(() => {
    dispose()
  })

  return {
    chartRef,
    chartInstance,
    loading,
    initChart,
    setOption,
    showLoading,
    hideLoading,
    resize,
    clear,
    dispose,
    getInstance
  }
}

/**
 * K线图组合式函数
 */
export function useKLineChart() {
  const chart = useChart()

  // 设置K线图配置
  const setKLineOption = (data: any[]) => {
    const option: EChartsOption = {
      backgroundColor: '#131722',
      grid: {
        left: 60,
        right: 60,
        top: 40,
        bottom: 60
      },
      xAxis: {
        type: 'category',
        data: data.map(d => d.date),
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { color: '#787b86' }
      },
      yAxis: {
        type: 'value',
        position: 'right',
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { color: '#787b86' },
        splitLine: { lineStyle: { color: '#2a2e39' } }
      },
      series: [
        {
          name: 'K线',
          type: 'candlestick',
          data: data.map(d => [d.open, d.close, d.low, d.high]),
          itemStyle: {
            color: '#26a69a',
            color0: '#ef5350',
            borderColor: '#26a69a',
            borderColor0: '#ef5350'
          }
        }
      ],
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'cross' },
        backgroundColor: 'rgba(19, 23, 34, 0.9)',
        borderColor: '#2a2e39',
        textStyle: { color: '#d1d4dc' }
      }
    }

    chart.setOption(option)
  }

  return {
    ...chart,
    setKLineOption
  }
}
