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
              <el-select v-model="backtestForm.strategy" placeholder="选择策略" class="w-full">
                <el-option label="MA 双均线" value="ma_cross" />
                <el-option label="RSI 反转" value="rsi_reversal" />
                <el-option label="MACD 金叉" value="macd_golden" />
                <el-option label="布林带突破" value="boll_breakout" />
                <el-option label="KDJ 超买超卖" value="kdj_overbought" />
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
                {{ backtestResult.totalReturn >= 0 ? '+' : '' }}{{ formatPercent(backtestResult.totalReturn) }}
              </div>
            </div>
            <div class="metric-card">
              <div class="metric-label">年化收益</div>
              <div :class="['metric-value', backtestResult.annualReturn >= 0 ? 'text-up' : 'text-down']">
                {{ backtestResult.annualReturn >= 0 ? '+' : '' }}{{ formatPercent(backtestResult.annualReturn) }}
              </div>
            </div>
            <div class="metric-card">
              <div class="metric-label">最大回撤</div>
              <div class="metric-value text-down">{{ formatPercent(backtestResult.maxDrawdown) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">夏普比率</div>
              <div class="metric-value">{{ backtestResult.sharpeRatio.toFixed(2) }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-label">胜率</div>
              <div class="metric-value">{{ formatPercent(backtestResult.winRate) }}</div>
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

          <!-- 净值曲线图 -->
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
                <el-descriptions-item label="胜率">{{ formatPercent(backtestResult.winRate) }}</el-descriptions-item>
                <el-descriptions-item label="平均盈利">¥{{ formatPrice(backtestResult.avgProfit) }}</el-descriptions-item>
                <el-descriptions-item label="平均亏损">¥{{ formatPrice(backtestResult.avgLoss) }}</el-descriptions-item>
                <el-descriptions-item label="最大单笔盈利">¥{{ formatPrice(backtestResult.maxProfit) }}</el-descriptions-item>
                <el-descriptions-item label="最大单笔亏损">¥{{ formatPrice(backtestResult.maxLoss) }}</el-descriptions-item>
                <el-descriptions-item label="盈亏比">{{ backtestResult.profitLossRatio.toFixed(2) }}</el-descriptions-item>
                <el-descriptions-item label="夏普比率">{{ backtestResult.sharpeRatio.toFixed(2) }}</el-descriptions-item>
                <el-descriptions-item label="最大回撤">{{ formatPercent(backtestResult.maxDrawdown) }}</el-descriptions-item>
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
import { ref, reactive, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import * as echarts from 'echarts'
import { analysisApi, stockApi, tradingApi, strategyApi } from '@/services/api'
import { formatPrice, formatPercent, formatDate } from '@/utils/format'

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
  rsiPeriod: 14
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

// 开始回测
const handleStartBacktest = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async (valid) => {
    if (!valid) return

    loading.value = true
    try {
      const result = await analysisApi.runBacktest({
        strategy: backtestForm.strategy,
        symbol: backtestForm.symbol,
        startDate: backtestForm.startDate.toISOString().split('T')[0],
        endDate: backtestForm.endDate.toISOString().split('T')[0],
        initialCapital: backtestForm.initialCapital,
        commission: backtestForm.commission,
        slippage: backtestForm.slippage,
        parameters: {
          fastPeriod: backtestForm.fastPeriod,
          slowPeriod: backtestForm.slowPeriod,
          rsiPeriod: backtestForm.rsiPeriod
        }
      })

      backtestResult.value = result
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

// 绘制净值曲线图
const renderEquityChart = () => {
  if (!equityChartRef.value || !backtestResult.value) return

  const chart = echarts.init(equityChartRef.value)
  const option = {
    backgroundColor: '#0a0a0f',
    grid: { left: 50, right: 50, top: 40, bottom: 30 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderColor: '#333',
      textStyle: { color: '#fff' }
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
        name: '净值',
        type: 'line',
        data: backtestResult.value.equityCurve.map((item: any) => item.value),
        smooth: true,
        lineStyle: { color: '#10b981', width: 2 },
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
