<template>
  <div class="portfolio">
    <!-- 顶部统计卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-4">
      <el-card class="stat-card">
        <div class="stat-label">总市值</div>
        <div class="stat-value">¥{{ formatPrice(portfolioStats.totalValue) }}</div>
        <div class="stat-sub">现金: ¥{{ formatPrice(portfolioStats.cash) }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">持仓数量</div>
        <div class="stat-value">{{ portfolioStats.totalPositions }}</div>
        <div class="stat-sub">
          {{ portfolioStats.profitPositions }} 盈利 / {{ portfolioStats.lossPositions }} 亏损
        </div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">总投入</div>
        <div class="stat-value">¥{{ formatPrice(portfolioStats.totalCost) }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">总盈亏</div>
        <div :class="['stat-value', portfolioStats.totalProfit >= 0 ? 'text-up' : 'text-down']">
          {{ portfolioStats.totalProfit >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(portfolioStats.totalProfit)) }}
        </div>
        <div :class="['stat-sub', portfolioStats.totalProfitPercent >= 0 ? 'text-up' : 'text-down']">
          {{ portfolioStats.totalProfitPercent >= 0 ? '+' : '' }}{{ formatPercent(portfolioStats.totalProfitPercent) }}
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
            <el-button type="primary" size="small" @click="handleCreateOrder">
              + 新建订单
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="positions" stripe v-loading="loading">
        <el-table-column prop="symbol" label="代码" width="120" fixed>
          <template #default="{ row }">
            <router-link :to="{ name: 'StockDetail', params: { symbol: row.symbol } }" class="text-blue-600 hover:underline">
              {{ row.symbol }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120" />

        <el-table-column prop="quantity" label="持仓量" width="100" align="right">
          <template #default="{ row }">
            {{ row.quantity }}
          </template>
        </el-table-column>

        <el-table-column prop="avgPrice" label="均价" width="100" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.avgPrice) }}
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
                {{ row.profit >= 0 ? '+' : '' }}¥{{ formatPrice(Math.abs(row.profit)) }}
              </div>
              <div class="text-xs">
                ({{ row.profitPercent >= 0 ? '+' : '' }}{{ formatPercent(row.profitPercent) }})
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="positionPercent" label="占比" width="100" align="right">
          <template #default="{ row }">
            <el-progress
              :percentage="row.positionPercent"
              :stroke-width="8"
              :show-text="true"
              :format="() => `${row.positionPercent.toFixed(1)}%`"
            />
          </template>
        </el-table-column>

        <el-table-column prop="stopLoss" label="止损价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.stopLoss" class="text-red-600">¥{{ formatPrice(row.stopLoss) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="targetPrice" label="目标价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.targetPrice" class="text-green-600">¥{{ formatPrice(row.targetPrice) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="reason" label="买入理由" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.reason }}</el-tag>
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
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { tradingApi } from '@/services/api'
import { usePortfolioStore } from '@/stores/portfolio'
import { useMarketWebSocket } from '@/composables/useWebSocket'
import { formatPrice, formatPercent } from '@/utils/format'
import type { Position } from '@/types/models'

const router = useRouter()
const portfolioStore = usePortfolioStore()

// 持仓数据
const positions = ref<Position[]>([])
const loading = ref(false)

// 统计数据
const portfolioStats = computed(() => ({
  totalValue: portfolioStore.totalValue,
  cash: portfolioStore.totalValue - positions.value.reduce((sum, p) => sum + p.marketValue, 0),
  totalPositions: positions.value.length,
  profitPositions: positions.value.filter(p => p.unrealizedPnL > 0).length,
  lossPositions: positions.value.filter(p => p.unrealizedPnL < 0).length,
  totalCost: positions.value.reduce((sum, p) => sum + p.avgCost * p.quantity, 0),
  totalProfit: positions.value.reduce((sum, p) => sum + p.unrealizedPnL, 0),
  totalProfitPercent: portfolioStore.totalPnLPercent
}))

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
  quantity: 100
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

// WebSocket连接
const { subscribe, unsubscribe, on } = useMarketWebSocket()

// 监听行情更新
on('quote', (data: any) => {
  const position = positions.value.find(p => p.symbol === data.symbol)
  if (position) {
    position.currentPrice = data.price
    position.marketValue = position.quantity * data.price
    position.unrealizedPnL = position.marketValue - position.avgCost * position.quantity
    position.unrealizedPnLPercent = (position.unrealizedPnL / (position.avgCost * position.quantity)) * 100
  }
})

// 加载持仓数据
const loadPositions = async () => {
  loading.value = true
  try {
    await portfolioStore.fetchPositions()
    positions.value = portfolioStore.positions

    // 订阅实时行情
    const symbols = positions.value.map(p => p.symbol)
    symbols.forEach(symbol => subscribe(symbol))
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

// 新建订单
const handleCreateOrder = () => {
  router.push({ name: 'Orders' })
}

// 买入（加仓）
const handleBuy = (position: Position) => {
  tradeForm.symbol = position.symbol
  tradeForm.name = position.symbolName
  tradeForm.type = 'BUY'
  tradeForm.priceType = 'market'
  tradeForm.currentPrice = position.currentPrice
  tradeForm.price = position.currentPrice
  tradeForm.quantity = 100
  tradeDialogVisible.value = true
}

// 卖出
const handleSell = (position: Position) => {
  tradeForm.symbol = position.symbol
  tradeForm.name = position.symbolName
  tradeForm.type = 'SELL'
  tradeForm.priceType = 'market'
  tradeForm.currentPrice = position.currentPrice
  tradeForm.price = position.currentPrice
  tradeForm.quantity = Math.min(position.quantity, 100)
  tradeDialogVisible.value = true
}

// 确认交易
const handleConfirmTrade = async () => {
  try {
    await ElMessageBox.confirm(
      `确认${tradeForm.type === 'BUY' ? '买入' : '卖出'} ${tradeForm.symbol} ${tradeForm.quantity}股？`,
      '确认交易',
      { type: 'warning' }
    )

    tradeLoading.value = true
    await tradingApi.createOrder({
      symbol: tradeForm.symbol,
      type: tradeForm.type.toLowerCase() as 'buy' | 'sell',
      priceType: tradeForm.priceType,
      price: tradeForm.priceType === 'limit' ? tradeForm.price : undefined,
      quantity: tradeForm.quantity
    })

    ElMessage.success('订单已提交')
    tradeDialogVisible.value = false

    // 刷新持仓
    setTimeout(() => {
      loadPositions()
    }, 1000)
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('下单失败')
    }
  } finally {
    tradeLoading.value = false
  }
}

// 设置止损
const handleSetStopLoss = (position: Position) => {
  stopLossForm.symbol = position.symbol
  stopLossForm.currentPrice = position.currentPrice
  stopLossForm.stopLoss = position.currentPrice * 0.95 // TODO: Add stopLoss field to Position type
  stopLossDialogVisible.value = true
}

// 确认止损
const handleConfirmStopLoss = async () => {
  try {
    // TODO: Implement setStopLoss API
    // await tradingApi.setStopLoss(stopLossForm.symbol, stopLossForm.stopLoss)
    ElMessage.success('止损价设置成功')
    stopLossDialogVisible.value = false

    // 更新本地数据
    // const position = positions.value.find(p => p.symbol === stopLossForm.symbol)
    // if (position) {
    //   position.stopLoss = stopLossForm.stopLoss
    // }
  } catch (error) {
    ElMessage.error('设置止损价失败')
  }
}

// 组件挂载
onMounted(() => {
  loadPositions()
})

// 组件卸载
onUnmounted(() => {
  const symbols = positions.value.map(p => p.symbol)
  symbols.forEach(symbol => unsubscribe(symbol))
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
