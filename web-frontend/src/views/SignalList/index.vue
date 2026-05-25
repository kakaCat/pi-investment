<template>
  <div class="signal-list-page">
    <!-- 工具栏 -->
    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar-content">
        <div class="toolbar-left">
          <h2 class="page-title">交易信号</h2>

          <!-- 筛选器 -->
          <el-select
            v-model="filters.type"
            placeholder="全部类型"
            clearable
            style="width: 140px"
            @change="handleFilterChange"
          >
            <el-option label="全部类型" value="" />
            <el-option label="BUY" value="buy" />
            <el-option label="SELL" value="sell" />
          </el-select>

          <el-select
            v-model="filters.status"
            placeholder="全部状态"
            clearable
            style="width: 140px"
            @change="handleFilterChange"
          >
            <el-option label="全部状态" value="" />
            <el-option label="待审批" value="pending" />
            <el-option label="已批准" value="approved" />
            <el-option label="已拒绝" value="rejected" />
            <el-option label="已执行" value="executed" />
          </el-select>

          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            style="width: 260px"
            @change="handleDateRangeChange"
          />

          <el-select
            v-model="filters.minConfidence"
            placeholder="最小置信度"
            clearable
            style="width: 140px"
            @change="handleFilterChange"
          >
            <el-option label="最小置信度: 0" :value="0" />
            <el-option label="0.6" :value="0.6" />
            <el-option label="0.7" :value="0.7" />
            <el-option label="0.8" :value="0.8" />
            <el-option label="0.9" :value="0.9" />
          </el-select>

          <el-input
            v-model="filters.symbol"
            placeholder="搜索股票代码"
            clearable
            style="width: 180px"
            @change="handleFilterChange"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>

        <div class="toolbar-right">
          <el-button type="primary" @click="handleScanSignals">
            <el-icon><Refresh /></el-icon>
            扫描信号
          </el-button>
        </div>
      </div>

      <!-- 批量操作栏 -->
      <div v-if="hasSelection" class="batch-actions">
        <span class="selection-info">已选择 {{ selectedRows.length }} 项</span>
        <el-button type="success" size="small" @click="handleBatchApprove">
          批量审批
        </el-button>
        <el-button type="danger" size="small" @click="handleBatchReject">
          批量拒绝
        </el-button>
        <el-button size="small" @click="clearSelection">
          取消选择
        </el-button>
      </div>
    </el-card>

    <!-- 信号列表表格 -->
    <el-card class="table-card" shadow="never">
      <el-table
        v-loading="loading"
        :data="data"
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />

        <el-table-column prop="createdAt" label="时间" width="100">
          <template #default="{ row }">
            <span class="text-secondary">{{ formatTime(row.createdAt) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }">
            <span class="font-medium">{{ row.symbol }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="symbolName" label="名称" width="120" />

        <el-table-column prop="type" label="信号" width="80">
          <template #default="{ row }">
            <el-tag
              :type="row.type === 'buy' ? 'danger' : 'success'"
              size="small"
              effect="dark"
            >
              {{ row.type?.toUpperCase() || '-' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="confidence" label="置信度" width="200">
          <template #default="{ row }">
            <div class="confidence-cell">
              <el-progress
                :percentage="row.confidence * 100"
                :color="getConfidenceColor(row.confidence)"
                :stroke-width="6"
                :show-text="false"
              />
              <span class="confidence-value">{{ (row.confidence * 100).toFixed(0) }}%</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="触发价格" width="100">
          <template #default="{ row }">
            ¥{{ row.price.toFixed(2) }}
          </template>
        </el-table-column>

        <el-table-column label="当前价格" width="100">
          <template #default="{ row }">
            <span v-if="realtimeQuotes.has(row.symbol)">
              ¥{{ realtimeQuotes.get(row.symbol).price.toFixed(2) }}
            </span>
            <span v-else class="text-secondary">--</span>
          </template>
        </el-table-column>

        <el-table-column label="涨跌幅" width="100">
          <template #default="{ row }">
            <span
              v-if="realtimeQuotes.has(row.symbol)"
              :class="getPriceChangeClass(realtimeQuotes.get(row.symbol).changePercent)"
            >
              {{ formatPercent(realtimeQuotes.get(row.symbol).changePercent) }}
            </span>
            <span v-else class="text-secondary">--</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">
              {{ getStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="策略来源" width="140">
          <template #default="{ row }">
            <span class="text-secondary">{{ row.reasons[0] || '--' }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="handleViewDetail(row)"
            >
              查看详情
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="success"
              link
              size="small"
              @click="handleApprove(row)"
            >
              审批
            </el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="danger"
              link
              size="small"
              @click="handleReject(row)"
            >
              拒绝
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrapper">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 审批对话框 -->
    <el-dialog
      v-model="approveDialogVisible"
      title="审批信号"
      width="500px"
    >
      <div v-if="currentSignal">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="股票">
            {{ currentSignal.symbol }} - {{ currentSignal.symbolName }}
          </el-descriptions-item>
          <el-descriptions-item label="信号类型">
            <el-tag :type="currentSignal.type === 'buy' ? 'danger' : 'success'">
              {{ currentSignal.type.toUpperCase() }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            {{ (currentSignal.confidence * 100).toFixed(0) }}%
          </el-descriptions-item>
          <el-descriptions-item label="价格">
            ¥{{ currentSignal.price.toFixed(2) }}
          </el-descriptions-item>
        </el-descriptions>
      </div>
      <template #footer>
        <el-button @click="approveDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmApprove">确认审批</el-button>
      </template>
    </el-dialog>

    <!-- 拒绝对话框 -->
    <el-dialog
      v-model="rejectDialogVisible"
      title="拒绝信号"
      width="500px"
    >
      <el-form :model="rejectForm" label-width="80px">
        <el-form-item label="拒绝原因">
          <el-input
            v-model="rejectForm.reason"
            type="textarea"
            :rows="4"
            placeholder="请输入拒绝原因"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="rejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmReject">确认拒绝</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import { useTable } from '@/composables/useTable'
import { useMarketWebSocket } from '@/composables/useWebSocket'
import { useSignalStore } from '@/stores/signals'
import type { TradingSignal, SignalFilters } from '@/types/models'

const router = useRouter()
const signalStore = useSignalStore()

// 表格
const {
  data,
  loading,
  total,
  currentPage,
  pageSize,
  selectedRows,
  hasSelection,
  loadData,
  changePage,
  changePageSize,
  clearSelection
} = useTable<TradingSignal>({ pageSize: 20 })

// WebSocket 实时行情
const { quotes: realtimeQuotes, subscribe, unsubscribe } = useMarketWebSocket()

// 筛选条件
const filters = reactive<SignalFilters>({
  type: undefined,
  status: undefined,
  minConfidence: undefined,
  symbol: undefined,
  startDate: undefined,
  endDate: undefined
})

const dateRange = ref<[Date, Date] | null>(null)

// 对话框
const approveDialogVisible = ref(false)
const rejectDialogVisible = ref(false)
const currentSignal = ref<TradingSignal | null>(null)
const rejectForm = reactive({
  reason: ''
})

// 加载信号列表
const fetchSignals = async () => {
  await loadData(async () => {
    const params = {
      ...filters,
      page: currentPage.value,
      pageSize: pageSize.value
    }
    await signalStore.fetchSignals(params)

    // 订阅实时行情
    signalStore.signals.forEach(signal => {
      subscribe(signal.symbol)
    })

    return {
      items: signalStore.signals,
      total: signalStore.total
    }
  })
}

// 筛选变化
const handleFilterChange = () => {
  currentPage.value = 1
  fetchSignals()
}

// 日期范围变化
const handleDateRangeChange = (value: [Date, Date] | null) => {
  if (value) {
    filters.startDate = value[0].toISOString().split('T')[0]
    filters.endDate = value[1].toISOString().split('T')[0]
  } else {
    filters.startDate = undefined
    filters.endDate = undefined
  }
  handleFilterChange()
}

// 扫描信号
const handleScanSignals = () => {
  ElMessage.info('正在扫描信号...')
  fetchSignals()
}

// 分页变化
const handlePageChange = (page: number) => {
  changePage(page)
  fetchSignals()
}

const handlePageSizeChange = (size: number) => {
  changePageSize(size)
  fetchSignals()
}

// 选择变化
const handleSelectionChange = (selection: TradingSignal[]) => {
  selectedRows.value = selection
}

// 查看详情
const handleViewDetail = (signal: TradingSignal) => {
  router.push({
    name: 'StockDetail',
    params: { symbol: signal.symbol }
  })
}

// 审批
const handleApprove = (signal: TradingSignal) => {
  currentSignal.value = signal
  approveDialogVisible.value = true
}

const confirmApprove = async () => {
  if (!currentSignal.value) return

  try {
    await signalStore.approveSignal(currentSignal.value.id)
    ElMessage.success('审批成功')
    approveDialogVisible.value = false
    fetchSignals()
  } catch (error: any) {
    ElMessage.error(error.message || '审批失败')
  }
}

// 拒绝
const handleReject = (signal: TradingSignal) => {
  currentSignal.value = signal
  rejectForm.reason = ''
  rejectDialogVisible.value = true
}

const confirmReject = async () => {
  if (!currentSignal.value) return

  if (!rejectForm.reason.trim()) {
    ElMessage.warning('请输入拒绝原因')
    return
  }

  try {
    await signalStore.rejectSignal(currentSignal.value.id, rejectForm.reason)
    ElMessage.success('已拒绝')
    rejectDialogVisible.value = false
    fetchSignals()
  } catch (error: any) {
    ElMessage.error(error.message || '操作失败')
  }
}

// 批量审批
const handleBatchApprove = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要批量审批选中的 ${selectedRows.value.length} 个信号吗？`,
      '批量审批',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    const promises = selectedRows.value
      .filter(s => s.status === 'pending')
      .map(s => signalStore.approveSignal(s.id))

    await Promise.all(promises)
    ElMessage.success('批量审批成功')
    clearSelection()
    fetchSignals()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量审批失败')
    }
  }
}

// 批量拒绝
const handleBatchReject = async () => {
  try {
    const { value: reason } = await ElMessageBox.prompt(
      '请输入拒绝原因',
      '批量拒绝',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /.+/,
        inputErrorMessage: '请输入拒绝原因'
      }
    )

    const promises = selectedRows.value
      .filter(s => s.status === 'pending')
      .map(s => signalStore.rejectSignal(s.id, reason))

    await Promise.all(promises)
    ElMessage.success('批量拒绝成功')
    clearSelection()
    fetchSignals()
  } catch (error: any) {
    if (error !== 'cancel') {
      ElMessage.error(error.message || '批量拒绝失败')
    }
  }
}

// 格式化时间
const formatTime = (dateStr: string) => {
  const date = new Date(dateStr)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`
}

// 格式化百分比
const formatPercent = (value: number) => {
  const sign = value >= 0 ? '+' : ''
  return `${sign}${(value * 100).toFixed(2)}%`
}

// 获取置信度颜色
const getConfidenceColor = (confidence: number) => {
  if (confidence >= 0.8) return '#f5222d'
  if (confidence >= 0.6) return '#fa8c16'
  return '#8c8c8c'
}

// 获取价格变化样式
const getPriceChangeClass = (changePercent: number) => {
  if (changePercent > 0) return 'text-success'
  if (changePercent < 0) return 'text-danger'
  return 'text-secondary'
}

// 获取状态类型
const getStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    pending: 'warning',
    approved: 'success',
    rejected: 'danger',
    executed: 'info'
  }
  return typeMap[status] || 'info'
}

// 获取状态标签
const getStatusLabel = (status: string) => {
  const labelMap: Record<string, string> = {
    pending: '待审批',
    approved: '已批准',
    rejected: '已拒绝',
    executed: '已执行'
  }
  return labelMap[status] || status
}

// 生命周期
onMounted(() => {
  fetchSignals()
})

onUnmounted(() => {
  // 取消订阅所有股票
  data.value.forEach(signal => {
    unsubscribe(signal.symbol)
  })
})
</script>

<style scoped lang="scss">
.signal-list-page {
  padding: 20px;
}

.toolbar-card {
  margin-bottom: 20px;

  .toolbar-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }

  .toolbar-left {
    display: flex;
    align-items: center;
    gap: 12px;
    flex: 1;
  }

  .page-title {
    font-size: 18px;
    font-weight: 600;
    color: #1f2937;
    margin: 0;
    margin-right: 8px;
  }

  .batch-actions {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #e5e7eb;

    .selection-info {
      font-size: 14px;
      color: #6b7280;
      margin-right: auto;
    }
  }
}

.table-card {
  .confidence-cell {
    display: flex;
    align-items: center;
    gap: 12px;

    :deep(.el-progress) {
      flex: 1;
    }

    .confidence-value {
      font-size: 14px;
      font-weight: 500;
      color: #1f2937;
      min-width: 40px;
    }
  }

  .pagination-wrapper {
    display: flex;
    justify-content: flex-end;
    margin-top: 20px;
  }
}

.font-medium {
  font-weight: 500;
}

.text-secondary {
  color: #6b7280;
}

.text-success {
  color: #10b981;
  font-weight: 500;
}

.text-danger {
  color: #ef4444;
  font-weight: 500;
}
</style>
