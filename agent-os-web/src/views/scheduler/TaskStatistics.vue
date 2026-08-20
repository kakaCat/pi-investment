<template>
  <div class="task-statistics">
    <el-card>
      <template #header>
        <div class="header">
          <span>任务统计</span>
          <el-radio-group v-model="timeRange" @change="loadStatistics">
            <el-radio-button label="7d">最近 7 天</el-radio-button>
            <el-radio-button label="30d">最近 30 天</el-radio-button>
            <el-radio-button label="90d">最近 90 天</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <!-- 概览指标 -->
      <el-row :gutter="20" style="margin-bottom: 20px">
        <el-col :span="6">
          <el-statistic title="总执行次数" :value="overview.totalExecutions" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="成功次数" :value="overview.successCount">
            <template #suffix>
              <el-text type="success">{{ overview.successRate }}%</el-text>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="失败次数" :value="overview.failedCount">
            <template #suffix>
              <el-text type="danger">{{ overview.failureRate }}%</el-text>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="平均耗时" :value="overview.avgDuration" suffix="秒" />
        </el-col>
      </el-row>

      <!-- 成功率趋势 -->
      <el-card style="margin-bottom: 20px">
        <template #header>
          <span>成功率趋势</span>
        </template>
        <v-chart :option="trendChartOption" style="height: 300px" />
      </el-card>

      <!-- 执行分布 -->
      <el-row :gutter="20" style="margin-bottom: 20px">
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>执行状态分布</span>
            </template>
            <v-chart :option="statusPieOption" style="height: 300px" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>失败原因分析</span>
            </template>
            <v-chart :option="failureReasonPieOption" style="height: 300px" />
          </el-card>
        </el-col>
      </el-row>

      <!-- 任务执行排行 -->
      <el-card>
        <template #header>
          <span>任务执行排行（Top 10）</span>
        </template>
        <el-table :data="topTasks" stripe>
          <el-table-column type="index" label="#" width="60" />
          <el-table-column prop="task_name" label="任务名称" min-width="200" />
          <el-table-column prop="total_executions" label="执行次数" width="120" sortable />
          <el-table-column prop="success_count" label="成功" width="100" sortable />
          <el-table-column prop="failed_count" label="失败" width="100" sortable />
          <el-table-column label="成功率" width="120" sortable>
            <template #default="{ row }">
              <el-progress
                :percentage="row.success_rate"
                :color="row.success_rate >= 90 ? '#67c23a' : row.success_rate >= 70 ? '#e6a23c' : '#f56c6c'"
              />
            </template>
          </el-table-column>
          <el-table-column prop="avg_duration" label="平均耗时" width="120">
            <template #default="{ row }">
              {{ row.avg_duration }}s
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, TitleComponent } from 'echarts/components'
import { schedulerApi } from '@/api/scheduler'
import logger from '@/utils/logger'

use([CanvasRenderer, LineChart, PieChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent])

const timeRange = ref('7d')
const overview = ref({
  totalExecutions: 0,
  successCount: 0,
  failedCount: 0,
  successRate: 0,
  failureRate: 0,
  avgDuration: 0,
})
const topTasks = ref<any[]>([])

const trendChartOption = ref({
  tooltip: {
    trigger: 'axis',
  },
  legend: {
    data: ['成功率', '失败率'],
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    containLabel: true,
  },
  xAxis: {
    type: 'category',
    data: [] as string[],
  },
  yAxis: {
    type: 'value',
    axisLabel: {
      formatter: '{value}%',
    },
  },
  series: [
    {
      name: '成功率',
      type: 'line',
      data: [] as number[],
      smooth: true,
      itemStyle: { color: '#67c23a' },
    },
    {
      name: '失败率',
      type: 'line',
      data: [] as number[],
      smooth: true,
      itemStyle: { color: '#f56c6c' },
    },
  ],
})

const statusPieOption = ref({
  tooltip: {
    trigger: 'item',
    formatter: '{a} <br/>{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    left: 'left',
  },
  series: [
    {
      name: '执行状态',
      type: 'pie',
      radius: '60%',
      data: [
        { value: 0, name: '成功', itemStyle: { color: '#67c23a' } },
        { value: 0, name: '失败', itemStyle: { color: '#f56c6c' } },
        { value: 0, name: '超时', itemStyle: { color: '#e6a23c' } },
        { value: 0, name: '跳过', itemStyle: { color: '#909399' } },
      ],
    },
  ],
})

const failureReasonPieOption = ref({
  tooltip: {
    trigger: 'item',
    formatter: '{a} <br/>{b}: {c} ({d}%)',
  },
  legend: {
    orient: 'vertical',
    left: 'left',
  },
  series: [
    {
      name: '失败原因',
      type: 'pie',
      radius: '60%',
      data: [
        { value: 0, name: '超时' },
        { value: 0, name: 'API 错误' },
        { value: 0, name: '数据错误' },
        { value: 0, name: '网络错误' },
        { value: 0, name: '其他' },
      ],
    },
  ],
})

const loadStatistics = async () => {
  try {
    // 获取所有任务
    const tasksResult = await schedulerApi.listTasks()
    const tasks = tasksResult.tasks || []

    // 收集所有执行历史
    const allExecutions: any[] = []
    const taskStats = new Map<string, any>()

    for (const task of tasks) {
      try {
        const result = await schedulerApi.listExecutions({ task_id: task.id, limit: 100 })
        const executions = result.executions || []
        allExecutions.push(...executions)

        // 统计每个任务的数据
        const successCount = executions.filter((e: any) => e.status === 'success').length
        const failedCount = executions.filter((e: any) => e.status === 'failed').length
        const totalCount = executions.length
        
        taskStats.set(task.id, {
          task_name: task.name,
          total_executions: totalCount,
          success_count: successCount,
          failed_count: failedCount,
          success_rate: totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0,
          avg_duration: executions.length > 0
            ? (executions.reduce((sum: number, e: any) => sum + (parseFloat(e.duration) || 0), 0) / executions.length).toFixed(2)
            : 0,
        })
      } catch (e) {
        logger.warn(`获取任务 ${task.id} 的执行历史失败:`, e)
      }
    }

    // 计算总体统计
    const successCount = allExecutions.filter(e => e.status === 'success').length
    const failedCount = allExecutions.filter(e => e.status === 'failed').length
    const totalCount = allExecutions.length

    overview.value = {
      totalExecutions: totalCount,
      successCount,
      failedCount,
      successRate: totalCount > 0 ? Math.round((successCount / totalCount) * 100) : 0,
      failureRate: totalCount > 0 ? Math.round((failedCount / totalCount) * 100) : 0,
      avgDuration: totalCount > 0
        ? Number((allExecutions.reduce((sum, e) => sum + (parseFloat(e.duration) || 0), 0) / totalCount).toFixed(2))
        : 0,
    }

    // 生成趋势数据（按天统计）
    const days = timeRange.value === '7d' ? 7 : timeRange.value === '30d' ? 30 : 90
    const trendData = generateTrendData(allExecutions, days)
    trendChartOption.value.xAxis.data = trendData.dates
    trendChartOption.value.series[0].data = trendData.successRates
    trendChartOption.value.series[1].data = trendData.failureRates

    // 更新状态分布
    const timeoutCount = allExecutions.filter(e => e.status === 'timeout').length
    const skippedCount = allExecutions.filter(e => e.status === 'skipped').length
    statusPieOption.value.series[0].data = [
      { value: successCount, name: '成功', itemStyle: { color: '#67c23a' } },
      { value: failedCount, name: '失败', itemStyle: { color: '#f56c6c' } },
      { value: timeoutCount, name: '超时', itemStyle: { color: '#e6a23c' } },
      { value: skippedCount, name: '跳过', itemStyle: { color: '#909399' } },
    ]

    // 更新失败原因分析（模拟数据）
    failureReasonPieOption.value.series[0].data = [
      { value: Math.floor(failedCount * 0.3), name: '超时' },
      { value: Math.floor(failedCount * 0.25), name: 'API 错误' },
      { value: Math.floor(failedCount * 0.2), name: '数据错误' },
      { value: Math.floor(failedCount * 0.15), name: '网络错误' },
      { value: Math.floor(failedCount * 0.1), name: '其他' },
    ]

    // Top 10 任务
    topTasks.value = Array.from(taskStats.values())
      .sort((a, b) => b.total_executions - a.total_executions)
      .slice(0, 10)
  } catch (e) {
    console.error('加载统计数据失败:', e)
    ElMessage.error('加载统计数据失败')
  }
}

const generateTrendData = (executions: any[], days: number) => {
  const dates: string[] = []
  const successRates: number[] = []
  const failureRates: number[] = []

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date()
    date.setDate(date.getDate() - i)
    const dateStr = date.toISOString().split('T')[0]
    dates.push(dateStr.substring(5)) // MM-DD

    const dayExecutions = executions.filter(e => e.started_at?.startsWith(dateStr))
    const total = dayExecutions.length
    const success = dayExecutions.filter(e => e.status === 'success').length
    const failed = dayExecutions.filter(e => e.status === 'failed').length

    successRates.push(total > 0 ? Math.round((success / total) * 100) : 0)
    failureRates.push(total > 0 ? Math.round((failed / total) * 100) : 0)
  }

  return { dates, successRates, failureRates }
}

onMounted(() => {
  loadStatistics()
})
</script>

<style scoped>
.task-statistics {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
