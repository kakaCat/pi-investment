<template>
  <div class="orders">
    <el-card>
      <template #header>
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-3">
            <span class="font-semibold">订单管理</span>
            <el-select v-model="filters.status" placeholder="全部状态" size="small" style="width: 120px" @change="handleFilterChange">
              <el-option label="全部状态" value="" />
              <el-option label="待成交" value="pending" />
              <el-option label="已成交" value="filled" />
              <el-option label="已取消" value="cancelled" />
              <el-option label="已拒绝" value="rejected" />
            </el-select>
            <el-select v-model="filters.type" placeholder="全部类型" size="small" style="width: 120px" @change="handleFilterChange">
              <el-option label="全部类型" value="" />
              <el-option label="限价单" value="limit" />
              <el-option label="市价单" value="market" />
              <el-option label="止损单" value="stop" />
            </el-select>
            <el-select v-model="filters.direction" placeholder="全部方向" size="small" style="width: 120px" @change="handleFilterChange">
              <el-option label="全部方向" value="" />
              <el-option label="买入" value="buy" />
              <el-option label="卖出" value="sell" />
            </el-select>
          </div>
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

      <el-table :data="orders" stripe v-loading="loading">
        <el-table-column prop="id" label="订单ID" width="120">
          <template #default="{ row }">
            <span class="font-mono text-xs text-gray-500">#{{ row.id }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }">
            <router-link :to="{ name: 'StockDetail', params: { symbol: row.symbol } }" class="text-blue-600 hover:underline font-medium">
              {{ row.symbol }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120" />

        <el-table-column prop="orderType" label="类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getOrderTypeTagType(row.orderType)" size="small">
              {{ getOrderTypeText(row.orderType) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="direction" label="方向" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 'buy' ? 'danger' : 'success'" size="small">
              {{ row.type === 'buy' ? '买入' : '卖出' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="price" label="限价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.price">¥{{ formatPrice(row.price) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="quantity" label="数量" width="100" align="right">
          <template #default="{ row }">
            {{ formatAmount(row.quantity, 0) }}
          </template>
        </el-table-column>

        <el-table-column prop="filledQuantity" label="已成交" width="100" align="right">
          <template #default="{ row }">
            <span :class="row.filledQuantity > 0 ? 'text-green-600 font-medium' : 'text-gray-400'">
              {{ formatAmount(row.filledQuantity, 0) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="avgPrice" label="成交均价" width="100" align="right">
          <template #default="{ row }">
            <span v-if="row.avgPrice">¥{{ formatPrice(row.avgPrice) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="source" label="信号来源" width="120">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.source || '-' }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="createTime" label="创建时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.createTime) }}
          </template>
        </el-table-column>

        <el-table-column prop="expireTime" label="过期时间" width="160">
          <template #default="{ row }">
            <span v-if="row.expireTime">{{ formatDateTime(row.expireTime) }}</span>
            <span v-else class="text-gray-400">-</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              type="danger"
              size="small"
              text
              @click="handleCancelOrder(row)"
            >
              取消
            </el-button>
            <el-button
              v-else-if="row.status === 'filled'"
              size="small"
              text
              @click="handleViewDetail(row)"
            >
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="mt-4 flex justify-end">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handlePageSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- 订单详情对话框 -->
    <el-dialog v-model="detailDialogVisible" title="订单详情" width="600px">
      <el-descriptions :column="2" border v-if="selectedOrder">
        <el-descriptions-item label="订单ID">
          {{ selectedOrder.id }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusTagType(selectedOrder.status)" size="small">
            {{ getStatusText(selectedOrder.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="股票代码">
          {{ selectedOrder.symbol }}
        </el-descriptions-item>
        <el-descriptions-item label="股票名称">
          {{ selectedOrder.symbolName }}
        </el-descriptions-item>
        <el-descriptions-item label="交易方向">
          <el-tag :type="selectedOrder.type === 'buy' || selectedOrder.type === 'BUY' ? 'danger' : 'success'" size="small">
            {{ selectedOrder.type === 'buy' || selectedOrder.type === 'BUY' ? '买入' : '卖出' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="订单类型">
          <el-tag :type="getOrderTypeTagType((selectedOrder as any).orderType || 'limit')" size="small">
            {{ getOrderTypeText((selectedOrder as any).orderType || 'limit') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="委托价格">
          ¥{{ formatPrice(selectedOrder.price) }}
        </el-descriptions-item>
        <el-descriptions-item label="委托数量">
          {{ selectedOrder.quantity }} 股
        </el-descriptions-item>
        <el-descriptions-item label="委托金额">
          ¥{{ formatAmount(selectedOrder.price * selectedOrder.quantity) }}
        </el-descriptions-item>
        <el-descriptions-item label="成交数量" v-if="selectedOrder.status === 'filled'">
          {{ (selectedOrder as any).filledQuantity || selectedOrder.quantity }} 股
        </el-descriptions-item>
        <el-descriptions-item label="成交均价" v-if="selectedOrder.status === 'filled'">
          ¥{{ formatPrice((selectedOrder as any).avgPrice || selectedOrder.price) }}
        </el-descriptions-item>
        <el-descriptions-item label="成交金额" v-if="selectedOrder.status === 'filled'">
          ¥{{ formatAmount(((selectedOrder as any).avgPrice || selectedOrder.price) * selectedOrder.quantity) }}
        </el-descriptions-item>
        <el-descriptions-item label="手续费" v-if="selectedOrder.status === 'filled'">
          ¥{{ formatAmount((selectedOrder as any).commission || 0) }}
        </el-descriptions-item>
        <el-descriptions-item label="信号来源">
          {{ (selectedOrder as any).source || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="操作员">
          {{ selectedOrder.operator }}
        </el-descriptions-item>
        <el-descriptions-item label="创建时间" :span="2">
          {{ formatDateTime((selectedOrder as any).createTime || selectedOrder.createdAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="成交时间" :span="2" v-if="selectedOrder.filledAt">
          {{ formatDateTime(selectedOrder.filledAt) }}
        </el-descriptions-item>
        <el-descriptions-item label="过期时间" :span="2" v-if="(selectedOrder as any).expireTime">
          {{ formatDateTime((selectedOrder as any).expireTime) }}
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2" v-if="(selectedOrder as any).remark">
          {{ (selectedOrder as any).remark }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
        <el-button
          v-if="selectedOrder && selectedOrder.status === 'pending'"
          type="danger"
          @click="handleCancelOrderFromDetail"
        >
          取消订单
        </el-button>
      </template>
    </el-dialog>

    <!-- 新建订单对话框 -->
    <el-dialog v-model="createDialogVisible" title="新建订单" width="500px">
      <el-form :model="orderForm" :rules="orderRules" ref="orderFormRef" label-width="100px">
        <el-form-item label="股票代码" prop="symbol">
          <el-autocomplete
            v-model="orderForm.symbol"
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

        <el-form-item label="交易方向" prop="direction">
          <el-radio-group v-model="orderForm.direction">
            <el-radio label="buy">买入</el-radio>
            <el-radio label="sell">卖出</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="订单类型" prop="orderType">
          <el-radio-group v-model="orderForm.orderType">
            <el-radio label="market">市价单</el-radio>
            <el-radio label="limit">限价单</el-radio>
            <el-radio label="stop">止损单</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="价格" prop="price" v-if="orderForm.orderType !== 'market'">
          <el-input-number v-model="orderForm.price" :min="0" :step="0.01" :precision="2" class="w-full" />
        </el-form-item>

        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="orderForm.quantity" :min="100" :step="100" class="w-full" />
        </el-form-item>

        <el-form-item label="过期时间" prop="expireTime" v-if="orderForm.orderType === 'limit'">
          <el-date-picker
            v-model="orderForm.expireTime"
            type="datetime"
            placeholder="选择过期时间"
            class="w-full"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleConfirmCreate" :loading="createLoading">
          提交订单
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { tradingApi, stockApi } from '@/services/api'
import { formatPrice, formatAmount, formatDateTime } from '@/utils/format'
import type { Order } from '@/types/models'

// 订单列表
const orders = ref<Order[]>([])
const loading = ref(false)

// 订单详情对话框
const detailDialogVisible = ref(false)
const selectedOrder = ref<Order | null>(null)

// 筛选条件
const filters = reactive<{
  status: string
  type: string
  direction: '' | 'buy' | 'sell'
}>({
  status: '',
  type: '',
  direction: ''
})

// 分页
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

// 新建订单对话框
const createDialogVisible = ref(false)
const createLoading = ref(false)
const orderFormRef = ref<FormInstance>()
const orderForm = reactive({
  symbol: '',
  direction: 'buy' as 'buy' | 'sell',
  orderType: 'market' as 'market' | 'limit' | 'stop',
  price: 0,
  quantity: 100,
  expireTime: null as Date | null
})

const orderRules: FormRules = {
  symbol: [{ required: true, message: '请输入股票代码', trigger: 'blur' }],
  direction: [{ required: true, message: '请选择交易方向', trigger: 'change' }],
  orderType: [{ required: true, message: '请选择订单类型', trigger: 'change' }],
  price: [{ required: true, message: '请输入价格', trigger: 'blur' }],
  quantity: [{ required: true, message: '请输入数量', trigger: 'blur' }]
}

// 加载订单列表
const loadOrders = async () => {
  loading.value = true
  try {
    const data = await tradingApi.getOrders({
      status: filters.status || undefined,
      type: (filters.type === 'buy' || filters.type === 'sell') ? filters.type : undefined,
      page: pagination.page,
      pageSize: pagination.pageSize
    })
    orders.value = data.items
    pagination.total = data.total
  } catch (error) {
    ElMessage.error('加载订单列表失败')
  } finally {
    loading.value = false
  }
}

// 筛选变化
const handleFilterChange = () => {
  pagination.page = 1
  loadOrders()
}

// 刷新
const handleRefresh = () => {
  loadOrders()
}

// 分页
const handlePageChange = () => {
  loadOrders()
}

const handlePageSizeChange = () => {
  pagination.page = 1
  loadOrders()
}

// 新建订单
const handleCreateOrder = () => {
  createDialogVisible.value = true
}

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
  orderForm.symbol = item.symbol
}

// 确认创建订单
const handleConfirmCreate = async () => {
  if (!orderFormRef.value) return

  await orderFormRef.value.validate(async (valid) => {
    if (!valid) return

    createLoading.value = true
    try {
      await tradingApi.createOrder({
        symbol: orderForm.symbol,
        type: orderForm.direction,
        priceType: orderForm.orderType,
        price: orderForm.orderType !== 'market' ? orderForm.price : undefined,
        quantity: orderForm.quantity
        // TODO: Add expireTime support to API
        // expireTime: orderForm.expireTime?.toISOString()
      })

      ElMessage.success('订单已提交')
      createDialogVisible.value = false
      orderFormRef.value?.resetFields()

      // 刷新列表
      loadOrders()
    } catch (error) {
      ElMessage.error('提交订单失败')
    } finally {
      createLoading.value = false
    }
  })
}

// 取消订单
const handleCancelOrder = async (order: Order) => {
  try {
    await ElMessageBox.confirm(
      `确认取消订单 #${order.id}？`,
      '取消订单',
      { type: 'warning' }
    )

    await tradingApi.cancelOrder(order.id)
    ElMessage.success('订单已取消')

    // 刷新列表
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消订单失败')
    }
  }
}

// 查看详情
const handleViewDetail = (order: Order) => {
  selectedOrder.value = order
  detailDialogVisible.value = true
}

// 从详情对话框取消订单
const handleCancelOrderFromDetail = async () => {
  if (!selectedOrder.value) return

  try {
    await ElMessageBox.confirm(
      `确认取消订单 #${selectedOrder.value.id}？`,
      '取消订单',
      { type: 'warning' }
    )

    await tradingApi.cancelOrder(selectedOrder.value.id)
    ElMessage.success('订单已取消')

    detailDialogVisible.value = false
    selectedOrder.value = null

    // 刷新列表
    loadOrders()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('取消订单失败')
    }
  }
}

// 工具函数
const getOrderTypeTagType = (type: string) => {
  const typeMap: Record<string, any> = {
    'market': 'success',
    'limit': '',
    'stop': 'warning'
  }
  return typeMap[type] || 'info'
}

const getOrderTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    'market': '市价单',
    'limit': '限价单',
    'stop': '止损单'
  }
  return textMap[type] || type
}

const getStatusTagType = (status: string) => {
  const typeMap: Record<string, any> = {
    'pending': 'warning',
    'filled': 'success',
    'cancelled': 'info',
    'rejected': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'pending': '待成交',
    'filled': '已成交',
    'cancelled': '已取消',
    'rejected': '已拒绝'
  }
  return textMap[status] || status
}

// 组件挂载
onMounted(() => {
  loadOrders()
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'Orders'
})
</script>

<style scoped lang="scss">
.orders {
  :deep(.el-input-number) {
    width: 100%;
  }
}
</style>
