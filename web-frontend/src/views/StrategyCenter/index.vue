<template>
  <div class="strategy-center">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-2xl font-bold mb-2">📊 策略运营中心</h2>
      <p class="text-sm text-gray-500">统一监控所有运行中的策略 - 实时PnL、持仓、风险、绩效</p>
    </div>

    <!-- 总览卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-6">
      <el-card class="stat-card">
        <div class="flex items-center justify-between mb-2">
          <span class="stat-label">运行中策略</span>
          <span class="icon-badge bg-green-100 text-green-600">🟢</span>
        </div>
        <div class="stat-value">{{ overview.runningCount }}</div>
        <div class="stat-sub">{{ overview.profitCount }}个盈利 / {{ overview.lossCount }}个亏损</div>
      </el-card>

      <el-card class="stat-card">
        <div class="flex items-center justify-between mb-2">
          <span class="stat-label">今日总PnL</span>
          <span class="icon-badge bg-green-100 text-green-600">💰</span>
        </div>
        <div :class="['stat-value', overview.todayPnl >= 0 ? 'text-green-600' : 'text-red-600']">
          {{ overview.todayPnl >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(overview.todayPnl)) }}
        </div>
        <div :class="['stat-sub', overview.todayPnlPercent >= 0 ? 'text-green-600' : 'text-red-600']">
          {{ overview.todayPnlPercent >= 0 ? '▲' : '▼' }} {{ overview.todayPnlPercent >= 0 ? '+' : '' }}{{ formatPercent(overview.todayPnlPercent) }}
        </div>
      </el-card>

      <el-card class="stat-card">
        <div class="flex items-center justify-between mb-2">
          <span class="stat-label">总持仓</span>
          <span class="icon-badge bg-blue-100 text-blue-600">📈</span>
        </div>
        <div class="stat-value">{{ overview.totalPositions }}只</div>
        <div class="stat-sub">分布在{{ overview.runningCount }}个策略</div>
      </el-card>

      <el-card class="stat-card">
        <div class="flex items-center justify-between mb-2">
          <span class="stat-label">风险度</span>
          <span class="icon-badge bg-yellow-100 text-yellow-600">⚠️</span>
        </div>
        <div class="stat-value text-yellow-600">{{ overview.riskLevel }}</div>
        <div class="stat-sub">仓位使用率 {{ overview.positionUsage }}%</div>
      </el-card>
    </div>

    <!-- 策略列表 -->
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">策略列表</span>
          <div class="flex items-center gap-2">
            <el-select v-model="filters.status" placeholder="全部状态" size="small" style="width: 120px" @change="handleFilterChange">
              <el-option label="全部状态" value="" />
              <el-option label="运行中" value="running" />
              <el-option label="已停止" value="stopped" />
            </el-select>
            <el-button size="small" @click="handleRefresh" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button type="primary" size="small" @click="handleCreateStrategy">
              + 新建策略
            </el-button>
          </div>
        </div>
      </template>

      <!-- 策略卡片列表 -->
      <div class="space-y-4" v-loading="loading">
        <div v-for="strategy in strategies" :key="strategy.id" class="strategy-card">
          <div class="flex items-start justify-between mb-3">
            <div class="flex-1">
              <div class="flex items-center gap-3 mb-2">
                <h4 class="text-lg font-bold">{{ strategy.name }}</h4>
                <el-tag :type="strategy.status === 'running' ? 'success' : 'info'" size="small">
                  {{ strategy.status === 'running' ? '🟢 运行中' : '⏸ 已停止' }}
                </el-tag>
                <span class="text-xs text-gray-500">启动于 {{ formatDate(strategy.startDate) }}</span>
              </div>
              <p class="text-sm text-gray-600">{{ strategy.description }}</p>
            </div>
            <div class="flex items-center gap-2">
              <el-switch
                v-model="strategy.status"
                active-value="running"
                inactive-value="stopped"
                @change="handleToggleStrategy(strategy)"
              />
            </div>
          </div>

          <div class="grid grid-cols-6 gap-4 mb-3">
            <div>
              <p class="text-xs text-gray-500 mb-1">今日PnL</p>
              <p :class="['text-lg font-bold', strategy.todayPnl >= 0 ? 'text-green-600' : 'text-red-600']">
                {{ strategy.todayPnl >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(strategy.todayPnl)) }}
              </p>
              <p :class="['text-xs', strategy.todayPnlPercent >= 0 ? 'text-green-600' : 'text-red-600']">
                {{ strategy.todayPnlPercent >= 0 ? '+' : '' }}{{ formatPercent(strategy.todayPnlPercent) }}
              </p>
            </div>

            <div>
              <p class="text-xs text-gray-500 mb-1">累计收益</p>
              <p :class="['text-lg font-bold', strategy.totalReturn >= 0 ? 'text-green-600' : 'text-red-600']">
                {{ strategy.totalReturn >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(strategy.totalReturn)) }}
              </p>
              <p :class="['text-xs', strategy.totalReturnPercent >= 0 ? 'text-green-600' : 'text-red-600']">
                {{ strategy.totalReturnPercent >= 0 ? '+' : '' }}{{ formatPercent(strategy.totalReturnPercent) }}
              </p>
            </div>

            <div>
              <p class="text-xs text-gray-500 mb-1">持仓</p>
              <p class="text-lg font-bold">{{ strategy.positionCount }}只</p>
              <p class="text-xs text-gray-500 truncate">{{ Array.isArray(strategy.positions) ? strategy.positions.join(', ') : (strategy.positionCount || 0) + '只' }}</p>
            </div>

            <div>
              <p class="text-xs text-gray-500 mb-1">胜率</p>
              <p class="text-lg font-bold">{{ formatPercent(strategy.winRate) }}</p>
              <p class="text-xs text-gray-500">{{ strategy.winTrades }}/{{ strategy.totalTrades }}</p>
            </div>

            <div>
              <p class="text-xs text-gray-500 mb-1">夏普比率</p>
              <p class="text-lg font-bold">{{ strategy.sharpeRatio?.toFixed(2) ?? '-' }}</p>
            </div>

            <div>
              <p class="text-xs text-gray-500 mb-1">最大回撤</p>
              <p class="text-lg font-bold text-red-600">{{ formatPercent(strategy.maxDrawdown) }}</p>
            </div>
          </div>

          <div class="flex items-center justify-between pt-3 border-t border-gray-200">
            <div class="flex items-center gap-4 text-xs text-gray-500">
              <span>运行时长: {{ strategy.runningDays }}天</span>
              <span>信号数: {{ strategy.signalCount }}</span>
              <span>最后运行: {{ formatDateTime(strategy.lastRunTime) }}</span>
            </div>
            <div class="flex items-center gap-2">
              <el-button size="small" @click="handleViewDetail(strategy)">查看详情</el-button>
              <el-button size="small" @click="handleEditStrategy(strategy)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDeleteStrategy(strategy)">删除</el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 空状态 -->
      <el-empty v-if="strategies.length === 0 && !loading" description="暂无策略" />
    </el-card>

    <!-- 策略新建/编辑对话框 -->
    <el-dialog
      v-model="strategyDialogVisible"
      :title="strategyDialogMode === 'create' ? '新建策略' : '编辑策略'"
      width="600px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="strategyFormRef"
        :model="strategyForm"
        :rules="strategyFormRules"
        label-width="100px"
      >
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="strategyForm.name" placeholder="请输入策略名称" />
        </el-form-item>

        <el-form-item label="策略描述" prop="description">
          <el-input
            v-model="strategyForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入策略描述"
          />
        </el-form-item>

        <el-form-item label="策略类型" prop="type">
          <el-select v-model="strategyForm.type" placeholder="请选择策略类型" class="w-full">
            <el-option label="趋势跟踪" value="trend" />
            <el-option label="均值回归" value="mean_reversion" />
            <el-option label="动量策略" value="momentum" />
            <el-option label="套利策略" value="arbitrage" />
          </el-select>
        </el-form-item>

        <el-form-item label="风险等级" prop="riskLevel">
          <el-radio-group v-model="strategyForm.riskLevel">
            <el-radio label="low">低风险</el-radio>
            <el-radio label="medium">中风险</el-radio>
            <el-radio label="high">高风险</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-divider content-position="left">策略参数</el-divider>

        <el-form-item label="快线周期">
          <el-input-number v-model="strategyForm.parameters.fastPeriod" :min="1" :max="100" />
        </el-form-item>

        <el-form-item label="慢线周期">
          <el-input-number v-model="strategyForm.parameters.slowPeriod" :min="1" :max="200" />
        </el-form-item>

        <el-divider content-position="left">风控设置</el-divider>

        <el-form-item label="止损比例">
          <el-input-number
            v-model="strategyForm.parameters.stopLoss"
            :min="0"
            :max="1"
            :step="0.01"
            :precision="2"
          />
          <span class="ml-2 text-sm text-gray-500">{{ formatPercent(strategyForm.parameters.stopLoss) }}</span>
        </el-form-item>

        <el-form-item label="止盈比例">
          <el-input-number
            v-model="strategyForm.parameters.takeProfit"
            :min="0"
            :max="2"
            :step="0.01"
            :precision="2"
          />
          <span class="ml-2 text-sm text-gray-500">{{ formatPercent(strategyForm.parameters.takeProfit) }}</span>
        </el-form-item>

        <el-form-item label="最大持仓数">
          <el-input-number v-model="strategyForm.parameters.maxPositions" :min="1" :max="20" />
        </el-form-item>

        <el-form-item label="单仓位大小">
          <el-input-number
            v-model="strategyForm.parameters.positionSize"
            :min="0.01"
            :max="1"
            :step="0.01"
            :precision="2"
          />
          <span class="ml-2 text-sm text-gray-500">{{ formatPercent(strategyForm.parameters.positionSize) }}</span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="strategyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitStrategy">
          {{ strategyDialogMode === 'create' ? '创建' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 策略详情对话框 -->
    <el-dialog
      v-model="detailDialogVisible"
      title="策略详情"
      width="800px"
    >
      <div v-if="currentStrategy">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="策略名称">{{ currentStrategy.name }}</el-descriptions-item>
          <el-descriptions-item label="策略类型">
            <el-tag>{{ getStrategyTypeLabel(currentStrategy.type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="运行状态">
            <el-tag :type="currentStrategy.status === 'running' ? 'success' : 'info'">
              {{ currentStrategy.status === 'running' ? '运行中' : '已停止' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(currentStrategy.startDate || currentStrategy.createdAt) }}
          </el-descriptions-item>
          <el-descriptions-item label="策略描述" :span="2">
            {{ currentStrategy.description }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">绩效指标</el-divider>

        <div class="grid grid-cols-4 gap-3 mb-4">
          <div class="metric-card">
            <div class="metric-label">累计收益</div>
            <div :class="['metric-value', currentStrategy.totalReturn >= 0 ? 'text-green-600' : 'text-red-600']">
              {{ currentStrategy.totalReturn >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(currentStrategy.totalReturn)) }}
            </div>
            <div :class="['text-xs', currentStrategy.totalReturnPercent >= 0 ? 'text-green-600' : 'text-red-600']">
              {{ currentStrategy.totalReturnPercent >= 0 ? '+' : '' }}{{ formatPercent(currentStrategy.totalReturnPercent) }}
            </div>
          </div>

          <div class="metric-card">
            <div class="metric-label">夏普比率</div>
            <div class="metric-value">{{ currentStrategy.sharpeRatio?.toFixed(2) || 'N/A' }}</div>
          </div>

          <div class="metric-card">
            <div class="metric-label">最大回撤</div>
            <div class="metric-value text-red-600">{{ formatPercent(currentStrategy.maxDrawdown || 0) }}</div>
          </div>

          <div class="metric-card">
            <div class="metric-label">胜率</div>
            <div class="metric-value">{{ formatPercent(currentStrategy.winRate || 0) }}</div>
          </div>
        </div>

        <el-divider content-position="left">策略参数</el-divider>

        <el-descriptions :column="2" border>
          <el-descriptions-item
            v-for="(value, key) in currentStrategy.parameters"
            :key="String(key)"
            :label="getParameterLabel(String(key))"
          >
            {{ formatParameterValue(String(key), value) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">持仓信息</el-divider>

        <div class="text-sm text-gray-600 mb-2">
          当前持仓: {{ currentStrategy.positionCount || 0 }}只
        </div>
        <div v-if="currentStrategy.positions && currentStrategy.positions.length > 0" class="flex flex-wrap gap-2">
          <el-tag v-for="pos in currentStrategy.positions" :key="pos">{{ pos }}</el-tag>
        </div>
        <div v-else class="text-sm text-gray-400">暂无持仓</div>
      </div>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button type="primary" @click="handleEditStrategy(currentStrategy)">编辑策略</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { strategyApi } from '@/services/api'
import { formatPrice, formatPercent, formatDate, formatDateTime } from '@/utils/format'

// 总览数据
const overview = reactive({
  totalStrategies: 0,
  runningCount: 0,
  stoppedCount: 0,
  profitCount: 0,
  lossCount: 0,
  todayPnl: 0,
  todayPnlPercent: 0,
  totalPositions: 0,
  winRate: 0,
  riskLevel: '低',
  positionUsage: 0
})

// 从策略列表和绩效数据动态计算 overview
const computeOverview = async () => {
  try {
    const strategyList = strategies.value || []

    overview.totalStrategies = strategyList.length
    overview.runningCount = strategyList.filter(s => s.status === 'running').length
    overview.stoppedCount = strategyList.filter(s => s.status === 'stopped').length

    // 加载各策略绩效来计算汇总（最多20个，避免请求过多）
    let totalPnl = 0
    let totalWinRate = 0
    let performanceCount = 0
    let totalPositions = 0
    let profitCount = 0
    let lossCount = 0

    const maxFetch = Math.min(strategyList.length, 20)
    for (let i = 0; i < maxFetch; i++) {
      const strategy = strategyList[i]
      try {
        const perf = await strategyApi.getStrategyPerformance(strategy.id)
        if (perf) {
          const pnl = (perf as any).totalReturn || (perf as any).stats?.total_return || 0
          totalPnl += pnl
          if (pnl > 0) profitCount++
          else if (pnl < 0) lossCount++

          totalWinRate += (perf as any).winRate || (perf as any).stats?.win_rate || 0
          totalPositions += (perf as any).positions || (perf as any).execution_count || 0
          performanceCount++
        }
      } catch {
        // 跳过无绩效数据的策略
      }
    }

    overview.todayPnl = Math.round(totalPnl * 100) / 100
    overview.profitCount = profitCount || overview.runningCount - overview.stoppedCount
    overview.lossCount = lossCount
    overview.winRate = performanceCount > 0
      ? Math.round((totalWinRate / performanceCount) * 100) / 100
      : 0
    overview.totalPositions = totalPositions

    // 从绩效数据估算百分比和风险等级
    overview.todayPnlPercent = performanceCount > 0
      ? Math.round((totalPnl / performanceCount) * 10000) / 10000
      : 0
    overview.positionUsage = performanceCount > 0
      ? Math.min(Math.round((totalPositions / (performanceCount * 5)) * 100), 100)
      : 0
    overview.riskLevel = overview.positionUsage > 70 ? '高' : overview.positionUsage > 30 ? '中' : '低'
  } catch (error) {
    console.error('计算概览数据失败:', error)
  }
}

// 策略列表
const strategies = ref<any[]>([])
const loading = ref(false)

// 筛选条件
const filters = reactive({
  status: ''
})

// 加载策略列表
const loadStrategies = async () => {
  loading.value = true
  try {
    const data = await strategyApi.getStrategies({
      status: filters.status || undefined
    })
    strategies.value = data.items || []
    await computeOverview()
  } catch (error) {
    ElMessage.error('加载策略列表失败')
  } finally {
    loading.value = false
  }
}

// 筛选变化
const handleFilterChange = () => {
  loadStrategies()
}

// 刷新
const handleRefresh = () => {
  loadStrategies()
}

// 启动/停止策略
const handleToggleStrategy = async (strategy: any) => {
  try {
    const action = strategy.status === 'running' ? '启动' : '停止'
    await ElMessageBox.confirm(
      `确认${action}策略 "${strategy.name}"？`,
      `${action}策略`,
      { type: 'warning' }
    )

    if (strategy.status === 'running') {
      await strategyApi.startStrategy(strategy.id)
      ElMessage.success('策略已启动')
    } else {
      await strategyApi.stopStrategy(strategy.id)
      ElMessage.success('策略已停止')
    }

    // 刷新列表
    loadStrategies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('操作失败')
      // 恢复状态
      strategy.status = strategy.status === 'running' ? 'stopped' : 'running'
    }
  }
}

// 策略表单对话框
const strategyDialogVisible = ref(false)
const strategyDialogMode = ref<'create' | 'edit'>('create')
const strategyFormRef = ref<any>()
const strategyForm = reactive({
  id: '',
  name: '',
  description: '',
  type: 'trend' as 'trend' | 'mean_reversion' | 'momentum' | 'arbitrage',
  riskLevel: 'medium' as 'low' | 'medium' | 'high',
  parameters: {
    fastPeriod: 5,
    slowPeriod: 20,
    stopLoss: 0.05,
    takeProfit: 0.15,
    maxPositions: 5,
    positionSize: 0.2
  }
})

const strategyFormRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入策略描述', trigger: 'blur' }],
  type: [{ required: true, message: '请选择策略类型', trigger: 'change' }],
  riskLevel: [{ required: true, message: '请选择风险等级', trigger: 'change' }]
}

// 策略详情对话框
const detailDialogVisible = ref(false)
const currentStrategy = ref<any>(null)

// 新建策略
const handleCreateStrategy = () => {
  strategyDialogMode.value = 'create'
  Object.assign(strategyForm, {
    id: '',
    name: '',
    description: '',
    type: 'trend',
    riskLevel: 'medium',
    parameters: {
      fastPeriod: 5,
      slowPeriod: 20,
      stopLoss: 0.05,
      takeProfit: 0.15,
      maxPositions: 5,
      positionSize: 0.2
    }
  })
  strategyDialogVisible.value = true
}

// 查看详情
const handleViewDetail = async (strategy: any) => {
  try {
    const detail = await strategyApi.getStrategyById(strategy.id)
    currentStrategy.value = detail
    detailDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载策略详情失败')
  }
}

// 编辑策略
const handleEditStrategy = (strategy: any) => {
  strategyDialogMode.value = 'edit'
  Object.assign(strategyForm, {
    id: strategy.id,
    name: strategy.name,
    description: strategy.description,
    type: strategy.type || 'trend',
    riskLevel: strategy.riskLevel || 'medium',
    parameters: strategy.parameters || {
      fastPeriod: 5,
      slowPeriod: 20,
      stopLoss: 0.05,
      takeProfit: 0.15,
      maxPositions: 5,
      positionSize: 0.2
    }
  })
  strategyDialogVisible.value = true
}

// 提交策略表单
const handleSubmitStrategy = async () => {
  if (!strategyFormRef.value) return

  await strategyFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    try {
      if (strategyDialogMode.value === 'create') {
        await strategyApi.createStrategy({
          name: strategyForm.name,
          description: strategyForm.description,
          type: strategyForm.type,
          code: strategyForm.type,
          parameters: strategyForm.parameters,
          riskLevel: strategyForm.riskLevel
        })
        ElMessage.success('策略创建成功')
      } else {
        await strategyApi.updateStrategy({
          id: strategyForm.id,
          name: strategyForm.name,
          description: strategyForm.description,
          parameters: strategyForm.parameters
        })
        ElMessage.success('策略更新成功')
      }

      strategyDialogVisible.value = false
      loadStrategies()
    } catch (error) {
      ElMessage.error(strategyDialogMode.value === 'create' ? '创建失败' : '更新失败')
    }
  })
}

// 删除策略
const handleDeleteStrategy = async (strategy: any) => {
  try {
    await ElMessageBox.confirm(
      `确认删除策略 "${strategy.name}"？此操作不可恢复。`,
      '删除策略',
      { type: 'warning' }
    )

    await strategyApi.deleteStrategy(strategy.id)
    ElMessage.success('策略已删除')

    // 刷新列表
    loadStrategies()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 组件挂载
onMounted(async () => {
  await loadStrategies()
})

// 辅助函数
const getStrategyTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    trend: '趋势跟踪',
    mean_reversion: '均值回归',
    momentum: '动量策略',
    arbitrage: '套利策略'
  }
  return labels[type] || type
}

const getParameterLabel = (key: string) => {
  const labels: Record<string, string> = {
    fastPeriod: '快线周期',
    slowPeriod: '慢线周期',
    stopLoss: '止损比例',
    takeProfit: '止盈比例',
    maxPositions: '最大持仓数',
    positionSize: '单仓位大小',
    rsiPeriod: 'RSI周期',
    macdFast: 'MACD快线',
    macdSlow: 'MACD慢线',
    macdSignal: 'MACD信号线'
  }
  return labels[key] || key
}

const formatParameterValue = (key: string, value: any) => {
  if (typeof value === 'number') {
    if (key.includes('Percent') || key.includes('Loss') || key.includes('Profit') || key.includes('Size')) {
      return formatPercent(value)
    }
    return String(value)
  }
  return String(value)
}
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'StrategyCenter'
})
</script>

<style scoped lang="scss">
.strategy-center {
  .stat-card {
    :deep(.el-card__body) {
      padding: 20px;
    }

    .stat-label {
      font-size: 11px;
      color: #64748b;
      font-weight: 500;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #0f172a;
      margin: 4px 0;
    }

    .stat-sub {
      font-size: 12px;
      color: #9ca3af;
    }

    .icon-badge {
      width: 32px;
      height: 32px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 14px;
    }
  }

  .strategy-card {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 16px;
    transition: all 0.2s;

    &:hover {
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
  }

  .space-y-4 > * + * {
    margin-top: 16px;
  }

  .metric-card {
    background: #f8fafc;
    border-radius: 8px;
    padding: 12px;
    text-align: center;

    .metric-label {
      font-size: 12px;
      color: #64748b;
      margin-bottom: 4px;
    }

    .metric-value {
      font-size: 18px;
      font-weight: bold;
      color: #0f172a;
    }
  }

  :deep(.el-input-number) {
    width: 100%;
  }
}
</style>
