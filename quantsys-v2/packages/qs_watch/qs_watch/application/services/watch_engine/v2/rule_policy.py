"""V2 股票规则的时间与持仓分类策略。"""
import structlog

logger = structlog.get_logger(__name__)


def in_active_window(rule, now) -> bool:
    windows = getattr(rule, 'active_window', None)
    if not windows:
        return True
    current = now.strftime('%H:%M')
    try:
        return any(start <= current <= end for window in windows
                   for start, end in [window.split('-')])
    except (ValueError, AttributeError, TypeError) as exc:
        logger.warning('v2.active_window_invalid',
                       rule_id=getattr(rule, 'id', None), error=str(exc))
        return True


def position_intent(intent) -> bool:
    return str(intent or '') in (
        'add_position', 'exit_take_profit', 'exit_stop', 'exit_reduce')
