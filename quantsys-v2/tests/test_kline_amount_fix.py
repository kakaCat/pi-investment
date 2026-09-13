"""成交额(amount)字段修复回归测试

背景：2026-07-13 起 kline_update_job 把 amount 硬编码为 0.0（KlineData 契约
无此字段），导致 _get_stock_pool 的流动性过滤（amount>=1亿）归零、v13/v14
调仓静默取消。同时 tencent/akshare 的 volume 单位为手，与 DB 历史数据（股）
不一致（历史 amount = volume股 × close，ratio=1.0 已验证）。
"""
import sys
from unittest.mock import patch, MagicMock

import pandas as pd

from adapters.outbound.datasources.providers.kline.base import KlineData
from adapters.outbound.datasources.providers.kline.tencent import TencentKlineProvider
from adapters.outbound.datasources.providers.kline.akshare import AkshareKlineProvider


TENCENT_RESPONSE = {
    "code": 0,
    "msg": "",
    "data": {
        "sz300001": {
            # 2026-09-11 (w-23c70356)：provider 自 2026-07-23（84ce0cc2）起只读
            # node['day']（新接口去掉 qfq 参数），此 fixture 仍写 qfqday → 该回归
            # 测试自 07-23 起实际从未跑到断言（Tencent returned no data 静默失败）。
            "day": [
                ["2026-07-15", "31.790", "32.280", "33.610", "31.400", "260109.000"],
                ["2026-07-16", "32.770", "31.280", "32.880", "30.940", "194854.000"],
            ]
        }
    }
}


def _mock_tencent_get(payload):
    resp = MagicMock()
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    return patch('adapters.outbound.datasources.providers.kline.tencent.requests.get',
                 return_value=resp)


def test_kline_data_has_amount_field():
    """KlineData 契约必须有 amount 字段（默认 0.0 向后兼容）"""
    k = KlineData(symbol='300001', date='2026-07-16', open=1, high=1,
                  low=1, close=1, volume=100)
    assert k.amount == 0.0


def test_tencent_volume_normalized_to_shares_and_amount_filled():
    """tencent volume（手）必须 ×100 归一为股，amount = 股 × close

    回归：此前原始手数直接入库，单位比历史数据（股）小 100 倍
    """
    with _mock_tencent_get(TENCENT_RESPONSE):
        klines = TencentKlineProvider().get_klines(
            '300001', 'daily', '2026-07-15', '2026-07-22')

    k = klines[0]
    assert k.volume == 26010900            # 260109 手 × 100
    assert k.amount == 26010900 * 32.28    # 股 × 收盘价


def test_akshare_amount_from_column_and_volume_normalized():
    """akshare 日K 有成交额列，应直接采用；volume（手）×100 归一为股"""
    df = pd.DataFrame({
        '日期': ['2026-07-15', '2026-07-16'],
        '开盘': [31.79, 32.77],
        '收盘': [32.28, 31.28],
        '最高': [33.61, 32.88],
        '最低': [31.40, 30.94],
        '成交量': [260109, 194854],
        '成交额': [839878123.0, 609523456.0],
    })
    mock_ak = MagicMock()
    mock_ak.stock_zh_a_hist.return_value = df

    with patch.dict(sys.modules, {'akshare': mock_ak}):
        klines = AkshareKlineProvider().get_klines(
            '300001', 'daily', '2026-07-15', '2026-07-16')

    k = klines[0]
    assert k.volume == 26010900          # 手 × 100
    assert k.amount == 839878123.0       # 直接用成交额列


def test_kline_update_job_writes_amount():
    """kline_update_job 必须把 k.amount 原样带到写入层（回归：此前硬编码 0.0）

    2026-09-13（w-32314d00，REQ-24e15d t4）适配：作业层的手写 INSERT 已收敛为
    KlineSyncRepository.upsert_fetched_klines → KlineORMRepository.batch_insert_daily_klines，
    断言点随之从"INSERT 语句的位置参数"改为"交给写入口的 DailyKline 对象"。
    断言的不变量完全不变：amount / turnover_rate 必须一路传到落库层。
    """
    from infrastructure.jobs import kline_update_job
    from adapters.outbound.repositories.kline_sync_repository import KlineSyncRepository
    from adapters.outbound.repositories import kline_repository as kr_module

    kline = KlineData(symbol='300001', date='2026-07-16', open=31.79,
                      high=33.61, low=31.40, close=32.28,
                      volume=26010900, amount=839878123.0, turnover_rate=2.5)

    manager = MagicMock()
    manager.get_klines.return_value = {'success': True, 'data': [kline], 'source': 'tencent'}

    repo = MagicMock()
    repo.select_sync_universe.return_value = [('300001', '测试股')]
    repo.count_missing_amount.return_value = 0
    repo.detect_amount_scale_anomalies.return_value = []
    repo.detect_volume_unit_anomalies.return_value = []
    # 让替身仓储执行**真实的** upsert 转换逻辑（本测试要验的正是这一段的字段透传），
    # 只把最底层的写入口 batch_insert_daily_klines 换成捕获器。
    repo.upsert_fetched_klines.side_effect = (
        lambda symbol, klines: KlineSyncRepository.upsert_fetched_klines(repo, symbol, klines))

    captured = {}

    def _capture_batch(self, objs):
        captured['objs'] = list(objs)
        return True

    with patch.object(kline_update_job, 'KlineSyncRepository', return_value=repo), \
         patch.object(kline_update_job, 'DataProviderManager', return_value=manager), \
         patch.object(kr_module.KlineORMRepository, 'batch_insert_daily_klines', _capture_batch):
        kline_update_job.update_gem_klines(days=1, symbols=['300001'], interval_seconds=0)

    objs = captured.get('objs')
    assert objs, "未调用 daily_klines 写入口"
    assert objs[0].amount == 839878123.0
    assert objs[0].turnover_rate == 2.5
