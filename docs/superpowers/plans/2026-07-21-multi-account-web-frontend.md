# web-frontend 统一账户页实施计划（计划 3）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** web-frontend 改造为统一「模拟交易」页：账户切换器驱动全部数据请求（account_name 显式传递），V14 硬编码页下线。

**Architecture:** 新增 `simulationApi` 服务模块（axios apiClient 模式）+ `AccountSwitcher` 组件（含开户对话框）；SimulationTrading 页以 `selectedAccount` 为单一数据源驱动策略卡/资金卡/持仓/交易/净值/调度各区块；路由 `/v14-trading` 重定向到统一页并预选 v14_simulation（query param）。

**Tech Stack:** Vue 3 `<script setup>`、Element Plus、axios、ECharts、vitest + @vue/test-utils。

**Spec:** `docs/superpowers/specs/2026-07-19-multi-account-domain-design.md` §6
**前置：** 计划 1 已完成——v2 端点 `GET/POST /api/simulation/accounts`、`GET /api/simulation/accounts/<name>`、`POST /api/simulation/accounts/<name>/trade`、`GET /api/simulation/trades|performance|execution-history`（account_name 均必填）；账户含 `cash_available/cash_frozen/position_value/initial_capital/strategy_name`；持仓含 `shares_total/shares_available/avg_cost/profit_total/profit_total_rate/profit_today`；交易含 `realized_pnl/reason`。

**工作目录：** `web-frontend/`（独立 git 仓库，当前分支 feat/watch-engine——在其上新建 feature 分支）

---

### Task 0: 建分支

- [ ] **Step 1: 创建 feature 分支**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
git checkout -b feature/multi-account-page
```

---

### Task 1: simulationApi 服务模块 + 类型

**Files:**
- Create: `web-frontend/src/services/api/simulation.ts`
- Modify: `web-frontend/src/services/api/index.ts`（加导出）
- Test: `web-frontend/tests/unit/simulationApi.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// tests/unit/simulationApi.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

import { simulationApi } from '@/services/api/simulation'

describe('simulationApi', () => {
  beforeEach(() => vi.clearAllMocks())

  it('listAccounts 请求账户发现端点', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: { accounts: [], total: 0 } })
    await simulationApi.listAccounts()
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/accounts', { params: { status: 'active' } })
  })

  it('createAccount 提交开户参数', async () => {
    apiClientMock.post.mockResolvedValue({ success: true, data: { account_name: 'x' } })
    await simulationApi.createAccount({ account_name: 'x', display_name: 'X', initial_capital: 100000 })
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/simulation/accounts', {
      account_name: 'x', display_name: 'X', initial_capital: 100000, strategy_name: undefined
    })
  })

  it('getAccount 按账户名查询', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: {} })
    await simulationApi.getAccount('v13_simulation')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/accounts/v13_simulation')
  })

  it('trade 提交交易到账户端点', async () => {
    apiClientMock.post.mockResolvedValue({ success: true, data: { order_id: 1 } })
    await simulationApi.trade('v13_simulation', { action: 'buy', symbol: '600519', shares: 100, reason: '测试理由：不少于十个字' })
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/simulation/accounts/v13_simulation/trade', {
      action: 'buy', symbol: '600519', shares: 100, reason: '测试理由：不少于十个字'
    })
  })

  it('getTrades/getPerformance/executionHistory 必传 account_name', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: [] })
    await simulationApi.getTrades('v13_simulation', 50)
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/trades', { params: { account_name: 'v13_simulation', limit: 50 } })
    await simulationApi.getPerformance('v13_simulation')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/performance', { params: { account_name: 'v13_simulation' } })
    await simulationApi.getExecutionHistory('v13_simulation', 50)
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/execution-history', { params: { account_name: 'v13_simulation', limit: 50 } })
  })

  it('runStrategy 携带 strategy_id 和 account_name', async () => {
    apiClientMock.post.mockResolvedValue({ success: true, data: {} })
    await simulationApi.runStrategy('v13', 'v13_simulation')
    expect(apiClientMock.post).toHaveBeenCalledWith('/api/simulation/run', {
      strategy_id: 'v13', account_name: 'v13_simulation'
    })
  })

  it('getStrategyInfo 查询策略详情', async () => {
    apiClientMock.get.mockResolvedValue({ success: true, data: {} })
    await simulationApi.getStrategyInfo('v13')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/simulation/strategies/v13')
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npx vitest run tests/unit/simulationApi.test.ts
```
预期：FAIL（模块不存在）

- [ ] **Step 3: 实现服务模块**

```typescript
// src/services/api/simulation.ts
import { apiClient } from './client'

// ---- 类型（对齐 v2 多账户域契约，snake_case 直传） ----
export interface AccountSummary {
  account_name: string
  display_name: string | null
  strategy_name: string | null
  status: string
  cash_available: number
  cash_frozen: number
  position_value: number
  total_value: number
  cumulative_return: number
  positions_count: number
}

export interface PositionItem {
  symbol: string
  name?: string
  shares_total: number
  shares_available: number
  avg_cost: number | null
  current_price: number | null
  market_value: number | null
  profit_total: number | null
  profit_total_rate: number | null
  profit_today: number | null
}

export interface AccountStatus {
  account_name: string
  display_name: string | null
  strategy_name: string | null
  cash_available: number
  cash_frozen: number
  position_value: number
  total_value: number
  initial_capital: number
  cumulative_return: number
  last_rebalance_date: string | null
  positions_count: number
  positions: PositionItem[]
}

export interface TradeItem {
  symbol: string
  name: string | null
  action: 'BUY' | 'SELL'
  shares: number
  price: number | null
  amount: number | null
  timestamp: string | null
  commission: number
  stamp_duty: number
  realized_pnl: number | null
  realized_pnl_rate: number | null
  reason: string | null
}

export interface EquityPoint {
  date: string
  total_value: number
  cash: number
  market_value: number
  return: number
}

export interface PerformanceData {
  equity_curve: EquityPoint[]
  initial_capital: number
  current_value: number
  cumulative_return: number
  max_drawdown: number
}

export interface CreateAccountRequest {
  account_name: string
  display_name?: string
  initial_capital: number
  strategy_name?: string
}

export interface TradeRequest {
  action: 'buy' | 'sell'
  symbol: string
  shares?: number
  amount?: number
  price_limit?: number
  reason: string
}

interface Envelope<T> { success: boolean; data: T; error?: string }

export const simulationApi = {
  listAccounts(status = 'active') {
    return apiClient.get<any, Envelope<{ accounts: AccountSummary[]; total: number }>>(
      '/api/simulation/accounts', { params: { status } })
  },

  createAccount(req: CreateAccountRequest) {
    return apiClient.post<any, Envelope<{ account_name: string }>>(
      '/api/simulation/accounts', { ...req, strategy_name: req.strategy_name })
  },

  getAccount(accountName: string) {
    return apiClient.get<any, Envelope<AccountStatus>>(`/api/simulation/accounts/${accountName}`)
  },

  trade(accountName: string, req: TradeRequest) {
    return apiClient.post<any, Envelope<any>>(`/api/simulation/accounts/${accountName}/trade`, req)
  },

  getTrades(accountName: string, limit = 50) {
    return apiClient.get<any, Envelope<TradeItem[]>>(
      '/api/simulation/trades', { params: { account_name: accountName, limit } })
  },

  getPerformance(accountName: string) {
    return apiClient.get<any, Envelope<PerformanceData>>(
      '/api/simulation/performance', { params: { account_name: accountName } })
  },

  getExecutionHistory(accountName: string, limit = 50) {
    return apiClient.get<any, Envelope<any[]>>(
      '/api/simulation/execution-history', { params: { account_name: accountName, limit } })
  },

  runStrategy(strategyId: string, accountName: string) {
    return apiClient.post<any, Envelope<any>>(
      '/api/simulation/run', { strategy_id: strategyId, account_name: accountName })
  },

  getStrategyInfo(strategyId: string) {
    return apiClient.get<any, Envelope<any>>(`/api/simulation/strategies/${strategyId}`)
  }
}
```

- [ ] **Step 4: 导出 + 测试通过**

```typescript
// src/services/api/index.ts 追加一行：
export { simulationApi } from './simulation'
```

```bash
npx vitest run tests/unit/simulationApi.test.ts
```
预期：7 个测试全过

- [ ] **Step 5: Commit**

```bash
git add src/services/api/simulation.ts src/services/api/index.ts tests/unit/simulationApi.test.ts
git commit -m "feat: simulationApi 服务模块（账户发现/开户/交易/绩效，account_name 显式化）"
```

---

### Task 2: AccountSwitcher 组件（含开户对话框）

**Files:**
- Create: `web-frontend/src/components/AccountSwitcher.vue`
- Test: `web-frontend/tests/unit/AccountSwitcher.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// tests/unit/AccountSwitcher.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AccountSwitcher from '@/components/AccountSwitcher.vue'

const simulationApiMock = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  createAccount: vi.fn()
}))

vi.mock('@/services/api/simulation', () => ({ simulationApi: simulationApiMock }))

const ACCOUNTS = [
  { account_name: 'v13_simulation', display_name: 'V13 多因子模拟仓', strategy_name: 'v13', status: 'active', cash_available: 110000, cash_frozen: 0, position_value: 37000, total_value: 147000, cumulative_return: 0.47, positions_count: 1 },
  { account_name: 'v14_simulation', display_name: 'V14 模拟仓', strategy_name: 'v14', status: 'active', cash_available: 101873, cash_frozen: 0, position_value: 0, total_value: 144859, cumulative_return: 0.45, positions_count: 5 }
]

describe('AccountSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    simulationApiMock.listAccounts.mockResolvedValue({ success: true, data: { accounts: ACCOUNTS, total: 2 } })
  })

  it('挂载后加载账户列表并默认选中第一个', async () => {
    const wrapper = mount(AccountSwitcher)
    await nextTick(); await nextTick()
    expect(simulationApiMock.listAccounts).toHaveBeenCalled()
    expect(wrapper.vm.selected).toBe('v13_simulation')
    expect(wrapper.emitted('change')?.[0]).toEqual(['v13_simulation', ACCOUNTS[0]])
  })

  it('切换账户时 emit change', async () => {
    const wrapper = mount(AccountSwitcher)
    await nextTick(); await nextTick()
    wrapper.vm.selected = 'v14_simulation'
    await nextTick()
    const events = wrapper.emitted('change')!
    expect(events[events.length - 1]).toEqual(['v14_simulation', ACCOUNTS[1]])
  })

  it('开户成功后刷新列表并选中新账户', async () => {
    simulationApiMock.createAccount.mockResolvedValue({ success: true, data: { account_name: 'new_acc' } })
    const wrapper = mount(AccountSwitcher)
    await nextTick(); await nextTick()
    await wrapper.vm.openCreateDialog()
    wrapper.vm.createForm.account_name = 'new_acc'
    wrapper.vm.createForm.initial_capital = 50000
    await wrapper.vm.submitCreate()
    expect(simulationApiMock.createAccount).toHaveBeenCalledWith(
      expect.objectContaining({ account_name: 'new_acc', initial_capital: 50000 }))
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
npx vitest run tests/unit/AccountSwitcher.test.ts
```
预期：FAIL（组件不存在）

- [ ] **Step 3: 实现组件**

```vue
<!-- src/components/AccountSwitcher.vue -->
<template>
  <div class="account-switcher">
    <el-select
      v-model="selected"
      placeholder="选择账户"
      style="width: 320px"
      @change="onChange"
    >
      <el-option
        v-for="acc in accounts"
        :key="acc.account_name"
        :label="`${acc.display_name || acc.account_name}（¥${formatWan(acc.total_value)}）`"
        :value="acc.account_name"
      >
        <div class="account-option">
          <span>{{ acc.display_name || acc.account_name }}</span>
          <span class="account-option-meta">
            ¥{{ formatWan(acc.total_value) }}
            <el-tag v-if="acc.strategy_name" size="small" type="info">{{ acc.strategy_name }}</el-tag>
          </span>
        </div>
      </el-option>
      <template #footer>
        <el-button text type="primary" size="small" @click="openCreateDialog">+ 开户</el-button>
      </template>
    </el-select>

    <el-dialog v-model="createVisible" title="开立模拟账户" width="420px">
      <el-form label-width="90px">
        <el-form-item label="账户名" required>
          <el-input v-model="createForm.account_name" placeholder="如 manual_test（禁止 default）" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="createForm.display_name" placeholder="如 手工测试仓" />
        </el-form-item>
        <el-form-item label="初始资金" required>
          <el-input-number v-model="createForm.initial_capital" :min="1000" :step="10000" style="width: 100%" />
        </el-form-item>
        <el-form-item label="绑定策略">
          <el-input v-model="createForm.strategy_name" placeholder="可选，如 v13" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { simulationApi } from '@/services/api/simulation'
import type { AccountSummary } from '@/services/api/simulation'

const props = defineProps<{ initialAccount?: string }>()
const emit = defineEmits<{ (e: 'change', accountName: string, account: AccountSummary): void }>()

const accounts = ref<AccountSummary[]>([])
const selected = ref<string>('')
const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({
  account_name: '',
  display_name: '',
  initial_capital: 100000,
  strategy_name: ''
})

function formatWan(v: number) {
  return (v / 10000).toFixed(1) + '万'
}

async function loadAccounts(selectName?: string) {
  const res = await simulationApi.listAccounts()
  if (res.success) {
    accounts.value = res.data.accounts
    const target = selectName
      || (props.initialAccount && accounts.value.find(a => a.account_name === props.initialAccount)?.account_name)
      || accounts.value[0]?.account_name
    if (target) {
      selected.value = target
      const acc = accounts.value.find(a => a.account_name === target)!
      emit('change', target, acc)
    }
  } else {
    ElMessage.error('加载账户列表失败')
  }
}

function onChange(name: string) {
  const acc = accounts.value.find(a => a.account_name === name)
  if (acc) emit('change', name, acc)
}

async function openCreateDialog() {
  createVisible.value = true
}

async function submitCreate() {
  if (!createForm.account_name || createForm.account_name === 'default') {
    ElMessage.warning('账户名必填且不能为 default')
    return
  }
  creating.value = true
  try {
    const res = await simulationApi.createAccount({
      account_name: createForm.account_name,
      display_name: createForm.display_name || undefined,
      initial_capital: createForm.initial_capital,
      strategy_name: createForm.strategy_name || undefined
    })
    if (res.success) {
      ElMessage.success('开户成功')
      createVisible.value = false
      await loadAccounts(createForm.account_name)
    } else {
      ElMessage.error(`开户失败: ${(res as any).error || '未知错误'}`)
    }
  } finally {
    creating.value = false
  }
}

onMounted(() => loadAccounts())

defineExpose({ selected, accounts, createForm, openCreateDialog, submitCreate, loadAccounts })
</script>

<style scoped>
.account-switcher { display: inline-block; }
.account-option { display: flex; justify-content: space-between; align-items: center; }
.account-option-meta { color: #999; font-size: 12px; display: flex; gap: 6px; align-items: center; }
</style>
```

- [ ] **Step 4: 测试通过**

```bash
npx vitest run tests/unit/AccountSwitcher.test.ts
```
预期：3 个测试全过（el-select/el-dialog 在 vitest 下可挂载，与现有 OpportunityRadar 测试同样依赖 jsdom 环境——若该仓库 vitest 未配 jsdom 环境则参考 tests/unit 现有用例的环境声明补齐）

- [ ] **Step 5: Commit**

```bash
git add src/components/AccountSwitcher.vue tests/unit/AccountSwitcher.test.ts
git commit -m "feat: AccountSwitcher 组件（账户切换 + 开户对话框）"
```

---

### Task 3: SimulationTrading 页改造 A —— 账户状态驱动 + 数据加载

**Files:**
- Modify: `web-frontend/src/views/SimulationTrading/index.vue`
- Test: `web-frontend/tests/unit/SimulationTrading.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// tests/unit/SimulationTrading.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SimulationTrading from '@/views/SimulationTrading/index.vue'

const simulationApiMock = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  getAccount: vi.fn(),
  getTrades: vi.fn(),
  getPerformance: vi.fn(),
  getExecutionHistory: vi.fn(),
  getStrategyInfo: vi.fn(),
  runStrategy: vi.fn(),
  trade: vi.fn(),
  createAccount: vi.fn()
}))

vi.mock('@/services/api/simulation', () => ({ simulationApi: simulationApiMock }))

vi.mock('echarts', () => ({
  init: () => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })
}))

const ACCOUNT_STATUS = {
  account_name: 'v13_simulation', display_name: 'V13 多因子模拟仓', strategy_name: 'v13',
  cash_available: 110030.89, cash_frozen: 0, position_value: 38255, total_value: 148285.89,
  initial_capital: 99993.81, cumulative_return: 0.483, last_rebalance_date: '2026-07-13',
  positions_count: 1,
  positions: [{ symbol: '601888', shares_total: 700, shares_available: 700, avg_cost: 52.87, current_price: 54.65, market_value: 38255, profit_total: 1246, profit_total_rate: 0.0337, profit_today: 100 }]
}

describe('SimulationTrading 统一账户页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    simulationApiMock.listAccounts.mockResolvedValue({ success: true, data: { accounts: [
      { account_name: 'v13_simulation', display_name: 'V13', strategy_name: 'v13', status: 'active', cash_available: 0, cash_frozen: 0, position_value: 0, total_value: 148285, cumulative_return: 0.48, positions_count: 1 },
      { account_name: 'v14_simulation', display_name: 'V14', strategy_name: 'v14', status: 'active', cash_available: 0, cash_frozen: 0, position_value: 0, total_value: 144859, cumulative_return: 0.45, positions_count: 5 }
    ], total: 2 } })
    simulationApiMock.getAccount.mockResolvedValue({ success: true, data: ACCOUNT_STATUS })
    simulationApiMock.getTrades.mockResolvedValue({ success: true, data: [] })
    simulationApiMock.getPerformance.mockResolvedValue({ success: true, data: { equity_curve: [], initial_capital: 100000, current_value: 148285, cumulative_return: 48.3, max_drawdown: -5 } })
    simulationApiMock.getExecutionHistory.mockResolvedValue({ success: true, data: [] })
    simulationApiMock.getStrategyInfo.mockResolvedValue({ success: true, data: { name: 'V13', version: '1.0.0', rebalance_days: 5, max_positions: 8 } })
  })

  it('切换账户后所有数据请求携带新 account_name', async () => {
    const wrapper = mount(SimulationTrading)
    await nextTick(); await nextTick(); await nextTick()
    expect(simulationApiMock.getAccount).toHaveBeenCalledWith('v13_simulation')

    await wrapper.vm.onAccountChange('v14_simulation', { account_name: 'v14_simulation', strategy_name: 'v14' })
    await nextTick(); await nextTick()
    expect(simulationApiMock.getAccount).toHaveBeenCalledWith('v14_simulation')
    expect(simulationApiMock.getTrades).toHaveBeenCalledWith('v14_simulation', 50)
    expect(simulationApiMock.getPerformance).toHaveBeenCalledWith('v14_simulation')
    expect(simulationApiMock.getStrategyInfo).toHaveBeenCalledWith('v14')
  })

  it('执行策略时携带 account_name', async () => {
    simulationApiMock.runStrategy.mockResolvedValue({ success: true, data: { action: 'skip', message: 'no rebalance' } })
    const wrapper = mount(SimulationTrading)
    await nextTick(); await nextTick(); await nextTick()
    await wrapper.vm.runStrategy()
    expect(simulationApiMock.runStrategy).toHaveBeenCalledWith('v13', 'v13_simulation')
  })

  it('账户无绑定策略时隐藏执行按钮', async () => {
    const wrapper = mount(SimulationTrading)
    await nextTick(); await nextTick(); await nextTick()
    await wrapper.vm.onAccountChange('manual_test', { account_name: 'manual_test', strategy_name: null })
    await nextTick()
    expect(wrapper.vm.hasStrategy).toBe(false)
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
npx vitest run tests/unit/SimulationTrading.test.ts
```
预期：FAIL（onAccountChange/hasStrategy 不存在）

- [ ] **Step 3: 改造 script 部分（账户状态驱动）**

在 `src/views/SimulationTrading/index.vue` 的 `<script setup>` 中：

**3a. 替换常量与状态（删除硬编码 API_BASE/default/v13）：**

```typescript
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
```

**3b. 新增账户切换处理器：**

```typescript
async function onAccountChange(accountName: string, account: AccountSummary | any) {
  selectedAccount.value = accountName
  currentAccount.value = account
  await Promise.all([
    loadAccount(),
    loadTradeRecords(),
    loadPerformance(),
    loadExecutionHistory(),
    strategyId.value ? loadStrategy() : Promise.resolve(),
    loadSchedulerTasks()
  ])
}
```

**3c. 改造各加载函数（删除 fetch 硬编码，改用 simulationApi + selectedAccount）：**

```typescript
async function loadStrategy() {
  if (!strategyId.value) { strategy.value = null; return }
  loading.value.strategy = true
  try {
    const res = await simulationApi.getStrategyInfo(strategyId.value)
    strategy.value = res.success ? res.data : null
  } catch (err: any) {
    console.error('加载策略失败:', err)
  } finally {
    loading.value.strategy = false
  }
}

async function loadAccount() {
  if (!selectedAccount.value) return
  loading.value.account = true
  try {
    const res = await simulationApi.getAccount(selectedAccount.value)
    if (res.success) {
      account.value = res.data
      await loadStockNames(res.data.positions)
    }
  } catch (err: any) {
    ElMessage.error(`加载账户失败: ${err.message}`)
  } finally {
    loading.value.account = false
  }
}

async function runStrategy() {
  if (!strategyId.value || !selectedAccount.value) return
  loading.value.run = true
  runResult.value = null
  try {
    const res = await simulationApi.runStrategy(strategyId.value, selectedAccount.value)
    const data = res
    if (data.success) {
      const action = data.data.action
      if (action === 'skip') {
        runResult.value = { type: 'warning', title: '无需调仓', message: data.data.message }
      } else {
        runResult.value = {
          type: 'success', title: '调仓成功',
          message: `信号数: ${data.data.signals_count}, 交易数: ${data.data.trades_count}`
        }
        setTimeout(() => { loadAccount(); loadExecutionHistory() }, 1000)
      }
    } else {
      runResult.value = { type: 'error', title: '执行失败', message: (data as any).error }
    }
  } catch (err: any) {
    runResult.value = { type: 'error', title: '执行失败', message: err.message }
  } finally {
    loading.value.run = false
  }
}

async function loadExecutionHistory() {
  if (!selectedAccount.value) return
  loading.value.history = true
  try {
    const res = await simulationApi.getExecutionHistory(selectedAccount.value, 50)
    if (res.success) executionHistory.value = res.data || []
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
    if (res.success) tradeRecords.value = res.data || []
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
    if (res.success && res.data) {
      await nextTick()
      renderChart(res.data)
    }
  } catch (err: any) {
    console.error('加载收益数据失败:', err)
  } finally {
    loading.value.performance = false
  }
}
```

**3d. 调度任务按当前账户的策略名过滤（替换 v13 硬编码）：**

```typescript
// loadSchedulerTasks 内过滤逻辑改为：
const strategyKey = (strategyId.value || '').toLowerCase()
const strategyTasks = strategyKey
  ? allTasks.filter((task: any) => (task.name || task.task_name || '').toLowerCase().includes(strategyKey))
  : []
// 后续 v13Tasks 引用全部改名 strategyTasks
```

**3e. onMounted 改为由 AccountSwitcher 的 change 事件驱动首载：**

```typescript
onMounted(() => {
  // 首次加载由 AccountSwitcher change 触发（支持 ?account=xxx 预选）
  refreshTimer = window.setInterval(() => {
    if (selectedAccount.value) loadAccount()
  }, 30000)
})
```

模板中挂载切换器（页首）：

```html
<el-page-header @back="$router.back()" content="模拟交易监控">
  <template #extra>
    <AccountSwitcher
      :initial-account="(route.query.account as string) || undefined"
      @change="onAccountChange"
    />
  </template>
</el-page-header>
```

- [ ] **Step 4: 测试通过**

```bash
npx vitest run tests/unit/SimulationTrading.test.ts
```
预期：3 个测试全过

- [ ] **Step 5: Commit**

```bash
git add src/views/SimulationTrading/index.vue tests/unit/SimulationTrading.test.ts
git commit -m "feat: 模拟交易页账户状态驱动（切换器联动全部数据请求）"
```

---

### Task 4: SimulationTrading 页改造 B —— 展示块对齐新域模型

**Files:**
- Modify: `web-frontend/src/views/SimulationTrading/index.vue`

- [ ] **Step 1: 资金卡片改为资金两态 + 策略卡条件渲染 + 执行按钮动态化**

```html
<!-- 账户状态卡片 info-list 替换为： -->
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

<!-- 策略信息卡片：无绑定策略时提示 -->
<el-card shadow="hover" v-if="hasStrategy">
  <!-- 原策略信息内容不变 -->
</el-card>
<el-card shadow="hover" v-else>
  <template #header><div class="card-header"><span>📊 策略信息</span></div></template>
  <el-empty description="该账户未绑定策略" :image-size="60" />
</el-card>

<!-- 执行按钮：文案动态化，无策略时禁用 -->
<el-button
  type="primary" size="large" style="width: 100%"
  @click="runStrategy" :loading="loading.run" :disabled="!hasStrategy"
>
  执行{{ strategyId ? strategyId.toUpperCase() + '策略' : '策略' }}
</el-button>

<!-- 调度任务卡片标题动态化 -->
<span>⏰ {{ strategyId ? strategyId.toUpperCase() : '' }}调度任务</span>
```

- [ ] **Step 2: 持仓表对齐新列（T+1 可用/总量、当日盈亏）**

```html
<el-table-column label="持仓(可用)" width="130">
  <template #default="scope">
    {{ scope.row.shares_total }}
    <span style="color: #999; font-size: 12px">({{ scope.row.shares_available }}可卖)</span>
  </template>
</el-table-column>
<el-table-column label="成本价" width="120">
  <template #default="scope">¥{{ parseFloat(scope.row.avg_cost ?? 0).toFixed(2) }}</template>
</el-table-column>
<el-table-column label="当前价" width="120">
  <template #default="scope">
    <span v-if="scope.row.current_price">¥{{ parseFloat(scope.row.current_price).toFixed(2) }}</span>
    <span v-else style="color: #999;">--</span>
  </template>
</el-table-column>
<el-table-column label="市值" width="150">
  <template #default="scope">¥{{ formatNumber(scope.row.market_value ?? 0) }}</template>
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
```

- [ ] **Step 3: 交易记录表加已实现盈亏与理由列**

```html
<!-- 在「金额」列后追加： -->
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
```

- [ ] **Step 4: 回归测试 + 全量 vitest**

```bash
npx vitest run tests/unit/SimulationTrading.test.ts tests/unit/AccountSwitcher.test.ts
npm run test 2>&1 | tail -5
```
预期：新增测试全过；既有测试不红（若有与旧字段耦合的用例失败，按新契约修正）

- [ ] **Step 5: Commit**

```bash
git add src/views/SimulationTrading/index.vue
git commit -m "feat: 模拟交易页对齐新域模型（资金两态/T+1可用/当日盈亏/已实现盈亏/交易理由）"
```

---

### Task 5: V14Trading 页下线（路由重定向 + 菜单合并）

**Files:**
- Modify: `web-frontend/src/router/index.ts`（v14-trading 改重定向；simulation-trading 标题改「模拟交易」）
- Modify: `web-frontend/src/components/layout/MainLayout.vue`（两个菜单项合并为一个）
- Delete: `web-frontend/src/views/V14Trading/index.vue`
- Test: `web-frontend/tests/unit/router.test.ts`

- [ ] **Step 1: 写失败测试**

```typescript
// tests/unit/router.test.ts
import { describe, it, expect } from 'vitest'
import router from '@/router'

describe('router 多账户', () => {
  it('/v14-trading 重定向到统一页并预选 v14_simulation', () => {
    const resolved = router.resolve('/v14-trading')
    expect(resolved.path).toBe('/simulation-trading')
    expect(resolved.query.account).toBe('v14_simulation')
  })

  it('/simulation-trading 标题为模拟交易', () => {
    const resolved = router.resolve('/simulation-trading')
    expect(resolved.meta.title).toBe('模拟交易')
  })
})
```

- [ ] **Step 2: 运行确认失败**

```bash
npx vitest run tests/unit/router.test.ts
```
预期：FAIL

- [ ] **Step 3: 路由与菜单改造**

```typescript
// router/index.ts
{
  path: '/simulation-trading',
  name: 'SimulationTrading',
  component: () => import(/* webpackChunkName: "simulation-trading" */ '@/views/SimulationTrading/index.vue'),
  meta: { title: '模拟交易' }
},
{
  path: '/v14-trading',
  redirect: { path: '/simulation-trading', query: { account: 'v14_simulation' } }
},
// 删除原 V14Trading 路由记录
```

```html
<!-- MainLayout.vue：两项合并 -->
<el-menu-item index="/simulation-trading">
  <el-icon><!-- 原图标保留 --></el-icon>
  <span>模拟交易</span>
</el-menu-item>
<!-- 删除 /v14-trading 菜单项 -->
```

```bash
git rm src/views/V14Trading/index.vue
```

- [ ] **Step 4: 测试通过 + 构建验证**

```bash
npx vitest run tests/unit/router.test.ts
npm run build 2>&1 | tail -3
```
预期：测试通过；构建无 V14Trading chunk、无报错

- [ ] **Step 5: Commit**

```bash
git add src/router/index.ts src/components/layout/MainLayout.vue tests/unit/router.test.ts
git commit -m "feat: V14 硬编码页下线（重定向统一页 + 菜单合并 + ?account 预选）"
```

---

### Task 6: 端到端验证（对接运行中的 v2）

- [ ] **Step 1: 全量测试**

```bash
npm run test 2>&1 | tail -5
```
预期：全绿

- [ ] **Step 2: 启动 dev server 并 curl 冒烟（依赖的 v2 端点）**

```bash
# v2 后端需在运行（127.0.0.1:5001）
export NO_PROXY=127.0.0.1,localhost
curl -s http://127.0.0.1:5001/api/simulation/accounts | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['success'] and d['data']['total'] >= 3; print('✅ 账户发现:', [a['account_name'] for a in d['data']['accounts']])"
curl -s "http://127.0.0.1:5001/api/simulation/accounts/v14_simulation" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['success']; print('✅ v14 账户详情: total_value=', d['data']['total_value'])"
curl -s "http://127.0.0.1:5001/api/simulation/performance?account_name=v13_simulation" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['success']; print('✅ v13 绩效: 快照点数=', len(d['data']['equity_curve']))"
```

- [ ] **Step 3: 手动核对清单（dev server http://127.0.0.1:3001/simulation-trading）**

- 切换器列出 v13/v14/v15 账户，切换后资金卡/持仓/交易/净值全部刷新
- v15（空仓）页面无报错；开户对话框可创建新账户
- /v14-trading 自动跳转并预选 V14 账户
- 菜单只剩一个「模拟交易」入口

- [ ] **Step 4: 最终 Commit（如有修正）**

```bash
git add -A && git commit -m "test: 统一账户页端到端验证修正" || echo "无修正，跳过"
```

---

## Self-Review 记录

- 覆盖：spec §6 全部（切换器/开户对话框/资金两态/新列/理由/菜单合并/重定向预选）✅
- 类型一致性：`onAccountChange(name, account)`、`AccountSummary`、`selectedAccount` 在 Task 2/3/5 间一致；`runStrategy(strategyId, accountName)` 与 Task 1 签名一致 ✅
- 已知风险：vitest 环境需 jsdom（现有 OpportunityRadar 测试已用 mount，环境应已就绪）；Task 4 若既有测试引用旧字段（shares/avg_price/profit）需同步修正
