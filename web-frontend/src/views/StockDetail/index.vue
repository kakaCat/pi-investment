<template>
  <div class="stock-detail">
    <div class="text-sm text-slate-400 mb-4">
      <router-link :to="{ name: 'StockList' }" class="hover:text-blue-500 cursor-pointer no-underline text-slate-400">股票列表</router-link>
      <span class="mx-2">/</span>
      <span class="text-slate-700 font-medium">{{ displayStockCode }} {{ stockInfo?.name || symbol }}</span>
    </div>

    <div class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 mb-4" v-if="stockInfo">
      <div class="stock-header-row">
        <div class="min-w-0">
          <div class="flex items-center gap-3 mb-2">
            <h2 class="text-2xl font-bold text-slate-900">{{ displayStockCode }}</h2>
            <span class="text-lg text-slate-500">{{ stockInfo.name }}</span>
            <span v-if="stockInfo.market" class="text-xs bg-slate-100 px-2 py-0.5 rounded">{{ stockInfo.market }}</span>
            <span class="text-xs bg-slate-100 px-2 py-0.5 rounded">{{ stockInfo.industry || stockInfo.sector || '未分类' }}</span>
          </div>
          <div class="flex items-center gap-4">
            <span class="text-3xl font-bold text-slate-900">¥{{ formatPrice(stockInfo.price || stockInfo.currentPrice) }}</span>
            <span :class="['text-lg font-semibold', stockInfo.changePercent >= 0 ? 'stat-up' : 'stat-down']">
              {{ signedPriceChange }}
            </span>
          </div>
        </div>
        <div class="flex items-center gap-3 stock-header-actions">
          <button
            class="px-4 py-2 border border-amber-200 bg-amber-50 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-100"
            @click="handleRepairData"
            :disabled="repairLoading"
          >
            {{ repairLoading ? '修复中...' : '修复数据' }}
          </button>
          <button class="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600" @click="handleCalculateFactors">计算因子</button>
          <button
            v-if="!isInWatchlist"
            class="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
            @click="handleAddToWatchlist"
            :disabled="watchlistLoading"
          >
            加入自选
          </button>
          <button
            v-else
            class="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-700 hover:bg-slate-50"
            @click="handleRemoveFromWatchlist"
            :disabled="watchlistLoading"
          >
            <el-icon><StarFilled /></el-icon>
            已自选
          </button>
        </div>
      </div>
    </div>

    <div class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div class="border-b border-slate-200">
        <div class="flex stock-detail-tabs">
          <button
            v-for="tab in detailTabs"
            :key="tab.name"
            :class="[
              'px-5 py-3 text-sm transition-colors',
              activeTab === tab.name
                ? 'font-medium text-blue-600 border-b-2 border-blue-500 bg-blue-50/50'
                : 'text-slate-500 hover:text-slate-700'
            ]"
            @click="setActiveTab(tab.name)"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <div v-show="activeTab === 'kline'" class="p-0">
        <div class="bg-slate-900 px-4 py-2 flex items-center justify-between border-b border-slate-700" :class="'chart-toolbar'">
          <div class="flex items-center gap-1 chart-toolbar-group">
            <span class="text-xs text-slate-400 mr-2">TIMEFRAME</span>
            <button
              v-for="option in timeframeOptions"
              :key="option.value"
              :class="[
                'px-2 py-1 text-xs rounded',
                timeframe === option.value ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800'
              ]"
              @click="setTimeframe(option.value)"
            >
              {{ option.label }}
            </button>
          </div>

          <div class="flex items-center gap-1 chart-toolbar-group">
            <span class="text-xs text-slate-400 mr-2">INDICATOR</span>
            <button
              v-for="option in indicatorOptions"
              :key="option.value"
              :class="[
                'px-2 py-1 text-xs rounded',
                indicators.includes(option.value) ? 'bg-slate-700 text-white' : 'text-slate-300 hover:bg-slate-800'
              ]"
              @click="toggleIndicator(option.value)"
            >
              {{ option.label }}
            </button>
            <span class="mx-2 text-slate-600 toolbar-divider">|</span>
            <button
              :class="[
                'px-2 py-1 text-xs rounded',
                showSignals ? 'text-green-400 bg-green-900/30' : 'text-slate-300 hover:bg-slate-800'
              ]"
              @click="toggleSignals"
            >
              显示买卖点
            </button>
          </div>
        </div>

        <div class="bg-slate-900 px-4 py-2 flex items-center gap-6 text-xs border-b border-slate-700 stock-price-bar">
          <span class="text-slate-400">Time: <span class="text-slate-200">{{ latestKline?.date || '--' }}</span></span>
          <span class="text-slate-400">Open: <span class="text-slate-200">{{ latestKline ? formatPrice(latestKline.open) : '--' }}</span></span>
          <span class="text-slate-400">High: <span class="text-red-400">{{ latestKline ? formatPrice(latestKline.high) : '--' }}</span></span>
          <span class="text-slate-400">Low: <span class="text-green-400">{{ latestKline ? formatPrice(latestKline.low) : '--' }}</span></span>
          <span class="text-slate-400">Close: <span class="text-slate-200 font-semibold">{{ latestKline ? formatPrice(latestKline.close) : '--' }}</span></span>
          <span class="text-slate-400">{{ latestKlineTurnoverLabel }}: <span class="text-slate-200">{{ latestKlineTurnoverValue }}</span></span>
          <span class="ml-auto text-slate-500 stock-price-note">{{ indicatorSummary }}</span>
        </div>

        <div class="professional-chart-area" :class="['relative', 'flex']">
          <div class="w-12 bg-[#1e222d] border-r border-[#2a2e39] flex flex-col items-center py-3 gap-3 stock-chart-tools">
            <button class="w-8 h-8 flex items-center justify-center text-slate-400 hover:bg-slate-700 rounded" title="十字光标">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M8 0v16M0 8h16" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
            <button class="w-8 h-8 flex items-center justify-center text-slate-400 hover:bg-slate-700 rounded" title="趋势线">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 14L14 2" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
            <button class="w-8 h-8 flex items-center justify-center text-slate-400 hover:bg-slate-700 rounded" title="水平线">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 8h12" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
            <button class="w-8 h-8 flex items-center justify-center text-slate-400 hover:bg-slate-700 rounded" title="矩形">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><rect x="3" y="4" width="10" height="8" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
          </div>
          <div class="flex-1 min-w-0">
            <KLineChart
              v-if="klineData.length > 0"
              :data="klineData as any"
              :signals="showSignals ? signals : []"
              height="600px"
              class="stock-kline-chart"
            />
            <div v-else class="chart-empty-state">
              暂无K线数据
            </div>
          </div>
        </div>
      </div>

      <div v-show="activeTab === 'factors'" class="p-5 factors-container">
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

      <div v-show="activeTab === 'technical'" class="p-5 technical-container">
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

      <div v-show="activeTab === 'signals'" class="p-5 signals-container">
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

      <div v-show="activeTab === 'chan'" class="chan-container">
        <!-- 顶部信息栏 -->
        <div class="bg-slate-900 px-4 py-3 flex items-center justify-between border-b border-slate-700">
          <div class="flex items-center gap-4">
            <span class="text-xs text-slate-400">走势类型：</span>
            <span v-if="chanLoading" class="text-sm text-slate-400">分析中...</span>
            <span v-else :class="['text-sm font-semibold px-3 py-1 rounded', chanTrendClass]">
              {{ chanResult?.trend_type || '--' }}
            </span>
          </div>
          <div class="flex items-center gap-6 text-xs text-slate-400">
            <span>笔: <span class="text-slate-200 font-medium">{{ chanResult?.bis?.length || 0 }}</span></span>
            <span>线段: <span class="text-slate-200 font-medium">{{ chanResult?.segments?.length || 0 }}</span></span>
            <span>中枢: <span class="text-slate-200 font-medium">{{ chanResult?.zhongshus?.length || 0 }}</span></span>
            <span>买卖点: <span class="text-slate-200 font-medium">{{ chanResult?.buypoints?.length || 0 }}</span></span>
          </div>
        </div>

        <!-- K线图 + 缠论标注 -->
        <div class="professional-chart-area relative flex">
          <div class="flex-1 min-w-0">
            <div v-if="chanLoading" class="chart-empty-state">
              <el-icon class="is-loading" :size="32"><Loading /></el-icon>
              <div class="mt-2">正在分析中...</div>
            </div>
            <KLineChart
              v-else-if="klineData.length > 0"
              :data="klineData"
              :signals="chanBuypoints"
              height="600px"
              class="stock-kline-chart"
            />
            <div v-else class="chart-empty-state">
              暂无K线数据
            </div>
          </div>
        </div>

        <!-- 买卖点列表 -->
        <div class="p-5 bg-slate-50">
          <div class="mb-3 text-sm font-semibold text-slate-700">买卖点信号</div>
          <el-table :data="chanResult?.buypoints || []" stripe>
            <el-table-column prop="type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag :type="row.type.includes('买') ? 'success' : 'danger'" size="small">
                  {{ row.type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="date" label="日期" width="120" />
            <el-table-column prop="price" label="价格" width="100">
              <template #default="{ row }">
                ¥{{ formatPrice(row.price) }}
              </template>
            </el-table-column>
            <el-table-column prop="confidence" label="置信度" width="120">
              <template #default="{ row }">
                <el-progress :percentage="row.confidence * 100" :stroke-width="8" />
              </template>
            </el-table-column>
            <el-table-column prop="position_ratio" label="建议仓位" width="100">
              <template #default="{ row }">
                {{ (row.position_ratio * 100).toFixed(0) }}%
              </template>
            </el-table-column>
            <el-table-column prop="reason" label="原因" show-overflow-tooltip />
          </el-table>

          <div v-if="!chanResult?.buypoints?.length && !chanLoading" class="text-center py-8 text-slate-400">
            暂无买卖点信号
          </div>
        </div>
      </div>
    </div>

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
import { computed, ref, reactive, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { StarFilled, Loading } from '@element-plus/icons-vue'
import KLineChart from '@/components/charts/KLineChart/index.vue'
import { stockApi, signalApi } from '@/services/api'
import { useMarketWebSocket } from '@/composables/useWebSocket'
import { formatPrice, formatPercent, formatDateTime, formatStockCode, formatVolume } from '@/utils/format'
import type { StockInfo, TradingSignal, WatchlistGroup } from '@/types/models'

const route = useRoute()

// 股票信息
const stockInfo = ref<StockInfo | null>(null)
const symbol = ref<string>(route.params.symbol as string)

// Tab状态
const activeTab = ref('kline')
const detailTabs = [
  { label: 'K线图', name: 'kline' },
  { label: '因子一览', name: 'factors' },
  { label: '技术指标', name: 'technical' },
  { label: '历史信号', name: 'signals' },
  { label: '缠论分析', name: 'chan' }
]

// K线图相关
const timeframe = ref('1d')
const indicators = ref<string[]>(['MA', 'VOL'])
const showSignals = ref(true)
const klineData = ref<any[]>([])
const signals = ref<TradingSignal[]>([])
const timeframeOptions = [
  { label: '1m', value: '1m' },
  { label: '5m', value: '5m' },
  { label: '15m', value: '15m' },
  { label: '1H', value: '1h' },
  { label: '4H', value: '4h' },
  { label: '1D', value: '1d' },
  { label: '1W', value: '1w' }
]
const indicatorOptions = [
  { label: 'SMA', value: 'MA' },
  { label: 'EMA', value: 'EMA' },
  { label: 'RSI', value: 'RSI' },
  { label: 'MACD', value: 'MACD' },
  { label: 'BB', value: 'BOLL' },
  { label: 'ATR', value: 'ATR' }
]

// 因子数据
const factors = ref<any[]>([])
const repairLoading = ref(false)

// 技术指标数据
const technicalIndicators = ref<any[]>([])

// 历史信号
const historicalSignals = ref<TradingSignal[]>([])
const signalPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 缠论分析相关
const chanResult = ref<any>(null)
const chanLoading = ref(false)

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
const { subscribe, unsubscribe, on } = useMarketWebSocket({ autoConnect: false })

const displayStockCode = computed(() => {
  const code = stockInfo.value?.symbol || symbol.value
  return formatStockCode(code)
})

const signedPriceChange = computed(() => {
  if (!stockInfo.value) return '--'
  const change = stockInfo.value.change || 0
  const percent = stockInfo.value.changePercent || 0
  const sign = change >= 0 ? '+' : ''
  return `${sign}${formatPrice(change)} (${formatPercent(percent)})`
})

const latestKline = computed(() => klineData.value[klineData.value.length - 1])

const latestKlineTurnoverLabel = computed(() => {
  if (!latestKline.value) return 'Volume'
  return latestKline.value.volume > 0 ? 'Volume' : 'Amount'
})

const latestKlineTurnoverValue = computed(() => {
  if (!latestKline.value) return '--'
  return latestKline.value.volume > 0
    ? formatVolume(latestKline.value.volume)
    : formatVolume(latestKline.value.amount)
})

const indicatorSummary = computed(() => {
  if (!indicators.value.length) return '未选择技术指标'
  return `${indicators.value.join('/')} active`
})

// 缠论相关计算属性
const chanBuypoints = computed(() => {
  if (!chanResult.value?.buypoints) return []
  return chanResult.value.buypoints.map((bp: any) => ({
    type: bp.type.includes('买') ? 'buy' : 'sell',
    price: bp.price,
    createdAt: bp.date,
    time: bp.date,
    confidence: bp.confidence
  }))
})

const chanTrendClass = computed(() => {
  const trend = chanResult.value?.trend_type
  if (trend === '上涨') return 'bg-green-500/20 text-green-400'
  if (trend === '下跌') return 'bg-red-500/20 text-red-400'
  return 'bg-slate-500/20 text-slate-400'
})

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
    console.log('[StockDetail] loadKlineData called, symbol:', symbol.value)
    const data = await stockApi.getKLineData({
      symbol: symbol.value,
      timeFrame: timeframe.value
    })
    console.log('[StockDetail] klineData received:', data?.length, 'items, first:', data?.[0])
    klineData.value = data

    // 如果显示买卖点，加载信号数据
    if (showSignals.value) {
      await loadSignals()
    }
  } catch (error) {
    console.error('[StockDetail] loadKlineData error:', error)
    ElMessage.error('加载K线数据失败')
  }
}

// 加载信号数据
const loadSignals = async () => {
  try {
    const data = await signalApi.getSignals({ symbol: symbol.value })
    signals.value = data.items.map((signal: TradingSignal) => ({
      time: signal.triggerTime || signal.createdAt,
      createdAt: signal.triggerTime || signal.createdAt || '',
      type: signal.type,
      price: signal.triggerPrice || signal.price,
      confidence: (signal as any).confidence ?? 0
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

// 加载缠论分析
const loadChanAnalysis = async () => {
  chanLoading.value = true
  try {
    const response = await fetch('http://localhost:5001/api/chan/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        symbol: symbol.value,
        startDate: new Date(Date.now() - 365 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        endDate: new Date().toISOString().split('T')[0]
      })
    })

    if (!response.ok) {
      throw new Error('API请求失败')
    }

    chanResult.value = await response.json()
  } catch (error) {
    console.error('加载缠论分析失败:', error)
    ElMessage.error('加载缠论分析失败')
  } finally {
    chanLoading.value = false
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
    case 'chan':
      if (!chanResult.value) {
        loadChanAnalysis()
      }
      break
  }
}

const setActiveTab = (tabName: string) => {
  activeTab.value = tabName
  handleTabChange(tabName)
}

const setTimeframe = (value: string) => {
  if (timeframe.value === value) return
  timeframe.value = value
  handleTimeframeChange()
}

const toggleIndicator = (value: string) => {
  if (indicators.value.includes(value)) {
    indicators.value = indicators.value.filter(item => item !== value)
  } else {
    indicators.value = [...indicators.value, value]
  }
  handleIndicatorChange()
}

const toggleSignals = () => {
  showSignals.value = !showSignals.value
  handleShowSignalsChange()
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

// 修复当前股票数据
const handleRepairData = async () => {
  if (repairLoading.value) return

  repairLoading.value = true
  try {
    const result = await stockApi.repairStockData(symbol.value)
    const runId = result?.run_id || result?.runId
    ElMessage.success(runId ? `数据修复任务已提交：${runId}` : '数据修复任务已提交')
    await Promise.all([
      loadStockInfo(),
      loadKlineData()
    ])
  } catch (error) {
    console.error('[StockDetail] repair data failed:', error)
    ElMessage.error('提交数据修复任务失败')
  } finally {
    repairLoading.value = false
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
  max-width: 100%;

  .stock-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
  }

  .stock-header-actions button:disabled {
    cursor: wait;
    opacity: 0.72;
  }

  .stat-up {
    color: #26a69a;
  }

  .stat-down {
    color: #ef5350;
  }

  .chart-toolbar {
    min-height: 41px;
    overflow-x: auto;

    button {
      line-height: 1.25;
      white-space: nowrap;
    }
  }

  .chart-toolbar-group {
    flex-wrap: nowrap;
  }

  .stock-price-bar {
    min-height: 37px;
    overflow-x: auto;
    white-space: nowrap;
  }

  .stock-price-note {
    min-width: max-content;
  }

  .professional-chart-area {
    height: 600px;
    background: #131722;
  }

  .stock-kline-chart {
    background: #131722;
  }

  .chart-empty-state {
    height: 600px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #787b86;
    background: #131722;
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

@media (max-width: 900px) {
  .stock-detail {
    .stock-header-row {
      align-items: flex-start;
      flex-direction: column;
    }

    .stock-header-actions {
      width: 100%;
      flex-wrap: wrap;
    }

    .stock-detail-tabs {
      overflow-x: auto;
    }

    .chart-toolbar {
      align-items: flex-start;
      flex-direction: column;
      gap: 8px;
    }

    .stock-price-bar {
      gap: 16px;
    }
  }
}

@media (max-width: 640px) {
  .stock-detail {
    .professional-chart-area {
      height: 520px;
    }

    .stock-chart-tools {
      display: none;
    }

    .chart-empty-state {
      height: 520px;
    }

    :deep(.stock-kline-chart) {
      height: 520px !important;
    }
  }
}
</style>
