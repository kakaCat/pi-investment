"""交易日日期工具（qs_ops 域内，2026-10-21 反向越层收口）

原定义：adapters/inbound/fastapi_app/daily_jobs/pipeline.py::_last_trading_day。
当时 qs_ops/application/services/scheduler_tasks_data.py 反向跨层引本壳私有
helper（包引内部适配器「包引 inbound 首例实锤」）。现权定义迁至本模块，
app 壳与其余消费方改从包内引（壳引包 = 合规边）。
"""
from datetime import datetime, time as dtime, timedelta


def last_trading_day(ref: datetime) -> str:
    """最近一个应为交易日的日期（周末排除法；节假日由告警人工复核）"""
    d = ref.date()
    # 收盘前（15:30 前）看前一工作日；收盘后看今天
    if ref.time() < dtime(15, 30) or d.weekday() >= 5:
        d = d - timedelta(days=1)
    while d.weekday() >= 5:
        d = d - timedelta(days=1)
    return d.strftime('%Y-%m-%d')
