<template>
  <div class="decision-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>决策中心</span>
          <el-tag type="info">Mock 数据</el-tag>
        </div>
      </template>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="决策中心功能开发中"
        description="Agent OS 决策模块 HTTP API 尚未提供，当前展示为模拟数据。"
        style="margin-bottom: 16px"
      />

      <!-- 筛选器 -->
      <div class="filters">
        <el-select v-model="actionFilter" placeholder="动作类型" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
          <el-option label="持有" value="hold" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="已执行" value="executed" />
          <el-option label="待执行" value="pending" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </div>

      <!-- 决策表格 -->
      <el-table :data="filteredDecisions" stripe style="margin-top: 16px">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 20px">
              <h4>决策详情</h4>
              <p><strong>理由：</strong>{{ row.reason }}</p>
              <p><strong>置信度：</strong>{{ row.confidence }}</p>
              <p><strong>标的：</strong>{{ row.targets.join(', ') }}</p>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="action" label="动作" width="100">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">
              {{ row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="targets" label="标的" width="150">
          <template #default="{ row }">
            {{ row.targets.join(', ') }}
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.confidence * 100)" :color="getConfidenceColor(row.confidence)" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'executed' ? 'success' : row.status === 'pending' ? 'warning' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="盈亏" width="100">
          <template #default="{ row }">
            <span :style="{ color: row.pnl.startsWith('+') ? '#67c23a' : '#f56c6c' }">{{ row.pnl }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { formatTime } from '@/utils/format'

const decisions = ref<any[]>([])
const actionFilter = ref('')
const statusFilter = ref('')

const filteredDecisions = computed(() => {
  let result = decisions.value
  if (actionFilter.value) {
    result = result.filter((d) => d.action === actionFilter.value)
  }
  if (statusFilter.value) {
    result = result.filter((d) => d.status === statusFilter.value)
  }
  return result
})

const getActionType = (action: string) => {
  const map: Record<string, string> = { buy: 'success', sell: 'danger', hold: 'info' }
  return map[action] || 'info'
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.5) return '#e6a23c'
  return '#f56c6c'
}

onMounted(() => {
  // Mock 数据
  decisions.value = [
    { id: '1', action: 'buy', targets: ['600519.SH'], confidence: 0.85, reason: 'ROE 25%，PE 历史30%分位', status: 'executed', pnl: '+5.2%', created_at: '2026-08-18T10:30:00Z' },
    { id: '2', action: 'sell', targets: ['000858.SZ'], confidence: 0.72, reason: '机构出货信号', status: 'executed', pnl: '-1.3%', created_at: '2026-08-18T11:00:00Z' },
    { id: '3', action: 'hold', targets: ['601888.SH'], confidence: 0.65, reason: '趋势不明，观望', status: 'pending', pnl: '0%', created_at: '2026-08-18T11:30:00Z' },
  ]
})
</script>

<style scoped>
.decision-list {
  padding: 20px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.filters {
  display: flex;
  gap: 12px;
}
</style>
