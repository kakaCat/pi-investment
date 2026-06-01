# Pool Management Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stock pool management pages to web-frontend: a list page (`/pools`) and a detail page (`/pools/:id`) with pool CRUD, scan-and-create, and multi-strategy validation results display.

**Architecture:** Two new Vue 3 pages using Element Plus components, connected via a new `poolApi` service to the existing `/api/pools/*` backend. Follows the established pattern: `apiClient` wrapper, lazy-loaded route, `el-menu-item` in sidebar.

**Tech Stack:** Vue 3 / Composition API / Element Plus / Axios / vue-router

**Spec:** `docs/superpowers/specs/2026-06-01-pool-frontend-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `web-frontend/src/services/api/pool.ts` | Pool API service (CRUD + validate + scan-and-create) |
| `web-frontend/src/views/PoolList/index.vue` | Pool list page at `/pools` |
| `web-frontend/src/views/PoolDetail/index.vue` | Pool detail page at `/pools/:id` |

### Modified Files

| File | Change |
|------|--------|
| `web-frontend/src/services/api/index.ts` | Add `export { poolApi } from './pool'` |
| `web-frontend/src/router/index.ts` | Add `/pools` and `/pools/:id` routes |
| `web-frontend/src/components/layout/MainLayout.vue` | Add "股票池" menu item |

---

### Task 1: Pool API Service

**Files:**
- Create: `web-frontend/src/services/api/pool.ts`
- Modify: `web-frontend/src/services/api/index.ts`

- [ ] **Step 1: Create pool.ts API service**

```typescript
// web-frontend/src/services/api/pool.ts
import { apiClient } from './client'

export interface FilterTemplate {
  min_score?: number
  max_risk_level?: string
  technical?: string[]
  fundamental?: string[]
  top_n?: number
}

export interface PoolCreateParams {
  name: string
  poolType: 'static' | 'dynamic'
  symbols?: string[]
  filterTemplate?: FilterTemplate
  refreshInterval?: 'daily' | 'weekly'
  description?: string
}

export interface PoolValidateParams {
  strategyIds?: number[]
  startDate?: string
  endDate?: string
}

export interface PoolScanCreateParams {
  name: string
  poolType: 'static' | 'dynamic'
  filter: FilterTemplate
  refreshInterval?: 'daily' | 'weekly'
  description?: string
}

export const poolApi = {
  list() {
    return apiClient.get('/api/pools')
  },

  getById(id: number) {
    return apiClient.get(`/api/pools/${id}`)
  },

  create(data: PoolCreateParams) {
    return apiClient.post('/api/pools', data)
  },

  update(id: number, data: { name?: string; description?: string; symbols?: string[] }) {
    return apiClient.put(`/api/pools/${id}`, data)
  },

  delete(id: number) {
    return apiClient.delete(`/api/pools/${id}`)
  },

  refresh(id: number) {
    return apiClient.post(`/api/pools/${id}/refresh`)
  },

  validate(id: number, params?: PoolValidateParams) {
    return apiClient.post(`/api/pools/${id}/validate`, params)
  },

  scanAndCreate(data: PoolScanCreateParams) {
    return apiClient.post('/api/pools/scan-and-create', data)
  }
}
```

- [ ] **Step 2: Add export to index.ts**

Add one line at the end of `web-frontend/src/services/api/index.ts`:

```typescript
export { poolApi } from './pool'
```

- [ ] **Step 3: Verify no import errors**

Run:
```bash
cd web-frontend && npx vue-tsc --noEmit 2>&1 | grep pool || echo "No pool errors"
```
Expected: No pool-related errors

- [ ] **Step 4: Commit**

```bash
cd web-frontend && git add src/services/api/pool.ts src/services/api/index.ts
git commit -m "feat(pool-ui): add poolApi service"
```

---

### Task 2: Router + Menu

**Files:**
- Modify: `web-frontend/src/router/index.ts`
- Modify: `web-frontend/src/components/layout/MainLayout.vue`

- [ ] **Step 1: Read router/index.ts**

Read `web-frontend/src/router/index.ts` to find the exact location to insert new routes (after the opportunity-radar route).

- [ ] **Step 2: Add pool routes**

Insert after the `/opportunity-radar` route entry:

```typescript
    {
      path: '/pools',
      name: 'PoolList',
      component: () => import(/* webpackChunkName: "pool-list" */ '@/views/PoolList/index.vue'),
      meta: { title: '股票池' }
    },
    {
      path: '/pools/:id',
      name: 'PoolDetail',
      component: () => import(/* webpackChunkName: "pool-detail" */ '@/views/PoolDetail/index.vue'),
      meta: { title: '股票池详情' }
    },
```

- [ ] **Step 3: Read MainLayout.vue**

Read `web-frontend/src/components/layout/MainLayout.vue` to find the menu section and the icon imports.

- [ ] **Step 4: Add menu item**

Add the "股票池" menu item in the "研究分析" group, after the "机会雷达" item:

```html
    <el-menu-item index="/pools">
      <el-icon><Grid /></el-icon>
      <span>股票池</span>
    </el-menu-item>
```

Also add `Grid` to the icon imports from `@element-plus/icons-vue` at the top of the script section.

- [ ] **Step 5: Create placeholder view files** (so router doesn't break)

Create `web-frontend/src/views/PoolList/index.vue`:

```vue
<template>
  <div class="pool-list-page">
    <h2>股票池（开发中）</h2>
  </div>
</template>

<script setup lang="ts">
</script>
```

Create `web-frontend/src/views/PoolDetail/index.vue`:

```vue
<template>
  <div class="pool-detail-page">
    <h2>池子详情（开发中）</h2>
  </div>
</template>

<script setup lang="ts">
</script>
```

- [ ] **Step 6: Verify dev server runs**

Run:
```bash
cd web-frontend && npm run dev &
sleep 3
curl -s http://127.0.0.1:3001/ | head -5
```
Expected: HTML page loads without errors

- [ ] **Step 7: Commit**

```bash
cd web-frontend && git add src/router/index.ts src/components/layout/MainLayout.vue src/views/PoolList/index.vue src/views/PoolDetail/index.vue
git commit -m "feat(pool-ui): add pool routes and menu item"
```

---

### Task 3: Pool List Page

**Files:**
- Modify: `web-frontend/src/views/PoolList/index.vue`

- [ ] **Step 1: Implement the complete list page**

Replace the placeholder content of `web-frontend/src/views/PoolList/index.vue` with:

```vue
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
```

- [ ] **Step 2: Verify page renders in browser**

Run:
```bash
cd web-frontend && npm run dev
```
Open `http://127.0.0.1:3001/pools` in browser. Expected: Stat cards + empty table with "暂无股票池" displayed.

- [ ] **Step 3: Commit**

```bash
cd web-frontend && git add src/views/PoolList/index.vue
git commit -m "feat(pool-ui): implement pool list page with CRUD dialogs"
```

---

### Task 4: Pool Detail Page

**Files:**
- Modify: `web-frontend/src/views/PoolDetail/index.vue`

- [ ] **Step 1: Implement the complete detail page**

Replace the placeholder content of `web-frontend/src/views/PoolDetail/index.vue` with:

```vue
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
        <el-button @click="showEditDialog = true">编辑</el-button>
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
        <el-table :data="pool.symbols?.map((s: string, i: number) => ({ index: i + 1, symbol: s })) || []" stripe>
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
```

- [ ] **Step 2: Verify page renders in browser**

Open `http://127.0.0.1:3001/pools` → create a test pool → click the pool name to navigate to detail page. Expected: Pool info displayed, two tabs (members + validation) visible.

- [ ] **Step 3: Commit**

```bash
cd web-frontend && git add src/views/PoolDetail/index.vue
git commit -m "feat(pool-ui): implement pool detail page with validation results"
```

---

### Task 5: Verify and Final Commit

- [ ] **Step 1: Run type check**

```bash
cd web-frontend && npx vue-tsc --noEmit 2>&1 | head -20
```
Expected: No errors from pool-related files

- [ ] **Step 2: Run build**

```bash
cd web-frontend && npm run build 2>&1 | tail -10
```
Expected: Build succeeds

- [ ] **Step 3: Manual E2E test**

1. Navigate to `http://127.0.0.1:3001/pools`
2. Verify sidebar shows "股票池" menu item with Grid icon
3. Click "创建静态池" → fill form → create → pool appears in table
4. Click pool name → detail page loads with members tab
5. Click "验证策略" → submit (if backend running) or verify dialog opens correctly
6. Click back → return to list
7. Delete pool → confirm → pool removed

- [ ] **Step 4: Final commit**

```bash
cd web-frontend && git add -A
git commit -m "feat(pool-ui): stock pool management frontend complete"
```
