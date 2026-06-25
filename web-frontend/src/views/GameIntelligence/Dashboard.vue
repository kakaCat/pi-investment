<template>
  <div class="game-intelligence-dashboard">
    <h1>📊 博弈智能系统 - 运行总览</h1>

    <el-row :gutter="20">
      <!-- 定时任务状态 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <div class="card-header">
              <span>⏰ 定时任务状态</span>
              <el-tag :type="systemStatus === 'running' ? 'success' : 'danger'">
                {{ systemStatus === 'running' ? '运行中' : '已停止' }}
              </el-tag>
            </div>
          </template>

          <div v-for="task in tasks" :key="task.name" class="task-item">
            <div class="task-info">
              <span class="task-name">{{ task.name }}</span>
              <el-tag :type="task.status === 'success' ? 'success' : 'info'" size="small">
                {{ task.status === 'success' ? '已执行' : '等待中' }}
              </el-tag>
            </div>
            <div class="task-time">
              {{ task.lastRun ? `上次: ${task.lastRun}` : `下次: ${task.nextRun}` }}
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 今日统计 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <span>📈 今日统计</span>
          </template>

          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-value">{{ stats.decisions }}</div>
              <div class="stat-label">自动决策</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.knowledge }}</div>
              <div class="stat-label">知识提取</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.alerts }}</div>
              <div class="stat-label">预警触发</div>
            </div>
            <div class="stat-item">
              <div class="stat-value">{{ stats.successRate }}%</div>
              <div class="stat-label">成功率</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" class="mt-20">
      <!-- 学习进展 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <span>🎓 学习进展</span>
          </template>

          <div class="learning-stats">
            <div class="stat-row">
              <span>知识库总数:</span>
              <span class="value">{{ learningStats.totalKnowledge }}条</span>
            </div>
            <div class="stat-row">
              <span>高置信度知识:</span>
              <span class="value success">{{ learningStats.highConfidence }}条</span>
            </div>
            <div class="stat-row">
              <span>本周新增:</span>
              <span class="value primary">{{ learningStats.weeklyNew }}条</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 对手行为概览 -->
      <el-col :span="12">
        <el-card class="box-card">
          <template #header>
            <span>👥 对手行为概览</span>
          </template>

          <div v-if="opponentData" class="opponent-overview">
            <div class="opponent-item">
              <span class="label">散户行为:</span>
              <el-tag :type="getRetailTagType(opponentData.retail?.behavior)">
                {{ translateBehavior(opponentData.retail?.behavior) }}
              </el-tag>
            </div>
            <div class="opponent-item">
              <span class="label">机构行为:</span>
              <el-tag :type="getInstitutionTagType(opponentData.institution?.behavior)">
                {{ translateBehavior(opponentData.institution?.behavior) }}
              </el-tag>
            </div>
            <div class="opponent-item">
              <span class="label">市场阶段:</span>
              <el-tag type="info">{{ translatePhase(opponentData.market_phase) }}</el-tag>
            </div>
          </div>
          <div v-else class="loading">加载中...</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最新预警 -->
    <el-card class="box-card mt-20">
      <template #header>
        <div class="card-header">
          <span>🚨 最新预警</span>
          <el-button size="small" @click="loadAlerts">刷新</el-button>
        </div>
      </template>

      <el-timeline v-if="alerts.length > 0">
        <el-timeline-item
          v-for="alert in alerts"
          :key="alert.alert_id"
          :timestamp="formatTime(alert.created_at)"
          :type="getAlertTimelineType(alert.level)"
        >
          <div class="alert-item">
            <h4>{{ getLevelIcon(alert.level) }} {{ alert.title }}</h4>
            <p>{{ alert.message }}</p>
            <div class="alert-footer">
              <el-tag :type="getAlertTagType(alert.level)" size="small">
                {{ translateLevel(alert.level) }}
              </el-tag>
              <span class="alert-action">{{ alert.action }}</span>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无预警" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { getAlerts, getKnowledgeSummary, getOpponentBehavior } from '@/services/game-intelligence'

const systemStatus = ref('running')
const tasks = ref([
  { name: '早盘分析 (9:00)', status: 'success', lastRun: '09:00', nextRun: '明天09:00' },
  { name: '实时监控 (每5分钟)', status: 'success', lastRun: '14:55', nextRun: '15:00' },
  { name: '每日学习 (18:00)', status: 'waiting', lastRun: null, nextRun: '今天18:00' }
])

const stats = ref({
  decisions: 0,
  knowledge: 0,
  alerts: 0,
  successRate: 0
})

const learningStats = ref({
  totalKnowledge: 0,
  highConfidence: 0,
  weeklyNew: 0
})

const opponentData = ref<any>(null)
const alerts = ref<any[]>([])

let refreshTimer: any = null

const loadAlerts = async () => {
  try {
    const res = await getAlerts()
    if (res.success) {
      alerts.value = res.data.slice(0, 10)
      stats.value.alerts = res.data.length
    }
  } catch (error) {
    console.error('加载预警失败:', error)
  }
}

const loadKnowledgeSummary = async () => {
  try {
    const res = await getKnowledgeSummary()
    if (res.success) {
      learningStats.value = {
        totalKnowledge: res.data.total_knowledge || 0,
        highConfidence: res.data.high_confidence || 0,
        weeklyNew: 5 // TODO: 从API获取
      }
      stats.value.knowledge = res.data.total_knowledge || 0
    }
  } catch (error) {
    console.error('加载知识摘要失败:', error)
  }
}

const loadOpponentBehavior = async () => {
  try {
    const res = await getOpponentBehavior()
    if (res.success) {
      opponentData.value = res.data
    }
  } catch (error) {
    console.error('加载对手行为失败:', error)
  }
}

const loadAllData = async () => {
  await Promise.all([
    loadAlerts(),
    loadKnowledgeSummary(),
    loadOpponentBehavior()
  ])
}

const getAlertTimelineType = (level: string) => {
  const map: Record<string, string> = {
    'critical': 'danger',
    'high': 'warning',
    'medium': 'primary',
    'low': 'success'
  }
  return map[level] || 'info'
}

const getAlertTagType = (level: string) => {
  const map: Record<string, any> = {
    'critical': 'danger',
    'high': 'warning',
    'medium': 'info',
    'low': 'success'
  }
  return map[level] || 'info'
}

const getLevelIcon = (level: string) => {
  const map: Record<string, string> = {
    'critical': '🔴',
    'high': '🟠',
    'medium': '🟡',
    'low': '🟢'
  }
  return map[level] || '⚪'
}

const translateLevel = (level: string) => {
  const map: Record<string, string> = {
    'critical': '紧急',
    'high': '高',
    'medium': '中',
    'low': '低'
  }
  return map[level] || level
}

const translateBehavior = (behavior: string) => {
  const map: Record<string, string> = {
    'panic_selling': '恐慌抛售',
    'fomo_buying': '追涨买入',
    'accumulating': '建仓',
    'distributing': '出货',
    'neutral': '中性'
  }
  return map[behavior] || behavior || '-'
}

const translatePhase = (phase: string) => {
  const map: Record<string, string> = {
    'accumulation': '吸筹',
    'markup': '拉升',
    'distribution': '派发',
    'markdown': '下跌'
  }
  return map[phase] || phase || '-'
}

const getRetailTagType = (behavior: string) => {
  if (behavior === 'panic_selling') return 'danger'
  if (behavior === 'fomo_buying') return 'warning'
  return 'info'
}

const getInstitutionTagType = (behavior: string) => {
  if (behavior === 'accumulating') return 'success'
  if (behavior === 'distributing') return 'danger'
  return 'info'
}

const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}小时前`
  return date.toLocaleDateString()
}

onMounted(() => {
  loadAllData()
  // 每30秒刷新一次
  refreshTimer = setInterval(loadAllData, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>

<style scoped>
.game-intelligence-dashboard {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-item {
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.task-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}

.task-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.task-name {
  font-weight: bold;
}

.task-time {
  color: #909399;
  font-size: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
}

.stat-item {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}

.stat-label {
  color: #909399;
  font-size: 14px;
  margin-top: 5px;
}

.learning-stats,
.opponent-overview {
  padding: 10px 0;
}

.stat-row,
.opponent-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding: 8px 0;
}

.stat-row:last-child,
.opponent-item:last-child {
  margin-bottom: 0;
}

.stat-row .value {
  font-weight: bold;
  font-size: 16px;
}

.value.success {
  color: #67c23a;
}

.value.primary {
  color: #409eff;
}

.opponent-item .label {
  color: #606266;
}

.alert-item h4 {
  margin: 0 0 8px 0;
  font-size: 16px;
}

.alert-item p {
  margin: 0 0 8px 0;
  color: #606266;
}

.alert-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.alert-action {
  color: #909399;
  font-size: 12px;
}

.mt-20 {
  margin-top: 20px;
}

.loading {
  text-align: center;
  color: #909399;
  padding: 20px;
}
</style>
