# quantsys-v2 端点可用性矩阵

**测试日期：** 2026-05-25  
**测试环境：** quantsys-v2 Flask API (端口 5001)

---

## 摘要

| 状态 | 数量 | 端点 |
|------|------|------|
| ✅ 可用 | 2 | 因子计算、算法交易 |
| ❌ 不可用 | 3 | 财务数据、因子分析、机会扫描 |
| **总计** | **5** | |

**可用率：** 40% (2/5)

---

## 详细测试结果

### 1. 财务数据 ❌

**端点：** `GET /api/stock/{symbol}/financials`  
**TypeScript 方法：** `getFinancials()`  
**工具：** `data_fetch_financial`

**测试命令：**
```bash
curl "http://127.0.0.1:5001/api/stock/600519/financials?type=income&periods=4"
```

**响应：**
```json
{
  "error": "Module not available: No module named 'quantsys'",
  "success": false
}
```

**状态：** ❌ 不可用

**原因：** 端点依赖旧 quantsys 模块（`quantsys.cli.financial_query`）

**代码位置：** `api/routes/analysis.py:267`

**修复方案：**
- 在 DataService 中实现 `get_financial_statements()` 方法
- 使用 akshare 或数据库获取财务数据
- 更新端点使用 DataService 而非旧 quantsys

**优先级：** P0（阻塞工具测试）

---

### 2. 因子计算 ✅

**端点：** `POST /api/compute/factors`  
**TypeScript 方法：** `computeFactors()`  
**工具：** `factor_calculate`

**测试命令：**
```bash
curl -X POST http://127.0.0.1:5001/api/compute/factors \
  -H "Content-Type: application/json" \
  -d '{"symbols":["600519"],"factors":["rsi"]}'
```

**响应：**
```json
{
  "count": 1,
  "results": [
    {
      "date": "2026-05-21",
      "factor_count": 13,
      "factors": {
        "atr14": 20.85535509331259,
        "bollinger_lower": 1292.259113057952,
        "bollinger_middle": 1371.0295,
        "bollinger_upper": 1449.7998869420483,
        "ma10": 1338.138,
        "ma20": 1371.0295,
        "ma5": 1321.25,
        "macd": -29.95050533645758,
        "macd_histogram": -5.362787302734674,
        "macd_signal": -24.587718033722908,
        "rsi14": 26.83471072443048,
        "volume_ma5": 47491.0,
        "volume_ratio": 0.8184287549219852
      },
      "symbol": "600519"
    }
  ],
  "success": true
}
```

**状态：** ✅ 可用

**实现方式：** 使用 v2 的 FactorRepository 和 quantlib

**代码位置：** `api/routes/jobs.py` (推测)

**注意事项：**
- 返回了 13 个因子（包括技术指标）
- 响应格式符合预期
- 需要验证 TypeScript 格式化器是否正确处理

---

### 3. 因子分析 ❌

**端点：** `POST /api/portfolio/factor-analyze`  
**TypeScript 方法：** `analyzeFactors()`  
**工具：** `factor_analyze`

**测试命令：**
```bash
curl -X POST http://127.0.0.1:5001/api/portfolio/factor-analyze \
  -H "Content-Type: application/json" \
  -d '{"factors":["rsi"],"start_date":"2024-01-01","end_date":"2024-01-31"}'
```

**响应：**
```json
{
  "error": "Module not available: No module named 'quantsys'",
  "success": false
}
```

**状态：** ❌ 不可用

**原因：** 端点依赖旧 quantsys 模块或端点未实现

**修复方案：**
- 检查端点是否存在于其他路由文件
- 如不存在，实现因子有效性分析逻辑（IC、覆盖率、稳定性）
- 使用 FactorRepository 和统计分析库

**优先级：** P1（新功能，非阻塞）

---

### 4. 机会扫描 ❌

**端点：** `POST /api/signals/scan`  
**TypeScript 方法：** `scanOpportunities()`  
**工具：** `opportunity_scan`

**测试命令：**
```bash
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{}'
```

**响应：**
```json
{
  "error": "查询指数成分股失败: relation \"quant.index_constituents\" does not exist\nLINE 3:             FROM quant.index_constituents\n                         ^\n",
  "success": false
}
```

**状态：** ❌ 不可用

**原因：** 数据库表 `quant.index_constituents` 不存在

**修复方案：**
- 创建 `quant.index_constituents` 表
- 或修改查询逻辑使用现有表
- 或使用 StockRepository 获取股票池

**优先级：** P1（功能存在但数据缺失）

---

### 5. 算法交易 ✅

**端点：** `POST /api/orders/algo-execute`  
**TypeScript 方法：** `algoExecute()`  
**工具：** `trade_algo_execute`

**测试命令：**
```bash
curl -X POST http://127.0.0.1:5001/api/orders/algo-execute \
  -H "Content-Type: application/json" \
  -d '{"symbol":"600519","side":"buy","quantity":1000,"algo":"TWAP","duration_minutes":30,"start_time":"09:30:00"}'
```

**响应：**
```json
{
  "data": {
    "algo": "TWAP",
    "childOrders": [
      {
        "quantity": 100,
        "status": "pending",
        "time": "09:30:00"
      },
      {
        "quantity": 100,
        "status": "pending",
        "time": "09:33:00"
      },
      // ... 10 个子订单
    ],
    "executionStats": {
      "avgQuantity": 100,
      "endTime": "10:00:00",
      "startTime": "09:30:00",
      "totalSlices": 10
    },
    "orderId": "...",
    "parentQuantity": 1000,
    "side": "buy",
    "symbol": "600519"
  },
  "success": true
}
```

**状态：** ✅ 可用

**实现方式：** Task 4.1 中实现的真正 v2 端点

**代码位置：** `api/routes/orders.py`

**注意事项：**
- TWAP 算法正确实现（10 个均匀分布的子订单）
- 响应格式符合 TypeScript 类型定义
- 需要验证 VWAP 算法

---

## 问题分类

### 类型 A：依赖旧 quantsys 模块

**端点：**
1. 财务数据 (`/api/stock/<symbol>/financials`)
2. 因子分析 (`/api/portfolio/factor-analyze`)

**特征：**
- 返回 "No module named 'quantsys'" 错误
- 代码中有 `from quantsys.cli.*` 导入

**修复策略：**
- 在 v2 中实现真正的端点
- 使用 DataService、Repository 层
- 移除对旧 quantsys 的依赖

---

### 类型 B：数据库表缺失

**端点：**
1. 机会扫描 (`/api/signals/scan`)

**特征：**
- 返回 "relation does not exist" 错误
- 端点逻辑存在，但数据不完整

**修复策略：**
- 创建缺失的数据库表
- 或修改查询逻辑使用现有表
- 填充必要的数据

---

### 类型 C：已正确实现

**端点：**
1. 因子计算 (`/api/compute/factors`)
2. 算法交易 (`/api/orders/algo-execute`)

**特征：**
- 返回正确的数据
- 使用 v2 的 Repository 和服务层
- 无外部依赖

**下一步：**
- 测试 TypeScript 工具集成
- 验证数据格式化
- 测试错误处理

---

## 修复优先级

### P0 - 阻塞发布

1. **财务数据端点** (`/api/stock/<symbol>/financials`)
   - 影响：阻塞 `data_fetch_financial` 工具测试
   - 工作量：4-6 小时
   - 依赖：需要实现 DataService.get_financial_statements()

### P1 - 重要但非阻塞

2. **机会扫描端点** (`/api/signals/scan`)
   - 影响：阻塞 `opportunity_scan` 工具测试
   - 工作量：2-3 小时
   - 依赖：需要创建或修复数据库表

3. **因子分析端点** (`/api/portfolio/factor-analyze`)
   - 影响：阻塞 `factor_analyze` 工具测试
   - 工作量：3-4 小时
   - 依赖：需要实现因子有效性分析逻辑

### P2 - 可以延后

4. **TypeScript 工具集成测试**
   - 测试已可用的端点（因子计算、算法交易）
   - 验证数据格式化
   - 测试错误处理

---

## 建议的修复顺序

### 阶段 1：测试已可用的端点（1-2 小时）

1. 测试因子计算工具 (`factor_calculate`)
2. 测试算法交易工具 (`trade_algo_execute`)
3. 验证数据格式化是否正确
4. 测试错误处理场景

**目标：** 验证 40% 的功能可用

---

### 阶段 2：修复财务数据端点（4-6 小时）

1. 在 DataService 中实现 `get_financial_statements()`
2. 使用 akshare 获取财务数据
3. 更新 `api/routes/analysis.py` 使用 DataService
4. 测试财务数据工具

**目标：** 可用率提升到 60%

---

### 阶段 3：修复机会扫描端点（2-3 小时）

1. 检查数据库 schema
2. 创建 `quant.index_constituents` 表或修改查询
3. 填充必要数据
4. 测试机会扫描工具

**目标：** 可用率提升到 80%

---

### 阶段 4：实现因子分析端点（3-4 小时）

1. 设计因子分析逻辑（IC、覆盖率、稳定性）
2. 实现端点
3. 测试因子分析工具

**目标：** 可用率达到 100%

---

## 总结

**当前状态：**
- ✅ 2/5 端点可用（40%）
- ❌ 3/5 端点不可用（60%）

**阻塞问题：**
- 财务数据端点依赖旧 quantsys 模块
- 机会扫描端点缺少数据库表
- 因子分析端点未实现或依赖旧模块

**预计修复时间：**
- 最小可行版本（测试已可用端点）：1-2 小时
- 修复财务数据（P0）：4-6 小时
- 完整修复所有端点：9-13 小时

**建议：**
1. 先测试已可用的 2 个端点，验证架构正确性
2. 优先修复财务数据端点（P0）
3. 根据业务需求决定是否修复其他端点

---

**创建时间：** 2026-05-25 21:35  
**测试人员：** Claude Code
