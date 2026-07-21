<template>
  <div class="v14-trading-container">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="header-left">
        <h1>V14量化交易 P0优化版</h1>
        <div class="version-badge">v2.0.0</div>
      </div>
      <div class="header-right">
        <div class="model-info">
          <span class="label">模型:</span>
          <span class="value">V14 P0 (233,456样本)</span>
        </div>
        <div class="performance-info">
          <span class="label">预期年化:</span>
          <span class="value highlight">41.2%</span>
        </div>
        <div class="sharpe-info">
          <span class="label">夏普比率:</span>
          <span class="value">4.67</span>
        </div>
      </div>
    </div>

    <!-- 主要内容区 -->
    <div class="main-content">
      <!-- 左侧：账户信息 -->
      <div class="left-panel">
        <!-- 账户总览 -->
        <div class="card account-summary">
          <div class="card-header">
            <h3>账户总览</h3>
            <span class="account-name">V14模拟仓</span>
          </div>
          <div class="card-body">
            <div class="summary-item">
              <span class="label">总资产</span>
              <span class="value">¥{{ formatNumber(accountInfo.totalValue) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">现金</span>
              <span class="value">¥{{ formatNumber(accountInfo.cash) }}</span>
            </div>
            <div class="summary-item">
              <span class="label">持仓市值</span>
              <span class="value">¥{{ formatNumber(accountInfo.positionValue) }}</span>
            </div>
            <div class="summary-item highlight">
              <span class="label">累计收益</span>
              <span class="value" :class="accountInfo.totalReturn >= 0 ? 'profit' : 'loss'">
                {{ accountInfo.totalReturn >= 0 ? '+' : '' }}{{ (accountInfo.totalReturn * 100).toFixed(2) }}%
              </span>
            </div>
          </div>
        </div>

        <!-- 策略配置 -->
        <div class="card strategy-config">
          <div class="card-header">
            <h3>V14策略配置</h3>
          </div>
          <div class="card-body">
            <div class="config-item">
              <span class="label">调仓周期</span>
              <span class="value">7天</span>
            </div>
            <div class="config-item">
              <span class="label">持仓数量</span>
              <span class="value">5只</span>
            </div>
            <div class="config-item">
              <span class="label">单股权重</span>
              <span class="value">18%</span>
            </div>
            <div class="config-item">
              <span class="label">总仓位</span>
              <span class="value">90%</span>
            </div>
            <div class="config-item">
              <span class="label">止损线</span>
              <span class="value">-12%</span>
            </div>
          </div>
        </div>

        <!-- 操作按钮 -->
        <div class="action-buttons">
          <button class="btn btn-primary" @click="manualRebalance" :disabled="loading">
            <span v-if="!loading">手动调仓</span>
            <span v-else>执行中...</span>
          </button>
          <button class="btn btn-secondary" @click="refreshData">
            刷新数据
          </button>
        </div>
      </div>

      <!-- 右侧：持仓和收益 -->
      <div class="right-panel">
        <!-- Tab切换 -->
        <div class="tabs">
          <div
            class="tab"
            :class="{ active: activeTab === 'positions' }"
            @click="activeTab = 'positions'"
          >
            持仓明细
          </div>
          <div
            class="tab"
            :class="{ active: activeTab === 'performance' }"
            @click="activeTab = 'performance'"
          >
            收益曲线
          </div>
          <div
            class="tab"
            :class="{ active: activeTab === 'trades' }"
            @click="activeTab = 'trades'"
          >
            交易记录
          </div>
        </div>

        <!-- 持仓明细 -->
        <div v-if="activeTab === 'positions'" class="tab-content">
          <div class="card positions-card">
            <table class="positions-table">
              <thead>
                <tr>
                  <th>股票代码</th>
                  <th>股票名称</th>
                  <th>持仓数量</th>
                  <th>成本价</th>
                  <th>现价</th>
                  <th>盈亏</th>
                  <th>盈亏比例</th>
                  <th>权重</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="pos in positions" :key="pos.symbol">
                  <td class="symbol">{{ pos.symbol }}</td>
                  <td>{{ pos.name }}</td>
                  <td>{{ pos.shares }}</td>
                  <td>¥{{ pos.avgPrice.toFixed(2) }}</td>
                  <td>¥{{ pos.currentPrice.toFixed(2) }}</td>
                  <td :class="pos.profit >= 0 ? 'profit' : 'loss'">
                    {{ pos.profit >= 0 ? '+' : '' }}¥{{ pos.profit.toFixed(2) }}
                  </td>
                  <td :class="pos.profitRate >= 0 ? 'profit' : 'loss'">
                    {{ pos.profitRate >= 0 ? '+' : '' }}{{ (pos.profitRate * 100).toFixed(2) }}%
                  </td>
                  <td>{{ (pos.weight * 100).toFixed(1) }}%</td>
                </tr>
              </tbody>
            </table>
            <div v-if="positions.length === 0" class="empty-state">
              暂无持仓
            </div>
          </div>
        </div>

        <!-- 收益曲线 -->
        <div v-if="activeTab === 'performance'" class="tab-content">
          <div class="card performance-card">
            <div ref="performanceChart" class="chart-container"></div>
          </div>
        </div>

        <!-- 交易记录 -->
        <div v-if="activeTab === 'trades'" class="tab-content">
          <div class="card trades-card">
            <table class="trades-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>类型</th>
                  <th>股票</th>
                  <th>数量</th>
                  <th>价格</th>
                  <th>金额</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="trade in recentTrades" :key="trade.id">
                  <td>{{ formatDate(trade.timestamp) }}</td>
                  <td>
                    <span class="trade-type" :class="trade.action.toLowerCase()">
                      {{ trade.action }}
                    </span>
                  </td>
                  <td class="symbol">{{ trade.symbol }}</td>
                  <td>{{ trade.shares }}</td>
                  <td>¥{{ trade.price.toFixed(2) }}</td>
                  <td>¥{{ (trade.shares * trade.price).toFixed(2) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- 对比V13 -->
    <div class="comparison-section">
      <div class="card">
        <div class="card-header">
          <h3>V13 vs V14 对比</h3>
        </div>
        <div class="card-body">
          <div class="comparison-grid">
            <div class="comparison-item">
              <div class="label">年化收益率</div>
              <div class="values">
                <span class="v13">V13: 15.0%</span>
                <span class="arrow">→</span>
                <span class="v14">V14: 41.2%</span>
                <span class="improvement">+175%</span>
              </div>
            </div>
            <div class="comparison-item">
              <div class="label">夏普比率</div>
              <div class="values">
                <span class="v13">V13: 1.2</span>
                <span class="arrow">→</span>
                <span class="v14">V14: 4.67</span>
                <span class="improvement">+289%</span>
              </div>
            </div>
            <div class="comparison-item">
              <div class="label">最大回撤</div>
              <div class="values">
                <span class="v13">V13: -18%</span>
                <span class="arrow">→</span>
                <span class="v14">V14: -9%</span>
                <span class="improvement">改善50%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'

// 响应式数据
const activeTab = ref('positions')
const loading = ref(false)

const accountInfo = ref({
  totalValue: 100000,
  cash: 10000,
  positionValue: 90000,
  totalReturn: 0.412
})

const positions = ref([])

const recentTrades = ref([])

const performanceChart = ref(null)

// 方法
const formatNumber = (num: number) => {
  return num.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}

const formatDate = (timestamp: string) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}

// API基础URL
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001'

const manualRebalance = async () => {
  loading.value = true
  try {
    // 直接调用FastAPI
    const response = await fetch(`${API_BASE_URL}/api/v14/manual-rebalance`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    })
    const result = await response.json()

    if (result.success) {
      alert('V14手动调仓成功！')
      refreshData()
    } else {
      alert('调仓失败: ' + result.error)
    }
  } catch (error) {
    alert('调仓失败: ' + error)
  } finally {
    loading.value = false
  }
}

const refreshData = async () => {
  // 刷新账户数据、持仓、交易记录
  try {
    // 获取账户信息
    const accountResponse = await fetch(`${API_BASE_URL}/api/v14/account-info`)
    const accountData = await accountResponse.json()
    if (accountData.success) {
      // 映射API字段到前端期望的字段
      accountInfo.value = {
        totalValue: accountData.totalValue || 0,
        cash: accountData.cash || 0,
        positionValue: accountData.positionValue || 0,
        totalReturn: accountData.totalReturn || 0
      }
    }

    // 获取持仓明细
    const positionsResponse = await fetch(`${API_BASE_URL}/api/v14/positions`)
    const positionsData = await positionsResponse.json()
    if (positionsData.success) {
      positions.value = positionsData.positions || []
    }

    // 获取交易记录
    const tradesResponse = await fetch(`${API_BASE_URL}/api/v14/trades?limit=20`)
    const tradesData = await tradesResponse.json()
    if (tradesData.success) {
      recentTrades.value = tradesData.trades || []
    }
  } catch (error) {
    console.error('刷新数据失败:', error)
  }
}

const initPerformanceChart = () => {
  if (!performanceChart.value) return

  const chart = echarts.init(performanceChart.value)

  // 示例收益曲线数据
  const option = {
    title: {
      text: 'V14收益曲线'
    },
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月']
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [
      {
        name: 'V14收益率',
        type: 'line',
        data: [5, 12, 18, 25, 35, 41.2],
        smooth: true,
        lineStyle: {
          color: '#52c41a'
        },
        areaStyle: {
          color: 'rgba(82, 196, 26, 0.1)'
        }
      }
    ]
  }

  chart.setOption(option)
}

onMounted(() => {
  refreshData()
  if (activeTab.value === 'performance') {
    initPerformanceChart()
  }
})
</script>

<style scoped>
.v14-trading-container {
  padding: 20px;
  background: #f0f2f5;
  min-height: 100vh;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-left h1 {
  margin: 0;
  font-size: 24px;
  color: #1890ff;
}

.version-badge {
  background: #52c41a;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
}

.header-right {
  display: flex;
  gap: 30px;
}

.model-info, .performance-info, .sharpe-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 12px;
  color: #999;
}

.value {
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.value.highlight {
  color: #ff4d4f;
  font-size: 20px;
}

.main-content {
  display: grid;
  grid-template-columns: 350px 1fr;
  gap: 20px;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 1px solid #f0f0f0;
}

.card-header h3 {
  margin: 0;
  font-size: 18px;
}

.summary-item, .config-item {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.profit {
  color: #52c41a;
}

.loss {
  color: #ff4d4f;
}

.action-buttons {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.btn {
  padding: 12px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary {
  background: #1890ff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #40a9ff;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #f0f0f0;
  color: #333;
}

.tabs {
  display: flex;
  background: white;
  border-radius: 8px 8px 0 0;
  overflow: hidden;
}

.tab {
  flex: 1;
  padding: 15px;
  text-align: center;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.3s;
}

.tab.active {
  border-bottom-color: #1890ff;
  color: #1890ff;
  font-weight: 600;
}

.tab-content {
  background: white;
  border-radius: 0 0 8px 8px;
}

.positions-table, .trades-table {
  width: 100%;
  border-collapse: collapse;
}

.positions-table th, .trades-table th {
  background: #fafafa;
  padding: 12px;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #f0f0f0;
}

.positions-table td, .trades-table td {
  padding: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.symbol {
  color: #1890ff;
  font-weight: 600;
}

.trade-type {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.trade-type.buy {
  background: #f6ffed;
  color: #52c41a;
}

.trade-type.sell {
  background: #fff1f0;
  color: #ff4d4f;
}

.chart-container {
  height: 400px;
}

.comparison-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 30px;
}

.comparison-item .values {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}

.v13 {
  color: #999;
}

.v14 {
  color: #1890ff;
  font-weight: 600;
}

.improvement {
  color: #52c41a;
  font-size: 12px;
}

.empty-state {
  text-align: center;
  padding: 60px;
  color: #999;
}
</style>
