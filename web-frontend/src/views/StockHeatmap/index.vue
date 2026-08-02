<template>
  <div class="stock-heatmap" v-loading="pageLoading">
    <div class="page-header">
      <h2 class="page-title">市场热力图</h2>
      <p class="page-subtitle">agent 判断 × 验证窗实际涨跌 — 白框红=判断对，白框绿=判断错</p>
      <div class="header-actions">
        <el-date-picker
          v-model="queryDate"
          type="date"
          value-format="YYYY-MM-DD"
          :clearable="false"
          placeholder="判断日"
          @change="loadData"
        />
        <el-radio-group v-model="windowDays" @change="loadData">
          <el-radio-button :value="1">1日</el-radio-button>
          <el-radio-button :value="5">5日</el-radio-button>
          <el-radio-button :value="20">20日</el-radio-button>
        </el-radio-group>
        <el-checkbox-group v-model="overlayList" @change="renderChart">
          <el-checkbox value="signals">信号</el-checkbox>
          <el-checkbox value="pool">池调整</el-checkbox>
          <el-checkbox value="industry">行业判断</el-checkbox>
        </el-checkbox-group>
      </div>
    </div>

    <el-alert
      v-if="heatmap?.partial"
      type="warning"
      :closable="false"
      :title="`验证窗未满：实际数据到 ${heatmap.actualEndDate}，统计计入「待定」`"
    />
    <el-alert
      v-if="heatmap && queryDate && heatmap.date !== queryDate"
      type="info"
      :closable="false"
      :title="`所选日期非交易日，已对齐到 ${heatmap.date}`"
    />
    <el-alert
      v-if="heatmap?.scopeDegraded"
      type="info"
      :closable="false"
      title="池成员历史无法完整回放，in_scope 口径已退化为「信号+持仓」"
    />
    <el-alert
      v-if="heatmap && heatmap.excludedCount > 0"
      type="info"
      :closable="false"
      :title="`${heatmap.excludedCount} 只股票停牌/缺数据未显示`"
    />

    <div v-if="heatmap && heatmap.industries.length > 0" class="chart-wrap">
      <div ref="chartRef" class="chart"></div>
    </div>
    <el-empty v-else-if="!pageLoading" description="该日期无热力图数据" />

    <div v-if="heatmap && heatmap.industries.length > 0" class="verdict-stats">
      <el-tag type="danger">判断对 {{ stats.right }}</el-tag>
      <el-tag type="success">判断错 {{ stats.wrong }}</el-tag>
      <el-tag type="info">待定 {{ stats.pending }}</el-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useChart } from '@/composables/useChart'
import { stockApi } from '@/services/api'
import type { HeatmapResponse } from '@/types'
import { buildHeatmapOption } from './chart-options'
import { judgePoolEvent, judgeSignal, judgeStance } from './verdict'

const router = useRouter()
const { chartRef, chartInstance, initChart, setOption } = useChart()

const queryDate = ref<string>('')
const windowDays = ref<number>(5)
const overlayList = ref<string[]>(['signals', 'pool', 'industry'])
const heatmap = ref<HeatmapResponse | null>(null)
const pageLoading = ref(false)

const overlays = computed(() => ({
  signals: overlayList.value.includes('signals'),
  pool: overlayList.value.includes('pool'),
  industry: overlayList.value.includes('industry'),
}))

const stats = computed(() => {
  const acc = { right: 0, wrong: 0, pending: 0 }
  if (!heatmap.value) return acc
  const tally = (v: 'right' | 'wrong' | 'none') => {
    if (v === 'none') return
    if (heatmap.value?.partial) { acc.pending++; return }
    acc[v]++
  }
  for (const ind of heatmap.value.industries) {
    tally(judgeStance(ind.agentStance, ind.changePct))
    for (const s of ind.stocks) {
      if (!s.inScope) continue
      if (s.signals?.length) tally(judgeSignal(s.signals[s.signals.length - 1].type, s.changePct))
      if (s.poolEvents?.length) tally(judgePoolEvent(s.poolEvents[s.poolEvents.length - 1].action, s.changePct))
    }
  }
  return acc
})

async function loadData() {
  pageLoading.value = true
  try {
    heatmap.value = await stockApi.getHeatmap({
      date: queryDate.value || undefined,
      window: windowDays.value,
    })
    await nextTick()
    // 图表容器在 v-if 内，onMounted 时不存在 → useChart 的自动 init 被跳过，
    // 必须在数据到达、容器渲染后手动 init（否则 setOption 永远空转，页面白图）
    if (!chartInstance.value) initChart()
    renderChart()
  } catch {
    ElMessage.error('获取热力图数据失败')
  } finally {
    pageLoading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !heatmap.value || heatmap.value.industries.length === 0) return
  setOption(buildHeatmapOption({ data: heatmap.value, overlays: overlays.value }), true)
  bindChartClick()
}

function bindChartClick() {
  const inst = chartInstance.value
  if (!inst) return
  inst.off('click')
  inst.on('click', (params: any) => {
    const symbol = params?.data?.raw?.symbol
    if (symbol) router.push(`/stocks/${symbol}`)
  })
}

loadData()
</script>

<style scoped>
.stock-heatmap { padding: 16px; display: flex; flex-direction: column; gap: 12px; height: 100%; }
.page-header { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.page-title { margin: 0; font-size: 20px; }
.page-subtitle { margin: 0; color: #888; font-size: 13px; flex-basis: 100%; }
.header-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.chart-wrap { flex: 1; min-height: 65vh; }
.chart { width: 100%; height: 100%; min-height: 65vh; }
.verdict-stats { display: flex; gap: 8px; }
</style>
