<template>
  <div class="pool-list-page">
    <!-- 统计卡片 -->
    <el-row :gutter="24">
      <el-col :xs="24" :sm="8">
        <el-card class="stat-card">
          <div class="stat-value">{{ pools.length }}</div>
          <div class="stat-label">📊 池子总数</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card class="stat-card">
          <div class="stat-value">{{ pools.filter(p => p.pool_type === 'static').length }}</div>
          <div class="stat-label">📌 静态池</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="8">
        <el-card class="stat-card">
          <div class="stat-value">{{ pools.filter(p => p.pool_type === 'dynamic').length }}</div>
          <div class="stat-label">🔄 动态池</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 操作栏 + 表格 -->
    <el-card style="margin-top: 24px;">
      <template #header>
        <div class="card-header">
          <span>股票池列表</span>
          <div>
            <el-button type="primary" @click="showCreateDialog = true">创建静态池</el-button>
            <el-button type="success" @click="showScanDialog = true">筛选建池</el-button>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="pools" stripe>
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="名称">
          <template #default="{ row }">
            <el-link type="primary" @click="router.push(`/pools/${row.id}`)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="pool_type" label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.pool_type === 'static' ? 'info' : 'success'" size="small">
              {{ row.pool_type === 'static' ? '静态' : '动态' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="symbol_count" label="股票数" width="80" />
        <el-table-column prop="refresh_interval" label="刷新周期" width="100">
          <template #default="{ row }">
            {{ row.refresh_interval || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="last_refreshed_at" label="上次刷新" width="150">
          <template #default="{ row }">
            {{ row.last_refreshed_at || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="has_validation" label="已验证" width="80">
          <template #default="{ row }">
            {{ row.has_validation ? '✅' : '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="150">
          <template #default="{ row }">
            {{ row.created_at?.slice(0, 19) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.pool_type === 'dynamic'"
              type="primary"
              link
              size="small"
              @click="handleRefresh(row.id)"
            >刷新</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row.id, row.name)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && pools.length === 0" description="暂无股票池" />
    </el-card>

    <!-- 创建静态池弹窗 -->
    <el-dialog v-model="showCreateDialog" title="创建静态池" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="createForm.name" placeholder="如：蓝筹精选池" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" placeholder="可选描述" />
        </el-form-item>
        <el-form-item label="股票代码" required>
          <el-input
            v-model="createForm.symbolsText"
            type="textarea"
            :rows="3"
            placeholder="逗号分隔，如 600519.SH, 000858.SZ, 000001.SZ"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 筛选建池弹窗 -->
    <el-dialog v-model="showScanDialog" title="筛选建池" width="600px">
      <el-form :model="scanForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="scanForm.name" placeholder="如：低估值蓝筹池" />
        </el-form-item>
        <el-form-item label="池子类型">
          <el-radio-group v-model="scanForm.poolType">
            <el-radio value="static">静态池</el-radio>
            <el-radio value="dynamic">动态池</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="技术面条件">
          <el-checkbox-group v-model="scanForm.technical">
            <el-checkbox value="rsi_oversold">RSI超卖</el-checkbox>
            <el-checkbox value="macd_golden_cross">MACD金叉</el-checkbox>
            <el-checkbox value="bollinger_breakout">布林突破</el-checkbox>
            <el-checkbox value="volume_surge">放量突破</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="基本面条件">
          <el-checkbox-group v-model="scanForm.fundamental">
            <el-checkbox value="pe_low">低PE</el-checkbox>
            <el-checkbox value="roe_high">高ROE</el-checkbox>
            <el-checkbox value="gross_margin_high">高毛利</el-checkbox>
            <el-checkbox value="debt_ratio_low">低负债</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="最低评分">
          <el-slider v-model="scanForm.minScore" :min="0" :max="100" :step="5" show-input />
        </el-form-item>
        <el-form-item label="取前N只">
          <el-input-number v-model="scanForm.topN" :min="5" :max="100" :step="5" />
        </el-form-item>
        <el-form-item label="刷新周期" v-if="scanForm.poolType === 'dynamic'">
          <el-radio-group v-model="scanForm.refreshInterval">
            <el-radio value="daily">每日</el-radio>
            <el-radio value="weekly">每周</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="scanForm.description" placeholder="可选描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showScanDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="handleScanCreate">筛选建池</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { poolApi } from '@/services/api'

const router = useRouter()
const loading = ref(false)
const submitting = ref(false)
const pools = ref<any[]>([])

// Create dialog
const showCreateDialog = ref(false)
const createForm = ref({
  name: '',
  description: '',
  symbolsText: '',
})

// Scan dialog
const showScanDialog = ref(false)
const scanForm = ref({
  name: '',
  poolType: 'dynamic' as 'static' | 'dynamic',
  technical: [] as string[],
  fundamental: [] as string[],
  minScore: 60,
  topN: 20,
  refreshInterval: 'weekly' as 'daily' | 'weekly',
  description: '',
})

const fetchPools = async () => {
  loading.value = true
  try {
    pools.value = await poolApi.list()
  } catch {
    ElMessage.error('获取股票池列表失败')
  } finally {
    loading.value = false
  }
}

const handleCreate = async () => {
  if (!createForm.value.name || !createForm.value.symbolsText) {
    ElMessage.warning('请填写名称和股票代码')
    return
  }
  submitting.value = true
  try {
    const symbols = createForm.value.symbolsText
      .split(/[,，\s]+/)
      .map(s => s.trim())
      .filter(Boolean)
    await poolApi.create({
      name: createForm.value.name,
      poolType: 'static',
      symbols,
      description: createForm.value.description || undefined,
    })
    ElMessage.success('创建成功')
    showCreateDialog.value = false
    createForm.value = { name: '', description: '', symbolsText: '' }
    await fetchPools()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    submitting.value = false
  }
}

const handleScanCreate = async () => {
  if (!scanForm.value.name) {
    ElMessage.warning('请填写名称')
    return
  }
  submitting.value = true
  try {
    await poolApi.scanAndCreate({
      name: scanForm.value.name,
      poolType: scanForm.value.poolType,
      filter: {
        technical: scanForm.value.technical,
        fundamental: scanForm.value.fundamental,
        min_score: scanForm.value.minScore,
        top_n: scanForm.value.topN,
      },
      refreshInterval: scanForm.value.poolType === 'dynamic' ? scanForm.value.refreshInterval : undefined,
      description: scanForm.value.description || undefined,
    })
    ElMessage.success('筛选建池成功')
    showScanDialog.value = false
    await fetchPools()
  } catch {
    ElMessage.error('筛选建池失败')
  } finally {
    submitting.value = false
  }
}

const handleRefresh = async (id: number) => {
  try {
    await poolApi.refresh(id)
    ElMessage.success('刷新成功')
    await fetchPools()
  } catch {
    ElMessage.error('刷新失败')
  }
}

const handleDelete = async (id: number, name: string) => {
  try {
    await ElMessageBox.confirm(`确定删除股票池「${name}」？`, '提示', { type: 'warning' })
    await poolApi.delete(id)
    ElMessage.success('删除成功')
    await fetchPools()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('删除失败')
  }
}

onMounted(() => { fetchPools() })
</script>

<style scoped>
.pool-list-page {
  padding: 24px;
}
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: var(--el-color-primary);
}
.stat-label {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
