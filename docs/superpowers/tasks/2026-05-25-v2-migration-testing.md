# Agent v2 迁移测试任务清单

**创建日期：** 2026-05-25  
**状态：** 待执行  
**优先级：** P0（阻塞发布）

---

## 背景

Agent v2 迁移的代码实现已完成（13个提交），但**未进行实际运行测试**。需要验证所有迁移的工具在真实环境中是否正常工作。

---

## 前置条件

### 1. 修复 quantsys-v2 Python 环境

**问题：** 启动 quantsys-v2 服务时报错 `No module named 'quantsys'`

**可能原因：**
- Python 路径配置问题
- 缺少 `__init__.py` 文件
- 虚拟环境未激活
- 依赖未安装

**修复步骤：**
```bash
cd quantsys-v2

# 检查 Python 环境
python3 -c "import sys; print(sys.path)"

# 检查是否有 quantsys 模块
find . -name "quantsys" -type d

# 安装依赖
pip install -r requirements.txt

# 尝试启动服务
python -m api.server
```

### 2. 验证 quantsys-v2 服务启动

**验证命令：**
```bash
# 启动服务
cd quantsys-v2 && python -m api.server &

# 等待启动
sleep 3

# 检查健康状态
curl http://127.0.0.1:5001/api/health
```

**预期输出：**
```json
{
  "status": "ok",
  "db_connected": true,
  "db_info": {...}
}
```

---

## 测试任务

### Task T1: 测试财务数据获取

**工具：** `data_fetch_financial`  
**v2 端点：** `GET /api/stock/{symbol}/financials`  
**QuantV2Client 方法：** `getFinancials()`

**测试用例：**

1. **正常情况 - 利润表**
   ```bash
   curl "http://127.0.0.1:5001/api/stock/600519/financials?type=income&periods=4"
   ```
   - 预期：返回贵州茅台最近4期利润表
   - 验证：包含营业收入、净利润等字段

2. **正常情况 - 资产负债表**
   ```bash
   curl "http://127.0.0.1:5001/api/stock/600519/financials?type=balance&periods=4"
   ```
   - 预期：返回资产负债表数据

3. **正常情况 - 现金流量表**
   ```bash
   curl "http://127.0.0.1:5001/api/stock/600519/financials?type=cash_flow&periods=4"
   ```
   - 预期：返回现金流量表数据

4. **错误情况 - 无效股票代码**
   ```bash
   curl "http://127.0.0.1:5001/api/stock/999999/financials?type=income&periods=4"
   ```
   - 预期：返回错误信息

**TypeScript 工具测试：**
```typescript
// 在 TypeScript 项目中运行
import { getFinancials } from './src/infrastructure/quant/quant-v2-client.js';
import { formatFinancialData } from './src/infrastructure/quant/formatters.js';

const result = await getFinancials('600519', 'income', 4);
console.log(formatFinancialData(result));
```

**验证点：**
- [ ] API 调用成功（无网络错误）
- [ ] 返回数据结构正确
- [ ] 格式化输出可读（亿元单位、百分比）
- [ ] 错误处理正确（无效代码返回友好错误）

---

### Task T2: 测试因子计算

**工具：** `factor_calculate`  
**v2 端点：** `POST /api/compute/factors`  
**QuantV2Client 方法：** `computeFactors()`

**测试用例：**

1. **正常情况 - 单股票多因子**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/compute/factors \
     -H "Content-Type: application/json" \
     -d '{
       "symbols": ["600519"],
       "factors": ["rsi", "macd", "roe"],
       "date": "2024-01-15"
     }'
   ```
   - 预期：返回 RSI、MACD、ROE 计算结果

2. **正常情况 - 多股票单因子**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/compute/factors \
     -H "Content-Type: application/json" \
     -d '{
       "symbols": ["600519", "000858"],
       "factors": ["rsi"],
       "date": "2024-01-15"
     }'
   ```
   - 预期：返回两只股票的 RSI

3. **错误情况 - 空股票列表**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/compute/factors \
     -H "Content-Type: application/json" \
     -d '{"symbols": [], "factors": ["rsi"]}'
   ```
   - 预期：返回验证错误

**TypeScript 工具测试：**
```typescript
import { computeFactors } from './src/infrastructure/quant/quant-v2-client.js';
import { formatFactorResult } from './src/infrastructure/quant/formatters.js';

const result = await computeFactors({
  symbols: ['600519'],
  factors: ['rsi', 'macd', 'roe'],
  date: '2024-01-15'
});
console.log(formatFactorResult(result));
```

**验证点：**
- [ ] API 调用成功
- [ ] 返回所有请求的因子
- [ ] 因子值不为 null（除非数据缺失）
- [ ] 格式化输出分类清晰（技术因子 vs 基本面因子）
- [ ] 错误处理正确

---

### Task T3: 测试因子分析

**工具：** `factor_analyze`  
**v2 端点：** `POST /api/portfolio/factor-analyze`  
**QuantV2Client 方法：** `analyzeFactors()`

**测试用例：**

1. **正常情况 - 单因子分析**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/portfolio/factor-analyze \
     -H "Content-Type: application/json" \
     -d '{
       "factors": ["rsi"],
       "start_date": "2024-01-01",
       "end_date": "2024-01-31"
     }'
   ```
   - 预期：返回 RSI 的 IC、覆盖率、稳定性等指标

2. **正常情况 - 多因子分析**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/portfolio/factor-analyze \
     -H "Content-Type: application/json" \
     -d '{
       "factors": ["rsi", "macd", "roe"],
       "start_date": "2024-01-01",
       "end_date": "2024-01-31",
       "pool": ["600519", "000858"]
     }'
   ```
   - 预期：返回三个因子的分析结果

3. **错误情况 - 缺少日期**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/portfolio/factor-analyze \
     -H "Content-Type: application/json" \
     -d '{"factors": ["rsi"]}'
   ```
   - 预期：返回验证错误

**TypeScript 工具测试：**
```typescript
import { analyzeFactors } from './src/infrastructure/quant/quant-v2-client.js';
import { formatFactorAnalysis } from './src/infrastructure/quant/formatters.js';

const result = await analyzeFactors({
  factors: ['rsi', 'macd'],
  start_date: '2024-01-01',
  end_date: '2024-01-31'
});
console.log(formatFactorAnalysis(result));
```

**验证点：**
- [ ] API 调用成功
- [ ] 返回 IC、覆盖率、稳定性等指标
- [ ] 格式化输出包含衰减曲线（如果有）
- [ ] 错误处理正确

**⚠️ 注意：** 此端点可能不存在，需要先验证或实现。

---

### Task T4: 测试机会扫描

**工具：** `invest_opportunity_scan`  
**v2 端点：** `POST /api/signals/scan`  
**QuantV2Client 方法：** `scanOpportunities()`

**测试用例：**

1. **正常情况 - 默认扫描**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/signals/scan \
     -H "Content-Type: application/json" \
     -d '{}'
   ```
   - 预期：返回所有股票的机会列表

2. **正常情况 - 指定股票池**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/signals/scan \
     -H "Content-Type: application/json" \
     -d '{
       "pool": ["600519", "000858"],
       "min_score": 60
     }'
   ```
   - 预期：返回评分 >= 60 的机会

3. **正常情况 - 高分过滤**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/signals/scan \
     -H "Content-Type: application/json" \
     -d '{"min_score": 80}'
   ```
   - 预期：只返回高分机会

**TypeScript 工具测试：**
```typescript
import { scanOpportunities } from './src/infrastructure/quant/quant-v2-client.js';
import { formatOpportunities } from './src/infrastructure/quant/formatters.js';

const result = await scanOpportunities({
  pool: ['600519', '000858'],
  min_score: 60
});
console.log(formatOpportunities(result));
```

**验证点：**
- [ ] API 调用成功
- [ ] 返回机会列表
- [ ] 每个机会包含评分、技术面、基本面、资金面
- [ ] 格式化输出包含星级评分（⭐）
- [ ] 评分权重正确（技术50% + 基本面30% + 资金20%）

**⚠️ 注意：** 此端点可能不存在，需要先验证或实现。

---

### Task T5: 测试算法交易执行

**工具：** `trade_algo_execute`  
**v2 端点：** `POST /api/orders/algo-execute`  
**QuantV2Client 方法：** `algoExecute()`

**测试用例：**

1. **正常情况 - TWAP 买入**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/orders/algo-execute \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "600519",
       "side": "buy",
       "quantity": 1000,
       "algo": "TWAP",
       "duration_minutes": 30,
       "start_time": "09:30:00"
     }'
   ```
   - 预期：返回订单ID和子订单列表

2. **正常情况 - VWAP 卖出**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/orders/algo-execute \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "600519",
       "side": "sell",
       "quantity": 2000,
       "algo": "VWAP",
       "duration_minutes": 60,
       "start_time": "10:00:00"
     }'
   ```
   - 预期：返回 VWAP 子订单分布

3. **错误情况 - 无效数量**
   ```bash
   curl -X POST http://127.0.0.1:5001/api/orders/algo-execute \
     -H "Content-Type: application/json" \
     -d '{
       "symbol": "600519",
       "side": "buy",
       "quantity": 50,
       "algo": "TWAP",
       "duration_minutes": 30,
       "start_time": "09:30:00"
     }'
   ```
   - 预期：返回验证错误（数量必须是100的倍数）

**TypeScript 工具测试：**
```typescript
import { algoExecute } from './src/infrastructure/quant/quant-v2-client.js';
import { formatAlgoOrder } from './src/infrastructure/quant/formatters.js';

const result = await algoExecute({
  symbol: '600519',
  side: 'buy',
  quantity: 1000,
  algo: 'TWAP',
  duration_minutes: 30,
  start_time: '09:30:00'
});
console.log(formatAlgoOrder(result));
```

**验证点：**
- [ ] API 调用成功
- [ ] 返回订单ID和子订单列表
- [ ] TWAP 子订单均匀分布
- [ ] VWAP 子订单按成交量分布
- [ ] 格式化输出包含执行统计
- [ ] 错误处理正确（无效数量、无效算法类型）

---

## 集成测试

### Task T6: 端到端工作流测试

**场景：** 完整的投资决策流程

```typescript
// 1. 获取财务数据
const financials = await getFinancials('600519', 'all', 4);
console.log('财务数据:', formatFinancialData(financials));

// 2. 计算因子
const factors = await computeFactors({
  symbols: ['600519'],
  factors: ['rsi', 'macd', 'roe', 'gross_margin'],
  date: '2024-01-15'
});
console.log('因子计算:', formatFactorResult(factors));

// 3. 分析因子有效性
const analysis = await analyzeFactors({
  factors: ['rsi', 'macd'],
  start_date: '2024-01-01',
  end_date: '2024-01-31'
});
console.log('因子分析:', formatFactorAnalysis(analysis));

// 4. 扫描投资机会
const opportunities = await scanOpportunities({
  pool: ['600519', '000858'],
  min_score: 70
});
console.log('投资机会:', formatOpportunities(opportunities));

// 5. 执行算法交易
const order = await algoExecute({
  symbol: '600519',
  side: 'buy',
  quantity: 1000,
  algo: 'TWAP',
  duration_minutes: 30,
  start_time: '09:30:00'
});
console.log('算法订单:', formatAlgoOrder(order));
```

**验证点：**
- [ ] 所有步骤顺序执行成功
- [ ] 数据在步骤间正确传递
- [ ] 格式化输出一致且可读
- [ ] 错误处理在任何步骤失败时正确工作

---

## 性能测试

### Task T7: 负载和响应时间测试

**测试场景：**

1. **单请求响应时间**
   - 每个端点的平均响应时间 < 2秒
   - 95分位响应时间 < 5秒

2. **并发请求**
   - 10个并发请求不应导致超时
   - 错误率 < 1%

3. **大数据量**
   - 100只股票的因子计算 < 10秒
   - 全市场机会扫描 < 30秒

---

## 错误处理测试

### Task T8: 异常场景测试

**测试场景：**

1. **网络错误**
   - 停止 quantsys-v2 服务
   - 调用任何工具
   - 预期：返回友好的连接错误

2. **超时**
   - 设置短超时（1秒）
   - 调用慢端点
   - 预期：返回超时错误

3. **无效参数**
   - 空字符串、负数、无效日期格式
   - 预期：返回验证错误

4. **后端错误**
   - 模拟 500 错误
   - 预期：返回服务器错误信息

---

## 测试执行计划

### 阶段 1: 环境准备（预计 30 分钟）
- [ ] 修复 quantsys-v2 Python 环境
- [ ] 启动服务并验证健康状态
- [ ] 准备测试数据和脚本

### 阶段 2: 单元测试（预计 1 小时）
- [ ] Task T1: 财务数据
- [ ] Task T2: 因子计算
- [ ] Task T3: 因子分析
- [ ] Task T4: 机会扫描
- [ ] Task T5: 算法交易

### 阶段 3: 集成测试（预计 30 分钟）
- [ ] Task T6: 端到端工作流

### 阶段 4: 性能和错误测试（预计 30 分钟）
- [ ] Task T7: 性能测试
- [ ] Task T8: 错误处理

### 阶段 5: 修复和重测（预计 1-2 小时）
- [ ] 修复发现的问题
- [ ] 重新运行失败的测试
- [ ] 更新文档

---

## 测试报告模板

完成测试后，创建报告：`docs/superpowers/reports/2026-05-25-v2-migration-test-report.md`

**内容包括：**
- 测试执行日期和环境
- 每个任务的测试结果（通过/失败）
- 发现的问题和修复
- 性能指标
- 最终结论（是否可以发布）

---

## 成功标准

迁移测试通过的标准：
- ✅ 所有 5 个工具的基本功能测试通过
- ✅ 端到端工作流测试通过
- ✅ 错误处理符合预期
- ✅ 性能满足要求（响应时间 < 5秒）
- ✅ 无阻塞性 bug

---

**创建者：** Claude Code  
**审核者：** 待指定  
**预计完成时间：** 3-4 小时
