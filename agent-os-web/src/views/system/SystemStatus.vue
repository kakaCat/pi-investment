<template>
  <div class="system-status">
    <!-- 服务健康状态 -->
    <el-row :gutter="20">
      <el-col :span="6" v-for="service in services" :key="service.name">
        <el-card shadow="hover">
          <div class="service-card">
            <el-icon :size="40" :color="service.status === 'healthy' ? '#67c23a' : '#f56c6c'">
              <CircleCheck v-if="service.status === 'healthy'" />
              <CircleClose v-else />
            </el-icon>
            <h3>{{ service.name }}</h3>
            <el-tag :type="service.status === 'healthy' ? 'success' : 'danger'">
              {{ service.status === 'healthy' ? '正常' : '异常' }}
            </el-tag>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统资源（来自资源配额） -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>资源配额使用</span>
      </template>
      <el-empty v-if="!loading && quotas.length === 0" description="暂无配额数据" />
      <div v-for="quota in quotas" :key="quota.id" class="resource-item">
        <div class="resource-label">
          <span>{{ quota.namespace }} / {{ quota.resource_type }} ({{ quota.unit }})</span>
          <span class="resource-usage">{{ quota.used }} / {{ quota.limit }}</span>
        </div>
        <el-progress :percentage="getUsagePercent(quota)" :color="getProgressColor(getUsagePercent(quota))" />
      </div>
    </el-card>

    <!-- 系统信息 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>系统信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="系统状态">
          <el-tag :type="systemStatus === 'ok' ? 'success' : 'danger'">{{ systemStatus }}</el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="版本">{{ systemInfo.version }}</el-descriptions-item>
        <el-descriptions-item label="运行时间">{{ formatUptime(uptime) }}</el-descriptions-item>
        <el-descriptions-item label="浏览器">{{ systemInfo.browser }}</el-descriptions-item>
        <el-descriptions-item label="用户代理">{{ systemInfo.userAgent }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { systemApi } from '@/api/system'

const loading = ref(false)
const services = ref<any[]>([])
const quotas = ref<any[]>([])
const systemStatus = ref('unknown')
const uptime = ref(0)
const systemInfo = ref({
  version: '-',
  browser: 'unknown',
  userAgent: '',
})

const getUsagePercent = (quota: any) => {
  if (!quota.limit) return 0
  return Math.min(Math.round((quota.used / quota.limit) * 100), 100)
}

const getProgressColor = (percentage: number) => {
  if (percentage < 60) return '#67c23a'
  if (percentage < 80) return '#e6a23c'
  return '#f56c6c'
}

const formatUptime = (seconds: number) => {
  if (!seconds) return '-'
  const days = Math.floor(seconds / 86400)
  const hours = Math.floor((seconds % 86400) / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (days > 0) return `${days}天${hours}小时`
  if (hours > 0) return `${hours}小时${minutes}分钟`
  return `${minutes}分钟`
}

const loadStatus = async () => {
  loading.value = true
  try {
    // 系统状态
    const status = await systemApi.getStatus()
    systemStatus.value = status.status || 'unknown'
    uptime.value = status.uptime || 0
    systemInfo.value.version = status.version || '-'
    services.value = (status.components || []).map((c: any) => ({
      name: c.name,
      status: c.status === 'healthy' ? 'healthy' : 'unhealthy',
    }))

    // 资源配额
    const quotaResult = await systemApi.getQuotas()
    quotas.value = quotaResult.quotas || []
  } catch (e) {
    console.error('加载系统状态失败:', e)
    ElMessage.error('加载系统状态失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  systemInfo.value.browser = navigator.userAgent.split(' ').pop() || 'unknown'
  systemInfo.value.userAgent = navigator.userAgent.substring(0, 100)
  loadStatus()
})
</script>

<style scoped>
.system-status {
  padding: 20px;
}
.service-card {
  text-align: center;
  padding: 10px 0;
}
.service-card h3 {
  margin: 10px 0;
  font-size: 16px;
}
.service-card .uptime {
  color: #909399;
  font-size: 12px;
}
.resource-item {
  margin-bottom: 16px;
}
.resource-label {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
  font-size: 13px;
}
.resource-usage {
  color: #909399;
}
</style>
