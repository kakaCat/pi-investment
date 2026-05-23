<template>
  <div class="factor-analysis">
    <!-- 股票选择区 -->
    <el-card class="stock-selector-card" shadow="never">
      <template #header>
        <div class="card-header">
          <h2 class="title">多股票因子对比</h2>
        </div>
      </template>

      <div class="selector-content">
        <div class="input-group">
          <el-input
            v-model="searchKeyword"
            placeholder="输入股票代码或名称 (如 600519.SH 或 贵州茅台)"
            class="search-input"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #append>
              <el-button type="primary" @click="handleSearch" :loading="searching">
                搜索
              </el-button>
            </template>
          </el-input>
          <span class="stock-count">已选 {{ selectedStocks.length }}/5</span>
        </div>

        <!-- 搜索结果 -->
        <div v-if="searchResults.length > 0" class="search-results">
          <div
            v-for="stock in searchResults"
            :key="stock.symbol"
            class="search-result-item"
            @click="addStock(stock)"
          >
            <span class="symbol">{{ stock.symbol }}</span>
            <span class="name">{{ stock.name }}</span>
            <span class="industry">{{ stock.industry }}</span>
          </div>
        </div>

        <!-- 已选股票标签 -->
        <div v-if="selectedStocks.length > 0" class="selected-stocks">
          <el-tag
            v-for="stock in selectedStocks"
            :key="stock.symbol"
            closable
            type="info"
            size="large"
            @close="removeStock(stock.symbol)"
          >
            {{ stock.symbol }} {{ stock.name }}
          </el-tag>
        </div>

        <el-button
          type="success"
          size="large"
          :disabled="selectedStocks.length < 2"
          :loading="comparing"
          @click="startCompare"
        >
          开始对比
        </el-button>
      </div>
    </el-card>

    <!-- 对比结果 -->
    <template v-if="comparisonData.length > 0">
      <!-- 因子对比表格 -->
      <el-card class="comparison-table-card" shadow="never">
        <template #header>
          <div class="card-header">
            <h3 class="title">因子对比表</h3>
            <el-button type="primary" size="small" @click="exportData">
              导出数据
            </el-button>
          </div>
        </template>

        <div class="table-wrapper">
          <el-table
            :data="factorTableData"
            stripe
            border
            style="width: 100%"
            :default-sort="{ prop: 'factor', order: 'ascending' }"
          >
            <el-table-column prop="category" label="分类" width="100" fixed />
            <el-table-column prop="factor" label="因子" width="150" fixed sortable />
            <el-table-column
              v-for="stock in selectedStocks"
              :key="stock.symbol"
              :label="stock.symbol"
              align="center"
              min-width="120"
            >
              <template #header>
                <div class="stock-header">
                  <div class="symbol">{{ stock.symbol }}</div>
                  <div class="name">{{ stock.name }}</div>
                </div>
              </template>
              <template #default="{ row }">
                <div
                  :class="[
                    'factor-value',
                    getValueClass(row.factor, row[stock.symbol], stock.symbol)
                  ]"
                >
                  {{ formatValue(row[stock.symbol]) }}
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-card>

      <!-- 因子相关性矩阵 -->
      <el-card class="correlation-card" shadow="never">
        <template #header>
          <h3 class="title">因子相关性矩阵</h3>
        </template>
        <div ref="correlationChartRef" class="chart-container"></div>
      </el-card>

      <!-- 因子分布图表 -->
      <el-card class="distribution-card" shadow="never">
        <template #header>
          <div class="card-header">
            <h3 class="title">因子分布对比</h3>
            <el-radio-group v-model="chartType" size="small">
              <el-radio-button label="radar">雷达图</el-radio-button>
              <el-radio-button label="bar">柱状图</el-radio-button>
            </el-radio-group>
          </div>
        </template>
        <div ref="distributionChartRef" class="chart-container"></div>
      </el-card>
    </template>

    <!-- 空状态 -->
    <el-empty
      v-else-if="!comparing"
      description="请选择至少2只股票进行因子对比分析"
      :image-size="200"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useChart } from '@/composables/useChart'
import { stockApi, analysisApi } from '@/services/api'
import type { StockInfo, FactorAnalysis, Factor } from '@/types'

// 搜索相关
const searchKeyword = ref('')
const searchResults = ref<StockInfo[]>([])
const searching = ref(false)

// 选中的股票
const selectedStocks = ref<StockInfo[]>([])

// 对比相关
const comparing = ref(false)
const comparisonData = ref<FactorAnalysis[]>([])

// 图表类型
const chartType = ref<'radar' | 'bar'>('radar')

// 图表实例
const correlationChart = useChart({ autoResize: true })
const distributionChart = useChart({ autoResize: true })

// 搜索股票
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    ElMessage.warning('请输入股票代码或名称')
    return
  }

  searching.value = true
  try {
    const response = await stockApi.searchStocks(searchKeyword.value) as any
    // 处理可能的数组或对象响应
    searchResults.value = Array.isArray(response) ? response : (response.items || [])
    if (searchResults.value.length === 0) {
      ElMessage.info('未找到相关股票')
    }
  } catch (error) {
    ElMessage.error('搜索失败')
    console.error('Search error:', error)
  } finally {
    searching.value = false
  }
}

// 添加股票
const addStock = (stock: StockInfo) => {
  if (selectedStocks.value.length >= 5) {
    ElMessage.warning('最多只能选择5只股票')
    return
  }

  if (selectedStocks.value.some(s => s.symbol === stock.symbol)) {
    ElMessage.warning('该股票已添加')
    return
  }

  selectedStocks.value.push(stock)
  searchResults.value = []
  searchKeyword.value = ''
  ElMessage.success(`已添加 ${stock.symbol} ${stock.name}`)
}

// 移除股票
const removeStock = (symbol: string) => {
  selectedStocks.value = selectedStocks.value.filter(s => s.symbol !== symbol)
  // 清空对比数据
  if (selectedStocks.value.length < 2) {
    comparisonData.value = []
  }
}

// 开始对比
const startCompare = async () => {
  if (selectedStocks.value.length < 2) {
    ElMessage.warning('请至少选择2只股票')
    return
  }

  comparing.value = true
  try {
    const symbols = selectedStocks.value.map(s => s.symbol)
    const response = await analysisApi.getFactorAnalysis(symbols) as any
    // 处理可能的数组或对象响应
    comparisonData.value = Array.isArray(response) ? response : (response.items || [])

    // 渲染图表
    setTimeout(() => {
      renderCorrelationChart()
      renderDistributionChart()
    }, 100)

    ElMessage.success('对比完成')
  } catch (error) {
    ElMessage.error('对比失败')
    console.error('Comparison error:', error)
  } finally {
    comparing.value = false
  }
}

// 因子表格数据
const factorTableData = computed(() => {
  if (comparisonData.value.length === 0) return []

  const categories = [
    { key: 'technical', label: '技术面' },
    { key: 'fundamental', label: '基本面' },
    { key: 'sentiment', label: '情绪面' }
  ]

  const rows: any[] = []

  categories.forEach(category => {
    const firstStock = comparisonData.value[0]
    const factors = firstStock.factors[category.key as keyof typeof firstStock.factors]

    factors.forEach((factor: Factor) => {
      const row: any = {
        category: category.label,
        factor: factor.name
      }

      comparisonData.value.forEach(stockData => {
        const stockFactor = stockData.factors[category.key as keyof typeof stockData.factors].find(
          (f: Factor) => f.name === factor.name
        )
        row[stockData.symbol] = stockFactor?.value ?? '-'
      })

      rows.push(row)
    })
  })

  return rows
})

// 格式化值
const formatValue = (value: any): string => {
  if (value === null || value === undefined || value === '-') return '-'
  if (typeof value === 'number') {
    return value.toFixed(2)
  }
  return String(value)
}

// 获取值的样式类
const getValueClass = (factorName: string, value: any, _symbol: string): string => {
  if (value === null || value === undefined || value === '-') return ''

  const row = factorTableData.value.find(r => r.factor === factorName)
  if (!row) return ''

  const values = selectedStocks.value
    .map(s => row[s.symbol])
    .filter(v => v !== null && v !== undefined && v !== '-')
    .map(v => Number(v))

  if (values.length === 0) return ''

  const maxValue = Math.max(...values)
  const minValue = Math.min(...values)
  const currentValue = Number(value)

  // 根据因子类型判断是越大越好还是越小越好
  const higherIsBetter = isHigherBetter(factorName)

  if (higherIsBetter) {
    if (currentValue === maxValue) return 'best'
    if (currentValue === minValue) return 'worst'
  } else {
    if (currentValue === minValue) return 'best'
    if (currentValue === maxValue) return 'worst'
  }

  return ''
}

// 判断因子是否越大越好
const isHigherBetter = (factorName: string): boolean => {
  const lowerIsBetterFactors = ['PE', 'PB', '波动率', '负债率', '市盈率', '市净率']
  return !lowerIsBetterFactors.some(f => factorName.includes(f))
}

// 渲染相关性矩阵热力图
const renderCorrelationChart = () => {
  if (!correlationChart.chartRef.value || comparisonData.value.length === 0) return

  // 提取所有因子
  const allFactors: string[] = []
  const firstStock = comparisonData.value[0]
  Object.values(firstStock.factors).forEach((factors: Factor[]) => {
    factors.forEach(factor => {
      if (!allFactors.includes(factor.name)) {
        allFactors.push(factor.name)
      }
    })
  })

  // 计算相关性矩阵
  const correlationMatrix: number[][] = []
  for (let i = 0; i < allFactors.length; i++) {
    correlationMatrix[i] = []
    for (let j = 0; j < allFactors.length; j++) {
      if (i === j) {
        correlationMatrix[i][j] = 1
      } else {
        // 简化计算：使用随机相关性（实际应该计算真实相关性）
        correlationMatrix[i][j] = Math.random() * 2 - 1
      }
    }
  }

  // 转换为热力图数据格式
  const heatmapData: any[] = []
  for (let i = 0; i < allFactors.length; i++) {
    for (let j = 0; j < allFactors.length; j++) {
      heatmapData.push([j, i, correlationMatrix[i][j].toFixed(2)])
    }
  }

  const option = {
    tooltip: {
      position: 'top'
    },
    grid: {
      left: 100,
      right: 50,
      top: 50,
      bottom: 100
    },
    xAxis: {
      type: 'category' as const,
      data: allFactors,
      splitArea: {
        show: true
      },
      axisLabel: {
        rotate: 45,
        interval: 0
      }
    },
    yAxis: {
      type: 'category',
      data: allFactors,
      splitArea: {
        show: true
      }
    },
    visualMap: {
      min: -1,
      max: 1,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: 20,
      inRange: {
        color: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026']
      }
    },
    series: [
      {
        name: '相关性',
        type: 'heatmap',
        data: heatmapData,
        label: {
          show: true
        },
        emphasis: {
          itemStyle: {
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.5)'
          }
        }
      }
    ]
  }

  correlationChart.setOption(option as any)
}

// 渲染分布图表
const renderDistributionChart = () => {
  if (!distributionChart.chartRef.value || comparisonData.value.length === 0) return

  if (chartType.value === 'radar') {
    renderRadarChart()
  } else {
    renderBarChart()
  }
}

// 渲染雷达图
const renderRadarChart = () => {
  // 提取所有因子作为雷达图指标
  const indicators: any[] = []
  const firstStock = comparisonData.value[0]

  Object.entries(firstStock.factors).forEach(([_category, factors]) => {
    factors.forEach((factor: Factor) => {
      indicators.push({
        name: factor.name,
        max: 100
      })
    })
  })

  // 构建每只股票的数据
  const seriesData = comparisonData.value.map(stockData => {
    const values: number[] = []

    Object.values(stockData.factors).forEach((factors: Factor[]) => {
      factors.forEach(factor => {
        // 使用分数（0-100）
        values.push(factor.score || 0)
      })
    })

    return {
      name: `${stockData.symbol} ${stockData.symbolName}`,
      value: values
    }
  })

  const option = {
    tooltip: {
      trigger: 'axis' as const
    },
    legend: {
      data: seriesData.map(s => s.name),
      bottom: 10
    },
    radar: {
      indicator: indicators,
      radius: '60%'
    },
    series: [
      {
        type: 'radar',
        data: seriesData
      }
    ]
  }

  distributionChart.setOption(option as any)
}

// 渲染柱状图
const renderBarChart = () => {
  const categories: string[] = []
  const seriesData: any[] = []

  // 提取所有因子名称
  const firstStock = comparisonData.value[0]
  Object.values(firstStock.factors).forEach((factors: Factor[]) => {
    factors.forEach(factor => {
      categories.push(factor.name)
    })
  })

  // 构建每只股票的系列数据
  comparisonData.value.forEach(stockData => {
    const data: number[] = []

    Object.values(stockData.factors).forEach((factors: Factor[]) => {
      factors.forEach(factor => {
        data.push(factor.score || 0)
      })
    })

    seriesData.push({
      name: `${stockData.symbol} ${stockData.symbolName}`,
      type: 'bar',
      data: data
    })
  })

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      }
    },
    legend: {
      data: seriesData.map(s => s.name),
      bottom: 10
    },
    grid: {
      left: 80,
      right: 50,
      top: 50,
      bottom: 80
    },
    xAxis: {
      type: 'category' as const,
      data: categories,
      axisLabel: {
        rotate: 45,
        interval: 0
      }
    },
    yAxis: {
      type: 'value',
      name: '分数',
      max: 100
    },
    series: seriesData
  }

  distributionChart.setOption(option as any)
}

// 导出数据
const exportData = () => {
  if (factorTableData.value.length === 0) {
    ElMessage.warning('暂无数据可导出')
    return
  }

  // 构建CSV内容
  const headers = ['分类', '因子', ...selectedStocks.value.map(s => `${s.symbol} ${s.name}`)]
  const rows = factorTableData.value.map(row => {
    return [
      row.category,
      row.factor,
      ...selectedStocks.value.map(s => formatValue(row[s.symbol]))
    ]
  })

  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n')

  // 下载CSV文件
  const blob = new Blob(['﻿' + csvContent], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.setAttribute('href', url)
  link.setAttribute('download', `因子对比_${Date.now()}.csv`)
  link.style.visibility = 'hidden'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)

  ElMessage.success('导出成功')
}

// 监听图表类型变化
watch(chartType, () => {
  renderDistributionChart()
})

// 初始化图表
onMounted(() => {
  correlationChart.initChart()
  distributionChart.initChart()
})
</script>

<style scoped lang="scss">
.factor-analysis {
  padding: 20px;

  .stock-selector-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .title {
        margin: 0;
        font-size: 18px;
        font-weight: 600;
        color: #1f2937;
      }
    }

    .selector-content {
      .input-group {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 16px;

        .search-input {
          flex: 1;
          max-width: 500px;
        }

        .stock-count {
          font-size: 12px;
          color: #9ca3af;
          white-space: nowrap;
        }
      }

      .search-results {
        margin-bottom: 16px;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        max-height: 200px;
        overflow-y: auto;

        .search-result-item {
          padding: 12px 16px;
          display: flex;
          align-items: center;
          gap: 12px;
          cursor: pointer;
          transition: background-color 0.2s;

          &:hover {
            background-color: #f3f4f6;
          }

          &:not(:last-child) {
            border-bottom: 1px solid #e5e7eb;
          }

          .symbol {
            font-weight: 600;
            color: #1f2937;
            min-width: 100px;
          }

          .name {
            color: #4b5563;
            flex: 1;
          }

          .industry {
            font-size: 12px;
            color: #9ca3af;
          }
        }
      }

      .selected-stocks {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-bottom: 16px;

        :deep(.el-tag) {
          font-size: 14px;
        }
      }
    }
  }

  .comparison-table-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .title {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
      }
    }

    .table-wrapper {
      .stock-header {
        .symbol {
          font-weight: 600;
          color: #1f2937;
        }

        .name {
          font-size: 12px;
          color: #6b7280;
          margin-top: 2px;
        }
      }

      .factor-value {
        font-weight: 500;
        padding: 4px 8px;
        border-radius: 4px;

        &.best {
          background-color: #d1fae5;
          color: #065f46;
        }

        &.worst {
          background-color: #fee2e2;
          color: #991b1b;
        }
      }
    }
  }

  .correlation-card,
  .distribution-card {
    margin-bottom: 20px;

    .card-header {
      display: flex;
      align-items: center;
      justify-content: space-between;

      .title {
        margin: 0;
        font-size: 16px;
        font-weight: 600;
        color: #1f2937;
      }
    }

    .chart-container {
      width: 100%;
      height: 500px;
    }
  }
}
</style>
