<template>
  <div class="dashboard-page">
    <el-row :gutter="24">
      <!-- 统计卡片 -->
      <el-col :xs="24" :sm="12" :md="6" :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #e6f7ff;">
              <el-icon :size="32" color="#1890ff"><TrendCharts /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">¥1,234,567</div>
              <div class="stat-label">总资产</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6" :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #f6ffed;">
              <el-icon :size="32" color="#52c41a"><ArrowUp /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value success">+¥12,345</div>
              <div class="stat-label">今日盈亏</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6" :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff7e6;">
              <el-icon :size="32" color="#fa8c16"><Bell /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">5</div>
              <div class="stat-label">待审批信号</div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6" :span="6">
        <el-card class="stat-card">
          <div class="stat-content">
            <div class="stat-icon" style="background: #fff1f0;">
              <el-icon :size="32" color="#f5222d"><Warning /></el-icon>
            </div>
            <div class="stat-info">
              <div class="stat-value">2</div>
              <div class="stat-label">风险预警</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="24" style="margin-top: 24px;">
      <!-- 组合净值走势 -->
      <el-col :xs="24" :sm="24" :md="16" :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>组合净值走势</span>
            </div>
          </template>
          <div ref="chartRef" class="chart-container" style="height: 300px;"></div>
        </el-card>
      </el-col>

      <!-- Agent今日工作摘要 -->
      <el-col :xs="24" :sm="24" :md="8" :span="8">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>Agent今日工作</span>
            </div>
          </template>
          <el-timeline>
            <el-timeline-item timestamp="09:30" placement="top">
              <div class="timeline-content">
                <div class="timeline-title">分析股票 600519</div>
                <div class="timeline-desc">技术面评分: 85分</div>
              </div>
            </el-timeline-item>
            <el-timeline-item timestamp="10:15" placement="top">
              <div class="timeline-content">
                <div class="timeline-title">生成买入信号</div>
                <div class="timeline-desc">600519 建议买入</div>
              </div>
            </el-timeline-item>
            <el-timeline-item timestamp="11:00" placement="top">
              <div class="timeline-content">
                <div class="timeline-title">风险检查</div>
                <div class="timeline-desc">持仓集中度正常</div>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="24" style="margin-top: 24px;">
      <!-- 待处理事项 -->
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>待处理事项</span>
              <el-button type="primary" size="small" @click="handleViewAll">查看全部</el-button>
            </div>
          </template>
          <el-table :data="pendingTasks" style="width: 100%">
            <el-table-column prop="type" label="类型" width="120">
              <template #default="{ row }">
                <el-tag :type="row.type === '买入申请' ? 'success' : 'warning'">
                  {{ row.type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="symbol" label="股票" width="120" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                {{ row.confidence }}%
              </template>
            </el-table-column>
            <el-table-column prop="time" label="时间" width="180" />
            <el-table-column label="操作" width="200">
              <template #default="{ row }">
                <el-button type="success" size="small" @click="handleApprove(row)">批准</el-button>
                <el-button type="danger" size="small" @click="handleReject(row)">拒绝</el-button>
                <el-button type="primary" size="small" @click="handleView(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import type { EChartsOption } from 'echarts'

const router = useRouter()

const pendingTasks = ref([
  {
    type: '买入申请',
    symbol: '600519',
    description: 'RSI超卖(28), MACD金叉, 主力净流入',
    confidence: 85,
    time: '2026-05-23 09:30:00'
  },
  {
    type: '止损提醒',
    symbol: '000001',
    description: '跌破止损线, 建议卖出',
    confidence: 90,
    time: '2026-05-23 10:15:00'
  }
])

const chartRef = ref<HTMLElement>()
let chartInstance: echarts.ECharts | null = null

const initChart = () => {
  if (!chartRef.value) return

  chartInstance = echarts.init(chartRef.value)

  // 模拟净值数据
  const dates = []
  const values = []
  const baseValue = 1.0
  for (let i = 0; i < 30; i++) {
    const date = new Date()
    date.setDate(date.getDate() - (29 - i))
    dates.push(date.toISOString().split('T')[0])
    values.push(+(baseValue + Math.random() * 0.2 - 0.05).toFixed(4))
  }

  const option: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      formatter: '{b}<br/>净值: {c}'
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates
    },
    yAxis: {
      type: 'value',
      scale: true
    },
    series: [
      {
        name: '组合净值',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#5470c6',
          width: 2
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(84, 112, 198, 0.3)' },
              { offset: 1, color: 'rgba(84, 112, 198, 0.05)' }
            ]
          }
        },
        data: values
      }
    ]
  }

  chartInstance.setOption(option)
}

const handleViewAll = () => {
  router.push('/opportunities')
}

const handleApprove = (row: any) => {
  ElMessage.success(`已批准 ${row.symbol} 的${row.type}`)
  // TODO: Call API to approve the signal
}

const handleReject = (row: any) => {
  ElMessage.warning(`已拒绝 ${row.symbol} 的${row.type}`)
  // TODO: Call API to reject the signal
}

const handleView = (row: any) => {
  router.push(`/opportunities/${row.symbol}`)
}

onMounted(() => {
  initChart()

  // 响应式调整
  window.addEventListener('resize', () => {
    chartInstance?.resize()
  })
})

onUnmounted(() => {
  chartInstance?.dispose()
  window.removeEventListener('resize', () => {
    chartInstance?.resize()
  })
})
</script>

<style scoped>
.dashboard-page {
  width: 100%;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #262626;
  margin-bottom: 4px;
}

.stat-value.success {
  color: #52c41a;
}

.stat-label {
  font-size: 14px;
  color: #8c8c8c;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.chart-container {
  width: 100%;
  height: 100%;
}

.timeline-content {
  padding: 4px 0;
}

.timeline-title {
  font-size: 14px;
  color: #262626;
  margin-bottom: 4px;
}

.timeline-desc {
  font-size: 12px;
  color: #8c8c8c;
}

@media (max-width: 768px) {
  .stat-card {
    margin-bottom: 16px;
  }

  .stat-value {
    font-size: 20px;
  }

  .stat-icon {
    width: 48px;
    height: 48px;
  }

  .card-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .chart-container {
    height: 250px !important;
  }

  :deep(.el-table) {
    font-size: 12px;
  }

  :deep(.el-button) {
    padding: 4px 8px;
    font-size: 12px;
  }
}
</style>
