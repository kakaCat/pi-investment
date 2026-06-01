<!-- web-frontend/src/views/BacktestCenter/DiagnosisCards.vue -->
<template>
  <div class="diagnosis-cards">
    <el-row :gutter="16">
      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="card-header">
            <span class="label">年化收益</span>
            <el-icon :class="['icon', metrics.annualReturn >= 0 ? 'text-up' : 'text-down']">
              <TrendCharts v-if="metrics.annualReturn >= 0" />
              <Bottom v-else />
            </el-icon>
          </div>
          <div :class="['value', metrics.annualReturn >= 0 ? 'text-up' : 'text-down']">
            {{ formatPercent(metrics.annualReturn) }}
          </div>
          <div class="benchmark">
            基准: {{ formatPercent(benchmark.annualReturn) }}
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="card-header">
            <span class="label">夏普比率</span>
            <el-icon class="icon">
              <DataAnalysis />
            </el-icon>
          </div>
          <div :class="['value', getSharpeColor(metrics.sharpeRatio)]">
            {{ metrics.sharpeRatio.toFixed(2) }}
          </div>
          <div class="benchmark">
            基准: {{ benchmark.sharpeRatio.toFixed(2) }}
          </div>
          <div v-if="metrics.sharpeRatio < 1.0" class="warning-text">
            ⚠️ 不如买指数
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="card-header">
            <span class="label">最大回撤</span>
            <el-icon class="icon text-down">
              <Bottom />
            </el-icon>
          </div>
          <div class="value text-down">
            {{ formatPercent(metrics.maxDrawdown) }}
          </div>
          <div class="benchmark">
            基准: {{ formatPercent(benchmark.maxDrawdown) }}
          </div>
        </el-card>
      </el-col>

      <el-col :span="6">
        <el-card shadow="hover" class="metric-card rating-card">
          <div class="card-header">
            <span class="label">综合评级</span>
          </div>
          <div :class="['rating-badge', `rating-${ratings.overall}`]">
            {{ ratings.overall }}
          </div>
          <div class="rating-desc">
            {{ getRatingText(ratings.overall) }}
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { TrendCharts, Bottom, DataAnalysis } from '@element-plus/icons-vue'

interface Props {
  metrics: {
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
    totalTrades: number
  }
  benchmark: {
    name: string
    annualReturn: number
    sharpeRatio: number
    maxDrawdown: number
  }
  ratings: {
    overall: 'A' | 'B' | 'C' | 'D'
    return: string
    risk: string
    stability: string
  }
}

defineProps<Props>()

const formatPercent = (value: number) => {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(2)}%`
}

const getSharpeColor = (sharpe: number) => {
  if (sharpe >= 1.5) return 'text-excellent'
  if (sharpe >= 1.0) return 'text-good'
  if (sharpe >= 0.5) return 'text-moderate'
  return 'text-poor'
}

const getRatingText = (rating: string) => {
  const mapping: Record<string, string> = {
    'A': '优秀',
    'B': '良好',
    'C': '一般',
    'D': '较差'
  }
  return mapping[rating] || rating
}
</script>

<style scoped>
.diagnosis-cards {
  margin-bottom: 20px;
}

.metric-card {
  text-align: center;
  padding: 16px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.label {
  font-size: 14px;
  color: #606266;
}

.icon {
  font-size: 20px;
}

.value {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 8px;
}

.benchmark {
  font-size: 12px;
  color: #909399;
}

.warning-text {
  margin-top: 8px;
  font-size: 12px;
  color: #E6A23C;
  font-weight: 500;
}

.text-up {
  color: #F56C6C;
}

.text-down {
  color: #67C23A;
}

.text-excellent {
  color: #67C23A;
}

.text-good {
  color: #409EFF;
}

.text-moderate {
  color: #E6A23C;
}

.text-poor {
  color: #F56C6C;
}

.rating-card {
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.rating-badge {
  font-size: 48px;
  font-weight: bold;
  margin: 12px 0;
}

.rating-A {
  color: #67C23A;
}

.rating-B {
  color: #409EFF;
}

.rating-C {
  color: #E6A23C;
}

.rating-D {
  color: #F56C6C;
}

.rating-desc {
  font-size: 14px;
  color: #909399;
}
</style>
