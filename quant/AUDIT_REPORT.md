# 🔍 量化系统生产审计报告

> 审计日期：2026-05-20  
> 审计范围：`quant/` 全部 130+ Python 文件  
> 审计方法：主链路（信号生成→策略→DB→风控）逐文件审查 + 极端场景追踪  
> 目标：找出导致用户真实资金亏损的代码缺陷

---

## 📊 执行摘要

| 级别 | 数量 | 定义 |
|------|------|------|
| 🔴 致命 | 6 | 已触发或极易触发，直接造成资金亏损 |
| 🟠 严重 | 4 | 特定条件下导致亏损或决策错误 |
| 🟡 警告 | 5 | 降低可靠性，间接风险 |
| 🔵 建议 | 4 | 改善健壮性 |

**TOP 3 优先修复：**
1. ST股票未被排除，信号可能推送给退市风险标的
2. 单只股票DB异常导致整个信号生成进程崩溃
3. 布林带/KDJ/RSI策略仍为状态信号，每日重复输出

---

## 🔴 致命缺陷

### 1. ST股票、停牌股未被信号生成排除

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `main()` 第 520 行 |
| **代码** | `symbols = parse_symbols(args.symbols) or db.get_all_symbols(market='A')` |
| **问题** | `get_all_symbols(market='A')` 从 `quant.stocks` 全量拉取，不检查 `is_st=1` 或 `is_suspended=1` |
| **复现** | 任意运行日，`*ST中航(002179)` 等技术形态好的ST股将被扫描并可能生成BUY信号 |
| **亏损场景** | 用户收到BUY信号买入ST股 → 股票退市 → 资金清零 |
| **修复** | `get_all_symbols` 加 `WHERE is_st = FALSE AND is_suspended = FALSE`，或 `generate_signals` 中过滤 |

---

### 2. 单只股票DB查询失败 → 全量信号生成崩溃

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `generate_signals()` 方法，per-symbol 循环 |
| **代码** | `for symbol in symbols:` 内 `factors = self.get_stock_factors(symbol, date)` 直接调用，无 try/except |
| **根因** | `db.py:get_factor_values()` 和 `get_price_on_date()` 都 `raise RuntimeError` |
| **复现** | 任意一只股票在DB中数据不完整 → RuntimeError → 循环终止 → 剩余4900只股票无信号 |
| **亏损场景** | 用户依赖每日信号做决策，某天信号为0 → 以为"市场无机会" → 错过实际存在的买卖点 |
| **修复** | per-symbol loop 加 try/except，单只失败记日志+跳过 |

---

### 3. 布林带突破策略：状态信号，非事件信号

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `strategy_bollinger()` |
| **代码** | `if close <= lower: return BUY` （仅检查当日状态） |
| **问题** | 价格连续3日在下轨下方 → 连续3日输出完全相同的BUY信号 |
| **对比** | 均线/MACD/多头排列策略已修复为事件检测（对比前一日），布林带未同步修复 |
| **亏损场景** | 同一信号重复3次 → 用户以为3个独立信号确认 → 重仓买入 → 实际只是持续超卖 |
| **修复** | 加 `prev_factors` 参数，检测"前一日不在下轨 → 今日在下轨"的穿越事件 |

---

### 4. KDJ策略：同上的状态信号问题

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `strategy_kdj()` |
| **代码** | `if k < 20 and d < 20: return BUY` |
| **问题** | KDJ在20以下可能持续多日，每日重复生成BUY |
| **修复** | 检测 K 刚跌破 20 的穿越事件（前一日 K ≥ 20，今日 K < 20） |

---

### 5. 固定止损默认5%，与Agent规则规定的8%不一致

| 项目 | 内容 |
|------|------|
| **位置** | `quantsys/risk/stop_loss.py` 第 17 行 `StopLossConfig.fixed_pct` |
| **默认值** | 0.05 (5%) |
| **规则要求** | Agent 行为准则规定 "跌破买入价 8% → 硬止损，不犹豫" |
| **亏损场景** | 用户信任系统生成的止损价 → 实际止损线比规则预期松3% → 可能多亏3000元（10万仓位） |
| **修复** | `fixed_pct = 0.08` |

---

### 6. `replace_trading_signals_for_date` 非原子操作

| 项目 | 内容 |
|------|------|
| **位置** | `quantsys/data/db.py` → `replace_trading_signals_for_date()` 第 1129 行 |
| **逻辑** | `DELETE FROM trading_signals WHERE signal_date = %s` → ⏸ → `INSERT` |
| **问题** | DELETE 和 INSERT 之间无事务包裹。进程崩溃或DB错误 → 当日信号全部丢失 |
| **亏损场景** | 用户依赖数据库中的信号列表 → 某天信号清空 → 无决策依据 |
| **修复** | 整个方法用 `BEGIN/COMMIT` 包裹，或使用 `UPSERT` (PostgreSQL 的 `ON CONFLICT`) |

---

## 🟠 严重缺陷

### 7. `_calculate_holding_days` 静默异常吞噬 → 时间止损永久失效

| 项目 | 内容 |
|------|------|
| **位置** | `quantsys/risk/stop_loss.py` 第 159 行 |
| **代码** | `except: return 0` |
| **影响** | 日期解析失败 → 持仓天数=0 → `0 >= max_holding_days(60)` 永远False → 时间止损永不触发 |
| **修复** | 记录日志并返回一个保守的大值（如 max_holding_days），触发止损保护 |

---

### 8. 放量突破策略：VR=None 时静默跳过量能确认

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `strategy_volume_breakout()` |
| **代码** | `volume_amplified = vr and vr > 1.5` |
| **问题** | `vr is None` 时 `volume_amplified = None`（伪假），带量突破的BUY信号不触发。正确逻辑应为：无VR数据时不发信号，而非静默跳过 |
| **修复** | `if vr is None: return None` 显式处理缺失数据 |

---

### 9. RSI阈值不一致：条件用 `rsi < 35`，日志写 `< 30`

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `strategy_rsi_reversal()` |
| **代码** | `if rsi < 35:` 但 `reason = f'RSI超卖 ({rsi:.2f} < 30)'` |
| **影响** | RSI=32 触发BUY，但日志显示 `< 30`，用户困惑。阈值意义混淆 |
| **修复** | 统一为 `rsi < 30` 或修正 reason 字符串 |

---

### 10. 前日交易日获取使用原始 SQLite fallback

| 项目 | 内容 |
|------|------|
| **位置** | `scripts/generate_signals.py` → `get_prev_trading_date()` |
| **代码** | 先调 `db.get_prev_trading_date()`，失败后回退到直接 `sqlite3.connect()` |
| **问题** | PG环境下到SQLite的fallback路径永远不会成功（PG下无SQLite文件）。且硬编码了`daily_klines`表名 |
| **修复** | DB类统一提供 `get_prev_trading_date()`，删除fallback逻辑 |

---

## 🟡 警告

### 11. 4处裸 `except:` 吞没致命异常

| 文件 | 行号 | 风险 |
|------|------|------|
| `factors/cache.py` | 127 | 缓存失败 → 静默 |
| `backtest/engine.py` | 408 | 回测数据异常 → 静默 |
| `ml/features/feature_engineering.py` | 174 | 特征工程崩溃 → 静默 |
| `risk/stop_loss.py` | 159 | 日期计算失败 → 静默（已列为严重） |

---

### 12. `signal.json` 写入路径不一致

| 项目 | 内容 |
|------|------|
| **写入** | `quant/.pi-invest/signals.json`（`generate_signals.py` 中 `output_dir` 计算为 quant 目录下） |
| **预期读取** | `quantsys/cli/` handler 可能从项目根 `.pi-invest/signals.json` 读取 |
| **风险** | 写入和读取不同路径 → Agent 读不到信号 |
| **修复** | 统一路径到项目根 `.pi-invest/signals.json` |

---

### 13. 信号不包含仓位建议

| 项目 | 内容 |
|------|------|
| **现状** | 信号仅含 `{symbol, signal(BUY/SELL), confidence, price, reason}` |
| **缺失** | 无建议股数、无仓位占比、无止损价 |
| **影响** | 用户拿到信号后需自行判断买多少、哪里止损 → 可能仓位失控 |
| **修复** | 计算 Kelly 仓位 + 止损价后纳入信号输出 |

---

### 14. 策略参数全量硬编码

| 参数 | 硬编码值 | 影响 |
|------|----------|------|
| MA 快慢线 | 5/20 | 不同市场风格（震荡/趋势）需要自适应 |
| 布林带周期/倍数 | 20/2.0 | 波动率变化时固定参数失效 |
| 止损比例 | 5%（应为8%） | 已列为致命 |
| 止盈比例 | 15% | 无差异化 |
| RSI阈值 | 35/70 | 强趋势市场可能需要 20/80 |

---

### 15. `_is_limit_up` 使用固定 0.099 阈值

| 项目 | 内容 |
|------|------|
| **位置** | `quantsys/backtest/engine.py` 第 225 行 |
| **问题** | 科创板/创业板 20% 涨跌停，主板 ¥1 步进可致 10.02% 涨停 |
| **修复** | 从 `stocks` 表读取所属板块动态计算阈值 |

---

## 🔵 建议

16. **无 A/B 实验框架** — 无法对比新旧策略参数效果
17. **`stock_analytics.py` 只用 `stocks` 表宽字段** — RSI/momentum 在 `factor_values` KV 表中，评分只有 PE/PB 两个因子有值
18. **ML 模型特征无版本控制** — 改变特征工程后旧模型不可用，无检测
19. **`confidence_calibration` 全局上限 0.85** — 理论上最佳信号也无法突破，可考虑动态上限

---

## 🔧 修复优先级路线图

### Phase 1（立即修复，今天）
- [ ] **致命1**: `get_all_symbols` 加 `is_st=FALSE` 过滤
- [ ] **致命2**: `generate_signals` per-symbol loop 加 try/except
- [ ] **致命5**: `StopLossConfig.fixed_pct` 改为 0.08

### Phase 2（本周内）
- [ ] **致命3**: `strategy_bollinger` 改为事件检测
- [ ] **致命4**: `strategy_kdj` 改为事件检测
- [ ] **致命6**: `replace_trading_signals_for_date` 加事务包裹
- [ ] **严重7**: `_calculate_holding_days` bare except 修复

### Phase 3（本月内）
- [ ] **严重8-10**: VR=None、RSI阈值、前日交易日fallback 修复
- [ ] **警告11-15**: bare except、路径一致、仓位建议、参数化、涨跌停阈值

---

*审计工具：手工代码审查 + 执行路径追踪 | 审查者：AI 量化审计系统*
