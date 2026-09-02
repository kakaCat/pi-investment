"""
market_style_detector 单测（2026-09-03 真实化后重写）

修复前测试断言的是造假实现：_calculate_value_style_score 恒 0.45、默认 growth/0.33、
异常回退 growth——那些测试锁死了"编造数据"行为，随真实化一并删除。

新测试覆盖真实契约：
  - compute_style_from_boards 纯函数：真实输入 → 显式映射桶 → 真实分数
  - 新浪 49 行业映射完整性（无遗漏，避免覆盖静默下降）
  - 三风格分化不足 → 真实 unknown（conf=0，非降级）
  - 无有效数据 → 显式 degraded（degraded=True + error，绝不 growth/0.33 编造）
  - detect_market_style：DB 真实行 fast path / 实时回退 / degraded 三层（monkeypatch，无网络）
  - 推荐因子与主导风格一致
"""
import pytest
from application.services.market_style_detector import (
    MarketStyleDetector,
    compute_style_from_boards,
    BOARD_STYLE_MAP,
    STYLE_VALUE,
    STYLE_GROWTH,
    STYLE_CYCLE,
)

# 新浪行业 49（实测 ak.stock_sector_spot(indicator='新浪行业') 返回全集）
SINA_49_BOARDS = [
    '玻璃行业', '船舶制造', '传媒娱乐', '电力行业', '电器行业', '电子器件', '电子信息',
    '房地产', '发电设备', '飞机制造', '纺织行业', '纺织机械', '服装鞋类', '公路桥梁',
    '供水供气', '钢铁行业', '环保行业', '化工行业', '化纤行业', '家电行业', '酒店旅游',
    '家具行业', '金融行业', '交通运输', '机械行业', '建筑建材', '开发区', '酿酒行业',
    '摩托车', '煤炭行业', '农林牧渔', '农药化肥', '汽车制造', '其它行业', '塑料制品',
    '水泥行业', '食品行业', '次新股', '生物制药', '商业百货', '石油行业', '陶瓷行业',
    '物资外贸', '医疗器械', '仪器仪表', '印刷包装', '有色金属', '综合行业', '造纸行业',
]


def _boards(rows):
    """rows: [(name, pct), ...] → boards dict 列表"""
    return [{'name': n, 'change_pct': p} for n, p in rows]


# ---------- 纯函数计算 ----------

def test_compute_style_from_boards_value_dominant():
    # 价值桶明显抗跌（跌最少），成长中等，周期最弱
    boards = _boards([
        ('金融行业', -0.3), ('酿酒行业', -0.5), ('电力行业', -0.2),   # value 偏强
        ('电子信息', -1.2), ('电子器件', -1.0),                        # growth 中
        ('钢铁行业', -2.5), ('煤炭行业', -2.8), ('有色金属', -2.2),   # cycle 最弱
    ])
    r = compute_style_from_boards(boards)
    assert r['style'] == STYLE_VALUE
    assert 0 < r['confidence'] <= 1
    assert set(r['scores'].keys()) == {STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE}
    assert r['recommended_factors'] == ['pe', 'pb', 'dividend_yield', 'debt_ratio']
    assert r['indicators']['degraded'] is False


def test_compute_style_from_boards_growth_dominant():
    boards = _boards([
        ('金融行业', -1.5), ('酿酒行业', -1.3),
        ('电子信息', 0.8), ('生物制药', 0.5), ('医疗器械', 0.4),
        ('钢铁行业', -1.0), ('煤炭行业', -1.2),
    ])
    r = compute_style_from_boards(boards)
    assert r['style'] == STYLE_GROWTH
    assert r['recommended_factors'] == ['roe', 'revenue_growth', 'macd', 'momentum']


def test_compute_style_from_boards_cycle_dominant():
    boards = _boards([
        ('金融行业', -1.5), ('酿酒行业', -1.3),
        ('电子信息', -1.0),
        ('钢铁行业', 1.2), ('煤炭行业', 0.8), ('有色金属', 1.0),
    ])
    r = compute_style_from_boards(boards)
    assert r['style'] == STYLE_CYCLE
    assert r['recommended_factors'] == ['rsi', 'volume', 'bollinger', 'macd']


def test_compute_style_from_boards_no_differentiation_is_unknown():
    # 分化 <0.3pp → 真实 unknown（非降级、非编造）
    boards = _boards([
        ('金融行业', -1.0), ('酿酒行业', -1.0), ('电力行业', -1.1),
        ('电子信息', -1.0), ('电子器件', -1.1),
        ('钢铁行业', -1.05), ('煤炭行业', -1.0),
    ])
    r = compute_style_from_boards(boards)
    assert r['style'] == 'unknown'
    assert r['confidence'] == 0.0
    assert r['indicators']['degraded'] is False
    assert r['recommended_factors'] == []
    assert '分化不足' in r['indicators']['note']


def test_compute_style_from_boards_empty_is_degraded():
    r = compute_style_from_boards([])
    assert r['style'] == 'unknown'
    assert r['confidence'] == 0.0
    assert r['indicators']['degraded'] is True
    assert r['indicators']['error']
    # 绝不回退到编造的 growth/0.33
    assert r['style'] != STYLE_GROWTH


def test_compute_style_from_boards_unknown_boards_excluded_with_coverage():
    # 无法归类的行业不计分但统计覆盖率
    boards = _boards([
        ('金融行业', -0.5), ('电子信息', -1.0), ('钢铁行业', -1.5),
        ('次新股', 5.0), ('其它行业', 3.0), ('开发区', 2.0),  # 混合题材，排除
    ])
    r = compute_style_from_boards(boards)
    ind = r['indicators']
    assert ind['boards_total'] == 6
    assert ind['mapped_total'] == 3
    assert ind['coverage'] == pytest.approx(0.5)
    assert set(ind['unmapped']) >= {'次新股', '其它行业', '开发区'}
    # 排除后 value 仍为主导
    assert r['style'] == STYLE_VALUE


def test_sina_49_boards_mapping_complete():
    """新浪 49 行业必须全部落入某风格桶或被显式排除——防覆盖静默下降"""
    from application.services.market_style_detector import (
        EXCLUDED_BOARDS, VALUE_BOARDS, GROWTH_BOARDS, CYCLE_BOARDS,
    )
    all_buckets = VALUE_BOARDS | GROWTH_BOARDS | CYCLE_BOARDS | EXCLUDED_BOARDS
    missing = [b for b in SINA_49_BOARDS if b not in all_buckets]
    assert missing == [], f"映射遗漏新浪行业: {missing}"
    # 映射表与集合一致
    for b in SINA_49_BOARDS:
        if b in EXCLUDED_BOARDS:
            assert b not in BOARD_STYLE_MAP
        else:
            assert b in BOARD_STYLE_MAP


# ---------- detect_market_style 数据路径（monkeypatch，无网络） ----------

def test_detect_returns_db_latest_when_real_row_exists(monkeypatch):
    detector = MarketStyleDetector()
    db_row = {
        'style': STYLE_GROWTH,
        'confidence': 0.7,
        'scores': {STYLE_VALUE: 0.1, STYLE_GROWTH: 0.7, STYLE_CYCLE: 0.2},
        'indicators': {'source': 'db_market_style_state', 'db_trade_date': '2026-09-02',
                       'degraded': False, 'note': '来自 DB 最近落库行（job 每日收盘后写库）'},
        'recommended_factors': ['roe', 'revenue_growth', 'macd', 'momentum'],
        'detection_date': '2026-09-02',
    }
    monkeypatch.setattr(detector, '_read_latest_db_row', lambda: db_row)
    # 若 DB 有真实行，不应触发网络拉取
    fetched = []
    monkeypatch.setattr('application.services.market_style_detector.fetch_sina_sector_boards',
                        lambda: fetched.append(1) or None)
    result = detector.detect_market_style()
    assert result['style'] == STYLE_GROWTH
    assert result['confidence'] == 0.7
    assert fetched == [], "DB 真实行存在时不应触发网络拉取"


def test_detect_falls_back_to_realtime_when_no_db_row(monkeypatch):
    detector = MarketStyleDetector()
    monkeypatch.setattr(detector, '_read_latest_db_row', lambda: None)
    boards = _boards([
        ('金融行业', -0.3), ('酿酒行业', -0.4),
        ('电子信息', -1.2), ('电子器件', -1.0),
        ('钢铁行业', -2.5), ('煤炭行业', -2.8),
    ])
    monkeypatch.setattr('application.services.market_style_detector.fetch_sina_sector_boards',
                        lambda: boards)
    result = detector.detect_market_style()
    assert result['style'] == STYLE_VALUE
    assert result['indicators']['degraded'] is False
    assert '实时回退' in result['indicators'].get('source', '') or result['indicators'].get(
        'method') is not None


def test_detect_degraded_when_no_db_and_fetch_fails(monkeypatch):
    detector = MarketStyleDetector()
    monkeypatch.setattr(detector, '_read_latest_db_row', lambda: None)
    monkeypatch.setattr('application.services.market_style_detector.fetch_sina_sector_boards',
                        lambda: None)
    result = detector.detect_market_style()
    assert result['style'] == 'unknown'
    assert result['confidence'] == 0.0
    assert result['indicators']['degraded'] is True
    assert result['indicators']['error']
    assert result['style'] != STYLE_GROWTH  # 绝不编造成 growth


def test_read_latest_db_row_ignores_fake_unknown_row(monkeypatch):
    """历史伪造行（unknown/0.0，如 2026-06-02）不得被当作真实风格返回"""
    detector = MarketStyleDetector()
    fake_row = {'style': 'unknown', 'confidence': 0.0, 'metrics': None,
                'trade_date': '2026-06-02'}

    class FakeRepo:
        def get_market_style(self):
            return fake_row

    monkeypatch.setattr(
        'adapters.outbound.repositories.market_style_repository.MarketStyleORMRepository',
        lambda: FakeRepo(),
    )
    assert detector._read_latest_db_row() is None


# ---------- 兼容性 ----------

def test_detector_initialization():
    detector = MarketStyleDetector()
    assert detector is not None
    assert hasattr(detector, 'detect_market_style')
    assert detector.kline_repo is None
    assert detector.stock_repo is None
    # 类级常量兼容引用
    assert detector.STYLE_FACTORS == MarketStyleDetector.STYLE_FACTORS


def test_detect_market_style_returns_result_contract(monkeypatch):
    detector = MarketStyleDetector()
    db_row = {
        'style': STYLE_CYCLE, 'confidence': 0.6,
        'scores': {STYLE_VALUE: 0.1, STYLE_GROWTH: 0.2, STYLE_CYCLE: 0.6},
        'indicators': {'source': 'db', 'degraded': False}, 'recommended_factors': [],
        'detection_date': '2026-09-02',
    }
    monkeypatch.setattr(detector, '_read_latest_db_row', lambda: db_row)
    result = detector.detect_market_style(lookback_days=30)
    for key in ('style', 'confidence', 'scores', 'indicators',
                'recommended_factors', 'detection_date'):
        assert key in result
