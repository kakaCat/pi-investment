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


def normalize_legacy_trade_action(action: str) -> str:
    """quant.trades 专用：归一小写 'buy'/'sell'。

    ⚠️ 与 normalize_action 的大写契约**方向相反**，这是有意的：quant.trades
    不在 2026-08-13 大写迁移的四张表清单内，其 DB CHECK 约束
    trades_action_check 强制小写（action = ANY(ARRAY['buy','sell'])），
    36 行存量数据亦全为小写。2026-09-14 实测：对该表写大写 'BUY' 直接
    CheckViolation。

    背景（本次修复的缺陷）：models/trade.py 原先误用大写 normalize_action，
    使 Trade ORM 的写入路径与真库约束正面冲突（写即炸），而读侧按小写比较的
    需求又无法满足——导致 record_trade 只能绕开 ORM 走裸 SQL，且
    get_trade_stats 用大写过滤，把 36 笔交易统计成「0 买 0 卖」而不报错。
    """
    normalized = (action or '').strip().lower()
    if normalized not in ('buy', 'sell'):
        raise ValueError(f"非法交易方向: {action!r}（quant.trades 期望 buy/sell）")
    return normalized


def normalize_signal_action(action: str) -> str:
    """信号方向归一化为大写 'BUY'/'SELL'/'HOLD'。"""
    normalized = (action or '').strip().upper()
    if normalized not in ('BUY', 'SELL', 'HOLD'):
        raise ValueError(f"非法信号方向: {action!r}（期望 buy/sell/hold）")
    return normalized
