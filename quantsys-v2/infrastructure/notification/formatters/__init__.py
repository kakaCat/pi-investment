# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file

"""
飞书格式化器包
"""

from .feishu_base_formatter import FeishuFormatter
from .feishu_formatters import (
    WatchTriggeredFormatter,
    StopLossFormatter,
    TakeProfitFormatter,
    DailyReportFormatter,
    WeeklyReportFormatter,
    MLTrainFormatter,
    SystemAlertFormatter,
)

__all__ = [
    'FeishuFormatter',
    'WatchTriggeredFormatter',
    'StopLossFormatter',
    'TakeProfitFormatter',
    'DailyReportFormatter',
    'WeeklyReportFormatter',
    'MLTrainFormatter',
    'SystemAlertFormatter',
]
