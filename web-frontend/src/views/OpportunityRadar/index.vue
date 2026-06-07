<template>
  <div class="opportunity-radar">
    <!-- 页面标题 -->
    <div class="page-header">
      <div>
        <h2 class="page-title">机会雷达</h2>
        <p class="page-subtitle">实时扫描全市场，发现高质量交易机会</p>
      </div>
      <div class="header-actions">
        <el-button
          type="primary"
          :icon="Search"
          :loading="scanning"
          @click="handleScan"
        >
          {{ scanning ? '扫描中...' : '开始扫描' }}
        </el-button>
        <span v-if="lastScanTime" class="last-scan-time">
          上次扫描：{{ formatRelativeTime(lastScanTime) }}
        </span>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-cards">
      <el-card class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #e3f2fd">
            <el-icon :size="24" color="#2196f3"><TrendCharts /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-label">今日机会数</div>
            <div class="stat-value">{{ stats.total }}</div>
          </div>
        </div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #fff3e0">
            <el-icon :size="24" color="#ff9800"><Star /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-label">高置信度机会</div>
            <div class="stat-value">{{ stats.highConfidence }}</div>
          </div>
        </div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #f3e5f5">
            <el-icon :size="24" color="#9c27b0"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-label">待处理</div>
            <div class="stat-value">{{ stats.pending }}</div>
          </div>
        </div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-content">
          <div class="stat-icon" style="background: #e8f5e9">
            <el-icon :size="24" color="#4caf50"><Check /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-label">已执行</div>
            <div class="stat-value">{{ stats.executed }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 筛选条件 -->
    <el-card class="filter-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">筛选条件</span>
          <div class="card-actions">
            <el-button size="small" @click="handleSaveFilters">保存筛选条件</el-button>
            <el-button size="small" @click="handleLoadPreset">加载预设</el-button>
            <el-button size="small" @click="handleResetFilters">重置</el-button>
          </div>
        </div>
      </template>

      <div class="filter-grid">
        <!-- 技术面 -->
        <div class="filter-section">
          <div class="section-title">📊 技术面</div>
          <div class="filter-options">
            <el-checkbox v-model="filters.technical.rsiOversold">RSI &lt; 30 (超卖)</el-checkbox>
            <el-checkbox v-model="filters.technical.macdGoldenCross">MACD 金叉</el-checkbox>
            <el-checkbox v-model="filters.technical.bollingerBreakout">突破布林带上轨</el-checkbox>
            <el-checkbox v-model="filters.technical.volumeSpike">成交量放大 &gt; 2倍</el-checkbox>
          </div>
        </div>

        <!-- 基本面 -->
        <div class="filter-section">
          <div class="section-title">💰 基本面</div>
          <div class="filter-options">
            <el-checkbox v-model="filters.fundamental.lowPE">PE &lt; 30</el-checkbox>
            <el-checkbox v-model="filters.fundamental.highROE">ROE &gt; 15%</el-checkbox>
            <el-checkbox v-model="filters.fundamental.highGrossMargin">毛利率 &gt; 30%</el-checkbox>
            <el-checkbox v-model="filters.fundamental.lowDebtRatio">负债率 &lt; 50%</el-checkbox>
          </div>
        </div>

        <!-- 资金面 -->
        <div class="filter-section">
          <div class="section-title">💵 资金面</div>
          <div class="filter-options">
            <el-checkbox v-model="filters.sentiment.mainForceInflow">主力净流入</el-checkbox>
            <el-checkbox v-model="filters.sentiment.northboundInflow">北向资金流入</el-checkbox>
            <el-checkbox v-model="filters.sentiment.institutionalIncrease">机构持仓增加</el-checkbox>
            <el-checkbox v-model="filters.sentiment.marginIncrease">融资余额增加</el-checkbox>
          </div>
        </div>
      </div>

      <div class="filter-advanced">
        <el-row :gutter="16">
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="扫描策略">
              <el-select
                v-model="filters.strategyId"
                placeholder="综合评分"
                clearable
                filterable
                :loading="strategyLoading"
              >
                <el-option label="综合评分模型" value="" />
                <el-option
                  v-for="strategy in strategyOptions"
                  :key="strategy.id"
                  :label="strategy.name"
                  :value="strategy.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="综合评分">
              <el-slider
                v-model="filters.scoreRange"
                range
                :min="0"
                :max="100"
                :marks="{ 0: '0', 50: '50', 100: '100' }"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="置信度">
              <el-slider
                v-model="filters.confidenceRange"
                range
                :min="0"
                :max="100"
                :marks="{ 0: '0%', 50: '50%', 100: '100%' }"
              />
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="风险等级">
              <el-select v-model="filters.riskLevel" placeholder="全部" clearable>
                <el-option label="低风险" value="low" />
                <el-option label="中风险" value="medium" />
                <el-option label="高风险" value="high" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-form-item label="行业">
              <el-select v-model="filters.industries" placeholder="全部" multiple clearable>
                <el-option label="白酒" value="白酒" />
                <el-option label="新能源" value="新能源" />
                <el-option label="半导体" value="半导体" />
                <el-option label="医药" value="医药" />
                <el-option label="银行" value="银行" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
      </div>
    </el-card>

    <!-- 机会列表 -->
    <el-card class="opportunities-card">
      <template #header>
        <div class="card-header">
          <span class="card-title">发现机会：{{ total }} 只股票</span>
          <div class="card-actions">
            <span class="sort-label">排序：</span>
            <el-select v-model="sortBy" size="small" style="width: 150px" @change="handleSort">
              <el-option label="综合评分 ▼" value="score" />
              <el-option label="技术面评分" value="technicalScore" />
              <el-option label="基本面评分" value="fundamentalScore" />
              <el-option label="资金面评分" value="sentimentScore" />
              <el-option label="置信度" value="confidence" />
              <el-option label="预期收益" value="expectedReturn" />
            </el-select>
          </div>
        </div>
      </template>

      <div v-loading="loading" class="opportunities-list">
        <div
          v-for="opportunity in paginatedData"
          :key="opportunity.id"
          class="opportunity-card"
          @click="handleViewDetail(opportunity)"
        >
          <!-- 头部信息 -->
          <div class="opportunity-header">
            <div class="stock-info">
              <div class="stock-main">
                <span class="stock-code">{{ opportunity.symbol }}</span>
                <span class="stock-name">{{ opportunity.symbolName }}</span>
                <el-tag :type="getRiskLevelType(opportunity.riskLevel)" size="small">
                  {{ getRiskLevelText(opportunity.riskLevel) }}
                </el-tag>
              </div>
            </div>
            <div class="score-info">
              <div class="score-stars">
                <el-rate
                  :model-value="getStarRating(opportunity.score)"
                  disabled
                  show-score
                  text-color="#ff9800"
                />
              </div>
              <div class="score-value">{{ opportunity.score }}分</div>
              <div class="score-label">综合评分</div>
            </div>
          </div>

          <!-- 评分进度条 -->
          <div class="score-bars">
            <div class="score-bar-item">
              <div class="score-bar-label">技术面</div>
              <div class="score-bar-content">
                <el-progress
                  :percentage="opportunity.technicalScore"
                  :color="getScoreColor(opportunity.technicalScore)"
                  :show-text="false"
                />
                <span class="score-bar-value">{{ opportunity.technicalScore }}</span>
              </div>
            </div>
            <div class="score-bar-item">
              <div class="score-bar-label">基本面</div>
              <div class="score-bar-content">
                <el-progress
                  :percentage="opportunity.fundamentalScore"
                  :color="getScoreColor(opportunity.fundamentalScore)"
                  :show-text="false"
                />
                <span class="score-bar-value">{{ opportunity.fundamentalScore }}</span>
              </div>
            </div>
            <div class="score-bar-item">
              <div class="score-bar-label">资金面</div>
              <div class="score-bar-content">
                <el-progress
                  :percentage="opportunity.sentimentScore"
                  :color="getScoreColor(opportunity.sentimentScore)"
                  :show-text="false"
                />
                <span class="score-bar-value">{{ opportunity.sentimentScore }}</span>
              </div>
            </div>
          </div>

          <!-- 机会标签 -->
          <div class="opportunity-tags">
            <el-tag
              v-for="(reason, index) in opportunity.reasons"
              :key="index"
              :type="getReasonTagType(reason)"
              size="small"
            >
              {{ reason }}
            </el-tag>
          </div>

          <!-- 操作按钮 -->
          <div class="opportunity-actions">
            <el-button type="primary" size="small" @click.stop="handleViewDetail(opportunity)">
              查看详情
            </el-button>
            <el-button size="small" @click.stop="handleAddToWatchlist(opportunity)">
              加入自选
            </el-button>
            <el-button type="success" size="small" @click.stop="handleQuickTrade(opportunity)">
              快速交易
            </el-button>
          </div>
        </div>

        <!-- 空状态 -->
        <el-empty v-if="!loading && opportunities.length === 0" description="暂无机会数据" />

        <!-- 加载更多 -->
        <div v-if="opportunities.length > 0 && hasMore" class="load-more">
          <el-button @click="handleLoadMore">
            加载更多 (还有 {{ total - currentPage * pageSize }} 只)
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 快速交易弹窗 -->
    <el-dialog
      v-model="quickTradeDialogVisible"
      title="快速交易"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form :model="quickTradeForm" label-width="100px">
        <el-form-item label="股票">
          <el-input :value="`${quickTradeForm.symbol} ${quickTradeForm.symbolName}`" disabled />
        </el-form-item>
        <el-form-item label="方向">
          <el-radio-group v-model="quickTradeForm.direction">
            <el-radio label="buy">买入</el-radio>
            <el-radio label="sell">卖出</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="价格类型">
          <el-radio-group v-model="quickTradeForm.priceType">
            <el-radio label="market">市价单</el-radio>
            <el-radio label="limit">限价单</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="quickTradeForm.priceType === 'limit'" label="价格">
          <el-input-number
            v-model="quickTradeForm.price"
            :min="0"
            :precision="2"
            :step="0.01"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="数量">
          <el-input-number
            v-model="quickTradeForm.quantity"
            :min="100"
            :step="100"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="quickTradeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="quickTradeLoading" @click="submitQuickTrade">
          提交订单
        </el-button>
      </template>
    </el-dialog>

    <!-- 加载预设弹窗 -->
    <el-dialog
      v-model="loadPresetDialogVisible"
      title="加载预设"
      width="600px"
    >
      <div v-if="presets.length === 0" class="empty-presets">
        <el-empty description="暂无保存的预设" />
      </div>
      <div v-else class="presets-list">
        <div
          v-for="(preset, index) in presets"
          :key="index"
          class="preset-item"
        >
          <div class="preset-info">
            <div class="preset-name">{{ preset.name }}</div>
            <div class="preset-date">{{ formatRelativeTime(preset.createdAt) }}</div>
          </div>
          <div class="preset-actions">
            <el-button type="primary" size="small" @click="applyPreset(preset)">
              应用
            </el-button>
            <el-button type="danger" size="small" @click="deletePreset(index)">
              删除
            </el-button>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="loadPresetDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Search,
  TrendCharts,
  Star,
  Clock,
  Check
} from '@element-plus/icons-vue'
import { useTable } from '@/composables/useTable'
import { analysisApi } from '@/services/api/analysis'
import { strategyApi } from '@/services/api/strategy'
import { tradingApi } from '@/services/api/trading'
import { toSnakeCase } from '@/utils/format'
import type { Opportunity, OpportunityFilters, CreateOrderRequest, Strategy } from '@/types'

// 筛选条件
const filters = reactive<{
  strategyId: string
  technical: Record<string, boolean>
  fundamental: Record<string, boolean>
  sentiment: Record<string, boolean>
  scoreRange: [number, number]
  confidenceRange: [number, number]
  riskLevel: string
  industries: string[]
}>({
  strategyId: '',
  technical: {
    rsiOversold: true,
    macdGoldenCross: true,
    bollingerBreakout: false,
    volumeSpike: false
  },
  fundamental: {
    lowPE: true,
    highROE: true,
    highGrossMargin: false,
    lowDebtRatio: false
  },
  sentiment: {
    mainForceInflow: true,
    northboundInflow: false,
    institutionalIncrease: false,
    marginIncrease: false
  },
  scoreRange: [60, 100],
  confidenceRange: [50, 100],
  riskLevel: '',
  industries: []
})

// 统计数据
const stats = reactive({
  total: 0,
  highConfidence: 0,
  pending: 0,
  executed: 0
})

// 扫描状态
const scanning = ref(false)
const lastScanTime = ref<string>('')
const strategyLoading = ref(false)
const strategyOptions = ref<Array<Pick<Strategy, 'id' | 'name'>>>([])

// 排序
const sortBy = ref('score')

// 快速交易弹窗
const quickTradeDialogVisible = ref(false)
const quickTradeForm = reactive({
  symbol: '',
  symbolName: '',
  direction: 'buy' as 'buy' | 'sell',
  priceType: 'market' as 'market' | 'limit',
  price: 0,
  quantity: 100
})
const quickTradeLoading = ref(false)

// 预设弹窗
const loadPresetDialogVisible = ref(false)
const presets = ref<Array<{
  name: string
  filters: any
  createdAt: string
}>>([])

// 表格数据
const {
  data: opportunities,
  loading,
  total,
  currentPage,
  pageSize,
  paginatedData,
  setData,
  changePage
} = useTable<Opportunity>({ pageSize: 10 })

// 是否有更多数据
const hasMore = computed(() => {
  return total.value > currentPage.value * pageSize.value
})

// 将筛选条件转换为后端期望的数组格式
const buildFilterArrays = () => {
  const technicalArray = Object.keys(filters.technical)
    .filter(key => filters.technical[key])
    .map(key => toSnakeCase(key))

  const fundamentalArray = Object.keys(filters.fundamental)
    .filter(key => filters.fundamental[key])
    .map(key => toSnakeCase(key))

  return { technicalArray, fundamentalArray }
}

// 获取机会列表
const fetchOpportunities = async () => {
  try {
    const { technicalArray, fundamentalArray } = buildFilterArrays()

    const apiFilters: OpportunityFilters = {
      minScore: filters.scoreRange[0],
      maxRiskLevel: filters.riskLevel || undefined,
      industries: filters.industries.length > 0 ? filters.industries : undefined,
      technical: technicalArray,
      fundamental: fundamentalArray
    }

    const response = await analysisApi.getOpportunities({
      page: currentPage.value,
      pageSize: pageSize.value,
      sortBy: sortBy.value,
      sortOrder: 'desc',
      ...apiFilters
    })

    setData(response.items, response.total)
    updateStats(response.items)
  } catch (error) {
    console.error('Failed to fetch opportunities:', error)
    ElMessage.error('获取机会列表失败')
  }
}

const loadStrategies = async () => {
  strategyLoading.value = true
  try {
    const response = await strategyApi.getStrategies({ page: 1, pageSize: 200 })
    strategyOptions.value = (response.items || []).map((strategy: any) => ({
      id: String(strategy.id),
      name: formatStrategyOptionLabel(strategy)
    }))
  } catch (error) {
    console.error('Failed to load strategies:', error)
    ElMessage.error('获取策略列表失败')
  } finally {
    strategyLoading.value = false
  }
}

const formatStrategyOptionLabel = (strategy: any): string => {
  const id = String(strategy.id ?? '')
  const rawName = strategy.name || strategy.strategyName || strategy.strategy_name
  const description = strategy.description || ''
  const codeTitle = extractStrategyCodeTitle(strategy.code)
  const name = String(rawName || description || codeTitle || `策略 ${id}`).trim()

  return id && !name.includes(`#${id}`) ? `${name} #${id}` : name
}

const extractStrategyCodeTitle = (code?: string): string => {
  if (!code) return ''

  const firstComment = code
    .split('\n')
    .map(line => line.trim())
    .find(line => line.startsWith('#'))

  return firstComment
    ? firstComment.replace(/^#+\s*/, '').trim()
    : ''
}

// 更新统计数据
const updateStats = (data: Opportunity[]) => {
  stats.total = total.value
  stats.highConfidence = data.filter(o => o.confidence >= 80).length
  stats.pending = data.filter(o => o.score >= 70).length
  stats.executed = 0 // TODO: 从API获取
}

// 扫描机会
const handleScan = async () => {
  scanning.value = true
  try {
    const { technicalArray, fundamentalArray } = buildFilterArrays()

    const apiFilters: OpportunityFilters = {
      strategyId: filters.strategyId || undefined,
      minScore: filters.scoreRange[0],
      maxRiskLevel: filters.riskLevel || undefined,
      industries: filters.industries.length > 0 ? filters.industries : undefined,
      technical: technicalArray,
      fundamental: fundamentalArray,
      page: currentPage.value,
      pageSize: pageSize.value
    }

    const response = await analysisApi.scanOpportunities(apiFilters)
    lastScanTime.value = new Date().toISOString()
    setData(response.opportunities, response.total)
    updateStats(response.opportunities)
    ElMessage.success(`扫描完成，发现 ${response.total} 个机会`)
  } catch (error) {
    console.error('Scan failed:', error)
    ElMessage.error('扫描失败')
  } finally {
    scanning.value = false
  }
}

// 排序
const handleSort = () => {
  handleScan()  // 使用 handleScan 而不是 fetchOpportunities
}

// 查看详情
const handleViewDetail = (opportunity: Opportunity) => {
  // TODO: 跳转到详情页或打开详情弹窗
  console.log('View detail:', opportunity)
  ElMessage.info(`查看 ${opportunity.symbolName} 详情`)
}

// 加入自选
const handleAddToWatchlist = async (opportunity: Opportunity) => {
  try {
    // TODO: 调用API加入自选
    ElMessage.success(`已将 ${opportunity.symbolName} 加入自选`)
  } catch (error) {
    ElMessage.error('加入自选失败')
  }
}

// 快速交易
const handleQuickTrade = async (opportunity: Opportunity) => {
  quickTradeDialogVisible.value = true
  quickTradeForm.symbol = opportunity.symbol
  quickTradeForm.symbolName = opportunity.symbolName
  quickTradeForm.price = 0 // 市价单
  quickTradeForm.quantity = 100
}

// 保存筛选条件
const handleSaveFilters = async () => {
  try {
    const { value: presetName } = await ElMessageBox.prompt('请输入预设名称', '保存筛选条件', {
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPattern: /\S+/,
      inputErrorMessage: '预设名称不能为空'
    })

    if (presetName) {
      const preset = {
        name: presetName,
        filters: JSON.parse(JSON.stringify(filters)),
        createdAt: new Date().toISOString()
      }

      // 保存到本地存储
      const savedPresets = JSON.parse(localStorage.getItem('opportunityPresets') || '[]')
      savedPresets.push(preset)
      localStorage.setItem('opportunityPresets', JSON.stringify(savedPresets))

      ElMessage.success('筛选条件已保存')
    }
  } catch {
    // 用户取消
  }
}

// 加载预设
const handleLoadPreset = () => {
  loadPresetDialogVisible.value = true
  loadPresets()
}

// 重置筛选条件
const handleResetFilters = () => {
  filters.technical = {
    rsiOversold: true,
    macdGoldenCross: true,
    bollingerBreakout: false,
    volumeSpike: false
  }
  filters.fundamental = {
    lowPE: true,
    highROE: true,
    highGrossMargin: false,
    lowDebtRatio: false
  }
  filters.sentiment = {
    mainForceInflow: true,
    northboundInflow: false,
    institutionalIncrease: false,
    marginIncrease: false
  }
  filters.strategyId = ''
  filters.scoreRange = [60, 100]
  filters.confidenceRange = [50, 100]
  filters.riskLevel = ''
  filters.industries = []
  handleScan()  // 使用 handleScan 而不是 fetchOpportunities
}

// 加载更多
const handleLoadMore = () => {
  changePage(currentPage.value + 1)
  handleScan()  // 使用 handleScan 而不是 fetchOpportunities，保持一致
}

// 获取星级评分
const getStarRating = (score: number): number => {
  return Math.round((score / 100) * 5)
}

// 获取评分颜色
const getScoreColor = (score: number): string => {
  if (score >= 80) return '#4caf50'
  if (score >= 60) return '#2196f3'
  if (score >= 40) return '#ff9800'
  return '#f44336'
}

// 获取风险等级类型
const getRiskLevelType = (level: string): 'success' | 'warning' | 'danger' => {
  const typeMap: Record<string, 'success' | 'warning' | 'danger'> = {
    low: 'success',
    medium: 'warning',
    high: 'danger'
  }
  return typeMap[level] || 'info'
}

// 获取风险等级文本
const getRiskLevelText = (level: string): string => {
  const textMap: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险'
  }
  return textMap[level] || level
}

// 获取原因标签类型
const getReasonTagType = (reason: string): 'success' | 'info' | 'warning' => {
  if (reason.includes('RSI') || reason.includes('MACD') || reason.includes('突破')) {
    return 'success'
  }
  if (reason.includes('PE') || reason.includes('ROE') || reason.includes('毛利')) {
    return 'info'
  }
  if (reason.includes('主力') || reason.includes('北向') || reason.includes('机构')) {
    return 'warning'
  }
  return 'info'
}

// 格式化相对时间
const formatRelativeTime = (time: string): string => {
  const now = new Date()
  const past = new Date(time)
  const diffMs = now.getTime() - past.getTime()
  const diffMins = Math.floor(diffMs / 60000)

  if (diffMins < 1) return '刚刚'
  if (diffMins < 60) return `${diffMins}分钟前`
  const diffHours = Math.floor(diffMins / 60)
  if (diffHours < 24) return `${diffHours}小时前`
  const diffDays = Math.floor(diffHours / 24)
  return `${diffDays}天前`
}

// 提交快速交易
const submitQuickTrade = async () => {
  if (quickTradeForm.quantity <= 0) {
    ElMessage.warning('请输入有效的数量')
    return
  }

  if (quickTradeForm.priceType === 'limit' && quickTradeForm.price <= 0) {
    ElMessage.warning('请输入有效的价格')
    return
  }

  quickTradeLoading.value = true

  try {
    const orderData: CreateOrderRequest = {
      symbol: quickTradeForm.symbol,
      type: quickTradeForm.direction,
      quantity: quickTradeForm.quantity,
      priceType: quickTradeForm.priceType,
      price: quickTradeForm.priceType === 'limit' ? quickTradeForm.price : undefined
    }

    await tradingApi.createOrder(orderData)
    ElMessage.success('订单已提交')
    quickTradeDialogVisible.value = false
  } catch (error) {
    console.error('提交订单失败:', error)
    ElMessage.error('订单提交失败')
  } finally {
    quickTradeLoading.value = false
  }
}

// 加载预设列表
const loadPresets = () => {
  const savedPresets = JSON.parse(localStorage.getItem('opportunityPresets') || '[]')
  presets.value = savedPresets
}

// 应用预设
const applyPreset = (preset: any) => {
  Object.assign(filters, preset.filters)
  loadPresetDialogVisible.value = false
  ElMessage.success(`已应用预设：${preset.name}`)
  handleScan()  // 使用 handleScan 而不是 fetchOpportunities
}

// 删除预设
const deletePreset = (index: number) => {
  ElMessageBox.confirm('确认删除该预设？', '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(() => {
    presets.value.splice(index, 1)
    localStorage.setItem('opportunityPresets', JSON.stringify(presets.value))
    ElMessage.success('预设已删除')
  }).catch(() => {
    // 用户取消
  })
}

// 初始化
onMounted(() => {
  loadStrategies()
  handleScan()  // 直接扫描，而不是 fetchOpportunities
})
</script>

<style scoped lang="scss">
.opportunity-radar {
  padding: 20px;

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;

    .page-title {
      font-size: 24px;
      font-weight: bold;
      color: #1f2937;
      margin: 0 0 8px 0;
    }

    .page-subtitle {
      font-size: 14px;
      color: #64748b;
      margin: 0;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 12px;

      .last-scan-time {
        font-size: 14px;
        color: #64748b;
      }
    }
  }

  .stats-cards {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;

    .stat-card {
      .stat-content {
        display: flex;
        align-items: center;
        gap: 16px;

        .stat-icon {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .stat-info {
          flex: 1;

          .stat-label {
            font-size: 14px;
            color: #64748b;
            margin-bottom: 4px;
          }

          .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #1f2937;
          }
        }
      }
    }
  }

  .filter-card {
    margin-bottom: 24px;

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .card-title {
        font-weight: bold;
        color: #1f2937;
      }

      .card-actions {
        display: flex;
        gap: 8px;
      }
    }

    .filter-grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 24px;
      margin-bottom: 24px;

      .filter-section {
        .section-title {
          font-size: 14px;
          font-weight: 500;
          color: #475569;
          margin-bottom: 12px;
        }

        .filter-options {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }
      }
    }

    .filter-advanced {
      padding-top: 24px;
      border-top: 1px solid #e2e8f0;
    }
  }

  .opportunities-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      .card-title {
        font-weight: bold;
        color: #1f2937;
      }

      .card-actions {
        display: flex;
        align-items: center;
        gap: 8px;

        .sort-label {
          font-size: 14px;
          color: #64748b;
        }
      }
    }

    .opportunities-list {
      min-height: 400px;

      .opportunity-card {
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 16px;
        cursor: pointer;
        transition: all 0.3s;

        &:hover {
          border-color: #3b82f6;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        }

        .opportunity-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 16px;

          .stock-info {
            .stock-main {
              display: flex;
              align-items: center;
              gap: 12px;

              .stock-code {
                font-size: 18px;
                font-weight: bold;
                color: #1f2937;
              }

              .stock-name {
                font-size: 16px;
                color: #475569;
              }
            }
          }

          .score-info {
            text-align: right;

            .score-stars {
              margin-bottom: 4px;
            }

            .score-value {
              font-size: 20px;
              font-weight: bold;
              color: #ff9800;
            }

            .score-label {
              font-size: 12px;
              color: #64748b;
            }
          }
        }

        .score-bars {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 16px;
          margin-bottom: 16px;

          .score-bar-item {
            .score-bar-label {
              font-size: 12px;
              color: #64748b;
              margin-bottom: 4px;
            }

            .score-bar-content {
              display: flex;
              align-items: center;
              gap: 8px;

              .score-bar-value {
                font-size: 14px;
                font-weight: bold;
                min-width: 30px;
                text-align: right;
              }
            }
          }
        }

        .opportunity-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 16px;
        }

        .opportunity-actions {
          display: flex;
          gap: 8px;

          .el-button {
            flex: 1;
          }
        }
      }

      .load-more {
        text-align: center;
        padding: 24px 0;
      }
    }
  }

  .empty-presets {
    padding: 40px 0;
  }

  .presets-list {
    max-height: 400px;
    overflow-y: auto;

    .preset-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 16px;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      margin-bottom: 12px;
      transition: all 0.3s;

      &:hover {
        border-color: #3b82f6;
        background: #f8fafc;
      }

      .preset-info {
        flex: 1;

        .preset-name {
          font-size: 16px;
          font-weight: 500;
          color: #1f2937;
          margin-bottom: 4px;
        }

        .preset-date {
          font-size: 12px;
          color: #64748b;
        }
      }

      .preset-actions {
        display: flex;
        gap: 8px;
      }
    }
  }
}

@media (max-width: 1200px) {
  .stats-cards {
    grid-template-columns: repeat(2, 1fr) !important;
  }

  .filter-grid {
    grid-template-columns: repeat(2, 1fr) !important;
  }
}

@media (max-width: 768px) {
  .stats-cards {
    grid-template-columns: 1fr !important;
  }

  .filter-grid {
    grid-template-columns: 1fr !important;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start !important;
    gap: 16px;
  }
}
</style>
