<template>
  <div class="opponent-behavior">
    <h1>👥 市场对手行为监控</h1>

    <!-- 市场状态概览 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>📊 当前市场状态</span>
          <div>
            <span class="update-time">更新时间: {{ updateTime }}</span>
            <el-button size="small" @click="loadData" :loading="loading">刷新</el-button>
          </div>
        </div>
      </template>

      <div v-if="marketData" class="market-overview">
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="info-item">
              <span class="label">市场阶段:</span>
              <el-tag :type="getPhaseType(marketData.market_phase)" size="large">
                {{ translatePhase(marketData.market_phase) }}
              </el-tag>
            </div>
          </el-col>
          <el-col :span="12">
            <div class="info-item">
              <span class="label">情绪指数:</span>
              <el-progress
                :percentage="marketData.retail?.emotion_index || 50"
                :color="getEmotionColor(marketData.retail?.emotion_index)"
                :stroke-width="20"
                :show-text="true"
              />
            </div>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <el-row :gutter="20" class="mt-20">
      <!-- 散户行为 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <span>👨‍👩‍👧‍👦 散户行为</span>
          </template>

          <div v-if="marketData?.retail" class="behavior-detail">
            <div class="behavior-header">
              <el-tag :type="getBehaviorType(marketData.retail.behavior)" size="large">
                {{ translateBehavior(marketData.retail.behavior) }}
              </el-tag>
            </div>

            <div class="metrics">
              <div class="metric-item">
                <span class="metric-label">资金流向:</span>
                <span :class="['metric-value', marketData.retail.flow_amount > 0 ? 'positive' : 'negative']">
                  {{ formatFlow(marketData.retail.flow_amount) }}
                </span>
              </div>

              <div class="metric-item">
                <span class="metric-label">情绪指数:</span>
                <span class="metric-value">{{ marketData.retail.emotion_index }}/100</span>
                <span class="emotion-label">({{ getEmotionLabel(marketData.retail.emotion_index) }})</span>
              </div>

              <div class="metric-item">
                <span class="metric-label">净流入比例:</span>
                <span class="metric-value">{{ marketData.retail.net_inflow_ratio }}%</span>
              </div>
            </div>

            <!-- 趋势图 -->
            <div class="chart-container">
              <div ref="retailChartRef" style="width: 100%; height: 200px;"></div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 机构行为 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <span>🏢 机构行为</span>
          </template>

          <div v-if="marketData?.institution" class="behavior-detail">
            <div class="behavior-header">
              <el-tag :type="getBehaviorType(marketData.institution.behavior)" size="large">
                {{ translateBehavior(marketData.institution.behavior) }}
              </el-tag>
            </div>

            <div class="metrics">
              <div class="metric-item">
                <span class="metric-label">资金流向:</span>
                <span :class="['metric-value', marketData.institution.flow_amount > 0 ? 'positive' : 'negative']">
                  {{ formatFlow(marketData.institution.flow_amount) }}
                </span>
              </div>

              <div class="metric-item">
                <span class="metric-label">操作阶段:</span>
                <span class="metric-value">{{ marketData.institution.stage || '-' }}</span>
              </div>

              <div class="metric-item">
                <span class="metric-label">净流入比例:</span>
                <span class="metric-value">{{ marketData.institution.net_inflow_ratio }}%</span>
              </div>
            </div>

            <!-- 趋势图 -->
            <div class="chart-container">
              <div ref="institutionChartRef" style="width: 100%; height: 200px;"></div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 博弈机会 -->
    <el-card class="box-card mt-20">
      <template #header>
        <span>💡 博弈机会分析</span>
      </template>

      <div v-if="marketData?.game_opportunities && marketData.game_opportunities.length > 0">
        <div v-for="(opp, index) in marketData.game_opportunities" :key="index" class="opportunity-item">
          <div class="opp-header">
            <h3>{{ opp.opportunity_type }}</h3>
            <el-tag :type="getConfidenceType(opp.confidence)">
              置信度: {{ (opp.confidence * 100).toFixed(0) }}%
            </el-tag>
          </div>
          <p class="opp-reason">{{ opp.reason }}</p>
          <div class="opp-action">
            <el-icon><Warning /></el-icon>
            <span>{{ opp.suggested_action }}</span>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无博弈机会" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { getOpponentBehavior } from '@/services/game-intelligence'
import * as echarts from 'echarts'

const loading = ref(false)
const marketData = ref<any>(null)
const updateTime = ref('')

const retailChartRef = ref<HTMLElement>()
const institutionChartRef = ref<HTMLElement>()

let retailChart: any = null
let institutionChart: any = null
let refreshTimer: any = null

const loadData = async () => {
  loading.value = true
  try {
    const res = await getOpponentBehavior()
    if (res.success) {
      marketData.value = res.data
      updateTime.value = new Date().toLocaleTimeString()

      // 更新图表
      await nextTick()
      initCharts()
    }
  } catch (error) {
    console.error('加载对手行为失败:', error)
  } finally {
    loading.value = false
  }
}

const initCharts = () => {
  if (retailChartRef.value && !retailChart) {
    retailChart = echarts.init(retailChartRef.value)
  }
  if (institutionChartRef.value && !institutionChart) {
    institutionChart = echarts.init(institutionChartRef.value)
  }

  // 模拟数据（实际应该从API获取历史数据）
  const dates = ['Day1', 'Day2', 'Day3', 'Day4', 'Day5']
  const retailData = [-10, -15, -25, -30, -35]
  const institutionData = [8, 12, 18, 23, 28]

  const option = {
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: '{value}亿'
      }
    },
    series: [{
      data: [],
      type: 'line',
      smooth: true,
      areaStyle: {},
      itemStyle: {
        color: '#409eff'
      }
    }]
  }

  if (retailChart) {
    retailChart.setOption({
      ...option,
      series: [{
        ...option.series[0],
        data: retailData,
        itemStyle: { color: '#f56c6c' }
      }]
    })
  }

  if (institutionChart) {
    institutionChart.setOption({
      ...option,
      series: [{
        ...option.series[0],
        data: institutionData,
        itemStyle: { color: '#67c23a' }
      }]
    })
  }
}

const translatePhase = (phase: string) => {
  const map: Record<string, string> = {
    'accumulation': '吸筹阶段',
    'markup': '拉升阶段',
    'distribution': '派发阶段',
    'markdown': '下跌阶段'
  }
  return map[phase] || phase || '-'
}

const translateBehavior = (behavior: string) => {
  const map: Record<string, string> = {
    'panic_selling': '恐慌抛售',
    'fomo_buying': '追涨买入',
    'accumulating': '逢低建仓',
    'distributing': '高位出货',
    'neutral': '观望'
  }
  return map[behavior] || behavior || '-'
}

const getPhaseType = (phase: string) => {
  if (phase === 'accumulation') return 'success'
  if (phase === 'markup') return 'warning'
  if (phase === 'distribution') return 'danger'
  return 'info'
}

const getBehaviorType = (behavior: string) => {
  if (behavior === 'panic_selling') return 'danger'
  if (behavior === 'fomo_buying') return 'warning'
  if (behavior === 'accumulating') return 'success'
  if (behavior === 'distributing') return 'danger'
  return 'info'
}

const getConfidenceType = (confidence: number) => {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.6) return 'warning'
  return 'info'
}

const formatFlow = (amount: number) => {
  const sign = amount >= 0 ? '+' : ''
  return `${sign}${amount.toFixed(1)}亿`
}

const getEmotionLabel = (value: number) => {
  if (value < 20) return '极度恐慌'
  if (value < 40) return '恐慌'
  if (value < 60) return '中性'
  if (value < 80) return '贪婪'
  return '极度贪婪'
}

const getEmotionColor = (value: number) => {
  if (value < 40) return '#f56c6c'
  if (value < 60) return '#e6a23c'
  return '#67c23a'
}

onMounted(() => {
  loadData()
  refreshTimer = setInterval(loadData, 60000) // 每分钟刷新
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (retailChart) retailChart.dispose()
  if (institutionChart) institutionChart.dispose()
})
</script>

<style scoped>
.opponent-behavior {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.update-time {
  color: #909399;
  font-size: 12px;
  margin-right: 10px;
}

.market-overview {
  padding: 10px 0;
}

.info-item {
  display: flex;
  align-items: center;
  gap: 10px;
}

.info-item .label {
  font-weight: bold;
  min-width: 80px;
}

.behavior-detail {
  padding: 10px 0;
}

.behavior-header {
  text-align: center;
  margin-bottom: 20px;
}

.metrics {
  margin: 20px 0;
}

.metric-item {
  display: flex;
  align-items: center;
  margin-bottom: 15px;
}

.metric-label {
  min-width: 100px;
  color: #606266;
}

.metric-value {
  font-size: 18px;
  font-weight: bold;
  margin-right: 10px;
}

.metric-value.positive {
  color: #67c23a;
}

.metric-value.negative {
  color: #f56c6c;
}

.emotion-label {
  color: #909399;
  font-size: 14px;
}

.chart-container {
  margin-top: 20px;
}

.opportunity-item {
  padding: 15px;
  margin-bottom: 15px;
  background: #f5f7fa;
  border-radius: 4px;
}

.opportunity-item:last-child {
  margin-bottom: 0;
}

.opp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.opp-header h3 {
  margin: 0;
  font-size: 16px;
}

.opp-reason {
  color: #606266;
  margin: 10px 0;
}

.opp-action {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #409eff;
  font-weight: bold;
}

.mt-20 {
  margin-top: 20px;
}
</style>
