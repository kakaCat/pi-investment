<template>
  <div class="stock-detail">
    <!-- 面包屑导航 -->
    <el-breadcrumb separator="/" class="mb-4">
      <el-breadcrumb-item :to="{ name: 'StockResearch' }">股票列表</el-breadcrumb-item>
      <el-breadcrumb-item v-if="stockInfo">
        {{ stockInfo.symbol }} {{ stockInfo.name }}
      </el-breadcrumb-item>
    </el-breadcrumb>

    <!-- 股票基本信息 -->
    <el-card class="stock-header mb-4" v-if="stockInfo">
      <div class="flex items-center justify-between">
        <div>
          <div class="flex items-center gap-3 mb-2">
            <h2 class="text-2xl font-bold">{{ stockInfo.symbol }}</h2>
            <span class="text-lg text-gray-500">{{ stockInfo.name }}</span>
            <el-tag v-if="stockInfo.market" size="small">{{ stockInfo.market }}</el-tag>
            <el-tag size="small" type="info">{{ stockInfo.industry }}</el-tag>
          </div>
          <div class="flex items-center gap-4">
            <span class="text-3xl font-bold">¥{{ formatPrice(stockInfo.price || stockInfo.currentPrice) }}</span>
            <span :class="['text-lg font-semibold', stockInfo.changePercent >= 0 ? 'text-up' : 'text-down']">
              {{ stockInfo.changePercent >= 0 ? '+' : '' }}{{ formatPrice(stockInfo.change) }}
              ({{ stockInfo.changePercent >= 0 ? '+' : '' }}{{ formatPercent(stockInfo.changePercent) }})
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <el-button type="primary" @click="handleCalculateFactors">计算因子</el-button>
          <el-button
            v-if="!isInWatchlist"
            type="success"
            @click="handleAddToWatchlist"
            :loading="watchlistLoading"
          >
            加入自选
          </el-button>
          <el-button
            v-else
            @click="handleRemoveFromWatchlist"
            :loading="watchlistLoading"
          >
            <el-icon><StarFilled /></el-icon>
            已自选
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- Tab切换 -->
    <el-card class="stock-tabs">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <!-- K线图Tab -->
        <el-tab-pane label="K线图" name="kline">
          <div class="kline-container">
            <!-- 图表工具栏 -->
            <div class="chart-toolbar">
              <div class="toolbar-section">
                <span class="toolbar-label">时间周期</span>
                <el-radio-group v-model="timeframe" size="small" @change="handleTimeframeChange">
                  <el-radio-button label="1m">1分钟</el-radio-button>
                  <el-radio-button label="5m">5分钟</el-radio-button>
                  <el-radio-button label="15m">15分钟</el-radio-button>
                  <el-radio-button label="30m">30分钟</el-radio-button>
                  <el-radio-button label="1h">1小时</el-radio-button>
                  <el-radio-button label="4h">4小时</el-radio-button>
                  <el-radio-button label="1d">日线</el-radio-button>
                  <el-radio-button label="1w">周线</el-radio-button>
                </el-radio-group>
              </div>
              <div class="toolbar-section">
                <span class="toolbar-label">技术指标</span>
                <el-checkbox-group v-model="indicators" size="small" @change="handleIndicatorChange">
                  <el-checkbox label="MA">均线</el-checkbox>
                  <el-checkbox label="EMA">EMA</el-checkbox>
                  <el-checkbox label="BOLL">布林带</el-checkbox>
                  <el-checkbox label="VOL">成交量</el-checkbox>
                  <el-checkbox label="MACD">MACD</el-checkbox>
                  <el-checkbox label="RSI">RSI</el-checkbox>
                  <el-checkbox label="KDJ">KDJ</el-checkbox>
                </el-checkbox-group>
                <el-divider direction="vertical" />
                <el-checkbox v-model="showSignals" @change="handleShowSignalsChange">
                  显示买卖点
                </el-checkbox>
              </div>
            </div>

            <!-- K线图 -->
            <KLineChart
              v-if="klineData.length > 0"
              :data="klineData as any"
              :indicators="indicators"
              :signals="showSignals ? signals : []"
              :height="600 as any"
            />
            <el-empty v-else description="暂无K线数据" />
          </div>
        </el-tab-pane>

        <!-- 因子一览Tab -->
        <el-tab-pane label="因子一览" name="factors">
          <div class="factors-container">
            <el-table :data="factors" stripe>
              <el-table-column prop="name" label="因子名称" width="200" />
              <el-table-column prop="category" label="类别" width="120">
                <template #default="{ row }">
                  <el-tag :type="getFactorCategoryType(row.category)" size="small">
                    {{ row.category }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="value" label="当前值" width="150">
                <template #default="{ row }">
                  <span class="font-medium">{{ formatFactorValue(row.value) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="percentile" label="分位数" width="120">
                <template #default="{ row }">
                  <el-progress
                    :percentage="row.percentile"
                    :color="getPercentileColor(row.percentile)"
                  />
                </template>
              </el-table-column>
              <el-table-column prop="description" label="说明" show-overflow-tooltip />
              <el-table-column prop="updateTime" label="更新时间" width="180">
                <template #default="{ row }">
                  {{ formatDateTime(row.updateTime) }}
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

        <!-- 技术指标Tab -->
        <el-tab-pane label="技术指标" name="technical">
          <div class="technical-container">
            <el-row :gutter="16">
              <el-col :span="8" v-for="indicator in technicalIndicators" :key="indicator.name">
                <el-card class="indicator-card mb-4">
                  <template #header>
                    <div class="flex items-center justify-between">
                      <span class="font-semibold">{{ indicator.name }}</span>
                      <el-tag :type="indicator.signal === 'BUY' ? 'danger' : indicator.signal === 'SELL' ? 'success' : 'info'" size="small">
                        {{ indicator.signal }}
                      </el-tag>
                    </div>
                  </template>
                  <div class="space-y-2">
                    <div v-for="(value, key) in indicator.values" :key="key" class="flex justify-between text-sm">
                      <span class="text-gray-600">{{ key }}:</span>
                      <span class="font-medium">{{ value }}</span>
                    </div>
                  </div>
                </el-card>
              </el-col>
            </el-row>
          </div>
        </el-tab-pane>

        <!-- 历史信号Tab -->
        <el-tab-pane label="历史信号" name="signals">
          <div class="signals-container">
            <el-table :data="historicalSignals" stripe>
              <el-table-column prop="time" label="时间" width="180">
                <template #default="{ row }">
                  {{ formatDateTime(row.time) }}
                </template>
              </el-table-column>
              <el-table-column prop="type" label="信号类型" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.type === 'BUY' ? 'danger' : 'success'" size="small">
                    {{ row.type }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="price" label="触发价格" width="120">
                <template #default="{ row }">
                  ¥{{ formatPrice(row.price) }}
                </template>
              </el-table-column>
              <el-table-column prop="confidence" label="置信度" width="120">
                <template #default="{ row }">
                  <el-progress :percentage="row.confidence * 100" :stroke-width="8" />
                </template>
              </el-table-column>
              <el-table-column prop="strategy" label="策略来源" width="150" />
              <el-table-column prop="status" label="状态" width="100">
                <template #default="{ row }">
                  <el-tag :type="getSignalStatusType(row.status)" size="small">
                    {{ getSignalStatusText(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="result" label="执行结果" show-overflow-tooltip />
            </el-table>

            <!-- 分页 -->
            <div class="mt-4 flex justify-end">
              <el-pagination
                v-model:current-page="signalPagination.page"
                v-model:page-size="signalPagination.pageSize"
                :total="signalPagination.total"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                @size-change="handleSignalPageSizeChange"
                @current-change="handleSignalPageChange"
              />
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <!-- 添加到自选股弹窗 -->
    <el-dialog v-model="watchlistDialogVisible" title="添加到自选股" width="400px">
      <el-form :model="watchlistForm" label-width="80px">
        <el-form-item label="股票代码">
          <el-input v-model="watchlistForm.symbol" disabled />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="watchlistForm.symbolName" disabled />
        </el-form-item>
        <el-form-item label="分组">
          <el-select v-model="watchlistForm.groupId" placeholder="请选择分组" class="w-full" clearable>
            <el-option label="默认分组" value="" />
            <el-option
              v-for="group in watchlistGroups"
              :key="group.id"
              :label="group.name"
              :value="group.id"
            />
          </el-select>
          <div class="mt-2">
            <el-button size="small" text type="primary" @click="handleCreateGroup">
              + 新建分组
            </el-button>
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="watchlistForm.note"
            type="textarea"
            :rows="3"
            placeholder="可选"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="watchlistDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmAddToWatchlist" :loading="watchlistLoading">
          添加
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建分组弹窗 -->
    <el-dialog v-model="groupDialogVisible" title="新建分组" width="400px">
      <el-form :model="groupForm" label-width="80px">
        <el-form-item label="分组名称">
          <el-input v-model="groupForm.name" placeholder="请输入分组名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="groupForm.description"
            type="textarea"
            :rows="3"
            placeholder="可选"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="groupDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmCreateGroup" :loading="groupLoading">
          创建
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { StarFilled } from '@element-plus/icons-vue'
import KLineChart from '@/components/charts/KLineChart/index.vue'
import { stockApi, signalApi } from '@/services/api'
import { useMarketWebSocket } from '@/composables/useWebSocket'
import { formatPrice, formatPercent, formatDateTime } from '@/utils/format'
import type { StockInfo, TradingSignal, WatchlistGroup } from '@/types/models'

const route = useRoute()

// 股票信息
const stockInfo = ref<StockInfo | null>(null)
const symbol = ref<string>(route.params.symbol as string)

// Tab状态
const activeTab = ref('kline')

// K线图相关
const timeframe = ref('1d')
const indicators = ref<string[]>(['MA', 'VOL'])
const showSignals = ref(true)
const klineData = ref<any[]>([])
const signals = ref<TradingSignal[]>([])

// 因子数据
const factors = ref<any[]>([])

// 技术指标数据
const technicalIndicators = ref<any[]>([])

// 历史信号
const historicalSignals = ref<TradingSignal[]>([])
const signalPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 自选股相关
const isInWatchlist = ref(false)
const watchlistLoading = ref(false)
const watchlistDialogVisible = ref(false)
const watchlistGroups = ref<WatchlistGroup[]>([])
const watchlistForm = reactive({
  symbol: '',
  symbolName: '',
  groupId: '',
  note: ''
})

// 分组管理
const groupDialogVisible = ref(false)
const groupLoading = ref(false)
const groupForm = reactive({
  name: '',
  description: ''
})

// WebSocket连接
const { subscribe, unsubscribe, on } = useMarketWebSocket()

// 监听行情更新
on('quote', (data: any) => {
  if (data.symbol === symbol.value && stockInfo.value) {
    stockInfo.value.price = data.price
    stockInfo.value.currentPrice = data.price
    stockInfo.value.change = data.change
    stockInfo.value.changePercent = data.changePercent
  }
})

// 加载股票信息
const loadStockInfo = async () => {
  try {
    const data = await stockApi.getStockDetail(symbol.value)
    stockInfo.value = data

    // 订阅实时行情
    subscribe(symbol.value)

    // 检查是否在自选股中
    checkWatchlistStatus()
  } catch (error) {
    ElMessage.error('加载股票信息失败')
  }
}

// 检查自选股状态
const checkWatchlistStatus = async () => {
  try {
    const result = await stockApi.isInWatchlist(symbol.value)
    isInWatchlist.value = result.isInWatchlist || false
  } catch (error) {
    console.error('检查自选股状态失败', error)
  }
}

// 加载自选股分组
const loadWatchlistGroups = async () => {
  try {
    const data = await stockApi.getWatchlistGroups()
    watchlistGroups.value = data
  } catch (error) {
    console.error('加载自选股分组失败', error)
  }
}

// 加载K线数据
const loadKlineData = async () => {
  try {
    const data = await stockApi.getKLineData({
      symbol: symbol.value,
      timeFrame: timeframe.value
    })
    klineData.value = data

    // 如果显示买卖点，加载信号数据
    if (showSignals.value) {
      await loadSignals()
    }
  } catch (error) {
    ElMessage.error('加载K线数据失败')
  }
}

// 加载信号数据
const loadSignals = async () => {
  try {
    const data = await signalApi.getSignals({ symbol: symbol.value })
    signals.value = data.items.map((signal: TradingSignal) => ({
      time: signal.triggerTime || signal.createdAt,
      type: signal.type,
      price: signal.triggerPrice || signal.price
    })) as any
  } catch (error) {
    console.error('加载信号数据失败', error)
  }
}

// 加载因子数据
const loadFactors = async () => {
  try {
    ElMessage.warning('因子数据功能开发中')
  } catch (error) {
    ElMessage.error('加载因子数据失败')
  }
}

// 加载技术指标
const loadTechnicalIndicators = async () => {
  try {
    const data = await stockApi.getTechnicalIndicators(symbol.value, ['ma', 'macd', 'kdj', 'rsi', 'boll'])
    technicalIndicators.value = data
  } catch (error) {
    ElMessage.error('加载技术指标失败')
  }
}

// 加载历史信号
const loadHistoricalSignals = async () => {
  try {
    const data = await signalApi.getSignals({
      symbol: symbol.value
    })
    historicalSignals.value = data.items
    signalPagination.total = data.total
  } catch (error) {
    ElMessage.error('加载历史信号失败')
  }
}

// Tab切换
const handleTabChange = (tabName: string) => {
  switch (tabName) {
    case 'kline':
      if (klineData.value.length === 0) {
        loadKlineData()
      }
      break
    case 'factors':
      if (factors.value.length === 0) {
        loadFactors()
      }
      break
    case 'technical':
      if (technicalIndicators.value.length === 0) {
        loadTechnicalIndicators()
      }
      break
    case 'signals':
      if (historicalSignals.value.length === 0) {
        loadHistoricalSignals()
      }
      break
  }
}

// 时间周期切换
const handleTimeframeChange = () => {
  loadKlineData()
}

// 指标切换
const handleIndicatorChange = () => {
  // 指标变化会自动传递给KLineChart组件
}

// 显示买卖点切换
const handleShowSignalsChange = () => {
  if (showSignals.value && signals.value.length === 0) {
    loadSignals()
  }
}

// 计算因子
const handleCalculateFactors = async () => {
  try {
    ElMessage.warning('因子计算功能开发中')
  } catch (error) {
    ElMessage.error('提交因子计算任务失败')
  }
}

// 加入自选
const handleAddToWatchlist = async () => {
  if (!stockInfo.value) return

  // 加载分组列表
  await loadWatchlistGroups()

  // 显示弹窗
  watchlistForm.symbol = stockInfo.value.symbol
  watchlistForm.symbolName = stockInfo.value.name
  watchlistForm.groupId = ''
  watchlistForm.note = ''
  watchlistDialogVisible.value = true
}

// 确认添加到自选股
const handleConfirmAddToWatchlist = async () => {
  watchlistLoading.value = true
  try {
    await stockApi.addToWatchlist(
      watchlistForm.symbol,
      watchlistForm.groupId || undefined,
      watchlistForm.note || undefined
    )
    ElMessage.success('已添加到自选股')
    isInWatchlist.value = true
    watchlistDialogVisible.value = false
  } catch (error) {
    ElMessage.error('添加到自选股失败')
  } finally {
    watchlistLoading.value = false
  }
}

// 从自选股移除
const handleRemoveFromWatchlist = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要从自选股中移除该股票吗？',
      '确认移除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    watchlistLoading.value = true
    await stockApi.removeFromWatchlist(symbol.value)
    ElMessage.success('已从自选股移除')
    isInWatchlist.value = false
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('移除失败')
    }
  } finally {
    watchlistLoading.value = false
  }
}

// 新建分组
const handleCreateGroup = () => {
  groupForm.name = ''
  groupForm.description = ''
  groupDialogVisible.value = true
}

// 确认创建分组
const handleConfirmCreateGroup = async () => {
  if (!groupForm.name.trim()) {
    ElMessage.warning('请输入分组名称')
    return
  }

  groupLoading.value = true
  try {
    const newGroup = await stockApi.createWatchlistGroup(
      groupForm.name,
      groupForm.description || undefined
    )
    ElMessage.success('分组创建成功')
    watchlistGroups.value.push(newGroup)
    groupDialogVisible.value = false
  } catch (error) {
    ElMessage.error('创建分组失败')
  } finally {
    groupLoading.value = false
  }
}

// 信号分页
const handleSignalPageChange = () => {
  loadHistoricalSignals()
}

const handleSignalPageSizeChange = () => {
  signalPagination.page = 1
  loadHistoricalSignals()
}

// 工具函数
const getFactorCategoryType = (category: string) => {
  const typeMap: Record<string, any> = {
    '技术': 'primary',
    '基本面': 'success',
    '情绪': 'warning',
    '其他': 'info'
  }
  return typeMap[category] || 'info'
}

const formatFactorValue = (value: number) => {
  if (Math.abs(value) < 0.01) {
    return value.toExponential(2)
  }
  return value.toFixed(4)
}

const getPercentileColor = (percentile: number) => {
  if (percentile >= 80) return '#67c23a'
  if (percentile >= 60) return '#409eff'
  if (percentile >= 40) return '#e6a23c'
  return '#f56c6c'
}

const getSignalStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    'pending': 'warning',
    'approved': 'primary',
    'rejected': 'danger',
    'executed': 'success'
  }
  return typeMap[status] || 'info'
}

const getSignalStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'pending': '待审批',
    'approved': '已批准',
    'rejected': '已拒绝',
    'executed': '已执行'
  }
  return textMap[status] || status
}

// 监听路由变化
watch(() => route.params.symbol, (newSymbol) => {
  if (newSymbol) {
    symbol.value = newSymbol as string
    // 重新加载数据
    loadStockInfo()
    loadKlineData()
  }
})

// 组件挂载
onMounted(() => {
  loadStockInfo()
  loadKlineData()
})

// 组件卸载
onUnmounted(() => {
  unsubscribe(symbol.value)
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'StockDetail'
})
</script>

<style scoped lang="scss">
.stock-detail {
  .stock-header {
    :deep(.el-card__body) {
      padding: 20px;
    }
  }

  .stock-tabs {
    :deep(.el-card__body) {
      padding: 0;
    }

    :deep(.el-tabs__header) {
      margin: 0;
      padding: 0 20px;
      background: #f5f7fa;
    }

    :deep(.el-tabs__content) {
      padding: 20px;
    }
  }

  .chart-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #1e222d;
    border-radius: 8px 8px 0 0;
    margin-bottom: 0;

    .toolbar-section {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .toolbar-label {
      font-size: 12px;
      color: #9ca3af;
      font-weight: 500;
    }

    :deep(.el-radio-button__inner) {
      padding: 6px 12px;
      font-size: 12px;
    }

    :deep(.el-checkbox) {
      color: #d1d5db;

      .el-checkbox__label {
        font-size: 12px;
      }
    }
  }

  .kline-container {
    background: #131722;
    border-radius: 8px;
    overflow: hidden;
  }

  .factors-container,
  .technical-container,
  .signals-container {
    min-height: 400px;
  }

  .indicator-card {
    :deep(.el-card__header) {
      padding: 12px 16px;
      background: #f5f7fa;
    }

    :deep(.el-card__body) {
      padding: 16px;
    }
  }
}
</style>
