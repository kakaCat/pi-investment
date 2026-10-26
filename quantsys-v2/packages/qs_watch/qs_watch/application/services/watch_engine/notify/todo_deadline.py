from datetime import datetime, time, timedelta


def p2_due(now: datetime):
    try:
        from qs_trading.domain.trading.services.market_session_policy import CONTINUOUS_END as close
    except Exception:  # noqa: BLE001
        close = time(15, 0)
    day_close = datetime.combine(now.date(), close)
    due = day_close if day_close > now else now + timedelta(minutes=1)
    return due, max(1, int((due - now).total_seconds()))
