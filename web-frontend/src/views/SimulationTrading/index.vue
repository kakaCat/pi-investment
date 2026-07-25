<template>
  <div class="simulation-trading">
    <el-page-header @back="$router.back()" content="模拟交易监控" />

    <!-- 账户切换工具栏 -->
    <div class="account-toolbar">
      <AccountSwitcher
        :initial-account="(route.query.account as string) || undefined"
        @change="onAccountChange"
      />
    </div>

    <el-row :gutter="20" style="margin-top: 20px;">
      <!-- 策略信息 -->
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>📊 策略信息</span>
              <el-tag v-if="hasStrategy" type="success" size="small">运行中</el-tag>
            </div>
          </template>
          <div v-if="!hasStrategy" style="padding: 20px 0; text-align: center; color: #999;">
            该账户未绑定策略
          </div>
          <div v-else v-loading="loading.strategy">
            <div v-if="strategy" class="info-list">
              <div class="info-item">
                <span class="label">策略名称</span>
                <span class="value">{{ strategy.name }}</span>
              </div>
              <div class="info-item">
                <span class="label">版本</span>
                <span class="value">{{ strategy.version }}</span>
              </div>
              <div class="info-item">
                <span class="label">调仓周期</span>
                <span class="value">{{ strategy.rebalance_days }} 天</span>
              </div>
              <div class="info-item">
                <span class="label">最大持仓</span>
                <span class="value">{{ strategy.max_positions }} 只</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 账户状态 -->
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>💰 账户状态</span>
              <el-button type="primary" size="small" @click="refreshAccount" :loading="loading.account">
                刷新
              </el-button>
            </div>
          </template>
          <div v-loading="loading.account">
            <div v-if="account" class="info-list">
              <div class="info-item">
                <span class="label">总资产</span>
                <span class="value">¥{{ formatNumber(account.total_value) }}</span>
              </div>
              <div class="info-item">
                <span class="label">可用资金</span>
                <span class="value">¥{{ formatNumber(account.cash_available) }}</span>
              </div>
              <div class="info-item">
                <span class="label">冻结资金</span>
                <span class="value">¥{{ formatNumber(account.cash_frozen) }}</span>
              </div>
              <div class="info-item">
                <span class="label">持仓市值</span>
                <span class="value">¥{{ formatNumber(account.position_value) }}</span>
              </div>
              <div class="info-item">
                <span class="label">收益率</span>
                <span class="value" :class="returnClass">{{ returnPercent }}%</span>
              </div>
              <div class="info-item">
                <span class="label">上次调仓</span>
                <span class="value">{{ account.last_rebalance_date || '未知' }}</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 执行策略 -->
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <span>⚡ 执行策略</span>
            </div>
          </template>
          <div>
            <el-button
              type="primary"
              size="large"
              style="width: 100%"
              @click="runStrategy"
              :loading="loading.run"
              :disabled="!hasStrategy"
            >
              执行{{ strategyId ? strategyId.toUpperCase() + '策略' : '策略' }}
            </el-button>
            <el-alert 
              v-if="runResult" 
              :type="runResult.type" 
              :title="runResult.title"
              :description="runResult.message"
              style="margin-top: 15px"
              show-icon
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Tab切换：持仓明细 / 交易记录 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <el-radio-group v-model="activeTab" size="small">
            <el-radio-button label="positions">📈 持仓明细</el-radio-button>
            <el-radio-button label="trades">📋 交易记录</el-radio-button>
          </el-radio-group>
        </div>
      </template>

      <!-- 持仓明细 -->
      <div v-show="activeTab === 'positions'">
        <el-table
          :data="positionsWithNames"
          v-loading="loading.account || loading.stocks"
          stripe
          style="width: 100%"
        >
          <el-table-column label="股票代码" width="120">
            <template #default="scope">
              <el-link
                type="primary"
                :href="`/stocks/${scope.row.symbol}`"
                target="_blank"
                style="font-weight: 500;"
              >
                {{ scope.row.symbol }}
              </el-link>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="公司名称" width="180">
            <template #default="scope">
              <span v-if="scope.row.name">{{ scope.row.name }}</span>
              <span v-else style="color: #999;">加载中...</span>
            </template>
          </el-table-column>
          <el-table-column label="持仓(可用)" width="130">
            <template #default="scope">
              {{ scope.row.shares_total }}
              <span style="color: #999; font-size: 12px">({{ scope.row.shares_available }}可卖)</span>
            </template>
          </el-table-column>
          <el-table-column label="成本价" width="120">
            <template #default="scope">
              ¥{{ parseFloat(scope.row.avg_cost ?? 0).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="当前价" width="120">
            <template #default="scope">
              <span v-if="scope.row.current_price">
                ¥{{ parseFloat(scope.row.current_price).toFixed(2) }}
              </span>
              <span v-else style="color: #999;">--</span>
            </template>
          </el-table-column>
          <el-table-column label="市值" width="150">
            <template #default="scope">
              ¥{{ formatNumber(scope.row.market_value) }}
            </template>
          </el-table-column>
          <el-table-column label="浮动盈亏" width="120">
            <template #default="scope">
              <span :class="parseFloat(scope.row.profit_total ?? 0) >= 0 ? 'positive' : 'negative'">
                ¥{{ parseFloat(scope.row.profit_total ?? 0).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="当日盈亏" width="110">
            <template #default="scope">
              <span :class="parseFloat(scope.row.profit_today ?? 0) >= 0 ? 'positive' : 'negative'">
                ¥{{ parseFloat(scope.row.profit_today ?? 0).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="收益率">
            <template #default="scope">
              <span :class="parseFloat(scope.row.profit_total_rate ?? 0) >= 0 ? 'positive' : 'negative'">
                {{ (parseFloat(scope.row.profit_total_rate ?? 0) * 100).toFixed(2) }}%
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 交易记录 -->
      <div v-show="activeTab === 'trades'">
        <el-table
          :data="tradeRecords"
          v-loading="loading.trades"
          stripe
          style="width: 100%"
        >
          <el-table-column label="时间" width="180">
            <template #default="scope">
              {{ formatTradeDateTime(scope.row.timestamp) }}
            </template>
          </el-table-column>
          <el-table-column label="类型" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.action === 'BUY' ? 'success' : 'danger'" size="small">
                {{ scope.row.action === 'BUY' ? '买入' : '卖出' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="股票" width="120">
            <template #default="scope">
              <el-link
                type="primary"
                :href="`/stocks/${scope.row.symbol}`"
                target="_blank"
                style="font-weight: 500;"
              >
                {{ scope.row.symbol }}
              </el-link>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="120">
            <template #default="scope">
              {{ scope.row.shares }}
            </template>
          </el-table-column>
          <el-table-column label="价格" width="120">
            <template #default="scope">
              ¥{{ parseFloat(scope.row.price).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="金额" width="150">
            <template #default="scope">
              ¥{{ formatNumber(parseFloat(scope.row.shares) * parseFloat(scope.row.price)) }}
            </template>
          </el-table-column>
          <el-table-column label="费用" width="100">
            <template #default="scope">
              ¥{{ (parseFloat(scope.row.commission || 0) + parseFloat(scope.row.stamp_duty || 0)).toFixed(2) }}
            </template>
          </el-table-column>
          <el-table-column label="已实现盈亏" width="120">
            <template #default="scope">
              <span v-if="scope.row.realized_pnl != null"
                    :class="parseFloat(scope.row.realized_pnl) >= 0 ? 'positive' : 'negative'">
                ¥{{ parseFloat(scope.row.realized_pnl).toFixed(2) }}
              </span>
              <span v-else style="color: #999;">--</span>
            </template>
          </el-table-column>
          <el-table-column label="理由" min-width="180">
            <template #default="scope">
              <span style="font-size: 12px; color: #666">{{ scope.row.reason || '--' }}</span>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="tradeRecords.length === 0 && !loading.trades" description="暂无交易记录" />
      </div>
    </el-card>

    <!-- V13调度任务状态 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>⏰ {{ strategyId ? strategyId.toUpperCase() + '调度任务' : '调度任务' }}</span>
          <el-button type="primary" size="small" @click="loadSchedulerTasks" :loading="loading.scheduler">
            刷新
          </el-button>
        </div>
      </template>
      <div v-loading="loading.scheduler">
        <el-table :data="schedulerTasks" stripe style="width: 100%">
          <el-table-column label="任务名称" width="200">
            <template #default="scope">
              <el-link
                type="primary"
                @click="showTaskDetail(scope.row)"
                style="font-weight: 500;"
              >
                {{ scope.row.task_name }}
              </el-link>
            </template>
          </el-table-column>
          <el-table-column prop="description" label="描述" min-width="250" />
          <el-table-column label="执行时间" width="150">
            <template #default="scope">
              <el-tag size="small">{{ scope.row.cron_expression }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="scope">
              <el-tag :type="scope.row.is_enabled ? 'success' : 'info'" size="small">
                {{ scope.row.is_enabled ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="最近执行" width="150">
            <template #default="scope">
              <span v-if="scope.row.last_run" style="font-size: 12px; color: #666;">
                {{ formatShortDateTime(scope.row.last_run) }}
              </span>
              <span v-else style="color: #999;">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="scope">
              <el-button
                size="small"
                @click="toggleTask(scope.row)"
                :loading="scope.row.loading"
              >
                {{ scope.row.is_enabled ? '禁用' : '启用' }}
              </el-button>
              <el-button
                type="primary"
                size="small"
                @click="triggerTask(scope.row)"
                :loading="scope.row.triggering"
              >
                触发
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <!-- 任务详情对话框 -->
    <el-dialog
      v-model="taskDetailDialog.visible"
      :title="`任务详情 - ${taskDetailDialog.task?.task_name || ''}`"
      width="80%"
      top="5vh"
    >
      <div v-if="taskDetailDialog.task">
        <!-- 任务基本信息 -->
        <el-descriptions :column="2" border style="margin-bottom: 20px;">
          <el-descriptions-item label="任务名称">
            {{ taskDetailDialog.task.task_name }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="taskDetailDialog.task.is_enabled ? 'success' : 'info'" size="small">
              {{ taskDetailDialog.task.is_enabled ? '启用' : '禁用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">
            {{ taskDetailDialog.task.description }}
          </el-descriptions-item>
          <el-descriptions-item label="Cron表达式">
            <el-tag>{{ taskDetailDialog.task.cron_expression }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="执行命令">
            <code style="font-size: 12px;">{{ taskDetailDialog.task.command }}</code>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ formatDateTime(taskDetailDialog.task.created_at) }}
          </el-descriptions-item>
          <el-descriptions-item label="更新时间">
            {{ formatDateTime(taskDetailDialog.task.updated_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 执行历史 -->
        <h3 style="margin: 20px 0 10px 0;">执行历史</h3>
        <div v-loading="taskDetailDialog.loading">
          <el-table
            :data="taskDetailDialog.history"
            stripe
            max-height="400"
            style="width: 100%"
          >
            <el-table-column label="状态" width="100">
              <template #default="scope">
                <el-tag
                  :type="scope.row.status === 'success' ? 'success' : 'danger'"
                  size="small"
                >
                  {{ scope.row.status === 'success' ? '成功' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="开始时间" width="180">
              <template #default="scope">
                {{ formatDateTime(scope.row.started_at) }}
              </template>
            </el-table-column>
            <el-table-column label="完成时间" width="180">
              <template #default="scope">
                {{ formatDateTime(scope.row.completed_at) }}
              </template>
            </el-table-column>
            <el-table-column label="耗时" width="100">
              <template #default="scope">
                <span :style="{ color: scope.row.duration_ms > 5000 ? '#f56c6c' : '#67c23a' }">
                  {{ scope.row.duration_ms }}ms
                </span>
              </template>
            </el-table-column>
            <el-table-column label="错误信息" min-width="300">
              <template #default="scope">
                <span v-if="scope.row.error" style="color: #f56c6c; font-size: 12px;">
                  {{ scope.row.error }}
                </span>
                <span v-else style="color: #67c23a;">执行成功</span>
              </template>
            </el-table-column>
          </el-table>

          <!-- 执行统计 -->
          <el-row :gutter="20" style="margin-top: 20px;">
            <el-col :span="6">
              <el-statistic title="总执行次数" :value="taskDetailDialog.stats.total" />
            </el-col>
            <el-col :span="6">
              <el-statistic
                title="成功次数"
                :value="taskDetailDialog.stats.success"
                value-style="color: #67c23a"
              />
            </el-col>
            <el-col :span="6">
              <el-statistic
                title="失败次数"
                :value="taskDetailDialog.stats.failed"
                value-style="color: #f56c6c"
              />
            </el-col>
            <el-col :span="6">
              <el-statistic
                title="成功率"
                :value="taskDetailDialog.stats.successRate"
                suffix="%"
              />
            </el-col>
          </el-row>
        </div>
      </div>

      <template #footer>
        <el-button @click="taskDetailDialog.visible = false">关闭</el-button>
        <el-button
          type="primary"
          @click="triggerTask(taskDetailDialog.task)"
          :loading="taskDetailDialog.task?.triggering"
        >
          立即执行
        </el-button>
      </template>
    </el-dialog>

    <!-- 执行历史 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>📋 执行历史</span>
          <el-button type="primary" size="small" @click="loadExecutionHistory" :loading="loading.history">
            刷新
          </el-button>
        </div>
      </template>
      <el-timeline v-if="executionHistory.length > 0">
        <el-timeline-item
          v-for="item in executionHistory"
          :key="item.date"
          :timestamp="item.date"
          placement="top"
        >
          <el-card shadow="hover">
            <h4>{{ item.strategy_name }}</h4>
            <p style="margin: 10px 0; color: #666;">
              <el-tag :type="item.status === 'completed' ? 'success' : 'info'" size="small">
                {{ item.status === 'completed' ? '执行完成' : '执行中' }}
              </el-tag>
              <span style="margin-left: 10px;">交易数量: {{ item.trades_count }}</span>
            </p>
            <el-table :data="item.trades" size="small" style="margin-top: 10px;" max-height="200">
              <el-table-column prop="symbol" label="股票" width="100" />
              <el-table-column label="操作" width="80">
                <template #default="scope">
                  <el-tag :type="scope.row.action === 'BUY' ? 'success' : 'danger'" size="small">
                    {{ scope.row.action === 'BUY' ? '买入' : '卖出' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="shares" label="数量" width="100" />
              <el-table-column label="价格" width="100">
                <template #default="scope">
                  ¥{{ scope.row.price.toFixed(2) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-timeline-item>
      </el-timeline>
      <el-empty v-else description="暂无执行历史" />
    </el-card>

    <!-- 收益曲线 -->
    <el-card shadow="hover" style="margin-top: 20px;">
      <template #header>
        <div class="card-header">
          <span>📈 收益曲线</span>
          <el-button type="primary" size="small" @click="loadPerformance" :loading="loading.performance">
            刷新
          </el-button>
        </div>
      </template>
      <div v-loading="loading.performance" style="height: 400px;">
        <div ref="chartRef" style="width: 100%; height: 100%;"></div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import AccountSwitcher from '@/components/AccountSwitcher.vue'
import { simulationApi } from '@/services/api/simulation'
import type { AccountSummary } from '@/services/api/simulation'

const STOCK_API = 'http://127.0.0.1:5001/api/stocks'
const SCHEDULER_API = 'http://127.0.0.1:5001/api/scheduler'

const route = useRoute()
// 当前账户（单一数据源，由 AccountSwitcher 驱动）
const selectedAccount = ref<string>('')
const currentAccount = ref<AccountSummary | null>(null)
const strategyId = computed(() => currentAccount.value?.strategy_name || null)
const hasStrategy = computed(() => !!strategyId.value)

const loading = ref({
  strategy: false,
  account: false,
  stocks: false,
  run: false,
  history: false,
  performance: false,
  scheduler: false,
  trades: false
})

const activeTab = ref('positions')
const strategy = ref<any>(null)
const account = ref<any>(null)
const stockNames = ref<Record<string, string>>({})
const executionHistory = ref<any[]>([])
const schedulerTasks = ref<any[]>([])
const schedulerHistory = ref<any[]>([])
const tradeRecords = ref<any[]>([])
const taskDetailDialog = ref({
  visible: false,
  task: null as any,
  history: [] as any[],
  loading: false,
  stats: {
    total: 0,
    success: 0,
    failed: 0,
    successRate: 0
  }
})
const chartRef = ref<HTMLDivElement | null>(null)
let chartInstance: echarts.ECharts | null = null

const positions = computed(() => account.value?.positions || [])
const positionsWithNames = computed(() => {
  return positions.value.map((pos: any) => ({
    ...pos,
    name: stockNames.value[pos.symbol] || ''
  }))
})
const runResult = ref<any>(null)
let refreshTimer: number | null = null

async function onAccountChange(accountName: string, account: AccountSummary | any) {
  selectedAccount.value = accountName
  currentAccount.value = account
  await Promise.all([
    loadAccount(),
    loadTradeRecords(),
    loadPerformance(),
    loadExecutionHistory(),
    strategyId.value ? loadStrategy() : Promise.resolve((strategy.value = null)),
    loadSchedulerTasks()
  ])
}

const returnPercent = computed(() => {
  if (!account.value) return '0.00'
  return (parseFloat(account.value.cumulative_return) * 100).toFixed(2)
})

const returnClass = computed(() => {
  if (!account.value) return ''
  return parseFloat(account.value.cumulative_return) >= 0 ? 'positive' : 'negative'
})

function formatNumber(value: any) {
  return parseFloat(value).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

function formatDateTime(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

function formatShortDateTime(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  })
}

function formatTradeDateTime(dateStr: string) {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

async function showTaskDetail(task: any) {
  taskDetailDialog.value.visible = true
  taskDetailDialog.value.task = task
  taskDetailDialog.value.loading = true
  taskDetailDialog.value.history = []

  try {
    // 加载该任务的执行历史（使用数字ID查询）
    const res = await fetch(`${SCHEDULER_API}/history?task_id=${task.task_id}&limit=50`)
    const data = await res.json()

    if (data.success) {
      const history = data.data || []
      taskDetailDialog.value.history = history

      // 计算统计信息
      const total = history.length
      const success = history.filter((h: any) => h.status === 'success').length
      const failed = total - success
      const successRate = total > 0 ? Math.round((success / total) * 100) : 0

      taskDetailDialog.value.stats = {
        total,
        success,
        failed,
        successRate
      }
    }
  } catch (err: any) {
    console.error('加载任务执行历史失败:', err)
    ElMessage.error(`加载执行历史失败: ${err.message}`)
  } finally {
    taskDetailDialog.value.loading = false
  }
}

async function loadSchedulerTasks() {
  loading.value.scheduler = true
  try {
    // 加载任务配置
    const tasksRes = await fetch(`${SCHEDULER_API}/tasks`)
    const tasksData = await tasksRes.json()

    if (tasksData.success) {
      // 只显示当前账户绑定策略相关的任务
      const allTasks = tasksData.tasks || tasksData.data || []
      const strategyKey = (strategyId.value || '').toLowerCase()
      const v13Tasks = allTasks
        .filter((task: any) => {
          if (!strategyKey) return false
          const taskName = task.name || task.task_name || ''
          return taskName.toLowerCase().includes(strategyKey)
        })
        .map((task: any) => ({
          ...task,
          task_name: task.name || task.task_name,
          task_id: task.id || task.task_id,  // 保存数字ID用于history匹配
          is_enabled: task.enabled !== undefined ? task.enabled : task.is_enabled,
          loading: false,
          triggering: false,
          last_run: null
        }))

      // 加载执行历史以获取最近执行时间
      const historyRes = await fetch(`${SCHEDULER_API}/history?limit=100`)
      const historyData = await historyRes.json()

      if (historyData.success) {
        const allHistory = historyData.data || []

        // 为每个任务找到最近的执行记录（使用数字ID匹配）
        v13Tasks.forEach((task: any) => {
          const taskHistory = allHistory.filter((h: any) => h.task_id === task.task_id)
          if (taskHistory.length > 0) {
            task.last_run = taskHistory[0].started_at
          }
        })

        // 保存最近的执行记录用于显示
        schedulerHistory.value = allHistory.slice(0, 10)
      }

      schedulerTasks.value = v13Tasks
    }
  } catch (err: any) {
    console.error('加载调度任务失败:', err)
    ElMessage.error(`加载调度任务失败: ${err.message}`)
  } finally {
    loading.value.scheduler = false
  }
}

async function toggleTask(task: any) {
  task.loading = true
  try {
    const action = task.is_enabled ? 'disable' : 'enable'
    const res = await fetch(`${SCHEDULER_API}/tasks/${task.task_name}/${action}`, {
      method: 'POST'
    })
    const data = await res.json()

    if (data.success) {
      task.is_enabled = !task.is_enabled
      ElMessage.success(`任务已${task.is_enabled ? '启用' : '禁用'}`)
    } else {
      ElMessage.error(`操作失败: ${data.error}`)
    }
  } catch (err: any) {
    ElMessage.error(`操作失败: ${err.message}`)
  } finally {
    task.loading = false
  }
}

async function triggerTask(task: any) {
  task.triggering = true
  try {
    const res = await fetch(`${SCHEDULER_API}/tasks/${task.task_name}/trigger`, {
      method: 'POST'
    })
    const data = await res.json()

    if (data.success) {
      ElMessage.success('任务已触发执行')
      // 3秒后刷新执行历史
      setTimeout(() => {
        loadSchedulerTasks()
      }, 3000)
    } else {
      ElMessage.error(`触发失败: ${data.error}`)
    }
  } catch (err: any) {
    ElMessage.error(`触发失败: ${err.message}`)
  } finally {
    task.triggering = false
  }
}

async function loadStrategy() {
  if (!strategyId.value) { strategy.value = null; return }
  loading.value.strategy = true
  try {
    const res = await simulationApi.getStrategyInfo(strategyId.value)
    strategy.value = res || null
  } catch (err: any) {
    console.error('加载策略失败:', err)
    // 策略失败不影响其他功能，不显示错误提示
  } finally {
    loading.value.strategy = false
  }
}

async function loadAccount() {
  if (!selectedAccount.value) return
  loading.value.account = true
  try {
    const res = await simulationApi.getAccount(selectedAccount.value)
    account.value = res
    // 加载持仓股票的名称
    await loadStockNames(res.positions)
  } catch (err: any) {
    ElMessage.error(`加载账户失败: ${err.message}`)
  } finally {
    loading.value.account = false
  }
}

async function loadStockNames(positions: any[]) {
  if (!positions || positions.length === 0) return

  loading.value.stocks = true
  try {
    const symbols = positions.map(p => p.symbol)

    // 批量查询股票信息
    const res = await fetch(`${STOCK_API}/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ symbols })
    })
    const data = await res.json()

    if (data.success && data.data) {
      // 将结果保存到stockNames
      Object.keys(data.data).forEach(symbol => {
        stockNames.value[symbol] = data.data[symbol].name || symbol
      })
    }
  } catch (err: any) {
    console.error('加载股票名称失败:', err)
  } finally {
    loading.value.stocks = false
  }
}

async function refreshAccount() {
  await loadAccount()
  ElMessage.success('刷新成功')
}

async function runStrategy() {
  if (!strategyId.value || !selectedAccount.value) return
  loading.value.run = true
  runResult.value = null
  try {
    const data = await simulationApi.runStrategy(strategyId.value, selectedAccount.value)

    const action = data.action
    if (action === 'skip') {
      runResult.value = {
        type: 'warning',
        title: '无需调仓',
        message: data.message
      }
    } else {
      runResult.value = {
        type: 'success',
        title: '调仓成功',
        message: `信号数: ${data.signals_count}, 交易数: ${data.trades_count}`
      }
      setTimeout(() => {
        loadAccount()
        loadExecutionHistory()
      }, 1000)
    }
  } catch (err: any) {
    runResult.value = {
      type: 'error',
      title: '执行失败',
      message: err.message
    }
  } finally {
    loading.value.run = false
  }
}

async function loadExecutionHistory() {
  if (!selectedAccount.value) return
  loading.value.history = true
  try {
    const res = await simulationApi.getExecutionHistory(selectedAccount.value, 50)
    executionHistory.value = res || []
  } catch (err: any) {
    console.error('加载执行历史失败:', err)
  } finally {
    loading.value.history = false
  }
}

async function loadTradeRecords() {
  if (!selectedAccount.value) return
  loading.value.trades = true
  try {
    const res = await simulationApi.getTrades(selectedAccount.value, 50)
    tradeRecords.value = res || []
  } catch (err: any) {
    console.error('加载交易记录失败:', err)
  } finally {
    loading.value.trades = false
  }
}

async function loadPerformance() {
  if (!selectedAccount.value) return
  loading.value.performance = true
  try {
    const res = await simulationApi.getPerformance(selectedAccount.value)
    if (res) {
      await nextTick()
      renderChart(res)
    }
  } catch (err: any) {
    console.error('加载收益数据失败:', err)
  } finally {
    loading.value.performance = false
  }
}

function renderChart(performanceData: any) {
  if (!chartRef.value) {
    console.warn('chartRef not available')
    return
  }

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const equityCurve = performanceData.equity_curve || []

  if (equityCurve.length === 0) {
    // 没有数据时显示空状态
    const option = {
      title: {
        text: '暂无收益数据',
        left: 'center',
        top: 'center',
        textStyle: {
          fontSize: 16,
          color: '#999'
        }
      }
    }
    chartInstance.setOption(option)
    return
  }

  const dates = equityCurve.map((item: any) => item.date)
  const values = equityCurve.map((item: any) => item.total_value)
  const returns = equityCurve.map((item: any) => item.return)

  const option = {
    title: {
      text: '账户净值曲线',
      left: 'center',
      textStyle: {
        fontSize: 16,
        fontWeight: 'normal'
      }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      formatter: function(params: any) {
        const date = params[0].axisValue
        const value = params[0].data
        const returnVal = params[1] ? params[1].data : 0
        return `日期: ${date}<br/>净值: ¥${value.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}<br/>收益率: ${returnVal.toFixed(2)}%`
      }
    },
    legend: {
      data: ['账户净值', '累计收益率'],
      top: 35
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates
    },
    yAxis: [
      {
        type: 'value',
        name: '净值(¥)',
        position: 'left',
        axisLabel: {
          formatter: (value: number) => {
            if (value >= 10000) {
              return `¥${(value / 10000).toFixed(1)}万`
            }
            return `¥${value.toFixed(0)}`
          }
        }
      },
      {
        type: 'value',
        name: '收益率(%)',
        position: 'right',
        axisLabel: {
          formatter: '{value}%'
        }
      }
    ],
    series: [
      {
        name: '账户净值',
        type: 'line',
        smooth: true,
        data: values,
        yAxisIndex: 0,
        lineStyle: {
          width: 3,
          color: '#5470c6'
        },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(84, 112, 198, 0.3)' },
            { offset: 1, color: 'rgba(84, 112, 198, 0.05)' }
          ])
        },
        symbol: equityCurve.length === 1 ? 'circle' : 'none',
        symbolSize: 8
      },
      {
        name: '累计收益率',
        type: 'line',
        smooth: true,
        data: returns,
        yAxisIndex: 1,
        lineStyle: {
          width: 2,
          color: '#91cc75',
          type: 'dashed'
        },
        symbol: equityCurve.length === 1 ? 'circle' : 'none',
        symbolSize: 8
      }
    ]
  }

  chartInstance.setOption(option)
  console.log('Chart rendered with', equityCurve.length, 'data points')
}

onMounted(() => {
  // 首次加载由 AccountSwitcher change 触发（支持 ?account=xxx 预选）
  // 每30秒自动刷新
  refreshTimer = window.setInterval(() => {
    if (selectedAccount.value) {
      loadAccount()
      loadSchedulerTasks()
    }
  }, 30000)

  // 响应式调整图表大小
  window.addEventListener('resize', () => {
    chartInstance?.resize()
  })
})

defineExpose({ onAccountChange, runStrategy, hasStrategy, selectedAccount })

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
  if (chartInstance) {
    chartInstance.dispose()
  }
  window.removeEventListener('resize', () => {
    chartInstance?.resize()
  })
})
</script>

<style scoped>
.simulation-trading {
  padding: 20px;
}

.account-toolbar {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
}

.label {
  color: #666;
  font-weight: 500;
}

.value {
  color: #333;
  font-weight: 700;
  font-size: 1.1em;
}

.positive {
  color: #67c23a;
}

.negative {
  color: #f56c6c;
}
</style>
