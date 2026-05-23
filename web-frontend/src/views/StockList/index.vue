<template>
  <div class="stock-list-page">
    <!-- 工具栏 -->
    <el-card shadow="never" class="mb-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <!-- 搜索框 -->
          <el-input
            v-model="searchKeyword"
            placeholder="搜索股票代码或名称..."
            :prefix-icon="Search"
            clearable
            style="width: 320px"
            @input="handleSearch"
          />

          <!-- 市场筛选 -->
          <el-select
            v-model="selectedMarket"
            placeholder="全部市场"
            style="width: 150px"
            @change="handleMarketChange"
          >
            <el-option label="全部市场" value="" />
            <el-option label="上海 (SH)" value="SH" />
            <el-option label="深圳 (SZ)" value="SZ" />
            <el-option label="港股 (HK)" value="HK" />
            <el-option label="美股 (US)" value="US" />
          </el-select>

          <!-- 行业筛选 -->
          <el-select
            v-model="selectedIndustry"
            placeholder="全部行业"
            style="width: 150px"
            clearable
            @change="fetchStocks"
          >
            <el-option label="全部行业" value="" />
            <el-option label="白酒" value="白酒" />
            <el-option label="电池" value="电池" />
            <el-option label="保险" value="保险" />
            <el-option label="互联网" value="互联网" />
            <el-option label="半导体" value="半导体" />
            <el-option label="新能源" value="新能源" />
          </el-select>
        </div>

        <div class="flex items-center gap-2">
          <el-button type="primary" @click="showAddStockDialog">
            <el-icon class="mr-1"><Plus /></el-icon>
            添加股票
          </el-button>
          <el-button @click="handleCompare" :disabled="selectedStocks.length === 0">
            对比选中 ({{ selectedStocks.length }}/5)
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 股票列表 -->
    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="stocks"
        @selection-change="handleSelectionChange"
        stripe
      >
        <el-table-column type="selection" width="55" :selectable="checkSelectable" />

        <el-table-column prop="code" label="代码" width="120">
          <template #default="{ row }">
            <router-link
              :to="`/stock/${row.code}`"
              class="text-blue-600 font-medium hover:underline"
            >
              {{ row.code }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120" />

        <el-table-column prop="market" label="市场" width="80">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.market }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="industry" label="行业" width="100" />

        <el-table-column prop="price" label="最新收盘价" width="120" align="right">
          <template #default="{ row }">
            <span class="font-medium">{{ formatPrice(row.price) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="changePercent" label="涨跌幅" width="100" align="right">
          <template #default="{ row }">
            <span :class="getChangeClass(row.changePercent)" class="font-medium">
              {{ formatPercent(row.changePercent) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column prop="klineDays" label="K线天数" width="100" align="right" />

        <el-table-column prop="factorCount" label="因子数" width="80" align="right" />

        <el-table-column prop="dataStatus" label="数据状态" width="100">
          <template #default="{ row }">
            <el-tag
              :type="row.dataStatus === 'complete' ? 'success' : 'warning'"
              size="small"
            >
              {{ row.dataStatus === 'complete' ? '完整' : '不完整' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              @click="viewDetail(row.code)"
            >
              详情 →
            </el-button>
            <el-button
              type="primary"
              link
              @click="addToFavorites(row)"
            >
              {{ row.isFavorite ? '已自选' : '加自选' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="mt-4 flex items-center justify-between">
        <span class="text-sm text-gray-500">共 {{ total }} 只股票</span>
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[20, 50, 100]"
          layout="prev, pager, next, sizes"
          @current-change="fetchStocks"
          @size-change="fetchStocks"
        />
      </div>
    </el-card>

    <!-- 添加股票对话框 -->
    <el-dialog
      v-model="addStockDialogVisible"
      title="添加股票"
      width="500px"
    >
      <el-form :model="addStockForm" label-width="80px">
        <el-form-item label="股票代码">
          <el-input
            v-model="addStockForm.code"
            placeholder="例如: 600519.SH"
          />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input
            v-model="addStockForm.name"
            placeholder="例如: 贵州茅台"
          />
        </el-form-item>
        <el-form-item label="市场">
          <el-select v-model="addStockForm.market" style="width: 100%">
            <el-option label="上海 (SH)" value="SH" />
            <el-option label="深圳 (SZ)" value="SZ" />
            <el-option label="港股 (HK)" value="HK" />
            <el-option label="美股 (US)" value="US" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addStockDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleAddStock">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, Plus } from '@element-plus/icons-vue'
import { stockApi } from '@/services/api'
import { formatPrice, formatPercent, getChangeClass } from '@/utils/format'
import type { StockInfo } from '@/types/models'

const router = useRouter()

// 状态
const loading = ref(false)
const stocks = ref<StockInfo[]>([])
const selectedStocks = ref<StockInfo[]>([])
const searchKeyword = ref('')
const selectedMarket = ref('')
const selectedIndustry = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 添加股票对话框
const addStockDialogVisible = ref(false)
const addStockForm = ref({
  code: '',
  name: '',
  market: 'SH'
})

// 获取股票列表
const fetchStocks = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      pageSize: pageSize.value,
      keyword: searchKeyword.value,
      market: selectedMarket.value,
      industry: selectedIndustry.value
    }
    const data = await stockApi.getStocks(params)
    stocks.value = data.items
    total.value = data.total
  } catch (error) {
    ElMessage.error('获取股票列表失败')
  } finally {
    loading.value = false
  }
}

// 搜索
let searchTimer: number | null = null
const handleSearch = () => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    currentPage.value = 1
    fetchStocks()
  }, 500)
}

// 市场筛选
const handleMarketChange = () => {
  currentPage.value = 1
  fetchStocks()
}

// 选择变化
const handleSelectionChange = (selection: StockInfo[]) => {
  selectedStocks.value = selection
}

// 检查是否可选择（最多5个）
const checkSelectable = (row: StockInfo) => {
  if (selectedStocks.value.length >= 5) {
    return selectedStocks.value.some(s => (s.code || s.symbol) === (row.code || row.symbol))
  }
  return true
}

// 查看详情
const viewDetail = (code: string) => {
  router.push(`/stock/${code}`)
}

// 添加到自选
const addToFavorites = async (stock: StockInfo) => {
  try {
    if ((stock as any).isFavorite) {
      ElMessage.info('已在自选列表中')
    } else {
      // 调用API添加自选
      ElMessage.success('已添加到自选')
      ;(stock as any).isFavorite = true
    }
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 对比选中
const handleCompare = () => {
  if (selectedStocks.value.length === 0) {
    ElMessage.warning('请至少选择一只股票')
    return
  }
  if (selectedStocks.value.length > 5) {
    ElMessage.warning('最多选择5只股票进行对比')
    return
  }
  const codes = selectedStocks.value.map(s => s.code || s.symbol).join(',')
  router.push(`/factor-analysis?stocks=${codes}`)
}

// 显示添加股票对话框
const showAddStockDialog = () => {
  addStockForm.value = {
    code: '',
    name: '',
    market: 'SH'
  }
  addStockDialogVisible.value = true
}

// 添加股票
const handleAddStock = async () => {
  if (!addStockForm.value.code || !addStockForm.value.name) {
    ElMessage.warning('请填写完整信息')
    return
  }
  try {
    // 调用API添加股票
    ElMessage.success('添加成功')
    addStockDialogVisible.value = false
    fetchStocks()
  } catch (error) {
    ElMessage.error('添加失败')
  }
}

onMounted(() => {
  fetchStocks()
})
</script>

<style scoped>
.stock-list-page {
  padding: 20px;
}
</style>
