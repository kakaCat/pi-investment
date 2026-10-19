"""盘中风控口径（宪法对齐，qs_trading 域内实现）

宪法止损口径：创业板（30 开头）/科创板（68 开头）-10%，其余 -8%。
止盈口径：+15%（全市场统一，宪法未对止盈分级）。

口径与 qs_watch 的 `position_lifecycle_service.stop_loss_pct` 等价，
但 qs_trading **不跨包 import qs_watch**（包依赖边界，方案卡 §11.3）——
两包各自持有一份实现，口径变更时需同步两处。
"""
from __future__ import annotations

# 返回值为正数口径（幅度），调用方自行取负作为阈值
DEFAULT_STOP_LOSS_PCT = 0.08
GEM_STAR_STOP_LOSS_PCT = 0.10  # 创业板/科创板

DEFAULT_TAKE_PROFIT_PCT = 0.15


def stop_loss_pct(symbol: str) -> float:
    """宪法止损口径：创业板/科创板（30/68 开头）10%，其余 8%（正数幅度）"""
    s = str(symbol).split(".")[0]
    return GEM_STAR_STOP_LOSS_PCT if s.startswith(("30", "68")) else DEFAULT_STOP_LOSS_PCT
