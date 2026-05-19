#!/usr/bin/env python3
"""
风控桥接层 - 连接 portfolio.db 和 quant/quantsys/risk
"""
import sqlite3
import sys
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from types import SimpleNamespace

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
            with sqlite3.connect(self.portfolio_db) as conn:
                cursor = conn.execute("SELECT key, value FROM risk_config")
                config = {row[0]: row[1] for row in cursor.fetchall()}
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

    def _get_portfolio_snapshot(self) -> SimpleNamespace:
        """读取当前持仓快照"""
        try:
            with sqlite3.connect(self.portfolio_db) as conn:
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

                return SimpleNamespace(
                    total_equity=total_equity,
                    positions=positions
                )
        except sqlite3.Error as e:
            print(f"Warning: Failed to get portfolio snapshot: {e}", file=sys.stderr)
            return SimpleNamespace(total_equity=100000.0, positions={})

    def _get_trade_history(self, symbol: Optional[str] = None) -> List[Dict]:
        """读取历史交易记录"""
        try:
            with sqlite3.connect(self.portfolio_db) as conn:
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

                return trades
        except sqlite3.Error as e:
            print(f"Warning: Failed to get trade history: {e}", file=sys.stderr)
            return []

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

    def _build_risk_config(self) -> Optional['RiskConfig']:
        """构建RiskConfig对象"""
        if not QUANT_AVAILABLE:
            return None

        try:
            return RiskConfig(
                max_position_pct=float(self.config.get('max_position_pct', 0.10)),
                max_sector_pct=float(self.config.get('max_sector_pct', 0.30)),
                max_drawdown=float(self.config.get('max_drawdown', 0.20)),
                max_daily_trades=int(self.config.get('max_daily_trades', 10)),
                blacklist=[],
                allow_st_stocks=False,
                min_liquidity=1000000
            )
        except (ValueError, TypeError) as e:
            print(f"Warning: Invalid risk config values: {e}", file=sys.stderr)
            return None

    def _calculate_max_allowed_shares(self, symbol: str, price: float, portfolio: SimpleNamespace) -> int:
        """计算最大允许买入股数（不超过仓位限制）"""
        if price <= 0:
            return 0

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

    def _fetch_current_price(self, symbol: str) -> Optional[float]:
        """从quant DB获取当前价格"""
        try:
            with sqlite3.connect(self.quant_db) as conn:
                cursor = conn.execute("""
                    SELECT close
                    FROM daily_klines
                    WHERE symbol = ?
                    ORDER BY date DESC
                    LIMIT 1
                """, (symbol,))

                row = cursor.fetchone()
                return row[0] if row else None
        except sqlite3.Error as e:
            print(f"Warning: Failed to fetch price for {symbol}: {e}", file=sys.stderr)
            return None

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
