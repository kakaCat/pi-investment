# 前端原型设计任务（继续完善HTML原型）

**负责人**: [待分配]  
**预计工期**: 1-2周  
**基础**: 现有原型 `quant-web-v2-prototype.html`

---

## 📋 任务概述

**继续完善现有的HTML原型，不是开发Vue项目！**

现有原型位置：
- `/Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html`

这是一个**单页HTML原型**（~1800行），包含17个功能页面，使用Tailwind CSS + 原生JavaScript。

你的任务是：
1. **在现有原型基础上继续画页面**
2. **增加"领导监督Agent"的功能页面**
3. **保持相同的技术栈**（HTML + Tailwind + 原生JS）
4. **保持相同的设计风格**

---

## 🎯 需要新增的页面

### 页面1：Agent工作日志

**位置**：在导航栏增加"Agent监控"菜单

**页面内容**：
```html
<div id="agent-logs" class="page hidden">
  <h2 class="text-2xl font-bold mb-6">🤖 Agent工作日志</h2>
  
  <!-- 日期筛选 -->
  <div class="mb-4 flex gap-4">
    <select class="border rounded px-3 py-2">
      <option>2026-05-22 (今天)</option>
      <option>2026-05-21</option>
      <option>2026-05-20</option>
    </select>
    <button class="btn-secondary">本周</button>
    <button class="btn-secondary">本月</button>
  </div>
  
  <!-- 操作日志列表 -->
  <div class="space-y-4">
    <!-- 日志卡片1 -->
    <div class="card">
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-gray-500">14:00</span>
            <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
              🔄 更新持仓止损位
            </span>
            <span class="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">
              ✅ 已完成
            </span>
          </div>
          <p class="text-gray-700 mb-2">
            操作：调整600519止损价 1,750→1,800
          </p>
          <p class="text-sm text-gray-500">
            原因：价格上涨15%，移动止损保护利润
          </p>
        </div>
        <button class="btn-secondary text-sm">查看详情</button>
      </div>
    </div>
    
    <!-- 日志卡片2 -->
    <div class="card">
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-gray-500">10:45</span>
            <span class="px-2 py-1 bg-purple-100 text-purple-800 rounded text-sm">
              📝 提交买入申请
            </span>
            <span class="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-sm">
              ⏳ 等待审批
            </span>
          </div>
          <p class="text-gray-700 mb-2">
            股票：600519 贵州茅台
          </p>
          <p class="text-sm text-gray-500">
            建议价：1,820-1,840 | 建议仓位：10% | 置信度：85%
          </p>
        </div>
        <div class="flex gap-2">
          <button class="btn-primary text-sm">批准</button>
          <button class="btn-secondary text-sm">拒绝</button>
          <button class="btn-secondary text-sm">查看分析</button>
        </div>
      </div>
    </div>
    
    <!-- 日志卡片3 -->
    <div class="card">
      <div class="flex items-start justify-between">
        <div class="flex-1">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-gray-500">09:30</span>
            <span class="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">
              🌅 市场扫描
            </span>
            <span class="px-2 py-1 bg-green-100 text-green-800 rounded text-sm">
              ✅ 已完成
            </span>
          </div>
          <p class="text-gray-700 mb-2">
            扫描范围：A股全市场 (5,234只)
          </p>
          <p class="text-sm text-gray-500">
            发现机会：23只股票符合筛选条件（PE<30, ROE>15%, RSI<40）
          </p>
        </div>
        <button class="btn-secondary text-sm">查看候选列表</button>
      </div>
    </div>
  </div>
</div>
```

---

### 页面2：工作详情弹窗（Modal）

**触发**：点击"查看分析"按钮

**弹窗内容**：
```html
<!-- 工作详情弹窗 -->
<div id="work-detail-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden flex items-center justify-center z-50">
  <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto m-4">
    <!-- 弹窗头部 -->
    <div class="sticky top-0 bg-white border-b px-6 py-4 flex justify-between items-center">
      <h3 class="text-xl font-bold">📄 工作详情 #1247</h3>
      <button onclick="closeWorkDetailModal()" class="text-gray-500 hover:text-gray-700">
        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
        </svg>
      </button>
    </div>
    
    <!-- 弹窗内容 -->
    <div class="p-6">
      <!-- 基本信息 -->
      <div class="mb-6">
        <p class="text-sm text-gray-500">时间：2026-05-22 10:45 | 员工：Agent-v2</p>
        <p class="text-sm text-gray-500">任务：分析600519并生成交易建议</p>
      </div>
      
      <!-- 结论 -->
      <div class="card bg-blue-50 mb-6">
        <h4 class="font-bold mb-3">🎯 结论</h4>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <p class="text-sm text-gray-600">建议操作</p>
            <p class="text-lg font-bold text-green-600">🟢 买入</p>
          </div>
          <div>
            <p class="text-sm text-gray-600">建议价格</p>
            <p class="text-lg font-bold">1,820 - 1,840</p>
          </div>
          <div>
            <p class="text-sm text-gray-600">建议仓位</p>
            <p class="text-lg font-bold">10%</p>
          </div>
          <div>
            <p class="text-sm text-gray-600">置信度</p>
            <p class="text-lg font-bold">★★★★☆ 85%</p>
          </div>
        </div>
      </div>
      
      <!-- 分析过程 -->
      <div class="mb-6">
        <h4 class="font-bold mb-4">📊 分析过程（Agent的工作步骤）</h4>
        
        <!-- 步骤1 -->
        <div class="border-l-4 border-green-500 pl-4 mb-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-green-600">✅</span>
            <span class="font-bold">步骤1：数据采集</span>
            <span class="text-sm text-gray-500">(10:45:01 - 10:45:15)</span>
          </div>
          <ul class="text-sm text-gray-600 ml-6 list-disc">
            <li>获取K线数据：最近90天</li>
            <li>获取财务数据：最近4个季度</li>
            <li>获取资金流向：最近5天</li>
          </ul>
          <button class="text-blue-600 text-sm mt-2">查看原始数据</button>
        </div>
        
        <!-- 步骤2 -->
        <div class="border-l-4 border-green-500 pl-4 mb-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-green-600">✅</span>
            <span class="font-bold">步骤2：技术面分析</span>
            <span class="text-sm text-gray-500">(10:45:16 - 10:45:28)</span>
          </div>
          <div class="bg-gray-50 p-3 rounded mb-2">
            <p class="font-bold mb-2">技术面评分：80/100</p>
            <ul class="text-sm text-gray-600 space-y-1">
              <li>• RSI(14): 28 → 超卖区域 (+15分)</li>
              <li>• MACD: 金叉 (DIF=12.5, DEA=8.3) (+15分)</li>
              <li>• 布林带: 接近下轨 (1,820) (+10分)</li>
              <li>• MA趋势: 短期多头排列 (+10分)</li>
            </ul>
          </div>
          <div class="flex gap-2">
            <button class="text-blue-600 text-sm">查看详细指标</button>
            <button class="text-blue-600 text-sm">我来复现这一步</button>
          </div>
        </div>
        
        <!-- 步骤3 -->
        <div class="border-l-4 border-green-500 pl-4 mb-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-green-600">✅</span>
            <span class="font-bold">步骤3：基本面分析</span>
            <span class="text-sm text-gray-500">(10:45:29 - 10:45:42)</span>
          </div>
          <div class="bg-gray-50 p-3 rounded mb-2">
            <p class="font-bold mb-2">基本面评分：70/100</p>
            <ul class="text-sm text-gray-600 space-y-1">
              <li>• PE(TTM): 28.5 (历史分位15%) (+15分)</li>
              <li>• ROE: 32.5% (优秀) (+15分)</li>
              <li>• 毛利率: 91.2% (极高) (+10分)</li>
              <li>• 负债率: 18.3% (健康) (+10分)</li>
            </ul>
          </div>
          <button class="text-blue-600 text-sm">我来复现这一步</button>
        </div>
        
        <!-- 更多步骤... -->
        <p class="text-sm text-gray-500 text-center">... 还有4个步骤 ...</p>
      </div>
      
      <!-- 复现工具 -->
      <div class="card bg-yellow-50 mb-6">
        <h4 class="font-bold mb-3">🔄 领导复现工具</h4>
        <p class="text-sm text-gray-600 mb-3">
          你可以使用相同的工具和数据，重新分析一遍：
        </p>
        <div class="flex gap-2">
          <button class="btn-primary">🔄 一键复现全部步骤</button>
          <button class="btn-secondary">📊 只复现技术分析</button>
          <button class="btn-secondary">💰 只复现基本面分析</button>
        </div>
      </div>
      
      <!-- 审批操作 -->
      <div class="flex gap-4">
        <button class="btn-primary flex-1">✅ 批准执行</button>
        <button class="btn-secondary flex-1">❌ 拒绝</button>
        <button class="btn-secondary flex-1">💬 要求补充分析</button>
      </div>
    </div>
  </div>
</div>

<script>
function showWorkDetailModal() {
  document.getElementById('work-detail-modal').classList.remove('hidden');
}

function closeWorkDetailModal() {
  document.getElementById('work-detail-modal').classList.add('hidden');
}
</script>
```

---

### 页面3：Agent绩效评估

**位置**：在"Agent监控"下增加子菜单

**页面内容**：
```html
<div id="agent-performance" class="page hidden">
  <h2 class="text-2xl font-bold mb-6">📊 Agent绩效评估</h2>
  
  <!-- 时间范围选择 -->
  <div class="mb-6">
    <select class="border rounded px-3 py-2">
      <option>最近30天</option>
      <option>最近7天</option>
      <option>最近90天</option>
    </select>
  </div>
  
  <!-- 决策准确率 -->
  <div class="card mb-6">
    <h3 class="font-bold mb-4">📈 决策准确率</h3>
    <div class="grid grid-cols-4 gap-4 mb-4">
      <div>
        <p class="text-sm text-gray-600">总决策数</p>
        <p class="text-2xl font-bold">156次</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">正确决策</p>
        <p class="text-2xl font-bold text-green-600">102次</p>
        <p class="text-sm text-gray-500">65.4%</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">错误决策</p>
        <p class="text-2xl font-bold text-red-600">38次</p>
        <p class="text-sm text-gray-500">24.4%</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">待验证</p>
        <p class="text-2xl font-bold text-yellow-600">16次</p>
        <p class="text-sm text-gray-500">10.2%</p>
      </div>
    </div>
    <!-- 准确率趋势图（SVG占位） -->
    <div class="bg-gray-100 h-48 rounded flex items-center justify-center">
      <p class="text-gray-500">准确率趋势图</p>
    </div>
  </div>
  
  <!-- 收益贡献 -->
  <div class="card mb-6">
    <h3 class="font-bold mb-4">💰 收益贡献</h3>
    <div class="grid grid-cols-5 gap-4">
      <div>
        <p class="text-sm text-gray-600">Agent执行的交易</p>
        <p class="text-xl font-bold">45笔</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">总收益</p>
        <p class="text-xl font-bold text-green-600">+¥125,600</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">平均单笔收益</p>
        <p class="text-xl font-bold">+¥2,791</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">胜率</p>
        <p class="text-xl font-bold">68.9%</p>
      </div>
      <div>
        <p class="text-sm text-gray-600">盈亏比</p>
        <p class="text-xl font-bold">2.3</p>
      </div>
    </div>
  </div>
  
  <!-- 常见错误 -->
  <div class="card">
    <h3 class="font-bold mb-4">⚠️ 常见错误</h3>
    <div class="space-y-3">
      <div class="border-l-4 border-red-500 pl-4">
        <p class="font-bold">1. 过度乐观 (15次)</p>
        <p class="text-sm text-gray-600">在技术面评分时倾向给高分</p>
        <p class="text-sm text-blue-600">建议：调整评分权重</p>
      </div>
      <div class="border-l-4 border-orange-500 pl-4">
        <p class="font-bold">2. 忽略地缘政治风险 (8次)</p>
        <p class="text-sm text-gray-600">未充分考虑宏观风险因素</p>
        <p class="text-sm text-blue-600">建议：增加地缘政治检测模块</p>
      </div>
      <div class="border-l-4 border-yellow-500 pl-4">
        <p class="font-bold">3. 止损设置过紧 (5次)</p>
        <p class="text-sm text-gray-600">导致过早止损，错失后续上涨</p>
        <p class="text-sm text-blue-600">建议：放宽止损幅度至10%</p>
      </div>
    </div>
  </div>
</div>
```

---

### 页面4：改造现有页面 - 仪表盘增加"待审批"

**在现有仪表盘中增加**：
```html
<!-- 在仪表盘的统计卡片后面增加 -->
<div class="mt-6">
  <h3 class="text-lg font-bold mb-4">⚠️ 待处理事项 (3项)</h3>
  
  <!-- 待审批卡片1 -->
  <div class="bg-red-50 border-l-4 border-red-500 p-4 mb-3 rounded">
    <div class="flex justify-between items-center">
      <div>
        <span class="text-red-600 font-bold">🔴 紧急</span>
        <span class="ml-2">Agent提交买入申请：600519 贵州茅台</span>
      </div>
      <div class="flex gap-2">
        <button class="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700">
          批准
        </button>
        <button class="px-3 py-1 bg-gray-600 text-white rounded hover:bg-gray-700">
          拒绝
        </button>
        <button class="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
          查看分析
        </button>
      </div>
    </div>
  </div>
  
  <!-- 待审批卡片2 -->
  <div class="bg-yellow-50 border-l-4 border-yellow-500 p-4 mb-3 rounded">
    <div class="flex justify-between items-center">
      <div>
        <span class="text-yellow-600 font-bold">🟡 提醒</span>
        <span class="ml-2">300750已达止损位</span>
      </div>
      <div class="flex gap-2">
        <button class="px-3 py-1 bg-green-600 text-white rounded hover:bg-green-700">
          批准卖出
        </button>
        <button class="px-3 py-1 bg-gray-600 text-white rounded hover:bg-gray-700">
          调整止损
        </button>
      </div>
    </div>
  </div>
  
  <!-- 信息卡片 -->
  <div class="bg-blue-50 border-l-4 border-blue-500 p-4 rounded">
    <div class="flex justify-between items-center">
      <div>
        <span class="text-blue-600 font-bold">🟢 信息</span>
        <span class="ml-2">周报已生成</span>
      </div>
      <button class="px-3 py-1 bg-blue-600 text-white rounded hover:bg-blue-700">
        查看周报
      </button>
    </div>
  </div>
</div>
```

---

### 页面5：改造现有页面 - 股票详情增加"双标签"

**在股票详情页面顶部增加**：
```html
<!-- 在股票详情页面的标题下方增加 -->
<div class="flex border-b mb-6">
  <button 
    onclick="switchTab('agent')" 
    id="tab-agent"
    class="px-6 py-3 border-b-2 border-blue-500 font-bold text-blue-600">
    🤖 Agent视图
  </button>
  <button 
    onclick="switchTab('user')" 
    id="tab-user"
    class="px-6 py-3 font-bold text-gray-600 hover:text-blue-600">
    👔 我的工作台
  </button>
</div>

<!-- Agent视图内容 -->
<div id="content-agent" class="tab-content">
  <div class="bg-blue-50 border-l-4 border-blue-500 p-3 mb-4">
    <p class="text-sm text-blue-800">
      ℹ️ 这是Agent在 2026-05-22 10:45 的分析结果
    </p>
  </div>
  
  <!-- 原有的分析内容 -->
  <div class="card">
    <h3 class="font-bold mb-3">技术指标</h3>
    <p>RSI(14): 28 (超卖)</p>
    <p>MACD: 金叉</p>
    <!-- ... 更多内容 ... -->
  </div>
  
  <div class="mt-4">
    <button class="btn-primary">🔄 我来复现这个分析</button>
  </div>
</div>

<!-- 我的工作台内容 -->
<div id="content-user" class="tab-content hidden">
  <div class="card mb-4">
    <h3 class="font-bold mb-3">分析工具</h3>
    <div class="space-y-2">
      <label class="flex items-center">
        <input type="checkbox" checked class="mr-2">
        <span>技术指标分析</span>
      </label>
      <label class="flex items-center">
        <input type="checkbox" checked class="mr-2">
        <span>基本面分析</span>
      </label>
      <label class="flex items-center">
        <input type="checkbox" checked class="mr-2">
        <span>资金流向分析</span>
      </label>
    </div>
    <button class="btn-primary mt-4">🚀 开始分析</button>
  </div>
  
  <!-- 分析结果区域 -->
  <div id="user-analysis-result" class="hidden">
    <!-- 分析完成后显示结果 -->
  </div>
</div>

<script>
function switchTab(tab) {
  // 切换标签样式
  document.getElementById('tab-agent').className = 
    tab === 'agent' 
    ? 'px-6 py-3 border-b-2 border-blue-500 font-bold text-blue-600'
    : 'px-6 py-3 font-bold text-gray-600 hover:text-blue-600';
  
  document.getElementById('tab-user').className = 
    tab === 'user' 
    ? 'px-6 py-3 border-b-2 border-blue-500 font-bold text-blue-600'
    : 'px-6 py-3 font-bold text-gray-600 hover:text-blue-600';
  
  // 切换内容显示
  document.getElementById('content-agent').classList.toggle('hidden', tab !== 'agent');
  document.getElementById('content-user').classList.toggle('hidden', tab !== 'user');
}
</script>
```

---

## 📖 必读文档

1. ✅ **现有原型** - `quant-web-v2-prototype.html`（必须先看）
2. ✅ **前端设计** - `docs/frontend-design.md`（参考新增页面的设计）
3. ✅ **整体架构** - `docs/v2-complete-design-summary.md`（理解设计理念）

---

## 🎨 设计要求

### 保持一致性
1. **技术栈**：HTML + Tailwind CSS + 原生JavaScript（与现有原型相同）
2. **颜色方案**：使用现有原型的颜色（蓝色主题）
3. **布局结构**：左侧导航 + 主内容区域
4. **组件风格**：卡片式布局、圆角按钮、阴影效果

### 新增元素标识
- 🤖 Agent相关内容用蓝色背景
- 👔 用户操作用灰色背景
- ⚠️ 待审批用红色/黄色边框
- ✅ 已完成用绿色标识

---

## ✅ 交付清单

### 第一周交付：
- [ ] Agent工作日志页面
- [ ] 工作详情弹窗
- [ ] 仪表盘增加"待审批"区域
- [ ] 股票详情增加"双标签"

### 第二周交付：
- [ ] Agent绩效评估页面
- [ ] 持仓管理页面增加"建仓信息"
- [ ] 订单管理页面增加"审批状态"
- [ ] 完整测试和优化

---

## 🚀 开始工作

### 第一步：查看现有原型
```bash
# 在浏览器中打开原型
open file:///Users/mac/Documents/ai/pi-investment/quant-web-v2-prototype.html

# 熟悉现有的17个页面
# 理解现有的代码结构和风格
```

### 第二步：阅读设计文档
- 查看 `docs/frontend-design.md` 了解新增页面的设计
- 查看 `docs/v2-complete-design-summary.md` 理解整体理念

### 第三步：开始画页面
1. 复制 `quant-web-v2-prototype.html` 为 `quant-web-v2-prototype-new.html`
2. 在新文件中增加新页面
3. 保持相同的技术栈和风格
4. 测试所有交互功能

---

**记住**：这是**继续画HTML原型**，不是开发Vue项目！保持与现有原型相同的技术栈和风格。
