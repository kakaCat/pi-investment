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
