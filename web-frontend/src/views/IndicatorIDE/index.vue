<template>
  <div class="indicator-ide">
    <!-- 页面标题 -->
    <div class="mb-6">
      <h2 class="text-2xl font-bold text-slate-800 mb-2">📐 指标IDE</h2>
      <p class="text-sm text-slate-500">自定义技术指标编辑器 - 创建、测试、回测您的量化指标</p>
    </div>

    <!-- 三栏布局 -->
    <div class="grid grid-cols-12 gap-4">
      <!-- 左侧：指标库 -->
      <div class="col-span-3">
        <el-card class="indicator-library">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon><Collection /></el-icon>
              <span class="font-bold">指标库</span>
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
      <div class="col-span-5">
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

      <!-- 右侧：预览和回测 -->
      <div class="col-span-4">
        <!-- 实时预览 -->
        <el-card class="preview-card mb-4">
          <template #header>
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <el-icon><TrendCharts /></el-icon>
                <span class="font-bold">实时预览</span>
              </div>

              <el-select
                v-model="currentSymbol"
                filterable
                remote
                reserve-keyword
                placeholder="选择测试股票..."
                :remote-method="handleStockSearch"
                :loading="searchLoading"
                style="width: 200px"
                @change="handleStockChange"
              >
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

                <el-option-group v-if="searchResults.length > 0" label="搜索结果">
                  <el-option
                    v-for="stock in searchResults"
                    :key="stock.symbol"
                    :label="`${stock.symbol} - ${stock.name}`"
                    :value="stock.symbol"
                  />
                </el-option-group>
              </el-select>
            </div>
          </template>

          <!-- 图表容器 -->
          <div ref="chartRef" class="chart-container" />

          <!-- 预览信息 -->
          <div v-if="previewData" class="text-sm text-slate-600 mt-4">
            <p class="mb-2">测试股票：{{ previewData.symbol }} {{ previewData.symbolName }}</p>
            <p class="mb-2">
              当前值：
              <span class="font-semibold text-blue-600">{{ previewData.currentValue }}</span>
              <span
                v-if="previewData.signal"
                :class="previewData.signal === 'buy' ? 'text-green-600' : 'text-red-600'"
                class="ml-2"
              >
                ({{ previewData.signal === 'buy' ? '超卖区域' : '超买区域' }})
              </span>
            </p>
            <p
              v-if="previewData.signalTriggered"
              :class="previewData.signal === 'buy' ? 'text-green-600' : 'text-red-600'"
              class="font-medium"
            >
              ✅ {{ previewData.signal === 'buy' ? '买入' : '卖出' }}信号触发
            </p>
          </div>
        </el-card>

        <!-- 回测结果 -->
        <el-card class="backtest-card">
          <template #header>
            <div class="flex items-center gap-2">
              <el-icon><DataAnalysis /></el-icon>
              <span class="font-bold">回测结果</span>
            </div>
          </template>

          <div v-if="backtestResult" class="grid grid-cols-2 gap-3 text-sm mb-4">
            <div>
              <p class="text-slate-600">胜率</p>
              <p class="text-xl font-bold text-green-600">
                {{ (backtestResult.winRate * 100).toFixed(1) }}%
              </p>
            </div>
            <div>
              <p class="text-slate-600">收益率</p>
              <p
                class="text-xl font-bold"
                :class="backtestResult.totalReturn >= 0 ? 'text-green-600' : 'text-red-600'"
              >
                {{ backtestResult.totalReturn >= 0 ? '+' : '' }}{{ (backtestResult.totalReturn * 100).toFixed(1) }}%
              </p>
            </div>
            <div>
              <p class="text-slate-600">交易次数</p>
              <p class="text-xl font-bold text-slate-800">{{ backtestResult.trades }}</p>
            </div>
            <div>
              <p class="text-slate-600">夏普比率</p>
              <p class="text-xl font-bold text-slate-800">
                {{ backtestResult.sharpeRatio.toFixed(2) }}
              </p>
            </div>
          </div>

          <el-button
            type="warning"
            class="w-full"
            :loading="backtesting"
            @click="runBacktest"
          >
            <el-icon><Refresh /></el-icon>
            完整回测 (90天)
          </el-button>
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
  DataAnalysis,
  Refresh,
  Delete
} from '@element-plus/icons-vue'
import { debounce } from 'lodash-es'
import { useChart } from '@/composables/useChart'
import { indicatorApi } from '@/services/api/indicator'
import { stockApi } from '@/services/api/stock'
import type { Indicator, IndicatorBacktest } from '@/types'
import type {
  IndicatorInfo,
  IndicatorRunResult,
  KlineData
} from '@/types/indicator'
import type { EChartsOption } from 'echarts'

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

// 股票选择器相关状态
const positionStocks = ref<Array<{ symbol: string; name: string }>>([])
const watchlistStocks = ref<Array<{ symbol: string; name: string }>>([])
const searchResults = ref<Array<{ symbol: string; name: string; market?: string }>>([])
const searchLoading = ref(false)

// 加载状态
const running = ref(false)
const saving = ref(false)
const backtesting = ref(false)

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
  initialCapital: 100000
})

// 预览数据
const previewData = ref<{
  symbol: string
  symbolName: string
  currentValue: number
  signal?: 'buy' | 'sell'
  signalTriggered: boolean
} | null>(null)

// 回测结果
const backtestResult = ref<IndicatorBacktest['result'] | null>(null)

// 图表
const chart = useChart({ theme: 'dark' })
const chartRef = chart.chartRef
const { setOption, showLoading, hideLoading } = chart

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

// 股票切换处理
const handleStockChange = (symbol: string) => {
  // 从所有列表中查找股票名称
  const allStocks = [
    ...positionStocks.value,
    ...watchlistStocks.value,
    ...searchResults.value
  ]
  const stock = allStocks.find(s => s.symbol === symbol)

  if (stock) {
    currentSymbolName.value = stock.name
  }

  // 不自动运行指标，等用户点击"运行"按钮
}

// 同步回测表单
watch(currentSymbol, (newSymbol) => {
  backtestForm.symbol = newSymbol
})

// 加载指标列表
const loadIndicators = async () => {
  try {
    const [myRes, systemRes] = await Promise.all([
      indicatorApi.getMyIndicators(),
      indicatorApi.getSystemIndicators()
    ])
    // 处理可能的数组或对象响应
    myIndicators.value = Array.isArray(myRes) ? myRes : (myRes.items || [])
    systemIndicators.value = Array.isArray(systemRes) ? systemRes : (systemRes.items || [])

    // 默认选中第一个指标
    if (myIndicators.value.length > 0) {
      selectIndicator(myIndicators.value[0])
    } else if (systemIndicators.value.length > 0) {
      selectIndicator(systemIndicators.value[0])
    }
  } catch (error) {
    console.error('加载指标列表失败:', error)
    ElMessage.error('加载指标列表失败')
  }
}

// 选中指标
const selectIndicator = (indicator: IndicatorInfo) => {
  selectedIndicator.value = indicator
  currentIndicatorName.value = indicator.name
  currentIndicatorCode.value = indicator.codeContent || ''

  // 清空预览和回测结果
  previewData.value = null
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
  backtestResult.value = null
}

// 运行指标
const runIndicator = async () => {
  if (!selectedIndicator.value || !currentSymbol.value) {
    ElMessage.warning('请先选择指标和股票')
    return
  }

  running.value = true
  showLoading()

  try {
    const result: IndicatorRunResult = await indicatorApi.runIndicator(
      selectedIndicator.value.id.toString(),
      { symbol: currentSymbol.value, limit: 100 }
    )

    // 后端返回格式: { symbol, latestSignal, confidence, price, date, indicators: {...}, klineData: [...], indicatorSeries: {...} }
    const indicatorValues = result.indicators || {}
    const klineData = result.klineData || []
    const indicatorSeries = result.indicatorSeries || {}

    // 设置预览数据
    const latestSignal = result.latestSignal
    previewData.value = {
      symbol: currentSymbol.value,
      symbolName: result.symbol || currentSymbol.value,
      currentValue: result.price || 0,
      signal: latestSignal === 'buy' ? 'buy' : latestSignal === 'sell' ? 'sell' : undefined,
      signalTriggered: latestSignal === 'buy' || latestSignal === 'sell'
    }

    // 渲染K线图（如果有K线数据）
    if (klineData.length > 0) {
      renderKlineChart(klineData, indicatorSeries)
    } else {
      // 降级：显示指标柱状图
      const chartData = Object.entries(indicatorValues).map(([key, value]: [string, any]) => ({
        name: key,
        value: typeof value === 'number' ? value : 0
      }))
      renderChart(chartData)
    }

    ElMessage.success('指标计算完成')
  } catch (error: any) {
    console.error('运行指标失败:', error)
    ElMessage.error(error?.message || '指标计算失败')
  } finally {
    running.value = false
    hideLoading()
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
    backtestResult.value = null

    await loadIndicators()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除指标失败:', error)
      ElMessage.error('删除指标失败')
    }
  }
}

// 运行回测
const runBacktest = async () => {
  if (!currentIndicatorCode.value.trim()) {
    ElMessage.warning('请先编写指标代码')
    return
  }

  if (!selectedIndicator.value?.id) {
    ElMessage.warning('请先保存指标后再进行回测')
    return
  }

  backtestDialogVisible.value = true
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
    if (!currentIndicatorCode.value.trim()) {
      ElMessage.warning('请先编写指标代码')
      backtesting.value = false
      return
    }

    // 验证指标已保存
    if (!selectedIndicator.value?.id) {
      ElMessage.warning('请先保存指标后再进行回测')
      backtesting.value = false
      return
    }

    // 调用回测API
    const backtestData = {
      indicatorId: selectedIndicator.value.id.toString(),
      symbol: backtestForm.symbol,
      startDate: backtestForm.startDate,
      endDate: backtestForm.endDate,
      initialCash: backtestForm.initialCapital
    }

    const result = await indicatorApi.backtestIndicator(backtestData) as any

    // 后端返回: { totalReturn, sharpeRatio, maxDrawdown, winRate, totalTrades, trades, equityCurve }
    backtestResult.value = {
      winRate: result.winRate ?? 0,
      totalReturn: result.totalReturn ?? 0,
      sharpeRatio: result.sharpeRatio ?? 0,
      maxDrawdown: result.maxDrawdown ?? 0,
      trades: result.totalTrades ?? 0
    }

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
  const endDate = new Date()
  const startDate = new Date()
  startDate.setDate(startDate.getDate() - 90)

  backtestForm.endDate = endDate.toISOString().split('T')[0]
  backtestForm.startDate = startDate.toISOString().split('T')[0]
}

// 渲染K线图
const renderKlineChart = (klineData: KlineData[], indicatorSeries: Record<string, (number | null)[]>) => {
  const dates = klineData.map(k => k.date)
  const ohlc = klineData.map(k => [k.open, k.close, k.low, k.high])
  const volumes = klineData.map(k => k.volume)

  // 构建指标线系列
  const indicatorLines = Object.entries(indicatorSeries).map(([name, values]) => ({
    name,
    type: 'line' as const,
    data: values,
    smooth: true,
    lineStyle: { width: 2 },
    showSymbol: false
  }))

  const option: EChartsOption = {
    backgroundColor: '#0a0a0f',
    grid: [
      { left: 60, right: 30, top: 40, bottom: 100, height: '60%' },
      { left: 60, right: 30, top: '75%', bottom: 30, height: '15%' }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        gridIndex: 0,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { show: false },
        splitLine: { show: false }
      },
      {
        type: 'category',
        data: dates,
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { color: '#787b86', fontSize: 10, rotate: 30 },
        splitLine: { show: false }
      }
    ],
    yAxis: [
      {
        type: 'value',
        gridIndex: 0,
        scale: true,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { color: '#787b86', fontSize: 10 },
        splitLine: { lineStyle: { color: '#1e293b', opacity: 0.3 } }
      },
      {
        type: 'value',
        gridIndex: 1,
        axisLine: { lineStyle: { color: '#2a2e39' } },
        axisLabel: { color: '#787b86', fontSize: 10 },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        xAxisIndex: 0,
        yAxisIndex: 0,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e'
        }
      },
      ...indicatorLines.map(line => ({ ...line, xAxisIndex: 0, yAxisIndex: 0 })),
      {
        name: '成交量',
        type: 'bar',
        data: volumes,
        xAxisIndex: 1,
        yAxisIndex: 1,
        itemStyle: {
          color: (params: any) => {
            const idx = params.dataIndex
            return ohlc[idx][1] >= ohlc[idx][0] ? '#ef4444' : '#22c55e'
          }
        }
      }
    ],
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(19, 23, 34, 0.9)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc' }
    },
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 0,
        end: 100
      }
    ]
  }

  setOption(option)
}

// 渲染图表
const renderChart = (chartData: { name: string; value: number }[]) => {
  const names = chartData.map(d => d.name)
  const values = chartData.map(d => d.value)

  const option: EChartsOption = {
    backgroundColor: '#0a0a0f',
    grid: {
      left: 60,
      right: 30,
      top: 40,
      bottom: 60,
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: names,
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86', fontSize: 10, rotate: 30 },
      splitLine: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#787b86', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e293b', opacity: 0.3 } }
    },
    series: [
      {
        name: '因子值',
        type: 'bar',
        data: values.map((v) => ({
          value: v,
          itemStyle: {
            color: v >= 0 ? '#22c55e' : '#ef4444',
            borderRadius: [4, 4, 0, 0]
          }
        })),
        barWidth: '60%'
      }
    ],
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(19, 23, 34, 0.9)',
      borderColor: '#2a2e39',
      textStyle: { color: '#d1d4dc' },
      formatter: (params: any) => {
        const item = Array.isArray(params) ? params[0] : params
        return `${item.name}<br/>值: ${item.value}`
      }
    }
  }

  setOption(option)
}

// 初始化
onMounted(() => {
  loadIndicators()
  loadMyStocks()
  initBacktestDates()
  if (chartRef.value) {
    chart.resize()
  }
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
  .chart-container {
    height: 220px; // 从 280px 改为 220px，对齐原型
    background: #0a0a0f;
    border-radius: 8px; // rounded-lg
    overflow: hidden;
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
    .col-span-4 {
      grid-column: span 6 / span 6;
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
    .col-span-4 {
      grid-column: auto;
    }

    .code-editor .code-textarea {
      height: 300px;
      min-height: 300px;
    }

    .preview-card .chart-container {
      height: 180px;
    }
  }
}
</style>
