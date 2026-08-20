<template>
  <div class="decision-statistics">
    <el-card>
      <template #header>
        <span>决策统计</span>
      </template>

      <!-- 概览 -->
      <el-row :gutter="20" style="margin-bottom: 20px">
        <el-col :span="6">
          <el-statistic title="总决策数" :value="stats.total" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已执行" :value="stats.executed" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="待执行" :value="stats.pending" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="平均置信度" :value="stats.avgConfidence" suffix="%" />
        </el-col>
      </el-row>

      <!-- 决策分布 -->
      <el-row :gutter="20">
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>决策类型分布</span>
            </template>
            <v-chart :option="typePieOption" style="height: 300px" />
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card>
            <template #header>
              <span>决策状态分布</span>
            </template>
            <v-chart :option="statusPieOption" style="height: 300px" />
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { decisionApi } from '@/api/decisions'

use([CanvasRenderer, PieChart, TooltipComponent, LegendComponent])

const stats = ref({
  total: 0,
  executed: 0,
  pending: 0,
  avgConfidence: 0,
})

const typePieOption = ref({
  tooltip: { trigger: 'item' },
  legend: { orient: 'vertical', left: 'left' },
  series: [
    {
      name: '决策类型',
      type: 'pie',
      radius: '60%',
      data: [],
    },
  ],
})

const statusPieOption = ref({
  tooltip: { trigger: 'item' },
  legend: { orient: 'vertical', left: 'left' },
  series: [
    {
      name: '决策状态',
      type: 'pie',
      radius: '60%',
      data: [],
    },
  ],
})

const loadStatistics = async () => {
  try {
    const result = await decisionApi.getStatistics()
    const statsData = result.stats || {}
    stats.value = statsData
    typePieOption.value.series[0].data = statsData.typeDistribution || []
    statusPieOption.value.series[0].data = statsData.statusDistribution || []
  } catch (e) {
    console.error('加载统计失败:', e)
    ElMessage.error('加载统计失败')
  }
}

onMounted(() => {
  loadStatistics()
})
</script>

<style scoped>
.decision-statistics {
  padding: 20px;
}
</style>
