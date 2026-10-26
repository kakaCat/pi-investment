from datetime import datetime, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

from qs_ops.infrastructure.scheduler.cron_compat import build_cron_trigger

MIGRATION = (Path(__file__).parents[2] / 'infrastructure/persistence/migrations'
             / '20261026_watch_scan_interval_trading_hours.py')
spec = spec_from_file_location('watch_scan_interval_trading_hours', MIGRATION)
module = module_from_spec(spec)
spec.loader.exec_module(module)
TRIGGERS = {}
for _, expression, command, _ in module.TASKS:
    TRIGGERS.setdefault(command, []).append(build_cron_trigger(expression))


def _next_fire(command, after):
    return min(trigger.get_next_fire_time(None, after)
               for trigger in TRIGGERS[command]).replace(tzinfo=None)


def _fires_for_day(command, day):
    current = datetime(2026, 10, day)
    fires = []
    while True:
        current = _next_fire(command, current + timedelta(seconds=1))
        if current.date() != datetime(2026, 10, day).date():
            return fires
        fires.append(current)


@pytest.mark.parametrize('command,expected', [
    ('watch_scan_10m', [
        datetime(2026, 10, 26, 9, 30) + timedelta(minutes=10 * i)
        for i in range(12)
    ] + [
        datetime(2026, 10, 26, 13, 0) + timedelta(minutes=10 * i)
        for i in range(12)
    ]),
    ('watch_scan_30m', [
        datetime(2026, 10, 26, 9, 30),
        datetime(2026, 10, 26, 10, 0),
        datetime(2026, 10, 26, 10, 30),
        datetime(2026, 10, 26, 11, 0),
        datetime(2026, 10, 26, 13, 0),
        datetime(2026, 10, 26, 13, 30),
        datetime(2026, 10, 26, 14, 0),
        datetime(2026, 10, 26, 14, 30),
    ]),
])
def test_interval_scans_match_continuous_auction(command, expected):
    assert _fires_for_day(command, 26) == expected


@pytest.mark.parametrize('command', ['watch_scan_10m', 'watch_scan_30m'])
def test_interval_scans_skip_weekend(command):
    assert _next_fire(command, datetime(2026, 10, 31, 12, 0)) == datetime(2026, 11, 2, 9, 30)


def test_next_run_time_supports_six_field_cron():
    from qs_ops.infrastructure.scheduler.scheduler import next_run_time

    result = next_run_time('0 30 9 * * 1-5', datetime(2026, 10, 26, 9, 0))
    assert result == datetime(2026, 10, 26, 9, 30, tzinfo=result.tzinfo)
    assert result.utcoffset() == timedelta(hours=8)
