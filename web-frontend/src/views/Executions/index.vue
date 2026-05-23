<template>
  <div class="executions">
    <!-- 顶部统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-4">
      <el-card class="stat-card">
        <div class="stat-label">今日执行数</div>
        <div class="stat-value">{{ stats.todayCount }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">成功率</div>
        <div class="stat-value text-green-600">{{ formatPercent(stats.successRate) }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">平均延迟</div>
        <div class="stat-value">{{ stats.avgLatency }}ms</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">失败数</div>
        <div class="stat-value text-red-600">{{ stats.failedCount }}</div>
      </el-card>
    </div>

    <!-- 执行记录列表 -->
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="font-semibold">执行记录</span>
            <el-select v-model="filters.status" placeholder="全部状态" size="small" style="width: 120px" @change="handleFilterChange">
              <el-option label="全部状态" value="" />
              <el-option label="待执行" value="pending" />
              <el-option label="已执行" value="executed" />
              <el-option label="已平仓" value="closed" />
              <el-option label="已取消" value="cancelled" />
            </el-select>
            <el-date-picker
              v-model="dateRange"
              type="daterange"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              size="small"
              @change="handleFilterChange"
            />
          </div>
          <div class="flex items-center gap-4 text-sm">
            <span class="text-gray-500">待处理: <strong class="text-orange-600">{{ stats.pendingCount }}</strong></span>
            <span class="text-gray-500">已执行: <strong>{{ stats.executedCount }}</strong></span>
            <span class="text-gray-500">已平仓: <strong>{{ stats.closedCount }}</strong></span>
            <el-button size="small" @click="handleRefresh" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="executions" stripe v-loading="loading">
        <el-table-column prop="executionId" label="ID" width="80">
          <template #default="{ row }">
            <span class="text-gray-400">#{{ row.executionId }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="signalId" label="信号ID" width="100">
          <template #default="{ row }">
            <span class="text-blue-600">S-{{ row.signalId }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }">
            <router-link :to="{ name: 'StockDetail', params: { symbol: row.symbol } }" class="text-blue-600 hover:underline font-medium">
              {{ row.symbol }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120" />

        <el-table-column prop="action" label="操作" width="80">
          <template #default="{ row }">
            <el-tag :type="row.action === 'BUY' ? 'danger' : 'success'" size="small">
              {{ row.action === 'BUY' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="价格" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.price) }}
          </template>
        </el-table-column>

        <el-table-column prop="quantity" label="数量" width="100" align="right">
          <template #default="{ row }">
            {{ formatAmount(row.quantity, 0) }}
          </template>
        </el-table-column>

        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            <span class="font-medium">¥{{ formatPrice(row.amount) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="openDate" label="开仓日" width="120">
          <template #default="{ row }">
            <span v-if="row.openDate">{{ formatDate(row.openDate) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="closeDate" label="平仓日" width="120">
          <template #default="{ row }">
            <span v-if="row.closeDate">{{ formatDate(row.closeDate) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="profit" label="盈亏" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.profit !== null" :class="row.profit >= 0 ? 'text-up' : 'text-down'">
              {{ row.profit >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(row.profit)) }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button-group size="small" v-if="row.status === 'pending'">
              <el-button type="primary" @click="handleExecute(row)">执行</el-button>
              <el-button type="danger" @click="handleCancel(row)">取消</el-button>
            </el-button-group>
            <el-button v-else-if="row.status === 'executed'" size="small" type="success" @click="handleClose(row)">
              平仓
            </el-button>
            <el-button v-else size="small" text @click="handleViewDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 执行详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="执行详情" width="700px">
      <el-descriptions :column="2" border v-if="selectedExecution">
        <!-- 基本信息 -->
        <el-descriptions-item label="执行ID">
          #{{ selectedExecution.executionId }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusTagType(selectedExecution.status)" size="small">
            {{ getStatusText(selectedExecution.status) }}
          </el-tag>
        </el-descriptions-item>

        <el-descriptions-item label="信号ID">
          <span class="text-blue-600">S-{{ selectedExecution.signalId }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="策略名称">
          {{ selectedExecution.strategyName || '-' }}
        </el-descriptions-item>

        <!-- 股票信息 -->
        <el-descriptions-item label="股票代码">
          <router-link :to="{ name: 'StockDetail', params: { symbol: selectedExecution.symbol } }" class="text-blue-600 hover:underline font-medium">
            {{ selectedExecution.symbol }}
          </router-link>
        </el-descriptions-item>
        <el-descriptions-item label="股票名称">
          {{ selectedExecution.name }}
        </el-descriptions-item>

        <!-- 交易信息 -->
        <el-descriptions-item label="操作方向">
          <el-tag :type="selectedExecution.action === 'BUY' ? 'danger' : 'success'" size="small">
            {{ selectedExecution.action === 'BUY' ? '买入' : '卖出' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="执行价格">
          ¥{{ formatPrice(selectedExecution.price) }}
        </el-descriptions-item>

        <el-descriptions-item label="执行数量">
          {{ formatAmount(selectedExecution.quantity, 0) }} 股
        </el-descriptions-item>
        <el-descriptions-item label="执行金额">
          <span class="font-medium">¥{{ formatPrice(selectedExecution.amount) }}</span>
        </el-descriptions-item>

        <!-- 执行结果 -->
        <el-descriptions-item label="执行结果" v-if="selectedExecution.status !== 'pending'">
          <el-tag :type="selectedExecution.executionSuccess ? 'success' : 'danger'" size="small">
            {{ selectedExecution.executionSuccess ? '成功' : '失败' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="错误信息" v-if="selectedExecution.errorMessage" :span="2">
          <span class="text-red-600 text-sm">{{ selectedExecution.errorMessage }}</span>
        </el-descriptions-item>

        <!-- 时间信息 -->
        <el-descriptions-item label="开仓日期" v-if="selectedExecution.openDate">
          {{ formatDate(selectedExecution.openDate) }}
        </el-descriptions-item>
        <el-descriptions-item label="平仓日期" v-if="selectedExecution.closeDate">
          {{ formatDate(selectedExecution.closeDate) }}
        </el-descriptions-item>

        <el-descriptions-item label="执行开始时间" v-if="selectedExecution.startTime">
          {{ formatDateTime(selectedExecution.startTime) }}
        </el-descriptions-item>
        <el-descriptions-item label="执行结束时间" v-if="selectedExecution.endTime">
          {{ formatDateTime(selectedExecution.endTime) }}
        </el-descriptions-item>

        <el-descriptions-item label="执行耗时" v-if="selectedExecution.startTime && selectedExecution.endTime">
          {{ calculateDuration(selectedExecution.startTime, selectedExecution.endTime) }}
        </el-descriptions-item>

        <!-- 盈亏信息 -->
        <el-descriptions-item label="盈亏金额" v-if="selectedExecution.profit !== null && selectedExecution.profit !== undefined">
          <span :class="selectedExecution.profit >= 0 ? 'text-up font-medium' : 'text-down font-medium'">
            {{ selectedExecution.profit >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(selectedExecution.profit)) }}
          </span>
        </el-descriptions-item>

        <el-descriptions-item label="盈亏比例" v-if="selectedExecution.profitRate !== null && selectedExecution.profitRate !== undefined">
          <span :class="selectedExecution.profitRate >= 0 ? 'text-up font-medium' : 'text-down font-medium'">
            {{ selectedExecution.profitRate >= 0 ? '+' : '' }}{{ formatPercent(selectedExecution.profitRate) }}
          </span>
        </el-descriptions-item>

        <!-- 执行日志 -->
        <el-descriptions-item label="执行日志" :span="2" v-if="selectedExecution.executionLog">
          <div class="bg-gray-50 p-3 rounded text-xs font-mono max-h-40 overflow-y-auto">
            {{ selectedExecution.executionLog }}
          </div>
        </el-descriptions-item>

        <!-- 备注 -->
        <el-descriptions-item label="备注" :span="2" v-if="selectedExecution.remark">
          {{ selectedExecution.remark }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { formatPrice, formatAmount, formatDate, formatPercent } from '@/utils/format'

// 格式化日期时间
const formatDateTime = (date: string | Date) => {
  if (!date) return '-'
  const d = new Date(date)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

// 计算时长
const calculateDuration = (startTime: string | Date, endTime: string | Date) => {
  const start = new Date(startTime).getTime()
  const end = new Date(endTime).getTime()
  const duration = end - start

  if (duration < 1000) {
    return `${duration}ms`
  } else if (duration < 60000) {
    return `${(duration / 1000).toFixed(2)}s`
  } else {
    const minutes = Math.floor(duration / 60000)
    const seconds = ((duration % 60000) / 1000).toFixed(0)
    return `${minutes}m ${seconds}s`
  }
}

// 统计数据
const stats = reactive({
  todayCount: 12,
  successRate: 0.95,
  avgLatency: 125,
  failedCount: 2,
  pendingCount: 3,
  executedCount: 28,
  closedCount: 15
})

// 执行记录
const executions = ref<any[]>([])
const loading = ref(false)

// 执行详情对话框
const detailDialogVisible = ref(false)
const selectedExecution = ref<any | null>(null)

// 筛选条件
const filters = reactive({
  status: ''
})
const dateRange = ref<[Date, Date] | null>(null)

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 加载执行记录
const loadExecutions = async () => {
  loading.value = true
  try {
    // TODO: Implement getExecutions API
    // const data = await tradingApi.getExecutions({
    //   status: filters.status || undefined,
    //   startDate: dateRange.value?.[0]?.toISOString().split('T')[0],
    //   endDate: dateRange.value?.[1]?.toISOString().split('T')[0],
    //   page: pagination.page,
    //   pageSize: pagination.pageSize
    // })
    // executions.value = data.items
    // pagination.total = data.total
    executions.value = []
    pagination.total = 0
  } catch (error) {
    ElMessage.error('加载执行记录失败')
  } finally {
    loading.value = false
  }
}

// 筛选变化
const handleFilterChange = () => {
  pagination.page = 1
  loadExecutions()
}

// 刷新
const handleRefresh = () => {
  loadExecutions()
}

// 分页
const handlePageChange = () => {
  loadExecutions()
}

const handlePageSizeChange = () => {
  pagination.page = 1
  loadExecutions()
}

// 执行
const handleExecute = async (execution: any) => {
  try {
    await ElMessageBox.confirm(
      `确认执行 ${execution.action === 'BUY' ? '买入' : '卖出'} ${execution.symbol}？`,
      '确认执行',
      { type: 'warning' }
    )

    // TODO: Implement executeSignal API
    // await tradingApi.executeSignal(execution.signalId)
    ElMessage.success('执行成功')

    // 刷新列表
    loadExecutions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('执行失败')
    }
  }
}

// 取消
const handleCancel = async (execution: any) => {
  try {
    await ElMessageBox.confirm(
      `确认取消执行 #${execution.executionId}？`,
      '取消执行',
      { type: 'warning' }
    )

    // TODO: Implement cancelExecution API
    // await tradingApi.cancelExecution(execution.executionId)
    ElMessage.success('已取消')

    // 刷新列表
    loadExecutions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消失败')
    }
  }
}

// 平仓
const handleClose = async (execution: any) => {
  try {
    await ElMessageBox.confirm(
      `确认平仓 ${execution.symbol}？`,
      '确认平仓',
      { type: 'warning' }
    )

    // TODO: Implement closePosition API
    // await tradingApi.closePosition(execution.symbol)
    ElMessage.success('平仓成功')

    // 刷新列表
    loadExecutions()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('平仓失败')
    }
  }
}

// 查看详情
const handleViewDetail = (execution: any) => {
  selectedExecution.value = execution
  detailDialogVisible.value = true
}

// 工具函数
const getStatusTagType = (status: string) => {
  const typeMap: Record<string, any> = {
    'pending': 'warning',
    'executed': 'primary',
    'closed': 'success',
    'cancelled': 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'pending': '待执行',
    'executed': '已执行',
    'closed': '已平仓',
    'cancelled': '已取消'
  }
  return textMap[status] || status
}

// 组件挂载
onMounted(() => {
  loadExecutions()
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'Executions'
})
</script>

<style scoped lang="scss">
.executions {
  .stat-card {
    :deep(.el-card__body) {
      padding: 16px;
    }

    .stat-label {
      font-size: 12px;
      color: #9ca3af;
      margin-bottom: 4px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #0f172a;
    }
  }
}
</style>
