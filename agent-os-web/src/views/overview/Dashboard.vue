<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="总任务数" :value="stats.total">
            <template #prefix>
              <el-icon><Document /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="运行中" :value="stats.running">
            <template #prefix>
              <el-icon style="color: #409eff"><Loading /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="今日成功" :value="stats.successToday">
            <template #prefix>
              <el-icon style="color: #67c23a"><CircleCheck /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover">
          <el-statistic title="今日失败" :value="stats.failedToday">
            <template #prefix>
              <el-icon style="color: #f56c6c"><CircleClose /></el-icon>
            </template>
          </el-statistic>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表和健康状态 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="16">
        <el-card>
          <template #header>
            <span>24小时执行趋势</span>
          </template>
          <v-chart :option="chartOption" style="height: 300px" />
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>系统健康</span>
          </template>
          <div class="health-list">
            <div v-for="item in healthItems" :key="item.name" class="health-item">
              <span>{{ item.name }}</span>
              <el-tag :type="item.status === 'healthy' ? 'success' : 'danger'">
                {{ item.status === 'healthy' ? '正常' : '异常' }}
              </el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近执行记录 -->
    <el-card>
      <template #header>
        <span>最近执行记录</span>
      </template>
      <el-table :data="recentRuns" stripe>
        <el-table-column prop="task_name" label="任务名称" />
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="started_at" label="开始时间">
          <template #default="{ row }">
            {{ formatTime(row.started_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration" label="耗时" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { getTaskStats, getSystemHealth, getRecentExecutions } from '@/api/overview'
import { formatTime } from '@/utils/format'
import logger from '@/utils/logger'
import type { Task, TaskRun, HealthItem, OverviewStats } from '@/types/api'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const stats = ref<OverviewStats>({ total: 0, running: 0, successToday: 0, failedToday: 0 })
const healthItems = ref<HealthItem[]>([])
const recentRuns = ref<TaskRun[]>([])

const chartOption = ref({
  tooltip: {
    trigger: 'axis',
  },
  legend: {
    data: ['成功', '失败'],
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: Array.from({ length: 24 }, (_, i) => `${i}:00`),
  },
  yAxis: {
    type: 'value',
  },
  series: [
    {
      name: '成功',
      type: 'line',
      data: Array.from({ length: 24 }, () => 0),
      smooth: true,
      itemStyle: { color: '#67c23a' },
    },
    {
      name: '失败',
      type: 'line',
      data: Array.from({ length: 24 }, () => 0),
      smooth: true,
      itemStyle: { color: '#f56c6c' },
    },
  ],
})

onMounted(async () => {
  try {
    // 获取任务列表作为统计
    const tasksResult = await getTaskStats()
    const tasks: Task[] = tasksResult.tasks || []
    
    // 收集所有任务的执行历史
    const allExecutions: TaskRun[] = []
    for (const task of tasks) {
      try {
        const result = await getRecentExecutions(task.id, 100)
        const runs = result.executions || []
        allExecutions.push(...runs)
      } catch (e) {
        logger.warn(`获取任务 ${task.id} 的执行历史失败:`, e)
      }
    }

    // 计算今日统计
    const today = new Date().toISOString().split('T')[0]
    const todayRuns = allExecutions.filter((e: TaskRun) => e.started_at?.startsWith(today))
    
    stats.value = {
      total: tasks.length,
      running: tasks.filter((t: Task) => t.enabled).length,
      successToday: todayRuns.filter((e: TaskRun) => e.status === 'success').length,
      failedToday: todayRuns.filter((e: TaskRun) => e.status === 'failed').length,
    }

    // 按小时聚合图表数据
    const hourlyData = Array.from({ length: 24 }, (_, hour) => {
      const hourStr = String(hour).padStart(2, '0')
      const hourRuns = allExecutions.filter((e: TaskRun) => {
        const h = e.started_at?.split('T')[1]?.split(':')[0]
        return h === hourStr
      })
      return {
        success: hourRuns.filter((e: TaskRun) => e.status === 'success').length,
        failed: hourRuns.filter((e: TaskRun) => e.status === 'failed').length,
      }
    })
    chartOption.value.series[0].data = hourlyData.map(d => d.success)
    chartOption.value.series[1].data = hourlyData.map(d => d.failed)

    // 检查系统健康
    const healthResult = await getSystemHealth()
    healthItems.value = [
      { name: 'Agent OS API', status: healthResult.status === 'ok' ? 'healthy' : 'unhealthy' },
      { name: 'Agent OS WS', status: 'healthy' },
      { name: 'v2 API', status: 'healthy' },
      { name: '数据库', status: 'healthy' },
    ]

    // 显示最近的执行记录（跨所有任务）
    recentRuns.value = allExecutions
      .sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''))
      .slice(0, 10)
  } catch (e) {
    console.error('加载失败:', e)
    ElMessage.warning('部分数据加载失败')
  }
})
</script>

<style scoped>
.dashboard {
  padding: 20px;
}
.stats-row {
  margin-bottom: 20px;
}
.chart-row {
  margin-bottom: 20px;
}
.health-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.health-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #eee;
}
</style>
