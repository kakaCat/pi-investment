# Strategy Execute 端点修复

**日期**: 2026-05-29  
**问题**: `strategy_execute` 工具返回 `undefined` 值  
**根本原因**: quantsys-v2 后端缺少执行单个内置策略的 API 端点

## 问题诊断

### 原始错误
```
【策略信号】undefined (undefined)
策略: undefined
时间: undefined

信号: undefined
置信度: NaN%
理由: undefined
```

### 根本原因
- TypeScript 工具调用 `/api/strategy/run` 端点
- 该端点返回的是**策略引擎流水线结果**（行业轮动 + 选股）
- 数据结构不匹配 `StrategySignal` 类型
- 缺少执行单个内置策略并返回信号的端点

## 解决方案

### 1. 添加新的 API 端点

**文件**: `quantsys-v2/api/routes/strategies.py`

**端点**: `POST /api/strategies/execute`

**功能**:
- 接收股票代码 + 策略名称
- 使用 `StrategyFactory` 创建策略实例
- 获取 K 线数据（最近 200 天）
- 调用策略的 `generate_signal()` 方法
- 返回买卖信号 + 风险管理参数

**请求格式**:
```json
{
  "symbol": "600000.SH",
  "strategyName": "Momentum",
  "date": "2024-12-31"  // 可选
}
```

**响应格式**:
```json
{
  "success": true,
  "data": {
    "symbol": "600000.SH",
    "name": "浦发银行",
    "strategy": "Momentum",
    "action": "hold",
    "confidence": 0.3,
    "reason": "弱势动量 (ROC MA=-5.85%), 当前价 1303.00, 趋势向下",
    "riskManagement": null,
    "indicators": null,
    "timestamp": "2026-05-29T14:58:18.846596"
  }
}
```

### 2. 更新 TypeScript 客户端

**文件**: `src/infrastructure/quant/quant-v2-client.ts`

**变更**:
- 修改 `executeStrategy()` 函数
- 从 `/api/strategy/run` 改为 `/api/strategies/execute`
- 请求参数转换为 camelCase（`strategyName`）

### 3. 关键实现细节

**股票代码标准化**:
```python
if not symbol.endswith(('.SH', '.SZ', '.BJ')):
    if symbol.startswith('6'):
        symbol = f"{symbol}.SH"
    elif symbol.startswith(('0', '3')):
        symbol = f"{symbol}.SZ"
```

**策略名称转换**:
```python
# "Momentum" -> "momentum"
strategy_type = StrategyFactory.class_name_to_type(strategy_name + 'Strategy')
```

**K 线数据获取**:
```python
if target_date:
    start_date = end_date - timedelta(days=400)  # ~200 trading days
    klines = kline_repo.get_range(symbol, start_date, target_date)
else:
    klines = kline_repo.get_latest(symbol, limit=200)
```

## 测试结果

### 测试 1: Momentum 策略
```bash
curl -X POST http://127.0.0.1:5001/api/strategies/execute \
  -H "Content-Type: application/json" \
  -d '{"symbol":"600000.SH","strategyName":"Momentum"}'
```

**结果**: ✅ 成功返回持有信号

### 测试 2: VolatilityBreakout 策略
```bash
curl -X POST http://127.0.0.1:5001/api/strategies/execute \
  -H "Content-Type: application/json" \
  -d '{"symbol":"600036.SH","strategyName":"VolatilityBreakout"}'
```

**结果**: ✅ 成功返回持有信号

### 测试 3: 策略不存在
```bash
curl -X POST http://127.0.0.1:5001/api/strategies/execute \
  -H "Content-Type: application/json" \
  -d '{"symbol":"600000.SH","strategyName":"NonExistent"}'
```

**结果**: ✅ 返回 404 错误 + 可用策略列表

## 支持的策略

通过 `StrategyFactory` 自动发现的 18 种内置策略：
- Momentum (动量策略)
- RSIReversal (RSI 反转)
- BollingerBreakout (布林带突破)
- Turtle (海龟策略)
- DonchianChannel (唐奇安通道)
- MeanReversion (均值回归)
- VolatilityBreakout (波动率突破)
- Breakout (突破策略)
- ... 等

## 相关文件

- `quantsys-v2/api/routes/strategies.py` - 新端点实现
- `src/infrastructure/quant/quant-v2-client.ts` - 客户端更新
- `src/infrastructure/tools/strategy/execute-tool.ts` - 工具定义
- `src/infrastructure/quant/formatters.ts` - 信号格式化

## 后续工作

- [ ] 添加端点的单元测试
- [ ] 添加端到端测试
- [ ] 更新 API 文档
- [ ] 考虑添加参数自定义支持（目前使用默认参数）
