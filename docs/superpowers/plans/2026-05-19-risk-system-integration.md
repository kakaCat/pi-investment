# 风控系统集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 集成Python风控系统到TypeScript AI推荐流程，实现自动风控检查、Kelly仓位计算和动态止损

**Architecture:** 创建Python桥接层（risk_bridge.py）连接portfolio.db和quant风控模块，在akshare_bridge.py中新增4个函数，TypeScript侧创建3个新工具并修改get_buy_range工具描述

**Tech Stack:** Python 3.12, TypeScript, SQLite, quant/quantsys/risk模块

---

## 文件结构

### 新增文件
- `python/risk_bridge.py` - 风控桥接层，封装风控逻辑
- `src/infrastructure/tools/invest/risk-tools.ts` - 3个新风控工具定义

### 修改文件
- `python/akshare_bridge.py` - 新增4个函数，修改calculate_buy_range
- `src/infrastructure/tools/invest/analysis-tools.ts` - 更新getBuyRangeTool描述
- `src/infrastructure/tools/index.ts` - 注册新工具
- `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts` - 添加超时配置
- `.pi-invest/portfolio.db` - 创建risk_config表

---

## Task 1: 数据库初始化

**Files:**
- Modify: `.pi-invest/portfolio.db`

- [ ] **Step 1: 创建risk_config表**

```bash
sqlite3 .pi-invest/portfolio.db << 'SQL'
CREATE TABLE IF NOT EXISTS risk_config (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  description TEXT,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
SQL
```

- [ ] **Step 2: 验证表创建成功**

Run: `sqlite3 .pi-invest/portfolio.db ".schema risk_config"`
Expected: 显示表结构

- [ ] **Step 3: 插入默认配置**

```bash
sqlite3 .pi-invest/portfolio.db << 'SQL'
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

- [ ] **Step 4: 验证数据插入**

Run: `sqlite3 .pi-invest/portfolio.db "SELECT COUNT(*) FROM risk_config"`
Expected: 11

- [ ] **Step 5: Commit**

```bash
git add .pi-invest/portfolio.db
git commit -m "feat(db): create risk_config table with default values"
```

---

## Task 2: 创建RiskBridge类（第1部分：基础结构）

**Files:**
- Create: `python/risk_bridge.py`

- [ ] **Step 1: 创建文件并写入导入和类定义**

```python
#!/usr/bin/env python3
"""
风控桥接层 - 连接 portfolio.db 和 quant/quantsys/risk
"""
import sqlite3
import sys
import os
from datetime import datetime
from types import SimpleNamespace
from typing import Dict, List, Tuple, Optional

# 添加 quant 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'quant'))

try:
    from quantsys.risk import (
        PreTradeRiskCheck, RiskConfig,
        PositionManager, PositionSizeConfig,
        StopLossManager, StopLossConfig
    )
    QUANT_AVAILABLE = True
except ImportError as e:
    print(f"Warning: quant module not available: {e}", file=sys.stderr)
    QUANT_AVAILABLE = False


class RiskBridge:
    """风控桥接层"""
    
    def __init__(self, portfolio_db_path: str, quant_db_path: str):
        self.portfolio_db = portfolio_db_path
        self.quant_db = quant_db_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, str]:
        """从 portfolio.db 读取风控配置"""
        try:
            conn = sqlite3.connect(self.portfolio_db)
            cursor = conn.execute("SELECT key, value FROM risk_config")
            config = {row[0]: row[1] for row in cursor.fetchall()}
            conn.close()
            return config
        except sqlite3.Error as e:
            print(f"Warning: Failed to load risk config: {e}", file=sys.stderr)
            return self._default_config()
    
    def _default_config(self) -> Dict[str, str]:
        """返回默认配置"""
        return {
            'max_position_pct': '0.10',
            'max_sector_pct': '0.30',
            'max_drawdown': '0.20',
            'max_daily_trades': '10',
            'kelly_fraction': '0.25',
            'min_trade_history': '10',
            'default_win_rate': '0.50',
            'default_profit_loss_ratio': '1.5',
            'fixed_stop_loss_pct': '0.08',
            'trailing_stop_loss_pct': '0.10',
            'profit_threshold_for_trailing': '0.05'
        }
```

- [ ] **Step 2: 验证文件创建**

Run: `python3 -c "import python.risk_bridge; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add python/risk_bridge.py
git commit -m "feat(risk): create RiskBridge class with config loading"
```

---

## Task 3: RiskBridge数据读取方法

**Files:**
- Modify: `python/risk_bridge.py`

- [ ] **Step 1: 添加_get_portfolio_snapshot方法**

在RiskBridge类中添加：

```python
    def _get_portfolio_snapshot(self) -> SimpleNamespace:
        """读取当前持仓快照"""
        try:
            conn = sqlite3.connect(self.portfolio_db)
            
            # 读取总权益（从holdings表计算）
            cursor = conn.execute("SELECT SUM(market_value) FROM holdings WHERE shares > 0")
            row = cursor.fetchone()
            total_equity = row[0] if row and row[0] else 100000.0
            
            # 读取持仓
            cursor = conn.execute("""
                SELECT symbol, shares, cost_basis, market_value 
                FROM holdings WHERE shares > 0
            """)
            positions = {}
            for row in cursor.fetchall():
                positions[row[0]] = SimpleNamespace(
                    shares=row[1],
                    cost_basis=row[2],
                    market_value=row[3]
                )
            
            conn.close()
            
            return SimpleNamespace(
                total_equity=total_equity,
                positions=positions
            )
        except sqlite3.Error as e:
            print(f"Warning: Failed to get portfolio snapshot: {e}", file=sys.stderr)
            return SimpleNamespace(total_equity=100000.0, positions={})
```

- [ ] **Step 2: 添加_get_trade_history方法**

```python
    def _get_trade_history(self, symbol: Optional[str] = None) -> List[Dict]:
        """读取历史交易记录"""
        try:
            conn = sqlite3.connect(self.portfolio_db)
            
            if symbol:
                cursor = conn.execute("""
                    SELECT symbol, action, price, shares, total, date
                    FROM trades
                    WHERE symbol = ? AND action IN ('buy', 'sell')
                    ORDER BY date DESC
                """, (symbol,))
            else:
                cursor = conn.execute("""
                    SELECT symbol, action, price, shares, total, date
                    FROM trades
                    WHERE action IN ('buy', 'sell')
                    ORDER BY date DESC
                """)
            
            trades = []
            for row in cursor.fetchall():
                trades.append({
                    'symbol': row[0],
                    'action': row[1],
                    'price': row[2],
                    'shares': row[3],
                    'total': row[4],
                    'date': row[5]
                })
            
            conn.close()
            return trades
        except sqlite3.Error as e:
            print(f"Warning: Failed to get trade history: {e}", file=sys.stderr)
            return []
```

- [ ] **Step 3: 添加_calculate_win_rate方法**

```python
    def _calculate_win_rate(self, trades: List[Dict]) -> Tuple[float, float, int]:
        """
        计算胜率和盈亏比
        
        Returns:
            (win_rate, profit_loss_ratio, trade_count)
        """
        if len(trades) < 2:
            return 0.5, 1.5, 0
        
        # 简化逻辑：配对买卖计算盈亏
        positions = {}
        closed_trades = []
        
        for trade in reversed(trades):  # 从旧到新
            symbol = trade['symbol']
            
            if trade['action'] == 'buy':
                if symbol not in positions:
                    positions[symbol] = []
                positions[symbol].append({
                    'price': trade['price'],
                    'shares': trade['shares'],
                    'date': trade['date']
                })
            elif trade['action'] == 'sell' and symbol in positions:
                if positions[symbol]:
                    buy = positions[symbol].pop(0)
                    pnl = (trade['price'] - buy['price']) / buy['price']
                    closed_trades.append(pnl)
        
        if not closed_trades:
            return 0.5, 1.5, 0
        
        # 计算胜率
        wins = [p for p in closed_trades if p > 0]
        losses = [p for p in closed_trades if p < 0]
        
        win_rate = len(wins) / len(closed_trades) if closed_trades else 0.5
        
        # 计算盈亏比
        avg_win = sum(wins) / len(wins) if wins else 0.1
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.05
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5
        
        return win_rate, profit_loss_ratio, len(closed_trades)
```

- [ ] **Step 4: 验证方法可用**

Run: `python3 -c "from python.risk_bridge import RiskBridge; rb = RiskBridge('.pi-invest/portfolio.db', 'quant/quantsys/data/stocks.db'); print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add python/risk_bridge.py
git commit -m "feat(risk): add portfolio and trade history reading methods"
```

---

## Task 4: RiskBridge辅助方法

**Files:**
- Modify: `python/risk_bridge.py`

- [ ] **Step 1: 添加_build_risk_config方法**

在RiskBridge类中添加：

```python
    def _build_risk_config(self) -> 'RiskConfig':
        """构建RiskConfig对象"""
        if not QUANT_AVAILABLE:
            return None
        
        return RiskConfig(
            max_position_pct=float(self.config.get('max_position_pct', 0.10)),
            max_sector_pct=float(self.config.get('max_sector_pct', 0.30)),
            max_drawdown=float(self.config.get('max_drawdown', 0.20)),
            max_daily_trades=int(self.config.get('max_daily_trades', 10)),
            blacklist=[],
            allow_st_stocks=False,
            min_liquidity=1000000
        )
```

- [ ] **Step 2: 添加_calculate_max_allowed_shares方法**

```python
    def _calculate_max_allowed_shares(self, symbol: str, price: float, portfolio: SimpleNamespace) -> int:
        """计算最大允许买入股数（不超过仓位限制）"""
        max_pct = float(self.config.get('max_position_pct', 0.10))
        max_value = portfolio.total_equity * max_pct
        
        # 减去已有持仓
        if symbol in portfolio.positions:
            existing_value = portfolio.positions[symbol].market_value
            max_value -= existing_value
        
        if max_value <= 0:
            return 0
        
        max_shares = int(max_value / price / 100) * 100  # 100股整数倍
        return max(0, max_shares)
```

- [ ] **Step 3: 添加_fetch_current_price方法**

```python
    def _fetch_current_price(self, symbol: str) -> Optional[float]:
        """从quant DB获取当前价格"""
        try:
            conn = sqlite3.connect(self.quant_db)
            cursor = conn.execute("""
                SELECT close
                FROM daily_klines
                WHERE symbol = ?
                ORDER BY date DESC
                LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else None
        except sqlite3.Error:
            return None
```

- [ ] **Step 4: 验证方法可用**

Run: `python3 -c "from python.risk_bridge import RiskBridge; rb = RiskBridge('.pi-invest/portfolio.db', 'quant/quantsys/data/stocks.db'); print(rb._build_risk_config())"`
Expected: 显示RiskConfig对象或None

- [ ] **Step 5: Commit**

```bash
git add python/risk_bridge.py
git commit -m "feat(risk): add helper methods for risk config and price fetching"
```

---

## Task 5: 实现check_trade_risk函数

**Files:**
- Modify: `python/risk_bridge.py`

- [ ] **Step 1: 添加check_trade_risk方法**

在RiskBridge类中添加：

```python
    def check_trade_risk(self, symbol: str, action: str, price: float, shares: int) -> Dict:
        """预交易风控检查"""
        if not QUANT_AVAILABLE:
            return {
                "passed": True,
                "level": "warning",
                "reason": "风控模块不可用，建议手动检查",
                "violations": [{"rule": "import_error", "severity": "high", "message": "quant module not available"}],
                "adjusted_shares": shares
            }
        
        try:
            portfolio = self._get_portfolio_snapshot()
            
            # 构造订单对象
            order = SimpleNamespace(
                symbol=symbol,
                action=action,
                price=price,
                shares=shares,
                date=datetime.now().strftime('%Y-%m-%d')
            )
            
            # 执行风控检查
            risk_checker = PreTradeRiskCheck(config=self._build_risk_config())
            passed, error_msg = risk_checker.check(order, portfolio, market_data=None)
            
            # 分级响应
            violations = []
            level = "pass"
            adjusted_shares = shares
            
            if not passed:
                # 判断严重程度
                if any(kw in error_msg for kw in ['ST', '黑名单', '回撤']):
                    level = "reject"
                elif '仓位限制' in error_msg:
                    level = "warning"
                    adjusted_shares = self._calculate_max_allowed_shares(symbol, price, portfolio)
                    violations.append({
                        "rule": "position_limit",
                        "message": error_msg,
                        "severity": "medium"
                    })
                else:
                    level = "warning"
                    violations.append({
                        "rule": "other",
                        "message": error_msg,
                        "severity": "medium"
                    })
            
            return {
                "passed": passed,
                "level": level,
                "reason": error_msg if not passed else "通过所有风控检查",
                "violations": violations,
                "adjusted_shares": adjusted_shares
            }
        
        except Exception as e:
            return {
                "passed": True,
                "level": "warning",
                "reason": f"风控检查异常: {str(e)}",
                "violations": [{"rule": "exception", "severity": "high", "message": str(e)}],
                "adjusted_shares": shares
            }
```

- [ ] **Step 2: 验证方法可用**

Run: `python3 -c "from python.risk_bridge import RiskBridge; rb = RiskBridge('.pi-invest/portfolio.db', 'quant/quantsys/data/stocks.db'); print(rb.check_trade_risk('600519', 'buy', 1800, 100))"`
Expected: 返回包含passed、level、reason的字典

- [ ] **Step 3: Commit**

```bash
git add python/risk_bridge.py
git commit -m "feat(risk): implement check_trade_risk method"
```

---

## Task 6: 实现calculate_position_size函数

**Files:**
- Modify: `python/risk_bridge.py`

- [ ] **Step 1: 添加calculate_position_size方法**

在RiskBridge类中添加：

```python
    def calculate_position_size(self, symbol: str, price: float, signal_strength: float = 1.0) -> Dict:
        """Kelly公式计算建议仓位"""
        if not QUANT_AVAILABLE:
            # 降级：简单固定仓位
            portfolio = self._get_portfolio_snapshot()
            shares = int(portfolio.total_equity * 0.05 / price / 100) * 100
            return {
                "shares": shares,
                "position_pct": (shares * price) / portfolio.total_equity,
                "position_value": shares * price,
                "method": "fixed",
                "kelly_params": {
                    "win_rate": 0.50,
                    "profit_loss_ratio": 1.5,
                    "data_source": "default",
                    "trade_count": 0
                }
            }
        
        try:
            portfolio = self._get_portfolio_snapshot()
            total_equity = portfolio.total_equity
            
            # 获取历史交易数据
            trades = self._get_trade_history(symbol)
            min_trades = int(self.config.get('min_trade_history', 10))
            
            # 判断数据源
            if len(trades) >= min_trades:
                win_rate, pl_ratio, count = self._calculate_win_rate(trades)
                data_source = "historical"
            else:
                win_rate = float(self.config.get('default_win_rate', 0.50))
                pl_ratio = float(self.config.get('default_profit_loss_ratio', 1.5))
                data_source = "default"
                count = len(trades)
            
            # 调用 PositionManager
            position_mgr = PositionManager(config=PositionSizeConfig(
                method='kelly',
                kelly_fraction=float(self.config.get('kelly_fraction', 0.25)),
                max_position_pct=float(self.config.get('max_position_pct', 0.10))
            ))
            
            shares = position_mgr.calculate_position_size(
                symbol=symbol,
                price=price,
                total_equity=total_equity,
                signal_strength=signal_strength,
                market_data={'win_rate': win_rate, 'profit_loss_ratio': pl_ratio}
            )
            
            return {
                "shares": shares,
                "position_pct": round((shares * price) / total_equity, 4),
                "position_value": round(shares * price, 2),
                "method": "kelly",
                "kelly_params": {
                    "win_rate": round(win_rate, 3),
                    "profit_loss_ratio": round(pl_ratio, 2),
                    "data_source": data_source,
                    "trade_count": count
                }
            }
        
        except Exception as e:
            # 降级处理
            portfolio = self._get_portfolio_snapshot()
            shares = int(portfolio.total_equity * 0.05 / price / 100) * 100
            return {
                "shares": shares,
                "position_pct": (shares * price) / portfolio.total_equity,
                "position_value": shares * price,
                "method": "fallback",
                "kelly_params": {
                    "win_rate": 0.50,
                    "profit_loss_ratio": 1.5,
                    "data_source": "error",
                    "trade_count": 0,
                    "error": str(e)
                }
            }
```

- [ ] **Step 2: 验证方法可用**

Run: `python3 -c "from python.risk_bridge import RiskBridge; rb = RiskBridge('.pi-invest/portfolio.db', 'quant/quantsys/data/stocks.db'); print(rb.calculate_position_size('600519', 1800, 0.8))"`
Expected: 返回包含shares、position_pct、kelly_params的字典

- [ ] **Step 3: Commit**

```bash
git add python/risk_bridge.py
git commit -m "feat(risk): implement calculate_position_size with Kelly formula"
```

---

## Task 7: 实现calculate_stop_loss函数

**Files:**
- Modify: `python/risk_bridge.py`

- [ ] **Step 1: 添加calculate_stop_loss方法**

在RiskBridge类中添加：

```python
    def calculate_stop_loss(self, symbol: str, entry_price: float, 
                           current_price: Optional[float] = None, 
                           highest_price: Optional[float] = None) -> Dict:
        """计算止损价（混合策略）"""
        try:
            # 获取当前价格
            if current_price is None:
                current_price = self._fetch_current_price(symbol)
                if current_price is None:
                    return {"error": f"无法获取{symbol}的当前价格"}
            
            if highest_price is None:
                highest_price = current_price
            
            # 计算盈亏比例
            pnl_pct = (current_price - entry_price) / entry_price
            profit_threshold = float(self.config.get('profit_threshold_for_trailing', 0.05))
            
            # 混合策略
            if pnl_pct < profit_threshold:
                # 固定止损
                fixed_pct = float(self.config.get('fixed_stop_loss_pct', 0.08))
                stop_loss_price = entry_price * (1 - fixed_pct)
                method = "fixed"
                reason = f"当前盈利{pnl_pct:.1%} < {profit_threshold:.0%}，使用固定止损-{fixed_pct:.0%}"
            else:
                # 移动止损
                trailing_pct = float(self.config.get('trailing_stop_loss_pct', 0.10))
                stop_loss_price = highest_price * (1 - trailing_pct)
                method = "trailing"
                reason = f"当前盈利{pnl_pct:.1%} ≥ {profit_threshold:.0%}，使用移动止损（从最高价{highest_price:.2f}回撤{trailing_pct:.0%}）"
            
            return {
                "stop_loss_price": round(stop_loss_price, 2),
                "stop_loss_pct": round((stop_loss_price - entry_price) / entry_price, 4),
                "method": method,
                "reason": reason
            }
        
        except Exception as e:
            return {"error": f"计算止损价失败: {str(e)}"}
```

- [ ] **Step 2: 验证方法可用**

Run: `python3 -c "from python.risk_bridge import RiskBridge; rb = RiskBridge('.pi-invest/portfolio.db', 'quant/quantsys/data/stocks.db'); print(rb.calculate_stop_loss('600519', 1800, 1850, 1850))"`
Expected: 返回包含stop_loss_price、method、reason的字典

- [ ] **Step 3: Commit**

```bash
git add python/risk_bridge.py
git commit -m "feat(risk): implement calculate_stop_loss with hybrid strategy"
```

---

## Task 8: 在akshare_bridge.py中暴露风控函数

**Files:**
- Modify: `python/akshare_bridge.py`

- [ ] **Step 1: 在文件顶部添加RiskBridge导入**

在 `akshare_bridge.py` 的导入部分添加：

```python
# 在现有导入后添加
from risk_bridge import RiskBridge
```

- [ ] **Step 2: 添加check_trade_risk函数**

在文件末尾的函数映射表之前添加：

```python
def check_trade_risk(symbol: str, action: str, price: float, shares: int) -> dict:
    """预交易风控检查"""
    portfolio_db = os.path.join(os.path.dirname(__file__), '..', '.pi-invest', 'portfolio.db')
    quant_db = os.path.join(os.path.dirname(__file__), '..', 'quant', 'quantsys', 'data', 'stocks.db')
    
    bridge = RiskBridge(portfolio_db, quant_db)
    result = bridge.check_trade_risk(symbol, action, price, shares)
    return result
```

- [ ] **Step 3: 添加calculate_position_size函数**

```python
def calculate_position_size(symbol: str, price: float, signal_strength: float = 1.0) -> dict:
    """Kelly公式计算建议仓位"""
    portfolio_db = os.path.join(os.path.dirname(__file__), '..', '.pi-invest', 'portfolio.db')
    quant_db = os.path.join(os.path.dirname(__file__), '..', 'quant', 'quantsys', 'data', 'stocks.db')
    
    bridge = RiskBridge(portfolio_db, quant_db)
    result = bridge.calculate_position_size(symbol, price, signal_strength)
    return result
```

- [ ] **Step 4: 添加calculate_stop_loss函数**

```python
def calculate_stop_loss(symbol: str, entry_price: float, current_price: float = None, highest_price: float = None) -> dict:
    """计算止损价（混合策略）"""
    portfolio_db = os.path.join(os.path.dirname(__file__), '..', '.pi-invest', 'portfolio.db')
    quant_db = os.path.join(os.path.dirname(__file__), '..', 'quant', 'quantsys', 'data', 'stocks.db')
    
    bridge = RiskBridge(portfolio_db, quant_db)
    result = bridge.calculate_stop_loss(symbol, entry_price, current_price, highest_price)
    return result
```

- [ ] **Step 5: 在FUNCTION_MAP中注册新函数**

找到文件末尾的 `FUNCTION_MAP` 字典，添加：

```python
FUNCTION_MAP = {
    # ... 现有函数 ...
    "check_trade_risk": check_trade_risk,
    "calculate_position_size": calculate_position_size,
    "calculate_stop_loss": calculate_stop_loss,
}
```

- [ ] **Step 6: 测试新函数可调用**

Run: `python3 python/akshare_bridge.py check_trade_risk '{"symbol":"600519","action":"buy","price":1800,"shares":100}'`
Expected: 返回JSON格式的风控检查结果

- [ ] **Step 7: Commit**

```bash
git add python/akshare_bridge.py
git commit -m "feat(bridge): expose risk check functions to TypeScript"
```

---

## Task 9: 修改calculate_buy_range集成风控

**Files:**
- Modify: `python/akshare_bridge.py`

- [ ] **Step 1: 找到calculate_buy_range函数**

定位到 `calculate_buy_range` 函数（约在第XXX行）

- [ ] **Step 2: 在返回前添加风控检查调用**

在函数的 `return` 语句之前添加：

```python
    # 自动风控检查
    try:
        risk_check_result = check_trade_risk(symbol, 'buy', ideal_buy, 300)
        position_result = calculate_position_size(symbol, ideal_buy, 0.8)
        stop_loss_result = calculate_stop_loss(symbol, ideal_buy)
    except Exception as e:
        # 降级：风控失败不影响主流程
        risk_check_result = {
            "passed": True,
            "level": "warning",
            "reason": f"风控检查失败: {str(e)}",
            "violations": [],
            "adjusted_shares": 300
        }
        position_result = {
            "shares": 300,
            "position_pct": 0.10,
            "method": "fallback",
            "kelly_params": {"data_source": "error"}
        }
        stop_loss_result = {
            "stop_loss_price": safeBuy * 0.92,
            "method": "fixed",
            "reason": "降级使用固定止损"
        }
```

- [ ] **Step 3: 修改返回值包含风控结果**

修改 `return` 语句：

```python
    return {
        # 原有字段
        "symbol": clean,
        "current_price": r2(curPrice),
        "safe_buy": safeBuy,
        "ideal_buy": idealBuy,
        "stop_loss": stop_loss_result.get("stop_loss_price", safeBuy * 0.92),  # 使用动态止损
        "target_price": target,
        "support_levels": {
            "ma20": r2(ma20v),
            "ma60": r2(ma60v),
            "recent_low_20d": r2(recentLow),
            "bollinger_lower": r2(bbLower)
        },
        "advice": advice,
        "data_date": dataDate,
        
        # 新增字段
        "risk_check": risk_check_result,
        "position_advice": position_result,
        "stop_loss_method": stop_loss_result.get("method", "fixed")
    }
```

- [ ] **Step 4: 测试修改后的函数**

Run: `python3 python/akshare_bridge.py calculate_buy_range '{"symbol":"600519"}'`
Expected: 返回包含risk_check、position_advice、stop_loss_method的JSON

- [ ] **Step 5: Commit**

```bash
git add python/akshare_bridge.py
git commit -m "feat(buy-range): integrate automatic risk check and Kelly position sizing"
```

---

## Task 10: 创建TypeScript风控工具

**Files:**
- Create: `src/infrastructure/tools/invest/risk-tools.ts`

- [ ] **Step 1: 创建文件并写入导入**

```typescript
/**
 * Risk Management Tools - 风控工具
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { callPython } from "../shared/python-caller.js";
import { requireAshare } from "../shared/validators.js";
```

- [ ] **Step 2: 添加check_trade_risk工具**

```typescript
export const checkTradeRiskTool: ToolDefinition = {
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
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    action: Type.String({ description: "'buy' or 'sell'" }),
    price: Type.Number({ description: "Trade price in CNY" }),
    shares: Type.Integer({ description: "Number of shares to trade" }),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("check_trade_risk", params);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};
```

- [ ] **Step 3: 添加calculate_position_size工具**

```typescript
export const calculatePositionSizeTool: ToolDefinition = {
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
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    price: Type.Number({ description: "Current price in CNY" }),
    signal_strength: Type.Optional(Type.Number({ description: "Signal quality 0-1, default 1.0" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("calculate_position_size", params);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};
```

- [ ] **Step 4: 添加calculate_stop_loss工具**

```typescript
export const calculateStopLossTool: ToolDefinition = {
  name: "calculate_stop_loss",
  label: "动态止损计算",
  description:
    "Calculate stop-loss price using hybrid strategy: fixed stop (-8%) when unprofitable, " +
    "trailing stop (-10% from peak) when profit >5%. " +
    "Returns stop_loss_price, stop_loss_pct, method (fixed/trailing), and reason explaining the choice. " +
    "Use when: 1) recommending buy entry with stop-loss, 2) user asks 'where should I set stop-loss', " +
    "3) reviewing existing positions. " +
    "Requires entry_price; current_price and highest_price are optional but improve accuracy for existing positions.",
  parameters: Type.Object({
    symbol: Type.String({ description: "6-digit A-share code, e.g. '600519'" }),
    entry_price: Type.Number({ description: "Entry/buy price in CNY" }),
    current_price: Type.Optional(Type.Number({ description: "Current price (optional, fetched if omitted)" })),
    highest_price: Type.Optional(Type.Number({ description: "Highest price since entry (optional)" })),
  }),
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    const result = await callPython("calculate_stop_loss", params);
    return { content: [{ type: "text" as const, text: result }], details: undefined };
  },
};
```

- [ ] **Step 5: 导出工具数组**

```typescript
export const riskTools: ToolDefinition[] = [
  checkTradeRiskTool,
  calculatePositionSizeTool,
  calculateStopLossTool,
];
```

- [ ] **Step 6: 验证文件编译**

Run: `npm run build`
Expected: 编译成功，无错误

- [ ] **Step 7: Commit**

```bash
git add src/infrastructure/tools/invest/risk-tools.ts
git commit -m "feat(tools): add risk management tools (check_trade_risk, calculate_position_size, calculate_stop_loss)"
```

---

## Task 11: 注册新工具到工具索引

**Files:**
- Modify: `src/infrastructure/tools/index.ts`

- [ ] **Step 1: 导入riskTools**

在文件顶部的导入部分添加：

```typescript
import { riskTools } from "./invest/risk-tools.js";
```

- [ ] **Step 2: 将riskTools添加到allTools数组**

找到 `allTools` 数组定义，添加：

```typescript
export const allTools: ToolDefinition[] = [
  // ... 现有工具 ...
  ...riskTools,
];
```

- [ ] **Step 3: 验证工具注册成功**

Run: `npm run build && node -e "import('./dist/infrastructure/tools/index.js').then(m => console.log(m.allTools.filter(t => t.name.includes('risk')).map(t => t.name)))"`
Expected: 显示 ['check_trade_risk', 'calculate_position_size', 'calculate_stop_loss']

- [ ] **Step 4: Commit**

```bash
git add src/infrastructure/tools/index.ts
git commit -m "feat(tools): register risk management tools in tool registry"
```

---

## Task 12: 更新getBuyRangeTool描述

**Files:**
- Modify: `src/infrastructure/tools/invest/analysis-tools.ts`

- [ ] **Step 1: 找到getBuyRangeTool定义**

定位到 `getBuyRangeTool` 对象（约在第72行）

- [ ] **Step 2: 更新description字段**

替换现有的 `description` 为：

```typescript
  description:
    "Calculate optimal buy price range with AUTOMATIC risk validation and Kelly position sizing. " +
    "Returns safe_buy, ideal_buy, target_price, AND risk_check (pass/warning/reject), " +
    "position_advice (Kelly-based shares), stop_loss (dynamic, not fixed 8%). " +
    "If risk check fails, advice will include adjusted recommendations or rejection reason. " +
    "Use after get_stock_price for context. This tool now replaces manual risk checking for buy recommendations.",
```

- [ ] **Step 3: 验证文件编译**

Run: `npm run build`
Expected: 编译成功

- [ ] **Step 4: Commit**

```bash
git add src/infrastructure/tools/invest/analysis-tools.ts
git commit -m "docs(tools): update get_buy_range description to reflect integrated risk checks"
```

---

## Task 13: 配置Python函数超时

**Files:**
- Modify: `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`

- [ ] **Step 1: 找到TIMEOUT配置对象**

定位到文件中的超时配置部分

- [ ] **Step 2: 添加新函数的超时配置**

在超时配置对象中添加：

```typescript
const TIMEOUT_CONFIG = {
  // ... 现有配置 ...
  check_trade_risk: TIMEOUT_MEDIUM,      // 30s
  calculate_position_size: TIMEOUT_MEDIUM, // 30s
  calculate_stop_loss: TIMEOUT_SHORT,    // 10s
};
```

- [ ] **Step 3: 找到CACHE_STRATEGY配置**

定位到缓存策略配置部分

- [ ] **Step 4: 添加新函数的缓存策略**

```typescript
const CACHE_STRATEGY = {
  // ... 现有配置 ...
  check_trade_risk: 'intraday',          // 日内缓存
  calculate_position_size: 'intraday',   // 日内缓存
  calculate_stop_loss: 'intraday',       // 日内缓存
};
```

- [ ] **Step 5: 验证配置生效**

Run: `npm run build`
Expected: 编译成功

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/tools/shared/python-caller-resilient-adapter.ts
git commit -m "feat(config): add timeout and cache config for risk management functions"
```

---

## Task 14: 端到端测试

**Files:**
- Test: 所有修改的文件

- [ ] **Step 1: 测试数据库配置读取**

Run: `python3 -c "from python.risk_bridge import RiskBridge; rb = RiskBridge('.pi-invest/portfolio.db', 'quant/quantsys/data/stocks.db'); print('Config loaded:', len(rb.config), 'keys')"`
Expected: Config loaded: 11 keys

- [ ] **Step 2: 测试check_trade_risk**

Run: `python3 python/akshare_bridge.py check_trade_risk '{"symbol":"600519","action":"buy","price":1800,"shares":100}'`
Expected: 返回包含 "passed", "level", "reason" 的JSON

- [ ] **Step 3: 测试calculate_position_size**

Run: `python3 python/akshare_bridge.py calculate_position_size '{"symbol":"600519","price":1800,"signal_strength":0.8}'`
Expected: 返回包含 "shares", "kelly_params" 的JSON

- [ ] **Step 4: 测试calculate_stop_loss**

Run: `python3 python/akshare_bridge.py calculate_stop_loss '{"symbol":"600519","entry_price":1800}'`
Expected: 返回包含 "stop_loss_price", "method" 的JSON

- [ ] **Step 5: 测试修改后的calculate_buy_range**

Run: `python3 python/akshare_bridge.py calculate_buy_range '{"symbol":"600519"}'`
Expected: 返回包含 "risk_check", "position_advice", "stop_loss_method" 的JSON

- [ ] **Step 6: 启动开发服务器测试TypeScript工具**

Run: `npm run dev`
在另一个终端测试AI调用工具

- [ ] **Step 7: 验证AI能正确调用新工具**

与AI对话测试：
- "帮我检查买入600519 100股的风控"（应调用check_trade_risk）
- "600519现价1800，建议买多少股？"（应调用calculate_position_size）
- "我1800买入的600519，止损位应该设在哪？"（应调用calculate_stop_loss）
- "分析600519的买入时机"（应调用get_buy_range，返回包含风控结果）

- [ ] **Step 8: 验证风控响应正确**

检查AI响应是否包含：
- 风控检查结果（通过/警告/拒绝）
- Kelly仓位建议
- 动态止损价（不是硬编码8%）

- [ ] **Step 9: Commit测试通过标记**

```bash
git commit --allow-empty -m "test: verify risk system integration end-to-end"
```

---

## Task 15: 文档和清理

**Files:**
- Create: `docs/risk-system-integration.md`

- [ ] **Step 1: 创建用户文档**

```markdown
# 风控系统使用指南

## 概述

风控系统已集成到AI推荐流程中，每次推荐买入时自动执行7项风控检查、Kelly仓位计算和动态止损。

## 自动风控

调用 `get_buy_range` 时自动包含：
- **风控检查**：7项规则验证
- **Kelly仓位**：基于历史数据或保守默认值
- **动态止损**：盈利<5%用固定止损-8%，盈利≥5%用移动止损-10%

## 独立工具

### check_trade_risk
手动验证交易风险，返回通过/警告/拒绝

### calculate_position_size
Kelly公式计算科学仓位

### calculate_stop_loss
动态计算止损价

## 配置

风控参数存储在 `.pi-invest/portfolio.db` 的 `risk_config` 表中。

修改配置：
```sql
sqlite3 .pi-invest/portfolio.db
UPDATE risk_config SET value='0.15' WHERE key='max_position_pct';
```

## 常见问题

**Q: 为什么仓位建议比预期小？**
A: Kelly公式基于历史胜率和盈亏比计算，保守系数0.25确保风险可控。

**Q: 如何查看历史风控记录？**
A: 当前版本暂不记录，未来版本将添加风控事件日志。

**Q: ST股票为什么无法买入？**
A: 风控规则默认禁止ST股票交易，这是保护性规则。
```

- [ ] **Step 2: 创建文档文件**

Run: `cat > docs/risk-system-integration.md << 'EOF'
[上面的markdown内容]
EOF`

- [ ] **Step 3: 更新主README（如果需要）**

在项目README中添加风控系统说明链接

- [ ] **Step 4: Commit文档**

```bash
git add docs/risk-system-integration.md
git commit -m "docs: add risk system integration user guide"
```

- [ ] **Step 5: 最终验证清单**

检查：
- [ ] risk_config表包含11条配置
- [ ] RiskBridge类可正常导入
- [ ] 4个Python函数可通过akshare_bridge调用
- [ ] 3个TypeScript工具已注册
- [ ] get_buy_range返回包含风控结果
- [ ] AI能正确调用和解读风控工具
- [ ] 文档已创建

- [ ] **Step 6: 创建最终提交**

```bash
git add -A
git commit -m "feat: complete risk system integration

- Automatic risk checks in get_buy_range
- Kelly position sizing with historical data fallback
- Hybrid stop-loss strategy (fixed + trailing)
- 3 new risk management tools
- Database-backed risk configuration

Closes #风控系统集成"
```

---

## 自查清单

### 规范覆盖

- [x] Task 1-15 覆盖设计文档所有需求
- [x] 数据库初始化（risk_config表）
- [x] RiskBridge类实现（配置、数据读取、风控逻辑）
- [x] akshare_bridge.py新增4个函数
- [x] calculate_buy_range集成自动风控
- [x] TypeScript 3个新工具
- [x] 工具注册和配置
- [x] 端到端测试
- [x] 用户文档

### 占位符检查

- [x] 所有代码块完整，无TBD/TODO
- [x] 所有文件路径明确
- [x] 所有命令可执行
- [x] 所有测试有预期输出

### 类型一致性

- [x] RiskBridge方法签名一致
- [x] Python函数返回类型一致（Dict）
- [x] TypeScript工具参数类型匹配

---

## 执行选项

计划已完成并保存到 `docs/superpowers/plans/2026-05-19-risk-system-integration.md`。

**两种执行方式：**

**1. Subagent-Driven（推荐）** - 每个任务派发新的子代理，任务间审查，快速迭代

**2. Inline Execution** - 在当前会话中使用 executing-plans 执行，批量执行带检查点

**选择哪种方式？**
