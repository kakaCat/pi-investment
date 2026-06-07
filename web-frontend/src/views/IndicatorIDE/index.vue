<template>
  <div class="indicator-ide">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-2xl font-bold text-slate-800 mb-2">📐 指标IDE</h2>
      <p class="text-sm text-slate-500">自定义技术指标编辑器 - 创建、测试、回测您的量化指标</p>
    </div>

    <!-- 编辑工作台 -->
    <div class="grid grid-cols-12 gap-4 workbench-grid">
      <!-- 左侧：指标库 -->
      <div class="col-span-3">
        <el-card class="indicator-library">
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <el-icon><Collection /></el-icon>
                <span class="font-bold">指标库</span>
              </div>
              <el-button
                size="small"
                circle
                :loading="loadingIndicators"
                data-test="refresh-indicators"
                title="刷新指标库"
                @click="refreshIndicators"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
            </div>
          </template>

          <!-- 搜索框 -->
          <el-input
            v-model="searchKeyword"
            placeholder="搜索指标..."
            :prefix-icon="Search"
            clearable
            class="mb-4"
          />

          <!-- 我的指标 -->
          <div class="mb-4">
            <div class="text-xs text-slate-500 uppercase font-medium mb-2">
              我的指标 ({{ myIndicators.length }})
            </div>
            <div class="space-y-1">
              <div
                v-for="indicator in filteredMyIndicators"
                :key="indicator.id"
                class="indicator-item"
                :class="{ active: selectedIndicator?.id === indicator.id }"
                @click="selectIndicator(indicator)"
              >
                <span class="text-sm">📊</span>
                <span class="text-sm font-medium">{{ indicator.name }}</span>
              </div>
            </div>
          </div>

          <!-- 系统指标 -->
          <div class="mb-4">
            <div class="text-xs text-slate-500 uppercase font-medium mb-2">
              系统指标 ({{ systemIndicators.length }})
            </div>
            <div class="space-y-1">
              <div
                v-for="indicator in filteredSystemIndicators"
                :key="indicator.id"
                class="indicator-item"
                :class="{ active: selectedIndicator?.id === indicator.id }"
                @click="selectIndicator(indicator)"
              >
                <span class="text-sm">📈</span>
                <span class="text-sm">{{ indicator.name }}</span>
              </div>
            </div>
          </div>

          <el-button type="primary" class="w-full" @click="createNewIndicator">
            <el-icon><Plus /></el-icon>
            新建指标
          </el-button>
        </el-card>
      </div>

      <!-- 中间：代码编辑器 -->
      <div class="col-span-6">
        <el-card class="code-editor-card">
          <!-- 指标名称 -->
          <el-input
            v-model="currentIndicatorName"
            placeholder="指标名称"
            class="mb-4"
            size="large"
          />

          <!-- 代码编辑器 -->
          <div class="mb-4">
            <div class="text-xs text-slate-500 uppercase font-medium mb-2">
              指标公式编辑器
            </div>
            <div class="code-editor">
              <textarea
                v-model="currentIndicatorCode"
                class="code-textarea"
                placeholder="// 在此编写指标代码..."
                spellcheck="false"
              />
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="flex gap-2">
            <el-button
              type="success"
              :loading="running"
              @click="runIndicator"
            >
              <el-icon><VideoPlay /></el-icon>
              运行
            </el-button>
            <el-button
              type="primary"
              :loading="saving"
              @click="saveIndicator"
            >
              <el-icon><Document /></el-icon>
              保存
            </el-button>
            <el-button
              type="warning"
              :disabled="!selectedIndicator || selectedIndicator.isPublic"
              @click="publishIndicator"
            >
              <el-icon><Upload /></el-icon>
              发布到社区
            </el-button>
            <el-button @click="copyCode">
              <el-icon><CopyDocument /></el-icon>
              复制代码
            </el-button>
            <el-button
              type="danger"
              :disabled="!selectedIndicator || selectedIndicator.strategyType !== 'custom'"
              data-test="delete-indicator"
              @click="deleteSelectedIndicator"
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </div>
        </el-card>
      </div>

      <!-- 右侧：策略记事本 -->
      <div class="col-span-3">
        <el-card class="notebook-card">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <el-icon><Notebook /></el-icon>
                <span class="font-bold">策略记事本</span>
              </div>
              <el-button
                size="small"
                type="primary"
                :loading="savingNotebook"
                :disabled="!selectedIndicator"
                @click="saveStrategyNotebook"
              >
                保存笔记
              </el-button>
            </div>
          </template>

          <div class="notebook-fields">
            <label>
              <span>好处 / 适用场景</span>
              <el-input
                v-model="strategyNotebook.pros"
                type="textarea"
                :rows="4"
                placeholder="例如：趋势明确时胜率高、逻辑容易解释..."
              />
            </label>
            <label>
              <span>坏处 / 风险</span>
              <el-input
                v-model="strategyNotebook.cons"
                type="textarea"
                :rows="4"
                placeholder="例如：震荡市假信号多、出场慢..."
              />
            </label>
            <label>
              <span>观察记录</span>
              <el-input
                v-model="strategyNotebook.observations"
                type="textarea"
                :rows="4"
                placeholder="记录回测、实盘、某只股票上的表现..."
              />
            </label>
            <label>
              <span>优化点</span>
              <el-input
                v-model="strategyNotebook.nextSteps"
                type="textarea"
                :rows="3"
                placeholder="例如：加入成交量过滤、比较 MA 参数..."
              />
            </label>
          </div>
        </el-card>
      </div>
    </div>

    <!-- 下方：预览和回测 -->
    <div class="grid grid-cols-12 gap-4 mt-4 lower-grid">
      <div class="col-span-12">
        <el-card class="preview-card mb-4">
          <template #header>
            <div class="preview-header">
              <div class="flex items-center gap-2">
                <el-icon><TrendCharts /></el-icon>
                <span class="font-bold">实时预览</span>
              </div>

              <div class="preview-actions">
                <el-select
                  v-model="selectedStrategy"
                  placeholder="选择策略"
                  class="strategy-select"
                  :loading="loadingStrategies"
                  data-test="indicator-strategy-select"
                  @change="handleStrategyChange"
                >
                  <el-option
                    v-for="option in strategyOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-select
                  v-model="backtestForm.period"
                  placeholder="频率"
                  class="frequency-select"
                  data-test="indicator-frequency-select"
                  @change="handleFrequencyChange"
                >
                  <el-option
                    v-for="option in frequencyOptions"
                    :key="option.value"
                    :label="option.label"
                    :value="option.value"
                  />
                </el-select>
                <el-select
                  v-model="selectedSymbols"
                  multiple
                  filterable
                  remote
                  reserve-keyword
                  collapse-tags
                  collapse-tags-tooltip
                  placeholder="选择多个测试股票..."
                  :remote-method="handleStockSearch"
                  :loading="searchLoading"
                  style="width: 360px"
                  @change="handleStockChange"
                >
                  <el-option-group v-if="searchResults.length > 0" label="搜索结果">
                    <el-option
                      v-for="stock in searchResults"
                      :key="stock.symbol"
                      :label="`${stock.symbol} - ${stock.name}`"
                      :value="stock.symbol"
                    />
                  </el-option-group>

                  <el-option-group v-if="positionStocks.length > 0" label="我的持仓">
                    <el-option
                      v-for="stock in positionStocks"
                      :key="stock.symbol"
                      :label="`${stock.symbol} - ${stock.name}`"
                      :value="stock.symbol"
                    />
                  </el-option-group>

                  <el-option-group v-if="watchlistStocks.length > 0" label="我的自选">
                    <el-option
                      v-for="stock in watchlistStocks"
                      :key="stock.symbol"
                      :label="`${stock.symbol} - ${stock.name}`"
                      :value="stock.symbol"
                    />
                  </el-option-group>
                </el-select>
                <el-button type="success" :loading="running" @click="runIndicator">
                  <el-icon><VideoPlay /></el-icon>
                  运行所选
                </el-button>
              </div>
            </div>
          </template>

          <div v-if="previewResults.length > 0" class="preview-grid">
            <div
              v-for="result in previewResults"
              :key="result.symbol"
              class="preview-result-card"
            >
              <div class="preview-click-area" @click="openChartDialog(result)">
                <div class="preview-result-header">
                  <div>
                    <div class="preview-symbol">{{ result.symbol }} {{ result.symbolName }}</div>
                    <div class="preview-date">{{ formatChartDate(result.date) }}</div>
                  </div>
                  <span
                    class="signal-badge"
                    :class="result.signal ? `signal-${result.signal}` : 'signal-hold'"
                  >
                    {{ getSignalLabel(result.signal) }}
                  </span>
                </div>

                <PreviewChart
                  v-if="result.klineData.length > 0"
                  :kline-data="result.klineData"
                  :indicator-series="result.indicatorSeries"
                  :signal-series="result.signalSeries"
                  :latest-signal="result.signal"
                  compact
                />
                <div v-else class="empty-chart">暂无 K 线数据</div>
              </div>

              <div class="preview-result-footer">
                <div>
                  <span>当前值</span>
                  <strong>{{ result.currentValue }}</strong>
                </div>
              </div>

              <div v-if="result.backtestResult" class="preview-backtest-metrics">
                <div>
                  <span>胜率</span>
                  <strong class="metric-positive">{{ (result.backtestResult.winRate * 100).toFixed(1) }}%</strong>
                </div>
                <div>
                  <span>收益率</span>
                  <strong :class="result.backtestResult.totalReturn >= 0 ? 'metric-positive' : 'metric-negative'">
                    {{ result.backtestResult.totalReturn >= 0 ? '+' : '' }}{{ (result.backtestResult.totalReturn * 100).toFixed(1) }}%
                  </strong>
                </div>
                <div>
                  <span>交易</span>
                  <strong>{{ result.backtestResult.trades }}</strong>
                </div>
                <div>
                  <span>夏普</span>
                  <strong>{{ result.backtestResult.sharpeRatio.toFixed(2) }}</strong>
                </div>
              </div>
            </div>
          </div>
          <div v-if="previewResults.length > 0" class="preview-batch-actions">
            <div class="preview-backtest-range">
              <span>回测时间</span>
              <el-date-picker
                v-model="backtestForm.startDate"
                type="date"
                placeholder="开始日期"
                value-format="YYYY-MM-DD"
                data-test="preview-backtest-start-date"
              />
              <span>至</span>
              <el-date-picker
                v-model="backtestForm.endDate"
                type="date"
                placeholder="结束日期"
                value-format="YYYY-MM-DD"
                data-test="preview-backtest-end-date"
              />
              <div class="preview-backtest-presets">
                <el-button
                  size="small"
                  data-test="preview-backtest-range-90d"
                  @click="applyBacktestRange('ninetyDays')"
                >
                  90天
                </el-button>
                <el-button
                  size="small"
                  data-test="preview-backtest-range-half-year"
                  @click="applyBacktestRange('halfYear')"
                >
                  半年
                </el-button>
                <el-button
                  size="small"
                  data-test="preview-backtest-range-one-year"
                  @click="applyBacktestRange('oneYear')"
                >
                  一年
                </el-button>
              </div>
            </div>
            <el-button
              type="warning"
              :loading="backtesting"
              @click="runAllPreviewBacktests"
            >
              <el-icon><Refresh /></el-icon>
              完整回测全部股票
            </el-button>
          </div>
          <el-empty v-else description="选择股票并运行后，在这里查看多股票独立图表" />
        </el-card>
      </div>
    </div>

    <!-- 保存指标弹窗 -->
    <el-dialog
      v-model="saveDialogVisible"
      title="保存指标"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="saveForm" label-width="100px">
        <el-form-item label="指标名称" required>
          <el-input v-model="saveForm.name" placeholder="请输入指标名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="saveForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入指标描述"
          />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="saveForm.category" placeholder="请选择分类" style="width: 100%">
            <el-option label="趋势指标" value="trend" />
            <el-option label="动量指标" value="momentum" />
            <el-option label="波动率指标" value="volatility" />
            <el-option label="成交量指标" value="volume" />
            <el-option label="自定义指标" value="custom" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitSaveIndicator">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 回测弹窗 -->
    <el-dialog
      v-model="backtestDialogVisible"
      title="运行回测"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="backtestForm" label-width="100px">
        <el-form-item label="股票代码" required>
          <el-input v-model="backtestForm.symbol" placeholder="请输入股票代码，如：600519" />
        </el-form-item>
        <el-form-item label="回测时间" required>
          <el-date-picker
            v-model="backtestForm.startDate"
            type="date"
            placeholder="开始日期"
            style="width: 48%"
            value-format="YYYY-MM-DD"
          />
          <span style="margin: 0 2%">至</span>
          <el-date-picker
            v-model="backtestForm.endDate"
            type="date"
            placeholder="结束日期"
            style="width: 48%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="K线频率">
          <el-select
            v-model="backtestForm.period"
            placeholder="请选择K线频率"
            style="width: 100%"
            data-test="backtest-frequency-select"
            @change="handleFrequencyChange"
          >
            <el-option
              v-for="option in frequencyOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初始资金">
          <el-input-number
            v-model="backtestForm.initialCapital"
            :min="10000"
            :step="10000"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="backtestDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="backtesting" @click="submitBacktest">
          开始回测
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="chartDialogVisible"
      :title="expandedPreview ? `${expandedPreview.symbol} ${expandedPreview.symbolName}` : '图表详情'"
      width="86vw"
      class="chart-dialog"
      destroy-on-close
    >
      <div v-if="expandedPreview" class="expanded-chart-wrap">
        <PreviewChart
          :kline-data="expandedPreview.klineData"
          :indicator-series="expandedPreview.indicatorSeries"
          :signal-series="expandedPreview.signalSeries"
          :latest-signal="expandedPreview.signal"
        />
        <div class="expanded-chart-meta">
          <span>{{ formatChartDate(expandedPreview.date) }}</span>
          <span>当前值：{{ expandedPreview.currentValue }}</span>
          <span>{{ getSignalLabel(expandedPreview.signal) }}</span>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  Collection,
  Plus,
  VideoPlay,
  Document,
  Upload,
  CopyDocument,
  TrendCharts,
  Refresh,
  Delete,
  Notebook
} from '@element-plus/icons-vue'
import { debounce } from 'lodash-es'
import PreviewChart from './PreviewChart.vue'
import { indicatorApi } from '@/services/api/indicator'
import { analysisApi } from '@/services/api/analysis'
import { stockApi } from '@/services/api/stock'
import { strategyApi } from '@/services/api/strategy'
import type { Indicator, IndicatorBacktest } from '@/types'
import type {
  IndicatorInfo,
  IndicatorRunResult,
  KlineData,
  StrategyNotebook
} from '@/types/indicator'

interface PreviewResult {
  symbol: string
  symbolName: string
  currentValue: number
  date: string
  signal?: 'buy' | 'sell'
  signalTriggered: boolean
  klineData: KlineData[]
  indicatorSeries: Record<string, (number | null)[]>
  signalSeries?: {
    buy?: (boolean | number | null)[]
    sell?: (boolean | number | null)[]
  }
  backtestLoading?: boolean
  backtestResult?: IndicatorBacktest['result']
}

type KlinePeriod = 'daily' | '1min' | '5min' | '15min' | '30min' | '60min'

// 搜索关键词
const searchKeyword = ref('')

// 指标列表
const myIndicators = ref<IndicatorInfo[]>([])
const systemIndicators = ref<IndicatorInfo[]>([])

// 当前选中的指标
const selectedIndicator = ref<IndicatorInfo | null>(null)

// 当前编辑的指标
const currentIndicatorName = ref('')
const currentIndicatorCode = ref('')

// 当前测试股票
const currentSymbol = ref('600519')
const currentSymbolName = ref('贵州茅台')
const selectedSymbols = ref<string[]>(['600519'])
const currentSymbolNameBySymbol = reactive<Record<string, string>>({
  '600519': '贵州茅台'
})

// 股票选择器相关状态
const positionStocks = ref<Array<{ symbol: string; name: string }>>([])
const watchlistStocks = ref<Array<{ symbol: string; name: string }>>([])
const searchResults = ref<Array<{ symbol: string; name: string; market?: string }>>([])
const searchLoading = ref(false)

// 加载状态
const running = ref(false)
const saving = ref(false)
const backtesting = ref(false)
const savingNotebook = ref(false)
const loadingIndicators = ref(false)
const loadingStrategies = ref(false)

// 保存指标弹窗
const saveDialogVisible = ref(false)
const saveForm = reactive({
  name: '',
  description: '',
  category: 'custom' as 'trend' | 'momentum' | 'volatility' | 'volume' | 'custom'
})

// 回测弹窗
const backtestDialogVisible = ref(false)
const backtestForm = reactive({
  symbol: '600519',
  startDate: '',
  endDate: '',
  period: 'daily' as KlinePeriod,
  initialCapital: 100000,
  fastPeriod: 5,
  slowPeriod: 20,
  rsiPeriod: 14,
  peHeavyBuy: 16.0,
  peBatchBuy: 17.0,
  peReduce: 19.5,
  peLiquidate: 20.5,
  epsStart: 1.20,
  epsEnd: 1.48,
  stopLossPct: 8,
  takeProfitPct: 25,
  dividendYield: 3.5,
  pbHeavyBuy: 2.0,
  pbBatchBuy: 2.5,
  pbReduce: 4.5,
  pbLiquidate: 5.5,
  roeMean: 0.35
})

const fallbackStrategies = [
  { label: 'MA 双均线', value: 'ma_cross' },
  { label: 'RSI 反转', value: 'rsi_reversal' },
  { label: 'MACD 金叉', value: 'macd_golden' },
  { label: '布林带突破', value: 'boll_breakout' },
  { label: 'KDJ 超买超卖', value: 'kdj_overbought' },
  { label: 'GridTradingStrategy', value: 'grid_trading' },
  { label: 'PE均值回归', value: 'pe_mean_reversion' },
  { label: 'PB均值回归', value: 'pb_mean_reversion' }
]
const selectedStrategy = ref(fallbackStrategies[0].value)
const strategyOptions = ref([...fallbackStrategies])

const frequencyOptions: Array<{ label: string; value: KlinePeriod }> = [
  { label: '日线', value: 'daily' },
  { label: '1分钟', value: '1min' },
  { label: '5分钟', value: '5min' },
  { label: '15分钟', value: '15min' },
  { label: '30分钟', value: '30min' },
  { label: '60分钟', value: '60min' }
]

// 策略笔记
const strategyNotebook = reactive<StrategyNotebook>({
  pros: '',
  cons: '',
  observations: '',
  nextSteps: ''
})

// 预览数据
const previewData = ref<PreviewResult | null>(null)
const previewResults = ref<PreviewResult[]>([])
const chartDialogVisible = ref(false)
const expandedPreview = ref<PreviewResult | null>(null)
const PREVIEW_KLINE_LIMIT = 260

// 回测结果
const backtestResult = ref<IndicatorBacktest['result'] | null>(null)

// 过滤后的指标列表
const filteredMyIndicators = computed(() => {
  if (!searchKeyword.value) return myIndicators.value
  const keyword = searchKeyword.value.toLowerCase()
  return myIndicators.value.filter(ind =>
    ind.name.toLowerCase().includes(keyword) ||
    (ind.description || '').toLowerCase().includes(keyword)
  )
})

const filteredSystemIndicators = computed(() => {
  if (!searchKeyword.value) return systemIndicators.value
  const keyword = searchKeyword.value.toLowerCase()
  return systemIndicators.value.filter(ind =>
    ind.name.toLowerCase().includes(keyword) ||
    (ind.description || '').toLowerCase().includes(keyword)
  )
})

// 加载持仓和自选股
const loadMyStocks = async () => {
  try {
    const response = await stockApi.getMyStocks()
    positionStocks.value = response.positions || []
    watchlistStocks.value = response.watchlist || []
  } catch (error) {
    console.error('加载持仓/自选股失败:', error)
    // 失败不阻塞，用户仍可搜索
  }
}

// 防抖搜索
const handleStockSearch = debounce(async (query: string) => {
  if (!query || query.length < 2) {
    searchResults.value = []
    return
  }

  searchLoading.value = true
  try {
    const results = await stockApi.searchStocks(query)
    searchResults.value = results
  } catch (error) {
    console.error('搜索股票失败:', error)
    ElMessage.error('搜索股票失败')
  } finally {
    searchLoading.value = false
  }
}, 300)

const getAllSelectableStocks = () => [
  ...positionStocks.value,
  ...watchlistStocks.value,
  ...searchResults.value
]

const getStockName = (symbol: string) => {
  return currentSymbolNameBySymbol[symbol] || getAllSelectableStocks().find(s => s.symbol === symbol)?.name || symbol
}

const isIndicatorStrategy = (strategy: string) => strategy.startsWith('indicator:')

const getIndicatorId = (strategy: string) => strategy.split(':')[1]

const normalizeStrategyResponseItems = (response: any) => {
  if (Array.isArray(response)) return response
  return response?.strategies ?? response?.items ?? response?.data?.strategies ?? response?.data?.items ?? []
}

const dedupeStrategyOptions = (options: Array<{ label: string, value: string }>) => {
  const seen = new Set<string>()
  return options.filter(option => {
    if (!option.value || seen.has(option.value)) return false
    seen.add(option.value)
    return true
  })
}

const formatBuiltinStrategyLabel = (strategy: any) => {
  return strategy.className ?? strategy.name ?? strategy.strategyName ?? strategy.strategy_type ?? strategy.strategyType
}

const buildStrategyOptions = (personalIndicators: any[], systemIndicators: any[], builtinStrategies: any) => dedupeStrategyOptions([
  ...personalIndicators.map((indicator: any) => ({
    label: indicator.name,
    value: `indicator:${indicator.id}`
  })),
  ...systemIndicators.map((indicator: any) => ({
    label: indicator.name,
    value: `indicator:${indicator.id}`
  })),
  ...normalizeStrategyResponseItems(builtinStrategies).map((strategy: any) => ({
    label: formatBuiltinStrategyLabel(strategy),
    value: strategy.strategyType ?? strategy.strategy_type ?? strategy.name
  })),
  ...fallbackStrategies
])

const findIndicatorByStrategy = (strategy: string) => {
  const indicatorId = getIndicatorId(strategy)
  return [...myIndicators.value, ...systemIndicators.value].find(indicator => indicator.id.toString() === indicatorId)
}

const getSelectedStrategyLabel = () => {
  return strategyOptions.value.find(option => option.value === selectedStrategy.value)?.label || selectedStrategy.value
}

const buildBacktestParameters = (strategy = selectedStrategy.value) => {
  if (strategy === 'pe_mean_reversion') {
    return {
      peHeavyBuy: backtestForm.peHeavyBuy,
      peBatchBuy: backtestForm.peBatchBuy,
      peReduce: backtestForm.peReduce,
      peLiquidate: backtestForm.peLiquidate,
      epsStart: backtestForm.epsStart,
      epsEnd: backtestForm.epsEnd,
      stopLossPct: backtestForm.stopLossPct / 100,
      takeProfitPct: backtestForm.takeProfitPct / 100,
      dividendYield: backtestForm.dividendYield / 100
    }
  }

  if (strategy === 'pb_mean_reversion') {
    return {
      pbHeavyBuy: backtestForm.pbHeavyBuy,
      pbBatchBuy: backtestForm.pbBatchBuy,
      pbReduce: backtestForm.pbReduce,
      pbLiquidate: backtestForm.pbLiquidate,
      roeMean: backtestForm.roeMean,
      epsStart: backtestForm.epsStart,
      epsEnd: backtestForm.epsEnd,
      stopLossPct: backtestForm.stopLossPct / 100,
      takeProfitPct: backtestForm.takeProfitPct / 100
    }
  }

  return {
    fastPeriod: backtestForm.fastPeriod,
    slowPeriod: backtestForm.slowPeriod,
    rsiPeriod: backtestForm.rsiPeriod
  }
}

const getBacktestSource = (result: any) => result?.data ?? result?.result ?? result ?? {}

const getBacktestTrades = (result: any) => {
  const source = getBacktestSource(result)
  const trades = source?.trades ?? source?.summary?.trades ?? []
  return Array.isArray(trades) ? trades : []
}

const runBuiltinBacktest = (symbol: string) => analysisApi.runBacktest({
  strategy: selectedStrategy.value,
  symbol,
  startDate: backtestForm.startDate,
  endDate: backtestForm.endDate,
  period: backtestForm.period,
  initialCapital: backtestForm.initialCapital,
  parameters: buildBacktestParameters()
})

const buildSignalSeriesFromTrades = (trades: any[], klineData: KlineData[]) => {
  const buy = klineData.map(() => false)
  const sell = klineData.map(() => false)

  trades.forEach((trade) => {
    const date = trade.date ?? trade.tradeDate ?? trade.trade_date ?? trade.entryDate ?? trade.entry_date ?? trade.exitDate ?? trade.exit_date
    const index = klineData.findIndex(kline => kline.date === date)
    if (index < 0) return

    const type = String(trade.type ?? trade.action ?? trade.side ?? '').toLowerCase()
    if (type === 'buy' || trade.entryDate || trade.entry_date) {
      buy[index] = true
    } else if (type === 'sell' || trade.exitDate || trade.exit_date) {
      sell[index] = true
    }
  })

  return { buy, sell }
}

// 股票切换处理
const handleStockChange = (symbols: string[] | string) => {
  const allStocks = [
    ...positionStocks.value,
    ...watchlistStocks.value,
    ...searchResults.value
  ]
  const values = Array.isArray(symbols) ? symbols : [symbols]

  values.forEach((symbol) => {
    const stock = allStocks.find(s => s.symbol === symbol)
    if (stock) {
      currentSymbolNameBySymbol[symbol] = stock.name
    }
  })

  if (values[0]) {
    currentSymbol.value = values[0]
    currentSymbolName.value = getStockName(values[0])
  }

  // 不自动运行指标，等用户点击"运行"按钮
}

const handleFrequencyChange = () => {
  previewResults.value = []
  previewData.value = null
  backtestResult.value = null
}

const handleStrategyChange = (strategy: string) => {
  if (isIndicatorStrategy(strategy)) {
    const indicator = findIndicatorByStrategy(strategy)
    if (indicator) selectIndicator(indicator)
    return
  }

  selectedIndicator.value = null
  currentIndicatorName.value = getSelectedStrategyLabel()
  currentIndicatorCode.value = ''
  applyStrategyNotebook(emptyNotebook())
  previewData.value = null
  previewResults.value = []
  backtestResult.value = null
}

// 同步回测表单
watch(selectedSymbols, (newSymbols) => {
  if (newSymbols[0]) {
    currentSymbol.value = newSymbols[0]
    backtestForm.symbol = newSymbols[0]
  }
})

watch(currentSymbol, (newSymbol) => {
  backtestForm.symbol = newSymbol
})

const emptyNotebook = (): StrategyNotebook => ({
  pros: '',
  cons: '',
  observations: '',
  nextSteps: ''
})

const normalizeStrategyNotebook = (notebook?: Partial<StrategyNotebook> & { next_steps?: string } | null): StrategyNotebook => ({
  pros: notebook?.pros || '',
  cons: notebook?.cons || '',
  observations: notebook?.observations || '',
  nextSteps: notebook?.nextSteps || notebook?.next_steps || ''
})

const parseStrategyNotebook = (indicator: IndicatorInfo): StrategyNotebook => {
  if (indicator.notebook) {
    return normalizeStrategyNotebook(indicator.notebook)
  }

  const description = indicator.description
  if (!description) return emptyNotebook()

  try {
    const parsed = JSON.parse(description)
    if (parsed?.notebook) {
      return normalizeStrategyNotebook(parsed.notebook)
    }
  } catch {
    // 兼容旧描述，保留在观察记录里
  }

  return {
    ...emptyNotebook(),
    observations: description
  }
}

const applyStrategyNotebook = (notebook: StrategyNotebook) => {
  strategyNotebook.pros = notebook.pros
  strategyNotebook.cons = notebook.cons
  strategyNotebook.observations = notebook.observations
  strategyNotebook.nextSteps = notebook.nextSteps
}

// 加载指标列表
const loadIndicators = async (params: Record<string, any> = {}) => {
  loadingIndicators.value = true
  loadingStrategies.value = true
  try {
    const previousStrategy = selectedStrategy.value
    const [myRes, systemRes, builtinStrategies] = await Promise.all([
      indicatorApi.getMyIndicators(params),
      indicatorApi.getSystemIndicators(params),
      strategyApi.getStrategies({ source: 'builtin', pageSize: 200 } as any)
    ])
    // 处理可能的数组或对象响应
    myIndicators.value = Array.isArray(myRes) ? myRes : (myRes.items || [])
    systemIndicators.value = Array.isArray(systemRes) ? systemRes : (systemRes.items || [])
    strategyOptions.value = buildStrategyOptions(myIndicators.value, systemIndicators.value, builtinStrategies)

    // 默认选中第一个指标
    if (myIndicators.value.length > 0) {
      selectIndicator(myIndicators.value[0])
    } else if (systemIndicators.value.length > 0) {
      selectIndicator(systemIndicators.value[0])
    }
    selectedStrategy.value = strategyOptions.value.some(option => option.value === previousStrategy)
      ? previousStrategy
      : fallbackStrategies[0].value
  } catch (error) {
    console.error('加载指标列表失败:', error)
    strategyOptions.value = [...fallbackStrategies]
    selectedStrategy.value = fallbackStrategies[0].value
    ElMessage.error('加载指标列表失败')
    throw error
  } finally {
    loadingIndicators.value = false
    loadingStrategies.value = false
  }
}

const refreshIndicators = async () => {
  const timestamp = Date.now()
  await loadIndicators({ _t: timestamp })
  ElMessage.success(`指标库已刷新：我的 ${myIndicators.value.length} 个，系统 ${systemIndicators.value.length} 个`)
}

// 选中指标
const selectIndicator = (indicator: IndicatorInfo) => {
  selectedIndicator.value = indicator
  selectedStrategy.value = `indicator:${indicator.id}`
  currentIndicatorName.value = indicator.name
  currentIndicatorCode.value = indicator.codeContent || ''
  applyStrategyNotebook(parseStrategyNotebook(indicator))

  // 清空预览和回测结果
  previewData.value = null
  previewResults.value = []
  backtestResult.value = null
}

// 创建新指标
const createNewIndicator = () => {
  selectedIndicator.value = null
  currentIndicatorName.value = '新指标'
  currentIndicatorCode.value = `# 自定义指标

# @param ma_short int 5 短期均线
# @param ma_long int 20 长期均线
# @strategy stopLossPct 0.02
# @strategy takeProfitPct 0.05
# @strategy entryPct 0.25

# 计算双均线
df['ma_short'] = df['close'].rolling(window=params['ma_short']).mean()
df['ma_long'] = df['close'].rolling(window=params['ma_long']).mean()

# 金叉买入：短期上穿长期
df['buy'] = (df['ma_short'] > df['ma_long']) & (df['ma_short'].shift(1) <= df['ma_long'].shift(1))

# 死叉卖出：短期下穿长期
df['sell'] = (df['ma_short'] < df['ma_long']) & (df['ma_short'].shift(1) >= df['ma_long'].shift(1))`

  previewData.value = null
  previewResults.value = []
  applyStrategyNotebook(emptyNotebook())
  backtestResult.value = null
}

// 运行指标
const runIndicator = async () => {
  const symbols = selectedSymbols.value.length > 0 ? selectedSymbols.value : [currentSymbol.value].filter(Boolean)
  if (!selectedStrategy.value || symbols.length === 0) {
    ElMessage.warning('请先选择策略和股票')
    return
  }

  running.value = true

  try {
    const results = await Promise.all(symbols.map(async (symbol) => {
      if (!isIndicatorStrategy(selectedStrategy.value)) {
        const [klineData, result] = await Promise.all([
          stockApi.getKLineData({
            symbol,
            timeFrame: backtestForm.period,
            limit: PREVIEW_KLINE_LIMIT
          }),
          runBuiltinBacktest(symbol)
        ])
        const trades = getBacktestTrades(result)
        const normalizedResult = buildBacktestResult(result)
        const latestTrade = trades.at(-1)
        const latestTradeType = String(latestTrade?.type ?? latestTrade?.action ?? latestTrade?.side ?? '').toLowerCase()

        return {
          symbol,
          symbolName: getStockName(symbol),
          currentValue: klineData.at(-1)?.close || 0,
          date: klineData.at(-1)?.date || '',
          signal: latestTradeType === 'buy' ? 'buy' as const : latestTradeType === 'sell' ? 'sell' as const : undefined,
          signalTriggered: latestTradeType === 'buy' || latestTradeType === 'sell',
          klineData,
          indicatorSeries: {},
          signalSeries: buildSignalSeriesFromTrades(trades, klineData),
          backtestResult: normalizedResult
        }
      }

      const indicatorId = getIndicatorId(selectedStrategy.value)
      const result: IndicatorRunResult = await indicatorApi.runIndicator(
        indicatorId,
        {
          symbol,
          period: backtestForm.period,
          limit: PREVIEW_KLINE_LIMIT,
          chartLimit: PREVIEW_KLINE_LIMIT
        }
      )
      const latestSignal = result.latestSignal

      return {
        symbol,
        symbolName: getStockName(symbol),
        currentValue: result.price || 0,
        date: result.date || result.klineData?.at(-1)?.date || '',
        signal: latestSignal === 'buy' ? 'buy' as const : latestSignal === 'sell' ? 'sell' as const : undefined,
        signalTriggered: latestSignal === 'buy' || latestSignal === 'sell',
        klineData: result.klineData || [],
        indicatorSeries: result.indicatorSeries || {},
        signalSeries: result.signalSeries
      }
    }))

    previewResults.value = results
    previewData.value = results[0] || null

    ElMessage.success('指标计算完成')
  } catch (error: any) {
    console.error('运行指标失败:', error)
    ElMessage.error(error?.message || '指标计算失败')
  } finally {
    running.value = false
  }
}

// 保存指标
const saveIndicator = async () => {
  saveDialogVisible.value = true

  // 如果是已有指标，填充表单
  if (selectedIndicator.value) {
    saveForm.name = currentIndicatorName.value
    saveForm.description = selectedIndicator.value.description || ''
    saveForm.category = selectedIndicator.value.category || 'custom'
  } else {
    saveForm.name = currentIndicatorName.value
    saveForm.description = ''
    saveForm.category = 'custom'
  }
}

// 发布指标到社区
const publishIndicator = async () => {
  if (!selectedIndicator.value) {
    ElMessage.warning('请先选择或创建一个指标')
    return
  }

  try {
    await ElMessageBox.confirm(
      '发布后，其他用户将可以看到并使用您的指标。是否继续？',
      '确认发布',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await indicatorApi.publishIndicator(selectedIndicator.value.id.toString())
    ElMessage.success('指标发布成功')

    // 重新加载指标列表
    await loadIndicators()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('发布指标失败:', error)
      ElMessage.error('发布指标失败')
    }
  }
}

// 复制代码
const copyCode = async () => {
  if (!currentIndicatorCode.value.trim()) {
    ElMessage.warning('没有可复制的代码')
    return
  }

  try {
    await navigator.clipboard.writeText(currentIndicatorCode.value)
    ElMessage.success('代码已复制到剪贴板')
  } catch (error) {
    console.error('复制失败:', error)
    ElMessage.error('复制失败')
  }
}

// 删除当前选中的自定义指标
const deleteSelectedIndicator = async () => {
  if (!selectedIndicator.value) {
    ElMessage.warning('请先选择要删除的指标')
    return
  }

  if (selectedIndicator.value.strategyType !== 'custom') {
    ElMessage.warning('系统指标不能删除')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定删除「${selectedIndicator.value.name}」吗？此操作不可恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await indicatorApi.deleteIndicator(selectedIndicator.value.id.toString())
    ElMessage.success('指标删除成功')

    selectedIndicator.value = null
    currentIndicatorName.value = ''
    currentIndicatorCode.value = ''
    previewData.value = null
    previewResults.value = []
    applyStrategyNotebook(emptyNotebook())
    backtestResult.value = null

    await loadIndicators()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除指标失败:', error)
      ElMessage.error('删除指标失败')
    }
  }
}

// 提交保存指标
const submitSaveIndicator = async () => {
  if (!saveForm.name.trim()) {
    ElMessage.warning('请输入指标名称')
    return
  }

  if (!currentIndicatorCode.value.trim()) {
    ElMessage.warning('请输入指标代码')
    return
  }

  saving.value = true

  try {
    const indicatorData: Partial<Indicator> = {
      name: saveForm.name,
      code: currentIndicatorCode.value,
      description: saveForm.description,
      category: saveForm.category,
      parameters: [],
      isPublic: false
    }

    if (selectedIndicator.value) {
      // 更新现有指标
      await indicatorApi.updateIndicator(selectedIndicator.value.id.toString(), indicatorData)
      ElMessage.success('指标更新成功')
    } else {
      // 创建新指标
      const res = await indicatorApi.createIndicator(indicatorData) as any
      selectedIndicator.value = res
      ElMessage.success('指标创建成功')
    }

    // 更新当前指标名称
    currentIndicatorName.value = saveForm.name

    // 重新加载指标列表
    await loadIndicators()

    saveDialogVisible.value = false
  } catch (error) {
    console.error('保存指标失败:', error)
    ElMessage.error('保存指标失败')
  } finally {
    saving.value = false
  }
}

const saveStrategyNotebook = async () => {
  if (!selectedIndicator.value) {
    ElMessage.warning('请先选择策略')
    return
  }

  savingNotebook.value = true
  try {
    const notebook = normalizeStrategyNotebook(strategyNotebook)
    await indicatorApi.updateIndicator(selectedIndicator.value.id.toString(), { notebook })
    selectedIndicator.value.notebook = notebook
    ElMessage.success('策略笔记已保存')
  } catch (error) {
    console.error('保存策略笔记失败:', error)
    ElMessage.error('保存策略笔记失败')
  } finally {
    savingNotebook.value = false
  }
}

const buildBacktestResult = (result: any): IndicatorBacktest['result'] => {
  const source = getBacktestSource(result)
  const trades = getBacktestTrades(result)

  return {
    winRate: source.winRate ?? source.win_rate ?? 0,
    totalReturn: source.totalReturn ?? source.total_return ?? 0,
    sharpeRatio: source.sharpeRatio ?? source.sharpe_ratio ?? 0,
    maxDrawdown: source.maxDrawdown ?? source.max_drawdown ?? 0,
    trades: source.totalTrades ?? source.total_trades ?? trades.length
  }
}

const runAllPreviewBacktests = async () => {
  if (previewResults.value.length === 0) {
    ElMessage.warning('请先运行指标生成股票预览')
    return
  }

  if (isIndicatorStrategy(selectedStrategy.value) && !currentIndicatorCode.value.trim()) {
    ElMessage.warning('请先编写指标代码')
    return
  }

  if (isIndicatorStrategy(selectedStrategy.value) && !selectedIndicator.value?.id) {
    ElMessage.warning('请先保存指标后再进行回测')
    return
  }

  backtesting.value = true
  previewResults.value.forEach((preview) => {
    preview.backtestLoading = true
  })

  try {
    await Promise.all(previewResults.value.map(async (preview) => {
      try {
        const result = isIndicatorStrategy(selectedStrategy.value)
          ? await indicatorApi.backtestIndicator({
            indicatorId: getIndicatorId(selectedStrategy.value),
            symbol: preview.symbol,
            startDate: backtestForm.startDate,
            endDate: backtestForm.endDate,
            initialCash: backtestForm.initialCapital,
            period: backtestForm.period
          }) as any
          : await runBuiltinBacktest(preview.symbol) as any

        preview.backtestResult = buildBacktestResult(result)
      } finally {
        preview.backtestLoading = false
      }
    }))

    ElMessage.success('全部股票回测完成')
  } catch (error) {
    console.error('批量回测失败:', error)
    ElMessage.error('批量回测失败')
  } finally {
    previewResults.value.forEach((preview) => {
      preview.backtestLoading = false
    })
    backtesting.value = false
  }
}

// 提交回测
const submitBacktest = async () => {
  if (!backtestForm.symbol.trim()) {
    ElMessage.warning('请输入股票代码')
    return
  }

  if (!backtestForm.startDate || !backtestForm.endDate) {
    ElMessage.warning('请选择回测时间范围')
    return
  }

  backtesting.value = true

  try {
    // 验证代码
    if (isIndicatorStrategy(selectedStrategy.value) && !currentIndicatorCode.value.trim()) {
      ElMessage.warning('请先编写指标代码')
      backtesting.value = false
      return
    }

    // 验证指标已保存
    if (isIndicatorStrategy(selectedStrategy.value) && !selectedIndicator.value?.id) {
      ElMessage.warning('请先保存指标后再进行回测')
      backtesting.value = false
      return
    }

    const backtestSymbol = await stockApi.resolveBacktestSymbol(backtestForm.symbol)

    // 调用回测API
    const result = isIndicatorStrategy(selectedStrategy.value)
      ? await indicatorApi.backtestIndicator({
        indicatorId: getIndicatorId(selectedStrategy.value),
        symbol: backtestSymbol,
        startDate: backtestForm.startDate,
        endDate: backtestForm.endDate,
        initialCash: backtestForm.initialCapital,
        period: backtestForm.period
      }) as any
      : await runBuiltinBacktest(backtestSymbol) as any

    // 后端返回: { totalReturn, sharpeRatio, maxDrawdown, winRate, totalTrades, trades, equityCurve }
    backtestResult.value = buildBacktestResult(result)

    ElMessage.success('回测完成')
    backtestDialogVisible.value = false
  } catch (error) {
    console.error('回测失败:', error)

    // 使用模拟数据作为降级方案
    ElMessage.warning('使用模拟数据进行回测')
    await new Promise(resolve => setTimeout(resolve, 2000))

    backtestResult.value = {
      winRate: 0.685,
      totalReturn: 0.234,
      sharpeRatio: 2.3,
      maxDrawdown: -0.12,
      trades: 45
    }

    backtestDialogVisible.value = false
  } finally {
    backtesting.value = false
  }
}

// 初始化回测日期
const initBacktestDates = () => {
  backtestForm.endDate = toDateInputValue(new Date())
  applyBacktestRange('oneYear')
}

type BacktestRangePreset = 'ninetyDays' | 'halfYear' | 'oneYear'

const toDateInputValue = (date: Date) => {
  const year = date.getFullYear()
  const month = `${date.getMonth() + 1}`.padStart(2, '0')
  const day = `${date.getDate()}`.padStart(2, '0')
  return `${year}-${month}-${day}`
}

const applyBacktestRange = (preset: BacktestRangePreset) => {
  const endDate = backtestForm.endDate ? new Date(`${backtestForm.endDate}T00:00:00`) : new Date()
  const startDate = new Date(endDate)

  if (preset === 'ninetyDays') {
    startDate.setDate(startDate.getDate() - 90)
  } else if (preset === 'halfYear') {
    startDate.setMonth(startDate.getMonth() - 6)
  } else {
    startDate.setFullYear(startDate.getFullYear() - 1)
  }

  backtestForm.endDate = toDateInputValue(endDate)
  backtestForm.startDate = toDateInputValue(startDate)
}

const formatChartDate = (value: string) => {
  if (!value) return ''
  return value.replace('T', ' ').slice(0, 10)
}

const getSignalLabel = (signal?: 'buy' | 'sell') => {
  if (signal === 'buy') return '买入'
  if (signal === 'sell') return '卖出'
  return '观望'
}

const openChartDialog = (result: PreviewResult) => {
  expandedPreview.value = result
  chartDialogVisible.value = true
}

// 初始化
onMounted(() => {
  loadIndicators()
  loadMyStocks()
  initBacktestDates()
})
</script>

<style scoped lang="scss">
.indicator-ide {
  padding: 24px; // 对齐原型 p-6
  min-height: 100vh;
  background: #eef2f7; // 从 #f8fafc 改为 #eef2f7
}

.indicator-library {
  height: calc(100vh - 200px);
  overflow-y: auto;

  .indicator-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px; // p-2
    border-radius: 4px; // rounded
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid transparent; // 添加透明边框

    &:hover {
      background: #f9fafb; // gray-50，从 #f1f5f9 改为 #f9fafb
    }

    &.active {
      background: #eff6ff; // blue-50，从 #dbeafe 改为 #eff6ff
      border-color: #bfdbfe; // blue-200，从 #3b82f6 改为 #bfdbfe
      color: #1e3a8a; // blue-900，从 #1e40af 改为 #1e3a8a
      font-weight: 500;
    }
  }

  // 搜索框样式覆盖 - 限定作用域
  :deep(.el-input) {
    .el-input__wrapper {
      border-radius: 8px; // rounded-lg
      border: 1px solid #e2e8f0; // border-slate-200
      padding: 8px 12px;

      &:hover {
        border-color: #cbd5e1; // slate-300
      }

      &.is-focus {
        border-color: #3b82f6; // blue-500
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
      }
    }
  }
}

.code-editor-card {
  height: calc(100vh - 200px);
  display: flex;
  flex-direction: column;

  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
}

.code-editor {
  flex: 1;
  background: #1f2937; // gray-900，从 #1e1e1e 改为 #1f2937
  border-radius: 8px; // rounded-lg
  overflow: hidden;
  border: none; // 移除原有的 border: 1px solid #333

  .code-textarea {
    width: 100%;
    height: 384px; // h-96，从 min-height: 400px 改为固定 384px
    min-height: 384px;
    padding: 16px;
    background: #1f2937; // 从 #1e1e1e 改为 #1f2937
    color: #4ade80; // green-400，从 #4ec9b0 改为 #4ade80
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 13px;
    line-height: 1.6;
    border: none;
    outline: none;
    resize: none;
    white-space: pre;
    overflow-wrap: normal;
    overflow-x: auto;

    &::placeholder {
      color: #6b7280; // gray-500，从 #6a9955 改为 #6b7280
    }
  }
}

.preview-card {
  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    flex-wrap: wrap;
  }

  .preview-actions {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }

  .preview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 12px;
  }

  .preview-batch-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 12px;
  }

  .preview-backtest-range {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    color: #475569;
    font-size: 13px;

    :deep(.el-date-editor.el-input) {
      width: 150px;
    }
  }

  .preview-backtest-presets {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;

    :deep(.el-button) {
      margin-left: 0;
      padding: 6px 10px;
    }
  }

  .preview-result-card {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 0;
    text-align: left;
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s, transform 0.2s;

    &:hover {
      border-color: #93c5fd;
      box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
      transform: translateY(-1px);
    }
  }

  .preview-click-area {
    cursor: pointer;
  }

  .preview-result-header,
  .preview-result-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    padding: 10px 12px;
  }

  .preview-result-header {
    border-bottom: 1px solid #e2e8f0;
  }

  .preview-result-footer {
    color: #475569;
    border-top: 1px solid #e2e8f0;

    > div {
      display: grid;
      gap: 2px;
    }

    strong {
      color: #2563eb;
    }
  }

  .preview-backtest-metrics {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 8px;
    padding: 0 12px 12px;

    > div {
      display: grid;
      gap: 2px;
      padding: 8px;
      border-radius: 6px;
      background: #f8fafc;
      min-width: 0;
    }

    span {
      font-size: 11px;
      color: #64748b;
    }

    strong {
      font-size: 13px;
      color: #1e293b;
    }

    .metric-positive {
      color: #15803d;
    }

    .metric-negative {
      color: #b91c1c;
    }
  }

  .preview-symbol {
    font-size: 14px;
    font-weight: 700;
    color: #1e293b;
  }

  .preview-date {
    margin-top: 2px;
    font-size: 12px;
    color: #64748b;
  }

  .signal-badge {
    flex: 0 0 auto;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
    background: #f1f5f9;
    color: #475569;

    &.signal-buy {
      background: #dcfce7;
      color: #15803d;
    }

    &.signal-sell {
      background: #fee2e2;
      color: #b91c1c;
    }
  }

  .preview-chart,
  .empty-chart {
    height: 220px;
    background: #0a0a0f;
  }

  .empty-chart {
    display: flex;
    align-items: center;
    justify-content: center;
    color: #94a3b8;
    font-size: 13px;
  }
}

.notebook-card {
  height: calc(100vh - 200px);
  overflow-y: auto;

  .notebook-fields {
    display: grid;
    gap: 12px;
  }

  label {
    display: grid;
    gap: 6px;

    > span {
      font-size: 12px;
      font-weight: 700;
      color: #475569;
    }
  }
}

.chart-dialog {
  :deep(.el-dialog__body) {
    padding-top: 8px;
  }
}

.expanded-chart-wrap {
  .preview-chart {
    height: 62vh;
    min-height: 460px;
    background: #0a0a0f;
    border-radius: 8px;
    overflow: hidden;
  }

  .expanded-chart-meta {
    display: flex;
    gap: 18px;
    flex-wrap: wrap;
    margin-top: 12px;
    color: #475569;
    font-size: 13px;
  }
}

.backtest-card {
  .grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px; // gap-3
    margin-bottom: 16px;

    > div {
      padding: 0; // 移除背景和内边距
      background: transparent; // 从 #f8fafc 改为透明
      border-radius: 0; // 从 8px 改为 0

      p:first-child {
        font-size: 13px;
        color: #475569; // text-slate-600
        margin-bottom: 4px;
      }

      p:last-child {
        font-size: 20px; // text-xl
        font-weight: 700; // font-bold
        line-height: 1.25;
      }
    }
  }

  // 回测按钮
  :deep(.el-button) {
    width: 100%;
    background-color: #ea580c; // orange-600
    border-color: #ea580c;
    color: #ffffff;

    &:hover {
      background-color: #c2410c; // orange-700
      border-color: #c2410c;
    }
  }
}

// Element Plus卡片样式覆盖
:deep(.el-card) {
  border-radius: 12px; // rounded-xl
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); // shadow-sm
  border: 1px solid #e2e8f0; // border-slate-200
  background: #ffffff;
}

:deep(.el-card__header) {
  padding: 16px; // p-4
  border-bottom: 1px solid #e2e8f0; // border-slate-200
  background: transparent;
}

:deep(.el-card__body) {
  padding: 16px; // p-4
}

// 按钮样式系统覆盖
:deep(.el-button) {
  border-radius: 8px; // rounded-lg
  padding: 8px 16px; // px-4 py-2
  font-size: 13px; // text-sm
  font-weight: 500; // font-medium
  height: auto;

  .el-icon {
    margin-right: 4px;
  }
}

// 运行按钮 - 绿色
:deep(.el-button--success) {
  background-color: #16a34a; // green-600
  border-color: #16a34a;

  &:hover {
    background-color: #15803d; // green-700
    border-color: #15803d;
  }
}

// 保存按钮 - 蓝色
:deep(.el-button--primary) {
  background-color: #2563eb; // blue-600
  border-color: #2563eb;

  &:hover {
    background-color: #1d4ed8; // blue-700
    border-color: #1d4ed8;
  }
}

// 发布按钮 - 紫色
:deep(.el-button--warning) {
  background-color: #9333ea; // purple-600
  border-color: #9333ea;
  color: #ffffff;

  &:hover {
    background-color: #7e22ce; // purple-700
    border-color: #7e22ce;
  }
}

// 复制按钮 - 默认样式
:deep(.el-button--default) {
  background-color: #ffffff;
  border-color: #e2e8f0; // border-slate-200
  color: #334155; // text-slate-700

  &:hover {
    background-color: #f8fafc; // bg-slate-50
    border-color: #cbd5e1;
  }
}

// 响应式设计 - 中等屏幕 (1180px)
@media (max-width: 1180px) {
  .indicator-ide {
    padding: 18px;

    .grid.grid-cols-12 {
      grid-template-columns: repeat(6, minmax(0, 1fr));
    }

    .col-span-3,
    .col-span-5,
    .col-span-6,
    .col-span-12,
    .col-span-4 {
      grid-column: span 6 / span 6;
    }

    .notebook-card,
    .indicator-library,
    .code-editor-card {
      height: auto;
    }
  }
}

// 响应式设计 - 移动端 (760px)
@media (max-width: 760px) {
  .indicator-ide {
    padding: 14px;

    .grid.grid-cols-12 {
      grid-template-columns: 1fr;
    }

    .col-span-3,
    .col-span-5,
    .col-span-6,
    .col-span-12,
    .col-span-4 {
      grid-column: auto;
    }

    .code-editor .code-textarea {
      height: 300px;
      min-height: 300px;
    }

    .preview-card .preview-chart,
    .preview-card .empty-chart {
      height: 180px;
    }

    .preview-card .preview-actions {
      width: 100%;

      :deep(.el-select) {
        width: 100% !important;
      }
    }

    .preview-card .preview-batch-actions {
      align-items: stretch;

      > .el-button {
        width: 100%;
      }
    }

    .preview-card .preview-backtest-range {
      width: 100%;

      :deep(.el-date-editor.el-input) {
        flex: 1 1 130px;
        width: auto;
      }
    }

    .preview-card .preview-backtest-presets {
      width: 100%;

      :deep(.el-button) {
        flex: 1 1 72px;
      }
    }
  }
}
</style>
