# 风控系统集成设计文档

**日期**: 2026-05-19  
**作者**: AI Assistant  
**状态**: 待审核

## 1. 问题陈述

### 现状
- Python 有完整风控系统（`quant/quantsys/risk/`）：7项预交易检查、Kelly公式仓位、5种止损策略、熔断机制
- TypeScript AI 推荐买入时**完全没有调用风控检查**
- `calculate_buy_range` 止损价硬编码为 `safeBuy * 0.92`（固定-8%）
- 没有科学的仓位计算，缺少 Kelly 公式应用

### 目标
每次 AI 推荐买入前：
1. 自动执行预交易风控检查（7项规则验证）
2. 使用 Kelly 公式计算科学仓位
3. 动态计算止损价（混合策略：固定止损 + 移动止损）
4. 提供独立工具供 AI 手动验证风险

## 2. 设计决策

### 2.1 风控执行时机
**选择**: C - 双重机制
- `get_buy_range` 自动集成风控（AI 无法跳过）
- 新增 `check_trade_risk` 独立工具（手动验证）

### 2.2 Kelly 参数来源
**选择**: C - 混合策略
- 优先使用历史交易数据（需≥10笔交易）
- 不足时降级到保守默认值（胜率50%，盈亏比1.5）

### 2.3 止损策略
**选择**: D - 混合策略
- 未盈利或盈利<5%：固定止损 -8%
- 盈利≥5%：移动止损，从最高价回撤 -10%

### 2.4 风控响应级别
**选择**: C - 分级响应
- **严重违规**（ST股票、黑名单、最大回撤）→ 硬拒绝
- **轻微违规**（仓位超限、行业集中度）→ 警告 + 调整建议

### 2.5 配置存储
**选择**: C - 数据库配置表
- 在 `portfolio.db` 创建 `risk_config` 表
- 支持动态读取，未来可扩展 UI 配置

## 3. 架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    TypeScript Layer                      │
│  ┌──────────────────┐         ┌──────────────────┐     │
│  │ analysis-tools   │         │  risk-tools      │     │
│  │ - get_buy_range  │         │ - check_trade_   │     │
│  │   (自动风控)      │         │   risk           │     │
│  │                  │         │ - calculate_     │     │
│  │                  │         │   position_size  │     │
│  │                  │         │ - calculate_     │     │
│  │                  │         │   stop_loss      │     │
│  └────────┬─────────┘         └────────┬─────────┘     │
└───────────┼──────────────────────────────┼──────────────┘
            │                              │
            │      callPython()            │
            ▼                              ▼
┌─────────────────────────────────────────────────────────┐
│                    Python Bridge Layer                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │           akshare_bridge.py                       │  │
│  │  - calculate_buy_range() [修改：集成风控]         │  │
│  │  - check_trade_risk() [新增]                      │  │
│  │  - calculate_position_size() [新增]               │  │
│  │  - calculate_stop_loss() [新增]                   │  │
│  └────────────────────┬─────────────────────────────┘  │
│                       │                                  │
│  ┌────────────────────▼─────────────────────────────┐  │
│  │           risk_bridge.py [新增]                   │  │
│  │  - RiskBridge 类                                  │  │
│  │    - _load_config()                               │  │
│  │    - _get_portfolio_snapshot()                    │  │
│  │    - _get_trade_history()                         │  │
│  │    - _calculate_win_rate()                        │  │
│  └────────────────────┬─────────────────────────────┘  │
└─────────────────────────┼──────────────────────────────┘
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
┌──────────────────────┐    ┌──────────────────────┐
│   portfolio.db       │    │ quant/quantsys/risk/ │
│ - holdings           │    │ - pre_trade.py       │
│ - trades             │    │ - position_manager.py│
│ - risk_config [新增] │    │ - stop_loss.py       │
└──────────────────────┘    └──────────────────────┘
```

### 3.2 数据库架构

#### risk_config 表结构

```sql
CREATE TABLE IF NOT EXISTS risk_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

#### 默认配置值

| key | value | description |
|-----|-------|-------------|
| max_position_pct | 0.10 | 单股最大仓位比例 |
| max_sector_pct | 0.30 | 单行业最大仓位比例 |
| max_drawdown | 0.20 | 最大回撤限制 |
| max_daily_trades | 10 | 单日最大交易次数 |
| kelly_fraction | 0.25 | Kelly公式保守系数 |
| min_trade_history | 10 | 使用真实数据的最小交易笔数 |
| default_win_rate | 0.50 | 默认胜率 |
| default_profit_loss_ratio | 1.5 | 默认盈亏比 |
| fixed_stop_loss_pct | 0.08 | 固定止损百分比 |
| trailing_stop_loss_pct | 0.10 | 移动止损百分比 |
| profit_threshold_for_trailing | 0.05 | 切换到移动止损的盈利阈值 |

## 4. 接口设计

### 4.1 Python 函数接口

#### check_trade_risk

```python
def check_trade_risk(symbol: str, action: str, price: float, shares: int) -> dict:
    """
    预交易风控检查
    
    Args:
        symbol: 股票代码（6位数字）
        action: 'buy' 或 'sell'
        price: 交易价格
        shares: 股数
    
    Returns:
        {
            "passed": bool,                    # 是否通过
            "level": "pass"|"warning"|"reject", # 响应级别
            "reason": str,                     # 原因说明
            "violations": [                    # 违规列表
                {
                    "rule": str,               # 规则名称
                    "message": str,            # 详细信息
                    "severity": "high"|"medium" # 严重程度
                }
            ],
            "adjusted_shares": int             # 调整后的合规股数
        }
    
    Raises:
        ValueError: 参数无效
        DatabaseError: 数据库连接失败（降级处理）
    """
```

**风控规则**：
1. 黑名单检查（severity: high）
2. ST股票检查（severity: high）
3. 单股仓位限制 ≤10%（severity: medium）
4. 行业集中度限制 ≤30%（severity: medium）
5. 最大回撤限制 ≤20%（severity: high）
6. 单日交易次数限制 ≤10次（severity: medium）
7. 流动性检查（severity: medium）

**分级响应逻辑**：
- `level: "reject"` → ST股票、黑名单、回撤超限
- `level: "warning"` → 仓位超限、行业集中度、流动性不足
- `level: "pass"` → 通过所有检查

#### calculate_position_size

```python
def calculate_position_size(symbol: str, price: float, signal_strength: float = 1.0) -> dict:
    """
    Kelly公式计算建议仓位
    
    Args:
        symbol: 股票代码
        price: 当前价格
        signal_strength: 信号强度 0-1（默认1.0）
    
    Returns:
        {
            "shares": int,              # 建议股数（100股整数倍）
            "position_pct": float,      # 仓位比例
            "position_value": float,    # 仓位金额
            "method": "kelly",          # 计算方法
            "kelly_params": {
                "win_rate": float,           # 胜率
                "profit_loss_ratio": float,  # 盈亏比
                "data_source": "historical"|"default",  # 数据来源
                "trade_count": int           # 历史交易笔数（仅historical）
            }
        }
    """
```

**Kelly公式**：
```
Kelly% = (p × b - q) / b × kelly_fraction
其中：
- p: 胜率
- q: 败率 (1-p)
- b: 盈亏比
- kelly_fraction: 保守系数（默认0.25）
```

**数据源选择**：
- 历史数据：该股票有 ≥10 笔交易记录
- 默认值：交易记录不足，使用保守值（win_rate=0.50, profit_loss_ratio=1.5）

#### calculate_stop_loss

```python
def calculate_stop_loss(
    symbol: str, 
    entry_price: float, 
    current_price: float = None, 
    highest_price: float = None
) -> dict:
    """
    计算止损价（混合策略）
    
    Args:
        symbol: 股票代码
        entry_price: 入场价
        current_price: 当前价（可选，自动获取）
        highest_price: 持有期间最高价（可选）
    
    Returns:
        {
            "stop_loss_price": float,   # 止损价
            "stop_loss_pct": float,     # 相对入场价的百分比
            "method": "fixed"|"trailing", # 止损方法
            "reason": str               # 选择该方法的原因
        }
    """
```

**混合策略逻辑**：
```python
pnl_pct = (current_price - entry_price) / entry_price

if pnl_pct < 0.05:  # 盈利 < 5%
    # 固定止损
    stop_loss = entry_price * (1 - 0.08)
    method = "fixed"
else:  # 盈利 ≥ 5%
    # 移动止损
    stop_loss = highest_price * (1 - 0.10)
    method = "trailing"
```

#### calculate_buy_range（修改）

```python
def calculate_buy_range(symbol: str, current_price: float = None) -> dict:
    """
    计算买入区间（集成自动风控）
    
    Returns:
        {
            # 原有字段
            "symbol": str,
            "current_price": float,
            "safe_buy": float,
            "ideal_buy": float,
            "target_price": float,
            "support_levels": {...},
            "advice": str,
            
            # 新增字段
            "risk_check": {              # 自动风控结果
                "passed": bool,
                "level": str,
                "reason": str,
                "violations": [...],
                "adjusted_shares": int
            },
            "position_advice": {         # Kelly仓位建议
                "shares": int,
                "position_pct": float,
                "kelly_params": {...}
            },
            "stop_loss": float,          # 动态止损价（替换硬编码）
            "stop_loss_method": str      # "fixed" 或 "trailing"
        }
    """
```

### 4.2 TypeScript 工具接口
#### check_trade_risk 工具

```typescript
{
  name: "check_trade_risk",
  label: "交易风控检查",
  description:
    "Execute pre-trade risk checks before recommending buy/sell. " +
    "Validates against 7 rules: blacklist, ST stocks, position limits (10%), " +
    "sector concentration (30%), max drawdown (20%), daily trade limit, liquidity. " +
    "Returns pass/warning/reject with specific violations and adjusted_shares if position limit exceeded. " +
    "Use when: 1) user asks 'can I buy X', 2) before finalizing buy recommendations, " +
    "3) checking existing position risk. " +
    "Note: get_buy_range already includes automatic risk check, so only call this explicitly " +
    "for manual verification or existing positions.",
  parameters: {
    symbol: "6-digit A-share code",
    action: "'buy' or 'sell'",
    price: "Trade price in CNY",
    shares: "Number of shares to trade"
  }
}
```

#### calculate_position_size 工具

```typescript
{
  name: "calculate_position_size",
  label: "Kelly仓位计算",
  description:
    "Calculate optimal position size using Kelly Criterion. " +
    "Uses historical win_rate and profit_loss_ratio if ≥10 trades exist for this symbol, " +
    "otherwise defaults to conservative values (50% win rate, 1.5 profit/loss ratio). " +
    "Returns suggested shares (100-share lots), position_pct, position_value, and kelly_params " +
    "showing data source. " +
    "Use when: 1) user asks 'how much should I buy', 2) you need scientific position sizing " +
    "beyond fixed percentages. " +
    "signal_strength (0-1) adjusts position based on signal quality: strong signals = 0.8-1.0, weak = 0.5-0.7.",
  parameters: {
    symbol: "6-digit A-share code",
    price: "Current price in CNY",
    signal_strength: "Signal quality 0-1, default 1.0 (optional)"
  }
}
```

#### calculate_stop_loss 工具

```typescript
{
  name: "calculate_stop_loss",
  label: "动态止损计算",
  description:
    "Calculate stop-loss price using hybrid strategy: fixed stop (-8%) when unprofitable, " +
    "trailing stop (-10% from peak) when profit >5%. " +
    "Returns stop_loss_price, stop_loss_pct, method (fixed/trailing), and reason explaining the choice. " +
    "Use when: 1) recommending buy entry with stop-loss, 2) user asks 'where should I set stop-loss', " +
    "3) reviewing existing positions. " +
    "Requires entry_price; current_price and highest_price are optional but improve accuracy for existing positions.",
  parameters: {
    symbol: "6-digit A-share code",
    entry_price: "Entry/buy price in CNY",
    current_price: "Current price (optional, fetched if omitted)",
    highest_price: "Highest price since entry (optional)"
  }
}
```

## 5. 实现细节

### 5.1 核心函数实现逻辑

#### check_trade_risk 实现

```python
def check_trade_risk(symbol, action, price, shares):
    bridge = RiskBridge(portfolio_db, quant_db)
    portfolio = bridge._get_portfolio_snapshot()
    
    # 构造订单对象
    order = SimpleNamespace(
        symbol=symbol, action=action, price=price, shares=shares,
        date=datetime.now().strftime('%Y-%m-%d')
    )
    
    # 执行风控检查
    risk_checker = PreTradeRiskCheck(config=bridge._build_risk_config())
    passed, error_msg = risk_checker.check(order, portfolio, market_data=None)
    
    # 分级响应
    violations = []
    level = "pass"
    adjusted_shares = shares
    
    if not passed:
        # 判断严重程度
        if any(kw in error_msg for kw in ['ST', '黑名单', '回撤']):
            level = "reject"  # 严重违规
        elif '仓位限制' in error_msg:
            level = "warning"  # 仓位超限
            adjusted_shares = bridge._calculate_max_allowed_shares(symbol, price, portfolio)
            violations.append({
                "rule": "position_limit",
                "message": error_msg,
                "severity": "medium"
            })
        else:
            level = "warning"
            violations.append({"rule": "other", "message": error_msg, "severity": "medium"})
    
    return {
        "passed": passed,
        "level": level,
        "reason": error_msg if not passed else "通过所有风控检查",
        "violations": violations,
        "adjusted_shares": adjusted_shares
    }
```

#### calculate_position_size 实现

```python
def calculate_position_size(symbol, price, signal_strength=1.0):
    bridge = RiskBridge(portfolio_db, quant_db)
    portfolio = bridge._get_portfolio_snapshot()
    total_equity = portfolio.total_equity
    
    # 获取历史交易数据
    trades = bridge._get_trade_history(symbol)
    min_trades = int(bridge.config.get('min_trade_history', 10))
    
    # 判断数据源
    if len(trades) >= min_trades:
        win_rate, pl_ratio, count = bridge._calculate_win_rate(trades)
        data_source = "historical"
    else:
        win_rate = float(bridge.config.get('default_win_rate', 0.50))
        pl_ratio = float(bridge.config.get('default_profit_loss_ratio', 1.5))
        data_source = "default"
        count = len(trades)
    
    # 调用 PositionManager
    position_mgr = PositionManager(config=PositionSizeConfig(
        method='kelly',
        kelly_fraction=float(bridge.config.get('kelly_fraction', 0.25)),
        max_position_pct=float(bridge.config.get('max_position_pct', 0.10))
    ))
    
    shares = position_mgr.calculate_position_size(
        symbol=symbol, price=price, total_equity=total_equity,
        signal_strength=signal_strength,
        market_data={'win_rate': win_rate, 'profit_loss_ratio': pl_ratio}
    )
    
    return {
        "shares": shares,
        "position_pct": (shares * price) / total_equity,
        "position_value": shares * price,
        "method": "kelly",
        "kelly_params": {
            "win_rate": round(win_rate, 3),
            "profit_loss_ratio": round(pl_ratio, 2),
            "data_source": data_source,
            "trade_count": count
        }
    }
```

#### calculate_stop_loss 实现

```python
def calculate_stop_loss(symbol, entry_price, current_price=None, highest_price=None):
    bridge = RiskBridge(portfolio_db, quant_db)
    
    # 获取当前价格
    if current_price is None:
        current_price = bridge._fetch_current_price(symbol)
    
    if highest_price is None:
        highest_price = current_price
    
    # 计算盈亏比例
    pnl_pct = (current_price - entry_price) / entry_price
    profit_threshold = float(bridge.config.get('profit_threshold_for_trailing', 0.05))
    
    # 混合策略
    if pnl_pct < profit_threshold:
        # 固定止损
        fixed_pct = float(bridge.config.get('fixed_stop_loss_pct', 0.08))
        stop_loss_price = entry_price * (1 - fixed_pct)
        method = "fixed"
        reason = f"当前盈利{pnl_pct:.1%} < {profit_threshold:.0%}，使用固定止损-{fixed_pct:.0%}"
    else:
        # 移动止损
        trailing_pct = float(bridge.config.get('trailing_stop_loss_pct', 0.10))
        stop_loss_price = highest_price * (1 - trailing_pct)
        method = "trailing"
        reason = f"当前盈利{pnl_pct:.1%} ≥ {profit_threshold:.0%}，使用移动止损（从最高价{highest_price:.2f}回撤{trailing_pct:.0%}）"
    
    return {
        "stop_loss_price": round(stop_loss_price, 2),
        "stop_loss_pct": round((stop_loss_price - entry_price) / entry_price, 4),
        "method": method,
        "reason": reason
    }
```

### 5.2 错误处理策略

#### 数据库连接失败

```python
try:
    portfolio = self._get_portfolio_snapshot()
except sqlite3.Error as e:
    # 降级：使用保守默认值
    return {
        "passed": True,
        "level": "warning",
        "reason": f"无法连接数据库，跳过风控检查: {e}",
        "violations": [{"rule": "db_error", "severity": "high", "message": str(e)}]
    }
```

#### quant模块导入失败

```python
try:
    from quantsys.risk import PreTradeRiskCheck
except ImportError as e:
    # 降级：返回简化检查
    return {
        "passed": True,
        "level": "warning",
        "reason": "风控模块不可用，建议手动检查仓位",
        "violations": [{"rule": "import_error", "severity": "high", "message": str(e)}]
    }
```

#### 历史数据不足

```python
if len(trades) < min_trades:
    # 使用保守默认值
    kelly_params["data_source"] = "default"
    kelly_params["note"] = f"历史交易不足{min_trades}笔（当前{len(trades)}笔），使用保守默认值"
```

#### 价格数据缺失

```python
if current_price is None:
    try:
        current_price = self._fetch_from_quant_db(symbol)
    except Exception:
        return {"error": f"无法获取{symbol}的当前价格，请手动提供"}
```


## 6. 数据流

### 6.1 完整数据流图

```
用户请求: "帮我分析600519的买入时机"
    ↓
AI 调用: get_buy_range(symbol="600519")
    ↓
TypeScript: analysis-tools.ts → callPython("calculate_buy_range")
    ↓
Python: akshare_bridge.py → calculate_buy_range()
    ↓
    ├─→ [技术分析] 计算 MA、布林带、支撑位
    │   └─→ 返回: safe_buy, ideal_buy, target_price
    │
    ├─→ [自动风控] risk_bridge.check_trade_risk()
    │   ├─→ 读取 portfolio.db (holdings, risk_config)
    │   ├─→ 调用 quant/quantsys/risk/pre_trade.py
    │   │   ├─→ 检查黑名单、ST股票
    │   │   ├─→ 检查单股仓位限制 (10%)
    │   │   ├─→ 检查行业集中度 (30%)
    │   │   ├─→ 检查最大回撤 (20%)
    │   │   ├─→ 检查单日交易次数
    │   │   └─→ 检查流动性
    │   └─→ 返回: {passed, level, violations, adjusted_shares}
    │
    ├─→ [Kelly仓位] risk_bridge.calculate_position_size()
    │   ├─→ 读取 portfolio.db (trades 历史)
    │   ├─→ 计算胜率/盈亏比
    │   │   ├─→ 如果 ≥10笔交易 → 使用历史数据
    │   │   └─→ 否则 → 使用默认值 (0.50, 1.5)
    │   ├─→ 调用 quant/quantsys/risk/position_manager.py
    │   │   └─→ Kelly% = (p×b - q)/b × 0.25
    │   └─→ 返回: {shares, position_pct, kelly_params}
    │
    └─→ [动态止损] risk_bridge.calculate_stop_loss()
        ├─→ 读取 risk_config
        ├─→ 计算盈亏比例
        ├─→ 判断策略:
        │   ├─→ 盈利 < 5% → 固定止损 -8%
        │   └─→ 盈利 ≥ 5% → 移动止损 -10%
        └─→ 返回: {stop_loss_price, method, reason}
    ↓
返回综合结果 JSON
    ↓
AI 解析并生成用户友好的建议
```

### 6.2 AI 响应示例

#### 场景1：风控通过

```
根据技术分析，600519当前价1850元接近理想买入区间（1820元）。

✅ 风控检查：通过
- 仓位建议：200股（Kelly仓位9%，基于历史胜率55%、盈亏比2.1）
- 止损位：1674元（固定-8%）
- 目标价：2100元（盈亏比1:2）

建议：可在1820~1780元分批建仓
- 首批：100股（1820元附近）
- 二批：100股（回调至1780元）
```

#### 场景2：仓位超限警告

```
根据技术分析，600519当前价1850元接近理想买入区间。

⚠️ 风控警告：按300股买入会超过单股仓位限制10%（预计12%）

调整方案：
- 建议买入：200股（仓位9%，符合风控）
- Kelly仓位：基于历史数据建议200股
- 止损位：1674元（-8%）
- 目标价：2100元

建议：先买入200股，如果后续其他持仓减仓释放空间，可考虑加仓。
```

#### 场景3：严重违规拒绝

```
❌ 风控拒绝：ST股票不允许交易

600000已被标记为ST股票，根据风控规则无法买入。

建议：
1. 等待摘帽后再考虑
2. 寻找同行业其他优质标的（可用 screen_stocks_quality 筛选）
```

## 7. 文件清单

### 7.1 需要创建的文件

```
python/
  └─ risk_bridge.py          [新增] 风控桥接层

src/infrastructure/tools/invest/
  └─ risk-tools.ts           [新增] 风控工具定义
```

### 7.2 需要修改的文件

```
python/
  └─ akshare_bridge.py       [修改] 新增4个函数，修改calculate_buy_range

src/infrastructure/tools/invest/
  └─ analysis-tools.ts       [修改] 更新getBuyRangeTool描述

src/infrastructure/tools/
  └─ index.ts                [修改] 注册新的风控工具

src/infrastructure/tools/shared/
  └─ python-caller-resilient-adapter.ts  [修改] 添加新函数的超时配置

.pi-invest/
  └─ portfolio.db            [修改] 创建risk_config表并插入默认值
```

### 7.3 依赖的现有文件

```
quant/quantsys/risk/
  ├─ __init__.py             [使用] 导入风控类
  ├─ pre_trade.py            [使用] PreTradeRiskCheck
  ├─ position_manager.py     [使用] PositionManager
  └─ stop_loss.py            [使用] StopLossManager

.pi-invest/
  └─ portfolio.db            [读取] holdings, trades表
```

## 8. 测试策略

### 8.1 单元测试

#### Python 函数测试

```python
# tests/test_risk_bridge.py

def test_check_trade_risk_pass():
    """测试风控通过场景"""
    result = check_trade_risk("600519", "buy", 1800, 100)
    assert result["passed"] == True
    assert result["level"] == "pass"

def test_check_trade_risk_position_limit():
    """测试仓位超限场景"""
    result = check_trade_risk("600519", "buy", 1800, 5000)
    assert result["level"] == "warning"
    assert "仓位限制" in result["reason"]
    assert result["adjusted_shares"] < 5000

def test_check_trade_risk_st_stock():
    """测试ST股票拒绝"""
    result = check_trade_risk("ST600000", "buy", 10, 100)
    assert result["level"] == "reject"
    assert "ST" in result["reason"]

def test_calculate_position_size_with_history():
    """测试Kelly仓位（有历史数据）"""
    result = calculate_position_size("600519", 1800, 0.8)
    assert result["shares"] % 100 == 0  # 100股整数倍
    assert result["kelly_params"]["data_source"] == "historical"

def test_calculate_position_size_default():
    """测试Kelly仓位（无历史数据）"""
    result = calculate_position_size("000001", 15, 1.0)
    assert result["kelly_params"]["data_source"] == "default"
    assert result["kelly_params"]["win_rate"] == 0.50

def test_calculate_stop_loss_fixed():
    """测试固定止损"""
    result = calculate_stop_loss("600519", 1800, 1850, 1850)
    assert result["method"] == "fixed"
    assert result["stop_loss_price"] == 1800 * 0.92

def test_calculate_stop_loss_trailing():
    """测试移动止损"""
    result = calculate_stop_loss("600519", 1800, 1950, 2000)
    assert result["method"] == "trailing"
    assert result["stop_loss_price"] == 2000 * 0.90
```

### 8.2 集成测试

```typescript
// tests/risk-integration.test.ts

describe("Risk System Integration", () => {
  test("get_buy_range includes risk check", async () => {
    const result = await callPython("calculate_buy_range", { symbol: "600519" });
    const data = JSON.parse(result);
    
    expect(data).toHaveProperty("risk_check");
    expect(data).toHaveProperty("position_advice");
    expect(data).toHaveProperty("stop_loss");
    expect(data.stop_loss).not.toBe(data.safe_buy * 0.92); // 不是硬编码
  });
  
  test("check_trade_risk tool works", async () => {
    const result = await checkTradeRiskTool.execute("test", {
      symbol: "600519",
      action: "buy",
      price: 1800,
      shares: 200
    });
    
    expect(result.content[0].text).toContain("passed");
  });
});
```

### 8.3 手动测试场景

1. **正常买入流程**
   - 调用 `get_buy_range("600519")`
   - 验证返回包含 risk_check、position_advice、stop_loss
   - 验证 AI 能正确解读结果

2. **仓位超限场景**
   - 持仓已有多只股票，总仓位接近满
   - 调用 `get_buy_range` 推荐新股票
   - 验证返回 warning 级别，给出 adjusted_shares

3. **ST股票拒绝**
   - 调用 `check_trade_risk("ST600000", "buy", 10, 100)`
   - 验证返回 reject 级别

4. **Kelly仓位计算**
   - 有历史交易的股票：验证使用 historical 数据
   - 新股票：验证使用 default 数据

5. **动态止损**
   - 未盈利持仓：验证使用 fixed 止损
   - 盈利>5%持仓：验证使用 trailing 止损

## 9. 部署步骤

### 9.1 数据库初始化

```bash
# 1. 创建 risk_config 表
sqlite3 .pi-invest/portfolio.db << 'SQL'
CREATE TABLE IF NOT EXISTS risk_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT OR IGNORE INTO risk_config (key, value, description) VALUES
  ('max_position_pct', '0.10', '单股最大仓位比例'),
  ('max_sector_pct', '0.30', '单行业最大仓位比例'),
  ('max_drawdown', '0.20', '最大回撤限制'),
  ('max_daily_trades', '10', '单日最大交易次数'),
  ('kelly_fraction', '0.25', 'Kelly公式保守系数'),
  ('min_trade_history', '10', '使用真实数据的最小交易笔数'),
  ('default_win_rate', '0.50', '默认胜率'),
  ('default_profit_loss_ratio', '1.5', '默认盈亏比'),
  ('fixed_stop_loss_pct', '0.08', '固定止损百分比'),
  ('trailing_stop_loss_pct', '0.10', '移动止损百分比'),
  ('profit_threshold_for_trailing', '0.05', '切换到移动止损的盈利阈值');
SQL
```

### 9.2 代码部署顺序

1. 创建 `python/risk_bridge.py`
2. 修改 `python/akshare_bridge.py`（新增4个函数）
3. 创建 `src/infrastructure/tools/invest/risk-tools.ts`
4. 修改 `src/infrastructure/tools/invest/analysis-tools.ts`
5. 修改 `src/infrastructure/tools/index.ts`（注册工具）
6. 修改 `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`（超时配置）
7. 运行测试
8. 重启服务

### 9.3 验证清单

- [ ] risk_config 表创建成功，包含11条默认配置
- [ ] Python 函数可以正常导入 quant 风控模块
- [ ] `calculate_buy_range` 返回包含 risk_check、position_advice、stop_loss
- [ ] 3个新工具在 AI 工具列表中可见
- [ ] AI 能正确调用新工具并解读结果
- [ ] 单元测试全部通过
- [ ] 集成测试全部通过

## 10. 未来扩展

### 10.1 短期优化（1-2周）

1. **风控配置UI**：在 Web 界面添加风控参数配置页面
2. **风控报告**：定时生成持仓风控报告（每日/每周）
3. **风控事件日志**：记录所有风控拒绝/警告事件到数据库

### 10.2 中期优化（1-2月）

1. **行业数据集成**：自动获取股票行业分类，支持行业集中度检查
2. **动态参数调整**：根据市场波动自动调整风控参数
3. **回测验证**：用历史数据验证风控规则的有效性

### 10.3 长期优化（3-6月）

1. **机器学习优化**：用ML模型优化Kelly参数（胜率、盈亏比预测）
2. **多策略支持**：支持不同风险偏好的风控配置（保守/平衡/激进）
3. **实时监控**：持仓实时监控，触发风控条件自动预警

## 11. 风险与限制

### 11.1 已知限制

1. **历史数据依赖**：Kelly仓位计算依赖历史交易数据，新用户效果有限
2. **行业分类缺失**：当前无行业数据，行业集中度检查可能跳过
3. **实时性**：风控检查基于数据库快照，可能有延迟
4. **ST股票识别**：简单字符串匹配，可能误判

### 11.2 潜在风险

1. **过度保守**：默认参数可能过于保守，限制收益
2. **数据不一致**：portfolio.db 和 quant DB 数据不同步
3. **性能影响**：每次 `get_buy_range` 都执行风控，可能增加延迟

### 11.3 缓解措施

1. 提供配置调整接口，用户可根据风险偏好调整
2. 定期同步数据，确保一致性
3. 优化查询性能，添加数据库索引
4. 错误降级策略，确保风控失败不影响核心功能

---

**文档版本**: 1.0  
**最后更新**: 2026-05-19  
**审核状态**: 待用户审核
