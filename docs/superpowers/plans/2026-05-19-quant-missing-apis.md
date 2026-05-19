# 量化系统缺失 API 功能实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补全 3 个缺失的后端 API 端点，修复 2 个前端问题，使量化系统 9 个页面全部可用

**Architecture:** 在现有 Express 路由中添加 3 个新端点（stocks/data-status, training/history, backtest/results），使用 SQLite 直接查询和文件读取。前端修复 antd Table 过滤器状态和硬编码 URL。

**Tech Stack:** Express, TypeScript, SQLite, React, Ant Design

---

## 文件结构

### 后端文件（修改）
- `src/api/web/routes/stocks.ts` - 添加 `/data-status` 端点
- `src/api/web/routes/training.ts` - 添加 `/history` 端点
- `src/api/web/routes/backtest.ts` - 添加 `/results` 端点

### 前端文件（修改）
- `quant-web/src/components/StockList.tsx` - 修复 filteredValue 警告
- `quant-web/src/components/ModelTraining.tsx` - 修复硬编码端口

---

## Task 1: 实现 /api/stocks/data-status 端点

**Files:**
- Modify: `src/api/web/routes/stocks.ts`

- [ ] **Step 1: 添加必要的导入**

在 `src/api/web/routes/stocks.ts` 文件顶部添加 SQLite 导入：

```typescript
import Database from 'better-sqlite3';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
```

- [ ] **Step 2: 添加 /data-status 路由处理函数**

在 `src/api/web/routes/stocks.ts` 文件末尾，`export` 语句之前添加：

```typescript
// GET /api/stocks/data-status - 获取股票数据完整性统计
stocksRouter.get('/data-status', async (req, res, next) => {
  try {
    // 查找数据库文件
    const dbPaths = [
      path.join(__dirname, '../../../quant/quantsys/data/stocks.db'),
      path.join(__dirname, '../../../.pi-invest/stock-db/stocks.db'),
    ];
    
    let dbPath = '';
    for (const p of dbPaths) {
      if (require('fs').existsSync(p)) {
        dbPath = p;
        break;
      }
    }
    
    if (!dbPath) {
      res.json({
        total_stocks: 0,
        complete_stocks: 0,
        incomplete_stocks: 0,
        stocks: []
      });
      return;
    }

    const db = new Database(dbPath, { readonly: true });

    // 查询股票基本信息
    const stocks = db.prepare(`
      SELECT symbol, name, market
      FROM stocks
      ORDER BY symbol
    `).all() as Array<{ symbol: string; name: string; market: string }>;

    // 查询每只股票的 K线统计（最近90天）
    const klineStats = db.prepare(`
      SELECT 
        symbol,
        COUNT(*) as kline_days,
        MIN(date) as earliest_date,
        MAX(date) as latest_date
      FROM daily_klines
      WHERE date >= date('now', '-90 days')
      GROUP BY symbol
    `).all() as Array<{
      symbol: string;
      kline_days: number;
      earliest_date: string;
      latest_date: string;
    }>;

    // 查询每只股票的因子统计（最近30天）
    const factorStats = db.prepare(`
      SELECT 
        symbol,
        COUNT(DISTINCT date) as factor_days,
        COUNT(DISTINCT factor_name) as factor_count
      FROM factor_values
      WHERE date >= date('now', '-30 days')
      GROUP BY symbol
    `).all() as Array<{
      symbol: string;
      factor_days: number;
      factor_count: number;
    }>;

    db.close();

    // 构建 Map 以便快速查找
    const klineMap = new Map(klineStats.map(k => [k.symbol, k]));
    const factorMap = new Map(factorStats.map(f => [f.symbol, f]));

    // 合并数据并判断完整性
    const now = new Date();
    const threeDaysAgo = new Date(now.getTime() - 3 * 24 * 60 * 60 * 1000);

    const stocksData = stocks.map(stock => {
      const kline = klineMap.get(stock.symbol);
      const factor = factorMap.get(stock.symbol);

      const klineDays = kline?.kline_days || 0;
      const factorDays = factor?.factor_days || 0;
      const latestDate = kline?.latest_date || '';
      
      // 判断数据完整性
      const isKlineComplete = klineDays >= 60;
      const isFactorComplete = factorDays >= 20;
      const isDataFresh = latestDate && new Date(latestDate) >= threeDaysAgo;
      const dataComplete = isKlineComplete && isFactorComplete && isDataFresh;

      return {
        symbol: stock.symbol,
        name: stock.name,
        market: stock.market,
        kline_days: klineDays,
        earliest_date: kline?.earliest_date || '',
        latest_date: latestDate,
        factor_days: factorDays,
        factor_count: factor?.factor_count || 0,
        data_complete: dataComplete
      };
    });

    // 统计完整和不完整的股票数
    const completeStocks = stocksData.filter(s => s.data_complete).length;
    const incompleteStocks = stocksData.length - completeStocks;

    res.json({
      total_stocks: stocksData.length,
      complete_stocks: completeStocks,
      incomplete_stocks: incompleteStocks,
      stocks: stocksData
    });
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 3: 安装 better-sqlite3 依赖（如果未安装）**

运行：
```bash
cd /Users/mac/Documents/ai/pi-investment
npm install better-sqlite3
npm install --save-dev @types/better-sqlite3
```

预期：依赖安装成功

- [ ] **Step 4: 测试 API 端点**

启动后端服务（如果未运行）：
```bash
npm run dev
```

在另一个终端测试：
```bash
curl http://localhost:3001/api/stocks/data-status | jq
```

预期：返回 JSON 格式的股票数据统计

- [ ] **Step 5: 提交更改**

```bash
git add src/api/web/routes/stocks.ts package.json package-lock.json
git commit -m "feat(api): add /api/stocks/data-status endpoint for stock data completeness"
```

---

## Task 2: 实现 /api/training/history 端点

**Files:**
- Modify: `src/api/web/routes/training.ts`

- [ ] **Step 1: 添加 /history 路由处理函数**

在 `src/api/web/routes/training.ts` 文件中，`export` 语句之前添加：

```typescript
// GET /api/training/history - 获取训练历史记录
router.get('/history', async (req, res, next) => {
  try {
    const modelsDir = path.join(__dirname, '../../../../quant/quantsys/ml/models');

    if (!fs.existsSync(modelsDir)) {
      res.json({ history: [] });
      return;
    }

    const files = fs.readdirSync(modelsDir);
    const reportFiles = files
      .filter(f => f.startsWith('training_report_') && f.endsWith('.json') && f !== 'training_report_latest.json')
      .sort()
      .reverse();

    const history = reportFiles.slice(0, 50).map(filename => {
      try {
        const filePath = path.join(modelsDir, filename);
        const content = fs.readFileSync(filePath, 'utf-8');
        const report = JSON.parse(content);

        return {
          timestamp: report.timestamp,
          model_type: report.model_type,
          n_features: report.data?.n_features || 0,
          total_samples: report.data?.total_samples || 0,
          cv_accuracy: report.cv_results?.mean_scores?.accuracy || 0,
          cv_auc: report.cv_results?.mean_scores?.auc || 0,
          test_accuracy: report.test_metrics?.accuracy || 0,
          test_auc: report.test_metrics?.auc || 0,
          class_balance: report.data?.class_balance || 0
        };
      } catch (error) {
        console.warn(`Failed to parse training report ${filename}:`, error);
        return null;
      }
    }).filter(record => record !== null);

    res.json({ history });
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 2: 测试 API 端点**

运行：
```bash
curl http://localhost:3001/api/training/history | jq
```

预期：返回训练历史记录数组，如果没有训练记录则返回空数组

- [ ] **Step 3: 提交更改**

```bash
git add src/api/web/routes/training.ts
git commit -m "feat(api): add /api/training/history endpoint for training records"
```

---

## Task 3: 实现 /api/backtest/results 端点

**Files:**
- Modify: `src/api/web/routes/backtest.ts`

- [ ] **Step 1: 添加必要的导入**

在 `src/api/web/routes/backtest.ts` 文件顶部确保有以下导入：

```typescript
import { Router } from 'express';
import { BacktestEngine } from '../../../services/quant/backtest-engine.js';
import { QuantService } from '../../../services/quant/quant-service.js';
import { FactorLibrary } from '../../../services/quant/factor-library.js';
import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
```

- [ ] **Step 2: 添加 /results 路由处理函数**

在 `src/api/web/routes/backtest.ts` 文件中，`export` 语句之前添加：

```typescript
// GET /api/backtest/results - 获取回测结果汇总
router.get('/results', async (req, res, next) => {
  try {
    // 检查可能的回测结果目录
    const backtestDirs = [
      path.join(__dirname, '../../../.pi-invest/quant/backtest'),
      path.join(__dirname, '../../../quant/quantsys/backtest/results'),
      path.join(__dirname, '../../../data/backtest')
    ];

    let backtestDir = '';
    for (const dir of backtestDirs) {
      if (fs.existsSync(dir)) {
        backtestDir = dir;
        break;
      }
    }

    // 如果没有回测结果目录，返回空数组
    if (!backtestDir) {
      res.json({ summary: [] });
      return;
    }

    const files = fs.readdirSync(backtestDir)
      .filter(f => f.endsWith('.json'))
      .sort()
      .reverse()
      .slice(0, 100);

    const summary = files.map(filename => {
      try {
        const filePath = path.join(backtestDir, filename);
        const content = fs.readFileSync(filePath, 'utf-8');
        const data = JSON.parse(content);

        return {
          symbol: data.symbol || '',
          date: data.date || data.end_date || '',
          best_strategy: data.best_strategy || data.strategy_name || 'unknown',
          best_return: data.total_return || data.best_return || 0,
          sharpe_ratio: data.sharpe_ratio || 0,
          max_drawdown: data.max_drawdown || 0,
          win_rate: data.win_rate || 0
        };
      } catch (error) {
        console.warn(`Failed to parse backtest result ${filename}:`, error);
        return null;
      }
    }).filter(record => record !== null);

    res.json({ summary });
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 3: 测试 API 端点**

运行：
```bash
curl http://localhost:3001/api/backtest/results | jq
```

预期：返回回测结果数组，如果没有回测结果则返回空数组 `{ "summary": [] }`

- [ ] **Step 4: 提交更改**

```bash
git add src/api/web/routes/backtest.ts
git commit -m "feat(api): add /api/backtest/results endpoint for backtest summaries"
```

---

## Task 4: 修复 StockList.tsx 的 filteredValue 警告

**Files:**
- Modify: `quant-web/src/components/StockList.tsx`

- [ ] **Step 1: 添加过滤器状态管理**

在 `StockList.tsx` 组件中，找到现有的 `useState` 声明，在 `searchText` 状态后添加：

```typescript
const [searchText, setSearchText] = useState('');
const [filteredMarket, setFilteredMarket] = useState<string[] | null>(null);
const [filteredStatus, setFilteredStatus] = useState<boolean[] | null>(null);
```

- [ ] **Step 2: 更新 Table 的 onChange 处理**

在 `columns` 定义之后，Table 组件之前添加：

```typescript
const handleTableChange = (pagination: any, filters: any) => {
  setFilteredMarket(filters.market || null);
  setFilteredStatus(filters.data_complete || null);
};
```

- [ ] **Step 3: 更新 market 列定义**

找到 `market` 列的定义，更新为：

```typescript
{
  title: '市场',
  dataIndex: 'market',
  key: 'market',
  width: 100,
  filters: [
    { text: 'SZ', value: 'SZ' },
    { text: 'SH', value: 'SH' }
  ],
  filteredValue: filteredMarket,
  onFilter: (value, record) => record.market === value
},
```

- [ ] **Step 4: 更新 data_complete 列定义**

找到 `data_complete` 列的定义，更新为：

```typescript
{
  title: '数据状态',
  dataIndex: 'data_complete',
  key: 'data_complete',
  width: 120,
  fixed: 'right',
  filters: [
    { text: '完整', value: true },
    { text: '不完整', value: false }
  ],
  filteredValue: filteredStatus,
  onFilter: (value, record) => record.data_complete === value,
  render: (complete: boolean) => (
    complete ? (
      <Tag icon={<CheckCircleOutlined />} color="success">完整</Tag>
    ) : (
      <Tag icon={<CloseCircleOutlined />} color="error">不完整</Tag>
    )
  )
}
```

- [ ] **Step 5: 更新 Table 组件添加 onChange**

找到 `<Table>` 组件，添加 `onChange` 属性：

```typescript
<Table
  columns={columns}
  dataSource={data.stocks}
  rowKey={(record) => record.symbol}
  pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (total) => `共 ${total} 只股票` }}
  scroll={{ x: 1200 }}
  onChange={handleTableChange}
/>
```

- [ ] **Step 6: 测试前端修复**

启动前端开发服务器：
```bash
cd quant-web
npm run dev
```

在浏览器中打开股票列表页，检查：
1. 控制台没有 filteredValue 警告
2. 市场和数据状态过滤器正常工作

预期：无警告，过滤功能正常

- [ ] **Step 7: 提交更改**

```bash
git add quant-web/src/components/StockList.tsx
git commit -m "fix(frontend): resolve antd Table filteredValue warning in StockList"
```

---

## Task 5: 修复 ModelTraining.tsx 的硬编码端口

**Files:**
- Modify: `quant-web/src/components/ModelTraining.tsx`

- [ ] **Step 1: 替换 fetchReports 中的 URL**

找到 `fetchReports` 函数，将：

```typescript
const response = await fetch('http://localhost:3001/api/training/reports');
```

替换为：

```typescript
const response = await fetch('/api/training/reports');
```

- [ ] **Step 2: 替换 startTraining 中的 URL**

找到 `startTraining` 函数，将：

```typescript
const response = await fetch('http://localhost:3001/api/training/start', {
```

替换为：

```typescript
const response = await fetch('/api/training/start', {
```

- [ ] **Step 3: 替换 pollTaskStatus 中的 URL**

找到 `pollTaskStatus` 函数，将：

```typescript
const response = await fetch(`http://localhost:3001/api/training/status/${taskId}`);
```

替换为：

```typescript
const response = await fetch(`/api/training/status/${taskId}`);
```

- [ ] **Step 4: 替换 viewReportDetail 中的 URL**

找到 `viewReportDetail` 函数，将：

```typescript
const response = await fetch(`http://localhost:3001/api/training/report/${filename}`);
```

替换为：

```typescript
const response = await fetch(`/api/training/report/${filename}`);
```

- [ ] **Step 5: 测试前端修复**

在浏览器中打开模型训练页，检查：
1. API 调用正常工作
2. 可以查看训练报告列表
3. 网络请求使用相对路径

预期：所有功能正常，使用相对路径调用 API

- [ ] **Step 6: 提交更改**

```bash
git add quant-web/src/components/ModelTraining.tsx
git commit -m "fix(frontend): replace hardcoded port with relative URLs in ModelTraining"
```

---

## Task 6: 端到端测试

**Files:**
- None (testing only)

- [ ] **Step 1: 启动后端服务**

运行：
```bash
cd /Users/mac/Documents/ai/pi-investment
npm run dev
```

预期：后端服务在 http://localhost:3001 启动

- [ ] **Step 2: 启动前端服务**

在新终端运行：
```bash
cd /Users/mac/Documents/ai/pi-investment/quant-web
npm run dev
```

预期：前端服务在 http://localhost:3000 启动

- [ ] **Step 3: 测试股票列表页**

在浏览器访问 http://localhost:3000，点击"股票列表"菜单：
1. 检查页面加载无错误
2. 检查统计卡片显示数据
3. 检查表格显示股票列表
4. 测试搜索功能
5. 测试市场过滤器
6. 测试数据状态过滤器
7. 检查控制台无警告

预期：所有功能正常，无控制台错误或警告

- [ ] **Step 4: 测试训练历史页**

点击"训练历史"菜单：
1. 检查页面加载无错误
2. 检查最新模型统计卡片
3. 检查训练记录表格
4. 检查数据排序功能

预期：显示训练历史记录或"无数据"提示

- [ ] **Step 5: 测试回测仪表板页**

点击"回测仪表板"菜单：
1. 检查页面加载无错误
2. 检查统计卡片
3. 检查回测结果表格

预期：显示回测结果或"无数据"提示

- [ ] **Step 6: 测试模型训练页**

点击"模型训练"菜单：
1. 检查页面加载无错误
2. 检查历史报告列表
3. 检查网络请求使用相对路径（开发者工具 Network 标签）

预期：所有 API 调用使用相对路径，功能正常

- [ ] **Step 7: 验证所有 9 个页面**

依次访问所有菜单项：
1. 欢迎页 ✓
2. 因子重要性 ✓
3. 股票分析 ✓
4. 股票对比 ✓
5. 交易信号 ✓
6. 回测仪表板 ✓
7. 模型训练 ✓
8. 训练历史 ✓
9. 股票列表 ✓

预期：所有页面可以正常访问，无错误

- [ ] **Step 8: 最终提交**

如果所有测试通过，创建最终提交：

```bash
git add -A
git commit -m "test: verify all 9 quant web pages are functional

- Stock list page displays data completeness statistics
- Training history page shows training records
- Backtest dashboard shows results or empty state
- All frontend warnings resolved
- All API endpoints working correctly"
```

---

## 自查清单

**规范完整性检查：**
- [x] Task 1: 实现 /api/stocks/data-status - 对应设计文档第1部分
- [x] Task 2: 实现 /api/training/history - 对应设计文档第2部分
- [x] Task 3: 实现 /api/backtest/results - 对应设计文档第3部分
- [x] Task 4: 修复 StockList.tsx - 对应设计文档前端修复第1项
- [x] Task 5: 修复 ModelTraining.tsx - 对应设计文档前端修复第2项
- [x] Task 6: 端到端测试 - 对应设计文档测试计划

**占位符检查：**
- [x] 无 TBD、TODO 或"稍后实现"
- [x] 所有代码步骤都有完整代码
- [x] 所有测试步骤都有具体命令和预期输出

**类型一致性检查：**
- [x] API 响应格式与前端组件期望一致
- [x] 数据库字段名与代码中使用的一致
- [x] TypeScript 类型定义完整

---

## 预期成果

完成本计划后：
- ✅ 3 个缺失的 API 端点全部实现
- ✅ 2 个前端问题全部修复
- ✅ 9 个前端页面全部可用
- ✅ 前后端对接率从 67% 提升到 100%
- ✅ 无控制台警告或错误
- ✅ 代码质量与现有代码保持一致

**总提交数：** 6-7 个提交
**预计时间：** 1-2 小时
