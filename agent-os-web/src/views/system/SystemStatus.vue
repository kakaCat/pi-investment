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
            <p class="uptime">运行时间: {{ service.uptime }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 系统资源 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>系统资源</span>
      </template>
      <div class="resource-item">
        <span>CPU 使用率</span>
        <el-progress :percentage="resources.cpu" :color="getProgressColor(resources.cpu)" />
      </div>
      <div class="resource-item">
        <span>内存使用率</span>
        <el-progress :percentage="resources.memory" :color="getProgressColor(resources.memory)" />
      </div>
      <div class="resource-item">
        <span>磁盘使用率</span>
        <el-progress :percentage="resources.disk" :color="getProgressColor(resources.disk)" />
      </div>
    </el-card>

    <!-- 数据库连接池 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>数据库连接池</span>
      </template>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="活跃连接">{{ dbPool.active }}</el-descriptions-item>
        <el-descriptions-item label="空闲连接">{{ dbPool.idle }}</el-descriptions-item>
        <el-descriptions-item label="最大连接">{{ dbPool.max }}</el-descriptions-item>
        <el-descriptions-item label="等待队列">{{ dbPool.waiting }}</el-descriptions-item>
        <el-descriptions-item label="连接超时">{{ dbPool.timeout }}ms</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="dbPool.active < dbPool.max ? 'success' : 'warning'">
            {{ dbPool.active < dbPool.max ? '正常' : '接近上限' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <!-- 系统信息 -->
    <el-card style="margin-top: 20px">
      <template #header>
        <span>系统信息</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="版本">{{ systemInfo.version }}</el-descriptions-item>
        <el-descriptions-item label="启动时间">{{ formatTime(systemInfo.startTime) }}</el-descriptions-item>
        <el-descriptions-item label="操作系统">{{ systemInfo.os }}</el-descriptions-item>
        <el-descriptions-item label="Node 版本">{{ systemInfo.nodeVersion }}</el-descriptions-item>
        <el-descriptions-item label="浏览器">{{ systemInfo.browser }}</el-descriptions-item>
        <el-descriptions-item label="用户代理">{{ systemInfo.userAgent }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { CircleCheck, CircleClose } from '@element-plus/icons-vue'
import { formatTime } from '@/utils/format'

const services = ref([
  { name: 'Agent OS API', status: 'healthy', uptime: '-' },
  { name: 'Agent OS WS', status: 'healthy', uptime: '-' },
  { name: 'v2 API', status: 'healthy', uptime: '-' },
  { name: '数据库', status: 'healthy', uptime: '-' },
])

const resources = ref({
  cpu: 35,
  memory: 60,
  disk: 45,
})

const dbPool = ref({
  active: 5,
  idle: 10,
  max: 20,
  waiting: 0,
  timeout: 5000,
})

const systemInfo = ref({
  version: '1.0.0',
  startTime: new Date().toISOString(),
  os: 'web',
  nodeVersion: 'unknown',
  browser: 'unknown',
  userAgent: '',
})

const getProgressColor = (percentage: number) => {
  if (percentage < 60) return '#67c23a'
  if (percentage < 80) return '#e6a23c'
  return '#f56c6c'
}

onMounted(async () => {
  // 获取浏览器信息
  systemInfo.value.browser = navigator.userAgent.split(' ').pop() || 'unknown'
  systemInfo.value.userAgent = navigator.userAgent.substring(0, 100)

  // 尝试获取真实数据
  try {
    // const health = await getSystemHealth()
    // services.value = health.services
  } catch (e) {
    console.error('加载系统状态失败:', e)
  }
})
</script>

<style scoped>
.system-status {
  padding: 20px;
}
.service-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.service-card h3 {
  margin: 0;
  font-size: 16px;
}
.uptime {
  margin: 0;
  font-size: 12px;
  color: #909399;
}
.resource-item {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-bottom: 20px;
}
.resource-item span {
  width: 120px;
  font-weight: 500;
}
</style>
