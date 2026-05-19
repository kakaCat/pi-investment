# 量化系统缺失 API 功能设计文档

**日期：** 2026-05-19  
**状态：** 设计完成，待实现  
**作者：** Claude (Kiro)

## 概述

本文档描述量化系统前端已完成但后端缺失的 API 功能的设计方案。目标是补全 3 个缺失的 API 端点，并修复 2 个前端问题，使量化系统的 9 个前端页面全部可用。

## 背景

### 当前状态
- **前端完成度：** 100% (9/9 组件已实现)
- **后端完成度：** 约 85% (缺 3 个端点)
- **前后端对接：** 67% (6/9 页面可用)

### 缺失功能
1. `GET /api/stocks/data-status` - 股票数据完整性统计（StockList 页面需要）
2. `GET /api/training/history` - 训练历史记录（TrainingHistory 页面需要）
3. `GET /api/backtest/results` - 回测结果汇总（BacktestDashboard 页面需要）

### 前端问题
1. StockList.tsx - antd Table `filteredValue` 警告
2. ModelTraining.tsx - 硬编码端口 `http://localhost:3001`

## 技术架构

### 技术栈
- **后端：** Express + TypeScript + SQLite
- **数据库：** `quant/quantsys/data/stocks.db`
- **前端：** React + Ant Design

### 设计原则
1. 使用纯 SQL 查询，不引入额外依赖
2. 保持与现有 API 架构一致
3. 优先实用性，避免过度设计
4. 所有修改在现有文件中完成，不新增文件

## API 详细设计

### 1. GET /api/stocks/data-status

#### 功能描述
返回所有股票的数据完整性统计，用于股票列表管理页面展示每只股票的 K线和因子数据状态。

#### 请求
```
GET /api/stocks/data-status
```

无参数。

#### 响应格式
```typescript
{
  total_stocks: number;        // 总股票数
  complete_stocks: number;     // 数据完整的股票数
  incomplete_stocks: number;   // 数据不完整的股票数
  stocks: [
    {
      symbol: string;          // 股票代码 (如 "000001")
      name: string;            // 股票名称 (如 "平安银行")
      market: string;          // 市场 (SH/SZ)
      kline_days: number;      // 最近90天内的K线天数
      earliest_date: string;   // 最早K线日期 (YYYY-MM-DD)
      latest_date: string;     // 最新K线日期 (YYYY-MM-DD)
      factor_days: number;     // 最近30天内的因子天数
      factor_count: number;    // 因子种类数量
      data_complete: boolean;  // 数据是否完整
    }
  ]
}
```

#### 数据完整性标准
一只股票被认为"数据完整"需要同时满足：
1. **K线数据：** 最近90天内有 ≥60 天的数据
2. **因子数据：** 最近30天内有 ≥20 天的数据
3. **数据新鲜度：** 最新数据日期在3天内

**理由：**
- 90天K线足够计算大部分技术指标（MA60、MACD等）
- 30天因子数据足够做短期分析
- 考虑周末和节假日，60/90 和 20/30 的比例合理
- 3天新鲜度可以排除长期停牌的股票

#### 实现策略

**数据库查询：**
```sql
-- 步骤1: 查询每只股票的 K线统计
SELECT 
  symbol, 
  COUNT(*) as kline_days,
  MIN(date) as earliest_date,
  MAX(date) as latest_date
FROM daily_klines
WHERE date >= date('now', '-90 days')
GROUP BY symbol

-- 步骤2: 查询每只股票的因子统计
SELECT 
  symbol,
  COUNT(DISTINCT date) as factor_days,
  COUNT(DISTINCT factor_name) as factor_count
FROM factor_values
WHERE date >= date('now', '-30 days')
GROUP BY symbol

-- 步骤3: JOIN stocks 表获取基本信息
SELECT 
  s.symbol,
  s.name,
  s.market
FROM stocks s
```

**处理逻辑：**
1. 执行三个查询获取数据
2. 在 TypeScript 中合并结果
3. 计算每只股票的 `data_complete` 状态
4. 统计 `complete_stocks` 和 `incomplete_stocks`
5. 返回完整响应

**文件位置：** `src/api/web/routes/stocks.ts`

#### 错误处理
- 数据库连接失败：返回 500 错误
- 数据库为空：返回空数组，统计数为 0
- SQL 查询异常：捕获并记录日志，返回友好错误信息

---

### 2. GET /api/training/history

#### 功能描述
返回模型训练历史记录列表，用于训练历史页面展示所有训练任务的指标。

#### 策略
复用现有的 `GET /api/training/reports` 接口，在路由层做字段映射和格式转换。

**原因：**
- `/api/training/reports` 已经实现了读取训练报告文件的逻辑
- 两个接口的数据源相同（`training_report_*.json` 文件）
- 只需要调整响应格式以匹配前端期望

#### 请求
```
GET /api/training/history
```

无参数。

#### 响应格式
```typescript
{
  history: [
    {
      timestamp: string;       // ISO 格式时间 (如 "2026-05-19T11:24:53.771906")
      model_type: string;      // 模型类型 (xgboost/lightgbm/random_forest)
      n_features: number;      // 特征数
      total_samples: number;   // 总样本数
      cv_accuracy: number;     // 交叉验证准确率 (0-1)
      cv_auc: number;          // CV AUC (0-1)
      test_accuracy: number;   // 测试准确率 (0-1)
      test_auc: number;        // 测试 AUC (0-1)
      class_balance: number;   // 正样本比例 (0-1)
    }
  ]
}
```

#### 实现策略

**字段映射：**
```typescript
// 从 training_report_*.json 提取
{
  timestamp: report.timestamp,
  model_type: report.model_type,
  n_features: report.data.n_features,
  total_samples: report.data.total_samples,
  cv_accuracy: report.cv_results.mean_scores.accuracy,
  cv_auc: report.cv_results.mean_scores.auc,
  test_accuracy: report.test_metrics.accuracy,
  test_auc: report.test_metrics.auc,
  class_balance: report.data.class_balance
}
```

**处理逻辑：**
1. 读取 `quant/quantsys/ml/models/` 目录下的所有 `training_report_*.json` 文件
2. 解析每个文件，提取所需字段
3. 按时间倒序排序
4. 返回 `{ history: [...] }` 格式

**文件位置：** `src/api/web/routes/training.ts`

#### 错误处理
- 目录不存在：返回空数组 `{ history: [] }`
- 文件解析失败：跳过该文件，记录警告日志
- 字段缺失：使用默认值或跳过该记录

---

### 3. GET /api/backtest/results

#### 功能描述
返回回测结果汇总列表，用于回测仪表板展示所有股票的回测表现。

#### 请求
```
GET /api/backtest/results
```

无参数。

#### 响应格式
```typescript
{
  summary: [
    {
      symbol: string;          // 股票代码
      date: string;            // 回测日期 (YYYY-MM-DD)
      best_strategy: string;   // 最佳策略名称
      best_return: number;     // 总收益率 (如 0.15 表示 15%)
      sharpe_ratio: number;    // 夏普比率
      max_drawdown: number;    // 最大回撤 (如 0.08 表示 8%)
      win_rate: number;        // 胜率 (0-1)
    }
  ]
}
```

#### 实现策略

**数据来源检查：**
1. 检查是否存在回测结果存储目录（可能的位置）：
   - `.pi-invest/quant/backtest/`
   - `quant/quantsys/backtest/results/`
   - 其他配置的目录

2. 如果目录存在，读取回测结果文件（JSON 格式）
3. 如果目录不存在或为空，返回空数组

**处理逻辑：**
```typescript
// 伪代码
const backtestDir = '.pi-invest/quant/backtest/';
if (!fs.existsSync(backtestDir)) {
  return { summary: [] };
}

const files = fs.readdirSync(backtestDir)
  .filter(f => f.endsWith('.json'));

const summary = files.map(file => {
  const data = JSON.parse(fs.readFileSync(file));
  return {
    symbol: data.symbol,
    date: data.date,
    best_strategy: data.best_strategy,
    best_return: data.total_return,
    sharpe_ratio: data.sharpe_ratio,
    max_drawdown: data.max_drawdown,
    win_rate: data.win_rate
  };
});

return { summary };
```

**文件位置：** `src/api/web/routes/backtest.ts`

#### 错误处理
- 目录不存在：返回空数组 `{ summary: [] }`
- 文件解析失败：跳过该文件，记录警告日志
- 字段缺失：使用默认值 0 或跳过该记录

**注意：** 如果当前系统还没有生成回测结果文件，这个接口会返回空数组，前端会显示"无数据"，这是预期行为。

---

## 前端修复

### 1. 修复 StockList.tsx 的 antd Table 警告

#### 问题描述
控制台警告：
```
Warning: [antd: Table] Columns should all contain `filteredValue` or not contain `filteredValue`.
```

**原因：** 只有 `symbol` 列有 `filteredValue` 属性，但 `market` 和 `data_complete` 列有 `filters` 却没有 `filteredValue`。

#### 解决方案

**添加状态管理：**
```typescript
const [searchText, setSearchText] = useState('');
const [filteredMarket, setFilteredMarket] = useState<string[] | null>(null);
const [filteredStatus, setFilteredStatus] = useState<boolean[] | null>(null);
```

**更新列定义：**
```typescript
{
  title: '市场',
  dataIndex: 'market',
  key: 'market',
  filters: [
    { text: 'SZ', value: 'SZ' },
    { text: 'SH', value: 'SH' }
  ],
  filteredValue: filteredMarket,  // 添加这行
  onFilter: (value, record) => record.market === value,
  onChange: (pagination, filters) => {
    setFilteredMarket(filters.market as string[] | null);
  }
},
{
  title: '数据状态',
  dataIndex: 'data_complete',
  key: 'data_complete',
  filters: [
    { text: '完整', value: true },
    { text: '不完整', value: false }
  ],
  filteredValue: filteredStatus,  // 添加这行
  onFilter: (value, record) => record.data_complete === value,
  onChange: (pagination, filters) => {
    setFilteredStatus(filters.data_complete as boolean[] | null);
  }
}
```

**文件位置：** `quant-web/src/components/StockList.tsx`

---

### 2. 修复 ModelTraining.tsx 的硬编码端口

#### 问题描述
组件中使用硬编码的 `http://localhost:3001/api/training/*`，与其他组件使用相对路径 `/api/*` 不一致。

#### 解决方案

**替换所有硬编码 URL：**
```typescript
// 修改前
const response = await fetch('http://localhost:3001/api/training/start', {...});
const response = await fetch('http://localhost:3001/api/training/status/${taskId}');
const response = await fetch('http://localhost:3001/api/training/reports');
const response = await fetch('http://localhost:3001/api/training/report/${filename}');

// 修改后
const response = await fetch('/api/training/start', {...});
const response = await fetch(`/api/training/status/${taskId}`);
const response = await fetch('/api/training/reports');
const response = await fetch(`/api/training/report/${filename}`);
```

**文件位置：** `quant-web/src/components/ModelTraining.tsx`

**影响范围：** 4 处 fetch 调用

---

## 文件修改清单

### 后端文件
1. **src/api/web/routes/stocks.ts**
   - 添加 `GET /data-status` 路由
   - 实现 SQLite 查询逻辑
   - 计算数据完整性

2. **src/api/web/routes/training.ts**
   - 添加 `GET /history` 路由
   - 复用现有文件读取逻辑
   - 字段映射和格式转换

3. **src/api/web/routes/backtest.ts**
   - 添加 `GET /results` 路由
   - 读取回测结果文件
   - 处理空数据情况

### 前端文件
4. **quant-web/src/components/StockList.tsx**
   - 添加过滤器状态管理
   - 更新列定义的 `filteredValue`

5. **quant-web/src/components/ModelTraining.tsx**
   - 替换硬编码 URL 为相对路径

**总计：** 5 个文件需要修改，0 个新文件

---

## 错误处理策略

### 后端错误处理
所有 API 使用统一的错误处理中间件 `errorHandler`：

```typescript
try {
  // API 逻辑
} catch (error) {
  next(error);  // 传递给 errorHandler
}
```

**错误类型：**
1. **数据库错误：** 捕获 SQLite 异常，返回 500 错误
2. **文件系统错误：** 捕获 fs 异常，返回 500 错误
3. **数据不存在：** 返回空数组，HTTP 200 状态码
4. **参数错误：** 返回 400 错误（本设计中无参数，不适用）

### 前端错误处理
所有组件已有完善的错误处理：

```typescript
const [loading, setLoading] = useState(true);
const [error, setError] = useState<string | null>(null);

// 加载状态
if (loading) return <Spin />;

// 错误状态
if (error) return <Alert type="error" message={error} />;

// 空数据状态
if (data.length === 0) return <Empty description="无数据" />;
```

---

## 测试计划

### 手动测试
1. **启动后端服务：** `npm run dev` 或 `node src/api/web/server.js`
2. **启动前端服务：** `cd quant-web && npm run dev`
3. **测试每个页面：**
   - 股票列表页：检查数据加载、统计数字、表格过滤
   - 训练历史页：检查历史记录显示、指标展示
   - 回测仪表板：检查空数据提示或结果展示
   - 模型训练页：检查 API 调用是否正常

### API 测试
使用 curl 或 Postman 测试：

```bash
# 测试股票数据状态
curl http://localhost:3001/api/stocks/data-status

# 测试训练历史
curl http://localhost:3001/api/training/history

# 测试回测结果
curl http://localhost:3001/api/backtest/results
```

### 验收标准
- [ ] 所有 API 返回正确格式的数据
- [ ] 前端 9 个页面全部可以正常访问
- [ ] 无控制台错误或警告
- [ ] 空数据情况显示友好提示
- [ ] 数据库查询性能可接受（<1秒）

---

## 性能考虑

### 数据库查询优化
1. **索引：** 确保 `daily_klines(symbol, date)` 和 `factor_values(symbol, date)` 有索引
2. **查询范围：** 限制在最近 90 天，避免全表扫描
3. **分页：** 如果股票数量 >5000，考虑添加分页参数

### 缓存策略
当前设计不使用缓存，理由：
- 股票列表页不是高频访问页面
- 数据需要实时性（显示最新数据状态）
- SQLite 查询性能足够（预计 <500ms）

如果未来性能成为问题，可以考虑：
- Redis 缓存，TTL 5分钟
- 定时任务预计算，存储到文件

---

## 未来扩展

### 可能的增强功能
1. **股票数据状态页：**
   - 添加"刷新数据"按钮，触发数据采集
   - 显示数据采集进度
   - 支持按市场、行业筛选

2. **训练历史页：**
   - 添加模型对比功能
   - 显示训练曲线图
   - 支持导出训练报告

3. **回测仪表板：**
   - 添加回测参数配置
   - 支持自定义回测策略
   - 显示详细的回测曲线

### 技术债务
无。本设计遵循现有架构，不引入技术债务。

---

## 总结

本设计方案通过修改 5 个现有文件，补全 3 个缺失的 API 端点，修复 2 个前端问题，使量化系统的前后端完全对接。

**关键决策：**
1. 使用纯 SQL 查询，保持架构简单
2. 复用现有接口，减少重复代码
3. 优先实用性，避免过度设计
4. 完善错误处理，提升用户体验

**预期成果：**
- 前后端对接率从 67% 提升到 100%
- 9 个前端页面全部可用
- 无控制台警告或错误
- 代码质量与现有代码保持一致

---

**文档版本：** 1.0  
**最后更新：** 2026-05-19
