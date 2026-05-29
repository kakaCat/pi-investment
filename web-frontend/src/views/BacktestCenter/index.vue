<template>
  <div class="backtest-center">
    <div class="grid grid-cols-3 gap-4">
      <!-- 左侧：回测配置表单 -->
      <div class="backtest-form">
        <el-card>
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold">新建回测</span>
              <el-button text @click="handleReset">重置</el-button>
            </div>
          </template>

          <el-form :model="backtestForm" :rules="formRules" ref="formRef" label-position="top">
            <el-form-item label="策略" prop="strategy">
              <el-select
                v-model="backtestForm.strategy"
                placeholder="选择策略"
                class="w-full"
                :loading="loadingStrategies"
              >
                <el-option-group v-if="myIndicators.length > 0" label="我的指标">
                  <el-option
                    v-for="indicator in myIndicators"
                    :key="indicator.id"
                    :label="indicator.name"
                    :value="`indicator:${indicator.id}`"
                  />
                </el-option-group>
                <el-option label="MA 双均线" value="ma_cross" />
                <el-option label="RSI 反转" value="rsi_reversal" />
                <el-option label="MACD 金叉" value="macd_golden" />
                <el-option label="布林带突破" value="boll_breakout" />
                <el-option label="KDJ 超买超卖" value="kdj_overbought" />
                <el-option label="PE均值回归" value="pe_mean_reversion" />
                <el-option label="PB均值回归" value="pb_mean_reversion" />
              </el-select>
            </el-form-item>

            <el-form-item label="股票代码" prop="symbol">
              <el-autocomplete
                v-model="backtestForm.symbol"
                :fetch-suggestions="searchStocks"
                placeholder="如 600519.SH"
                class="w-full"
                @select="handleStockSelect"
              >
                <template #default="{ item }">
                  <div class="flex items-center justify-between">
                    <span>{{ item.symbol }}</span>
                    <span class="text-gray-400 text-sm">{{ item.name }}</span>
                  </div>
                </template>
              </el-autocomplete>
            </el-form-item>

            <el-form-item label="时间范围" required>
              <el-row :gutter="8">
                <el-col :span="12">
                  <el-form-item prop="startDate">
                    <el-date-picker
                      v-model="backtestForm.startDate"
                      type="date"
                      placeholder="开始日期"
                      class="w-full"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="12">
                  <el-form-item prop="endDate">
                    <el-date-picker
                      v-model="backtestForm.endDate"
                      type="date"
                      placeholder="结束日期"
                      class="w-full"
                    />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form-item>

            <el-form-item label="初始资金" prop="initialCapital">
              <el-input-number
                v-model="backtestForm.initialCapital"
                :min="10000"
                :max="100000000"
                :step="10000"
                class="w-full"
              />
            </el-form-item>

            <el-form-item label="手续费率 (%)" prop="commission">
              <el-input-number
                v-model="backtestForm.commission"
                :min="0"
                :max="1"
                :step="0.01"
                :precision="3"
                class="w-full"
              />
            </el-form-item>

            <el-form-item label="滑点 (%)" prop="slippage">
              <el-input-number
                v-model="backtestForm.slippage"
                :min="0"
                :max="1"
                :step="0.01"
                :precision="3"
                class="w-full"
              />
            </el-form-item>

            <!-- 策略参数 -->
            <el-divider content-position="left">策略参数</el-divider>

            <el-form-item label="快线周期" prop="fastPeriod" v-if="backtestForm.strategy === 'ma_cross'">
              <el-input-number v-model="backtestForm.fastPeriod" :min="1" :max="100" class="w-full" />
            </el-form-item>

            <el-form-item label="慢线周期" prop="slowPeriod" v-if="backtestForm.strategy === 'ma_cross'">
              <el-input-number v-model="backtestForm.slowPeriod" :min="1" :max="200" class="w-full" />
            </el-form-item>

            <el-form-item label="RSI周期" prop="rsiPeriod" v-if="backtestForm.strategy === 'rsi_reversal'">
              <el-input-number v-model="backtestForm.rsiPeriod" :min="5" :max="50" class="w-full" />
            </el-form-item>

            <!-- PE均值回归参数 -->
            <template v-if="backtestForm.strategy === 'pe_mean_reversion'">
              <el-form-item label="PE重仓买入线">
                <el-input-number v-model="backtestForm.peHeavyBuy" :min="5" :max="30" :step="0.5" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PE ≤ 此值 → 重仓买入（60%仓位）</span>
              </el-form-item>
              <el-form-item label="PE分批买入线">
                <el-input-number v-model="backtestForm.peBatchBuy" :min="5" :max="30" :step="0.5" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PE ≤ 此值 → 分批买入（40%仓位）</span>
              </el-form-item>
              <el-form-item label="PE减仓线">
                <el-input-number v-model="backtestForm.peReduce" :min="5" :max="50" :step="0.5" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PE ≥ 此值 → 减仓至10%</span>
              </el-form-item>
              <el-form-item label="PE清仓线">
                <el-input-number v-model="backtestForm.peLiquidate" :min="5" :max="50" :step="0.5" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PE ≥ 此值 → 清仓</span>
              </el-form-item>
              <el-form-item label="EPS起点（估算）">
                <el-input-number v-model="backtestForm.epsStart" :min="0.1" :max="10" :step="0.01" :precision="2" class="w-full" />
                <span class="text-xs text-gray-400">回测起始日EPS_TTM估算值</span>
              </el-form-item>
              <el-form-item label="EPS终点（估算）">
                <el-input-number v-model="backtestForm.epsEnd" :min="0.1" :max="10" :step="0.01" :precision="2" class="w-full" />
                <span class="text-xs text-gray-400">回测结束日EPS_TTM估算值</span>
              </el-form-item>
              <el-form-item label="止损比例(%)">
                <el-input-number v-model="backtestForm.stopLossPct" :min="1" :max="30" :step="1" class="w-full" />
              </el-form-item>
              <el-form-item label="止盈比例(%)">
                <el-input-number v-model="backtestForm.takeProfitPct" :min="5" :max="100" :step="5" class="w-full" />
              </el-form-item>
              <el-form-item label="年化股息率(%)">
                <el-input-number v-model="backtestForm.dividendYield" :min="0" :max="10" :step="0.1" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">长江电力约3.5%，模拟分红现金流入</span>
              </el-form-item>
            </template>

            <template v-if="backtestForm.strategy === 'pb_mean_reversion'">
              <el-form-item label="PB重仓买入线">
                <el-input-number v-model="backtestForm.pbHeavyBuy" :min="0.5" :max="5" :step="0.1" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PB ≤ 此值 → 重仓买入（60%仓位）</span>
              </el-form-item>
              <el-form-item label="PB分批买入线">
                <el-input-number v-model="backtestForm.pbBatchBuy" :min="0.5" :max="5" :step="0.1" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PB ≤ 此值 → 分批买入（40%仓位）</span>
              </el-form-item>
              <el-form-item label="PB减仓线">
                <el-input-number v-model="backtestForm.pbReduce" :min="1" :max="10" :step="0.5" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PB ≥ 此值 → 减仓至10%</span>
              </el-form-item>
              <el-form-item label="PB清仓线">
                <el-input-number v-model="backtestForm.pbLiquidate" :min="1" :max="10" :step="0.5" :precision="1" class="w-full" />
                <span class="text-xs text-gray-400">PB ≥ 此值 → 清仓</span>
              </el-form-item>
              <el-form-item label="ROE均值（估算PB用）">
                <el-input-number v-model="backtestForm.roeMean" :min="0.05" :max="0.60" :step="0.01" :precision="2" class="w-full" />
                <span class="text-xs text-gray-400">紫金矿业约0.35（近3年ROE 33~41%）</span>
              </el-form-item>
              <el-form-item label="EPS起点（估算）">
                <el-input-number v-model="backtestForm.epsStart" :min="0.1" :max="10" :step="0.01" :precision="2" class="w-full" />
                <span class="text-xs text-gray-400">回测起始日EPS_TTM估算值</span>
              </el-form-item>
              <el-form-item label="EPS终点（估算）">
                <el-input-number v-model="backtestForm.epsEnd" :min="0.1" :max="10" :step="0.01" :precision="2" class="w-full" />
                <span class="text-xs text-gray-400">回测结束日EPS_TTM估算值</span>
              </el-form-item>
              <el-form-item label="止损比例(%)">
                <el-input-number v-model="backtestForm.stopLossPct" :min="1" :max="30" :step="1" class="w-full" />
              </el-form-item>
              <el-form-item label="止盈比例(%)">
                <el-input-number v-model="backtestForm.takeProfitPct" :min="5" :max="100" :step="5" class="w-full" />
              </el-form-item>
            </template>

            <el-form-item>
              <el-button type="primary" @click="handleStartBacktest" :loading="loading" class="w-full">
                开始回测
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <!-- 快速交易面板 -->
        <el-card class="mt-4">
          <template #header>
            <span class="font-semibold">快速交易</span>
          </template>

          <el-form :model="tradeForm" label-position="top" size="small">
            <el-form-item label="股票代码">
              <el-autocomplete
                v-model="tradeForm.symbol"
                :fetch-suggestions="searchStocks"
                placeholder="如 600519.SH"
                class="w-full"
              />
            </el-form-item>

            <el-form-item label="交易方向">
              <el-radio-group v-model="tradeForm.direction" class="w-full">
                <el-radio-button label="buy" class="flex-1">买入</el-radio-button>
                <el-radio-button label="sell" class="flex-1">卖出</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="价格类型">
              <el-radio-group v-model="tradeForm.priceType" class="w-full">
                <el-radio-button label="market" class="flex-1">市价</el-radio-button>
                <el-radio-button label="limit" class="flex-1">限价</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <el-form-item label="价格" v-if="tradeForm.priceType === 'limit'">
              <el-input-number v-model="tradeForm.price" :min="0" :step="0.01" :precision="2" class="w-full" />
            </el-form-item>

            <el-form-item label="数量">
              <el-input-number v-model="tradeForm.quantity" :min="100" :step="100" class="w-full" />
            </el-form-item>

            <el-form-item>
              <el-button
                :type="tradeForm.direction === 'buy' ? 'danger' : 'success'"
                @click="handleQuickTrade"
                class="w-full"
              >
                {{ tradeForm.direction === 'buy' ? '买入' : '卖出' }}
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </div>

      <!-- 右侧：回测结果 -->
      <div class="col-span-2">
        <el-card v-if="backtestResult">
          <template #header>
            <div class="flex items-center justify-between">
              <span class="font-semibold">回测结果</span>
              <div class="flex items-center gap-2">
                <el-button size="small" @click="handleExportResult">导出报告</el-button>
                <el-button size="small" @click="handleSaveStrategy">保存策略</el-button>
              </div>
            </div>
          </template>

          <!-- 关键指标卡片 -->
          <div class="grid grid-cols-4 gap-3 mb-4">
            <div class="metric-card">
              <div class="metric-label">最终资金</div>
              <div class="metric-value">¥{{ formatPrice(backtestResult.finalCapital) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">总收益率</div>
              <div :class="['metric-value', backtestResult.totalReturn >= 0 ? 'text-up' : 'text-down']">
                {{ formatBacktestPercent(backtestResult.totalReturn) }}
              </div>
            </div>
            <div class="metric-card">
              <div class="metric-label">年化收益</div>
              <div :class="['metric-value', backtestResult.annualReturn >= 0 ? 'text-up' : 'text-down']">
                {{ formatBacktestPercent(backtestResult.annualReturn) }}
              </div>
            </div>
            <div class="metric-card">
              <div class="metric-label">最大回撤</div>
              <div class="metric-value text-down">{{ formatBacktestPercent(backtestResult.maxDrawdown, false) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">夏普比率</div>
              <div class="metric-value">{{ backtestResult.sharpeRatio.toFixed(2) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">胜率</div>
              <div class="metric-value">{{ formatBacktestPercent(backtestResult.winRate, false) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">盈亏比</div>
              <div class="metric-value">{{ backtestResult.profitLossRatio.toFixed(2) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">交易次数</div>
              <div class="metric-value">{{ backtestResult.totalTrades }}</div>
            </div>
          </div>

          <!-- 资产权益曲线图 -->
          <div class="chart-container mb-4">
            <div ref="equityChartRef" style="height: 300px"></div>
          </div>

          <!-- Tab切换 -->
          <el-tabs v-model="resultTab">
            <el-tab-pane label="交易记录" name="trades">
              <el-table :data="backtestResult.trades" stripe max-height="400">
                <el-table-column prop="date" label="日期" width="120">
                  <template #default="{ row }">
                    {{ formatDate(row.date) }}
                  </template>
                </el-table-column>
                <el-table-column prop="type" label="类型" width="80">
                  <template #default="{ row }">
                    <el-tag :type="row.type === 'BUY' ? 'danger' : 'success'" size="small">
                      {{ row.type }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="price" label="价格" width="100">
                  <template #default="{ row }">
                    ¥{{ formatPrice(row.price) }}
                  </template>
                </el-table-column>
                <el-table-column prop="quantity" label="数量" width="100" />
                <el-table-column prop="amount" label="金额" width="120">
                  <template #default="{ row }">
                    ¥{{ formatPrice(row.amount) }}
                  </template>
                </el-table-column>
                <el-table-column prop="commission" label="手续费" width="100">
                  <template #default="{ row }">
                    ¥{{ formatPrice(row.commission) }}
                  </template>
                </el-table-column>
                <el-table-column prop="profit" label="盈亏" width="120">
                  <template #default="{ row }">
                    <span v-if="row.profit !== null" :class="row.profit >= 0 ? 'text-up' : 'text-down'">
                      {{ row.profit >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(row.profit)) }}
                    </span>
                    <span v-else class="text-gray-400">-</span>
                  </template>
                </el-table-column>
                <el-table-column prop="balance" label="余额" width="120">
                  <template #default="{ row }">
                    ¥{{ formatPrice(row.balance) }}
                  </template>
                </el-table-column>
              </el-table>
            </el-tab-pane>

            <el-tab-pane label="月度收益" name="monthly">
              <div ref="monthlyChartRef" style="height: 300px"></div>
            </el-tab-pane>

            <el-tab-pane label="详细统计" name="stats">
              <el-descriptions :column="2" border>
                <el-descriptions-item label="总交易次数">{{ backtestResult.totalTrades }}</el-descriptions-item>
                <el-descriptions-item label="盈利次数">{{ backtestResult.winTrades }}</el-descriptions-item>
                <el-descriptions-item label="亏损次数">{{ backtestResult.lossTrades }}</el-descriptions-item>
                <el-descriptions-item label="胜率">{{ formatBacktestPercent(backtestResult.winRate, false) }}</el-descriptions-item>
                <el-descriptions-item label="平均盈利">¥{{ formatPrice(backtestResult.avgProfit) }}</el-descriptions-item>
                <el-descriptions-item label="平均亏损">¥{{ formatPrice(backtestResult.avgLoss) }}</el-descriptions-item>
                <el-descriptions-item label="最大单笔盈利">¥{{ formatPrice(backtestResult.maxProfit) }}</el-descriptions-item>
                <el-descriptions-item label="最大单笔亏损">¥{{ formatPrice(backtestResult.maxLoss) }}</el-descriptions-item>
                <el-descriptions-item label="盈亏比">{{ backtestResult.profitLossRatio.toFixed(2) }}</el-descriptions-item>
                <el-descriptions-item label="夏普比率">{{ backtestResult.sharpeRatio.toFixed(2) }}</el-descriptions-item>
                <el-descriptions-item label="最大回撤">{{ formatBacktestPercent(backtestResult.maxDrawdown, false) }}</el-descriptions-item>
                <el-descriptions-item label="回撤恢复天数">{{ backtestResult.recoveryDays }}天</el-descriptions-item>
              </el-descriptions>
            </el-tab-pane>
          </el-tabs>
        </el-card>

        <!-- 空状态 -->
        <el-card v-else>
          <el-empty description="请配置回测参数并开始回测" />
        </el-card>
      </div>
    </div>

    <!-- 保存策略对话框 -->
    <el-dialog
      v-model="saveStrategyDialogVisible"
      title="保存为策略"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="saveStrategyFormRef"
        :model="saveStrategyForm"
        :rules="saveStrategyRules"
        label-width="100px"
      >
        <el-form-item label="策略名称" prop="name">
          <el-input v-model="saveStrategyForm.name" placeholder="请输入策略名称" />
        </el-form-item>

        <el-form-item label="策略描述" prop="description">
          <el-input
            v-model="saveStrategyForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入策略描述"
          />
        </el-form-item>

        <el-alert
          title="提示"
          type="info"
          :closable="false"
          show-icon
        >
          <template #default>
            <div class="text-sm">
              <p>保存后将包含以下配置:</p>
              <ul class="mt-2 ml-4 list-disc">
                <li>策略类型: {{ backtestForm.strategy }}</li>
                <li>股票代码: {{ backtestForm.symbol }}</li>
                <li>初始资金: ¥{{ formatPrice(backtestForm.initialCapital) }}</li>
                <li>手续费率: {{ formatPercent(backtestForm.commission) }}</li>
                <li>滑点: {{ formatPercent(backtestForm.slippage) }}</li>
              </ul>
            </div>
          </template>
        </el-alert>
      </el-form>

      <template #footer>
        <el-button @click="saveStrategyDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmitSaveStrategy">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, nextTick, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import * as echarts from 'echarts'
import { analysisApi, stockApi, tradingApi, strategyApi, indicatorApi } from '@/services/api'
import { formatPrice, formatPercent, formatDate } from '@/utils/format'
import type { Indicator } from '@/types'

// 表单引用
const formRef = ref<FormInstance>()

// 回测表单
const backtestForm = reactive({
  strategy: 'ma_cross',
  symbol: '',
  startDate: new Date(new Date().setFullYear(new Date().getFullYear() - 1)),
  endDate: new Date(),
  initialCapital: 1000000,
  commission: 0.0003,
  slippage: 0.001,
  fastPeriod: 5,
  slowPeriod: 20,
  rsiPeriod: 14,
  // PE均值回归参数
  peHeavyBuy: 16.0,
  peBatchBuy: 17.0,
  peReduce: 19.5,
  peLiquidate: 20.5,
  epsStart: 1.20,
  epsEnd: 1.48,
  stopLossPct: 8,
  takeProfitPct: 25,
  dividendYield: 3.5,  // 长江电力默认3.5%年化股息率
  // PB均值回归参数
  pbHeavyBuy: 2.0,
  pbBatchBuy: 2.5,
  pbReduce: 4.5,
  pbLiquidate: 5.5,
  roeMean: 0.35,  // 紫金矿业近3年ROE均值约35%
})

// 表单验证规则
const formRules: FormRules = {
  strategy: [{ required: true, message: '请选择策略', trigger: 'change' }],
  symbol: [{ required: true, message: '请输入股票代码', trigger: 'blur' }],
  startDate: [{ required: true, message: '请选择开始日期', trigger: 'change' }],
  endDate: [{ required: true, message: '请选择结束日期', trigger: 'change' }],
  initialCapital: [{ required: true, message: '请输入初始资金', trigger: 'blur' }]
}

// 快速交易表单
const tradeForm = reactive({
  symbol: '',
  direction: 'buy',
  priceType: 'market',
  price: 0,
  quantity: 100
})

// 回测结果
const backtestResult = ref<any>(null)
const resultTab = ref('trades')
const loading = ref(false)
const loadingStrategies = ref(false)
const myIndicators = ref<Indicator[]>([])

// 图表引用
const equityChartRef = ref<HTMLElement>()
const monthlyChartRef = ref<HTMLElement>()

// 搜索股票
const searchStocks = async (queryString: string, cb: any) => {
  if (!queryString) {
    cb([])
    return
  }

  try {
    const results = await stockApi.searchStocks(queryString)
    cb(results)
  } catch (error) {
    cb([])
  }
}

// 选择股票
const handleStockSelect = (item: any) => {
  backtestForm.symbol = item.symbol
}

const toDateString = (date: Date | string) => {
  if (typeof date === 'string') return date
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const isIndicatorStrategy = (strategy: string) => strategy.startsWith('indicator:')

const getIndicatorId = (strategy: string) => strategy.split(':')[1]

const loadMyIndicators = async () => {
  loadingStrategies.value = true
  try {
    myIndicators.value = await indicatorApi.getMyIndicators()
  } catch (error) {
    console.error('加载我的指标失败:', error)
    ElMessage.error('加载我的指标失败')
  } finally {
    loadingStrategies.value = false
  }
}

const toFiniteNumber = (value: any, fallback = 0) => {
  const numberValue = Number(value)
  return Number.isFinite(numberValue) ? numberValue : fallback
}

const normalizeRatioMetric = (value: any) => {
  const numberValue = toFiniteNumber(value)
  return Math.abs(numberValue) <= 1 ? numberValue * 100 : numberValue
}

const formatBacktestPercent = (value: number | string, showSign = true) => {
  return formatPercent(value, 2, showSign)
}

const normalizeTradeType = (trade: any) => {
  const rawType = String(trade.type ?? trade.action ?? trade.side ?? '').toUpperCase()
  if (rawType === 'BUY' || rawType === 'SELL') return rawType
  if (trade.exit_date ?? trade.exitDate ?? trade.exit_price ?? trade.exitPrice) return 'SELL'
  return rawType || '--'
}

const normalizeBacktestTrade = (trade: any) => {
  const type = normalizeTradeType(trade)
  const date = trade.date ?? trade.tradeDate ?? trade.trade_date ?? trade.exitDate ?? trade.exit_date ?? trade.entryDate ?? trade.entry_date
  const entryDate = trade.entryDate ?? trade.entry_date ?? (type === 'BUY' ? date : undefined)
  const exitDate = trade.exitDate ?? trade.exit_date ?? (type === 'SELL' ? date : undefined)
  const price = toFiniteNumber(trade.price ?? trade.exitPrice ?? trade.exit_price ?? trade.entryPrice ?? trade.entry_price)
  const quantity = toFiniteNumber(trade.quantity ?? trade.shares ?? trade.size ?? trade.volume, 0)
  const amount = toFiniteNumber(trade.amount ?? trade.turnover ?? trade.value, price * quantity)
  const commission = toFiniteNumber(trade.commission ?? trade.fee ?? trade.comm, 0)
  const profitValue = trade.profit ?? trade.pnl ?? trade.realizedPnl ?? trade.realized_pnl
  const balanceValue = trade.balance ?? trade.cash ?? trade.totalEquity ?? trade.total_equity ?? trade.equity

  return {
    ...trade,
    date,
    entryDate,
    exitDate,
    type,
    price,
    quantity,
    amount,
    commission,
    profit: profitValue === undefined || profitValue === null ? null : toFiniteNumber(profitValue),
    balance: balanceValue === undefined || balanceValue === null ? undefined : toFiniteNumber(balanceValue)
  }
}

const normalizeBacktestResult = (result: any) => {
  const source = result?.data ?? result?.result ?? result ?? {}
  const summary = source?.summary ?? source?.metrics ?? {}
  const equityCurve = (source?.equityCurve ?? source?.equity_curve ?? []).map((item: any) => ({
    ...item,
    date: item.date ?? item.tradeDate ?? item.trade_date,
    value: toFiniteNumber(item.value ?? item.equity ?? item.totalEquity ?? item.total_equity ?? item.balance)
  }))
  const trades = (source?.trades ?? summary.trades ?? []).map(normalizeBacktestTrade)
  const totalTrades = toFiniteNumber(source?.totalTrades ?? source?.total_trades ?? summary.totalTrades ?? summary.total_trades ?? trades.length)
  const winTrades = toFiniteNumber(source?.winTrades ?? source?.winningTrades ?? source?.winning_trades ?? summary.winningTrades ?? summary.winning_trades)
  const lossTrades = toFiniteNumber(source?.lossTrades ?? source?.losingTrades ?? source?.losing_trades ?? summary.losingTrades ?? summary.losing_trades)
  const avgProfit = toFiniteNumber(source?.avgProfit ?? source?.avgWin ?? source?.avg_win ?? summary.avgWin ?? summary.avg_win)
  const avgLoss = toFiniteNumber(source?.avgLoss ?? source?.avg_loss ?? summary.avgLoss ?? summary.avg_loss)
  const profitLossRatio = toFiniteNumber(source?.profitLossRatio ?? source?.profit_loss_ratio ?? source?.profit_factor ?? summary.profitLossRatio ?? summary.profit_loss_ratio ?? summary.profitFactor ?? summary.profit_factor)
  const finalCapital = toFiniteNumber(
    source?.finalCapital ??
    source?.final_capital ??
    source?.finalEquity ??
    source?.final_equity ??
    summary.finalCapital ??
    summary.final_capital ??
    summary.finalEquity ??
    summary.final_equity ??
    equityCurve[equityCurve.length - 1]?.value ??
    backtestForm.initialCapital,
    backtestForm.initialCapital
  )

  return {
    ...source,
    finalCapital,
    totalReturn: normalizeRatioMetric(source?.totalReturn ?? source?.total_return ?? summary.totalReturn ?? summary.total_return),
    annualReturn: normalizeRatioMetric(source?.annualReturn ?? source?.annual_return ?? summary.annualReturn ?? summary.annual_return),
    maxDrawdown: normalizeRatioMetric(source?.maxDrawdown ?? source?.max_drawdown ?? summary.maxDrawdown ?? summary.max_drawdown),
    sharpeRatio: toFiniteNumber(source?.sharpeRatio ?? source?.sharpe_ratio ?? summary.sharpeRatio ?? summary.sharpe_ratio),
    winRate: normalizeRatioMetric(source?.winRate ?? source?.win_rate ?? summary.winRate ?? summary.win_rate),
    profitLossRatio,
    totalTrades,
    winTrades,
    lossTrades,
    avgProfit,
    avgLoss,
    maxProfit: toFiniteNumber(source?.maxProfit ?? summary.maxProfit),
    maxLoss: toFiniteNumber(source?.maxLoss ?? summary.maxLoss),
    recoveryDays: toFiniteNumber(source?.recoveryDays ?? summary.recoveryDays),
    trades,
    equityCurve,
    monthlyReturns: source?.monthlyReturns ?? source?.monthly_returns ?? []
  }
}

// 开始回测
const handleStartBacktest = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      const startDate = toDateString(backtestForm.startDate)
      const endDate = toDateString(backtestForm.endDate)
      const result = isIndicatorStrategy(backtestForm.strategy)
        ? await indicatorApi.backtestIndicator({
          indicatorId: getIndicatorId(backtestForm.strategy),
          symbol: backtestForm.symbol,
          startDate,
          endDate,
          initialCash: backtestForm.initialCapital
        })
        : await analysisApi.runBacktest({
          strategy: backtestForm.strategy,
          symbol: backtestForm.symbol,
          startDate,
          endDate,
          initialCapital: backtestForm.initialCapital,
          commission: backtestForm.commission,
          slippage: backtestForm.slippage,
          parameters: backtestForm.strategy === 'pe_mean_reversion'
            ? {
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
            : backtestForm.strategy === 'pb_mean_reversion'
            ? {
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
            : {
                fastPeriod: backtestForm.fastPeriod,
                slowPeriod: backtestForm.slowPeriod,
                rsiPeriod: backtestForm.rsiPeriod
              }
        })

      backtestResult.value = normalizeBacktestResult(result)
      ElMessage.success('回测完成')

      // 绘制图表
      await nextTick()
      renderEquityChart()
      renderMonthlyChart()
    } catch (error) {
      ElMessage.error('回测失败')
    } finally {
      loading.value = false
    }
  })
}

const findEquityValueByDate = (date: string) => {
  return backtestResult.value.equityCurve.find((item: any) => item.date === date)?.value
}

const buildTradeMarkers = () => {
  if (!backtestResult.value?.trades?.length) return []

  return backtestResult.value.trades.flatMap((trade: any) => {
    const markers = []
    if (trade.entryDate) {
      const value = findEquityValueByDate(trade.entryDate)
      if (value !== undefined) {
        markers.push({
          name: '买入',
          value: '买',
          coord: [trade.entryDate, value],
          itemStyle: { color: '#ef4444' }
        })
      }
    }
    if (trade.exitDate) {
      const value = findEquityValueByDate(trade.exitDate)
      if (value !== undefined) {
        markers.push({
          name: '卖出',
          value: '卖',
          coord: [trade.exitDate, value],
          itemStyle: { color: '#22c55e' }
        })
      }
    }
    return markers
  })
}

// 绘制资产权益曲线图
const renderEquityChart = () => {
  if (!equityChartRef.value || !backtestResult.value) return

  const chart = echarts.init(equityChartRef.value)
  const tradeMarkers = buildTradeMarkers()
  const option = {
    backgroundColor: '#0a0a0f',
    title: {
      text: '资产权益曲线',
      subtext: '现金 + 持仓市值，买/卖标记来自交易记录',
      left: 18,
      top: 10,
      textStyle: { color: '#e5e7eb', fontSize: 14, fontWeight: 600 },
      subtextStyle: { color: '#94a3b8', fontSize: 12 }
    },
    legend: {
      top: 18,
      right: 24,
      textStyle: { color: '#94a3b8' }
    },
    grid: { left: 72, right: 78, top: 72, bottom: 36 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderColor: '#333',
      textStyle: { color: '#fff' },
      formatter: (params: any) => {
        const point = Array.isArray(params) ? params[0] : params
        return `${point.axisValue}<br/>资产权益: ¥${formatPrice(point.data)}`
      }
    },
    xAxis: {
      type: 'category',
      data: backtestResult.value.equityCurve.map((item: any) => item.date),
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#64748b' }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#2a2e39' } },
      axisLabel: { color: '#64748b', formatter: '¥{value}' },
      splitLine: { lineStyle: { color: '#2a2e39' } }
    },
    series: [
      {
        name: '资产权益',
        type: 'line',
        data: backtestResult.value.equityCurve.map((item: any) => item.value),
        smooth: true,
        lineStyle: { color: '#10b981', width: 2 },
        showSymbol: false,
        markPoint: {
          symbol: 'pin',
          symbolSize: 46,
          label: { color: '#ffffff', fontSize: 11, fontWeight: 600 },
          data: tradeMarkers
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
            { offset: 1, color: 'rgba(16, 185, 129, 0.02)' }
          ])
        }
      }
    ]
  }
  chart.setOption(option)
}

// 绘制月度收益热力图
const renderMonthlyChart = () => {
  if (!monthlyChartRef.value || !backtestResult.value) return

  const chart = echarts.init(monthlyChartRef.value)
  const option = {
    tooltip: {
      position: 'top',
      formatter: (params: any) => {
        return `${params.name}: ${params.value >= 0 ? '+' : ''}${params.value.toFixed(2)}%`
      }
    },
    grid: { left: 80, right: 20, top: 20, bottom: 20 },
    xAxis: {
      type: 'category',
      data: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
      splitArea: { show: true }
    },
    yAxis: {
      type: 'category',
      data: backtestResult.value.monthlyReturns.map((item: any) => item.year),
      splitArea: { show: true }
    },
    visualMap: {
      min: -20,
      max: 20,
      calculable: true,
      orient: 'horizontal',
      left: 'center',
      bottom: '0%',
      inRange: {
        color: ['#ef5350', '#ffffff', '#26a69a']
      }
    },
    series: [
      {
        type: 'heatmap',
        data: backtestResult.value.monthlyReturns.flatMap((yearData: any) =>
          yearData.months.map((value: number, index: number) => [index, yearData.year, value])
        ),
        label: { show: true, formatter: (params: any) => `${params.value[2].toFixed(1)}%` }
      }
    ]
  }
  chart.setOption(option)
}

// 快速交易
const handleQuickTrade = async () => {
  try {
    await ElMessageBox.confirm(
      `确认${tradeForm.direction === 'buy' ? '买入' : '卖出'} ${tradeForm.symbol} ${tradeForm.quantity}股？`,
      '确认交易',
      { type: 'warning' }
    )

    await tradingApi.createOrder({
      symbol: tradeForm.symbol,
      type: tradeForm.direction as 'buy' | 'sell',
      priceType: tradeForm.priceType,
      price: tradeForm.priceType === 'limit' ? tradeForm.price : undefined,
      quantity: tradeForm.quantity
    })

    ElMessage.success('订单已提交')
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('下单失败')
    }
  }
}

// 导出报告
const handleExportResult = () => {
  if (!backtestResult.value) {
    ElMessage.warning('暂无回测结果')
    return
  }

  try {
    // 使用浏览器打印功能导出PDF
    const printContent = generateReportHTML()
    const printWindow = window.open('', '_blank')
    if (printWindow) {
      printWindow.document.write(printContent)
      printWindow.document.close()
      printWindow.focus()
      setTimeout(() => {
        printWindow.print()
        ElMessage.success('正在准备导出报告')
      }, 500)
    }
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

// 生成报告HTML
const generateReportHTML = () => {
  const result = backtestResult.value
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>回测报告 - ${backtestForm.symbol}</title>
      <style>
        body { font-family: Arial, sans-serif; padding: 20px; }
        h1 { color: #333; border-bottom: 2px solid #409eff; padding-bottom: 10px; }
        h2 { color: #666; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f5f5f5; }
        .metric { display: inline-block; margin: 10px 20px 10px 0; }
        .metric-label { color: #999; font-size: 12px; }
        .metric-value { font-size: 24px; font-weight: bold; }
        .positive { color: #67c23a; }
        .negative { color: #f56c6c; }
      </style>
    </head>
    <body>
      <h1>回测报告</h1>
      <p><strong>股票代码:</strong> ${backtestForm.symbol}</p>
      <p><strong>策略:</strong> ${backtestForm.strategy}</p>
      <p><strong>回测周期:</strong> ${backtestForm.startDate.toISOString().split('T')[0]} 至 ${backtestForm.endDate.toISOString().split('T')[0]}</p>
      <p><strong>初始资金:</strong> ¥${formatPrice(backtestForm.initialCapital)}</p>

      <h2>关键指标</h2>
      <div class="metric">
        <div class="metric-label">最终资金</div>
        <div class="metric-value">¥${formatPrice(result.finalCapital)}</div>
      </div>
      <div class="metric">
        <div class="metric-label">总收益率</div>
        <div class="metric-value ${result.totalReturn >= 0 ? 'positive' : 'negative'}">
          ${result.totalReturn >= 0 ? '+' : ''}${formatPercent(result.totalReturn)}
        </div>
      </div>
      <div class="metric">
        <div class="metric-label">年化收益</div>
        <div class="metric-value ${result.annualReturn >= 0 ? 'positive' : 'negative'}">
          ${result.annualReturn >= 0 ? '+' : ''}${formatPercent(result.annualReturn)}
        </div>
      </div>
      <div class="metric">
        <div class="metric-label">最大回撤</div>
        <div class="metric-value negative">${formatPercent(result.maxDrawdown)}</div>
      </div>
      <div class="metric">
        <div class="metric-label">夏普比率</div>
        <div class="metric-value">${result.sharpeRatio.toFixed(2)}</div>
      </div>
      <div class="metric">
        <div class="metric-label">胜率</div>
        <div class="metric-value">${formatPercent(result.winRate)}</div>
      </div>

      <h2>交易记录</h2>
      <table>
        <thead>
          <tr>
            <th>日期</th>
            <th>类型</th>
            <th>价格</th>
            <th>数量</th>
            <th>金额</th>
            <th>手续费</th>
            <th>盈亏</th>
          </tr>
        </thead>
        <tbody>
          ${result.trades.map((trade: any) => `
            <tr>
              <td>${formatDate(trade.date)}</td>
              <td>${trade.type}</td>
              <td>¥${formatPrice(trade.price)}</td>
              <td>${trade.quantity}</td>
              <td>¥${formatPrice(trade.amount)}</td>
              <td>¥${formatPrice(trade.commission)}</td>
              <td class="${trade.profit >= 0 ? 'positive' : 'negative'}">
                ${trade.profit !== null ? (trade.profit >= 0 ? '+' : '') + '¥' + formatPrice(Math.abs(trade.profit)) : '-'}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>

      <p style="margin-top: 40px; color: #999; font-size: 12px;">
        报告生成时间: ${new Date().toLocaleString('zh-CN')}
      </p>
    </body>
    </html>
  `
}

// 保存策略对话框
const saveStrategyDialogVisible = ref(false)
const saveStrategyForm = reactive({
  name: '',
  description: ''
})
const saveStrategyFormRef = ref<any>()

const saveStrategyRules = {
  name: [{ required: true, message: '请输入策略名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入策略描述', trigger: 'blur' }]
}

// 保存策略
const handleSaveStrategy = () => {
  if (!backtestResult.value) {
    ElMessage.warning('暂无回测结果')
    return
  }

  saveStrategyForm.name = `${backtestForm.strategy}_${backtestForm.symbol}_${new Date().toISOString().split('T')[0]}`
  saveStrategyForm.description = `基于${backtestForm.symbol}的${backtestForm.strategy}策略回测`
  saveStrategyDialogVisible.value = true
}

// 提交保存策略
const handleSubmitSaveStrategy = async () => {
  if (!saveStrategyFormRef.value) return

  await saveStrategyFormRef.value.validate(async (valid: boolean) => {
    if (!valid) return

    try {
      await strategyApi.createStrategy({
        name: saveStrategyForm.name,
        description: saveStrategyForm.description,
        type: 'trend',
        code: backtestForm.strategy,
        parameters: {
          strategy: backtestForm.strategy,
          symbol: backtestForm.symbol,
          initialCapital: backtestForm.initialCapital,
          commission: backtestForm.commission,
          slippage: backtestForm.slippage,
          fastPeriod: backtestForm.fastPeriod,
          slowPeriod: backtestForm.slowPeriod,
          rsiPeriod: backtestForm.rsiPeriod
        },
        riskLevel: 'medium'
      })

      ElMessage.success('策略保存成功')
      saveStrategyDialogVisible.value = false
    } catch (error) {
      ElMessage.error('保存失败')
    }
  })
}

// 重置表单
const handleReset = () => {
  formRef.value?.resetFields()
  backtestResult.value = null
}

onMounted(() => {
  loadMyIndicators()
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'BacktestCenter'
})
</script>

<style scoped lang="scss">
.backtest-center {
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

  .chart-container {
    background: #0a0a0f;
    border-radius: 8px;
    padding: 16px;
  }

  :deep(.el-input-number) {
    width: 100%;
  }

  :deep(.el-radio-group) {
    display: flex;
    width: 100%;

    .el-radio-button {
      flex: 1;

      .el-radio-button__inner {
        width: 100%;
      }
    }
  }
}
</style>
