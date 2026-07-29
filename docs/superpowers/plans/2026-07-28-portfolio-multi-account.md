# Portfolio 页面多账户适配 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 web-frontend 的 Portfolio 页面与 Dashboard 适配多账户域（account_name 必填），持仓数据按选中账户加载，手工交易改走 simulation trade API。

**Architecture:** 复用现有 `AccountSwitcher.vue` 组件做账户切换（与 SimulationTrading 页同模式）；`tradingApi.getPositions/getPortfolioSummary` 增加 `account_name` 参数；portfolio store 修正为后端现行 snake_case 契约；交易按钮改调 `simulationApi.trade`（立即成交，限价=保护价语义）。

**Tech Stack:** Vue 3 + Element Plus + Pinia + Vitest（web-frontend，`npm test` = `vitest run`）

**设计文档:** `docs/superpowers/specs/2026-07-28-portfolio-multi-account-design.md`

**Worktree:** `.claude/worktrees/portfolio-multi-account`，分支 `worktree-portfolio-multi-account`

---

## 后端契约要点（实现时必须遵守）

- `GET /api/portfolio/positions?account_name=X` → `{ positions: [{ symbol, name:'', quantity(=shares_total), shares_available, avg_cost, current_price, total_cost, current_value, profit_loss, profit_loss_pct, profit_today }], count }`
- `GET /api/portfolio/summary?account_name=X` → `{ totalValue, totalCost, totalMarketValue, totalPnl, totalPnlPct, dailyChange, positions, cash, liquidAssets, profitCount, lossCount, lastUpdated }`
- `POST /api/simulation/accounts/<name>/trade` body: `{ action: 'buy'|'sell', symbol, shares?, amount?, price_limit?, reason }`
  - **reason 必填且 strip 后 ≥10 字符**，否则 400「必须提供详细的交易理由（至少10字）」
  - **shares 必须是 100 的整数倍**，否则 422
  - **price_limit 是保护价不是挂单**：买入时现价 > price_limit 则 422 拒单；卖出时现价 < price_limit 则拒单。市价单不传 price_limit
  - 非交易时段拒单（`allow_off_hours` 默认 false，前端**不传**该字段，把后端错误信息弹给用户即可）
- apiClient 响应拦截器解包 `{success, data}` 信封：调用方拿到的就是内层 `data`；后端错误时拦截器 reject，error.message 为后端 error 文案

---

### Task 1: tradingApi 增加 account_name 参数

**Files:**
- Modify: `web-frontend/src/services/api/trading.ts:54-73`
- Test: `web-frontend/tests/unit/tradingApi.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `web-frontend/tests/unit/tradingApi.test.ts`（模式照抄 `tests/unit/simulationApi.test.ts`）：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

import { tradingApi } from '@/services/api/trading'

describe('tradingApi 多账户契约', () => {
  beforeEach(() => vi.clearAllMocks())

  it('getPositions 必传 account_name', async () => {
    apiClientMock.get.mockResolvedValue({ positions: [], count: 0 })
    await tradingApi.getPositions('v13_simulation')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/portfolio/positions', {
      params: { account_name: 'v13_simulation' }
    })
  })

  it('getPortfolioSummary 必传 account_name', async () => {
    apiClientMock.get.mockResolvedValue({ totalValue: 0 })
    await tradingApi.getPortfolioSummary('agent_virtual')
    expect(apiClientMock.get).toHaveBeenCalledWith('/api/portfolio/summary', {
      params: { account_name: 'agent_virtual' }
    })
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web-frontend && npx vitest run tests/unit/tradingApi.test.ts`
Expected: FAIL — `getPositions`/`getPortfolioSummary` 调用时未带 params（断言不匹配）

- [ ] **Step 3: 修改 trading.ts**

`web-frontend/src/services/api/trading.ts` 中两个方法改为：

```ts
  /**
   * 获取持仓列表（account_name 必填）
   */
  getPositions(accountName: string) {
    return apiClient.get('/api/portfolio/positions', {
      params: { account_name: accountName }
    })
  },

  /**
   * 获取持仓明细（含实时价格、盈亏、权重）
   */
  getHoldings() {
    return apiClient.get('/api/portfolio/holdings')
  },

  /**
   * 获取持仓汇总（account_name 必填）
   */
  getPortfolioSummary(accountName: string) {
    return apiClient.get<PortfolioSummaryResponse>('/api/portfolio/summary', {
      params: { account_name: accountName }
    })
  },
```

（`getHoldings` 不变，此处仅为定位上下文。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd web-frontend && npx vitest run tests/unit/tradingApi.test.ts`
Expected: PASS 2 个用例

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/services/api/trading.ts web-frontend/tests/unit/tradingApi.test.ts
git commit -m "feat(web): tradingApi getPositions/getPortfolioSummary 增加 account_name 必填参数"
```

---

### Task 2: Position 类型加 sharesAvailable + portfolio store 账户化与 snake_case 映射

**Files:**
- Modify: `web-frontend/src/types/models.ts:126-148`
- Modify: `web-frontend/src/stores/portfolio.ts`
- Test: `web-frontend/tests/unit/portfolioStore.test.ts`（新建）

- [ ] **Step 1: 写失败测试**

新建 `web-frontend/tests/unit/portfolioStore.test.ts`：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

import { usePortfolioStore } from '@/stores/portfolio'

const POSITION_PAYLOAD = {
  symbol: '600519',
  name: '',
  quantity: 200,
  shares_available: 100,
  avg_cost: 1400.5,
  current_price: 1500,
  total_cost: 280100,
  current_value: 300000,
  profit_loss: 19900,
  profit_loss_pct: 7.1,
  profit_today: 500
}

describe('portfolio store 多账户适配', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
  })

  it('fetchAll 透传 account_name 并记录 currentAccount', async () => {
    apiClientMock.get.mockImplementation((url: string) => {
      if (url === '/api/portfolio/summary') {
        return Promise.resolve({ totalValue: 400000, totalCost: 280100, totalPnl: 19900, totalPnlPct: 7.1, positions: 1, cash: 100000 })
      }
      return Promise.resolve({ positions: [POSITION_PAYLOAD], count: 1 })
    })
    const store = usePortfolioStore()
    await store.fetchAll('v13_simulation')
    expect(store.currentAccount).toBe('v13_simulation')
    const calledUrls = apiClientMock.get.mock.calls.map(c => c[0])
    expect(calledUrls).toContain('/api/portfolio/summary')
    expect(calledUrls).toContain('/api/portfolio/positions')
    for (const call of apiClientMock.get.mock.calls) {
      expect(call[1]).toEqual({ params: { account_name: 'v13_simulation' } })
    }
  })

  it('fetchPositions 按 snake_case 契约映射字段', async () => {
    apiClientMock.get.mockResolvedValue({ positions: [POSITION_PAYLOAD], count: 1 })
    const store = usePortfolioStore()
    await store.fetchPositions('v13_simulation')
    const p = store.positions[0]
    expect(p.symbol).toBe('600519')
    expect(p.quantity).toBe(200)
    expect(p.sharesAvailable).toBe(100)
    expect(p.avgCost).toBe(1400.5)
    expect(p.currentPrice).toBe(1500)
    expect(p.marketValue).toBe(300000)
    expect(p.totalCost).toBe(280100)
    expect(p.profit).toBe(19900)
    expect(p.profitPercent).toBe(7.1)
    expect(p.name).toBe('600519')  // 后端 name 为空时 fallback symbol
    expect(p.weight).toBe(100)     // 单持仓权重 100%
  })

  it('账户名为空时不发请求', async () => {
    const store = usePortfolioStore()
    await store.fetchAll('')
    expect(apiClientMock.get).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web-frontend && npx vitest run tests/unit/portfolioStore.test.ts`
Expected: FAIL — `currentAccount` 不存在、映射字段全错位、`fetchAll('')` 仍会发请求

- [ ] **Step 3: 修改类型与 store**

`web-frontend/src/types/models.ts` 的 `Position` interface（126-148 行）在 `quantity: number` 后加一行：

```ts
  quantity: number
  sharesAvailable?: number   // T+1 可用股数（simulation 体系）
```

`web-frontend/src/stores/portfolio.ts` 修改：

1. state 区（`const error = ref...` 之后）加：

```ts
  const currentAccount = ref<string>('')
```

2. `fetchSummary` / `fetchPositions` / `fetchAll` 替换为：

```ts
  // Actions
  const fetchSummary = async (accountName: string) => {
    if (!accountName) return
    try {
      const data = await tradingApi.getPortfolioSummary(accountName)
      summary.value = data as unknown as PortfolioSummaryResponse
    } catch (e: any) {
      console.error('获取持仓汇总失败:', e)
    }
  }

  const fetchPositions = async (accountName: string) => {
    if (!accountName) return
    loading.value = true
    error.value = null
    try {
      const data = await tradingApi.getPositions(accountName)
      const rawList: any[] = (data as any).positions ?? []

      const totalMV = rawList.reduce((sum, p) => sum + (p.current_value || 0), 0)

      positions.value = rawList.map((p: any) => ({
        id: p.symbol,
        symbol: p.symbol,
        symbolName: p.name || p.symbol,
        name: p.name || p.symbol,
        quantity: p.quantity,
        sharesAvailable: p.shares_available,
        avgCost: p.avg_cost,
        currentPrice: p.current_price,
        marketValue: p.current_value,
        totalCost: p.total_cost || p.avg_cost * p.quantity,
        unrealizedPnL: p.profit_loss,
        unrealizedPnLPercent: p.profit_loss_pct,
        profit: p.profit_loss,
        profitPercent: p.profit_loss_pct,
        weight: totalMV > 0 ? (p.current_value / totalMV) * 100 : 0,
        buyDate: '',
        addedDate: '',
        market: '',
        sector: null,
        stopLoss: undefined,
        targetPrice: undefined,
        reason: ''
      })) as Position[]
    } catch (e: any) {
      error.value = e.message
      console.error('获取持仓列表失败:', e)
    } finally {
      loading.value = false
    }
  }

  const fetchAll = async (accountName: string) => {
    if (!accountName) return
    currentAccount.value = accountName
    await Promise.all([fetchSummary(accountName), fetchPositions(accountName)])
  }
```

注意：删掉旧映射里的 `buyDate: p.updatedAt || ''` / `addedDate: p.updatedAt || ''` / `market: p.market || ''` / `sector: p.sector || null` —— 后端契约无这些字段，置空串/null。

3. return 的 State 区加 `currentAccount`：

```ts
  return {
    // State
    positions,
    summary,
    loading,
    error,
    currentAccount,
    // ... 其余不变
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd web-frontend && npx vitest run tests/unit/portfolioStore.test.ts`
Expected: PASS 3 个用例

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/types/models.ts web-frontend/src/stores/portfolio.ts web-frontend/tests/unit/portfolioStore.test.ts
git commit -m "feat(web): portfolio store 账户化 + snake_case 字段映射修正 + shares_available"
```

---

### Task 3: Portfolio 页面接入 AccountSwitcher + 交易改走 simulationApi.trade

**Files:**
- Modify: `web-frontend/src/views/Portfolio/index.vue`
- Test: `web-frontend/tests/unit/Portfolio.test.ts`（新建）

注意：`web-frontend/src/services/api/index.ts` 已 re-export `tradingApi`/`riskApi`；`simulationApi` 从 `@/services/api/simulation` 导入（AccountSwitcher.vue 即如此）。

- [ ] **Step 1: 写失败测试（页面级冒烟）**

新建 `web-frontend/tests/unit/Portfolio.test.ts`：

```ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

vi.mock('@/composables/useWebSocket', () => ({
  useMarketWebSocket: () => ({
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    on: vi.fn()
  })
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} })
}))

// AccountSwitcher 打桩：挂载即触发 change，模拟用户选中账户
vi.mock('@/components/AccountSwitcher.vue', () => ({
  default: defineComponent({
    emits: ['change'],
    mounted() {
      this.$emit('change', 'v13_simulation', { account_name: 'v13_simulation' })
    },
    template: '<div class="account-switcher-stub" />'
  })
}))

import PortfolioPage from '@/views/Portfolio/index.vue'

describe('Portfolio 页面多账户', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    apiClientMock.get.mockImplementation((url: string) => {
      if (url === '/api/portfolio/summary') return Promise.resolve({ totalValue: 1, positions: 0, cash: 0 })
      if (url === '/api/portfolio/positions') return Promise.resolve({ positions: [], count: 0 })
      return Promise.resolve([])
    })
  })

  it('账户切换后按账户加载持仓与汇总', async () => {
    mount(PortfolioPage)
    await new Promise(r => setTimeout(r, 0))
    const portfolioCalls = apiClientMock.get.mock.calls.filter(c =>
      String(c[0]).startsWith('/api/portfolio/'))
    expect(portfolioCalls.length).toBeGreaterThanOrEqual(2)
    for (const call of portfolioCalls) {
      expect(call[1]).toEqual({ params: { account_name: 'v13_simulation' } })
    }
  })
})
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd web-frontend && npx vitest run tests/unit/Portfolio.test.ts`
Expected: FAIL — 当前页面挂载后直接无账户请求（400 契约不符，断言 `params.account_name` 不存在）

- [ ] **Step 3: 修改页面**

`web-frontend/src/views/Portfolio/index.vue`：

**3a. template 顶部（`.portfolio` div 内、统计卡片之前）加账户工具条：**

```vue
    <!-- 账户切换工具栏 -->
    <div class="account-toolbar mb-4">
      <AccountSwitcher
        :initial-account="(route.query.account as string) || undefined"
        @change="onAccountChange"
      />
    </div>
```

**3b. 「持仓明细」header 右侧按钮组：删除「+ 新建订单」按钮，保留刷新：**

```vue
          <div class="flex items-center gap-2">
            <el-button size="small" @click="handleRefresh" :loading="loading">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
```

**3c. 「持仓量」列改为显示 总量/可用：**

```vue
        <el-table-column prop="quantity" label="持仓量" width="110" align="right">
          <template #default="{ row }">
            <div>{{ row.quantity }}</div>
            <div class="text-xs text-gray-400">可用 {{ row.sharesAvailable ?? row.quantity }}</div>
          </template>
        </el-table-column>
```

**3d. 删除「目标价」列和「买入理由」列**（即 `prop="targetPrice"` 和 `prop="reason"` 两个 `el-table-column` 整块删除）。「止损价」列保留。

**3e. script 修改：**

imports 替换/新增：

```ts
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
```

（删除 `useRouter`、`tradingApi` 的 import；`handleCreateOrder` 函数整个删除。）

新增：

```ts
const route = useRoute()

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
```

`loadPositions` 改为走当前账户（刷新按钮用）：

```ts
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
```

`onMounted` 改为空操作（首次加载由 AccountSwitcher 的 change 事件触发）：

```ts
onMounted(() => {
  // 首次加载由 AccountSwitcher change 触发（支持 ?account=xxx 预选）
})
```

`onUnmounted` 改用 `subscribedSymbols`：

```ts
onUnmounted(() => {
  subscribedSymbols.value.forEach(s => unsubscribe(s))
})
```

`handleSell` 的数量上限改用可用股数（T+1）：

```ts
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
```

`handleBuy` 末尾同样加 `tradeForm.reason = ''`。

`tradeForm` reactive 加 `reason: ''` 字段。

**交易对话框 template 加理由输入**（「数量」表单项之后）：

```vue
        <el-form-item label="交易理由" required>
          <el-input
            v-model="tradeForm.reason"
            type="textarea"
            :rows="2"
            placeholder="必填，至少 10 个字（后端审计要求）"
          />
        </el-form-item>
```

**对话框 footer 确认按钮加 disabled 校验**：

```vue
        <el-button
          :type="tradeForm.type === 'BUY' ? 'danger' : 'success'"
          @click="handleConfirmTrade"
          :loading="tradeLoading"
          :disabled="tradeForm.reason.trim().length < 10"
        >
```

**`handleConfirmTrade` 改走 simulationApi**：

```ts
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
```

注意删除原来 `setTimeout(() => loadPositions(), 1000)` 的旧逻辑。

**3f. style 区加：**

```scss
  .account-toolbar {
    display: flex;
    align-items: center;
  }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd web-frontend && npx vitest run tests/unit/Portfolio.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/views/Portfolio/index.vue web-frontend/tests/unit/Portfolio.test.ts
git commit -m "feat(web): Portfolio 页接入 AccountSwitcher，交易改走 simulation trade API"
```

---

### Task 4: Dashboard 修复 summary 调用

**Files:**
- Modify: `web-frontend/src/views/Dashboard/index.vue:206-231`
- Modify: `web-frontend/tests/unit/DashboardPendingTasks.test.ts:14-21`

- [ ] **Step 1: 改测试（先红）**

`web-frontend/tests/unit/DashboardPendingTasks.test.ts` 中 `vi.mock('@/services/api/trading', ...)` 块之后新增 simulationApi mock：

```ts
vi.mock('@/services/api/simulation', () => ({
  simulationApi: {
    listAccounts: vi.fn().mockResolvedValue({
      accounts: [{ account_name: 'agent_virtual' }],
      total: 1
    })
  }
}))
```

并把 trading mock 的 `getPortfolioSummary` 改为断言接收账户名（在 mock 定义里保持返回即可，测试断言不变——Dashboard 正常挂载即证明链路通）：

```ts
vi.mock('@/services/api/trading', () => ({
  tradingApi: {
    getPortfolioSummary: vi.fn().mockResolvedValue({
      totalValue: 100000,
      dailyChange: 100
    })
  }
}))
```

- [ ] **Step 2: 跑测试确认当前失败**

Run: `cd web-frontend && npx vitest run tests/unit/DashboardPendingTasks.test.ts`
Expected: 现 Dashboard 直接调 `getPortfolioSummary()` 无参——测试可能仍绿（mock 不校验参数）。若绿，直接进入 Step 3 并在 Step 4 用断言锁行为；若红则预期内。

- [ ] **Step 3: 修改 Dashboard**

`web-frontend/src/views/Dashboard/index.vue`：

script 顶部 import 加：

```ts
import { simulationApi } from '@/services/api/simulation'
```

`fetchPortfolioSummary` 改为：

```ts
// 获取投资组合概览数据（多账户：优先 agent_virtual，否则第一个账户）
const fetchPortfolioSummary = async () => {
  try {
    const { accounts } = await simulationApi.listAccounts()
    const account = accounts.find(a => a.account_name === 'agent_virtual') || accounts[0]
    if (!account) return  // 无账户时静默显示 0

    const data = await tradingApi.getPortfolioSummary(account.account_name)

    // 总资产 = 持仓市值 + 现金
    totalAssets.value = `¥${data.totalValue?.toLocaleString() || '0'}`

    // 流动资产（现金）
    const cash = data.cash || data.liquidAssets || 0
    liquidAssets.value = `¥${Number(cash).toLocaleString()}`

    // 持仓盈亏（未实现盈亏）
    const pnl = data.totalPnl || 0
    unrealizedPnL.value = formatSignedCurrency(pnl)
    unrealizedPnLClass.value = pnl >= 0 ? 'success' : 'danger'

    const change = data.dailyChange || 0
    dailyPnL.value = formatSignedCurrency(change)
    dailyPnLClass.value = change >= 0 ? 'success' : 'danger'

    // TODO: 从其他接口获取待审批信号和风险预警数量
    pendingSignals.value = 0
    riskAlerts.value = 0
  } catch (error) {
    console.error('获取投资组合概览失败:', error)
  }
}
```

（除新增选账户逻辑和 `getPortfolioSummary(account.account_name)` 外，函数体其余部分保持原样。）

- [ ] **Step 4: 跑测试确认通过 + 补参数断言**

Run: `cd web-frontend && npx vitest run tests/unit/DashboardPendingTasks.test.ts tests/unit/Dashboard.test.ts tests/unit/DashboardButtons.test.ts`
Expected: PASS

在 `DashboardPendingTasks.test.ts` 的用例末尾补一行断言（锁定账户透传行为）：

```ts
    const { tradingApi } = await import('@/services/api/trading')
    expect(tradingApi.getPortfolioSummary).toHaveBeenCalledWith('agent_virtual')
```

再跑一次确认仍 PASS。

- [ ] **Step 5: Commit**

```bash
git add web-frontend/src/views/Dashboard/index.vue web-frontend/tests/unit/DashboardPendingTasks.test.ts
git commit -m "fix(web): Dashboard 持仓概览按账户查询（优先 agent_virtual）"
```

---

### Task 5: 全量回归 + 合并准备

**Files:** 无新增

- [ ] **Step 1: 全量前端测试**

Run: `cd web-frontend && npm test`
Expected: 全部 PASS（含既有 17+ 测试文件；重点确认 `api-contract.test.ts`、`simulation-envelope-contract.test.ts`、`AccountSwitcher.test.ts`、`SimulationTrading.test.ts` 不受影响）

- [ ] **Step 2: TypeScript 检查**

Run: `cd web-frontend && npx vue-tsc -b`
Expected: 无类型错误（重点：`fetchAll`/`getPositions`/`getPortfolioSummary` 签名变化后无遗漏调用方 —— `grep -rn "fetchAll\|getPortfolioSummary\|getPositions" web-frontend/src` 应只有 Portfolio 页、Dashboard、store 本身）

- [ ] **Step 3: 真机冒烟（可选但推荐）**

后端在线时：`cd web-frontend && npm run dev`，打开 `http://localhost:3001/portfolio`，确认：
1. 账户切换器列出账户并默认选中第一个
2. 持仓/汇总按账户加载，无 400
3. 切账户后表格刷新

- [ ] **Step 4: 合并回 main**

按仓库规则（CLAUDE.md 多会话并行工作规则）：worktree 内验证完成后，回主工作区合并：

```bash
cd /Users/mac/Documents/ai/pi-investment
git merge worktree-portfolio-multi-account
```

合并后删除 worktree（ExitWorktree action: remove），推送由用户确认后执行。
