"""
风控桥接层 - 连接 portfolio.db 和 quantsys.risk
"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from types import SimpleNamespace

from quantsys.risk.pre_trade import PreTradeRiskCheck, RiskConfig
from quantsys.risk.position_manager import PositionManager, PositionSizeConfig
from quantsys.risk.stop_loss import StopLossManager, StopLossConfig


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
        except sqlite3.Error:
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
                cursor = conn.execute("SELECT SUM(market_value) FROM holdings WHERE shares > 0")
                row = cursor.fetchone()
                total_equity = row[0] if row and row[0] else 100000.0

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
        except sqlite3.Error:
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
        except sqlite3.Error:
            return []

    def _calculate_win_rate(self, trades: List[Dict]) -> tuple:
        """
        计算胜率和盈亏比

        Returns:
            (win_rate, profit_loss_ratio, trade_count)
        """
        if len(trades) < 2:
            return 0.5, 1.5, 0

        positions = {}
        closed_trades = []

        for trade in reversed(trades):
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

        wins = [p for p in closed_trades if p > 0]
        losses = [p for p in closed_trades if p < 0]

        win_rate = len(wins) / len(closed_trades) if closed_trades else 0.5

        avg_win = sum(wins) / len(wins) if wins else 0.1
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.05
        profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.5

        return win_rate, profit_loss_ratio, len(closed_trades)

    def _build_risk_config(self):
        """构建RiskConfig对象"""
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
        except (ValueError, TypeError):
            return None

    def _calculate_max_allowed_shares(self, symbol: str, price: float, portfolio: SimpleNamespace) -> int:
        """计算最大允许买入股数（不超过仓位限制）"""
        if price <= 0:
            return 0

        max_pct = float(self.config.get('max_position_pct', 0.10))
        max_value = portfolio.total_equity * max_pct

        if symbol in portfolio.positions:
            existing_value = portfolio.positions[symbol].market_value
            max_value -= existing_value

        if max_value <= 0:
            return 0

        max_shares = int(max_value / price / 100) * 100
        return max(0, max_shares)

    def _fetch_current_price(self, symbol: str):
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
        except sqlite3.Error:
            return None

    def check_trade_risk(self, symbol: str, action: str, price: float, shares: int) -> Dict:
        """预交易风控检查"""
        if price <= 0:
            return {
                "passed": False,
                "level": "reject",
                "reason": "价格必须大于0",
                "violations": [{"rule": "invalid_price", "severity": "high", "message": f"Invalid price: {price}"}],
                "adjusted_shares": 0
            }

        if shares <= 0:
            return {
                "passed": False,
                "level": "reject",
                "reason": "股数必须大于0",
                "violations": [{"rule": "invalid_shares", "severity": "high", "message": f"Invalid shares: {shares}"}],
                "adjusted_shares": 0
            }

        try:
            portfolio = self._get_portfolio_snapshot()

            order = SimpleNamespace(
                symbol=symbol,
                action=action,
                price=price,
                shares=shares,
                date=datetime.now().strftime('%Y-%m-%d')
            )

            risk_checker = PreTradeRiskCheck(config=self._build_risk_config())
            passed, error_msg = risk_checker.check(order, portfolio, market_data=None)

            violations = []
            level = "pass"
            adjusted_shares = shares

            if not passed:
                if any(kw in error_msg for kw in ['ST', '黑名单', '回撤']):
                    level = "reject"
                elif '仓位限制' in error_msg:
                    adjusted_shares = self._calculate_max_allowed_shares(symbol, price, portfolio)
                    if adjusted_shares == 0:
                        level = "reject"
                    else:
                        level = "warning"
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
                "passed": False,
                "level": "warning",
                "reason": f"风控检查异常: {str(e)}",
                "violations": [{"rule": "exception", "severity": "high", "message": str(e)}],
                "adjusted_shares": shares
            }

    def calculate_position_size(self, symbol: str, price: float, signal_strength: float = 1.0) -> Dict:
        """Kelly公式计算建议仓位"""
        if price <= 0:
            return {
                "shares": 0,
                "position_pct": 0.0,
                "position_value": 0.0,
                "method": "error",
                "kelly_params": {
                    "win_rate": 0.50,
                    "profit_loss_ratio": 1.5,
                    "data_source": "error",
                    "trade_count": 0,
                    "error": f"Invalid price: {price}"
                }
            }

        try:
            portfolio = self._get_portfolio_snapshot()
            total_equity = portfolio.total_equity

            if total_equity <= 0:
                return {
                    "shares": 0,
                    "position_pct": 0.0,
                    "position_value": 0.0,
                    "method": "error",
                    "kelly_params": {
                        "win_rate": 0.50,
                        "profit_loss_ratio": 1.5,
                        "data_source": "error",
                        "trade_count": 0,
                        "error": "Total equity is zero or negative"
                    }
                }

            trades = self._get_trade_history(symbol)
            min_trades = int(self.config.get('min_trade_history', 10))

            if len(trades) >= min_trades:
                win_rate, pl_ratio, count = self._calculate_win_rate(trades)
                data_source = "historical"
            else:
                win_rate = float(self.config.get('default_win_rate', 0.50))
                pl_ratio = float(self.config.get('default_profit_loss_ratio', 1.5))
                data_source = "default"
                count = len(trades)

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
            portfolio = self._get_portfolio_snapshot()
            if portfolio.total_equity <= 0:
                shares = 0
            else:
                shares = int(portfolio.total_equity * 0.05 / price / 100) * 100

            return {
                "shares": shares,
                "position_pct": (shares * price) / portfolio.total_equity if portfolio.total_equity > 0 else 0.0,
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

    def calculate_stop_loss(self, symbol: str, entry_price: float,
                           current_price: Optional[float] = None,
                           highest_price: Optional[float] = None) -> Dict:
        """计算止损价（混合策略）"""
        if entry_price <= 0:
            return {"error": "入场价格必须大于0"}

        try:
            if current_price is None:
                current_price = self._fetch_current_price(symbol)
                if current_price is None:
                    return {"error": f"无法获取{symbol}的当前价格"}

            if current_price <= 0:
                return {"error": f"当前价格无效: {current_price}"}

            if highest_price is None:
                highest_price = current_price

            if highest_price <= 0:
                return {"error": f"最高价格无效: {highest_price}"}

            if entry_price == 0:
                return {"error": "入场价格不能为0"}

            pnl_pct = (current_price - entry_price) / entry_price
            profit_threshold = float(self.config.get('profit_threshold_for_trailing', 0.05))

            if pnl_pct < profit_threshold:
                fixed_pct = float(self.config.get('fixed_stop_loss_pct', 0.08))
                stop_loss_price = entry_price * (1 - fixed_pct)
                method = "fixed"
                reason = f"当前盈利{pnl_pct:.1%} < {profit_threshold:.0%}，使用固定止损-{fixed_pct:.0%}"
            else:
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
