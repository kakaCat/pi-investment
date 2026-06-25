<template>
  <div class="automation-monitor">
    <h1>🤖 自动化任务监控</h1>

    <!-- 任务执行时间轴 -->
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>📅 任务执行历史（最近24小时）</span>
          <el-button size="small" @click="loadTaskHistory">刷新</el-button>
        </div>
      </template>

      <el-timeline>
        <el-timeline-item
          v-for="task in taskHistory"
          :key="task.id"
          :timestamp="task.timestamp"
          :type="task.status === 'success' ? 'success' : 'danger'"
        >
          <div class="task-detail">
            <h4>{{ task.name }}</h4>
            <p>{{ task.description }}</p>
            <div class="task-meta">
              <el-tag :type="task.status === 'success' ? 'success' : 'danger'" size="small">
                {{ task.status === 'success' ? '成功' : '失败' }}
              </el-tag>
              <span>耗时: {{ task.duration }}s</span>
            </div>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 任务执行统计 -->
    <el-card class="box-card mt-20">
      <template #header>
        <span>📊 任务执行统计</span>
      </template>

      <el-table :data="taskStats" stripe>
        <el-table-column prop="name" label="任务名称" min-width="120" />
        <el-table-column prop="total" label="总次数" width="100" align="center" />
        <el-table-column prop="success" label="成功" width="100" align="center">
          <template #default="{ row }">
            <span style="color: #67c23a; font-weight: bold;">{{ row.success }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed" label="失败" width="100" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.failed > 0 ? '#f56c6c' : '#909399', fontWeight: 'bold' }">
              {{ row.failed }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="成功率" width="150" align="center">
          <template #default="{ row }">
            <el-progress
              :percentage="getSuccessRate(row)"
              :color="getProgressColor(getSuccessRate(row))"
              :stroke-width="12"
            />
          </template>
        </el-table-column>
        <el-table-column prop="avgDuration" label="平均耗时" width="120" align="center">
          <template #default="{ row }">
            {{ row.avgDuration }}s
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 日志查看 -->
    <el-card class="box-card mt-20">
      <template #header>
        <div class="card-header">
          <span>🔍 任务日志查看</span>
          <el-select v-model="selectedLog" placeholder="选择日志" @change="loadLogContent">
            <el-option label="早盘分析日志" value="morning" />
            <el-option label="实时监控日志" value="monitor" />
            <el-option label="每日学习日志" value="learning" />
          </el-select>
        </div>
      </template>

      <div class="log-viewer">
        <div v-if="logContent" class="log-content">
          <div v-for="(line, index) in logLines" :key="index" :class="getLogLineClass(line)">
            {{ line }}
          </div>
        </div>
        <el-empty v-else description="请选择日志文件" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const taskHistory = ref([
  {
    id: 1,
    name: '早盘分析',
    description: '对手行为分析 → 预警检查 → 池子评估',
    timestamp: '2026-06-26 09:00:00',
    status: 'success',
    duration: 12
  },
  {
    id: 2,
    name: '实时监控',
    description: '检查紧急预警',
    timestamp: '2026-06-26 09:05:00',
    status: 'success',
    duration: 2
  },
  {
    id: 3,
    name: '实时监控',
    description: '检查紧急预警',
    timestamp: '2026-06-26 09:10:00',
    status: 'success',
    duration: 2
  },
  {
    id: 4,
    name: '实时监控',
    description: '检查紧急预警',
    timestamp: '2026-06-26 09:15:00',
    status: 'success',
    duration: 2
  }
])

const taskStats = ref([
  {
    name: '早盘分析',
    total: 1,
    success: 1,
    failed: 0,
    avgDuration: 12
  },
  {
    name: '实时监控',
    total: 72,
    success: 72,
    failed: 0,
    avgDuration: 2
  },
  {
    name: '每日学习',
    total: 0,
    success: 0,
    failed: 0,
    avgDuration: 0
  }
])

const selectedLog = ref('')
const logContent = ref('')

const logLines = computed(() => {
  return logContent.value ? logContent.value.split('\n') : []
})

const loadTaskHistory = () => {
  // TODO: 从API加载任务历史
  console.log('刷新任务历史')
}

const loadLogContent = () => {
  // 模拟日志内容
  const logs: Record<string, string> = {
    morning: `2026-06-26 09:00:00 [INFO] 开始早盘分析
2026-06-26 09:00:01 [INFO] 分析对手行为...
2026-06-26 09:00:03 [INFO] 散户恐慌抛售
2026-06-26 09:00:04 [INFO] 机构逢低建仓
2026-06-26 09:00:05 [INFO] 检查预警...
2026-06-26 09:00:07 [INFO] 发现2条机会预警
2026-06-26 09:00:08 [INFO] 评估池子#1...
2026-06-26 09:00:10 [INFO] 池子#1评分: 78.5，建议持有
2026-06-26 09:00:12 [INFO] 早盘分析完成`,
    monitor: `2026-06-26 09:05:00 [INFO] 开始实时监控
2026-06-26 09:05:01 [INFO] 检查预警...
2026-06-26 09:05:02 [INFO] 无紧急预警
2026-06-26 09:05:02 [INFO] 监控完成`,
    learning: `2026-06-25 18:00:00 [INFO] 开始每日学习
2026-06-25 18:00:01 [INFO] 评估历史决策...
2026-06-25 18:00:05 [INFO] 评估完成: 5条, 成功3条, 失败2条
2026-06-25 18:00:06 [INFO] 提取知识...
2026-06-25 18:00:08 [INFO] 提取知识2条
2026-06-25 18:00:10 [INFO] 学习完成`
  }

  logContent.value = logs[selectedLog.value] || ''
}

const getSuccessRate = (row: any) => {
  if (row.total === 0) return 0
  return Math.round((row.success / row.total) * 100)
}

const getProgressColor = (rate: number) => {
  if (rate >= 90) return '#67c23a'
  if (rate >= 70) return '#e6a23c'
  return '#f56c6c'
}

const getLogLineClass = (line: string) => {
  if (line.includes('[ERROR]')) return 'log-line log-error'
  if (line.includes('[WARN]')) return 'log-line log-warn'
  if (line.includes('[INFO]')) return 'log-line log-info'
  return 'log-line'
}

onMounted(() => {
  // 初始加载
})
</script>

<style scoped>
.automation-monitor {
  padding: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-detail h4 {
  margin: 0 0 5px 0;
  font-size: 16px;
}

.task-detail p {
  margin: 0 0 8px 0;
  color: #606266;
  font-size: 14px;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  color: #909399;
}

.log-viewer {
  background: #1e1e1e;
  border-radius: 4px;
  padding: 15px;
  max-height: 400px;
  overflow-y: auto;
}

.log-content {
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
}

.log-line {
  color: #d4d4d4;
  padding: 2px 0;
}

.log-error {
  color: #f48771;
  font-weight: bold;
}

.log-warn {
  color: #dcdcaa;
}

.log-info {
  color: #4ec9b0;
}

.mt-20 {
  margin-top: 20px;
}
</style>
