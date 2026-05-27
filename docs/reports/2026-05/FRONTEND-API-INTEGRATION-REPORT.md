# 前端页面API调用情况分析报告

**项目**: pi-investment  
**日期**: 2026-05-23  
**分析范围**: 20个前端页面组件  
**分析目标**: 识别未调用后端API的页面

---

## 📊 执行摘要

### 总体统计

| 状态 | 页面数 | 占比 | 说明 |
|------|--------|------|------|
| ✅ 完全调用API | 13 | 65% | 正常使用后端接口 |
| ❌ 无API调用 | 4 | 20% | 使用Mock数据或本地状态 |
| ⚠️ 部分调用/降级 | 3 | 15% | API被注释或有降级处理 |
| **总计** | **20** | **100%** | - |

### 关键发现
- 🔴 **4个页面完全未接入后端**（StrategyConfig, DataUpdate, Scheduler, DailyReport）
- 🟡 **3个页面部分接入或降级**（Executions, QuantPipeline, MLEngine）
- 🟢 **13个页面正常工作**（65%的核心功能已接入）

---

## ✅ 完全调用API的页面（13个）

### 核心业务页面

#### 1. Dashboard - 仪表盘 ✅
- **路由**: `/`
- **API调用**:
  - `tradingApi.getPortfolioSummary()` - 持仓汇总
  - `apiClient.get('/api/signals')` - 信号列表
  - `apiClient.get('/api/portfolio/history')` - 资产历史
- **状态**: 完全接入
- **功能**: 展示投资组合概览、最新信号、资产曲线

#### 2. Portfolio - 持仓管理 ✅
- **路由**: `/portfolio`
- **API调用**:
  - `portfolioStore.fetchPositions()` - 获取持仓列表
  - `tradingApi.createOrder()` - 创建订单
- **状态**: 完全接入
- **功能**: 持仓列表、盈亏统计、快速下单

#### 3. SignalList - 信号列表 ✅
- **路由**: `/signals`
- **API调用**:
  - `signalStore.fetchSignals()` - 获取信号列表
  - `signalStore.approveSignal()` - 批准信号
  - `signalStore.rejectSignal()` - 拒绝信号
- **状态**: 完全接入
- **功能**: 信号管理、批准/拒绝操作

#### 4. StockList - 股票列表 ✅
- **路由**: `/stocks`
- **API调用**:
  - `stockApi.getStocks()` - 获取股票列表
- **状态**: 完全接入
- **功能**: 股票浏览、搜索、筛选

#### 5. StockDetail - 股票详情 ✅
- **路由**: `/stock/:symbol`
- **API调用**:
  - `stockApi.getStockDetail()` - 股票基本信息
  - `stockApi.getKLineData()` - K线数据
  - `stockApi.getTechnicalIndicators()` - 技术指标
  - `signalApi.getSignals()` - 相关信号
- **状态**: 完全接入
- **功能**: 股票详情、K线图、技术分析

#### 6. Orders - 订单管理 ✅
- **路由**: `/orders`
- **API调用**:
  - `tradingApi.getOrders()` - 订单列表
  - `tradingApi.createOrder()` - 创建订单
  - `tradingApi.cancelOrder()` - 取消订单
  - `stockApi.searchStocks()` - 搜索股票
- **状态**: 完全接入
- **功能**: 订单CRUD、状态管理

#### 7. Trades - 交易历史 ✅
- **路由**: `/trades`
- **API调用**:
  - `tradingApi.getTrades()` - 交易记录列表
- **状态**: 完全接入
- **功能**: 交易历史查询、统计

#### 8. StrategyCenter - 策略中心 ✅
- **路由**: `/strategy`
- **API调用**:
  - `strategyApi.getStrategies()` - 策略列表
  - `strategyApi.startStrategy()` - 启动策略
  - `strategyApi.stopStrategy()` - 停止策略
  - `strategyApi.createStrategy()` - 创建策略
  - `strategyApi.updateStrategy()` - 更新策略
  - `strategyApi.deleteStrategy()` - 删除策略
- **状态**: 完全接入
- **功能**: 策略管理、启停控制

#### 9. BacktestCenter - 回测中心 ✅
- **路由**: `/backtest`
- **API调用**:
  - `analysisApi.runBacktest()` - 运行回测
  - `tradingApi.createOrder()` - 创建订单
  - `strategyApi.createStrategy()` - 创建策略
- **状态**: 完全接入
- **功能**: 回测配置、结果分析

#### 10. RiskCheck - 风险检查 ✅
- **路由**: `/risk`
- **API调用**:
  - `riskApi.checkRisk()` - 风险检查
  - `riskApi.getStopLossRules()` - 止损规则列表
  - `riskApi.createStopLossRule()` - 创建止损规则
  - `riskApi.updateStopLossRule()` - 更新止损规则
  - `riskApi.deleteStopLossRule()` - 删除止损规则
- **状态**: 完全接入
- **功能**: 风险评估、止损管理

#### 11. OpportunityRadar - 机会雷达 ✅
- **路由**: `/opportunities`
- **API调用**:
  - `analysisApi.getOpportunities()` - 获取机会列表
  - `analysisApi.scanOpportunities()` - 扫描机会
  - `tradingApi.createOrder()` - 创建订单
- **状态**: 完全接入
- **功能**: 投资机会发现、快速下单

#### 12. FactorAnalysis - 因子分析 ✅
- **路由**: `/factor-analysis`
- **API调用**:
  - `stockApi.searchStocks()` - 搜索股票
  - `analysisApi.getFactorAnalysis()` - 因子分析
- **状态**: 完全接入
- **功能**: 多因子分析、股票对比

#### 13. IndicatorIDE - 指标IDE ✅
- **路由**: `/indicator-ide`
- **API调用**:
  - `indicatorApi.getMyIndicators()` - 我的指标
  - `indicatorApi.getSystemIndicators()` - 系统指标
  - `indicatorApi.createIndicator()` - 创建指标
  - `indicatorApi.updateIndicator()` - 更新指标
  - `indicatorApi.publishIndicator()` - 发布指标
  - `indicatorApi.backtestIndicator()` - 回测指标
- **状态**: 完全接入
- **功能**: 指标开发、测试、发布

---

## ❌ 无API调用的页面（4个）

### 1. StrategyConfig - 策略配置 ❌

**路由**: `/strategy-config`

**问题描述**:
- 完全使用本地状态管理（`ref`, `reactive`）
- 所有配置数据仅存储在前端内存中
- 页面刷新后配置丢失

**当前实现**:
```typescript
// 所有数据都是本地状态
const strategies = ref([
  { id: '1', name: '趋势跟踪', enabled: true, ... }
])

// 保存操作仅更新本地状态
const handleSave = () => {
  // 没有API调用
  ElMessage.success('配置已保存')
}
```

**影响**:
- 🔴 配置无法持久化
- 🔴 多设备无法同步
- 🔴 无法团队协作

**建议修复**:
```typescript
// 应该调用后端API
import { strategyApi } from '@/services/api'

const loadConfig = async () => {
  const config = await strategyApi.getStrategyConfig()
  strategies.value = config.strategies
}

const handleSave = async () => {
  await strategyApi.updateStrategyConfig({
    strategies: strategies.value
  })
  ElMessage.success('配置已保存')
}
```

---

### 2. DataUpdate - 数据更新 ❌

**路由**: `/data-update`

**问题描述**:
- `fetchJobs()` 使用硬编码的Mock数据
- `startUpdate()` 仅模拟创建任务，不调用真实API
- 任务状态无法实时更新

**当前实现**:
```typescript
const fetchJobs = () => {
  // Mock数据
  jobs.value = [
    {
      id: '1',
      source: 'hs300',
      status: 'completed',
      // ... 硬编码数据
    }
  ]
}

const startUpdate = (scope: string) => {
  // 仅模拟创建
  const newJob = {
    id: Date.now().toString(),
    source: scope,
    status: 'running'
  }
  jobs.value.unshift(newJob)
}
```

**影响**:
- 🔴 无法查看真实的数据更新任务
- 🔴 无法触发真实的数据更新
- 🔴 任务状态不准确

**建议修复**:
```typescript
import { dataApi } from '@/services/api'

const fetchJobs = async () => {
  const response = await dataApi.getJobs()
  jobs.value = response.items
}

const startUpdate = async (scope: string) => {
  const result = await dataApi.startUpdate({
    scope,
    days: 730,
    forceUpdate: false
  })
  ElMessage.success(`任务已创建: ${result.jobId}`)
  await fetchJobs()
}
```

---

### 3. Scheduler - 调度器 ❌

**路由**: `/scheduler`

**问题描述**:
- 所有任务和历史记录都是硬编码
- 无法创建、修改、删除真实的定时任务
- 无法查看真实的执行历史

**当前实现**:
```typescript
const tasks = ref([
  {
    id: '1',
    name: '每日数据更新',
    schedule: '0 2 * * *',
    enabled: true,
    // ... 硬编码
  }
])

const history = ref([
  {
    id: '1',
    taskId: '1',
    status: 'success',
    // ... 硬编码
  }
])
```

**影响**:
- 🔴 无法管理真实的定时任务
- 🔴 无法查看任务执行历史
- 🔴 功能完全不可用

**建议修复**:
需要后端实现定时任务管理API（可能需要使用APScheduler或Celery）

---

### 4. DailyReport - 每日报告 ❌

**路由**: `/daily-report`

**问题描述**:
- `fetchReport()` 仅显示消息，不获取真实数据
- 所有报告数据都是静态的Mock数据
- 无法生成真实的每日报告

**当前实现**:
```typescript
const fetchReport = () => {
  ElMessage.info('每日报告功能开发中...')
  // 使用静态Mock数据
  report.value = {
    date: '2024-01-15',
    summary: { /* 硬编码 */ },
    signals: [ /* 硬编码 */ ],
    // ...
  }
}
```

**影响**:
- 🔴 无法查看真实的每日报告
- 🔴 数据不准确
- 🔴 功能不可用

**建议修复**:
```typescript
import { apiClient } from '@/services/api'

const fetchReport = async (date?: string) => {
  const response = await apiClient.get('/api/report/daily', {
    params: { date }
  })
  report.value = response.data
}
```

---

## ⚠️ 部分调用/降级处理的页面（3个）

### 1. Executions - 执行记录 ⚠️

**路由**: `/executions`

**问题描述**:
- API调用代码存在但被注释掉
- 标记为 `TODO: 接入真实API`
- 当前返回空数组

**当前实现**:
```typescript
const loadExecutions = async () => {
  loading.value = true
  try {
    // TODO: 接入真实API
    // const response = await apiClient.get('/api/executions')
    // executions.value = response.data
    executions.value = [] // 临时返回空数组
  } finally {
    loading.value = false
  }
}
```

**影响**:
- 🟡 页面可以打开但无数据
- 🟡 功能不完整

**建议修复**:
```typescript
const loadExecutions = async () => {
  loading.value = true
  try {
    const response = await apiClient.get('/api/executions', {
      params: {
        status: filters.value.status,
        limit: 100
      }
    })
    executions.value = response.data.executions
  } catch (error) {
    ElMessage.error('加载执行记录失败')
  } finally {
    loading.value = false
  }
}
```

---

### 2. QuantPipeline - 量化流水线 ⚠️

**路由**: `/pipeline`

**问题描述**:
- `fetchHistory()` 使用Mock数据
- `runPipeline()` 仅模拟流程，不调用真实API
- 有降级处理但数据不真实

**当前实现**:
```typescript
const fetchHistory = () => {
  history.value = [
    {
      id: '1',
      startTime: '2024-01-15 09:00:00',
      status: 'success',
      // ... Mock数据
    }
  ]
}

const runPipeline = () => {
  ElMessage.success('流水线已启动（模拟）')
  // 模拟添加历史记录
}
```

**影响**:
- 🟡 页面可用但数据不真实
- 🟡 无法触发真实的流水线

**建议修复**:
```typescript
import { pipelineApi } from '@/services/api'

const fetchHistory = async () => {
  const response = await pipelineApi.getRunsList()
  history.value = response.items
}

const runPipeline = async () => {
  await pipelineApi.trigger({
    symbols: selectedSymbols.value,
    stages: selectedStages.value
  })
  ElMessage.success('流水线已启动')
  await fetchHistory()
}
```

---

### 3. MLEngine - ML引擎 ⚠️

**路由**: `/ml-engine`

**问题描述**:
- `handleTrain()` 和 `handlePredict()` 有try-catch降级
- API失败时使用模拟数据
- 有真实API调用但有降级处理

**当前实现**:
```typescript
const handleTrain = async () => {
  try {
    // 尝试调用真实API
    const response = await apiClient.post('/api/ml/train', trainConfig.value)
    trainResult.value = response.data
  } catch (error) {
    // 降级：使用模拟数据
    ElMessage.warning('使用模拟训练结果')
    trainResult.value = {
      accuracy: 0.85,
      loss: 0.15,
      // ... Mock数据
    }
  }
}
```

**影响**:
- 🟡 有API调用但有降级
- 🟡 用户可能看到模拟数据

**建议**:
- 保持当前实现（降级处理是合理的）
- 确保后端ML API稳定可用
- 在UI上明确标识是否为模拟数据

---

## 📊 API调用模块使用统计

| API模块 | 使用页面数 | 主要功能 |
|---------|-----------|---------|
| `tradingApi` | 7 | 订单、持仓、交易 |
| `stockApi` | 5 | 股票查询、详情 |
| `strategyApi` | 3 | 策略管理 |
| `signalApi` | 2 | 信号管理 |
| `analysisApi` | 3 | 分析、回测 |
| `riskApi` | 1 | 风险检查 |
| `indicatorApi` | 1 | 指标开发 |
| `dataApi` | 0 | ❌ 未使用（DataUpdate页面未接入） |
| `pipelineApi` | 0 | ❌ 未使用（QuantPipeline页面未接入） |

---

## 🎯 修复优先级建议

### P0 - 高优先级（影响核心功能）

1. **Executions - 执行记录** 🔴
   - 取消注释API调用代码
   - 工作量: 1小时
   - 影响: 执行记录功能完全不可用

2. **DataUpdate - 数据更新** 🔴
   - 接入 `dataApi.getJobs()` 和 `dataApi.startUpdate()`
   - 工作量: 2小时
   - 影响: 无法管理数据更新任务

### P1 - 中优先级（影响用户体验）

3. **StrategyConfig - 策略配置** 🟡
   - 实现配置持久化API
   - 工作量: 4小时（需要后端支持）
   - 影响: 配置无法保存

4. **DailyReport - 每日报告** 🟡
   - 接入 `/api/report/daily` 接口
   - 工作量: 2小时
   - 影响: 报告数据不准确

### P2 - 低优先级（可延后）

5. **Scheduler - 调度器** 🟢
   - 需要后端实现定时任务管理
   - 工作量: 8小时（需要后端APScheduler集成）
   - 影响: 功能完全不可用，但可能不是核心需求

6. **QuantPipeline - 量化流水线** 🟢
   - 接入真实的流水线API
   - 工作量: 3小时
   - 影响: 使用Mock数据

---

## 📋 修复检查清单

### 立即修复（本周）
- [ ] Executions: 取消注释API调用
- [ ] DataUpdate: 接入dataApi
- [ ] 验证修复后的功能

### 短期修复（本月）
- [ ] StrategyConfig: 实现配置API
- [ ] DailyReport: 接入报告API
- [ ] 更新前端类型定义

### 长期规划（下季度）
- [ ] Scheduler: 后端定时任务系统
- [ ] QuantPipeline: 完整的流水线管理
- [ ] 补充单元测试

---

## 💡 技术建议

### 1. 统一Mock数据管理
建议创建 `src/mocks/` 目录，统一管理所有Mock数据：
```
src/mocks/
  ├── strategy-config.ts
  ├── scheduler.ts
  ├── daily-report.ts
  └── index.ts
```

### 2. 添加开发模式标识
在使用Mock数据的页面添加明显标识：
```vue
<el-alert v-if="isDevelopment" type="warning">
  当前使用模拟数据，实际功能开发中
</el-alert>
```

### 3. API调用统一错误处理
建议在 `apiClient` 中添加统一的错误处理和降级策略。

### 4. 添加API调用监控
建议添加API调用成功率监控，及时发现未接入的接口。

---

## 📈 改进建议

### 代码质量
1. 为所有API调用添加TypeScript类型
2. 统一错误处理和加载状态
3. 添加API调用的单元测试

### 用户体验
1. 明确标识Mock数据页面
2. 添加功能开发进度提示
3. 优化加载和错误状态展示

### 文档完善
1. 更新API文档，标注已接入/未接入状态
2. 添加前端页面功能清单
3. 维护API接口变更日志

---

## 📞 附录

### 相关文档
- [API集成分析报告](API-INTEGRATION-ANALYSIS.md)
- [API集成修复报告](API-INTEGRATION-FINAL-REPORT.md)
- [测试脚本](quantsys-v2/test_api_fixes.py)

### 联系方式
如有问题或建议，请联系开发团队。

---

**报告生成时间**: 2026-05-23 20:20  
**分析页面数**: 20个  
**完全接入**: 13个 (65%)  
**未接入**: 4个 (20%)  
**部分接入**: 3个 (15%)
