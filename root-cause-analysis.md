# 因子注入问题 - 根本原因分析

## 问题描述

用户报告：
1. 全局搜索 `inject_factor` 零结果
2. 策略代码的 `test_pair(df)` 拿不到预计算的 RSI/MACD/布林带列

## 根本原因

### 1. 函数名称问题

**用户搜索的函数名不存在：**
- 用户搜索：`inject_factor` ❌
- 实际函数名：`_inject_financial` ✅

位置：`quantsys-v2/services/strategy_code_service.py:1260`

### 2. 技术指标注入缺失

**财务指标已注入，但技术指标未注入：**

#### 已注入的指标（18个财务指标）：
```python
# quantsys-v2/services/strategy_code_service.py:393
klines = self._inject_financial(klines, symbol)
```

注入的列：
- 季度指标（_q 后缀）：`roe_q`, `gross_margin_q`, `net_profit_margin_q`, `debt_ratio_q`, `revenue_growth_q`, `ocf_to_profit_q`, `current_ratio_q`, `roa_q`, `operating_margin_q`
- 年度指标（_y 后缀）：`roe_y`, `gross_margin_y`, `net_profit_margin_y`, `debt_ratio_y`, `revenue_growth_y`, `ocf_to_profit_y`, `current_ratio_y`, `roa_y`, `operating_margin_y`

#### 未注入的指标（技术指标）：
- `rsi` - RSI 指标
- `macd` - MACD 指标
- `macd_signal` - MACD 信号线
- `bollinger_upper` - 布林带上轨
- `bollinger_lower` - 布林带下轨
- 等其他技术指标

### 3. 示例代码的假设

示例策略代码（`quantsys-v2/examples/strategy_with_financials.py`）假设技术指标已存在：

```python
# 2. 技术面信号
df['oversold'] = df['rsi'] < 30  # ❌ 假设 rsi 列存在
df['macd_golden'] = (df['macd'] > df['macd_signal']) & ...  # ❌ 假设 macd 列存在

# 4. 卖出信号：技术面超买
df['sell'] = df['rsi'] > 70  # ❌ 假设 rsi 列存在
```

但实际上，`run_strategy()` 方法只注入了：
1. 资金流数据（`_inject_fund_flow`）
2. 财务指标数据（`_inject_financial`）
3. **没有注入技术指标数据**

### 4. 测试中的 Mock 数据

测试文件中手动添加了 RSI 列来绕过这个问题：

```python
# quantsys-v2/tests/test_strategy_financial_injection.py:259
klines = [
    {'trade_date': '2026-04-20', 'close': 100, 'rsi': 30},  # 手动添加 rsi
    {'trade_date': '2026-04-25', 'close': 102, 'rsi': 32},
    {'trade_date': '2026-05-15', 'close': 105, 'rsi': 70},
]
```

这掩盖了真实场景中技术指标缺失的问题。

## 数据流分析

```
StrategyCodeService.run_strategy()
  ↓
1. 获取 K 线数据
   klines = self._get_klines(symbol, limit)
   列：['trade_date', 'open', 'high', 'low', 'close', 'volume']
  ↓
2. 注入资金流数据
   klines = self._inject_fund_flow(klines, symbol)
   新增列：['main_net_inflow', 'main_net_pct', 'super_large_net', ...]
  ↓
3. 注入财务指标数据
   klines = self._inject_financial(klines, symbol)
   新增列：['roe_q', 'roe_y', 'gross_margin_q', ...]
  ↓
4. 执行策略代码
   result = self.indicator_executor.execute(code, klines, params)
   ↓
   df = pd.DataFrame(klines)
   ↓
   exec(code, namespace)  # 策略代码在这里执行
   ↓
   ❌ KeyError: 'rsi' 列不存在！
```

## 验证结果

运行 `test-financial-injection.py` 确认：
- ✅ 财务指标已正确注入（18个列）
- ✅ 策略代码可以访问财务指标列
- ❌ 技术指标（RSI、MACD、布林带）**未注入**

## 解决方案

### 方案 1：添加技术指标注入（推荐）

在 `StrategyCodeService.run_strategy()` 中添加技术指标注入步骤：

```python
# 3.7. 注入技术指标数据到 kline（让策略代码可直接使用技术因子）
klines = self._inject_technical_indicators(klines, symbol)
```

实现 `_inject_technical_indicators()` 方法，计算并注入：
- RSI
- MACD + MACD Signal
- 布林带（上轨、中轨、下轨）
- 其他常用技术指标

### 方案 2：策略代码自行计算（当前状态）

策略代码需要自己计算技术指标：

```python
# 计算 RSI
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

# 计算 MACD
ema12 = df['close'].ewm(span=12).mean()
ema26 = df['close'].ewm(span=26).mean()
df['macd'] = ema12 - ema26
df['macd_signal'] = df['macd'].ewm(span=9).mean()

# 然后使用
df['buy'] = (df['rsi'] < 30) & df['quality_stock']
```

### 方案 3：更新示例代码和文档

如果选择方案 2，需要：
1. 更新 `examples/strategy_with_financials.py` 示例，展示如何计算技术指标
2. 更新 `quantsys-v2/CLAUDE.md` 文档，说明只有财务指标被注入
3. 提供技术指标计算的辅助函数或库

## 推荐行动

1. **立即**：更新文档和示例代码，明确说明哪些指标被注入，哪些需要自行计算
2. **短期**：实现 `_inject_technical_indicators()` 方法，提供常用技术指标
3. **长期**：考虑可配置的指标注入系统，让用户选择需要的指标

## 相关文件

- `quantsys-v2/services/strategy_code_service.py` - 策略服务（注入逻辑）
- `quantsys-v2/examples/strategy_with_financials.py` - 示例策略（假设技术指标存在）
- `quantsys-v2/tests/test_strategy_financial_injection.py` - 测试（手动 mock RSI）
- `quantsys-v2/CLAUDE.md` - 文档（需要更新）
