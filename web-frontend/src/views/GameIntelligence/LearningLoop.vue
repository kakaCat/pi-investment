<template>
  <div class="learning-loop">
    <h1>🧠 学习闭环进展</h1>

    <!-- 学习流程图 -->
    <el-card class="box-card">
      <template #header>
        <span>🔄 学习循环流程</span>
      </template>

      <div class="loop-diagram">
        <div class="loop-step">
          <div class="step-box">
            <h3>1. 做决策</h3>
            <p>查询知识库<br/>应用经验</p>
            <div class="step-count">{{ loopStats.decisions }}次</div>
          </div>
          <div class="arrow">→</div>
        </div>

        <div class="loop-step">
          <div class="step-box">
            <h3>2. 记录执行</h3>
            <p>完整上下文<br/>等待评估</p>
          </div>
          <div class="arrow">→</div>
        </div>

        <div class="loop-step">
          <div class="step-box">
            <h3>3. 自动评估</h3>
            <p>7天后评估<br/>计算收益</p>
            <div class="step-count">{{ loopStats.evaluated }}次</div>
          </div>
          <div class="arrow">→</div>
        </div>

        <div class="loop-step">
          <div class="step-box success">
            <h3>4. 提取知识</h3>
            <p>成功决策<br/>形成规则</p>
            <div class="step-count">{{ loopStats.knowledge }}条</div>
          </div>
          <div class="arrow-up">↑</div>
        </div>

        <div class="loop-step reverse">
          <div class="arrow">←</div>
          <div class="step-box">
            <h3>5. 学习优化</h3>
            <p>分析模式<br/>优化参数</p>
            <div class="step-count">{{ loopStats.optimizations }}次</div>
          </div>
        </div>
      </div>
    </el-card>

    <el-row :gutter="20" class="mt-20">
      <!-- 知识库统计 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <span>📚 知识库统计</span>
          </template>

          <div class="knowledge-stats">
            <el-statistic-group>
              <el-statistic title="总知识" :value="knowledgeSummary.total_knowledge || 0" suffix="条" />
              <el-statistic
                title="本周新增"
                :value="knowledgeSummary.weekly_new || 0"
                suffix="条"
                value-style="color: #409eff"
              />
            </el-statistic-group>

            <div class="confidence-distribution mt-20">
              <h4>按置信度分布</h4>
              <div class="progress-item">
                <span class="label">高 (≥80%)</span>
                <el-progress
                  :percentage="getPercentage(knowledgeSummary.by_confidence?.high, knowledgeSummary.total_knowledge)"
                  color="#67c23a"
                />
                <span class="count">{{ knowledgeSummary.by_confidence?.high || 0 }}条</span>
              </div>
              <div class="progress-item">
                <span class="label">中 (50-80%)</span>
                <el-progress
                  :percentage="getPercentage(knowledgeSummary.by_confidence?.medium, knowledgeSummary.total_knowledge)"
                  color="#e6a23c"
                />
                <span class="count">{{ knowledgeSummary.by_confidence?.medium || 0 }}条</span>
              </div>
              <div class="progress-item">
                <span class="label">低 (<50%)</span>
                <el-progress
                  :percentage="getPercentage(knowledgeSummary.by_confidence?.low, knowledgeSummary.total_knowledge)"
                  color="#f56c6c"
                />
                <span class="count">{{ knowledgeSummary.by_confidence?.low || 0 }}条</span>
              </div>
            </div>

            <div class="domain-distribution mt-20">
              <h4>按领域分布</h4>
              <div ref="domainChartRef" style="width: 100%; height: 200px;"></div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 学习报告 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>📊 学习报告</span>
              <el-button size="small" @click="loadLearningReport">刷新</el-button>
            </div>
          </template>

          <div v-if="learningReport" class="learning-report">
            <div class="report-item">
              <span class="label">总决策数:</span>
              <span class="value">{{ learningReport.total_decisions || 0 }}条</span>
            </div>
            <div class="report-item">
              <span class="label">已评估:</span>
              <span class="value">{{ learningReport.evaluated_decisions || 0 }}条</span>
            </div>
            <div class="report-item">
              <span class="label">总体成功率:</span>
              <span class="value success">{{ (learningReport.overall_success_rate * 100).toFixed(1) }}%</span>
            </div>

            <div class="trend-chart mt-20">
              <h4>成功率趋势</h4>
              <div ref="trendChartRef" style="width: 100%; height: 200px;"></div>
            </div>
          </div>
          <el-empty v-else description="暂无学习报告" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 最新学到的知识 -->
    <el-card class="box-card mt-20">
      <template #header>
        <span>📝 最新学到的知识</span>
      </template>

      <div v-if="knowledgeList.length > 0" class="knowledge-list">
        <div v-for="item in knowledgeList" :key="item.id" class="knowledge-item">
          <div class="knowledge-header">
            <el-tag :type="getConfidenceType(item.confidence)">
              {{ (item.confidence * 100).toFixed(0) }}%
            </el-tag>
            <span class="knowledge-title">{{ item.rule }}</span>
          </div>
          <div class="knowledge-body">
            <p class="reason">{{ item.reason }}</p>
            <div class="knowledge-meta">
              <span>验证 {{ item.validation_count }}次，成功 {{ item.success_count }}次</span>
              <span class="domain">{{ item.domain }}</span>
            </div>
          </div>
        </div>
      </div>
      <el-empty v-else description="暂无知识" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { getKnowledgeActive, getKnowledgeSummary, getLearningReport } from '@/services/game-intelligence'
import * as echarts from 'echarts'

const loopStats = ref({
  decisions: 15,
  evaluated: 10,
  knowledge: 8,
  optimizations: 3
})

const knowledgeSummary = ref<any>({})
const learningReport = ref<any>(null)
const knowledgeList = ref<any[]>([])

const domainChartRef = ref<HTMLElement>()
const trendChartRef = ref<HTMLElement>()

let domainChart: any = null
let trendChart: any = null

const loadKnowledgeSummary = async () => {
  try {
    const res = await getKnowledgeSummary()
    if (res.success) {
      knowledgeSummary.value = res.data
      await nextTick()
      initDomainChart()
    }
  } catch (error) {
    console.error('加载知识摘要失败:', error)
  }
}

const loadLearningReport = async () => {
  try {
    const res = await getLearningReport()
    if (res.success) {
      learningReport.value = res.data
      await nextTick()
      initTrendChart()
    }
  } catch (error) {
    console.error('加载学习报告失败:', error)
  }
}

const loadKnowledgeList = async () => {
  try {
    const res = await getKnowledgeActive()
    if (res.success) {
      knowledgeList.value = (res.data || []).slice(0, 5)
    }
  } catch (error) {
    console.error('加载知识列表失败:', error)
  }
}

const initDomainChart = () => {
  if (!domainChartRef.value) return

  if (!domainChart) {
    domainChart = echarts.init(domainChartRef.value)
  }

  const byDomain = knowledgeSummary.value.by_domain || {}
  const data = Object.entries(byDomain).map(([name, value]) => ({ name, value }))

  domainChart.setOption({
    tooltip: {
      trigger: 'item'
    },
    series: [{
      type: 'pie',
      radius: '60%',
      data,
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

const initTrendChart = () => {
  if (!trendChartRef.value) return

  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  // 模拟趋势数据
  const dates = ['Day1', 'Day10', 'Day20', 'Day30']
  const successRates = [50, 60, 72, 85]

  trendChart.setOption({
    tooltip: {
      trigger: 'axis'
    },
    xAxis: {
      type: 'category',
      data: dates
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: {
        formatter: '{value}%'
      }
    },
    series: [{
      data: successRates,
      type: 'line',
      smooth: true,
      areaStyle: {},
      itemStyle: {
        color: '#409eff'
      }
    }]
  })
}

const getPercentage = (value: number, total: number) => {
  if (!total) return 0
  return Math.round((value / total) * 100)
}

const getConfidenceType = (confidence: number) => {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.5) return 'warning'
  return 'danger'
}

onMounted(() => {
  loadKnowledgeSummary()
  loadLearningReport()
  loadKnowledgeList()
})

onUnmounted(() => {
  if (domainChart) domainChart.dispose()
  if (trendChart) trendChart.dispose()
})
</script>

<style scoped>
.learning-loop {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loop-diagram {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 30px 20px;
  flex-wrap: wrap;
  gap: 10px;
}

.loop-step {
  display: flex;
  align-items: center;
  gap: 10px;
}

.loop-step.reverse {
  flex-direction: row-reverse;
}

.step-box {
  border: 2px solid #409eff;
  border-radius: 8px;
  padding: 20px;
  background: white;
  min-width: 150px;
  text-align: center;
  transition: all 0.3s;
}

.step-box:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.step-box.success {
  border-color: #67c23a;
  background: #f0f9ff;
}

.step-box h3 {
  margin: 0 0 10px 0;
  font-size: 16px;
  color: #409eff;
}

.step-box.success h3 {
  color: #67c23a;
}

.step-box p {
  margin: 0;
  font-size: 12px;
  color: #606266;
  line-height: 1.5;
}

.step-count {
  margin-top: 10px;
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.step-box.success .step-count {
  color: #67c23a;
}

.arrow {
  font-size: 24px;
  color: #409eff;
  font-weight: bold;
}

.arrow-up {
  font-size: 24px;
  color: #67c23a;
  font-weight: bold;
  writing-mode: vertical-rl;
}

.knowledge-stats,
.learning-report {
  padding: 10px 0;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}

.progress-item .label {
  min-width: 80px;
  font-size: 14px;
}

.progress-item .count {
  min-width: 40px;
  text-align: right;
  font-size: 14px;
  color: #606266;
}

.confidence-distribution h4,
.domain-distribution h4,
.trend-chart h4 {
  margin: 10px 0;
  font-size: 14px;
  color: #606266;
}

.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;
}

.report-item:last-child {
  border-bottom: none;
}

.report-item .label {
  color: #606266;
}

.report-item .value {
  font-size: 18px;
  font-weight: bold;
}

.report-item .value.success {
  color: #67c23a;
}

.knowledge-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.knowledge-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 15px;
  transition: all 0.3s;
}

.knowledge-item:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.knowledge-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.knowledge-title {
  font-weight: bold;
  font-size: 16px;
}

.knowledge-body .reason {
  color: #606266;
  margin: 10px 0;
  line-height: 1.6;
}

.knowledge-meta {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #909399;
}

.knowledge-meta .domain {
  color: #409eff;
}

.mt-20 {
  margin-top: 20px;
}
</style>
