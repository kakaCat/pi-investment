# 前端开发任务说明（基于现有原型）

**负责人**: [待分配]  
**预计工期**: 3周  
**基础**: 现有原型 `quant-web-v2-prototype.html`

---

## 📋 任务概述

**不是从零开发，而是改造现有原型！**

现有原型位置：
- `/Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html`

这是一个**单页HTML原型**（~1800行），包含17个功能页面，使用Tailwind CSS + 原生JavaScript。

你的任务是：
1. **保留原型的UI设计**（很优秀）
2. **改造为Vue 3项目**（组件化、状态管理）
3. **增加"领导监督Agent"的功能**（核心改动）
4. **对接后端API**（替换静态数据）

---

## 🎯 核心改造点

### 改造1：增加"双角色"概念

**原型现状**：
- 只有一个视角（人操作）
- 没有Agent的概念

**需要改造为**：
```
每个分析页面都有两个标签：
┌─────────────────────────────────┐
│ [🤖 Agent视图] [👔 我的工作台] │ ← 新增
└─────────────────────────────────┘

🤖 Agent视图：
- 展示Agent的分析结果
- 只读，不能修改
- 显示"Agent在10:45分析的"

👔 我的工作台：
- 自己做分析
- 可以操作
- 使用相同的工具
```

### 改造2：增加"Agent工作日志"页面

**原型现状**：
- 没有这个页面

**需要新增**：
```
📋 Agent工作日志页面
- 显示Agent今天做了什么
- 每个操作可以点击查看详情
- 可以复现Agent的分析
```

### 改造3：增加"待审批"功能

**原型现状**：
- 没有审批流程

**需要新增**：
```
⚠️ 待审批列表（在仪表盘和工作台）
- Agent提交的买入/卖出申请
- 可以批准/拒绝
- 可以查看完整分析过程
```

### 改造4：增加"工作详情"弹窗

**原型现状**：
- 没有详细的分析过程展示

**需要新增**：
```
📄 工作详情弹窗
- 展示Agent的7步分析过程
- 每一步可以查看原始数据
- 可以一键复现
- 可以批准/拒绝
```

---

## 📂 原型页面清单（17个）

### 原型已有的页面：

1. ✅ **仪表盘** - 保留，增加"待审批"区域
2. ✅ **股票列表** - 保留
3. ✅ **股票详情** - 改造为"市场研究"，增加双标签
4. ✅ **因子对比** - 保留
5. ✅ **交易信号** - 改造，区分"Agent生成"和"我的分析"
6. ✅ **回测** - 保留
7. ✅ **持仓管理** - 改造，增加"建仓原因"和"操作者"
8. ✅ **交易记录** - 保留
9. ✅ **订单管理** - 改造，增加"审批状态"
10. ✅ **风险管理** - 保留
11. ✅ **执行记录** - 保留
12. ✅ **量化流程** - 保留
13. ✅ **策略配置** - 保留
14. ✅ **ML引擎** - 保留
15. ✅ **定时任务** - 保留
16. ✅ **数据更新** - 保留
17. ✅ **日报** - 保留

### 需要新增的页面：

18. 🆕 **Agent工作日志** - 全新页面
19. 🆕 **Agent绩效评估** - 全新页面
20. 🆕 **工作详情弹窗** - 全新弹窗

---

## 🔧 改造步骤

### 第一步：项目搭建（2天）

```bash
# 1. 创建Vue 3项目
cd /Users/mac/Documents/ai/pi-investment
npm create vite@latest web-frontend -- --template vue-ts
cd web-frontend
npm install

# 2. 安装依赖
npm install vue-router pinia
npm install element-plus
npm install echarts
npm install axios
npm install dayjs

# 3. 配置Tailwind CSS（保持原型风格）
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### 第二步：提取原型资源（3天）

从 `quant-web-v2-prototype.html` 中提取：

1. **提取HTML结构** → 转换为Vue组件
   ```
   原型的每个页面 → 一个Vue组件
   例如：仪表盘的HTML → Dashboard.vue
   ```

2. **提取CSS样式** → 保留Tailwind类名
   ```
   原型使用Tailwind CDN → 项目使用Tailwind配置
   保持相同的颜色、间距、布局
   ```

3. **提取JavaScript逻辑** → 转换为Vue逻辑
   ```
   原型的showPage() → Vue Router
   原型的数据 → Pinia Store
   原型的事件 → Vue事件处理
   ```

### 第三步：改造现有页面（1周）

#### 改造优先级：

**P0（必须）**：
1. ✅ 仪表盘 - 增加"待审批"区域
2. ✅ 持仓管理 - 增加"建仓原因"和"操作者"字段
3. ✅ 订单管理 - 增加"审批状态"和"提交者"字段

**P1（重要）**：
4. ✅ 股票详情 → 市场研究 - 增加双标签（Agent视图 + 我的工作台）
5. ✅ 交易信号 - 区分"Agent生成"和"我的分析"

**P2（可选）**：
6. ✅ 其他页面保持原样，只对接API

### 第四步：新增页面（1周）

1. **Agent工作日志页面**
   - 参考 `docs/frontend-design.md` 的"页面5"
   - 显示Agent的操作记录
   - 可以点击查看详情

2. **Agent绩效评估页面**
   - 显示Agent的准确率、收益贡献
   - 常见错误分析
   - 领导反馈记录

3. **工作详情弹窗**
   - 参考 `docs/frontend-design.md` 的"页面6"
   - 展示完整的分析过程
   - 支持复现和审批

### 第五步：对接API（3天）

替换原型中的静态数据：

```typescript
// 原型中的静态数据
const mockData = {
  positions: [...],
  orders: [...]
};

// 改造为API调用
import { useMainStore } from '@/stores/main';

const store = useMainStore();
await store.fetchPositions(); // 调用 GET /api/portfolio/get-positions
```

---

## 📖 必读文档

### 主要文档：
1. ✅ **现有原型** - `quant-web-v2-prototype.html`（必须先看）
2. ✅ **前端设计** - `docs/frontend-design.md`（新增功能参考）
3. ✅ **后端API** - `docs/backend-api-spec.md`（API接口）

### 参考文档：
4. ✅ **整体架构** - `docs/v2-complete-design-summary.md`
5. ✅ **原型对比** - `docs/v2-prototype-gap-analysis.md`

---

## 🎨 UI设计原则

### 保持原型风格：

1. **颜色方案**（保持不变）
   - 主色：蓝色 `#3b82f6`
   - 成功：绿色 `#10b981`
   - 警告：黄色 `#f59e0b`
   - 危险：红色 `#ef4444`

2. **布局结构**（保持不变）
   - 左侧导航栏
   - 顶部标题栏
   - 主内容区域
   - 卡片式布局

3. **组件风格**（保持不变）
   - 圆角按钮
   - 阴影卡片
   - 表格样式
   - 图表样式

### 新增元素风格：

1. **双标签切换**
   ```html
   <div class="flex border-b">
     <button class="px-4 py-2 border-b-2 border-blue-500">
       🤖 Agent视图
     </button>
     <button class="px-4 py-2">
       👔 我的工作台
     </button>
   </div>
   ```

2. **待审批卡片**
   ```html
   <div class="bg-red-50 border-l-4 border-red-500 p-4">
     <div class="flex items-center">
       <span class="text-red-600">🔴 紧急</span>
       <span class="ml-2">Agent提交买入申请：600519</span>
     </div>
     <div class="mt-2 flex gap-2">
       <button class="btn-primary">批准</button>
       <button class="btn-secondary">拒绝</button>
     </div>
   </div>
   ```

---

## 📊 数据流设计

### 原型的数据流：
```
静态数据 → 直接渲染
```

### 改造后的数据流：
```
后端API → Pinia Store → Vue组件 → 渲染
         ↑
    WebSocket（实时更新）
```

### Store结构：

```typescript
// stores/main.ts
export const useMainStore = defineStore('main', {
  state: () => ({
    // 账户信息
    account: null,
    
    // 持仓列表
    positions: [],
    
    // 待审批订单
    pendingOrders: [],
    
    // Agent日志
    agentLogs: [],
    
    // 当前分析的股票
    currentStock: null
  }),
  
  actions: {
    async fetchPositions() {
      const res = await api.get('/portfolio/get-positions');
      this.positions = res.data.positions;
    },
    
    async fetchPendingOrders() {
      const res = await api.get('/order/get-pending');
      this.pendingOrders = res.data.orders;
    },
    
    async approveOrder(orderId: string) {
      await api.post('/order/approve', {
        order_id: orderId,
        action: 'approve'
      });
      await this.fetchPendingOrders();
    }
  }
});
```

---

## 🔄 改造示例

### 示例1：仪表盘改造

**原型代码**（静态）：
```html
<div id="dashboard" class="page">
  <h2>仪表盘</h2>
  <div class="grid grid-cols-3 gap-4">
    <div class="card">
      <h3>总资产</h3>
      <p class="text-2xl">¥1,250,000</p>
    </div>
  </div>
</div>
```

**改造后**（动态）：
```vue
<template>
  <div class="page">
    <h2>仪表盘</h2>
    
    <!-- 原有的资产卡片 -->
    <div class="grid grid-cols-3 gap-4">
      <div class="card">
        <h3>总资产</h3>
        <p class="text-2xl">¥{{ formatNumber(account.total_value) }}</p>
      </div>
    </div>
    
    <!-- 🆕 新增：待审批区域 -->
    <div class="mt-6">
      <h3 class="text-lg font-bold mb-4">⚠️ 待处理事项 ({{ pendingOrders.length }})</h3>
      <div v-for="order in pendingOrders" :key="order.order_id" 
           class="bg-red-50 border-l-4 border-red-500 p-4 mb-2">
        <div class="flex justify-between items-center">
          <div>
            <span class="text-red-600">🔴 紧急</span>
            <span class="ml-2">Agent提交{{ order.action }}申请：{{ order.symbol }}</span>
          </div>
          <div class="flex gap-2">
            <button @click="handleApprove(order.order_id)" class="btn-primary">
              批准
            </button>
            <button @click="handleReject(order.order_id)" class="btn-secondary">
              拒绝
            </button>
            <button @click="showDetail(order.order_id)" class="btn-secondary">
              查看详情
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useMainStore } from '@/stores/main';

const store = useMainStore();
const account = computed(() => store.account);
const pendingOrders = computed(() => store.pendingOrders);

const handleApprove = async (orderId: string) => {
  await store.approveOrder(orderId);
};

const handleReject = async (orderId: string) => {
  await store.rejectOrder(orderId);
};

const showDetail = (orderId: string) => {
  // 打开工作详情弹窗
};
</script>
```

### 示例2：股票详情改造为市场研究

**原型代码**（单一视角）：
```html
<div id="stock-detail" class="page">
  <h2>600519 贵州茅台</h2>
  <div class="card">
    <h3>技术指标</h3>
    <p>RSI: 28</p>
    <p>MACD: 金叉</p>
  </div>
</div>
```

**改造后**（双视角）：
```vue
<template>
  <div class="page">
    <h2>市场研究</h2>
    
    <!-- 🆕 新增：双标签切换 -->
    <div class="flex border-b mb-4">
      <button 
        @click="activeTab = 'agent'"
        :class="['px-4 py-2', activeTab === 'agent' ? 'border-b-2 border-blue-500' : '']">
        🤖 Agent视图
      </button>
      <button 
        @click="activeTab = 'user'"
        :class="['px-4 py-2', activeTab === 'user' ? 'border-b-2 border-blue-500' : '']">
        👔 我的工作台
      </button>
    </div>
    
    <!-- Agent视图 -->
    <div v-if="activeTab === 'agent'" class="card">
      <div class="bg-blue-50 p-2 mb-4 text-sm">
        ℹ️ 这是Agent在 {{ agentAnalysis.timestamp }} 的分析结果
      </div>
      <h3>技术指标</h3>
      <p>RSI: {{ agentAnalysis.rsi }}</p>
      <p>MACD: {{ agentAnalysis.macd }}</p>
      <div class="mt-4">
        <button @click="reproduce" class="btn-primary">
          🔄 我来复现这个分析
        </button>
      </div>
    </div>
    
    <!-- 我的工作台 -->
    <div v-else class="card">
      <h3>技术指标</h3>
      <button @click="analyze" class="btn-primary">
        🚀 开始分析
      </button>
      <div v-if="userAnalysis">
        <p>RSI: {{ userAnalysis.rsi }}</p>
        <p>MACD: {{ userAnalysis.macd }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

const activeTab = ref('agent');
const agentAnalysis = ref(null);
const userAnalysis = ref(null);

const analyze = async () => {
  // 调用分析API
};

const reproduce = async () => {
  // 复现Agent的分析
};
</script>
```

---

## ✅ 交付清单

### 第一周交付：
- [ ] Vue 3项目搭建完成
- [ ] 原型HTML转换为Vue组件（至少5个核心页面）
- [ ] 仪表盘改造完成（增加待审批）
- [ ] 持仓管理改造完成（增加建仓信息）

### 第二周交付：
- [ ] 市场研究页面改造完成（双标签）
- [ ] Agent工作日志页面完成
- [ ] 工作详情弹窗完成
- [ ] 所有页面对接API

### 第三周交付：
- [ ] Agent绩效评估页面完成
- [ ] 复现验证功能完成
- [ ] WebSocket实时推送完成
- [ ] 完整测试和优化

---

## 🚀 开始工作

### 第一步：查看原型
```bash
# 在浏览器中打开原型
open file:///Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html

# 仔细查看每个页面的布局和交互
# 记录需要改造的地方
```

### 第二步：阅读文档
1. 先看 `docs/frontend-design.md` 了解新增功能
2. 再看 `docs/backend-api-spec.md` 了解API接口
3. 最后看 `docs/v2-prototype-gap-analysis.md` 了解差异

### 第三步：开始改造
1. 搭建Vue 3项目
2. 提取原型的第一个页面（仪表盘）
3. 改造并对接API
4. 逐步完成其他页面

---

**记住**：不是从零开发，而是**改造现有原型**！保留优秀的UI设计，增加"领导监督Agent"的功能。
