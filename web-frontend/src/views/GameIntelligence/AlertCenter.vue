<template>
  <div class="alert-center">
    <h1>🚨 预警中心</h1>

    <!-- 筛选器 -->
    <el-card class="box-card">
      <el-form :inline="true">
        <el-form-item label="预警类型">
          <el-select v-model="filters.type" placeholder="全部" @change="loadAlerts">
            <el-option label="全部" value="" />
            <el-option label="风险预警" value="risk" />
            <el-option label="机会预警" value="opportunity" />
          </el-select>
        </el-form-item>

        <el-form-item label="预警级别">
          <el-select v-model="filters.level" placeholder="全部级别" @change="loadAlerts">
            <el-option label="全部级别" value="" />
            <el-option label="紧急" value="critical" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="loadAlerts" :loading="loading">
            <el-icon><Refresh /></el-icon>
            刷新
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 预警统计 -->
    <el-row :gutter="20" class="mt-20">
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic title="总预警数" :value="statistics.total_alerts || 0" suffix="条" />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="风险预警"
            :value="statistics.by_type?.risk || 0"
            suffix="条"
            value-style="color: #f56c6c"
          />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="机会预警"
            :value="statistics.by_type?.opportunity || 0"
            suffix="条"
            value-style="color: #67c23a"
          />
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <el-statistic
            title="紧急预警"
            :value="statistics.by_level?.critical || 0"
            suffix="条"
            value-style="color: #e6a23c"
          />
        </el-card>
      </el-col>
    </el-row>

    <!-- 预警列表 -->
    <el-card class="box-card mt-20">
      <template #header>
        <span>📋 预警列表 ({{ alerts.length }}条)</span>
      </template>

      <div v-if="alerts.length > 0" class="alerts-list">
        <div
          v-for="alert in alerts"
          :key="alert.alert_id"
          :class="['alert-item', `alert-${alert.level}`]"
        >
          <div class="alert-header">
            <div class="alert-title">
              <span class="level-icon">{{ getLevelIcon(alert.level) }}</span>
              <span class="level-badge">{{ translateLevel(alert.level) }}</span>
              <span class="type-badge" :class="`type-${alert.type}`">
                {{ translateType(alert.type) }}
              </span>
              <h3>{{ alert.title }}</h3>
            </div>
            <div class="alert-time">{{ formatTime(alert.created_at) }}</div>
          </div>

          <div class="alert-content">
            <p class="alert-message">{{ alert.message }}</p>

            <div v-if="alert.symbols && alert.symbols.length > 0" class="alert-symbols">
              <span class="label">相关股票:</span>
              <el-tag v-for="symbol in alert.symbols" :key="symbol" size="small">
                {{ symbol }}
              </el-tag>
            </div>

            <div class="alert-action-text">
              <el-icon><InfoFilled /></el-icon>
              <span>{{ alert.action }}</span>
            </div>
          </div>

          <div class="alert-footer">
            <el-button size="small" @click="viewDetails(alert)">查看详情</el-button>
            <el-button
              size="small"
              :type="alert.type === 'opportunity' ? 'success' : 'warning'"
              v-if="alert.type === 'opportunity'"
            >
              创建池子
            </el-button>
            <el-button size="small" plain @click="ignoreAlert(alert)">忽略</el-button>
          </div>
        </div>
      </div>

      <el-empty v-else description="暂无预警" />
    </el-card>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailsVisible" title="预警详情" width="600px">
      <div v-if="selectedAlert">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="预警ID">{{ selectedAlert.alert_id }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag :type="selectedAlert.type === 'risk' ? 'danger' : 'success'">
              {{ translateType(selectedAlert.type) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="级别">
            <el-tag :type="getAlertTagType(selectedAlert.level)">
              {{ translateLevel(selectedAlert.level) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="标题">{{ selectedAlert.title }}</el-descriptions-item>
          <el-descriptions-item label="消息">{{ selectedAlert.message }}</el-descriptions-item>
          <el-descriptions-item label="建议">{{ selectedAlert.action }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ selectedAlert.created_at }}</el-descriptions-item>
        </el-descriptions>

        <div v-if="selectedAlert.details" class="details-section">
          <h4>详细信息</h4>
          <pre>{{ JSON.stringify(selectedAlert.details, null, 2) }}</pre>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAlerts, getAlertStatistics } from '@/services/game-intelligence'
import { ElMessage } from 'element-plus'

const loading = ref(false)
const alerts = ref<any[]>([])
const statistics = ref<any>({})
const detailsVisible = ref(false)
const selectedAlert = ref<any>(null)

const filters = ref({
  type: '',
  level: ''
})

const loadAlerts = async () => {
  loading.value = true
  try {
    const res = await getAlerts()
    if (res.success) {
      let data = res.data || []

      // 应用筛选
      if (filters.value.type) {
        data = data.filter((a: any) => a.type === filters.value.type)
      }
      if (filters.value.level) {
        data = data.filter((a: any) => a.level === filters.value.level)
      }

      alerts.value = data
    }
  } catch (error) {
    console.error('加载预警失败:', error)
    ElMessage.error('加载预警失败')
  } finally {
    loading.value = false
  }
}

const loadStatistics = async () => {
  try {
    const res = await getAlertStatistics()
    if (res.success) {
      statistics.value = res.data || {}
    }
  } catch (error) {
    console.error('加载统计失败:', error)
  }
}

const viewDetails = (alert: any) => {
  selectedAlert.value = alert
  detailsVisible.value = true
}

const ignoreAlert = (_alert: any) => {
  ElMessage.success('已忽略预警')
  // TODO: 调用API标记为已读
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

const translateType = (type: string) => {
  return type === 'risk' ? '风险' : '机会'
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

const formatTime = (time: string) => {
  if (!time) return '-'
  const date = new Date(time)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (minutes < 1440) return `${Math.floor(minutes / 60)}小时前`
  return date.toLocaleString()
}

onMounted(() => {
  loadAlerts()
  loadStatistics()
})
</script>

<style scoped>
.alert-center {
  padding: 20px;
}

.stat-card {
  text-align: center;
}

.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.alert-item {
  border: 2px solid;
  border-radius: 8px;
  padding: 20px;
  transition: all 0.3s;
}

.alert-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.alert-critical {
  border-color: #f56c6c;
  background: #fef0f0;
}

.alert-high {
  border-color: #e6a23c;
  background: #fdf6ec;
}

.alert-medium {
  border-color: #409eff;
  background: #ecf5ff;
}

.alert-low {
  border-color: #67c23a;
  background: #f0f9ff;
}

.alert-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 15px;
}

.alert-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.level-icon {
  font-size: 20px;
}

.level-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.type-badge {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.type-risk {
  background: #f56c6c;
  color: white;
}

.type-opportunity {
  background: #67c23a;
  color: white;
}

.alert-title h3 {
  margin: 0;
  font-size: 16px;
}

.alert-time {
  color: #909399;
  font-size: 12px;
  white-space: nowrap;
}

.alert-content {
  margin-bottom: 15px;
}

.alert-message {
  color: #606266;
  margin: 0 0 10px 0;
  line-height: 1.6;
}

.alert-symbols {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 10px 0;
}

.alert-symbols .label {
  color: #909399;
  font-size: 14px;
}

.alert-action-text {
  display: flex;
  align-items: center;
  gap: 5px;
  color: #409eff;
  font-weight: bold;
  margin-top: 10px;
}

.alert-footer {
  display: flex;
  gap: 10px;
}

.details-section {
  margin-top: 20px;
}

.details-section h4 {
  margin-bottom: 10px;
}

.details-section pre {
  background: #f5f7fa;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

.mt-20 {
  margin-top: 20px;
}
</style>
