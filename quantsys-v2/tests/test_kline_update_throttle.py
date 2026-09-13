"""kline_update_job 限速与封禁降级检测测试

背景（2026-07-28）：tencent 被封的直接诱因是回填时 5 分钟 1348 次连发请求；
且源被封时 job 全部标记"跳过"，两周无人发现。

2026-09-13（w-32314d00，REQ-24e15d t4）适配：作业层不再直接持有 engine/cursor
（SQL 已收敛到 KlineSyncRepository），因此 mock 点从 get_engine 换成仓储，
断言也从"INSERT 文本是否出现"换成"仓储写方法是否被调用"——后者更直接地表达了
本测试真正关心的不变量（**不该发请求、不该落库**）。
"""
from unittest.mock import patch, MagicMock

from infrastructure.jobs import kline_update_job
from adapters.outbound.datasources.providers.kline.base import KlineData


def _repo_for(symbols):
    """构造替身仓储：选股返回给定宇宙，写方法与自检方法均为无害桩。"""
    repo = MagicMock()
    repo.select_sync_universe.return_value = [(s, f'股{s}') for s in symbols]
    repo.upsert_fetched_klines.return_value = 1
    repo.count_missing_amount.return_value = 0
    repo.detect_amount_scale_anomalies.return_value = []
    repo.detect_volume_unit_anomalies.return_value = []
    return repo


def _run_job(symbols, manager_results, **params):
    """以替身仓储/数据源运行 update_gem_klines，返回 (结果, 仓储替身, 数据源替身)"""
    repo = _repo_for(symbols)

    manager = MagicMock()
    manager.get_klines.side_effect = manager_results

    defaults = {'interval_seconds': 0}
    defaults.update(params)
    with patch.object(kline_update_job, 'KlineSyncRepository', return_value=repo), \
         patch.object(kline_update_job, 'DataProviderManager', return_value=manager):
        result = kline_update_job.update_gem_klines(days=1, **defaults)
    return result, repo, manager


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
    result, _repo, _mgr = _run_job(symbols, [_fail_result()] * 25)
    assert result['provider_health'] == 'degraded'


def test_health_ok_when_mostly_success():
    """正常情况 provider_health=ok"""
    symbols = [f'3000{i:02d}' for i in range(25)]
    result, _repo, _mgr = _run_job(symbols, [_ok_result()] * 25)
    assert result['provider_health'] == 'ok'


def test_health_ok_below_min_sample():
    """样本 <20 只时不做降级判定（小批量手动更新不误报）"""
    result, _repo, _mgr = _run_job(['300001', '300002'], [_fail_result()] * 2)
    assert result['provider_health'] == 'ok'


def test_write_failure_counted_as_failed():
    """仓储 upsert 返回 None（写失败）时计 failed，不得计 success（2026-09-13 新增）"""
    repo = _repo_for(['300001'])
    repo.upsert_fetched_klines.return_value = None
    manager = MagicMock()
    manager.get_klines.return_value = _ok_result()

    with patch.object(kline_update_job, 'KlineSyncRepository', return_value=repo), \
         patch.object(kline_update_job, 'DataProviderManager', return_value=manager):
        result = kline_update_job.update_gem_klines(
            days=1, symbols=['300001'], interval_seconds=0)

    assert result['failed'] == 1
    assert result['success'] == 0


def test_nonstandard_symbol_skipped_before_write():
    """伪代码/非 6 位符号在写入循环被兜底拦下（2026-09-11 w-23c70356）

    背景：quant.stocks 曾被测试数据污染（600000.SH…600009.SH，name='Test'），
    同步任务把它们当宇宙成员逐日写出 1,213 行伪 K 线（其中 600001/600002/600003/
    600005 早已退市却有 2026 年行情）。清理 1,507 行后加写入侧兜底：显式 symbols
    入参（如手动补跑）也不能穿透，且连 provider 请求都不该发出。
    """
    manager = MagicMock()
    manager.get_klines.return_value = _ok_result()
    # 选股替身故意返回伪代码（模拟显式 symbols 穿透选股层）
    repo = _repo_for(['600000.SH'])

    with patch.object(kline_update_job, 'KlineSyncRepository', return_value=repo), \
         patch.object(kline_update_job, 'DataProviderManager', return_value=manager):
        result = kline_update_job.update_gem_klines(
            days=1, symbols=['600000.SH'], interval_seconds=0)

    assert result['skipped'] == 1
    assert result['success'] == 0
    manager.get_klines.assert_not_called()
    repo.upsert_fetched_klines.assert_not_called()


def test_standard_symbol_still_written():
    """对照组：6 位裸码照常写入（兜底不能误伤正常标的）"""
    result, repo, _mgr = _run_job(['300001'], [_ok_result()], interval_seconds=0)

    assert result['success'] == 1
    assert result['skipped'] == 0
    assert repo.upsert_fetched_klines.call_count == 1
