"""GameAlertService 内容指纹、窗口口径和当日 critical 闸门测试。"""
from datetime import datetime, timedelta

from qs_intel.application.services.game_alert_service import GameAlertService


NOW = datetime(2026, 11, 18, 9, 30, 0)


class FakeOpponentService:
    def __init__(self, result):
        self.result = result

    def analyze_current_behavior(self):
        return self.result


class FakeManipulationDetector:
    def detect_market_manipulation(self):
        return {'active_manipulations': [], 'post_manipulation_opportunities': []}


def _behavior(*, institution_flow=-1527.1 * 100_000_000,
              current_day_flow=None, has_current_day=False):
    as_of = '2026-11-18' if has_current_day else '2026-11-17'
    return {
        'retail': {
            'behavior': 'fomo_buying',
            'net_flow': 1421.0 * 100_000_000,
            'emotion_index': 80.0,
        },
        'institution': {
            'behavior': 'distributing',
            'net_flow': institution_flow,
            'current_day_net_flow': current_day_flow,
        },
        'market_phase': 'distribution',
        'market_phase_basis': 'fund_flow_combination_only',
        'window': 'trailing_5d_cumulative',
        'window_unit': 'calendar_days',
        'lookback_days': 5,
        'start': '2026-11-14',
        'end': '2026-11-18',
        'as_of': as_of,
        'source': 'fund_flow_repository.get_market_aggregate_flow',
        'source_row_kind': 'daily_market_aggregate',
        'source_rows': 5 if has_current_day else 4,
        'current_day': '2026-11-18',
        'current_day_source_rows': 1 if has_current_day else 0,
        'has_current_day_data': has_current_day,
        'timestamp': NOW.isoformat(),
    }


def _service(opponent, state=None, clock=None):
    clock = clock if clock is not None else {'now': NOW}
    kwargs = {
        'opponent_service': opponent,
        'manipulation_detector': FakeManipulationDetector(),
        'now_fn': lambda: clock['now'],
    }
    if state is not None:
        kwargs['alert_state'] = state
    return GameAlertService(**kwargs)


def _by_title(alerts, title):
    return next(alert for alert in alerts if alert['title'] == title)


def test_repeated_polling_is_deterministic_and_not_notify_worthy():
    opponent = FakeOpponentService(_behavior())
    shared_state = {}
    clock = {'now': NOW}

    first = _service(opponent, shared_state, clock).check_alerts()
    assert len(first) == 2
    assert all(alert['notify_worthy'] is True for alert in first)
    assert all(alert['dedup_persistence'] == 'injected_store' for alert in first)
    assert all(alert['dedup_restart_safe'] is None for alert in first)

    clock['now'] += timedelta(minutes=30)
    # 仅轮询时间变化，业务输入不变；重建服务但复用注入状态仍须去重。
    opponent.result['timestamp'] = clock['now'].isoformat()
    second = _service(opponent, shared_state, clock).check_alerts()

    assert len(second) == len(first)
    assert all(alert['notify_worthy'] is False for alert in second)
    assert all(alert['notification_reason'] == 'unchanged' for alert in second)
    assert [a['alert_id'] for a in second] == [a['alert_id'] for a in first]
    assert [a['content_fingerprint'] for a in second] == [
        a['content_fingerprint'] for a in first]
    assert [a['created_at'] for a in second] == [a['created_at'] for a in first]
    assert all(a['last_seen_at'] == clock['now'].isoformat(timespec='seconds')
               for a in second)


def test_dedup_state_error_keeps_alerts_visible_but_not_notify_worthy():
    class BrokenStore:
        persistence = 'broken'
        restart_safe = False

        def observe(self, key, fingerprint, observed_at):
            raise RuntimeError('state unavailable')

    alerts = _service(FakeOpponentService(_behavior()), BrokenStore()).check_alerts()
    assert len(alerts) == 2
    assert all(alert['notify_worthy'] is False for alert in alerts)
    assert all(alert['notification_reason'] == 'dedup_error' for alert in alerts)
    assert all(alert['dedup_status'] == 'error' for alert in alerts)
    assert all('state unavailable' in alert['dedup_error'] for alert in alerts)


def test_alert_id_is_deterministic_across_time_and_empty_state_restarts():
    opponent = FakeOpponentService(_behavior())
    first_clock = {'now': NOW}
    first = _service(opponent, {}, first_clock).check_alerts()

    second_clock = {'now': NOW + timedelta(hours=1)}
    second = _service(opponent, {}, second_clock).check_alerts()

    assert [a['alert_id'] for a in second] == [a['alert_id'] for a in first]
    assert [a['content_fingerprint'] for a in second] == [
        a['content_fingerprint'] for a in first]
    # 空状态等价于默认内存重启后的情况：ID不变，但可能再提醒一次。
    assert all(a['notify_worthy'] is True for a in second)


def test_changed_input_gets_new_deterministic_id_and_can_notify_again():
    opponent = FakeOpponentService(_behavior())
    state = {}
    service = _service(opponent, state)
    first = _by_title(service.check_alerts(), '机构资金区间累计净流出')

    opponent.result['institution']['net_flow'] = -1600.0 * 100_000_000
    second = _by_title(service.check_alerts(), '机构资金区间累计净流出')

    assert second['notify_worthy'] is True
    assert second['notification_reason'] == 'new_or_changed'
    assert second['content_fingerprint'] != first['content_fingerprint']
    assert second['alert_id'] != first['alert_id']
    assert '1600.0亿' in second['message']


def test_without_current_day_data_cumulative_flow_cannot_be_same_day_critical():
    service = _service(FakeOpponentService(_behavior(has_current_day=False)))

    alerts = service.check_alerts()

    assert all(alert['level'] != 'critical' for alert in alerts)
    cumulative = _by_title(alerts, '机构资金区间累计净流出')
    assert cumulative['level'] == 'high'
    assert cumulative['window'] == 'trailing_5d_cumulative'
    assert cumulative['start'] == '2026-11-14'
    assert cumulative['end'] == '2026-11-18'
    assert cumulative['as_of'] == '2026-11-17'
    assert cumulative['source_rows'] == 4
    assert cumulative['has_current_day_data'] is False
    assert cumulative['details']['current_day_data_missing'] is True
    assert '5日累计窗口' in cumulative['message']
    assert '数据截至2026-11-17' in cumulative['message']
    assert '该数值不是当日流量' in cumulative['message']


def test_real_current_day_large_outflow_can_be_critical_with_single_day_window():
    behavior = _behavior(
        institution_flow=-30.0 * 100_000_000,
        current_day_flow=-60.0 * 100_000_000,
        has_current_day=True,
    )
    service = _service(FakeOpponentService(behavior))

    alerts = service.check_alerts()

    critical = _by_title(alerts, '机构资金当日大额净流出')
    assert critical['level'] == 'critical'
    assert critical['window'] == 'single_day'
    assert critical['start'] == critical['end'] == '2026-11-18'
    assert critical['as_of'] == '2026-11-18'
    assert critical['source_rows'] == 1
    assert critical['details']['flow_scope'] == 'single_day'
    assert '60.0亿（单日数据）' in critical['message']
    # 累计只有30亿，不能额外触发累计50亿阈值告警。
    assert all(alert['title'] != '机构资金区间累计净流出' for alert in alerts)


def test_current_day_critical_fails_closed_when_source_row_count_is_zero():
    behavior = _behavior(
        current_day_flow=-60.0 * 100_000_000,
        has_current_day=True,
    )
    behavior['current_day_source_rows'] = 0  # 矛盾元数据不得绕过单日证据闸门。
    service = _service(FakeOpponentService(behavior))

    alerts = service.check_alerts()

    assert all(alert['level'] != 'critical' for alert in alerts)
    cumulative = _by_title(alerts, '机构资金区间累计净流出')
    assert cumulative['details']['current_day_data_missing'] is True


def test_low_location_flow_divergence_does_not_claim_top_or_direct_liquidation():
    behavior = _behavior()
    behavior['price_location'] = 'low'  # 即使低位，资金组合本身也不得改变措辞。
    service = _service(FakeOpponentService(behavior))

    alerts = service.check_alerts()

    divergence = _by_title(alerts, '资金流向分歧')
    text = divergence['title'] + divergence['message'] + divergence['action']
    assert all(word not in text for word in ('顶部风险', '市场剧增', '清仓', '高位接盘'))
    assert divergence['details']['market_phase_requires_price_confirmation'] is True
    assert divergence['message'].startswith('5日累计窗口')
    assert '不直接触发交易动作' in divergence['action']


def test_default_memory_dedup_explicitly_discloses_restart_risk():
    service = _service(FakeOpponentService(_behavior()))

    alert = service.check_alerts()[0]

    assert alert['dedup_persistence'] == 'process_memory'
    assert alert['dedup_restart_safe'] is False


def test_file_store_preserves_dedup_across_service_restart(tmp_path):
    from adapters.outbound.state.game_alert_state_store import FileGameAlertStateStore

    path = str(tmp_path / 'alerts.json')
    opponent = FakeOpponentService(_behavior())
    first = _service(opponent, FileGameAlertStateStore(path)).check_alerts()
    # 新建 service 和 store，等价于进程重启；不是复用同一个内存 dict。
    second = _service(opponent, FileGameAlertStateStore(path)).check_alerts()

    assert all(row['notify_worthy'] for row in first)
    assert all(not row['notify_worthy'] for row in second)
    assert all(row['dedup_persistence'] == 'file_atomic' for row in second)
    assert all(row['dedup_restart_safe'] is True for row in second)
    assert [row['created_at'] for row in second] == [row['created_at'] for row in first]


def test_file_store_atomic_observe_allows_only_one_notification_per_alert(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from adapters.outbound.state.game_alert_state_store import FileGameAlertStateStore

    path = str(tmp_path / 'shared-alerts.json')
    opponent = FakeOpponentService(_behavior())

    def check(_):
        service = _service(opponent, FileGameAlertStateStore(path))
        return service.check_alerts()

    with ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(check, range(16)))

    flattened = [row for batch in batches for row in batch]
    alerts_per_batch = len(batches[0])
    assert alerts_per_batch == 2
    assert len(flattened) == 16 * alerts_per_batch
    assert sum(row['notify_worthy'] for row in flattened) == alerts_per_batch
    assert all(row['dedup_status'] == 'ok' for row in flattened)
