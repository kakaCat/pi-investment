<template>
  <div class="dashboard-page">
    <el-row :gutter="24">
      <!-- Row 1: 总资产 / 流动资产 / 亏损 -->
      <el-col :xs="24" :sm="12" :md="8" :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff;">
              <el-icon :size="32" color="#1890ff"><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ totalAssets }}</div>
              <div class="stat-label">总资产</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="8" :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6fffb;">
              <el-icon :size="32" color="#13c2c2"><Money /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ liquidAssets }}</div>
              <div class="stat-label">流动资产</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="8" :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6;">
              <el-icon :size="32" color="#fa8c16"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="unrealizedPnLClass">{{ unrealizedPnL }}</div>
              <div class="stat-label">持仓盈亏</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="24" style="margin-top: 24px;">
      <!-- Row 2: 今日盈亏 / 待审批信号 / 风险预警 -->
      <el-col :xs="24" :sm="12" :md="8" :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed;">
              <el-icon :size="32" color="#52c41a"><ArrowUp /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value" :class="dailyPnLClass">{{ dailyPnL }}</div>
              <div class="stat-label">今日盈亏</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="8" :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f9f0ff;">
              <el-icon :size="32" color="#722ed1"><Bell /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ pendingSignals }}</div>
              <div class="stat-label">待审批信号</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="8" :span="8">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff1f0;">
              <el-icon :size="32" color="#f5222d"><WarningFilled /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">{{ riskAlerts }}</div>
              <div class="stat-label">风险预警</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="24" style="margin-top: 24px;">
      <!-- 组合净值走势 -->
      <el-col :xs="24" :sm="24" :md="16" :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>组合净值走势</span>
            </div>
          </template>
          <div ref="chartRef" class="chart-container" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <!-- Agent今日工作摘要 -->
      <el-col :xs="24" :sm="24" :md="8" :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Agent今日工作</span>
            </div>
          </template>
          <el-timeline v-if="agentLogs.length > 0">
            <el-timeline-item
              v-for="log in agentLogs"
              :key="log.id"
              :timestamp="formatLogTime(log.timestamp)"
              placement="top"
            >
              <div class="timeline-content">
                <div class="timeline-title">{{ log.action }}</div>
                <div class="timeline-desc">{{ log.description }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无今日工作记录" :image-size="80" />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="24" style="margin-top: 24px;">
      <!-- 待处理事项 -->
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>待处理事项</span>
              <el-button type="primary" size="small" @click="handleViewAll">查看全部</el-button>
            </div>
          </template>
          <el-table :data="pendingTasks" style="width: 100%">
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="row.type === '买入申请' ? 'success' : 'warning'">
                  {{ row.type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="symbol" label="股票" width="120" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                {{ row.confidence }}%
              </template>
            </el-table-column>
            <el-table-column prop="time" label="时间" width="180" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button type="success" size="small" @click="handleApprove(row)">批准</el-button>
                <el-button type="danger" size="small" @click="handleReject(row)">拒绝</el-button>
                <el-button type="primary" size="small" @click="handleView(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { TrendCharts, ArrowUp, Bell, Warning, Money, WarningFilled } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'
import { tradingApi } from '@/services/api/trading'
import { apiClient } from '@/services/api/client'
import { useAgentStore } from '@/stores/agent'
import { formatSignedCurrency } from '@/utils/format'

const router = useRouter()
const agentStore = useAgentStore()

// 统计数据
const totalAssets = ref('¥0')
const liquidAssets = ref('¥0')
const unrealizedPnL = ref('¥0')
const unrealizedPnLClass = ref('')
const dailyPnL = ref('¥0')
const dailyPnLClass = ref('')
const pendingSignals = ref(0)
const riskAlerts = ref(0)

const pendingTasks = ref<any[]>([])
const agentLogs = ref<any[]>([])
const loading = ref(false)

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

// 获取投资组合概览数据
const fetchPortfolioSummary = async () => {
  try {
    const data = await tradingApi.getPortfolioSummary()

    // 总资产 = 持仓市值 + 现金
    totalAssets.value = `¥${data.totalValue?.toLocaleString() || '0'}`

    // 流动资产（现金）
    const cash = data.cash || data.liquidAssets || 0
    liquidAssets.value = `¥${Number(cash).toLocaleString()}`

    // 持仓盈亏（未实现盈亏）
    const pnl = data.totalPnl || 0
    unrealizedPnL.value = formatSignedCurrency(pnl)
    unrealizedPnLClass.value = pnl >= 0 ? 'success' : 'danger'

    const change = data.dailyChange || 0
    dailyPnL.value = formatSignedCurrency(change)
    dailyPnLClass.value = change >= 0 ? 'success' : 'danger'

    // TODO: 从其他接口获取待审批信号和风险预警数量
    pendingSignals.value = 0
    riskAlerts.value = 0
  } catch (error) {
    console.error('获取投资组合概览失败:', error)
  }
}

// 获取今日信号作为待处理事项
const fetchPendingTasks = async () => {
  try {
    const response = await apiClient.get('/api/signals', {
      params: {
        date: 'today',
        limit: 10
      }
    })

    // 转换信号数据为待处理任务格式
    pendingTasks.value = (response?.items || []).map((signal: any) => ({
      type: signal.action === 'buy' ? '买入申请' : signal.action === 'sell' ? '卖出申请' : '信号',
      symbol: signal.symbol,
      description: signal.reason || '无描述',
      confidence: Math.round((signal.confidence || 0) * 100),
      time: signal.signalDate || signal.createdAt || ''
    }))

    pendingSignals.value = pendingTasks.value.length
  } catch (error) {
    console.error('获取今日信号失败:', error)
  }
}

// 获取Agent今日工作日志
const fetchAgentLogs = async () => {
  try {
    const today = new Date().toISOString().split('T')[0]
    await agentStore.fetchLogs({ startDate: today, endDate: today, limit: 10 })
    agentLogs.value = agentStore.recentLogs
  } catch (error) {
    console.error('获取Agent日志失败:', error)
  }
}

const formatLogTime = (timestamp: string) => {
  if (!timestamp) return ''
  const d = new Date(timestamp)
  return d.toTimeString().slice(0, 5)
}

// 获取历史数据并渲染图表
const fetchHistoryAndRenderChart = async () => {
  try {
    const data = await apiClient.get('/api/portfolio/history', {
      params: { days: 30 }
    })

    if (!isAlive.value) return

    if (!data || !data.history || data.history.length === 0) {
      console.warn('没有历史数据')
      renderChartWithMockData()
      return
    }

    const dates = data.history.map((item: any) => item.date)
    const values = data.history.map((item: any) => item.totalAssets)

    renderChart(dates, values)
  } catch (error) {
    if (!isAlive.value) return
    console.error('获取历史数据失败:', error)
    renderChartWithMockData()
  }
}

const renderChart = (dates: string[], values: number[]) => {
  if (!chartRef.value) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const param = params[0]
        return `${param.name}<br/>总资产: ¥${param.value.toLocaleString()}`
      }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates
    },
    yAxis: {
      type: 'value',
      scale: true,
      axisLabel: {
        formatter: (value: number) => `¥${(value / 10000).toFixed(1)}万`
      }
    },
    series: [
      {
        name: '总资产',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#5470c6',
          width: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(84, 112, 198, 0.3)' },
              { offset: 1, color: 'rgba(84, 112, 198, 0.05)' }
            ]
          }
        },
        data: values
      }
    ]
  }

  chartInstance.setOption(option)
}

const renderChartWithMockData = () => {
  // 如果没有真实数据，使用模拟数据
  const dates = []
  const values = []
  const baseValue = 1000000
  for (let i = 0; i < 30; i++) {
    const date = new Date()
    date.setDate(date.getDate() - (29 - i))
    dates.push(date.toISOString().split('T')[0])
    values.push(baseValue + Math.random() * 200000 - 50000)
  }

  renderChart(dates, values)
}

const handleViewAll = () => {
  router.push('/opportunities')
}

const handleApprove = (row: any) => {
  ElMessage.success(`已批准 ${row.symbol} 的${row.type}`)
  // TODO: Call API to approve the signal
}

const handleReject = (row: any) => {
  ElMessage.warning(`已拒绝 ${row.symbol} 的${row.type}`)
  // TODO: Call API to reject the signal
}

const handleView = (row: any) => {
  router.push(`/opportunities/${row.symbol}`)
}

const handleResize = () => {
  chartInstance?.resize()
}

const isAlive = ref(true)

onMounted(async () => {
  loading.value = true

  try {
    // 并行获取所有数据
    await Promise.all([
      fetchPortfolioSummary(),
      fetchPendingTasks(),
      fetchHistoryAndRenderChart(),
      fetchAgentLogs()
    ])
  } catch (error) {
    if (isAlive.value) {
      console.error('加载 Dashboard 数据失败:', error)
    }
  } finally {
    if (isAlive.value) {
      loading.value = false
    }
  }

  // 响应式调整
  if (isAlive.value) {
    window.addEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  isAlive.value = false
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
})
</script>

<style scoped>
.dashboard-page {
  width: 100%;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #262626;
  margin-bottom: 4px;
}

.stat-value.success {
  color: #52c41a;
}

.stat-value.danger {
  color: #f5222d;
}

.stat-label {
  font-size: 14px;
  color: #8c8c8c;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  width: 100%;
  height: 100%;
}

.timeline-content {
  padding: 4px 0;
}

.timeline-title {
  font-size: 14px;
  color: #262626;
  margin-bottom: 4px;
}

.timeline-desc {
  font-size: 12px;
  color: #8c8c8c;
}

@media (max-width: 768px) {
  .stat-card {
    margin-bottom: 16px;
  }

  .stat-value {
    font-size: 20px;
  }

  .stat-icon {
    width: 48px;
    height: 48px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .chart-container {
    height: 250px !important;
  }

  :deep(.el-table) {
    font-size: 12px;
  }

  :deep(.el-button) {
    padding: 4px 8px;
    font-size: 12px;
  }
}
</style>
