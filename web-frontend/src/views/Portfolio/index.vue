<template>
  <div class="portfolio">
    <!-- 账户切换工具栏 -->
    <div class="account-toolbar mb-4">
      <AccountSwitcher
        :initial-account="(route.query.account as string) || undefined"
        @change="onAccountChange"
      />
    </div>

    <!-- 顶部统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-4">
      <el-card class="stat-card">
        <div class="stat-label">总市值</div>
        <div class="stat-value">¥{{ formatPrice(portfolioStore.totalValue) }}</div>
        <div class="stat-sub">现金: ¥{{ formatPrice(portfolioStore.cash) }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">持仓数量</div>
        <div class="stat-value">{{ portfolioStore.positionCount }}</div>
        <div class="stat-sub">
          {{ profitCount }} 盈利 / {{ lossCount }} 亏损
        </div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">总投入</div>
        <div class="stat-value">¥{{ formatPrice(portfolioStore.totalCost) }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">总盈亏</div>
        <div :class="['stat-value', portfolioStore.totalPnL >= 0 ? 'text-up' : 'text-down']">
          {{ formatSignedCurrency(portfolioStore.totalPnL) }}
        </div>
        <div :class="['stat-sub', portfolioStore.totalPnLPercent >= 0 ? 'text-up' : 'text-down']">
          {{ formatPercent(portfolioStore.totalPnLPercent) }}
        </div>
      </el-card>
    </div>

    <!-- 持仓明细 -->
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">持仓明细</span>
          <div class="flex items-center gap-2">
            <el-button size="small" @click="handleRefresh" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="portfolioStore.positions" stripe v-loading="loading">
        <el-table-column prop="updatedAt" label="日期" width="110">
          <template #default="{ row }">
            {{ row.addedDate?.slice(0, 10) || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="symbol" label="代码" width="120" fixed>
          <template #default="{ row }">
            <router-link :to="{ name: 'StockDetail', params: { symbol: row.symbol } }" class="text-blue-600 hover:underline">
              {{ row.symbol }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120" />

        <el-table-column prop="quantity" label="持仓量" width="110" align="right">
          <template #default="{ row }">
            <div>{{ row.quantity }}</div>
            <div class="text-xs text-gray-400">可用 {{ row.sharesAvailable ?? row.quantity }}</div>
          </template>
        </el-table-column>

        <el-table-column prop="avgCost" label="均价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.avgCost) }}
          </template>
        </el-table-column>

        <el-table-column prop="currentPrice" label="现价" width="100" align="right">
          <template #default="{ row }">
            <span class="font-medium">¥{{ formatPrice(row.currentPrice) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="marketValue" label="市值" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.marketValue) }}
          </template>
        </el-table-column>

        <el-table-column label="盈亏" width="150" align="right">
          <template #default="{ row }">
            <div :class="row.profit >= 0 ? 'text-up' : 'text-down'">
              <div class="font-medium">
                {{ formatSignedCurrency(row.profit) }}
              </div>
              <div class="text-xs">
                ({{ formatPercent(row.profitPercent) }})
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="weight" label="占比" width="100" align="right">
          <template #default="{ row }">
            <el-progress
              :percentage="row.weight"
              :stroke-width="8"
              :show-text="true"
              :format="() => `${(row.weight || 0).toFixed(1)}%`"
            />
          </template>
        </el-table-column>

        <el-table-column prop="stopLoss" label="止损价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.stopLoss" class="text-red-600">¥{{ formatPrice(row.stopLoss) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button-group size="small">
              <el-button @click="handleBuy(row)">加仓</el-button>
              <el-button type="danger" @click="handleSell(row)">卖出</el-button>
              <el-button @click="handleSetStopLoss(row)">止损</el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 交易对话框 -->
    <el-dialog
      v-model="tradeDialogVisible"
      :title="tradeForm.type === 'BUY' ? '买入' : '卖出'"
      width="500px"
    >
      <el-form :model="tradeForm" label-width="80px">
        <el-form-item label="股票">
          <el-input v-model="tradeForm.symbol" disabled />
        </el-form-item>

        <el-form-item label="价格类型">
          <el-radio-group v-model="tradeForm.priceType">
            <el-radio label="market">市价</el-radio>
            <el-radio label="limit">限价</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="价格" v-if="tradeForm.priceType === 'limit'">
          <el-input-number v-model="tradeForm.price" :min="0" :step="0.01" :precision="2" class="w-full" />
        </el-form-item>

        <el-form-item label="数量">
          <el-input-number v-model="tradeForm.quantity" :min="100" :step="100" class="w-full" />
        </el-form-item>

        <el-form-item label="交易理由" required>
          <el-input
            v-model="tradeForm.reason"
            type="textarea"
            :rows="2"
            placeholder="必填，至少 10 个字（后端审计要求）"
          />
        </el-form-item>

        <el-form-item label="预计金额">
          <div class="text-lg font-semibold">
            ¥{{ formatPrice(tradeForm.quantity * (tradeForm.priceType === 'limit' ? tradeForm.price : tradeForm.currentPrice)) }}
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="tradeDialogVisible = false">取消</el-button>
        <el-button
          :type="tradeForm.type === 'BUY' ? 'danger' : 'success'"
          @click="handleConfirmTrade"
          :loading="tradeLoading"
          :disabled="tradeForm.reason.trim().length < 10"
        >
          确认{{ tradeForm.type === 'BUY' ? '买入' : '卖出' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 止损设置对话框 -->
    <el-dialog v-model="stopLossDialogVisible" title="设置止损价" width="400px">
      <el-form :model="stopLossForm" label-width="80px">
        <el-form-item label="股票">
          <el-input v-model="stopLossForm.symbol" disabled />
        </el-form-item>

        <el-form-item label="当前价">
          <div class="text-lg font-semibold">¥{{ formatPrice(stopLossForm.currentPrice) }}</div>
        </el-form-item>

        <el-form-item label="止损价">
          <el-input-number v-model="stopLossForm.stopLoss" :min="0" :step="0.01" :precision="2" class="w-full" />
        </el-form-item>

        <el-form-item label="止损幅度">
          <div :class="stopLossPercent < 0 ? 'text-red-600' : 'text-green-600'">
            {{ stopLossPercent.toFixed(2) }}%
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="stopLossDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmStopLoss">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { riskApi } from '@/services/api'
import { simulationApi } from '@/services/api/simulation'
import AccountSwitcher from '@/components/AccountSwitcher.vue'
import { usePortfolioStore } from '@/stores/portfolio'
import { useMarketWebSocket } from '@/composables/useWebSocket'
import { formatPrice, formatPercent, formatSignedCurrency } from '@/utils/format'
import type { Position } from '@/types/models'

const route = useRoute()
const portfolioStore = usePortfolioStore()

const loading = ref(false)

// 盈亏计数
const profitCount = computed(() => portfolioStore.positions.filter(p => p.profit > 0).length)
const lossCount = computed(() => portfolioStore.positions.filter(p => p.profit < 0).length)

// 交易对话框
const tradeDialogVisible = ref(false)
const tradeLoading = ref(false)
const tradeForm = reactive({
  symbol: '',
  name: '',
  type: 'BUY' as 'BUY' | 'SELL',
  priceType: 'market' as 'market' | 'limit',
  price: 0,
  currentPrice: 0,
  quantity: 100,
  reason: ''
})

// 止损对话框
const stopLossDialogVisible = ref(false)
const stopLossForm = reactive({
  symbol: '',
  currentPrice: 0,
  stopLoss: 0
})

const stopLossPercent = computed(() => {
  if (stopLossForm.currentPrice === 0) return 0
  return ((stopLossForm.stopLoss - stopLossForm.currentPrice) / stopLossForm.currentPrice) * 100
})

// 止损规则列表
const stopLossRules = ref<any[]>([])

const loadStopLossRules = async () => {
  try {
    const rules = await riskApi.getStopLossRules()
    stopLossRules.value = rules || []
  } catch (error) {
    console.error('加载止损规则失败:', error)
  }
}

// WebSocket连接
const { subscribe, unsubscribe, on } = useMarketWebSocket()

// 监听行情更新
on('quote', (data: any) => {
  const position = portfolioStore.positions.find(p => p.symbol === data.symbol)
  if (position) {
    position.currentPrice = data.price
    position.marketValue = position.quantity * data.price
    position.profit = position.marketValue - position.avgCost * position.quantity
    position.profitPercent = position.totalCost > 0 ? (position.profit / position.totalCost) * 100 : 0
  }
})

// 账户切换：加载数据并刷新行情订阅
const subscribedSymbols = ref<string[]>([])

const onAccountChange = async (accountName: string) => {
  subscribedSymbols.value.forEach(s => unsubscribe(s))
  subscribedSymbols.value = []
  await portfolioStore.fetchAll(accountName)
  const symbols = portfolioStore.positions.map(p => p.symbol)
  symbols.forEach(s => subscribe(s))
  subscribedSymbols.value = symbols
}

// 加载持仓数据（刷新当前账户）
const loadPositions = async () => {
  if (!portfolioStore.currentAccount) return
  loading.value = true
  try {
    await portfolioStore.fetchAll(portfolioStore.currentAccount)
  } catch (error) {
    ElMessage.error('加载持仓数据失败')
  } finally {
    loading.value = false
  }
}

// 刷新
const handleRefresh = () => {
  loadPositions()
}

// 买入（加仓）
const handleBuy = (position: Position) => {
  tradeForm.symbol = position.symbol
  tradeForm.name = position.name
  tradeForm.type = 'BUY'
  tradeForm.priceType = 'market'
  tradeForm.currentPrice = position.currentPrice
  tradeForm.price = position.currentPrice
  tradeForm.quantity = 100
  tradeForm.reason = ''
  tradeDialogVisible.value = true
}

// 卖出
const handleSell = (position: Position) => {
  const available = position.sharesAvailable ?? position.quantity
  tradeForm.symbol = position.symbol
  tradeForm.name = position.name
  tradeForm.type = 'SELL'
  tradeForm.priceType = 'market'
  tradeForm.currentPrice = position.currentPrice
  tradeForm.price = position.currentPrice
  tradeForm.quantity = Math.min(available, 100)
  tradeForm.reason = ''
  tradeDialogVisible.value = true
}

// 确认交易
const handleConfirmTrade = async () => {
  try {
    await ElMessageBox.confirm(
      `确认${tradeForm.type === 'BUY' ? '买入' : '卖出'} ${tradeForm.symbol} ${tradeForm.quantity}股（账户 ${portfolioStore.currentAccount}）？`,
      '确认交易',
      { type: 'warning' }
    )

    tradeLoading.value = true
    await simulationApi.trade(portfolioStore.currentAccount, {
      action: tradeForm.type.toLowerCase() as 'buy' | 'sell',
      symbol: tradeForm.symbol,
      shares: tradeForm.quantity,
      price_limit: tradeForm.priceType === 'limit' ? tradeForm.price : undefined,
      reason: tradeForm.reason.trim()
    })

    ElMessage.success('交易已成交')
    tradeDialogVisible.value = false
    await loadPositions()
  } catch (error: any) {
    if (error !== 'cancel') {
      // 后端拒单（非交易时段/限价不满足/可用不足等）直接展示后端文案
      ElMessage.error(error?.message || '交易失败')
    }
  } finally {
    tradeLoading.value = false
  }
}

// 设置止损
const handleSetStopLoss = (position: Position) => {
  stopLossForm.symbol = position.symbol
  stopLossForm.currentPrice = position.currentPrice
  stopLossForm.stopLoss = position.stopLoss || position.currentPrice * 0.95
  stopLossDialogVisible.value = true
}

// 确认止损
const handleConfirmStopLoss = async () => {
  if (!stopLossForm.symbol) return

  try {
    await riskApi.createStopLossRule({
      symbol: stopLossForm.symbol,
      name: `${stopLossForm.symbol}止损`,
      type: 'fixed_percent',
      stopLossPercent: Math.abs(stopLossPercent.value)
    })

    ElMessage.success('止损规则已设置')
    stopLossDialogVisible.value = false

    // 更新本地持仓数据中的止损价
    const position = portfolioStore.positions.find(p => p.symbol === stopLossForm.symbol)
    if (position) {
      position.stopLoss = stopLossForm.stopLoss
    }

    // 刷新止损规则列表
    await loadStopLossRules()
  } catch (error: any) {
    ElMessage.error(error?.message || '设置止损失败')
  }
}

// 组件挂载
onMounted(() => {
  // 首次加载由 AccountSwitcher change 触发（支持 ?account=xxx 预选）
})

// 组件卸载
onUnmounted(() => {
  subscribedSymbols.value.forEach(s => unsubscribe(s))
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'Portfolio'
})
</script>

<style scoped lang="scss">
.portfolio {
  .account-toolbar {
    display: flex;
    align-items: center;
  }

  .stat-card {
    :deep(.el-card__body) {
      padding: 16px;
    }

    .stat-label {
      font-size: 12px;
      color: #9ca3af;
      margin-bottom: 4px;
    }

    .stat-value {
      font-size: 24px;
      font-weight: bold;
      color: #0f172a;
      margin-bottom: 4px;
    }

    .stat-sub {
      font-size: 12px;
      color: #9ca3af;
    }
  }

  :deep(.el-input-number) {
    width: 100%;
  }
}
</style>
