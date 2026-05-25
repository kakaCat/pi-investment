# Agent 工具迁移到 v2 设计文档

**日期：** 2026-05-25  
**作者：** Claude Code  
**状态：** 设计阶段

## 1. 概述

### 1.1 目标

将 TypeScript Agent 的所有量化工具从 v1（已删除）完全迁移到 quantsys-v2（端口 5001），修复能力矩阵中的 6 个失败功能。

### 1.2 背景

从能力矩阵（`quant-enterprise-plan.md`）诊断，v1 系统存在以下问题：

| 功能 | 状态 | 问题描述 |
|------|------|----------|
| 财务三张表 | ❌ | spawn python 挂了 |
| 质量因子（ROE/毛利率/现金流） | ❌ | 挂了 |
| 动量因子 | ❌ | 挂了 |
| 多因子评分 | ⚠️ | 能跑但 ROE/RSI 全部 null |
| 因子分析 | ❌ | 挂了 |
| TWAP/VWAP 算法执行 | ❌ | 不存在 |

**决策：** v1 已删除，完全迁移到 v2，不保留任何 v1 依赖。

### 1.3 迁移策略

**方案：** 渐进式迁移（自底向上）

**顺序：**
1. 数据层：财务数据
2. 因子层：质量因子 → 动量因子 → 多因子评分 → 因子分析
3. 执行层：TWAP/VWAP

**原则：**
- 每个功能独立验证后再进入下一个
- 统一使用 `QuantV2Client` 调用 v2 API
- 如果 v2 缺少端点，先在 v2 中实现
- 保持 Agent 工具接口不变，只改内部实现

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────┐
│   Agent Tools (src/infrastructure/tools) │
│   - data/                                │
│   - factor/                              │
│   - portfolio/                           │
│   - trade/                               │
│   - monitor/                             │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   QuantV2Client                          │
│   (src/infrastructure/quant/             │
│    quant-v2-client.ts)                   │
│   - 统一的 HTTP 客户端                    │
│   - 错误处理和重试                        │
│   - 类型安全的接口                        │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│   quantsys-v2 Flask API                  │
│   http://127.0.0.1:5001                  │
│   - 217+ API 端点                        │
│   - Repository 层                        │
│   - Pipeline 模式                        │
└─────────────────────────────────────────┘
```

### 2.2 QuantV2Client 设计

**职责：** 统一的 v2 API 客户端，提供类型安全的接口和错误处理。

**核心方法：**

```typescript
class QuantV2Client {
  private baseURL: string = "http://127.0.0.1:5001";
  
  // 数据层
  async getFinancials(symbol: string, reportType?: string): Promise<FinancialData>
  async getKlines(symbol: string, period: string, limit?: number): Promise<KlineData[]>
  async getStockInfo(symbol: string): Promise<StockInfo>
  
  // 因子层
  async computeFactors(params: {
    symbols: string[];
    factors?: string[];
    date?: string;
  }): Promise<FactorResult>
  
  async analyzeFactors(params: {
    factors: string[];
    startDate: string;
    endDate: string;
  }): Promise<FactorAnalysis>
  
  async scanOpportunities(params: {
    stocks?: string[];
    minScore?: number;
    maxRiskLevel?: string;
  }): Promise<Opportunity[]>
  
  // 执行层
  async algoExecute(params: {
    symbol: string;
    side: 'buy' | 'sell';
    quantity: number;
    algo: 'TWAP' | 'VWAP';
    duration?: number;
  }): Promise<AlgoOrder>
  
  // 通用方法
  private async request<T>(endpoint: string, options?: RequestInit): Promise<T>
}
```

**错误处理策略：**
- 网络错误：重试 3 次，指数退避
- 4xx 错误：直接抛出，不重试
- 5xx 错误：重试 2 次
- 超时：30 秒

## 3. 工具迁移映射

### 3.1 财务数据工具

**现状：** `financial.indicators` / `financial.statements` - ❌ spawn python 挂了

**迁移方案：**
- **v2 端点：** `GET /api/stock/<symbol>/financials`
- **新工具：** `data_fetch_financial` (已在 L1 数据管道层)
- **实现：** 调用 `QuantV2Client.getFinancials(symbol, reportType)`
- **返回数据：** 利润表、资产负债表、现金流量表的最近 4 个季度数据

**工具定义：**
```typescript
export const dataFetchFinancialTool: Tool = {
  name: "data_fetch_financial",
  description: "获取财务数据（利润表、资产负债表、现金流量表）",
  parameters: {
    type: "object",
    properties: {
      symbol: { type: "string", description: "股票代码" },
      reportType: { 
        type: "string", 
        enum: ["income", "balance", "cashflow", "all"],
        description: "报表类型，默认 all"
      }
    },
    required: ["symbol"]
  },
  execute: async (args) => {
    const client = new QuantV2Client();
    const data = await client.getFinancials(args.symbol, args.reportType);
    return formatFinancialData(data);
  }
};
```

### 3.2 质量因子工具

**现状：** ROE/毛利率/现金流 - ❌ 挂了

**迁移方案：**
- **v2 端点：** `GET /api/stock/<symbol>/indicators` + `POST /api/factors/compute`
- **新工具：** `factor_calculate` (已在 L2 因子工厂层)
- **实现：** 
  - 先调用 `getFinancials()` 获取财务数据
  - 再调用 `computeFactors()` 计算质量因子
- **返回数据：** ROE、毛利率、净利率、现金流比率等

### 3.3 动量因子工具

**现状：** `factor.compute` - ❌ 挂了

**迁移方案：**
- **v2 端点：** `POST /api/factors/compute`
- **新工具：** `factor_calculate` (统一因子计算入口)
- **实现：** 调用 `QuantV2Client.computeFactors({ symbols, factors: ['momentum', 'rsi', 'macd'] })`
- **返回数据：** 动量、RSI、MACD、布林带等技术因子

### 3.4 多因子评分工具

**现状：** `stock.score` - ⚠️ 能跑但 ROE/RSI 全部 null

**迁移方案：**
- **v2 端点：** `POST /api/signals/scan`
- **新工具：** 增强现有的 `opportunity-scan-tool.ts`
- **实现：** 调用 `QuantV2Client.scanOpportunities()`，使用 v2 的 OpportunityScoringService
- **返回数据：** 综合评分（技术 50% + 基本面 30% + 资金 20%）

### 3.5 因子分析工具

**现状：** `factor.analyze` - ❌ 挂了

**迁移方案：**
- **v2 端点：** `POST /api/factors/analyze`（需要在 v2 中新增）
- **新工具：** `factor_analyze`（新建）
- **实现：** 调用 `QuantV2Client.analyzeFactors()`
- **返回数据：** IC 值、IC 衰减曲线、因子覆盖率、因子稳定性

### 3.6 TWAP/VWAP 算法执行

**现状：** ❌ 不存在

**迁移方案：**
- **v2 端点：** `POST /api/orders/algo-execute`（需要在 v2 中新增）
- **新工具：** `trade_algo_execute`（新建）
- **实现：** 调用 `QuantV2Client.algoExecute()`
- **返回数据：** 订单 ID、拆单计划、执行状态

## 4. v2 缺失端点补全

### 4.1 因子分析端点

**文件：** `quantsys-v2/api/routes/analysis.py`

**新增路由：**
```python
@analysis_bp.route('/api/factors/analyze', methods=['POST'])
def analyze_factors():
    """
    因子分析：IC值、衰减曲线、覆盖率、稳定性
    
    Request:
    {
      "factors": ["RSI14", "ROE", "momentum_20"],
      "start_date": "2025-01-01",
      "end_date": "2026-05-25",
      "universe": ["600519", "000858"]  // 可选，空=全市场
    }
    
    Response:
    {
      "success": true,
      "factors": [
        {
          "name": "RSI14",
          "ic_daily": 0.05,
          "ic_weekly": 0.08,
          "ic_monthly": 0.12,
          "coverage": 0.95,
          "stability": 0.88,
          "decay_curve": [0.05, 0.04, 0.03, ...]
        }
      ]
    }
    """
```

**实现逻辑：**
- 从 `factor_values` 表读取因子数据
- 计算 Rank IC（Spearman 相关系数）
- 计算因子覆盖率（有值的股票数 / 总股票数）
- 计算因子稳定性（本期因子值与上期的相关系数）

### 4.2 TWAP/VWAP 算法执行端点

**文件：** `quantsys-v2/api/routes/orders.py`

**新增路由：**
```python
@orders_bp.route('/api/orders/algo-execute', methods=['POST'])
def algo_execute():
    """
    算法交易执行：TWAP/VWAP拆单
    
    Request:
    {
      "symbol": "600519.SH",
      "side": "buy",
      "quantity": 1000,
      "algo": "TWAP",
      "duration_minutes": 30,
      "start_time": "09:30:00"  // 可选
    }
    
    Response:
    {
      "success": true,
      "order_id": "algo_20260525_001",
      "slices": [
        {"time": "09:30:00", "quantity": 100},
        {"time": "09:33:00", "quantity": 100},
        ...
      ],
      "status": "pending"
    }
    """
```

**实现逻辑：**
- TWAP：均匀拆分到时间段内
- VWAP：根据历史成交量分布加权拆分
- 生成拆单计划，写入 `algo_orders` 表
- 返回订单 ID 和拆单明细

## 5. 数据格式转换

### 5.1 财务数据格式化

**v2 API 返回：**
```json
{
  "success": true,
  "data": {
    "income_statement": [
      {"period": "2026Q1", "revenue": 123456789, "net_profit": 23456789}
    ],
    "balance_sheet": [...],
    "cash_flow": [...]
  }
}
```

**Agent 工具输出（格式化为文本）：**
```
财务数据 - 600519.SH 贵州茅台

【利润表】最近4季度
2026Q1: 营收 1,234.57亿  净利润 234.57亿  净利率 19.0%
2025Q4: 营收 1,156.23亿  净利润 220.34亿  净利率 19.1%
...

【资产负债表】2026Q1
总资产 3,456.78亿  净资产 2,345.67亿  资产负债率 32.1%

【现金流量表】2026Q1
经营现金流 345.67亿  投资现金流 -123.45亿  筹资现金流 -45.67亿
```

### 5.2 因子计算格式化

**v2 API 返回：**
```json
{
  "success": true,
  "factors": {
    "600519.SH": {
      "RSI14": 65.3,
      "MACD": 2.5,
      "ROE": 0.28,
      "gross_margin": 0.91
    }
  }
}
```

**Agent 工具输出：**
```
因子计算结果 - 600519.SH

【技术因子】
RSI(14): 65.3 (中性偏多)
MACD: 2.5 (金叉)
布林带位置: 0.75 (接近上轨)

【基本面因子】
ROE: 28.0% (优秀)
毛利率: 91.0% (极高)
净利率: 52.3% (优秀)
```

**格式化原则：**
- 数字格式化（亿、万、百分比）
- 添加解释性标签（优秀/良好/一般/较差）
- 分组展示（技术/基本面/资金）
- 突出关键指标

## 6. 错误处理和降级策略

### 6.1 v2 服务不可用

```typescript
class QuantV2Client {
  async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        ...options,
        timeout: 30000
      });
      
      if (!response.ok) {
        throw new APIError(response.status, await response.text());
      }
      
      return await response.json();
    } catch (error) {
      if (error instanceof NetworkError) {
        throw new Error(
          `v2 服务连接失败 (${this.baseURL})。请检查：\n` +
          `1. v2 服务是否启动: python quantsys-v2/api/server.py\n` +
          `2. 端口 5001 是否被占用\n` +
          `3. 环境变量 QUANTSYS_API_URL 是否正确`
        );
      }
      throw error;
    }
  }
}
```

### 6.2 数据缺失

```typescript
async getFinancials(symbol: string): Promise<FinancialData> {
  const result = await this.request(`/api/stock/${symbol}/financials`);
  
  if (!result.data || result.data.length === 0) {
    throw new Error(
      `${symbol} 财务数据缺失。可能原因：\n` +
      `1. 该股票尚未录入数据库\n` +
      `2. 财务报告尚未披露\n` +
      `建议：使用 data_fetch_stock 先获取基本信息`
    );
  }
  
  return result.data;
}
```

### 6.3 因子计算失败

```typescript
async computeFactors(params): Promise<FactorResult> {
  const result = await this.request('/api/factors/compute', {
    method: 'POST',
    body: JSON.stringify(params)
  });
  
  // 检查因子覆盖率
  const coverage = result.factors.filter(f => f.value !== null).length / 
                   result.factors.length;
  
  if (coverage < 0.5) {
    console.warn(
      `因子覆盖率较低 (${(coverage * 100).toFixed(1)}%)。` +
      `可能需要先更新 K 线数据。`
    );
  }
  
  return result;
}
```

**降级策略：**
- **不使用 v1 降级**（v1 已删除）
- **错误信息提供明确的修复建议**
- **部分失败时返回可用数据 + 警告**

## 7. 工具文件组织

```
src/infrastructure/tools/
├── data/
│   ├── data-fetch-stock.ts       (已存在)
│   ├── data-fetch-kline.ts       (已存在)
│   └── data-fetch-financial.ts   (已存在，需迁移到v2)
├── factor/
│   ├── factor-calculate.ts       (已存在，需迁移到v2)
│   └── factor-analyze.ts         (新建)
├── portfolio/
│   └── portfolio-rebalance.ts    (已存在)
├── trade/
│   ├── trade-manage-orders.ts    (已存在)
│   └── trade-algo-execute.ts     (新建)
└── monitor/
    └── monitor-alert.ts          (已存在)
```

**工具实现模式（统一）：**

```typescript
export const factorCalculateTool: Tool = {
  name: "factor_calculate",
  description: "批量计算技术因子和基本面因子",
  parameters: {
    type: "object",
    properties: {
      symbols: {
        type: "array",
        items: { type: "string" },
        description: "股票代码列表，空=全市场"
      },
      factors: {
        type: "array",
        items: { type: "string" },
        description: "因子列表，空=全部因子"
      },
      date: {
        type: "string",
        description: "计算日期，空=最新交易日"
      }
    }
  },
  execute: async (args) => {
    const client = new QuantV2Client();
    const result = await client.computeFactors({
      symbols: args.symbols || [],
      factors: args.factors,
      date: args.date
    });
    return formatFactorResult(result);
  }
};
```

**关键点：**
1. 所有工具统一使用 `QuantV2Client`
2. 参数验证在工具层完成
3. 错误处理统一格式化为用户友好的消息
4. 返回数据格式化为 Agent 可理解的文本

## 8. 迁移验证和测试

### 8.1 验证 v2 服务可用性

```bash
# 启动 v2 服务
cd quantsys-v2
python api/server.py

# 验证健康检查
curl http://127.0.0.1:5001/api/health
```

### 8.2 端点可用性测试

```bash
# 测试财务数据
curl http://127.0.0.1:5001/api/stock/600519.SH/financials

# 测试因子计算
curl -X POST http://127.0.0.1:5001/api/factors/compute \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["600519.SH"], "factors": ["RSI14", "ROE"]}'

# 测试信号扫描
curl -X POST http://127.0.0.1:5001/api/signals/scan \
  -H "Content-Type: application/json" \
  -d '{"minScore": 60}'
```

### 8.3 Agent 工具集成测试

```typescript
// 测试脚本：src/tests/integration/v2-migration.test.ts
describe('V2 Migration', () => {
  test('财务数据工具', async () => {
    const result = await dataFetchFinancialTool.execute({
      symbol: '600519.SH'
    });
    expect(result).toContain('利润表');
  });
  
  test('因子计算工具', async () => {
    const result = await factorCalculateTool.execute({
      symbols: ['600519.SH'],
      factors: ['RSI14', 'ROE']
    });
    expect(result).toContain('RSI');
  });
  
  test('多因子评分工具', async () => {
    const result = await opportunityScanTool.execute({
      minScore: 60
    });
    expect(result).toContain('综合评分');
  });
});
```

### 8.4 清理残留配置

```bash
# 删除 .env 中的 v1 配置
- PYTHON_BACKEND_URL=http://127.0.0.1:5002
- QUANT_API_HOST=127.0.0.1
- QUANT_API_PORT=5002

# 只保留 v2 配置
QUANTSYS_API_URL=http://127.0.0.1:5001
QUANTSYS_API_HOST=127.0.0.1
QUANTSYS_API_PORT=5001
```

## 9. 实施计划

### 9.1 Phase 1: 基础设施（1 个工作单元）

**任务：**
1. 增强 `QuantV2Client` 类
   - 添加所有需要的方法
   - 实现错误处理和重试逻辑
   - 添加类型定义
2. 创建格式化工具函数
   - `formatFinancialData()`
   - `formatFactorResult()`
   - `formatOpportunities()`

**验收标准：**
- `QuantV2Client` 单元测试通过
- 可以成功调用 v2 的健康检查端点

### 9.2 Phase 2: 数据层迁移（1 个工作单元）

**任务：**
1. 迁移 `data_fetch_financial` 工具
2. 测试财务数据获取和格式化

**验收标准：**
- 可以获取 600519.SH 的财务数据
- 输出格式符合 Agent 要求

### 9.3 Phase 3: 因子层迁移（2 个工作单元）

**任务：**
1. 迁移 `factor_calculate` 工具（质量因子 + 动量因子）
2. 迁移 `opportunity-scan-tool`（多因子评分）
3. 在 v2 中实现 `/api/factors/analyze` 端点
4. 创建 `factor_analyze` 工具

**验收标准：**
- 可以计算 600519.SH 的所有因子
- 多因子评分不再返回 null
- 因子分析返回 IC 值和覆盖率

### 9.4 Phase 4: 执行层迁移（1 个工作单元）

**任务：**
1. 在 v2 中实现 `/api/orders/algo-execute` 端点
2. 创建 `trade_algo_execute` 工具
3. 实现 TWAP/VWAP 拆单逻辑

**验收标准：**
- 可以生成 TWAP 拆单计划
- 可以生成 VWAP 拆单计划

### 9.5 Phase 5: 清理和文档（1 个工作单元）

**任务：**
1. 删除 v1 相关代码
   - `src/services/python/python-backend-client.ts`
   - 环境变量配置
2. 更新 CLAUDE.md 和 README.md
3. 编写迁移完成报告

**验收标准：**
- 代码中无 v1 引用
- 文档更新完成
- 所有测试通过

## 10. 风险和注意事项

### 10.1 风险

1. **v2 端点可能不完全可用**
   - 缓解：先静态检查代码，再实际测试
   - 如果不可用，先在 v2 中实现

2. **数据格式可能不兼容**
   - 缓解：编写格式转换层
   - 保持 Agent 工具接口不变

3. **性能问题**
   - 缓解：v2 使用 Repository 层和缓存
   - 监控响应时间，必要时优化

### 10.2 注意事项

1. **环境配置**
   - 确保 v2 服务正常启动
   - 确保 PostgreSQL 可用
   - 确保环境变量正确

2. **数据完整性**
   - v2 数据库可能需要初始化
   - 可能需要从 SQLite 迁移数据

3. **向后兼容**
   - Agent 工具接口保持不变
   - 只改内部实现

## 11. 成功标准

迁移完成后，能力矩阵应该全部变为 ✅：

| 功能 | 迁移前 | 迁移后 |
|------|--------|--------|
| 财务三张表 | ❌ | ✅ |
| 质量因子 | ❌ | ✅ |
| 动量因子 | ❌ | ✅ |
| 多因子评分 | ⚠️ | ✅ |
| 因子分析 | ❌ | ✅ |
| TWAP/VWAP | ❌ | ✅ |

**验收测试：**
1. 所有 6 个功能可以正常调用
2. 返回数据格式正确
3. 无 v1 代码残留
4. 集成测试全部通过

