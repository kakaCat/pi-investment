<template>
  <div class="daily-report-page">
    <el-card shadow="never" v-loading="loading">
      <!-- 顶部日期选择 -->
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-base font-semibold">日报</h2>
        <div class="flex items-center gap-2">
          <el-button :icon="ArrowLeft" @click="previousDay">前一天</el-button>
          <el-date-picker
            v-model="selectedDate"
            type="date"
            placeholder="选择日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="fetchReport"
          />
          <el-button :icon="ArrowRight" @click="nextDay">后一天</el-button>
          <el-button type="primary" :icon="Download" @click="exportReport">导出报告</el-button>
        </div>
      </div>

      <!-- 报告摘要 -->
      <div class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-gray-50 rounded-lg p-4">
          <div class="text-xs text-gray-400 mb-1">今日信号数</div>
          <div class="text-3xl font-bold text-gray-900">{{ report.signalCount }}</div>
          <div class="flex gap-2 mt-1 text-xs">
            <span class="text-red-500">{{ report.buySignals }} 买入</span>
            <span class="text-green-600">{{ report.sellSignals }} 卖出</span>
            <span class="text-gray-500">{{ report.holdSignals }} 持有</span>
          </div>
        </div>

        <div class="bg-gray-50 rounded-lg p-4">
          <div class="text-xs text-gray-400 mb-1">风险概况</div>
          <div class="text-3xl font-bold" :class="getRiskColor(report.riskLevel)">
            {{ getRiskText(report.riskLevel) }}
          </div>
          <div class="text-xs text-gray-400 mt-1">
            VaR(95%): {{ formatPercent(report.var) }} | 波动率: {{ formatPercent(report.volatility) }}
          </div>
        </div>

        <div class="bg-gray-50 rounded-lg p-4">
          <div class="text-xs text-gray-400 mb-1">组合收益率</div>
          <div class="text-3xl font-bold" :class="report.portfolioReturn >= 0 ? 'text-red-500' : 'text-green-600'">
            {{ formatPercent(report.portfolioReturn) }}
          </div>
          <div class="text-xs text-gray-400 mt-1">
            今日 | 年化: {{ formatPercent(report.annualizedReturn) }}
          </div>
        </div>
      </div>

      <!-- 高置信度信号 -->
      <h3 class="text-base font-semibold mb-3">高置信度信号</h3>
      <div class="space-y-2 mb-6">
        <div
          v-for="signal in topSignals"
          :key="signal.id"
          class="flex items-center gap-4 text-sm px-4 py-2.5 rounded-lg"
          :class="signal.type === 'buy' ? 'bg-red-50' : 'bg-green-50'"
        >
          <el-tag
            :type="signal.type === 'buy' ? 'danger' : 'success'"
            size="small"
          >
            {{ signal.type === 'buy' ? 'BUY' : 'SELL' }}
          </el-tag>
          <span class="font-medium">{{ signal.stockCode }} {{ signal.stockName }}</span>
          <span class="text-gray-500">置信度 {{ signal.confidence.toFixed(2) }}</span>
          <span class="text-gray-400 ml-auto">{{ signal.strategy }} 策略</span>
        </div>
      </div>

      <!-- 风控提醒 -->
      <h3 class="text-base font-semibold mb-3">风控提醒</h3>
      <div
        v-if="riskAlerts.length > 0"
        class="space-y-2 mb-6"
      >
        <div
          v-for="(alert, index) in riskAlerts"
          :key="index"
          class="border rounded-lg p-4 text-sm"
          :class="getAlertClass(alert.level)"
        >
          <div class="flex items-start gap-2">
            <span class="font-bold">{{ getAlertIcon(alert.level) }}</span>
            <div class="flex-1">
              <div class="font-medium mb-1">{{ alert.title }}</div>
              <div class="text-gray-600">{{ alert.message }}</div>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="bg-green-50 border border-green-200 rounded-lg p-4 text-sm text-green-700 mb-6">
        ✓ 无风险提醒，一切正常
      </div>

      <!-- 持仓变化 -->
      <h3 class="text-base font-semibold mb-3">持仓变化</h3>
      <div class="grid grid-cols-2 gap-4 mb-6">
        <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">新增持仓</h4>
          <div v-if="positionChanges.added.length > 0" class="space-y-2">
            <div
              v-for="pos in positionChanges.added"
              :key="pos.code"
              class="flex items-center justify-between bg-red-50 px-3 py-2 rounded text-sm"
            >
              <span class="font-medium">{{ pos.code }} {{ pos.name }}</span>
              <span class="text-gray-600">{{ pos.quantity }} 股</span>
            </div>
          </div>
          <div v-else class="text-sm text-gray-400">无新增持仓</div>
        </div>

        <div>
          <h4 class="text-sm font-medium text-gray-700 mb-2">减少持仓</h4>
          <div v-if="positionChanges.removed.length > 0" class="space-y-2">
            <div
              v-for="pos in positionChanges.removed"
              :key="pos.code"
              class="flex items-center justify-between bg-green-50 px-3 py-2 rounded text-sm"
            >
              <span class="font-medium">{{ pos.code }} {{ pos.name }}</span>
              <span class="text-gray-600">{{ pos.quantity }} 股</span>
            </div>
          </div>
          <div v-else class="text-sm text-gray-400">无减少持仓</div>
        </div>
      </div>

      <!-- 策略表现 -->
      <h3 class="text-base font-semibold mb-3">策略表现</h3>
      <el-table :data="strategyPerformance" stripe class="mb-6">
        <el-table-column prop="name" label="策略名称" width="200" />
        <el-table-column prop="signalCount" label="信号数" width="100" align="right" />
        <el-table-column prop="winRate" label="胜率" width="100" align="right">
          <template #default="{ row }">
            {{ formatPercent(row.winRate) }}
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="盈亏" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.pnl >= 0 ? 'text-red-500' : 'text-green-600'" class="font-medium">
              {{ formatPrice(row.pnl) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="avgReturn" label="平均收益率" width="120" align="right">
          <template #default="{ row }">
            <span :class="row.avgReturn >= 0 ? 'text-red-500' : 'text-green-600'">
              {{ formatPercent(row.avgReturn) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="sharpe" label="夏普比率" width="100" align="right">
          <template #default="{ row }">
            {{ row.sharpe.toFixed(2) }}
          </template>
        </el-table-column>
      </el-table>

      <!-- 市场回顾 -->
      <h3 class="text-base font-semibold mb-3">市场回顾</h3>
      <div class="grid grid-cols-3 gap-4">
        <div class="bg-gray-50 rounded-lg p-4">
          <h4 class="text-sm font-medium text-gray-700 mb-2">大盘走势</h4>
          <div class="space-y-1 text-sm">
            <div class="flex justify-between">
              <span>上证指数</span>
              <span class="text-red-500 font-medium">+1.23%</span>
            </div>
            <div class="flex justify-between">
              <span>深证成指</span>
              <span class="text-red-500 font-medium">+0.87%</span>
            </div>
            <div class="flex justify-between">
              <span>创业板指</span>
              <span class="text-green-600 font-medium">-0.45%</span>
            </div>
          </div>
        </div>

        <div class="bg-gray-50 rounded-lg p-4">
          <h4 class="text-sm font-medium text-gray-700 mb-2">行业表现</h4>
          <div class="space-y-1 text-sm">
            <div class="flex justify-between">
              <span>白酒</span>
              <span class="text-red-500 font-medium">+2.34%</span>
            </div>
            <div class="flex justify-between">
              <span>新能源</span>
              <span class="text-red-500 font-medium">+1.56%</span>
            </div>
            <div class="flex justify-between">
              <span>半导体</span>
              <span class="text-green-600 font-medium">-1.23%</span>
            </div>
          </div>
        </div>

        <div class="bg-gray-50 rounded-lg p-4">
          <h4 class="text-sm font-medium text-gray-700 mb-2">热点概念</h4>
          <div class="flex flex-wrap gap-2">
            <el-tag size="small">AI应用</el-tag>
            <el-tag size="small">新能源车</el-tag>
            <el-tag size="small">芯片国产化</el-tag>
            <el-tag size="small">医药创新</el-tag>
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight, Download } from '@element-plus/icons-vue'
import { formatPercent, formatPrice } from '@/utils/format'
import { apiClient } from '@/services/api/client'

interface Report {
  signalCount: number
  buySignals: number
  sellSignals: number
  holdSignals: number
  riskLevel: 'low' | 'medium' | 'high'
  var: number
  volatility: number
  portfolioReturn: number
  annualizedReturn: number
}

interface Signal {
  id: string
  type: 'buy' | 'sell'
  stockCode: string
  stockName: string
  confidence: number
  strategy: string
}

interface RiskAlert {
  level: 'warning' | 'danger'
  title: string
  message: string
}

interface StrategyPerf {
  name: string
  signalCount: number
  winRate: number
  pnl: number
  avgReturn: number
  sharpe: number
}

// 状态
const selectedDate = ref(new Date().toISOString().split('T')[0])
const loading = ref(false)

// 报告数据
const report = reactive<Report>({
  signalCount: 12,
  buySignals: 5,
  sellSignals: 3,
  holdSignals: 4,
  riskLevel: 'medium',
  var: -3.2,
  volatility: 15.8,
  portfolioReturn: 2.34,
  annualizedReturn: 18.5
})

// 高置信度信号
const topSignals = ref<Signal[]>([
  {
    id: '1',
    type: 'buy',
    stockCode: '000858.SZ',
    stockName: '五粮液',
    confidence: 0.92,
    strategy: 'RSI_Reversal'
  },
  {
    id: '2',
    type: 'buy',
    stockCode: '600519.SH',
    stockName: '贵州茅台',
    confidence: 0.87,
    strategy: 'ML_Predictor'
  },
  {
    id: '3',
    type: 'sell',
    stockCode: '300750.SZ',
    stockName: '宁德时代',
    confidence: 0.81,
    strategy: 'MA_Crossover'
  }
])

// 风控提醒
const riskAlerts = ref<RiskAlert[]>([
  {
    level: 'warning',
    title: '持仓集中度偏高',
    message: '前3大持仓占比达到65%，建议适当分散投资'
  }
])

// 持仓变化
const positionChanges = reactive({
  added: [
    { code: '000858.SZ', name: '五粮液', quantity: 500 },
    { code: '600519.SH', name: '贵州茅台', quantity: 100 }
  ],
  removed: [
    { code: '300750.SZ', name: '宁德时代', quantity: 500 }
  ]
})

// 策略表现
const strategyPerformance = ref<StrategyPerf[]>([
  {
    name: 'RSI_Reversal',
    signalCount: 5,
    winRate: 68.5,
    pnl: 12500,
    avgReturn: 3.2,
    sharpe: 1.85
  },
  {
    name: 'MA_Crossover',
    signalCount: 4,
    winRate: 55.0,
    pnl: 8200,
    avgReturn: 2.1,
    sharpe: 1.42
  },
  {
    name: 'ML_Predictor',
    signalCount: 3,
    winRate: 72.3,
    pnl: 15800,
    avgReturn: 4.5,
    sharpe: 2.15
  }
])

// 获取报告
const fetchReport = async () => {
  loading.value = true
  try {
    const response = await apiClient.get('/api/report/daily', {
      params: {
        date: selectedDate.value
      }
    })

    // 适配后端返回的数据结构
    if (response.error) {
      ElMessage.warning(response.error)
      return
    }

    // 如果返回的是 markdown 格式
    if (response.report?.format === 'markdown') {
      ElMessage.info('报告为 Markdown 格式，暂不支持展示')
      return
    }

    // 解析后端数据并更新前端状态
    const signalsData = response.signals || {}
    const riskData = response.risk || {}

    // 更新报告摘要
    Object.assign(report, {
      signalCount: signalsData.total || 0,
      buySignals: signalsData.buy_count || signalsData.buyCount || 0,
      sellSignals: signalsData.sell_count || signalsData.sellCount || 0,
      holdSignals: signalsData.hold_count || signalsData.holdCount || 0,
      riskLevel: riskData.level || 'medium',
      var: riskData.var || 0,
      volatility: riskData.volatility || 0,
      portfolioReturn: riskData.portfolio_return || riskData.portfolioReturn || 0,
      annualizedReturn: riskData.annualized_return || riskData.annualizedReturn || 0
    })

    // 更新高置信度信号
    const rawSignals = response.signals?.signals || []
    topSignals.value = rawSignals
      .filter((s: any) => (s.confidence || 0) > 0.7)
      .slice(0, 5)
      .map((s: any, idx: number) => ({
        id: String(idx + 1),
        type: s.signal === 'BUY' ? 'buy' : 'sell',
        stockCode: s.symbol || s.stock_code || s.stockCode,
        stockName: s.name || s.stock_name || s.stockName || '',
        confidence: s.confidence || 0,
        strategy: s.strategy || 'Unknown'
      }))

    // 更新风控提醒
    const alerts = riskData.alerts || []
    riskAlerts.value = alerts.map((alert: any) => ({
      level: alert.level || 'warning',
      title: alert.title || '风险提醒',
      message: alert.message || alert.description || ''
    }))

    // 更新持仓变化
    const changes = riskData.position_changes || riskData.positionChanges || {}
    positionChanges.added = (changes.added || []).map((p: any) => ({
      code: p.code || p.symbol,
      name: p.name,
      quantity: p.quantity || p.shares
    }))
    positionChanges.removed = (changes.removed || []).map((p: any) => ({
      code: p.code || p.symbol,
      name: p.name,
      quantity: p.quantity || p.shares
    }))

    // 更新策略表现
    const strategies = response.strategy_performance || response.strategyPerformance || []
    strategyPerformance.value = strategies.map((s: any) => ({
      name: s.name || s.strategy_name || s.strategyName,
      signalCount: s.signal_count || s.signalCount || 0,
      winRate: s.win_rate || s.winRate || 0,
      pnl: s.pnl || 0,
      avgReturn: s.avg_return || s.avgReturn || 0,
      sharpe: s.sharpe || s.sharpe_ratio || s.sharpeRatio || 0
    }))

    ElMessage.success(`已加载 ${selectedDate.value} 的日报`)
  } catch (error) {
    console.error('获取每日报告失败:', error)
    ElMessage.error('获取每日报告失败，请检查后端服务是否运行')
  } finally {
    loading.value = false
  }
}

// 前一天
const previousDay = () => {
  const date = new Date(selectedDate.value)
  date.setDate(date.getDate() - 1)
  selectedDate.value = date.toISOString().split('T')[0]
  fetchReport()
}

// 后一天
const nextDay = () => {
  const date = new Date(selectedDate.value)
  date.setDate(date.getDate() + 1)
  selectedDate.value = date.toISOString().split('T')[0]
  fetchReport()
}

// 导出报告
const exportReport = () => {
  try {
    const reportData = {
      date: selectedDate.value,
      summary: report,
      signals: topSignals.value,
      riskAlerts: riskAlerts.value,
      positionChanges,
      strategyPerformance: strategyPerformance.value
    }

    const dataStr = JSON.stringify(reportData, null, 2)
    const blob = new Blob([dataStr], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `daily_report_${selectedDate.value}.json`
    link.click()
    URL.revokeObjectURL(url)

    ElMessage.success('报告导出成功')
  } catch (error) {
    console.error('导出报告失败:', error)
    ElMessage.error('导出报告失败')
  }
}

// 获取风险颜色
const getRiskColor = (level: string) => {
  const map: Record<string, string> = {
    low: 'text-green-500',
    medium: 'text-orange-500',
    high: 'text-red-500'
  }
  return map[level] || 'text-gray-500'
}

// 获取风险文本
const getRiskText = (level: string) => {
  const map: Record<string, string> = {
    low: '低',
    medium: '中等',
    high: '高'
  }
  return map[level] || level
}

// 获取提醒样式
const getAlertClass = (level: string) => {
  const map: Record<string, string> = {
    warning: 'bg-yellow-50 border-yellow-200',
    danger: 'bg-red-50 border-red-200'
  }
  return map[level] || 'bg-gray-50 border-gray-200'
}

// 获取提醒图标
const getAlertIcon = (level: string) => {
  const map: Record<string, string> = {
    warning: '⚠',
    danger: '✗'
  }
  return map[level] || 'ℹ'
}

onMounted(() => {
  fetchReport()
})

// 监听日期变化
watch(selectedDate, () => {
  fetchReport()
})
</script>

<style scoped>
.daily-report-page {
  padding: 20px;
}
</style>
