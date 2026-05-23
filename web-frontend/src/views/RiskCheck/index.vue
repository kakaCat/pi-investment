<template>
  <div class="risk-check">
    <!-- 顶部操作栏 -->
    <el-card class="mb-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">风控检查</h2>
        <div class="flex items-center gap-3">
          <el-input-number
            v-model="accountValue"
            :min="0"
            :step="10000"
            placeholder="账户总值"
            style="width: 180px"
          />
          <el-button type="primary" @click="handleRunCheck" :loading="loading">
            执行检查
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 风险概览卡片 -->
    <div class="grid grid-cols-4 gap-4 mb-4">
      <el-card class="stat-card">
        <div class="stat-label">总体风险等级</div>
        <div :class="['stat-value', getRiskLevelColor(riskOverview.level)]">
          {{ getRiskLevelText(riskOverview.level) }}
        </div>
        <div class="stat-sub">Level {{ riskOverview.level }} / 5</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">预警数量</div>
        <div class="stat-value">{{ riskOverview.warningCount }}</div>
        <div class="stat-sub">{{ riskOverview.criticalCount }} 严重</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">VaR (95%)</div>
        <div class="stat-value text-down">{{ formatPercent(riskOverview.var) }}</div>
        <div class="stat-sub">¥{{ formatPrice(Math.abs(riskOverview.varAmount)) }}</div>
      </el-card>

      <el-card class="stat-card">
        <div class="stat-label">组合波动率</div>
        <div class="stat-value">{{ formatPercent(riskOverview.volatility) }}</div>
      </el-card>
    </div>

    <!-- 风险指标 -->
    <el-card class="mb-4">
      <template #header>
        <span class="font-semibold">风险指标</span>
      </template>

      <div class="grid grid-cols-2 gap-4">
        <div v-for="indicator in riskIndicators" :key="indicator.name" class="risk-indicator">
          <div class="flex items-center justify-between mb-2">
            <span class="font-medium">{{ indicator.name }}</span>
            <el-tag :type="getIndicatorTagType(indicator.status)" size="small">
              {{ indicator.status }}
            </el-tag>
          </div>
          <el-progress
            :percentage="indicator.value"
            :color="getIndicatorColor(indicator.value, indicator.threshold)"
            :stroke-width="12"
          />
          <div class="flex items-center justify-between mt-1 text-xs text-gray-500">
            <span>当前: {{ indicator.value.toFixed(1) }}%</span>
            <span>阈值: {{ indicator.threshold }}%</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 持仓风险明细 -->
    <el-card>
      <template #header>
        <span class="font-semibold">持仓风险明细</span>
      </template>

      <el-table :data="positionRisks" stripe v-loading="loading">
        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }">
            <router-link :to="{ name: 'StockDetail', params: { symbol: row.symbol } }" class="text-blue-600 hover:underline font-medium">
              {{ row.symbol }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="name" label="名称" width="120" />

        <el-table-column prop="marketValue" label="持仓市值" width="120" align="right">
          <template #default="{ row }">
            ¥{{ formatPrice(row.marketValue) }}
          </template>
        </el-table-column>

        <el-table-column prop="positionPercent" label="占比" width="100" align="right">
          <template #default="{ row }">
            {{ row.positionPercent.toFixed(1) }}%
          </template>
        </el-table-column>

        <el-table-column prop="var" label="VaR 95%" width="100" align="right">
          <template #default="{ row }">
            <span class="text-down">{{ formatPercent(row.var) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="volatility" label="波动率" width="100" align="right">
          <template #default="{ row }">
            {{ formatPercent(row.volatility) }}
          </template>
        </el-table-column>

        <el-table-column prop="maxDrawdown" label="最大回撤" width="100" align="right">
          <template #default="{ row }">
            <span class="text-down">{{ formatPercent(row.maxDrawdown) }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="checksPassed" label="检查项" width="100" align="center">
          <template #default="{ row }">
            <span class="text-xs text-gray-500">{{ row.checksPassed }}/{{ row.totalChecks }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)" size="small">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text @click="handleViewDetail(row)">
              详情
            </el-button>
            <el-button size="small" text type="primary" @click="handleSetStopLoss(row)">
              设置止损
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 批量操作 -->
      <div class="mt-4 flex items-center justify-between">
        <el-button @click="handleBatchSetStopLoss" :disabled="positionRisks.length === 0">
          批量设置止损
        </el-button>
      </div>
    </el-card>

    <!-- 风险预警列表 -->
    <el-card class="mt-4" v-if="warnings.length > 0">
      <template #header>
        <span class="font-semibold">风险预警</span>
      </template>

      <el-table :data="warnings" stripe>
        <el-table-column prop="time" label="时间" width="160">
          <template #default="{ row }">
            {{ formatDateTime(row.time) }}
          </template>
        </el-table-column>

        <el-table-column prop="type" label="风险类型" width="150">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="level" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="getWarningLevelType(row.level)" size="small">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="description" label="描述" min-width="200" show-overflow-tooltip />

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'pending' ? 'warning' : 'success'" size="small">
              {{ row.status === 'pending' ? '待处理' : '已处理' }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'pending'"
              size="small"
              type="primary"
              text
              @click="handleMarkResolved(row)"
            >
              标记已处理
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 止损规则设置弹窗 -->
    <el-dialog v-model="stopLossDialogVisible" title="设置止损规则" width="500px">
      <el-form :model="stopLossForm" label-width="100px">
        <el-form-item label="股票代码">
          <el-input v-model="stopLossForm.symbol" disabled />
        </el-form-item>
        <el-form-item label="股票名称">
          <el-input v-model="stopLossForm.symbolName" disabled />
        </el-form-item>
        <el-form-item label="当前价格">
          <div class="text-lg font-semibold">¥{{ formatPrice(stopLossForm.currentPrice) }}</div>
        </el-form-item>
        <el-form-item label="止损类型">
          <el-radio-group v-model="stopLossForm.type">
            <el-radio label="price">固定价格</el-radio>
            <el-radio label="percent">百分比</el-radio>
            <el-radio label="trailing">追踪止损</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="stopLossForm.type === 'price'" label="止损价格">
          <el-input-number
            v-model="stopLossForm.triggerPrice"
            :min="0"
            :step="0.01"
            :precision="2"
            class="w-full"
          />
          <div class="text-xs text-gray-500 mt-1">
            跌幅: {{ calculatePricePercent(stopLossForm.triggerPrice, stopLossForm.currentPrice) }}
          </div>
        </el-form-item>
        <el-form-item v-if="stopLossForm.type === 'percent'" label="止损比例">
          <el-input-number
            v-model="stopLossForm.triggerPercent"
            :min="0"
            :max="100"
            :step="1"
            :precision="1"
            class="w-full"
          />
          <div class="text-xs text-gray-500 mt-1">
            触发价格: ¥{{ calculatePercentPrice(stopLossForm.triggerPercent, stopLossForm.currentPrice) }}
          </div>
        </el-form-item>
        <el-form-item v-if="stopLossForm.type === 'trailing'" label="追踪比例">
          <el-input-number
            v-model="stopLossForm.trailingPercent"
            :min="0"
            :max="100"
            :step="1"
            :precision="1"
            class="w-full"
          />
          <div class="text-xs text-gray-500 mt-1">
            当价格回撤超过 {{ stopLossForm.trailingPercent }}% 时触发
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stopLossDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveStopLoss" :loading="savingStopLoss">
          保存
        </el-button>
      </template>
    </el-dialog>

    <!-- 批量设置止损弹窗 -->
    <el-dialog v-model="batchStopLossDialogVisible" title="批量设置止损" width="500px">
      <el-form :model="batchStopLossForm" label-width="100px">
        <el-form-item label="止损类型">
          <el-radio-group v-model="batchStopLossForm.type">
            <el-radio label="percent">百分比</el-radio>
            <el-radio label="trailing">追踪止损</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="batchStopLossForm.type === 'percent'" label="止损比例">
          <el-input-number
            v-model="batchStopLossForm.triggerPercent"
            :min="0"
            :max="100"
            :step="1"
            :precision="1"
            class="w-full"
          />
          <div class="text-xs text-gray-500 mt-1">
            将为所有持仓设置相同的止损比例
          </div>
        </el-form-item>
        <el-form-item v-if="batchStopLossForm.type === 'trailing'" label="追踪比例">
          <el-input-number
            v-model="batchStopLossForm.trailingPercent"
            :min="0"
            :max="100"
            :step="1"
            :precision="1"
            class="w-full"
          />
          <div class="text-xs text-gray-500 mt-1">
            将为所有持仓设置相同的追踪止损比例
          </div>
        </el-form-item>
        <el-form-item label="应用范围">
          <el-checkbox-group v-model="batchStopLossForm.symbols">
            <div v-for="position in positionRisks" :key="position.symbol" class="mb-2">
              <el-checkbox :label="position.symbol">
                {{ position.symbol }} {{ position.name }}
              </el-checkbox>
            </div>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="batchStopLossDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSaveBatchStopLoss" :loading="savingStopLoss">
          批量设置
        </el-button>
      </template>
    </el-dialog>

    <!-- 止损规则列表 -->
    <el-card class="mt-4" v-if="stopLossRules.length > 0">
      <template #header>
        <span class="font-semibold">止损规则</span>
      </template>

      <el-table :data="stopLossRules" stripe>
        <el-table-column prop="symbol" label="代码" width="120">
          <template #default="{ row }">
            <router-link :to="{ name: 'StockDetail', params: { symbol: row.symbol } }" class="text-blue-600 hover:underline font-medium">
              {{ row.symbol }}
            </router-link>
          </template>
        </el-table-column>

        <el-table-column prop="symbolName" label="名称" width="120" />

        <el-table-column prop="type" label="类型" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ getStopLossTypeText(row.type) }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="触发条件" width="200">
          <template #default="{ row }">
            <span v-if="row.type === 'price'">¥{{ formatPrice(row.triggerPrice) }}</span>
            <span v-else-if="row.type === 'percent'">-{{ row.triggerPercent }}%</span>
            <span v-else-if="row.type === 'trailing'">回撤 {{ row.trailingPercent }}%</span>
          </template>
        </el-table-column>

        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStopLossStatusType(row.status)" size="small">
              {{ getStopLossStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="createdAt" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.createdAt) }}
          </template>
        </el-table-column>

        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'active'"
              size="small"
              text
              type="primary"
              @click="handleEditStopLoss(row)"
            >
              编辑
            </el-button>
            <el-button
              v-if="row.status === 'active'"
              size="small"
              text
              type="danger"
              @click="handleDeleteStopLoss(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { riskApi } from '@/services/api'
import { formatPrice, formatPercent, formatDateTime } from '@/utils/format'
import type { StopLossRule } from '@/types/models'

const router = useRouter()

// 账户总值
const accountValue = ref(1258400)
const loading = ref(false)

// 风险概览
const riskOverview = reactive({
  level: 2,
  warningCount: 3,
  criticalCount: 1,
  var: -0.032,
  varAmount: -40269,
  volatility: 0.158
})

// 风险指标
const riskIndicators = ref([
  { name: '持仓集中度', value: 26.7, threshold: 30, status: '正常' },
  { name: '单票风险敞口', value: 26.7, threshold: 30, status: '正常' },
  { name: '行业集中度', value: 45.2, threshold: 50, status: '正常' },
  { name: '最大回撤', value: 15.3, threshold: 20, status: '正常' },
  { name: '波动率', value: 15.8, threshold: 25, status: '正常' },
  { name: 'VaR风险价值', value: 3.2, threshold: 5, status: '正常' }
])

// 持仓风险
const positionRisks = ref<any[]>([])

// 风险预警
const warnings = ref<any[]>([])

// 止损规则
const stopLossRules = ref<StopLossRule[]>([])
const stopLossDialogVisible = ref(false)
const batchStopLossDialogVisible = ref(false)
const savingStopLoss = ref(false)

// 止损表单
const stopLossForm = reactive({
  id: '',
  symbol: '',
  symbolName: '',
  currentPrice: 0,
  type: 'percent' as 'price' | 'percent' | 'trailing',
  triggerPrice: 0,
  triggerPercent: 5,
  trailingPercent: 10
})

// 批量止损表单
const batchStopLossForm = reactive({
  type: 'percent' as 'percent' | 'trailing',
  triggerPercent: 5,
  trailingPercent: 10,
  symbols: [] as string[]
})

// 执行风控检查
const handleRunCheck = async () => {
  loading.value = true
  try {
    const result = await riskApi.checkRisk({
      accountValue: accountValue.value,
      positions: []
    })

    // 更新数据
    Object.assign(riskOverview, {
      riskLevel: result.riskLevel,
      riskScore: result.riskScore,
      var: result.var,
      maxDrawdown: result.maxDrawdown
    })

    ElMessage.success('风控检查完成')
  } catch (error) {
    ElMessage.error('风控检查失败')
  } finally {
    loading.value = false
  }
}

// 加载止损规则
const loadStopLossRules = async () => {
  try {
    const data = await riskApi.getStopLossRules()
    stopLossRules.value = data
  } catch (error) {
    console.error('加载止损规则失败', error)
  }
}

// 设置止损
const handleSetStopLoss = (row: any) => {
  stopLossForm.id = ''
  stopLossForm.symbol = row.symbol
  stopLossForm.symbolName = row.name
  stopLossForm.currentPrice = row.currentPrice || 0
  stopLossForm.type = 'percent'
  stopLossForm.triggerPrice = stopLossForm.currentPrice * 0.95
  stopLossForm.triggerPercent = 5
  stopLossForm.trailingPercent = 10
  stopLossDialogVisible.value = true
}

// 编辑止损
const handleEditStopLoss = (rule: StopLossRule) => {
  stopLossForm.id = rule.id
  stopLossForm.symbol = rule.symbol
  stopLossForm.symbolName = rule.symbolName || ''
  stopLossForm.currentPrice = 0 // 需要从持仓中获取
  stopLossForm.type = rule.type
  stopLossForm.triggerPrice = rule.triggerPrice || 0
  stopLossForm.triggerPercent = rule.triggerPercent || 5
  stopLossForm.trailingPercent = rule.trailingPercent || 10
  stopLossDialogVisible.value = true
}

// 保存止损
const handleSaveStopLoss = async () => {
  savingStopLoss.value = true
  try {
    const data: any = {
      symbol: stopLossForm.symbol,
      type: stopLossForm.type
    }

    if (stopLossForm.type === 'price') {
      data.triggerPrice = stopLossForm.triggerPrice
    } else if (stopLossForm.type === 'percent') {
      data.triggerPercent = stopLossForm.triggerPercent
    } else if (stopLossForm.type === 'trailing') {
      data.trailingPercent = stopLossForm.trailingPercent
    }

    if (stopLossForm.id) {
      await riskApi.updateStopLossRule(stopLossForm.id, data)
      ElMessage.success('止损规则已更新')
    } else {
      await riskApi.createStopLossRule(data)
      ElMessage.success('止损规则已创建')
    }

    stopLossDialogVisible.value = false
    loadStopLossRules()
  } catch (error) {
    ElMessage.error('保存止损规则失败')
  } finally {
    savingStopLoss.value = false
  }
}

// 批量设置止损
const handleBatchSetStopLoss = () => {
  batchStopLossForm.type = 'percent'
  batchStopLossForm.triggerPercent = 5
  batchStopLossForm.trailingPercent = 10
  batchStopLossForm.symbols = positionRisks.value.map(p => p.symbol)
  batchStopLossDialogVisible.value = true
}

// 保存批量止损
const handleSaveBatchStopLoss = async () => {
  if (batchStopLossForm.symbols.length === 0) {
    ElMessage.warning('请选择至少一个股票')
    return
  }

  savingStopLoss.value = true
  try {
    const rules = batchStopLossForm.symbols.map(symbol => {
      const data: any = {
        symbol,
        type: batchStopLossForm.type
      }

      if (batchStopLossForm.type === 'percent') {
        data.triggerPercent = batchStopLossForm.triggerPercent
      } else if (batchStopLossForm.type === 'trailing') {
        data.trailingPercent = batchStopLossForm.trailingPercent
      }

      return data
    })

    await riskApi.batchCreateStopLossRules(rules)
    ElMessage.success(`已为 ${rules.length} 个股票设置止损规则`)

    batchStopLossDialogVisible.value = false
    loadStopLossRules()
  } catch (error) {
    ElMessage.error('批量设置止损规则失败')
  } finally {
    savingStopLoss.value = false
  }
}

// 删除止损
const handleDeleteStopLoss = async (rule: StopLossRule) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${rule.symbol} 的止损规则吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )

    await riskApi.deleteStopLossRule(rule.id)
    ElMessage.success('止损规则已删除')
    loadStopLossRules()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除止损规则失败')
    }
  }
}

// 查看详情
const handleViewDetail = (row: any) => {
  router.push({ name: 'StockDetail', params: { symbol: row.symbol } })
}

// 标记已处理
const handleMarkResolved = async (warning: any) => {
  try {
    warning.status = 'resolved'
    ElMessage.success('已标记为已处理')
  } catch (error) {
    ElMessage.error('操作失败')
  }
}

// 计算价格对应的百分比
const calculatePricePercent = (price: number, currentPrice: number) => {
  if (currentPrice === 0) return '0%'
  const percent = ((price - currentPrice) / currentPrice) * 100
  return `${percent >= 0 ? '+' : ''}${percent.toFixed(2)}%`
}

// 计算百分比对应的价格
const calculatePercentPrice = (percent: number, currentPrice: number) => {
  const price = currentPrice * (1 - percent / 100)
  return formatPrice(price)
}

// 工具函数
const getRiskLevelColor = (level: number) => {
  if (level <= 1) return 'text-green-600'
  if (level <= 2) return 'text-yellow-600'
  if (level <= 3) return 'text-orange-600'
  return 'text-red-600'
}

const getRiskLevelText = (level: number) => {
  const texts = ['低风险', '低风险', '中风险', '高风险', '严重风险', '极高风险']
  return texts[level] || '未知'
}

const getIndicatorTagType = (status: string) => {
  const typeMap: Record<string, any> = {
    '正常': 'success',
    '关注': 'warning',
    '预警': 'danger'
  }
  return typeMap[status] || 'info'
}

const getIndicatorColor = (value: number, threshold: number) => {
  const ratio = value / threshold
  if (ratio < 0.7) return '#67c23a'
  if (ratio < 0.9) return '#e6a23c'
  return '#f56c6c'
}

const getStatusTagType = (status: string) => {
  const typeMap: Record<string, any> = {
    'normal': 'success',
    'warning': 'warning',
    'danger': 'danger'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'normal': '正常',
    'warning': '⚠ 关注',
    'danger': '⚠ 预警'
  }
  return textMap[status] || status
}

const getWarningLevelType = (level: string) => {
  const typeMap: Record<string, any> = {
    '低': 'info',
    '中': 'warning',
    '高': 'danger',
    '严重': 'danger'
  }
  return typeMap[level] || 'info'
}

const getStopLossTypeText = (type: string) => {
  const textMap: Record<string, string> = {
    'price': '固定价格',
    'percent': '百分比',
    'trailing': '追踪止损'
  }
  return textMap[type] || type
}

const getStopLossStatusType = (status: string) => {
  const typeMap: Record<string, any> = {
    'active': 'success',
    'triggered': 'warning',
    'cancelled': 'info'
  }
  return typeMap[status] || 'info'
}

const getStopLossStatusText = (status: string) => {
  const textMap: Record<string, string> = {
    'active': '生效中',
    'triggered': '已触发',
    'cancelled': '已取消'
  }
  return textMap[status] || status
}

// 组件挂载
onMounted(() => {
  handleRunCheck()
  loadStopLossRules()
})
</script>

<script lang="ts">
import { defineComponent } from 'vue'
export default defineComponent({
  name: 'RiskCheck'
})
</script>

<style scoped lang="scss">
.risk-check {
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

  .risk-indicator {
    padding: 16px;
    background: #f8fafc;
    border-radius: 8px;
  }
}
</style>
