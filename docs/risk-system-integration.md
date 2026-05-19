# 风控系统使用指南

## 概述

风控系统已集成到AI推荐流程中，每次推荐买入时自动执行7项风控检查、Kelly仓位计算和动态止损。

## 自动风控

调用 `get_buy_range` 时自动包含：
- **风控检查**：7项规则验证（黑名单、ST股票、仓位限制10%、行业集中度30%、最大回撤20%、日交易次数、流动性）
- **Kelly仓位**：基于历史数据（≥10笔交易）或保守默认值（胜率50%、盈亏比1.5）
- **动态止损**：盈利<5%用固定止损-8%，盈利≥5%用移动止损-10%

### 返回字段

```json
{
  "symbol": "600519",
  "current_price": 1323.0,
  "safe_buy": 1310.84,
  "ideal_buy": 1422.38,
  "stop_loss": 1205.97,
  "risk_check": {
    "passed": false,
    "level": "reject",
    "reason": "超过单股仓位限制 10.0%",
    "violations": [...],
    "adjusted_shares": 0
  },
  "position_advice": {
    "shares": 100,
    "position_pct": 1.42,
    "position_value": 142238.0,
    "method": "kelly",
    "kelly_params": {
      "win_rate": 0.5,
      "profit_loss_ratio": 1.5,
      "data_source": "default"
    }
  },
  "stop_loss_method": "fixed"
}
```

## 独立工具

### check_trade_risk

手动验证交易风险，返回通过/警告/拒绝。

**参数：**
- `symbol`: 股票代码（如 "600519"）
- `action`: 交易方向（"buy" 或 "sell"）
- `price`: 交易价格
- `shares`: 交易股数

**返回：**
- `passed`: 是否通过（boolean）
- `level`: 风险级别（"pass" / "warning" / "reject"）
- `reason`: 原因说明
- `violations`: 违规列表
- `adjusted_shares`: 调整后的建议股数（仓位超限时）

**使用场景：**
1. 用户询问"我能买X吗？"
2. 验证现有持仓风险
3. 手动风控检查

### calculate_position_size

Kelly公式计算科学仓位。

**参数：**
- `symbol`: 股票代码
- `price`: 当前价格
- `signal_strength`: 信号强度（0-1，默认1.0）

**返回：**
- `shares`: 建议股数（100股整数倍）
- `position_pct`: 仓位百分比
- `position_value`: 仓位金额
- `method`: 计算方法（"kelly" / "fixed" / "fallback"）
- `kelly_params`: Kelly参数（胜率、盈亏比、数据来源）

**使用场景：**
1. 用户询问"应该买多少股？"
2. 需要科学仓位计算
3. 信号强度调整：强信号0.8-1.0，弱信号0.5-0.7

### calculate_stop_loss

动态计算止损价。

**参数：**
- `symbol`: 股票代码
- `entry_price`: 入场价格
- `current_price`: 当前价格（可选，自动获取）
- `highest_price`: 最高价格（可选）

**返回：**
- `stop_loss_price`: 止损价格
- `stop_loss_pct`: 止损百分比
- `method`: 止损方法（"fixed" / "trailing"）
- `reason`: 选择原因

**使用场景：**
1. 推荐买入时设置止损
2. 用户询问"止损位应该设在哪？"
3. 审查现有持仓止损

## 配置

风控参数存储在 `.pi-invest/portfolio.db` 的 `risk_config` 表中。

### 默认配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| max_position_pct | 0.10 | 单股最大仓位10% |
| max_sector_pct | 0.30 | 行业最大集中度30% |
| max_drawdown | 0.20 | 最大回撤20% |
| max_daily_trades | 10 | 每日最大交易次数 |
| kelly_fraction | 0.25 | Kelly系数（保守） |
| min_trade_history | 10 | 最小历史交易数 |
| default_win_rate | 0.50 | 默认胜率50% |
| default_profit_loss_ratio | 1.5 | 默认盈亏比1.5 |
| fixed_stop_loss_pct | 0.08 | 固定止损8% |
| trailing_stop_loss_pct | 0.10 | 移动止损10% |
| profit_threshold_for_trailing | 0.05 | 移动止损触发阈值5% |

### 修改配置

```bash
sqlite3 .pi-invest/portfolio.db
```

```sql
-- 修改单股仓位限制为15%
UPDATE risk_config SET value='0.15' WHERE key='max_position_pct';

-- 修改Kelly系数为0.5（更激进）
UPDATE risk_config SET value='0.5' WHERE key='kelly_fraction';

-- 查看所有配置
SELECT key, value, description FROM risk_config;
```

## 风控响应级别

### Pass（通过）
所有风控检查通过，可以执行交易。

### Warning（警告）
存在轻微风险，但允许交易。AI会提示风险点。

### Reject（拒绝）
存在严重风险，拒绝交易。包括：
- ST股票
- 黑名单股票
- 超过最大回撤限制
- 仓位调整后为0股

## 常见问题

**Q: 为什么仓位建议比预期小？**  
A: Kelly公式基于历史胜率和盈亏比计算，保守系数0.25确保风险可控。如果历史交易少于10笔，使用默认值（胜率50%、盈亏比1.5）。

**Q: 如何查看历史风控记录？**  
A: 当前版本暂不记录风控事件。未来版本将添加风控事件日志表。

**Q: ST股票为什么无法买入？**  
A: 风控规则默认禁止ST股票交易，这是保护性规则。ST股票风险极高，不建议普通投资者参与。

**Q: 为什么显示"超过单股仓位限制"但我没有持仓？**  
A: 这是因为 `holdings` 表不存在或为空，系统无法获取当前持仓快照。风控系统会降级处理，但仍会基于总资产计算仓位限制。

**Q: 止损价为什么不是固定的8%？**  
A: 系统使用混合止损策略：
- 盈利<5%：固定止损（入场价-8%）
- 盈利≥5%：移动止损（最高价-10%）
这样既保护本金，又能锁定利润。

**Q: Kelly仓位计算的"信号强度"是什么？**  
A: 信号强度（0-1）用于调整仓位大小：
- 强信号（技术面+基本面都好）：0.8-1.0
- 中等信号（部分指标支持）：0.6-0.8
- 弱信号（仅部分支持）：0.5-0.7
AI会根据分析结果自动选择合适的信号强度。

## 技术架构

### 数据流

```
TypeScript AI
    ↓ (调用工具)
TypeScript Tools (risk-tools.ts)
    ↓ (callPython)
Python Bridge (akshare_bridge.py)
    ↓ (调用)
RiskBridge (risk_bridge.py)
    ↓ (读取)
portfolio.db (risk_config表)
quant DB (历史数据)
```

### 文件结构

```
python/
  ├── risk_bridge.py              # 风控核心逻辑
  └── akshare_bridge.py           # Python桥接层

src/infrastructure/tools/
  ├── invest/
  │   ├── risk-tools.ts           # TypeScript风控工具
  │   └── analysis-tools.ts       # 分析工具（含get_buy_range）
  └── shared/
      └── python-caller-resilient-adapter.ts  # 超时和缓存配置

.pi-invest/
  └── portfolio.db                # 风控配置数据库
      └── risk_config表           # 11个配置参数

quant/quantsys/
  └── risk/                       # Python风控模块（被RiskBridge调用）
```

## 未来改进

1. **风控事件日志**：记录所有风控检查结果到数据库
2. **UI配置界面**：通过Web界面修改风控参数
3. **实时监控**：持仓风险实时监控和告警
4. **回测集成**：风控规则应用到回测系统
5. **自定义规则**：支持用户自定义风控规则

## 相关文档

- [设计文档](./superpowers/specs/2026-05-19-risk-system-integration-design.md)
- [实施计划](./superpowers/plans/2026-05-19-risk-system-integration.md)
