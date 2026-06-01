<template>
  <div class="diagnosis-tab">
    <div class="toolbar">
      <el-button
        type="primary"
        :loading="loading"
        :disabled="!backtestResult"
        @click="handleRunDiagnosis"
      >
        <el-icon><DataAnalysis /></el-icon>
        运行诊断
      </el-button>

      <el-button
        v-if="diagnosisResult"
        @click="handleViewReport"
      >
        <el-icon><Document /></el-icon>
        查看报告
      </el-button>
    </div>

    <div v-if="!diagnosisResult && !loading" class="empty-state">
      <el-empty description="暂无诊断结果">
        <el-button type="primary" @click="handleRunDiagnosis" :disabled="!backtestResult">
          运行诊断
        </el-button>
      </el-empty>
    </div>

    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <div v-if="diagnosisResult && !loading" class="diagnosis-content">
      <!-- 关键指标卡片 -->
      <DiagnosisCards
        v-if="diagnosisResult.benchmark"
        :metrics="diagnosisResult.metrics"
        :benchmark="diagnosisResult.benchmark"
        :ratings="diagnosisResult.ratings"
      />

      <!-- 诊断结论 -->
      <el-card shadow="never" class="conclusion-card">
        <template #header>
          <div class="card-header">
            <span class="title">诊断结论</span>
            <el-tag :type="getRatingType(diagnosisResult.ratings.overall)" size="large">
              {{ diagnosisResult.ratings.overall }} 级
            </el-tag>
          </div>
        </template>

        <div class="conclusion-text">
          {{ diagnosisResult.diagnosis.conclusion }}
        </div>

        <el-divider />

        <!-- 优势 -->
        <div v-if="diagnosisResult.diagnosis.strengths.length > 0" class="section">
          <h4 class="section-title">
            <el-icon color="#67C23A"><CircleCheck /></el-icon>
            优势
          </h4>
          <ul class="list">
            <li v-for="(item, index) in diagnosisResult.diagnosis.strengths" :key="index" class="list-item strength">
              {{ item }}
            </li>
          </ul>
        </div>

        <!-- 劣势 -->
        <div v-if="diagnosisResult.diagnosis.weaknesses.length > 0" class="section">
          <h4 class="section-title">
            <el-icon color="#F56C6C"><CircleClose /></el-icon>
            劣势
          </h4>
          <ul class="list">
            <li v-for="(item, index) in diagnosisResult.diagnosis.weaknesses" :key="index" class="list-item weakness">
              {{ item }}
            </li>
          </ul>
        </div>

        <!-- 优化建议 -->
        <div v-if="diagnosisResult.diagnosis.suggestions.length > 0" class="section">
          <h4 class="section-title">
            <el-icon color="#409EFF"><InfoFilled /></el-icon>
            优化建议
          </h4>
          <ol class="list suggestions">
            <li v-for="(item, index) in diagnosisResult.diagnosis.suggestions" :key="index" class="list-item">
              {{ item }}
            </li>
          </ol>
        </div>
      </el-card>

      <!-- 与基准对比 -->
      <el-card shadow="never" class="comparison-card">
        <template #header>
          <span class="title">与基准对比</span>
        </template>

        <el-table :data="comparisonData" stripe>
          <el-table-column prop="metric" label="指标" width="120" />
          <el-table-column prop="strategy" label="策略" align="right" />
          <el-table-column prop="benchmark" label="基准" align="right" />
          <el-table-column prop="diff" label="差值" align="right">
            <template #default="{ row }">
              <span :class="row.diffClass">{{ row.diff }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, Document, CircleCheck, CircleClose, InfoFilled } from '@element-plus/icons-vue'
import DiagnosisCards from './DiagnosisCards.vue'
import { runDiagnosis, type DiagnosisResult } from '@/services/api/diagnosis'

interface Props {
  backtestResult: any
}

const props = defineProps<Props>()

const loading = ref(false)
const diagnosisResult = ref<DiagnosisResult | null>(null)

const handleRunDiagnosis = async () => {
  if (!props.backtestResult) {
    ElMessage.warning('请先运行回测')
    return
  }

  loading.value = true
  try {
    const params = {
      symbol: props.backtestResult.symbol,
      startDate: props.backtestResult.startDate,
      endDate: props.backtestResult.endDate,
      strategyName: props.backtestResult.strategyName,
      benchmark: '000300.SH'
    }

    const result = await runDiagnosis(params)
    diagnosisResult.value = result
    ElMessage.success('诊断完成')
  } catch (error: any) {
    ElMessage.error(error.message || '诊断失败')
  } finally {
    loading.value = false
  }
}

const handleViewReport = () => {
  if (diagnosisResult.value?.reportPath) {
    ElMessage.info(`报告路径: ${diagnosisResult.value.reportPath}`)
  }
}

const getRatingType = (rating: string) => {
  const mapping: Record<string, any> = {
    'A': 'success',
    'B': 'primary',
    'C': 'warning',
    'D': 'danger'
  }
  return mapping[rating] || 'info'
}

const comparisonData = computed(() => {
  if (!diagnosisResult.value || !diagnosisResult.value.benchmark) return []

  const { metrics, benchmark } = diagnosisResult.value

  const formatPercent = (value: number) => {
    const sign = value >= 0 ? '+' : ''
    return `${sign}${(value * 100).toFixed(2)}%`
  }

  return [
    {
      metric: '年化收益',
      strategy: formatPercent(metrics.annualReturn),
      benchmark: formatPercent(benchmark.annualReturn),
      diff: formatPercent(metrics.annualReturn - benchmark.annualReturn),
      diffClass: metrics.annualReturn >= benchmark.annualReturn ? 'text-up' : 'text-down'
    },
    {
      metric: '夏普比率',
      strategy: metrics.sharpeRatio.toFixed(2),
      benchmark: benchmark.sharpeRatio.toFixed(2),
      diff: (metrics.sharpeRatio - benchmark.sharpeRatio).toFixed(2),
      diffClass: metrics.sharpeRatio >= benchmark.sharpeRatio ? 'text-up' : 'text-down'
    },
    {
      metric: '最大回撤',
      strategy: formatPercent(metrics.maxDrawdown),
      benchmark: formatPercent(benchmark.maxDrawdown),
      diff: formatPercent(metrics.maxDrawdown - benchmark.maxDrawdown),
      diffClass: metrics.maxDrawdown >= benchmark.maxDrawdown ? 'text-up' : 'text-down'
    }
  ]
})
</script>

<style scoped>
.diagnosis-tab {
  padding: 20px;
}

.toolbar {
  margin-bottom: 20px;
  display: flex;
  gap: 12px;
}

.empty-state,
.loading-state {
  padding: 60px 0;
}

.diagnosis-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.title {
  font-size: 16px;
  font-weight: 600;
}

.conclusion-text {
  font-size: 15px;
  line-height: 1.8;
  color: #303133;
  padding: 12px;
  background: #F5F7FA;
  border-radius: 4px;
}

.section {
  margin-top: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 12px;
}

.list {
  margin: 0;
  padding-left: 24px;
}

.list-item {
  margin-bottom: 8px;
  line-height: 1.6;
}

.strength {
  color: #67C23A;
}

.weakness {
  color: #F56C6C;
}

.suggestions {
  color: #409EFF;
}

.text-up {
  color: #F56C6C;
  font-weight: 500;
}

.text-down {
  color: #67C23A;
  font-weight: 500;
}

.comparison-card {
  margin-top: 20px;
}
</style>
