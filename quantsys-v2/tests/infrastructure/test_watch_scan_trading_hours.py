from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from qs_ops.infrastructure.scheduler.cron_compat import build_cron_trigger

MIGRATION = (Path(__file__).parents[2] / 'infrastructure/persistence/migrations'
             / '20261026_watch_scan_trading_hours.py')
spec = spec_from_file_location('watch_scan_trading_hours', MIGRATION)
module = module_from_spec(spec)
spec.loader.exec_module(module)


def _next_fire(after):
    fires = []
    for _, expression, _ in module.TASKS:
        trigger = build_cron_trigger(expression)
        fires.append(trigger.get_next_fire_time(None, after))
    return min(fires).replace(tzinfo=None)


def test_scan_30s_only_runs_during_continuous_auction():
    cases = [
        (datetime(2026, 10, 26, 9, 0), datetime(2026, 10, 26, 9, 30)),
        (datetime(2026, 10, 26, 11, 29, 30), datetime(2026, 10, 26, 11, 29, 30)),
        (datetime(2026, 10, 26, 11, 29, 31), datetime(2026, 10, 26, 13, 0)),
        (datetime(2026, 10, 26, 14, 59, 31), datetime(2026, 10, 27, 9, 30)),
        (datetime(2026, 10, 31, 12, 0), datetime(2026, 11, 2, 9, 30)),
    ]
    for after, expected in cases:
        assert _next_fire(after) == expected


def test_scan_30s_has_complete_weekday_coverage_without_gaps():
    current = datetime(2026, 10, 26, 9, 30)
    fires = [current]
    for _ in range(479):
        current = _next_fire(current + timedelta(seconds=1))
        fires.append(current)

    assert fires[-1] == datetime(2026, 10, 26, 14, 59, 30)
    assert all(b - a == timedelta(seconds=30)
               for a, b in zip(fires, fires[1:])
               if b - a < timedelta(hours=1))
    assert _next_fire(fires[-1] + timedelta(seconds=1)) == datetime(2026, 10, 27, 9, 30)
