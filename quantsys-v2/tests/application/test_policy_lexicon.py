"""词表配置化与政策/行业词表单测（2026-10-21）

覆盖三条验收：
  0. 个股口径默认行为与初版逐字一致（词表是转发别名，判定结果不变）；
  1. 政策/行业词表分级与降噪规则；
  2. 词表是**配置数据**：扩展行业只加词表条目，判定路径零改动。
"""
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

# 机械验收用的 pytest 未必是装了 editable 包的 venv：按仓库布局兜底源码路径
# （等价的 pip install -e ./packages/*），让本文件在裸解释器下也能直接收集。
_PACKAGES = Path(__file__).resolve().parents[2] / 'packages'
if _PACKAGES.is_dir():
    for _pkg in sorted(_PACKAGES.iterdir()):
        if _pkg.is_dir() and (_pkg / _pkg.name).is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))

from qs_watch.application.services.watch_engine import policy_lexicon as pl  # noqa: E402
from qs_watch.application.services.watch_engine import news_watch_service  # noqa: E402
from qs_watch.application.services.watch_engine.news_watch_service import (  # noqa: E402
    CRITICAL_WORDS, NOISE_WORDS, SOFT_WORDS, NewsWatchService, classify,
)

NOW = datetime(2026, 10, 20, 10, 0)   # 周二盘中（扫描窗口内）


# ── 0. 个股口径默认行为逐字不变 ─────────────────────────────────────

def test_default_still_individual_stock_lexicon_verbatim():
    """不传词表 = 个股口径；初版判定结果（既有用例即契约）逐条不变。"""
    assert classify('证监会立案：公司涉嫌信息披露违规')[0] == 'critical'
    assert classify('股东拟减持不超过2%股份')[0] == 'soft'
    assert classify('业绩说明会纪要发布')[0] == 'none'          # 噪声词降级
    assert classify('关于召开业绩说明会的公告')[0] == 'none'
    assert classify('收到警示函 同时被立案调查')[0] == 'critical'  # critical 压过噪声
    # 政策/行业词不会漏进个股默认口径（口径明确、互不污染）
    assert classify('央行宣布降准0.5个百分点') == ('none', [])
    assert classify('某半导体厂被列入实体清单') == ('none', [])


def test_stock_word_tables_are_byte_for_byte_the_historical_lists():
    """『个股词表逐字不变』的硬契约：历史字面量原样锁在这里，改一个词就红。"""
    assert pl.STOCK_CRITICAL == (
        '立案', '退市', '爆雷', '违规', '处罚', '罚款', '破产', '债务违约', '逾期',
        '巨亏', '商誉减值', '清仓式减持', '强制平仓', '爆仓', 'st风险', '退市风险',
        '暂停上市', '终止上市', '重大诉讼', '实控人失联', '资金占用', '违规担保',
    )
    assert pl.STOCK_SOFT == (
        '减持', '问询函', '警示函', '监管函', '质押', '亏损', '预亏', '裁员',
        '高管辞职', '高管离职', '解禁', '定增', '再融资', '关联交易', '变更会计师',
    )
    assert pl.STOCK_NOISE == ('业绩说明会', '调研', '回复关注函', '补充公告', '更正公告',
                              '摘要', '英文版')


def test_word_tables_are_forwarded_config_aliases():
    """服务里的三份词表是配置数据的转发别名，不是第二份拷贝。"""
    assert CRITICAL_WORDS is pl.STOCK_CRITICAL
    assert SOFT_WORDS is pl.STOCK_SOFT
    assert NOISE_WORDS is pl.STOCK_NOISE
    assert pl.lexicon_for() is pl.STOCK_LEXICON
    assert classify('立案') == pl.classify('立案', pl.STOCK_LEXICON)
    assert news_watch_service._TIER_ORDER is pl.TIER_ORDER
    assert pl.TIER_ORDER[pl.TIER_CRITICAL] < pl.TIER_ORDER[pl.TIER_SOFT]


# ── 1a. 政策口径分级与降噪 ─────────────────────────────────────────

def test_policy_critical_and_soft_tiers():
    assert classify('央行宣布降准0.5个百分点', policy=True) == ('critical', ['降准'])
    tier, words = classify('国常会部署加快专项债发行', policy=True)
    assert tier == 'critical' and '国常会' in words and '专项债' in words
    assert classify('证监会就量化交易征求意见', policy=True) == ('soft', ['征求意见'])
    assert classify('监管部门约谈平台企业', policy=True)[0] == 'soft'


def test_policy_noise_reduction_but_critical_overrides():
    # 二手解读/例行发布会：信息已消化 → 不打扰
    assert classify('政策解读：一季度货币政策执行报告', policy=True) == ('none', [])
    assert classify('例行新闻发布会介绍国民经济运行情况', policy=True) == ('none', [])
    # 弱词 + 噪声词 → 仍降为 none（降噪优先于 soft）
    assert classify('关于《私募管理办法》的政策解读', policy=True) == ('none', [])
    # 强词压过噪声词：『图解降准』是真政策，不是科普
    assert classify('【一图读懂】央行降准落地', policy=True) == ('critical', ['降准'])


# ── 1b. 行业口径分级与降噪（含别名解析）────────────────────────────

def test_industry_tiers_and_sector_alias_resolution():
    assert classify('某半导体厂被列入实体清单', sector='半导体')[0] == 'critical'
    assert classify('某半导体厂被列入实体清单', sector='芯片')[0] == 'critical'   # 别名
    assert classify('光伏龙头宣布扩产', sector='新能源') == ('soft', ['扩产'])
    assert classify('某药企集采落标', sector='医药')[0] == 'critical'
    assert classify('白酒企业提价', sector='白酒')[0] == 'soft'
    assert classify('猪瘟疫情扩散', sector='养殖') == ('critical', ['猪瘟', '疫情'])
    # 板块名规范化：后缀/大小写/空白
    assert pl.resolve_sector('半导体板块') == '半导体'
    assert pl.resolve_sector('光伏概念') == '新能源'
    assert pl.resolve_sector(' ai ') == 'AI'
    assert pl.normalize_sector('新能源汽车产业链') == '新能源汽车'


def test_industry_noise_is_downgraded_but_critical_wins():
    # 论坛纪要/投资者关系活动：行业口径的噪声词 → none
    assert classify('半导体设备投资论坛纪要', sector='半导体') == ('none', [])
    # 强词压过噪声词
    assert classify('半导体论坛纪要：曝某厂出口管制加码', sector='半导体')[0] == 'critical'


def test_unregistered_sector_falls_back_to_stock_lexicon():
    """未登记板块回落到个股口径——绝不返回空词表（空词表会把新闻全判 none）。"""
    assert pl.resolve_sector('未登记板块') == ''
    assert pl.industry_lexicon('未登记板块') is None
    assert pl.lexicon_for('未登记板块') is pl.STOCK_LEXICON
    assert classify('实控人收到证监会立案告知书', sector='未登记板块')[0] == 'critical'


def test_sector_scan_can_opt_into_stock_risk_words():
    """行业扫描默认只看行业词；需要同时抓个股级风险词时 include_stock=True。"""
    assert classify('实控人收到证监会立案告知书', sector='半导体') == ('none', [])
    assert classify('实控人收到证监会立案告知书', sector='半导体',
                    include_stock=True) == ('critical', ['立案'])
    lex = pl.lexicon_for('半导体', include_stock=True)
    assert lex.critical[:len(pl.STOCK_CRITICAL)] == pl.STOCK_CRITICAL


# ── 2. 词表是配置数据：扩行业只加条目 ──────────────────────────────

def test_new_industry_is_pure_data():
    """register_industry 加一条 → classify 立刻可用，不改任何判定代码。"""
    lex = pl.register_industry('船舶', critical=('订单取消', '交付延迟'),
                               soft=('新船订单', '造船价'))
    try:
        assert pl.resolve_sector('船舶') == '船舶'
        assert pl.resolve_sector('船舶板块') == '船舶'
        assert pl.industry_lexicon('船舶') is lex
        assert classify('某船厂交付延迟', sector='船舶') == ('critical', ['交付延迟'])
        assert classify('船厂新船订单落地', sector='船舶') == ('soft', ['新船订单'])
        # 没登记的词不会凭空命中（判定路径里没有板块 if 分支）
        assert classify('某船厂扩产', sector='船舶') == ('none', [])
    finally:
        pl.INDUSTRY_LEXICONS.pop('船舶', None)
    # 注销后回到「未登记 → 回落个股口径」
    assert pl.resolve_sector('船舶') == ''
    assert classify('某船厂交付延迟', sector='船舶') == ('none', [])


def test_registry_accepts_direct_dict_entry():
    """注册表就是普通字典：直接塞一条 Lexicon 也生效（配置可来自 YAML/JSON）。"""
    pl.INDUSTRY_LEXICONS['零售'] = pl.Lexicon(
        'industry:零售', ('关店潮',), ('开店计划',), pl.INDUSTRY_NOISE)
    try:
        # 与 SECTOR_ALIASES['零售'] → '消费' 的别名并存时，已登记的 canonical 键优先
        assert pl.resolve_sector('零售') == '零售'
        assert classify('某连锁品牌关店潮', sector='零售')[0] == 'critical'
        assert classify('某连锁品牌开店计划落地', sector='零售') == ('soft', ['开店计划'])
    finally:
        pl.INDUSTRY_LEXICONS.pop('零售', None)
    assert pl.resolve_sector('零售') == '消费'   # 摘掉后回到别名


def test_every_registered_industry_is_driven_by_its_config():
    """注册表里每条词表都真在驱动判定：逐板块逐词验证，没有旁路分支。"""
    for key, lex in pl.INDUSTRY_LEXICONS.items():
        assert isinstance(lex, pl.Lexicon)
        assert lex.name == 'industry:%s' % key
        assert lex.critical and lex.soft
        assert lex.noise                               # 通用行业噪声已并入
        for w in lex.critical:
            tier, words = classify('受%s影响' % w, sector=key)
            assert tier == 'critical' and w in words, (key, w, tier)
        soft_grades = [classify('受%s影响' % w, sector=key)[0] for w in lex.soft]
        assert 'soft' in soft_grades, (key, soft_grades)


def test_merge_dedups_and_keeps_declared_order():
    a = pl.Lexicon('a', ('降准', '降息'), noise=('解读',))
    b = pl.Lexicon('b', ('降息', '断供'), noise=('纪要',))
    m = a.merged(b)
    assert m.name == 'a+b'
    assert m.critical == ('降准', '降息', '断供')      # 同词只留首次出现
    assert m.noise == ('解读', '纪要')
    assert a.critical == ('降准', '降息')              # 原词表不动
    assert b.extended(critical=('降息', '加息')).critical == ('降息', '断供', '加息')


def test_classify_accepts_mapping_lexicon():
    """外部配置（字典）可直接当词表注入；非法类型明确报错。"""
    lex = {'name': 'demo', 'critical': ['关店潮'], 'soft': ['开店'], 'noise': ['探店']}
    assert classify('某品牌关店潮', lex) == ('critical', ['关店潮'])
    assert classify('探店视频', lex) == ('none', [])
    assert pl.Lexicon.from_mapping('demo2', lex).critical == ('关店潮',)
    with pytest.raises(TypeError):
        classify('x', 123)


# ── 服务接线：注入词表 / 默认不变 ──────────────────────────────────

def _pos(symbols):
    class P:
        def get_all_positions(self, account):
            return [SimpleNamespace(symbol=s, shares_total=100) for s in symbols]
    return P()


class _News:
    def __init__(self, items):
        self._items = items

    def fetch_news(self, symbol, limit=20):
        return self._items.get(symbol, [])


class _Alerts:
    def __init__(self):
        self.seen = set()

    def record(self, symbol, title, words, tier):
        key = (symbol, title)
        if key in self.seen:
            return None
        self.seen.add(key)
        return {'symbol': symbol, 'title': title, 'tier': tier}


def _n(title, time='2026-10-20 09:30:00'):
    return {'title': title, 'time': time, 'source': 'cninfo', 'url': ''}


def _svc(items, sender=None, lexicon=None, sector=None, policy=False):
    return NewsWatchService(
        news_source=_News(items), alert_repo=_Alerts(),
        position_repo=_pos(('300750',)), sender=sender, interval_sec=60,
        lexicon=lexicon, sector=sector, policy=policy)


def test_service_default_keeps_stock_lexicon():
    """不注入任何口径：政策词不报（行为与初版逐字一致）。"""
    sent = []
    svc = _svc({'300750': [_n('央行宣布降准0.5个百分点')]},
               sender=lambda p: sent.append(p) or True)
    out = svc.scan(now=NOW)
    assert out['reported'] == 0 and sent == []
    assert svc._active_lexicon() is None


def test_service_uses_injected_lexicon():
    sent = []
    svc = _svc({'300750': [_n('某半导体厂被列入实体清单')]},
               sender=lambda p: sent.append(p) or True,
               lexicon=pl.industry_lexicon('半导体'))
    out = svc.scan(now=NOW)
    assert out['reported'] == 1
    assert sent and sent[0]['level'] == 'P0'
    assert '实体清单' in sent[0]['message']
    assert svc._active_lexicon() is pl.industry_lexicon('半导体')


def test_service_sector_and_policy_routes():
    """不注入词表时可按 sector / policy 选口径（候选池只读口同样生效）。"""
    by_policy = _svc({'300750': [_n('央行宣布降准0.5个百分点')]}, policy=True)
    assert by_policy.query_negative_news('300750', now=NOW)['tier'] == 'critical'
    by_sector = _svc({'300750': [_n('某半导体厂被列入实体清单')]}, sector='芯片')
    assert by_sector.query_negative_news('300750', now=NOW)['tier'] == 'critical'
    # 默认服务对同一批标题仍判 none（口径隔离）
    assert _svc({'300750': [_n('某半导体厂被列入实体清单')]}
                ).query_negative_news('300750', now=NOW)['tier'] == 'none'
