<template>
  <div class="pool-detail-page" v-loading="loading">
    <!-- 顶部信息 -->
    <el-page-header @back="router.push('/pools')">
      <template #content>
        <span>{{ pool.name }}</span>
        <el-tag
          :type="pool.pool_type === 'static' ? 'info' : 'success'"
          size="small"
          style="margin-left: 8px;"
        >
          {{ pool.pool_type === 'static' ? '静态池' : '动态池' }}
        </el-tag>
      </template>
      <template #extra>
        <el-button
          v-if="pool.pool_type === 'dynamic'"
          @click="handleRefresh"
          :loading="refreshing"
        >刷新池子</el-button>
        <el-button @click="handleSyncStockNames" :loading="syncingStockNames">同步股票名称</el-button>
        <el-button type="primary" @click="showValidateDialog = true">验证策略</el-button>
        <el-button @click="openEditDialog">编辑</el-button>
        <el-button type="danger" @click="handleDelete">删除</el-button>
      </template>
    </el-page-header>

    <!-- 池子信息 -->
    <el-descriptions :column="3" border style="margin-top: 24px;" v-if="pool.id">
      <el-descriptions-item label="描述">{{ pool.description || '—' }}</el-descriptions-item>
      <el-descriptions-item label="股票数量">{{ pool.symbols?.length || 0 }}</el-descriptions-item>
      <el-descriptions-item label="刷新周期">{{ pool.refresh_interval || '—' }}</el-descriptions-item>
      <el-descriptions-item label="上次刷新">{{ pool.last_refreshed_at || '—' }}</el-descriptions-item>
      <el-descriptions-item label="创建时间">{{ pool.created_at?.slice(0, 19) }}</el-descriptions-item>
    </el-descriptions>

    <!-- 筛选条件标签 -->
    <div v-if="pool.filter_template" style="margin-top: 16px;">
      <span style="color: var(--el-text-color-secondary); margin-right: 8px;">筛选条件:</span>

      <!-- 新格式：条件数组 -->
      <template v-if="pool.filter_template.conditions && pool.filter_template.conditions.length > 0">
        <el-tag
          v-for="(cond, i) in pool.filter_template.conditions"
          :key="i"
          type="primary"
          size="small"
          style="margin-right: 4px;"
        >
          {{ formatCondition(cond) }}
        </el-tag>
        <el-tag type="info" size="small">逻辑: {{ pool.filter_template.logic || 'AND' }}</el-tag>
      </template>

      <!-- 旧格式：布尔标签（向后兼容） -->
      <template v-else>
        <el-tag v-for="t in pool.filter_template?.technical || []" :key="t" size="small" style="margin-right: 4px;">{{ filterLabels[t] || t }}</el-tag>
        <el-tag v-for="f in pool.filter_template?.fundamental || []" :key="f" type="warning" size="small" style="margin-right: 4px;">{{ filterLabels[f] || f }}</el-tag>
      </template>

      <el-tag v-if="pool.filter_template?.min_score" type="info" size="small" style="margin-right: 4px;">最低分: {{ pool.filter_template.min_score }}</el-tag>
      <el-tag v-if="pool.filter_template?.top_n" type="info" size="small">Top {{ pool.filter_template.top_n }}</el-tag>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" style="margin-top: 24px;">
      <!-- 成员列表 Tab -->
      <el-tab-pane label="成员列表" name="members">
        <el-table :data="memberRows" stripe>
          <el-table-column prop="index" label="序号" width="80" />
          <el-table-column prop="symbol" label="股票代码" width="120" />
          <el-table-column prop="name" label="股票名称" width="120">
            <template #default="{ row }">
              {{ row.name || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="180">
            <template #default="{ row }">
              {{ row.description || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="buy_point" label="关注买点" width="120">
            <template #default="{ row }">
              {{ row.buy_point || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="sell_point" label="关注卖点" width="120">
            <template #default="{ row }">
              {{ row.sell_point || '—' }}
            </template>
          </el-table-column>
          <el-table-column prop="tags" label="标签" width="150">
            <template #default="{ row }">
              <el-tag v-for="tag in row.tags || []" :key="tag" size="small" style="margin-right: 4px;">{{ tag }}</el-tag>
              <span v-if="!row.tags || row.tags.length === 0">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openMemberEditDialog(row)">编辑</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 验证结果 Tab -->
      <el-tab-pane label="验证结果" name="validation">
        <template v-if="!validation">
          <el-empty description="尚未执行策略验证">
            <el-button type="primary" @click="showValidateDialog = true">立即验证</el-button>
          </el-empty>
        </template>

        <template v-else>
          <!-- 验证摘要 -->
          <el-descriptions :column="4" border>
            <el-descriptions-item label="验证时间">{{ validation.validated_at?.slice(0, 19) }}</el-descriptions-item>
            <el-descriptions-item label="测试策略数">{{ validation.strategies_tested }}</el-descriptions-item>
            <el-descriptions-item label="池内股票数">{{ validation.stocks_in_pool }}</el-descriptions-item>
            <el-descriptions-item label="验证期间">{{ validation.period?.start }} ~ {{ validation.period?.end }}</el-descriptions-item>
          </el-descriptions>

          <!-- 最优策略 -->
          <el-card v-if="validation.best_strategy" class="best-strategy-card" style="margin-top: 16px;">
            <div class="best-strategy-header">🏆 最优策略: {{ validation.best_strategy.name }}</div>
            <el-row :gutter="24" style="margin-top: 12px;">
              <el-col :span="6">
                <div class="metric-value highlight">{{ validation.best_strategy.score }}</div>
                <div class="metric-label">综合评分</div>
              </el-col>
              <el-col :span="6">
                <div class="metric-value">{{ validation.best_strategy.avg_return }}%</div>
                <div class="metric-label">平均收益</div>
              </el-col>
              <el-col :span="6">
                <div class="metric-value">{{ validation.best_strategy.avg_win_rate }}%</div>
                <div class="metric-label">平均胜率</div>
              </el-col>
              <el-col :span="6">
                <div class="metric-value">{{ validation.best_strategy.avg_sharpe }}</div>
                <div class="metric-label">平均夏普</div>
              </el-col>
            </el-row>
          </el-card>

          <!-- 策略排名 -->
          <h4 style="margin-top: 24px;">📈 策略排名</h4>
          <el-table :data="validation.rankings || []" stripe style="margin-top: 8px;">
            <el-table-column type="index" label="排名" width="60" />
            <el-table-column prop="name" label="策略名称" />
            <el-table-column prop="score" label="综合评分" width="150">
              <template #default="{ row }">
                <el-progress :percentage="row.score" :stroke-width="16" :text-inside="true" />
              </template>
            </el-table-column>
            <el-table-column prop="avg_return" label="平均收益%" width="100">
              <template #default="{ row }">
                <span :style="{ color: row.avg_return >= 0 ? '#67C23A' : '#F56C6C' }">{{ row.avg_return }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="avg_win_rate" label="平均胜率%" width="100" />
            <el-table-column prop="avg_sharpe" label="平均夏普" width="100" />
            <el-table-column prop="avg_drawdown" label="平均回撤%" width="100">
              <template #default="{ row }">
                <span style="color: #F56C6C;">{{ row.avg_drawdown }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="stocks_tested" label="测试股票数" width="100" />
          </el-table>

          <!-- 推荐组合 -->
          <h4 style="margin-top: 24px;">💡 推荐组合</h4>
          <el-table :data="recommendedPairRows" stripe style="margin-top: 8px;">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="symbol" label="股票代码" />
            <el-table-column prop="name" label="股票名称">
              <template #default="{ row }">
                {{ row.name || '—' }}
              </template>
            </el-table-column>
            <el-table-column prop="expected_return" label="预期收益%" width="120">
              <template #default="{ row }">
                <span :style="{ color: row.expected_return >= 0 ? '#67C23A' : '#F56C6C' }">{{ row.expected_return }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="win_rate" label="胜率%" width="100" />
            <el-table-column prop="sharpe" label="夏普比率" width="100" />
          </el-table>
        </template>
      </el-tab-pane>

      <!-- 买卖信号 Tab -->
      <el-tab-pane name="signals">
        <template #label>
          <span>
            买卖信号
            <el-badge
              v-if="signalData?.summary?.buy > 0"
              :value="signalData.summary.buy"
              type="success"
              style="margin-left: 4px;"
            />
          </span>
        </template>

        <!-- 扫描控制 -->
        <el-card style="margin-bottom: 16px;">
          <el-row :gutter="24" align="middle">
            <el-col :span="12">
              <div v-if="signalData?.scanned_at">
                <span style="color: #909399;">扫描时间：</span>
                <span>{{ formatDateTime(signalData.scanned_at) }}</span>
              </div>
              <div v-else style="color: #909399;">
                尚未扫描信号
              </div>
            </el-col>
            <el-col :span="12" style="text-align: right;">
              <el-button
                type="primary"
                @click="handleScanSignals"
                :loading="scanningSignals"
              >
                <el-icon><Refresh /></el-icon>
                {{ signalData ? '重新扫描' : '立即扫描' }}
              </el-button>
            </el-col>
          </el-row>
        </el-card>

        <!-- 信号统计 -->
        <el-row :gutter="16" style="margin-bottom: 16px;">
          <el-col :span="6">
            <el-card class="stat-card stat-success">
              <div class="stat-value">{{ signalData?.summary?.buy || 0 }}</div>
              <div class="stat-label">✅ 买入信号</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="stat-card stat-danger">
              <div class="stat-value">{{ signalData?.summary?.sell || 0 }}</div>
              <div class="stat-label">❌ 卖出信号</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="stat-card">
              <div class="stat-value">{{ signalData?.summary?.hold || 0 }}</div>
              <div class="stat-label">⏸️ 观望</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card class="stat-card stat-warning">
              <div class="stat-value">{{ signalData?.summary?.error || 0 }}</div>
              <div class="stat-label">⚠️ 失败</div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 买入信号列表 -->
        <el-card v-if="signalData?.buy_signals?.length > 0">
          <template #header>
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <span>🎯 买入推荐清单</span>
              <el-button
                type="primary"
                size="small"
                @click="handleExportSignals"
              >
                <el-icon><Download /></el-icon>
                导出清单
              </el-button>
            </div>
          </template>

          <el-table
            :data="buySignalRows"
            stripe
            :row-class-name="getSignalRowClassName"
          >
            <el-table-column type="index" label="#" width="50" />

            <el-table-column prop="symbol" label="股票代码" width="120">
              <template #default="{ row }">
                <el-button
                  type="primary"
                  link
                  @click="handleViewStock(row.symbol)"
                >
                  {{ row.symbol }}
                </el-button>
              </template>
            </el-table-column>

            <el-table-column prop="name" label="股票名称" width="120">
              <template #default="{ row }">
                {{ row.name || '—' }}
              </template>
            </el-table-column>

            <el-table-column prop="current_price" label="当前价" width="100">
              <template #default="{ row }">
                <span style="font-weight: bold; color: #303133;">
                  ¥{{ row.current_price.toFixed(2) }}
                </span>
              </template>
            </el-table-column>

            <el-table-column label="止损价" width="110">
              <template #default="{ row }">
                <div style="color: #F56C6C; font-weight: bold;">
                  ¥{{ row.trade_params.stop_loss.toFixed(2) }}
                  <div style="font-size: 12px; color: #909399;">(-3%)</div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="止盈价" width="110">
              <template #default="{ row }">
                <div style="color: #67C23A; font-weight: bold;">
                  ¥{{ row.trade_params.take_profit.toFixed(2) }}
                  <div style="font-size: 12px; color: #909399;">(+8%)</div>
                </div>
              </template>
            </el-table-column>

            <el-table-column label="建议仓位" width="100" align="center">
              <template #default="{ row }">
                <el-tag type="info">
                  {{ (row.trade_params.suggested_position * 100).toFixed(0) }}%
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="买入理由" min-width="250">
              <template #default="{ row }">
                <el-tag
                  v-for="(reason, index) in row.reasons"
                  :key="index"
                  size="small"
                  type="success"
                  style="margin-right: 4px; margin-bottom: 4px;"
                >
                  {{ reason }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="技术指标" width="150">
              <template #default="{ row }">
                <div style="font-size: 12px; color: #606266; line-height: 1.6;">
                  <div v-if="row.indicators?.rsi || row.indicators?.rsi14">
                    RSI: {{ (row.indicators.rsi || row.indicators.rsi14).toFixed(1) }}
                  </div>
                  <div v-if="row.indicators?.macd">
                    MACD: {{ row.indicators.macd.toFixed(3) }}
                  </div>
                  <div v-if="row.indicators?.volume_ratio">
                    量比: {{ row.indicators.volume_ratio.toFixed(2) }}
                  </div>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="trade_date" label="交易日期" width="110" />
          </el-table>
        </el-card>

        <!-- 无信号提示 -->
        <el-empty
          v-else-if="signalData && signalData.buy_signals?.length === 0"
          description="当前没有买入信号"
          style="margin-top: 40px;"
        >
          <el-button type="primary" @click="handleScanSignals">
            重新扫描
          </el-button>
        </el-empty>

        <!-- 未扫描提示 -->
        <el-empty
          v-else
          description="尚未扫描信号"
          style="margin-top: 40px;"
        >
          <el-button type="primary" @click="handleScanSignals">
            立即扫描
          </el-button>
        </el-empty>
      </el-tab-pane>
    </el-tabs>

    <!-- 验证策略弹窗 -->
    <el-dialog v-model="showValidateDialog" title="验证策略" width="500px">
      <el-form :model="validateForm" label-width="80px">
        <el-form-item label="策略选择">
          <el-input v-model="validateForm.strategyIdsText" placeholder="策略ID，逗号分隔，留空=全部活跃策略" />
        </el-form-item>
        <el-form-item label="起始日期">
          <el-date-picker v-model="validateForm.startDate" type="date" value-format="YYYY-MM-DD" placeholder="默认近6个月" style="width: 100%;" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="validateForm.endDate" type="date" value-format="YYYY-MM-DD" placeholder="默认今天" style="width: 100%;" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showValidateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleValidate">开始验证</el-button>
      </template>
    </el-dialog>

    <!-- 编辑弹窗 -->
    <el-dialog v-model="showEditDialog" title="编辑池子" width="500px">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="editForm.name" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 编辑成员弹窗 -->
    <el-dialog v-model="showMemberEditDialog" title="编辑股票信息" width="500px">
      <el-form :model="memberEditForm" label-width="80px">
        <el-form-item label="股票代码">
          <el-input v-model="memberEditForm.symbol" disabled />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="memberEditForm.name" disabled />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="memberEditForm.description" type="textarea" :rows="3" placeholder="例如：高ROE成长股，基本面优秀" />
        </el-form-item>
        <el-form-item label="关注买点">
          <el-input v-model="memberEditForm.buy_point" placeholder="例如：25.5-26.0 或 突破30日均线" />
        </el-form-item>
        <el-form-item label="关注卖点">
          <el-input v-model="memberEditForm.sell_point" placeholder="例如：32.0 或 跌破支撑位28.5" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="memberEditForm.tags" multiple filterable allow-create placeholder="选择或输入标签" style="width: 100%;">
            <el-option v-for="tag in commonTags" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showMemberEditDialog = false">取消</el-button>
        <el-button type="primary" :loading="submittingMember" @click="handleMemberEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading, ElNotification } from 'element-plus'
import { poolApi } from '@/services/api'

const router = useRouter()
const route = useRoute()
const poolId = computed(() => Number(route.params.id))

const loading = ref(false)
const refreshing = ref(false)
const syncingStockNames = ref(false)
const submitting = ref(false)
const submittingMember = ref(false)
const pool = ref<any>({})
const activeTab = ref('members')

const validation = computed(() => pool.value.last_validation)
const signalData = computed(() => pool.value.last_signal_scan)
const scanningSignals = ref(false)
const stockNameBySymbol = computed(() => {
  const names: Record<string, string> = {}
  const members = Array.isArray(pool.value.members) ? pool.value.members : []

  members.forEach((member: { symbol?: string; name?: string; stock_name?: string; stockName?: string }) => {
    const symbol = member.symbol
    const name = member.name || member.stock_name || member.stockName
    if (symbol && name) {
      names[symbol] = name
    }
  })

  return names
})
const memberRows = computed(() => {
  const members = Array.isArray(pool.value.members) && pool.value.members.length > 0
    ? pool.value.members
    : (pool.value.symbols || [])

  return members.map((member: string | { symbol?: string; name?: string; stock_name?: string; stockName?: string; description?: string; buy_point?: string; sell_point?: string; tags?: string[] }, i: number) => {
    if (typeof member === 'string') {
      return {
        index: i + 1,
        symbol: member,
        name: undefined,
        description: undefined,
        buy_point: undefined,
        sell_point: undefined,
        tags: []
      }
    }

    return {
      index: i + 1,
      symbol: member.symbol || '',
      name: member.name || member.stock_name || member.stockName,
      description: member.description,
      buy_point: member.buy_point,
      sell_point: member.sell_point,
      tags: member.tags || []
    }
  })
})
const recommendedPairRows = computed(() =>
  (validation.value?.recommended_pairs || []).map((pair: { symbol?: string; [key: string]: any }) => ({
    ...pair,
    name: pair.name || (pair.symbol ? stockNameBySymbol.value[pair.symbol] : undefined),
  }))
)
const buySignalRows = computed(() =>
  (signalData.value?.buy_signals || []).map((signal: { symbol?: string; name?: string; [key: string]: any }) => ({
    ...signal,
    name: signal.name || (signal.symbol ? stockNameBySymbol.value[signal.symbol] : undefined),
  }))
)

const filterLabels: Record<string, string> = {
  rsi_oversold: 'RSI超卖',
  macd_golden_cross: 'MACD金叉',
  bollinger_breakout: '布林突破',
  volume_surge: '放量突破',
  pe_low: '低PE',
  roe_high: '高ROE',
  gross_margin_high: '高毛利',
  debt_ratio_low: '低负债',
}

const fieldOptions = [
  { value: 'roe', label: 'ROE' },
  { value: 'pe', label: 'PE' },
  { value: 'pb', label: 'PB' },
  { value: 'gross_margin', label: '毛利率' },
  { value: 'debt_ratio', label: '负债率' },
  { value: 'net_profit_growth', label: '净利润增长' },
  { value: 'market_cap', label: '总市值' },
  { value: 'circulating_mv', label: '流通市值' },
  { value: 'rsi', label: 'RSI' },
  { value: 'volume_ratio_5d', label: '5日量比' }
]

const formatCondition = (cond: any) => {
  const fieldLabel = fieldOptions.find(f => f.value === cond.field)?.label || cond.field
  const operatorSymbols: Record<string, string> = {
    '>=': '≥', '<=': '≤', '>': '>', '<': '<', '==': '=', '!=': '≠'
  }
  const operatorSymbol = operatorSymbols[cond.operator] || cond.operator
  return `${fieldLabel} ${operatorSymbol} ${cond.value}`
}

// Validate dialog
const showValidateDialog = ref(false)
const validateForm = ref({
  strategyIdsText: '',
  startDate: '',
  endDate: '',
})

// Edit dialog
const showEditDialog = ref(false)
const editForm = ref({ name: '', description: '' })

// Member edit dialog
const showMemberEditDialog = ref(false)
const memberEditForm = ref({
  symbol: '',
  name: '',
  description: '',
  buy_point: '',
  sell_point: '',
  tags: [] as string[]
})

// Common tags for selection
const commonTags = [
  '价值股', '成长股', '周期股', '防御股',
  '高股息', '低估值', '高ROE', '高毛利',
  '技术突破', '基本面优秀', '行业龙头', '概念股'
]

const fetchPool = async () => {
  loading.value = true
  try {
    pool.value = await poolApi.getById(poolId.value)
  } catch {
    ElMessage.error('获取池子详情失败')
  } finally {
    loading.value = false
  }
}

const handleRefresh = async () => {
  refreshing.value = true
  try {
    await poolApi.refresh(poolId.value)
    ElMessage.success('刷新成功')
    await fetchPool()
  } catch {
    ElMessage.error('刷新失败')
  } finally {
    refreshing.value = false
  }
}

const handleSyncStockNames = async () => {
  syncingStockNames.value = true
  try {
    await poolApi.syncStockNames(poolId.value)
    ElMessage.success('股票名称同步成功')
    await fetchPool()
  } catch {
    ElMessage.error('股票名称同步失败')
  } finally {
    syncingStockNames.value = false
  }
}

const handleValidate = async () => {
  showValidateDialog.value = false
  const loadingInstance = ElLoading.service({ fullscreen: true, text: '正在执行策略验证，可能需要几分钟...' })
  try {
    const strategyIds = validateForm.value.strategyIdsText
      ? validateForm.value.strategyIdsText.split(/[,，]/).map(s => Number(s.trim())).filter(Boolean)
      : undefined
    await poolApi.validate(poolId.value, {
      strategyIds,
      startDate: validateForm.value.startDate || undefined,
      endDate: validateForm.value.endDate || undefined,
    })
    ElMessage.success('策略验证完成')
    await fetchPool()
    activeTab.value = 'validation'
  } catch {
    ElMessage.error('策略验证失败')
  } finally {
    loadingInstance.close()
  }
}

const openEditDialog = () => {
  editForm.value = {
    name: pool.value.name || '',
    description: pool.value.description || '',
  }
  showEditDialog.value = true
}

const handleEdit = async () => {
  submitting.value = true
  try {
    await poolApi.update(poolId.value, {
      name: editForm.value.name || undefined,
      description: editForm.value.description || undefined,
    })
    ElMessage.success('更新成功')
    showEditDialog.value = false
    await fetchPool()
  } catch {
    ElMessage.error('更新失败')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async () => {
  try {
    await ElMessageBox.confirm(`确定删除股票池「${pool.value.name}」？`, '提示', { type: 'warning' })
    await poolApi.delete(poolId.value)
    ElMessage.success('删除成功')
    router.push('/pools')
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

const openMemberEditDialog = (row: any) => {
  memberEditForm.value = {
    symbol: row.symbol,
    name: row.name || '',
    description: row.description || '',
    buy_point: row.buy_point || '',
    sell_point: row.sell_point || '',
    tags: row.tags || []
  }
  showMemberEditDialog.value = true
}

const handleMemberEdit = async () => {
  submittingMember.value = true
  try {
    await poolApi.updateMember(poolId.value, memberEditForm.value.symbol, {
      description: memberEditForm.value.description || undefined,
      buyPoint: memberEditForm.value.buy_point || undefined,
      sellPoint: memberEditForm.value.sell_point || undefined,
      tags: memberEditForm.value.tags
    })
    ElMessage.success('更新成功')
    showMemberEditDialog.value = false
    await fetchPool()
  } catch {
    ElMessage.error('更新失败')
  } finally {
    submittingMember.value = false
  }
}

// 信号扫描相关方法
const handleScanSignals = async () => {
  scanningSignals.value = true
  try {
    const response = await poolApi.scanSignals(poolId.value, { strategy_id: 272 })
    const scanResult = response?.data || response

    if (scanResult?.summary) {
      // 直接更新 pool.value.last_signal_scan，触发 signalData 的响应式更新
      pool.value.last_signal_scan = scanResult

      ElMessage.success('信号扫描完成')

      const buyCount = scanResult.summary.buy
      if (buyCount > 0) {
        ElNotification({
          title: '发现买入机会！',
          message: `${buyCount}只股票有买入信号`,
          type: 'success',
          duration: 5000
        })
      }
    }
  } catch (error) {
    ElMessage.error('扫描失败')
  } finally {
    scanningSignals.value = false
  }
}

const handleExportSignals = () => {
  if (!signalData.value?.buy_signals) return

  const csv = generateCSV(signalData.value.buy_signals)
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)

  link.href = url
  link.download = `买入清单_${pool.value.name}_${new Date().toISOString().slice(0, 10)}.csv`
  link.click()

  URL.revokeObjectURL(url)
  ElMessage.success('导出成功')
}

const generateCSV = (signals: any[]) => {
  const headers = ['股票代码', '股票名称', '当前价', '止损价', '止盈价', '建议仓位', '买入理由', '交易日期']
  const rows = signals.map(s => [
    s.symbol,
    s.name || stockNameBySymbol.value[s.symbol] || '',
    s.current_price.toFixed(2),
    s.trade_params.stop_loss.toFixed(2),
    s.trade_params.take_profit.toFixed(2),
    `${(s.trade_params.suggested_position * 100).toFixed(0)}%`,
    s.reasons.join('; '),
    s.trade_date
  ])

  return [headers, ...rows].map(row => row.join(',')).join('\n')
}

const handleViewStock = (symbol: string) => {
  router.push(`/stocks/${symbol}`)
}

const getSignalRowClassName = ({ rowIndex }: { rowIndex: number }) => {
  return rowIndex === 0 ? 'highlight-row' : ''
}

const formatDateTime = (dateTime: string) => {
  if (!dateTime) return '-'
  return new Date(dateTime).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

onMounted(() => {
  fetchPool()
})
</script>

<style scoped>
.pool-detail-page {
  padding: 24px;
}
.best-strategy-card {
  background: linear-gradient(135deg, #f6f8fc 0%, #eef2f9 100%);
}
.best-strategy-header {
  font-size: 18px;
  font-weight: bold;
}
.metric-value {
  font-size: 24px;
  font-weight: bold;
  text-align: center;
}
.metric-value.highlight {
  color: var(--el-color-primary);
  font-size: 32px;
}
.metric-label {
  text-align: center;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

/* 买卖信号相关样式 */
.stat-card {
  text-align: center;
  padding: 20px;
  border-radius: 8px;
}

.stat-card .stat-value {
  font-size: 32px;
  font-weight: bold;
  margin-bottom: 8px;
}

.stat-card .stat-label {
  font-size: 14px;
  color: #606266;
}

.stat-card.stat-success {
  background: linear-gradient(135deg, #67C23A 0%, #85CE61 100%);
  color: white;
}

.stat-card.stat-success .stat-label {
  color: rgba(255, 255, 255, 0.9);
}

.stat-card.stat-danger {
  background: linear-gradient(135deg, #F56C6C 0%, #F78989 100%);
  color: white;
}

.stat-card.stat-danger .stat-label {
  color: rgba(255, 255, 255, 0.9);
}

.stat-card.stat-warning {
  background: linear-gradient(135deg, #E6A23C 0%, #EBB563 100%);
  color: white;
}

.stat-card.stat-warning .stat-label {
  color: rgba(255, 255, 255, 0.9);
}

.highlight-row {
  background-color: #FFF7E6 !important;
}

.highlight-row:hover {
  background-color: #FFE7BA !important;
}

</style>
