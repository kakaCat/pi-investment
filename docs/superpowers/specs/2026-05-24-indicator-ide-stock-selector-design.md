# 指标IDE测试股票选择器设计文档

**日期：** 2026-05-24  
**功能：** 在指标IDE中添加可交互的股票选择器，替代硬编码的默认测试股票

## 需求概述

当前指标IDE使用硬编码的股票代码（600519 贵州茅台）作为测试股票。用户希望能够在页面上选择不同的股票进行指标测试和回测，而不是每次都修改代码。

## 设计决策

### 核心决策
1. **位置：** 股票选择器放在右侧"实时预览"卡片的 header 区域
2. **输入方式：** 使用 Element Plus Select 组件，支持远程搜索 + 持仓/自选股快捷选择
3. **数据源：** 从后端 API 获取用户持仓和自选股，搜索时调用股票搜索接口
4. **触发方式：** 切换股票后不自动运行，用户需手动点击"运行"按钮
5. **搜索实现：** 后端实时搜索，前端防抖 300ms

### 为什么选择这些方案
- **位置选择：** 预览卡片是测试结果展示区域，股票选择器作为测试参数放在这里语义清晰，不干扰代码编辑流程
- **Element Plus Select：** 可以分组展示持仓/自选股和搜索结果，用户体验好，开发成本适中
- **后端搜索：** 数据完整且实时，支持拼音搜索等复杂匹配逻辑
- **手动触发：** 避免频繁的自动计算，用户可以先选好股票再运行，节省资源

## UI 设计

### 布局结构

```
┌─ 实时预览卡片 ─────────────────────┐
│ 📈 实时预览    [股票选择器 ▼]      │
├────────────────────────────────────┤
│                                    │
│         图表容器                    │
│                                    │
├────────────────────────────────────┤
│ 测试股票：600519 贵州茅台           │
│ 当前值：1850.00 (超买区域)         │
└────────────────────────────────────┘
```

### 选择器样式
- **组件：** `el-select`
- **宽度：** 200px
- **位置：** header 右侧，与"实时预览"标题同行
- **占位符：** `选择测试股票...`
- **显示格式：** `600519 - 贵州茅台`（代码 + 名称）

### 下拉选项分组
1. **我的持仓** - 显示用户当前持有的股票
2. **我的自选** - 显示用户自选股列表
3. **搜索结果** - 用户输入时显示匹配的股票（仅在有搜索时显示）

## 数据流设计

### 前端状态管理

```typescript
// 当前选中的股票
const currentSymbol = ref('600519')
const currentSymbolName = ref('贵州茅台')

// 持仓股票列表
const positionStocks = ref<Array<{ symbol: string; name: string }>>([])

// 自选股列表
const watchlistStocks = ref<Array<{ symbol: string; name: string }>>([])

// 搜索结果
const searchResults = ref<Array<{ symbol: string; name: string; market: string }>>([])

// 加载状态
const searchLoading = ref(false)
```

### 数据流程

1. **页面加载**
   - 调用 API 获取持仓和自选股
   - 填充下拉默认选项
   - 保持默认股票 600519

2. **用户输入搜索**
   - 用户在选择器中输入关键词
   - 防抖 300ms 后调用搜索 API
   - 更新搜索结果到下拉列表

3. **用户选择股票**
   - 更新 `currentSymbol` 和 `currentSymbolName`
   - 同步更新回测表单的默认股票
   - 不自动运行指标

4. **用户点击运行**
   - 使用 `currentSymbol` 调用指标计算 API
   - 更新预览图表和数据

## API 接口设计

### 1. 获取用户持仓和自选股

**接口：** `GET /api/stocks/my-stocks`

或复用现有接口：
- `GET /api/portfolio/positions` (持仓)
- `GET /api/watchlist` (自选股)

**响应格式：**
```json
{
  "positions": [
    { "symbol": "600519", "name": "贵州茅台" },
    { "symbol": "000001", "name": "平安银行" }
  ],
  "watchlist": [
    { "symbol": "600036", "name": "招商银行" },
    { "symbol": "000858", "name": "五粮液" }
  ]
}
```

### 2. 股票搜索接口

**接口：** `GET /api/stocks/search?q={query}`

**查询参数：**
- `q`: 搜索关键词（股票代码或名称）

**响应格式：**
```json
[
  { "symbol": "600519", "name": "贵州茅台", "market": "SH" },
  { "symbol": "600036", "name": "招商银行", "market": "SH" },
  { "symbol": "000858", "name": "五粮液", "market": "SZ" }
]
```

**搜索逻辑：**
- 支持股票代码模糊匹配（如：输入 "6005" 匹配 600519）
- 支持股票名称模糊匹配（如：输入 "茅台" 匹配贵州茅台）
- 支持拼音首字母匹配（如：输入 "gzmt" 匹配贵州茅台）
- 返回前 20 条结果
- 超时时间：5 秒

## 组件实现

### Vue 模板

```vue
<template #header>
  <div class="flex items-center justify-between">
    <div class="flex items-center gap-2">
      <el-icon><TrendCharts /></el-icon>
      <span class="font-bold">实时预览</span>
    </div>
    
    <el-select
      v-model="currentSymbol"
      filterable
      remote
      reserve-keyword
      placeholder="选择测试股票..."
      :remote-method="handleStockSearch"
      :loading="searchLoading"
      style="width: 200px"
      @change="handleStockChange"
    >
      <el-option-group v-if="positionStocks.length > 0" label="我的持仓">
        <el-option
          v-for="stock in positionStocks"
          :key="stock.symbol"
          :label="`${stock.symbol} - ${stock.name}`"
          :value="stock.symbol"
        />
      </el-option-group>
      
      <el-option-group v-if="watchlistStocks.length > 0" label="我的自选">
        <el-option
          v-for="stock in watchlistStocks"
          :key="stock.symbol"
          :label="`${stock.symbol} - ${stock.name}`"
          :value="stock.symbol"
        />
      </el-option-group>
      
      <el-option-group v-if="searchResults.length > 0" label="搜索结果">
        <el-option
          v-for="stock in searchResults"
          :key="stock.symbol"
          :label="`${stock.symbol} - ${stock.name}`"
          :value="stock.symbol"
        />
      </el-option-group>
    </el-select>
  </div>
</template>
```

### TypeScript 逻辑

```typescript
import { ref, watch, onMounted } from 'vue'
import { debounce } from 'lodash-es'
import { ElMessage } from 'element-plus'

// 状态定义
const currentSymbol = ref('600519')
const currentSymbolName = ref('贵州茅台')
const positionStocks = ref<Array<{ symbol: string; name: string }>>([])
const watchlistStocks = ref<Array<{ symbol: string; name: string }>>([])
const searchResults = ref<Array<{ symbol: string; name: string; market: string }>>([])
const searchLoading = ref(false)

// 加载持仓和自选股
const loadMyStocks = async () => {
  try {
    const response = await stockApi.getMyStocks()
    positionStocks.value = response.positions || []
    watchlistStocks.value = response.watchlist || []
  } catch (error) {
    console.error('加载持仓/自选股失败:', error)
    // 失败不阻塞，用户仍可搜索
  }
}

// 防抖搜索
const handleStockSearch = debounce(async (query: string) => {
  if (!query || query.length < 2) {
    searchResults.value = []
    return
  }
  
  searchLoading.value = true
  try {
    const results = await stockApi.searchStocks(query)
    searchResults.value = results
  } catch (error) {
    console.error('搜索股票失败:', error)
    ElMessage.error('搜索股票失败')
  } finally {
    searchLoading.value = false
  }
}, 300)

// 股票切换处理
const handleStockChange = (symbol: string) => {
  // 从所有列表中查找股票名称
  const allStocks = [
    ...positionStocks.value,
    ...watchlistStocks.value,
    ...searchResults.value
  ]
  const stock = allStocks.find(s => s.symbol === symbol)
  
  if (stock) {
    currentSymbolName.value = stock.name
  }
  
  // 不自动运行指标，等用户点击"运行"按钮
}

// 同步回测表单
watch(currentSymbol, (newSymbol) => {
  backtestForm.symbol = newSymbol
})

// 页面加载时初始化
onMounted(() => {
  loadMyStocks()
})
```

### API Service 扩展

在 `web-frontend/src/services/api/stock.ts` 中添加：

```typescript
export const stockApi = {
  /**
   * 获取用户持仓和自选股
   */
  getMyStocks() {
    return apiClient.get<{
      positions: Array<{ symbol: string; name: string }>
      watchlist: Array<{ symbol: string; name: string }>
    }>('/api/stocks/my-stocks')
  },

  /**
   * 搜索股票
   */
  searchStocks(query: string) {
    return apiClient.get<Array<{
      symbol: string
      name: string
      market: string
    }>>('/api/stocks/search', { params: { q: query } })
  }
}
```

## 错误处理

### API 调用失败

1. **持仓/自选股加载失败**
   - 不阻塞页面加载
   - 显示空列表
   - 用户仍可使用搜索功能

2. **搜索 API 失败**
   - 显示错误提示："搜索股票失败"
   - 保留已有的持仓/自选股选项
   - 不清空用户输入

3. **指标运行失败**
   - 保持当前股票选择
   - 显示具体错误信息
   - 用户可以重试或切换股票

### 网络超时

- 搜索超时设置为 5 秒
- 超时后取消请求，提示"搜索超时，请重试"
- 使用 AbortController 取消过期的搜索请求

### 边界情况

1. **用户没有持仓和自选股**
   - 下拉列表只显示搜索结果分组
   - 默认值保持 600519（贵州茅台）

2. **用户输入无效股票代码**
   - el-select 会保持上一次有效的选择
   - 不会清空 currentSymbol

3. **快速切换股票**
   - 防抖确保不会发送过多请求
   - 使用 AbortController 取消未完成的请求

4. **页面刷新后状态保持**
   - 不需要持久化到 localStorage
   - 每次加载使用默认值 600519
   - 用户重新选择即可

5. **无搜索结果**
   - 显示"未找到匹配的股票"
   - 保留持仓/自选股选项可见

## 实现清单

### 前端任务

1. **修改 IndicatorIDE/index.vue**
   - 在预览卡片 header 添加股票选择器
   - 添加状态变量：positionStocks, watchlistStocks, searchResults
   - 实现 loadMyStocks, handleStockSearch, handleStockChange 函数
   - 添加 watch 监听同步回测表单

2. **扩展 services/api/stock.ts**
   - 添加 getMyStocks 方法
   - 添加 searchStocks 方法

3. **更新 types/indicator.ts**（如需要）
   - 添加股票搜索相关类型定义

### 后端任务

1. **实现 GET /api/stocks/my-stocks**
   - 查询用户持仓表
   - 查询用户自选股表
   - 返回合并结果

2. **实现 GET /api/stocks/search**
   - 支持股票代码模糊匹配
   - 支持股票名称模糊匹配
   - 支持拼音首字母匹配
   - 限制返回 20 条结果
   - 设置 5 秒超时

### 测试任务

1. **单元测试**
   - 测试防抖搜索逻辑
   - 测试股票切换处理
   - 测试错误处理

2. **集成测试**
   - 测试完整的选择 → 运行流程
   - 测试 API 失败场景
   - 测试边界情况

3. **手动测试**
   - 验证 UI 布局和交互
   - 验证搜索性能
   - 验证不同用户场景（有持仓/无持仓）

## 非功能需求

### 性能
- 搜索防抖 300ms，避免频繁请求
- 搜索结果限制 20 条，避免渲染过多选项
- 使用 AbortController 取消过期请求

### 可用性
- 占位符文案清晰："选择测试股票..."
- 分组标签明确："我的持仓"、"我的自选"、"搜索结果"
- 加载状态明确（loading spinner）
- 错误提示友好

### 可维护性
- 使用 Element Plus 标准组件，减少自定义代码
- API 调用集中在 service 层
- 状态管理清晰，职责单一

## 未来扩展

以下功能不在本次实现范围内，但可作为未来优化方向：

1. **最近使用列表** - 记录用户最近测试的股票，快速访问
2. **收藏功能** - 允许用户标记常用测试股票
3. **批量测试** - 支持选择多只股票批量运行指标
4. **股票对比** - 同时显示多只股票的指标结果对比
5. **本地缓存** - 缓存搜索结果，减少 API 调用

## 总结

本设计通过在指标IDE的预览卡片中添加股票选择器，替代硬编码的测试股票，提升用户体验。使用 Element Plus Select 组件实现远程搜索和分组展示，平衡了开发成本和用户体验。后端提供持仓/自选股和搜索接口，前端通过防抖和错误处理确保稳定性。
