"""交易/信号方向（action）的统一规范化 —— 全系统唯一事实源（2026-08-13）。

契约：quant.simulation_trades / simulation_order / simulation_pending_orders /
signals 四张表的 action 列一律大写（BUY/SELL[/HOLD]），由 ORM @validates +
DB CHECK 约束双重强制。背景：61528de 只在 repository 单点规范化，大小写
混写导致幽灵持仓（08-12）、settle_t1 失效、日买入护栏失效等多起事故。

models 层不能 import repository 层（循环依赖），故规范化函数放在本模块；
repository 层从本模块 import 并再导出以兼容旧调用方。
"""


def normalize_action(action: str) -> str:
    """交易方向归一化为大写 'BUY'/'SELL'。

    所有写入必须经过此函数（ORM @validates 已自动调用）；
    读取侧直接按大写比较（历史脏数据已由 migrate_20260813 清洗）。
    """
    normalized = (action or '').strip().upper()
    if normalized not in ('BUY', 'SELL'):
        raise ValueError(f"非法交易方向: {action!r}（期望 buy/sell）")
    return normalized


def normalize_signal_action(action: str) -> str:
    """信号方向归一化为大写 'BUY'/'SELL'/'HOLD'。"""
    normalized = (action or '').strip().upper()
    if normalized not in ('BUY', 'SELL', 'HOLD'):
        raise ValueError(f"非法信号方向: {action!r}（期望 buy/sell/hold）")
    return normalized
