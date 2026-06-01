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
      <el-tag v-for="t in pool.filter_template?.technical || []" :key="t" size="small" style="margin-right: 4px;">{{ filterLabels[t] || t }}</el-tag>
      <el-tag v-for="f in pool.filter_template?.fundamental || []" :key="f" type="warning" size="small" style="margin-right: 4px;">{{ filterLabels[f] || f }}</el-tag>
      <el-tag v-if="pool.filter_template?.min_score" type="info" size="small" style="margin-right: 4px;">最低分: {{ pool.filter_template.min_score }}</el-tag>
      <el-tag v-if="pool.filter_template?.top_n" type="info" size="small">Top {{ pool.filter_template.top_n }}</el-tag>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" style="margin-top: 24px;">
      <!-- 成员列表 Tab -->
      <el-tab-pane label="成员列表" name="members">
        <el-table :data="memberRows" stripe>
          <el-table-column prop="index" label="序号" width="80" />
          <el-table-column prop="symbol" label="股票代码" />
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
          <el-table :data="validation.recommended_pairs || []" stripe style="margin-top: 8px;">
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="symbol" label="股票代码" />
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox, ElLoading } from 'element-plus'
import { poolApi } from '@/services/api'

const router = useRouter()
const route = useRoute()
const poolId = computed(() => Number(route.params.id))

const loading = ref(false)
const refreshing = ref(false)
const submitting = ref(false)
const pool = ref<any>({})
const activeTab = ref('members')

const validation = computed(() => pool.value.last_validation)
const memberRows = computed(() =>
  (pool.value.symbols || []).map((s: string, i: number) => ({ index: i + 1, symbol: s }))
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
</style>
