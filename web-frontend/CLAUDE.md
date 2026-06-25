# web-frontend - PI Investment 观察窗口

## 系统定位

**web-frontend = PI Investment 系统的观察窗口**

展示 agent-ts 大脑的风采和表现。

## 角色：窗口 👁️

### 职责
- 展示 agent 的决策过程
- 展示 agent 的表现（收益、胜率）
- 展示 agent 的思考（博弈分析、学习进度）
- 让人类观察者了解 agent 在做什么

### 特点
- **被动性**: 不参与决策，只展示
- **观察性**: 给人类提供观察窗口
- **展示性**: 展示 agent 的"风采"

### 不是什么
- ❌ 不是控制台
- ❌ 不是操作界面
- ❌ 不是给 agent 用的

## 系统架构

```
Human (观察者) ← 通过这里观察
    ↓
web-frontend (窗口) ← 你在这里
    ↓ 从这里获取数据展示
quantsys-v2 API
    ↓ 反映的是
agent-ts (大脑) 的状态和决策
```

## 主要页面

### 已有页面 (20+个)
- Dashboard - 系统总览
- StockList - 股票列表
- PoolList - 池子管理
- Portfolio - 持仓管理
- BacktestCenter - 回测中心
- ... 等

### 新增：博弈智能页面 (6个)

**目的**: 展示 agent 的博弈分析和学习能力

```
src/views/GameIntelligence/
├── Dashboard.vue              # agent 的博弈总览
├── OpponentBehavior.vue       # agent 如何看待对手
├── AlertCenter.vue            # agent 发现的风险和机会
├── LearningLoop.vue           # agent 如何学习进化
├── AutomationMonitor.vue      # agent 的自动化运行
└── AutomationConfig.vue       # agent 的规则配置
```

展示内容：
- agent 分析的对手行为（散户/机构/游资）
- agent 识别的博弈机会和风险
- agent 的知识库和学习进度
- agent 的自动化任务执行情况

## 数据流

```
agent-ts 做决策
    ↓
quantsys-v2 记录
    ↓
quantsys-v2 API 返回
    ↓
web-frontend 展示 ← 让人类看到
```

## 技术栈

- Vue 3 + TypeScript
- Element Plus (UI 组件)
- ECharts (图表可视化)
- Vite (开发服务器)

## 开发原则

1. **被动展示**: 只展示数据，不影响 agent 决策
2. **实时更新**: 及时反映 agent 的最新状态
3. **清晰直观**: 让人类观察者容易理解
4. **完整记录**: 展示 agent 的完整决策过程

## 与其他组件的关系

### 与 agent-ts
- web 不控制 agent
- web 只展示 agent 的决策和表现
- agent 不知道 web 的存在

### 与 quantsys-v2
- 从 quantsys-v2 API 获取数据
- 展示 quantsys-v2 记录的 agent 状态
- 不直接调用 agent-ts

## 目标

让人类观察者能够：
- 理解 agent 在做什么
- 评估 agent 的表现
- 监督 agent 的运行
- 欣赏 agent 的"风采"

**记住**: web-frontend 是窗口，让人类看到 agent 的表现，而不是控制 agent。
