<template>
  <div class="trades-page">
    <!-- 顶部统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-4">
      <el-card shadow="never">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm text-gray-500 mb-1">今日成交笔数</div>
            <div class="text-2xl font-bold">{{ stats.todayCount }}</div>
          </div>
          <div class="w-12 h-12 bg-blue-100 rounded-lg flex items-center justify-center">
            <el-icon :size="24" color="#3b82f6"><Document /></el-icon>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm text-gray-500 mb-1">今日成交金额</div>
            <div class="text-2xl font-bold">{{ formatPrice(stats.todayAmount) }}</div>
          </div>
          <div class="w-12 h-12 bg-green-100 rounded-lg flex items-center justify-center">
            <el-icon :size="24" color="#22c55e"><Money /></el-icon>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm text-gray-500 mb-1">今日盈亏</div>
            <div class="text-2xl font-bold" :class="stats.todayPnl >= 0 ? 'text-red-500' : 'text-green-600'">
              {{ formatPrice(stats.todayPnl) }}
            </div>
          </div>
          <div class="w-12 h-12 bg-yellow-100 rounded-lg flex items-center justify-center">
            <el-icon :size="24" color="#eab308"><TrendCharts /></el-icon>
          </div>
        </div>
      </el-card>

      <el-card shadow="never">
        <div class="flex items-center justify-between">
          <div>
            <div class="text-sm text-gray-500 mb-1">胜率</div>
            <div class="text-2xl font-bold">{{ formatPercent(stats.winRate) }}</div>
          </div>
          <div class="w-12 h-12 bg-purple-100 rounded-lg flex items-center justify-center">
            <el-icon :size="24" color="#a855f7"><Trophy /></el-icon>
          </div>
        </div>
      </el-card>
    </div>

    <!-- 交易记录列表 -->
    <el-card shadow="never">
      <!-- 工具栏 -->
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-3">
          <span class="text-base font-semibold">交易记录</span>

          <!-- 操作类型筛选 -->
          <el-select
            v-model="filters.direction"
            placeholder="全部操作"
            style="width: 120px"
            @change="fetchTrades"
          >
            <el-option label="全部操作" value="" />
            <el-option label="买入" value="buy" />
            <el-option label="卖出" value="sell" />
          </el-select>

          <!-- 日期范围 -->
          <el-date-picker
            v-model="filters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="fetchTrades"
          />

          <!-- 股票搜索 -->
          <el-input
            v-model="filters.keyword"
            placeholder="搜索股票代码或名称"
            :prefix-icon="Search"
            clearable
            style="width: 200px"
            @input="handleSearch"
          />
        </div>

        <div class="flex items-center gap-3 text-sm">
          <span class="text-gray-500">总笔数: <strong>{{ stats.totalCount }}</strong></span>
          <span class="text-red-500">盈利: {{ stats.profitCount }}</span>
          <span class="text-green-600">亏损: {{ stats.lossCount }}</span>
          <span class="text-gray-500">胜率: <strong>{{ formatPercent(stats.winRate) }}</strong></span>
          <el-button type="primary" :icon="Download" @click="handleExport">导出</el-button>
        </div>
      </div>

      <!-- 表格 -->
      <el-table
        v-loading="loading"
        :data="trades"
        stripe
      >
        <el-table-column prop="tradeDate" label="日期" width="180">
          <template #default="{ row }">
            <span class="text-gray-500">{{ formatDateTime(row.tradeDate) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }">
            <span class="font-medium">{{ row.symbol }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="100" />

        <el-table-column prop="action" label="操作" width="80">
          <template #default="{ row }">
            <el-tag
              :type="row.action === 'buy' ? 'danger' : 'success'"
              size="small"
            >
              {{ row.action === 'buy' ? 'BUY' : 'SELL' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="价格" width="100" align="right">
          <template #default="{ row }">
            {{ formatPrice(row.price) }}
          </template>
        </el-table-column>

        <el-table-column prop="quantity" label="数量" width="100" align="right">
          <template #default="{ row }">
            {{ formatAmount(row.quantity) }}
          </template>
        </el-table-column>

        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            <span class="font-medium">{{ formatPrice(row.amount) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="fee" label="佣金" width="100" align="right">
          <template #default="{ row }">
            {{ formatPrice(row.fee) }}
          </template>
        </el-table-column>

        <el-table-column prop="stampDuty" label="印花税" width="100" align="right">
          <template #default="{ row }">
            {{ row.stampDuty ? formatPrice(row.stampDuty) : '-' }}
          </template>
        </el-table-column>

        <el-table-column prop="pnl" label="盈亏" width="120" align="right">
          <template #default="{ row }">
            <span v-if="row.pnl !== null" :class="row.pnl >= 0 ? 'text-red-500' : 'text-green-600'" class="font-medium">
              {{ formatPrice(row.pnl) }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="pnlPercent" label="盈亏比例" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.pnlPercent !== null" :class="row.pnlPercent >= 0 ? 'text-red-500' : 'text-green-600'" class="font-medium">
              {{ formatPercent(row.pnlPercent) }}
            </span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="orderId" label="关联订单" width="120">
          <template #default="{ row }">
            <span class="text-xs text-gray-500 font-mono">{{ row.orderId }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="reason" label="理由" min-width="150" show-overflow-tooltip />
      </el-table>

      <!-- 分页 -->
      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchTrades"
          @size-change="fetchTrades"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search, Download, Document, Money, TrendCharts, Trophy } from '@element-plus/icons-vue'
import { simulationApi } from '@/services/api'

// 默认账户
const DEFAULT_ACCOUNT = 'agent_virtual'
import { formatPrice, formatPercent, formatAmount, formatDateTime } from '@/utils/format'

interface Trade {
  id: number
  tradeDate: string
  symbol: string
  name: string
  action: 'buy' | 'sell'
  price: number
  quantity: number
  amount: number
  fee: number
  stampDuty: number
  pnl: number | null
  pnlPercent: number | null
  orderId: string
  reason: string
}

interface Stats {
  todayCount: number
  todayAmount: number
  todayPnl: number
  totalCount: number
  profitCount: number
  lossCount: number
  winRate: number
}

// 状态
const loading = ref(false)
const trades = ref<Trade[]>([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 统计数据
const stats = reactive<Stats>({
  todayCount: 0,
  todayAmount: 0,
  todayPnl: 0,
  totalCount: 0,
  profitCount: 0,
  lossCount: 0,
  winRate: 0
})

// 筛选条件
const filters = reactive({
  direction: '',
  dateRange: [] as string[],
  keyword: ''
})

// 获取交易记录
const fetchTrades = async () => {
  loading.value = true
  try {
    const data = await simulationApi.getTrades(DEFAULT_ACCOUNT, 100)
    // 前端过滤（新 API 不支持后端过滤，暂时在前端实现）
    let filteredTrades = data
    if (filters.direction) {
      filteredTrades = filteredTrades.filter((t: any) => t.action === filters.direction)
    }
    if (filters.keyword) {
      const kw = filters.keyword.toLowerCase()
      filteredTrades = filteredTrades.filter((t: any) => 
        t.symbol?.toLowerCase().includes(kw) || t.name?.toLowerCase().includes(kw)
      )
    }
    // 日期过滤（如果 API 不支持）
    if (filters.dateRange[0]) {
      filteredTrades = filteredTrades.filter((t: any) => 
        new Date(t.timestamp) >= new Date(filters.dateRange[0])
      )
    }
    if (filters.dateRange[1]) {
      filteredTrades = filteredTrades.filter((t: any) => 
        new Date(t.timestamp) <= new Date(filters.dateRange[1])
      )
    }
    
    total.value = filteredTrades.length
    // 前端分页
    const start = (currentPage.value - 1) * pageSize.value
    const end = start + pageSize.value
    trades.value = filteredTrades.slice(start, end)
  } catch (error) {
    ElMessage.error('获取交易记录失败')
  } finally {
    loading.value = false
  }
}

// 搜索
let searchTimer: ReturnType<typeof setTimeout> | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    currentPage.value = 1
    fetchTrades()
  }, 500)
}

// 导出
const handleExport = () => {
  try {
    // 构建CSV内容
    const headers = ['日期', '代码', '名称', '操作', '价格', '数量', '金额', '佣金', '印花税', '盈亏', '盈亏比例', '关联订单', '理由']
    const rows = trades.value.map(trade => [
      formatDateTime(trade.tradeDate),
      trade.symbol,
      trade.name,
      trade.action === 'buy' ? '买入' : '卖出',
      trade.price,
      trade.quantity,
      trade.amount,
      trade.fee,
      trade.stampDuty || '-',
      trade.pnl !== null ? trade.pnl : '-',
      trade.pnlPercent !== null ? `${trade.pnlPercent}%` : '-',
      trade.orderId,
      trade.reason
    ])

    const csv = [headers, ...rows].map(row => row.join(',')).join('\n')
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `交易记录_${new Date().toISOString().split('T')[0]}.csv`
    link.click()

    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败')
  }
}

onMounted(() => {
  fetchTrades()
})
</script>

<style scoped>
.trades-page {
  padding: 20px;
}
</style>
