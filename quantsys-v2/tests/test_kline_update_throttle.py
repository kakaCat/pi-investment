"""kline_update_job 限速与封禁降级检测测试

背景（2026-07-28）：tencent 被封的直接诱因是回填时 5 分钟 1348 次连发请求；
且源被封时 job 全部标记"跳过"，两周无人发现。
"""
from unittest.mock import patch, MagicMock

from infrastructure.jobs import kline_update_job
from adapters.outbound.datasources.providers.kline.base import KlineData


def _run_job(symbols, manager_results, **params):
    """以 mock engine/manager 运行 update_gem_klines"""
    cursor = MagicMock()
    cursor.fetchall.return_value = [(s, f'股{s}') for s in symbols]
    conn = MagicMock()
    conn.cursor.return_value = cursor
    engine = MagicMock()
    engine.raw_connection.return_value = conn

    manager = MagicMock()
    manager.get_klines.side_effect = manager_results

    defaults = {'interval_seconds': 0}
    defaults.update(params)
    with patch.object(kline_update_job, 'get_engine', return_value=engine), \
         patch.object(kline_update_job, 'DataProviderManager', return_value=manager):
        return kline_update_job.update_gem_klines(days=1, **defaults)


def _ok_result():
    # 日期必须 >= 任务基准日（最近已收盘交易日），否则被计为 stale 而非 success
    # （2026-07-30 stale 检测特性）；硬编码历史日期会随时间漂移失败
    from datetime import date as _date
    k = KlineData(symbol='300001', date=_date.today().isoformat(), open=1, high=1,
                  low=1, close=1, volume=100, amount=100.0)
    return {'success': True, 'data': [k], 'source': 'baostock'}


def _fail_result():
    return {'success': False, 'data': None, 'provider_errors': {'baostock': 'WAF 501'}}


def test_throttle_sleeps_between_symbols():
    """每只之间 sleep random.uniform(low, high)，首只前不 sleep"""
    symbols = ['300001', '300002', '300003']
    with patch.object(kline_update_job.time, 'sleep') as mock_sleep:
        _run_job(symbols, [_ok_result()] * 3, interval_seconds=(0.5, 0.5))

    assert mock_sleep.call_count == 2  # 3 只 → 2 次间隔
    for c in mock_sleep.call_args_list:
        assert c[0][0] == 0.5


def test_throttle_disabled_with_zero_interval():
    """interval_seconds=0 时不 sleep（测试/小批量用）"""
    with patch.object(kline_update_job.time, 'sleep') as mock_sleep:
        _run_job(['300001', '300002'], [_ok_result()] * 2, interval_seconds=0)
    mock_sleep.assert_not_called()


def test_degraded_when_mostly_failed():
    """≥20 只且成功率 <50% → provider_health=degraded"""
    symbols = [f'3000{i:02d}' for i in range(25)]
    result = _run_job(symbols, [_fail_result()] * 25)
    assert result['provider_health'] == 'degraded'


def test_health_ok_when_mostly_success():
    """正常情况 provider_health=ok"""
    symbols = [f'3000{i:02d}' for i in range(25)]
    result = _run_job(symbols, [_ok_result()] * 25)
    assert result['provider_health'] == 'ok'


def test_health_ok_below_min_sample():
    """样本 <20 只时不做降级判定（小批量手动更新不误报）"""
    result = _run_job(['300001', '300002'], [_fail_result()] * 2)
    assert result['provider_health'] == 'ok'
