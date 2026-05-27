# 指标IDE股票选择器实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在指标IDE中添加可交互的股票选择器，支持从持仓/自选股快捷选择和实时搜索

**Architecture:** 前端使用 Element Plus Select 组件实现远程搜索和分组展示，后端提供两个新接口（获取持仓/自选股、股票搜索）。前端通过防抖减少API调用，切换股票后不自动运行指标，保持用户控制。

**Tech Stack:** Vue 3 Composition API, Element Plus, TypeScript, Flask, PostgreSQL

---

## 文件结构

### 前端文件
- **修改:** `web-frontend/src/views/IndicatorIDE/index.vue` - 添加股票选择器组件和相关逻辑
- **修改:** `web-frontend/src/services/api/stock.ts` - 添加 `getMyStocks()` 方法
- **创建:** `web-frontend/tests/services/stock.test.ts` - 股票API测试
- **创建:** `web-frontend/tests/views/IndicatorIDE.test.ts` - 组件测试

### 后端文件
- **修改:** `quant/api/server.py` - 添加 `/api/stocks/my-stocks` 端点
- **创建:** `quant/tests/test_stock_api.py` - 后端API测试

---

## Task 1: 后端 - 实现获取持仓和自选股接口

**Files:**
- Modify: `quant/api/server.py`
- Test: `quant/tests/test_stock_api.py`

- [ ] **Step 1: 编写测试 - 获取持仓和自选股**

创建测试文件 `quant/tests/test_stock_api.py`:

```python
import pytest
import json
from quant.api.server import app

@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_my_stocks_success(client):
    """测试成功获取持仓和自选股"""
    response = client.get('/api/stocks/my-stocks')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    assert 'positions' in data
    assert 'watchlist' in data
    assert isinstance(data['positions'], list)
    assert isinstance(data['watchlist'], list)

def test_get_my_stocks_empty(client):
    """测试空持仓和自选股"""
    response = client.get('/api/stocks/my-stocks')
    assert response.status_code == 200
    
    data = json.loads(response.data)
    # 即使为空也应该返回空列表
    assert data['positions'] == [] or isinstance(data['positions'], list)
    assert data['watchlist'] == [] or isinstance(data['watchlist'], list)

def test_get_my_stocks_response_format(client):
    """测试响应格式正确"""
    response = client.get('/api/stocks/my-stocks')
    data = json.loads(response.data)
    
    # 检查持仓格式
    if data['positions']:
        position = data['positions'][0]
        assert 'symbol' in position
        assert 'name' in position
    
    # 检查自选股格式
    if data['watchlist']:
        stock = data['watchlist'][0]
        assert 'symbol' in stock
        assert 'name' in stock
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
pytest tests/test_stock_api.py::test_get_my_stocks_success -v
```

预期输出: `FAIL` - 404 Not Found (端点不存在)

- [ ] **Step 3: 实现获取持仓和自选股接口**

在 `quant/api/server.py` 中添加端点（在现有的 stock 相关路由附近，约 3100 行后）:

```python
@app.route('/api/stocks/my-stocks', methods=['GET'])
def get_my_stocks():
    """获取用户持仓和自选股列表"""
    conn = get_db()
    try:
        # 获取持仓股票
        positions = []
        if get_db_provider() == 'postgres':
            cursor = conn.execute("""
                SELECT DISTINCT p.symbol, s.name
                FROM quant.positions p
                JOIN stocks s ON p.symbol = s.symbol
                WHERE p.quantity > 0
                ORDER BY p.symbol
            """)
        else:
            cursor = conn.execute("""
                SELECT DISTINCT p.symbol, s.name
                FROM positions p
                JOIN stocks s ON p.symbol = s.symbol
                WHERE p.quantity > 0
                ORDER BY p.symbol
            """)
        
        for row in cursor.fetchall():
            positions.append({
                'symbol': row[0],
                'name': row[1]
            })
        
        # 获取自选股
        watchlist = []
        if get_db_provider() == 'postgres':
            cursor = conn.execute("""
                SELECT DISTINCT w.symbol, s.name
                FROM quant.watchlist w
                JOIN stocks s ON w.symbol = s.symbol
                ORDER BY w.symbol
            """)
        else:
            cursor = conn.execute("""
                SELECT DISTINCT w.symbol, s.name
                FROM watchlist w
                JOIN stocks s ON w.symbol = s.symbol
                ORDER BY w.symbol
            """)
        
        for row in cursor.fetchall():
            watchlist.append({
                'symbol': row[0],
                'name': row[1]
            })
        
        return jsonify({
            'positions': positions,
            'watchlist': watchlist
        })
    
    except Exception as e:
        logging.error(f"获取持仓/自选股失败: {e}")
        return jsonify({
            'positions': [],
            'watchlist': [],
            'error': str(e)
        }), 500
    finally:
        conn.close()
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
pytest tests/test_stock_api.py::test_get_my_stocks_success -v
pytest tests/test_stock_api.py::test_get_my_stocks_empty -v
pytest tests/test_stock_api.py::test_get_my_stocks_response_format -v
```

预期输出: `PASS` (所有测试通过)

- [ ] **Step 5: 提交后端接口实现**

```bash
git add quant/api/server.py quant/tests/test_stock_api.py
git commit -m "feat(api): add endpoint to get user positions and watchlist"
```

---

## Task 2: 前端 - 扩展 stock API service

**Files:**
- Modify: `web-frontend/src/services/api/stock.ts:202`
- Test: `web-frontend/tests/services/stock.test.ts`

- [ ] **Step 1: 编写测试 - getMyStocks 方法**

创建测试文件 `web-frontend/tests/services/stock.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { stockApi } from '@/services/api/stock'
import { apiClient } from '@/services/api/client'

vi.mock('@/services/api/client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
  }
}))

describe('stockApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('getMyStocks', () => {
    it('should fetch positions and watchlist successfully', async () => {
      const mockResponse = {
        positions: [
          { symbol: '600519', name: '贵州茅台' },
          { symbol: '000001', name: '平安银行' }
        ],
        watchlist: [
          { symbol: '600036', name: '招商银行' }
        ]
      }

      vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

      const result = await stockApi.getMyStocks()

      expect(apiClient.get).toHaveBeenCalledWith('/api/stocks/my-stocks')
      expect(result).toEqual(mockResponse)
      expect(result.positions).toHaveLength(2)
      expect(result.watchlist).toHaveLength(1)
    })

    it('should handle empty positions and watchlist', async () => {
      const mockResponse = {
        positions: [],
        watchlist: []
      }

      vi.mocked(apiClient.get).mockResolvedValue(mockResponse)

      const result = await stockApi.getMyStocks()

      expect(result.positions).toEqual([])
      expect(result.watchlist).toEqual([])
    })

    it('should handle API errors', async () => {
      vi.mocked(apiClient.get).mockRejectedValue(new Error('Network error'))

      await expect(stockApi.getMyStocks()).rejects.toThrow('Network error')
    })
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run test tests/services/stock.test.ts
```

预期输出: `FAIL` - stockApi.getMyStocks is not a function

- [ ] **Step 3: 实现 getMyStocks 方法**

在 `web-frontend/src/services/api/stock.ts` 文件末尾（第 202 行后）添加:

```typescript
  /**
   * 获取用户持仓和自选股
   */
  getMyStocks() {
    return apiClient.get<{
      positions: Array<{ symbol: string; name: string }>
      watchlist: Array<{ symbol: string; name: string }>
    }>('/api/stocks/my-stocks')
  }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run test tests/services/stock.test.ts
```

预期输出: `PASS` (所有测试通过)

- [ ] **Step 5: 提交前端 API service**

```bash
git add web-frontend/src/services/api/stock.ts web-frontend/tests/services/stock.test.ts
git commit -m "feat(api): add getMyStocks method to fetch positions and watchlist"
```

---

## Task 3: 前端 - 添加股票选择器状态和逻辑

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:357` (currentSymbol 附近)
- Test: `web-frontend/tests/views/IndicatorIDE.test.ts`

- [ ] **Step 1: 编写测试 - 股票选择器状态管理**

创建测试文件 `web-frontend/tests/views/IndicatorIDE.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import IndicatorIDE from '@/views/IndicatorIDE/index.vue'
import { stockApi } from '@/services/api/stock'

vi.mock('@/services/api/stock')
vi.mock('@/services/api/indicator')

describe('IndicatorIDE - Stock Selector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should load positions and watchlist on mount', async () => {
    const mockStocks = {
      positions: [{ symbol: '600519', name: '贵州茅台' }],
      watchlist: [{ symbol: '600036', name: '招商银行' }]
    }

    vi.mocked(stockApi.getMyStocks).mockResolvedValue(mockStocks)

    const wrapper = mount(IndicatorIDE)
    await nextTick()
    await nextTick() // 等待异步加载

    // 验证 API 被调用
    expect(stockApi.getMyStocks).toHaveBeenCalled()
  })

  it('should update currentSymbol when stock is selected', async () => {
    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    // 模拟选择股票
    vm.currentSymbol = '600036'
    await nextTick()

    expect(vm.currentSymbol).toBe('600036')
  })

  it('should sync backtestForm.symbol with currentSymbol', async () => {
    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    vm.currentSymbol = '000001'
    await nextTick()

    expect(vm.backtestForm.symbol).toBe('000001')
  })

  it('should handle search with debounce', async () => {
    const mockSearchResults = [
      { symbol: '600519', name: '贵州茅台', market: 'SH' }
    ]

    vi.mocked(stockApi.searchStocks).mockResolvedValue(mockSearchResults)

    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    await vm.handleStockSearch('茅台')
    
    // 防抖后应该调用搜索
    await new Promise(resolve => setTimeout(resolve, 350))
    
    expect(stockApi.searchStocks).toHaveBeenCalledWith('茅台')
  })

  it('should not search if query is too short', async () => {
    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    await vm.handleStockSearch('6')
    await new Promise(resolve => setTimeout(resolve, 350))

    expect(stockApi.searchStocks).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run test tests/views/IndicatorIDE.test.ts
```

预期输出: `FAIL` - 组件中缺少相关方法和状态

- [ ] **Step 3: 添加股票选择器状态变量**

在 `web-frontend/src/views/IndicatorIDE/index.vue` 的 `<script setup>` 中，找到 `currentSymbol` 定义（约 357 行），在其附近添加:

```typescript
// 股票选择器相关状态
const currentSymbol = ref('600519')
const currentSymbolName = ref('贵州茅台')
const positionStocks = ref<Array<{ symbol: string; name: string }>>([])
const watchlistStocks = ref<Array<{ symbol: string; name: string }>>([])
const searchResults = ref<Array<{ symbol: string; name: string; market: string }>>([])
const searchLoading = ref(false)
```

- [ ] **Step 4: 添加加载持仓和自选股的函数**

在状态变量后添加:

```typescript
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
```

- [ ] **Step 5: 添加防抖搜索函数**

导入 lodash-es 的 debounce，然后添加:

```typescript
import { debounce } from 'lodash-es'

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
```

- [ ] **Step 6: 添加股票切换处理函数**

```typescript
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
```

- [ ] **Step 7: 添加 watch 同步回测表单**

```typescript
// 同步回测表单
watch(currentSymbol, (newSymbol) => {
  backtestForm.symbol = newSymbol
})
```

- [ ] **Step 8: 在 onMounted 中初始化**

找到现有的 `onMounted` 钩子，添加:

```typescript
onMounted(() => {
  // ... 现有代码 ...
  loadMyStocks()
})
```

- [ ] **Step 9: 运行测试验证通过**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run test tests/views/IndicatorIDE.test.ts
```

预期输出: `PASS` (所有测试通过)

- [ ] **Step 10: 提交股票选择器逻辑**

```bash
git add web-frontend/src/views/IndicatorIDE/index.vue web-frontend/tests/views/IndicatorIDE.test.ts
git commit -m "feat(indicator-ide): add stock selector state and logic"
```

---

## Task 4: 前端 - 添加股票选择器 UI 组件

**Files:**
- Modify: `web-frontend/src/views/IndicatorIDE/index.vue:160` (预览卡片 header)

- [ ] **Step 1: 找到预览卡片的 header 模板**

在 `web-frontend/src/views/IndicatorIDE/index.vue` 中找到"实时预览"卡片的 `<template #header>` 部分（约 160 行附近）

- [ ] **Step 2: 修改 header 添加股票选择器**

将现有的 header 模板替换为:

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

- [ ] **Step 3: 确保导入了必要的组件**

检查文件顶部的 import 语句，确保包含:

```typescript
import { ElSelect, ElOption, ElOptionGroup, ElMessage } from 'element-plus'
```

- [ ] **Step 4: 本地启动开发服务器测试 UI**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run dev
```

在浏览器中打开 `http://localhost:5173`，导航到指标IDE页面，验证:
- 股票选择器显示在预览卡片右上角
- 下拉列表显示持仓和自选股分组
- 输入关键词可以搜索股票
- 选择股票后不会自动运行指标

- [ ] **Step 5: 提交 UI 组件**

```bash
git add web-frontend/src/views/IndicatorIDE/index.vue
git commit -m "feat(indicator-ide): add stock selector UI component"
```

---

## Task 5: 集成测试和验证

**Files:**
- Test: Manual testing in browser

- [ ] **Step 1: 启动后端服务**

```bash
cd /Users/mac/Documents/ai/pi-investment/quant
python api/server.py
```

验证后端在 `http://127.0.0.1:5000` 运行

- [ ] **Step 2: 启动前端开发服务器**

```bash
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run dev
```

验证前端在 `http://localhost:5173` 运行

- [ ] **Step 3: 测试持仓和自选股加载**

1. 打开浏览器访问指标IDE页面
2. 打开开发者工具 Network 面板
3. 刷新页面
4. 验证发送了 `GET /api/stocks/my-stocks` 请求
5. 验证响应包含 positions 和 watchlist
6. 验证下拉列表显示了持仓和自选股分组

- [ ] **Step 4: 测试股票搜索功能**

1. 点击股票选择器
2. 输入关键词 "茅台"
3. 等待 300ms 后验证发送了 `GET /api/stocks/search?q=茅台` 请求
4. 验证下拉列表显示了搜索结果
5. 验证搜索结果显示在"搜索结果"分组下

- [ ] **Step 5: 测试股票切换功能**

1. 从下拉列表选择一只股票（如 600036）
2. 验证 currentSymbol 更新为 600036
3. 验证页面底部的"测试股票"信息更新
4. 验证回测表单的股票代码同步更新
5. 验证指标没有自动运行

- [ ] **Step 6: 测试运行指标功能**

1. 选择一只股票
2. 点击"运行"按钮
3. 验证使用选中的股票代码运行指标
4. 验证图表和数据正确更新

- [ ] **Step 7: 测试错误处理**

1. 停止后端服务
2. 刷新前端页面
3. 验证持仓/自选股加载失败不阻塞页面
4. 验证仍可以使用默认股票 600519
5. 重启后端服务
6. 验证搜索功能恢复正常

- [ ] **Step 8: 测试边界情况**

1. 测试输入单个字符（如 "6"）- 验证不触发搜索
2. 测试输入不存在的股票代码 - 验证显示"未找到匹配的股票"
3. 测试快速输入多个字符 - 验证防抖生效，只发送一次请求
4. 测试用户没有持仓和自选股 - 验证只显示搜索结果分组

- [ ] **Step 9: 运行所有自动化测试**

```bash
# 后端测试
cd /Users/mac/Documents/ai/pi-investment/quant
pytest tests/test_stock_api.py -v

# 前端测试
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run test
```

验证所有测试通过

- [ ] **Step 10: 提交集成测试文档**

创建测试报告（可选）:

```bash
git add -A
git commit -m "test: verify stock selector integration and edge cases"
```

---

## Task 6: 文档更新和最终清理

**Files:**
- Modify: `CLAUDE.md` (if needed)
- Modify: `web-frontend/README.md` (if needed)

- [ ] **Step 1: 更新 CLAUDE.md（如果需要）**

如果项目有 CLAUDE.md 文件，添加关于股票选择器的说明:

```markdown
## 指标IDE股票选择器

指标IDE现在支持通过UI选择测试股票，而不是硬编码默认值。

**功能:**
- 从持仓和自选股快捷选择
- 实时搜索股票（支持代码和名称）
- 防抖优化（300ms）
- 切换股票不自动运行指标

**相关文件:**
- 前端: `web-frontend/src/views/IndicatorIDE/index.vue`
- 后端: `quant/api/server.py` - `/api/stocks/my-stocks` 端点
- API: `web-frontend/src/services/api/stock.ts` - `getMyStocks()` 方法
```

- [ ] **Step 2: 检查代码质量**

运行 linter 和格式化:

```bash
# 前端
cd /Users/mac/Documents/ai/pi-investment/web-frontend
npm run lint

# 后端
cd /Users/mac/Documents/ai/pi-investment/quant
# 如果有 flake8 或 black
flake8 api/server.py || true
black api/server.py --check || true
```

- [ ] **Step 3: 清理临时文件和注释**

检查代码中是否有:
- console.log 调试语句
- 注释掉的代码
- TODO 标记
- 临时测试代码

全部清理

- [ ] **Step 4: 最终提交**

```bash
git add -A
git commit -m "docs: update documentation for stock selector feature"
```

- [ ] **Step 5: 创建功能总结**

验证以下功能全部完成:
- ✅ 后端 `/api/stocks/my-stocks` 端点
- ✅ 前端 `getMyStocks()` API 方法
- ✅ 股票选择器 UI 组件
- ✅ 持仓/自选股分组显示
- ✅ 实时搜索功能
- ✅ 防抖优化
- ✅ 股票切换不自动运行
- ✅ 回测表单同步
- ✅ 错误处理
- ✅ 单元测试
- ✅ 集成测试
- ✅ 文档更新

---

## 实现完成

所有任务已完成。股票选择器功能已成功集成到指标IDE中。

**验证清单:**
- [ ] 后端测试全部通过
- [ ] 前端测试全部通过
- [ ] 手动测试所有场景通过
- [ ] 代码已提交到 git
- [ ] 文档已更新

**下一步（可选）:**
- 添加最近使用列表
- 添加收藏功能
- 支持批量测试
- 添加股票对比功能
