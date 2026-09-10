"""paper_trading_engine 迁移过渡垫片（2026-09-10，w-f4aa1f6a）

另一会话的 WIP 把 domain/trading/services/__init__.py 改为
from .paper_trading_engine import PaperTradingEngine，但目标文件未随附——
整个 domain.trading.services 包不可导入，交易护栏链路（trade_guard_service）
与相关测试收集全部中断。

真实实现在 application/trading/paper_trading_engine.py（未删除）。
本垫片让新位置可解析：WIP 会话落地正式迁移后直接覆盖本文件即可。
"""

from application.trading.paper_trading_engine import PaperTradingEngine  # noqa: F401
