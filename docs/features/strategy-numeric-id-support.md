# 策略数字ID支持功能

## 概述

为 `strategy_execute` 工具添加数字ID支持，允许使用数字ID（如 "53"）或策略名称（如 "adx_trend"）执行策略。

## 实现日期

2026-06-02

## 问题背景

**原始错误**:
```
strategy_execute (numeric) │ 策略不存在 │ HTTP 400: ID 53 不存在, 可用是 adx_trend/bollinger_breakout 等名称
```

**原因**:
- 数据库中策略使用数字ID（`quant.strategy_configs.id`）
- `StrategyFactory` 使用字符串名称（`strategy_type`）作为标识符
- 前端工具直接传递用户输入，没有ID转换逻辑

## 解决方案

### 1. 前端工具修改

**文件**: `src/infrastructure/tools/strategy/execute-tool.ts`

**修改内容** (第136-157行):
```typescript
// 数字ID检测：使用正则 /^\d+$/
if (/^\d+$/.test(strategy)) {
  try {
    // 调用 GET /api/strategies/{strategy_id}
    const response = await fetch(`${baseUrl}/api/strategies/${strategy}`, {
      signal: AbortSignal.timeout(5_000),
    });

    if (!response.ok) {
      return {
        content: [{
          type: "text" as const,
          text: `策略ID ${strategy} 不存在。请使用 strategy_list 查看可用策略。`,
        }],
        details: undefined,
      };
    }

    const data = (await response.json()) as any;
    if (data.success && data.data?.strategy_type) {
      const originalId = strategy;
      strategy = data.data.strategy_type;  // 替换为策略名称
      console.log(`[strategy_execute] ID ${originalId} → 名称 ${strategy}`);
    }
  } catch (error) {
    // 静默失败，继续使用原值
    console.warn(`[strategy_execute] ID转换失败: ${error}`);
  }
}
```

### 2. 后端API修改

**文件**: `quantsys-v2/api/routes/strategies.py`

**修改内容** (第89-104行):
```python
enriched = {
    'id': str(strategy.get('id')),
    'name': strategy.get('strategy_name'),          # 修复：使用正确的字段名
    'strategy_type': strategy.get('strategy_type'),  # 新增：保留原始字段
    'type': type_mapping.get(strategy.get('code_type'), 'trend'),
    'status': status_mapping.get(validation_status, 'stopped'),
    'description': strategy.get('description'),
    'code': strategy.get('code_content'),
    'params': strategy.get('parsed_params'),
    'performance': None,
    'positions': 0,
    'created_at': strategy.get('created_at'),
    'updated_at': strategy.get('updated_at'),
    'last_executed': strategy.get('last_executed')
}
```

**关键变更**:
1. `name` 字段：从 `strategy.get('name')` 改为 `strategy.get('strategy_name')`
2. 新增 `strategy_type` 字段：用于ID转换

## 数据模型

### 数据库表: `quant.strategy_configs`

```sql
CREATE TABLE quant.strategy_configs (
    id BIGSERIAL PRIMARY KEY,              -- 数字ID
    strategy_name TEXT NOT NULL UNIQUE,    -- 显示名称
    strategy_type TEXT NOT NULL,           -- StrategyFactory 标识符
    code_type TEXT,                        -- 策略代码类型
    code_content TEXT,                     -- 策略代码
    ...
);
```

### 策略类型

#### 用户自定义策略
- 存储在：`quant.strategy_configs`
- `strategy_type` 可能为 `null` 或自定义值
- `code_type`: "indicator" | "script" | "strategy"

#### 内置策略
- 来源：`StrategyFactory._registry`
- 19个内置策略类型：
  - `adx_trend` - ADX趋势策略
  - `bollinger_breakout` - 布林带突破
  - `breakout` - 价格突破
  - `cci_reversal` - CCI反转
  - `config_driven` - 配置驱动
  - `donchian_channel` - 唐奇安通道
  - `ensemble_vote` - 集成投票
  - `grid_trading` - 网格交易
  - `ma_cross` - 均线交叉
  - `mean_reversion` - 均值回归
  - `ml_prediction` - ML预测
  - `momentum` - ROC动量
  - `multi_factor` - 多因子
  - `multi_factor_swing` - 多因子波段
  - `pairs_correlation` - 配对交易
  - `pe_momentum_ma60` - PE价值+动量+MA60
  - `rsi_reversal` - RSI反转
  - `turtle` - 海龟交易
  - `volatility_breakout` - 波动率突破

## 使用示例

### 场景1: 使用数字ID（新功能）

```typescript
// Agent调用
strategy_execute({
  action: "single",
  strategy: "231",        // 数字ID
  symbol: "600000.SH"
})

// 工具行为：
// 1. 检测到 "231" 是纯数字
// 2. 调用 GET /api/strategies/231
// 3. 提取 strategy_type 字段（如果存在）
// 4. 使用策略名称执行
```

### 场景2: 使用策略名称（向后兼容）

```typescript
// Agent调用
strategy_execute({
  action: "single",
  strategy: "adx_trend",  // 内置策略名称
  symbol: "600000.SH"
})

// 工具行为：
// 1. 检测到不是纯数字
// 2. 跳过ID转换
// 3. 直接使用策略名称执行
```

### 场景3: 批量执行

```typescript
strategy_execute({
  action: "batch",
  strategy: "multi_factor_swing",
  symbols: ["600000.SH", "600519.SH", "000001.SZ"]
})
```

## 错误处理

### 错误1: 策略ID不存在

**输入**: `strategy: "999"`

**输出**: 
```
策略ID 999 不存在。请使用 strategy_list 查看可用策略。
```

### 错误2: strategy_type 为 null

**情况**: 用户自定义策略，数据库中 `strategy_type` 字段为空

**行为**: 
- ID转换后得到 `null`
- 传递给后端
- 后端报错: "策略不存在: null，可用: [adx_trend, bollinger_breakout, ...]"

**解决方法**: 用户自定义策略暂不支持通过ID执行，应使用策略名称或修复数据

### 错误3: API超时

**情况**: 后端服务不可用或响应超时（>5秒）

**行为**: 
- 静默失败，继续使用原始数字ID
- 后端可能报错（取决于后端如何处理数字ID）

## 测试验证

### 1. 查询策略列表
```bash
curl http://127.0.0.1:5001/api/strategies | jq '.data.items[] | {id, name, strategy_type}'
```

### 2. 查询单个策略
```bash
curl http://127.0.0.1:5001/api/strategies/231 | jq '.data | {id, name, strategy_type}'
```

**预期输出**:
```json
{
  "id": "231",
  "name": null,           // 用户策略可能没有名称
  "strategy_type": null   // 用户策略可能没有 strategy_type
}
```

### 3. 查询内置策略列表
```bash
curl 'http://127.0.0.1:5001/api/strategies?source=builtin' | jq '.data.strategies[] | {strategyType, description}'
```

## 已知限制

1. **用户自定义策略**: 如果 `strategy_type` 为 `null`，则无法通过数字ID执行
2. **缓存缺失**: 每次ID转换都会调用API，无缓存机制
3. **超时处理**: API超时时静默失败，可能导致混乱的错误信息
4. **工具覆盖**: 仅 `strategy_execute` 工具支持数字ID，其他工具（如 `strategy_detail`）未实现

## 后续优化建议

### 高优先级
1. **数据修复**: 确保所有策略都有有效的 `strategy_type`
2. **ID缓存**: 在内存中缓存ID→名称映射，减少API调用
3. **错误提示**: 当 `strategy_type` 为 `null` 时，返回更友好的提示

### 中优先级
4. **工具统一**: 其他策略工具也支持数字ID（`strategy_detail`, `strategy_optimize`, `strategy_batch_validate`）
5. **性能监控**: 记录ID转换的成功率和延迟

### 低优先级
6. **批量转换**: 支持 `symbols` 数组中的多个策略ID
7. **本地映射**: 在工具注册时预加载策略映射表

## 相关文件

### 前端
- `src/infrastructure/tools/strategy/execute-tool.ts`

### 后端
- `quantsys-v2/api/routes/strategies.py` - API路由和数据转换
- `quantsys-v2/services/strategy_code_service.py` - 策略服务层
- `quantsys-v2/repositories/strategy_repository.py` - 数据库访问层
- `quantsys-v2/services/strategy_execution_service.py` - 策略执行引擎

### 数据库
- `quant.strategy_configs` - 策略配置表
- `quant.strategy_metadata` - 内置策略元数据表（已弃用）

### 文档
- `test-strategy-id-support.md` - 测试文档（临时）

## 变更日志

| 日期 | 修改内容 | 文件 |
|------|---------|------|
| 2026-06-02 | 添加数字ID检测和转换逻辑 | `execute-tool.ts` |
| 2026-06-02 | 修复 `name` 字段映射，添加 `strategy_type` 字段 | `strategies.py` |
| 2026-06-02 | 重启后端服务应用更改 | - |

## 验证状态

- ✅ 前端工具修改完成
- ✅ 后端API修改完成
- ✅ 后端服务已重启
- ✅ API返回包含 `strategy_type` 字段
- ⚠️ 端到端测试待完成（需要有效的策略数据）
- ⏳ 数据修复待进行（用户策略 `strategy_type` 为 `null`）
