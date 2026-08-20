<template>
  <div class="decision-list">
    <el-card>
      <template #header>
        <div class="header">
          <span>决策中心</span>
          <div class="header-actions">
            <el-tag v-if="loading" type="info" effect="plain">加载中...</el-tag>
            <el-tag v-else type="success" effect="plain">共 {{ total }} 条</el-tag>
          </div>
        </div>
      </template>

      <!-- 筛选器 -->
      <div class="filters">
        <el-select v-model="actionFilter" placeholder="动作类型" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="买入" value="buy" />
          <el-option label="卖出" value="sell" />
          <el-option label="持有" value="hold" />
          <el-option label="观察" value="watch" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 150px">
          <el-option label="全部" value="" />
          <el-option label="已执行" value="executed" />
          <el-option label="待执行" value="pending" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
        <el-button type="primary" @click="loadDecisions" style="margin-left: 10px">
          查询
        </el-button>
        <el-button @click="clearFilters">重置</el-button>
      </div>

      <!-- 决策表格 -->
      <el-table v-loading="loading" :data="filteredDecisions" stripe style="margin-top: 16px">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 20px">
              <h4>决策详情</h4>
              <p><strong>理由：</strong>{{ row.reason }}</p>
              <p><strong>置信度：</strong>{{ row.confidence }}</p>
              <p><strong>标的：</strong>{{ row.targets.join(', ') }}</p>
              <p v-if="row.target"><strong>目标：</strong>{{ row.target }}</p>
              <p v-if="row.context"><strong>上下文：</strong><pre style="white-space: pre-wrap">{{ JSON.stringify(row.context, null, 2) }}</pre></p>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="80" show-overflow-tooltip />
        <el-table-column prop="action" label="动作" width="90">
          <template #default="{ row }">
            <el-tag :type="getActionType(row.action)">
              {{ getActionLabel(row.action) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="targets" label="标的" width="140">
          <template #default="{ row }">
            {{ row.targets?.join(', ') }}
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="130">
          <template #default="{ row }">
            <el-progress :percentage="Math.round((row.confidence || 0) * 100)" :color="getConfidenceColor(row.confidence)" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pnl" label="盈亏" width="100">
          <template #default="{ row }">
            <span v-if="row.pnl !== null && row.pnl !== undefined" :style="{ color: row.pnl >= 0 ? '#67c23a' : '#f56c6c' }">
              {{ row.pnl > 0 ? '+' : '' }}{{ row.pnl }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && filteredDecisions.length === 0" description="暂无决策数据" />

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadDecisions"
          @current-change="loadDecisions"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { decisionApi } from '@/api/decisions'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const decisions = ref<any[]>([])
const total = ref(0)
const actionFilter = ref('')
const statusFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(10)

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
  const map: Record<string, string> = { buy: 'success', sell: 'danger', hold: 'info', watch: 'warning' }
  return map[action] || 'info'
}

const getActionLabel = (action: string) => {
  const map: Record<string, string> = { buy: '买入', sell: '卖出', hold: '持有', watch: '观察' }
  return map[action] || action
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = { executed: 'success', pending: 'warning', cancelled: 'info' }
  return map[status] || 'info'
}

const getStatusLabel = (status: string) => {
  const map: Record<string, string> = { executed: '已执行', pending: '待执行', cancelled: '已取消' }
  return map[status] || status
}

const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.5) return '#e6a23c'
  return '#f56c6c'
}

const loadDecisions = async () => {
  loading.value = true
  try {
    const params: any = { limit: pageSize.value }
    if (actionFilter.value) params.action = actionFilter.value
    if (statusFilter.value) params.status = statusFilter.value

    const result = await decisionApi.list(params)
    decisions.value = result.decisions || []
    total.value = result.total || 0
  } catch (e) {
    console.error('加载决策失败:', e)
    ElMessage.error('加载决策失败')
  } finally {
    loading.value = false
  }
}

const clearFilters = () => {
  actionFilter.value = ''
  statusFilter.value = ''
  currentPage.value = 1
  loadDecisions()
}

onMounted(() => {
  loadDecisions()
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
  align-items: center;
}
.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
