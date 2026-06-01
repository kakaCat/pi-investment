# 股票池管理前端页面设计文档

**日期**: 2026-06-01  
**状态**: 设计完成，待实施  
**依赖**: 后端 `/api/pools/*` API（已实现）

## 概述

为 web-frontend 添加股票池管理页面，对接已有的 `/api/pools/*` 后端 API。包含列表页（`/pools`）和详情页（`/pools/:id`），支持池子 CRUD、筛选建池、动态池刷新、多策略验证结果展示。

## 技术栈

- Vue 3 + Composition API (`<script setup>`)
- Element Plus（表格、表单、弹窗、Tag、卡片）
- Axios（通过现有 `apiClient` 封装）
- vue-router（列表→详情跳转）

## 文件结构

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/services/api/pool.ts` | Pool API service（CRUD + 操作） |
| `src/views/PoolList/index.vue` | 池子列表页 `/pools` |
| `src/views/PoolDetail/index.vue` | 池子详情页 `/pools/:id` |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/router/index.ts` | 添加 `/pools` 和 `/pools/:id` 路由 |
| `src/services/api/index.ts` | 导出 `poolApi` |
| `src/components/layout/MainLayout.vue` | 添加"股票池"菜单项 |

## 路由配置

```typescript
{
  path: '/pools',
  name: 'PoolList',
  component: () => import('@/views/PoolList/index.vue'),
  meta: { title: '股票池' }
},
{
  path: '/pools/:id',
  name: 'PoolDetail',
  component: () => import('@/views/PoolDetail/index.vue'),
  meta: { title: '股票池详情' }
}
```

菜单图标使用 Element Plus `Grid` 图标，放在"机会雷达"和"回测中心"之间。

## API Service

```typescript
// src/services/api/pool.ts
import { apiClient } from './client'

export const poolApi = {
  // CRUD
  list():                                GET /api/pools
  getById(id: number):                   GET /api/pools/:id
  create(data: PoolCreateParams):        POST /api/pools
  update(id: number, data):              PUT /api/pools/:id
  delete(id: number):                    DELETE /api/pools/:id

  // 操作
  refresh(id: number):                   POST /api/pools/:id/refresh
  validate(id: number, params?):         POST /api/pools/:id/validate
  scanAndCreate(data):                   POST /api/pools/scan-and-create
}
```

**类型定义**（内联在 pool.ts 中）：

```typescript
interface PoolCreateParams {
  name: string
  poolType: 'static' | 'dynamic'
  symbols?: string[]
  filterTemplate?: FilterTemplate
  refreshInterval?: 'daily' | 'weekly'
  description?: string
}

interface FilterTemplate {
  min_score?: number
  max_risk_level?: string
  technical?: string[]
  fundamental?: string[]
  top_n?: number
}

interface PoolValidateParams {
  strategyIds?: number[]
  startDate?: string
  endDate?: string
}

interface PoolScanCreateParams {
  name: string
  poolType: 'static' | 'dynamic'
  filter: FilterTemplate
  refreshInterval?: 'daily' | 'weekly'
  description?: string
}
```

## 列表页 `/pools`

### 顶部统计卡片（3个）

```
[📊 池子总数: 5]  [📌 静态池: 2]  [🔄 动态池: 3]
```

使用 `el-row :gutter="24"` + `el-col :xs="24" :sm="8"` + `el-card class="stat-card"` 布局。从列表数据中计算统计值（不需要额外 API）。

### 操作栏

两个按钮，右对齐：
- 「创建静态池」→ 弹窗
- 「筛选建池」→ 弹窗

### 创建静态池弹窗

```
名称:        [输入框]
描述:        [输入框]（可选）
股票代码:    [文本域，逗号分隔，如 600519.SH, 000858.SZ]
```

调用 `poolApi.create({ name, poolType: 'static', symbols, description })`

### 筛选建池弹窗

```
名称:        [输入框]
类型:        [单选: 静态 / 动态]
技术面条件:  [多选: RSI超卖, MACD金叉, 布林突破, 放量突破]
基本面条件:  [多选: 低PE, 高ROE, 高毛利, 低负债]
最低评分:    [滑块 0-100，默认60]
取前N只:     [数字输入，默认20]
刷新周期:    [单选: 每日/每周]（仅动态池显示）
描述:        [输入框]（可选）
```

调用 `poolApi.scanAndCreate({ name, poolType, filter: {...}, refreshInterval, description })`

### 表格

| 列 | 字段 | 宽度 | 渲染 |
|---|---|---|---|
| ID | id | 60px | 文本 |
| 名称 | name | — | `el-link` 点击跳转 `/pools/:id` |
| 类型 | pool_type | 80px | `el-tag`：static=蓝色(info)，dynamic=绿色(success) |
| 股票数 | symbol_count | 80px | 数字 |
| 刷新周期 | refresh_interval | 100px | daily/weekly/— |
| 上次刷新 | last_refreshed_at | 150px | 日期格式化，null 显示"—" |
| 已验证 | has_validation | 80px | ✅ / — |
| 创建时间 | created_at | 150px | 日期格式化 |
| 操作 | — | 150px | 刷新按钮(仅动态池) + 删除按钮 |

**删除确认**: `ElMessageBox.confirm('确定删除该股票池？', '提示', { type: 'warning' })`

**空状态**: `el-empty description="暂无股票池"`

## 详情页 `/pools/:id`

### 顶部信息区

```html
<el-page-header @back="router.push('/pools')">
  <template #content>
    {{ pool.name }} <el-tag>{{ pool.pool_type === 'static' ? '静态池' : '动态池' }}</el-tag>
  </template>
  <template #extra>
    <el-button @click="handleRefresh" v-if="pool.pool_type === 'dynamic'">刷新池子</el-button>
    <el-button type="primary" @click="showValidateDialog = true">验证策略</el-button>
    <el-button @click="showEditDialog = true">编辑</el-button>
    <el-button type="danger" @click="handleDelete">删除</el-button>
  </template>
</el-page-header>
```

**信息描述列表**（`el-descriptions`）：
- 描述 | 刷新周期 | 上次刷新时间 | 股票数量 | 创建时间

**筛选条件展示**（仅动态池）：
- 使用 `el-tag` 展示各筛选条件，如 `低PE` `高ROE` `最低分: 60`

### 两个 Tab

使用 `el-tabs`：

#### Tab 1: 成员列表

简洁的 `el-table`：

| 列 | 说明 |
|---|---|
| 序号 | 行号 1, 2, 3... |
| 股票代码 | symbol 字符串 |

#### Tab 2: 验证结果

**无验证数据时**：`el-empty description="尚未执行策略验证"` + 「立即验证」按钮

**有验证数据时**：

**验证摘要**（`el-descriptions`）：
- 验证时间 | 测试策略数 | 池内股票数 | 验证期间

**🏆 最优策略卡片**（`el-card` 高亮样式）：
- 策略名称、综合评分（大字）、收益率、胜率、夏普

**策略排名表格**（`el-table`）：

| 列 | 字段 | 渲染 |
|---|---|---|
| 排名 | index + 1 | 数字 |
| 策略名称 | name | 文本 |
| 综合评分 | score | `el-progress :percentage="score"` |
| 平均收益% | avg_return | 数字，正绿负红 |
| 平均胜率% | avg_win_rate | 数字 |
| 平均夏普 | avg_sharpe | 数字 |
| 平均回撤% | avg_drawdown | 数字，红色 |
| 测试股票数 | stocks_tested | 数字 |

**💡 推荐组合表格**（`el-table`）：

| 列 | 字段 | 渲染 |
|---|---|---|
| 序号 | index + 1 | 数字 |
| 股票代码 | symbol | 文本 |
| 预期收益% | expected_return | 正绿负红 |
| 胜率% | win_rate | 数字 |
| 夏普比率 | sharpe | 数字 |

### 验证策略弹窗

```
策略选择:    [多选下拉，留空=全部活跃策略]
起始日期:    [DatePicker，默认6个月前]
结束日期:    [DatePicker，默认今天]
```

提交后：
1. `ElLoading.service({ fullscreen: true, text: '正在执行策略验证...' })`
2. 调用 `poolApi.validate(id, { strategyIds, startDate, endDate })`
3. 完成后关闭 loading，`ElMessage.success`，重新加载详情数据
4. 失败时 `ElMessage.error`

### 编辑弹窗

```
名称:    [输入框，预填现值]
描述:    [输入框，预填现值]
```

调用 `poolApi.update(id, { name, description })`

## 数据流

```
列表页加载 → poolApi.list() → 渲染表格 + 计算统计
         ↓
      点击池子名 → router.push('/pools/:id')
         ↓
详情页加载 → poolApi.getById(id) → 渲染信息 + 成员 + 验证结果
         ↓
      点击"验证策略" → 弹窗 → poolApi.validate(id, params)
         ↓
      验证完成 → 重新 poolApi.getById(id) → 更新验证结果 Tab
```

## 约束

- 不新建 Pinia store，数据在组件内管理（`ref` + `onMounted` 加载）
- 遵循现有模式：`isAlive` 守护异步回调、`ElMessage` 错误提示
- 策略验证可能耗时数分钟，使用全屏 loading 提示
- 筛选条件选项硬编码（与后端 OpportunityScoringService 支持的一致）
