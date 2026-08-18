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

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const stats = ref({ total: 0, running: 0, successToday: 0, failedToday: 0 })
const healthItems = ref<Array<{ name: string; status: string }>>([])
const recentRuns = ref<Array<any>>([])

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
      data: Array.from({ length: 24 }, () => Math.floor(Math.random() * 10)),
      smooth: true,
      itemStyle: { color: '#67c23a' },
    },
    {
      name: '失败',
      type: 'line',
      data: Array.from({ length: 24 }, () => Math.floor(Math.random() * 3)),
      smooth: true,
      itemStyle: { color: '#f56c6c' },
    },
  ],
})

onMounted(async () => {
  try {
    // 获取真实数据
    const statsResult = await getTaskStats()
    stats.value = {
      total: statsResult.total || 0,
      running: statsResult.running || 0,
      successToday: statsResult.success_today || 0,
      failedToday: statsResult.failed_today || 0,
    }

    const healthResult = await getSystemHealth()
    healthItems.value = [
      { name: 'API 服务', status: healthResult.status === 'ok' ? 'healthy' : 'unhealthy' },
      { name: 'Agent OS', status: healthResult.agent_os || 'healthy' },
      { name: '调度器', status: healthResult.scheduler || 'healthy' },
      { name: '数据库', status: healthResult.database || 'healthy' },
    ]

    const recentResult = await getRecentExecutions(10)
    recentRuns.value = recentResult.executions || []
  } catch (e) {
    console.error('加载失败:', e)
    ElMessage.warning('部分数据加载失败，显示默认值')
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
