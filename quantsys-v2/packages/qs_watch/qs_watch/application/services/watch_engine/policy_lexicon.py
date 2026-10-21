"""词表配置中心（2026-10-21）：个股 / 政策 / 行业 三套分级词表 + 唯一分级实现

为什么单独成模块：词表是**配置数据**，不是散落在服务里的 if 分支。
  · 个股口径（默认）：STOCK_CRITICAL / STOCK_SOFT / STOCK_NOISE——与
    news_watch_service 初版（2026-10-20）词表**逐字一致**；classify() 不传词表时
    行为不变（既有用例就是契约）；
  · 政策口径：POLICY_CRITICAL / POLICY_SOFT / POLICY_NOISE；
  · 行业口径：INDUSTRY_LEXICONS[板块]——**加一个板块 = 往字典里加一条**，判定路径零改动。

分级规则（`_classify_with` 是唯一实现，三套词表共用同一套判定）：
  1) 命中噪声词**且**没有强词 → none（解读/纪要/转载这类已消化的内容不打扰）；
  2) 命中强词 → critical（可能直接破坏交易逻辑）；
  3) 命中弱词 → soft（需要关注但未必破坏逻辑）；
  4) 都没命中 → none。
「critical 压过噪声」是硬规则：『【图解】央行降准』仍判 critical。

扩展一个行业（两种等效写法，**都是加数据不是改代码**）：
    register_industry('船舶', critical=('订单取消', '交付延迟'), soft=('新船订单',))
    INDUSTRY_LEXICONS['船舶'] = Lexicon('industry:船舶', critical=(...), soft=(...))
之后 classify('某船厂交付延迟', lexicon=industry_lexicon('船舶')) 直接可用，
不需要在 classify 里加任何板块分支。
"""
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

__all__ = [
    'TIER_CRITICAL', 'TIER_SOFT', 'TIER_NONE', 'TIER_ORDER',
    'Lexicon', 'STOCK_CRITICAL', 'STOCK_SOFT', 'STOCK_NOISE', 'STOCK_LEXICON',
    'POLICY_CRITICAL', 'POLICY_SOFT', 'POLICY_NOISE', 'POLICY_LEXICON',
    'INDUSTRY_NOISE', 'INDUSTRY_LEXICONS', 'SECTOR_ALIASES',
    'normalize_sector', 'resolve_sector', 'industry_lexicon', 'register_industry',
    'lexicon_for', 'classify',
]

TIER_CRITICAL = 'critical'
TIER_SOFT = 'soft'
TIER_NONE = 'none'
#: 严重度排序（critical 压过 soft）；与 news_watch_service 取最高 tier 的口径同源
TIER_ORDER = {TIER_CRITICAL: 0, TIER_SOFT: 1}


def _words(raw) -> Tuple[str, ...]:
    """规范化词表：去空、去重、**保持声明顺序**（顺序决定命中词展示顺序，不排序）。"""
    out = []
    for w in raw or ():
        s = str(w or '').strip()
        if s and s not in out:
            out.append(s)
    return tuple(out)


@dataclass(frozen=True)
class Lexicon:
    """一套分级词表（纯数据；判定分支只看这三组词，不看板块名）。"""

    name: str
    critical: Tuple[str, ...] = ()
    soft: Tuple[str, ...] = ()
    noise: Tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, 'name', str(self.name))
        object.__setattr__(self, 'critical', _words(self.critical))
        object.__setattr__(self, 'soft', _words(self.soft))
        object.__setattr__(self, 'noise', _words(self.noise))

    # ── 判定（唯一实现的薄包装，逐字等同 classify(title, self)）──────────
    def classify(self, title: str) -> Tuple[str, list]:
        """标题分级：返回 (tier, [命中词])，tier ∈ critical|soft|none。"""
        return _classify_with(str(title or ''), self)

    # ── 组合/扩展（都产出**新**词表，原词表不动）──────────────────────
    def merged(self, *others: 'Lexicon') -> 'Lexicon':
        """按顺序合并多套词表（同词只留首次出现的位置）。"""
        rest = tuple(o for o in others if o is not None)
        if not rest:
            return self
        return Lexicon(
            '+'.join([self.name] + [o.name for o in rest]),
            self.critical + tuple(w for o in rest for w in o.critical),
            self.soft + tuple(w for o in rest for w in o.soft),
            self.noise + tuple(w for o in rest for w in o.noise),
        )

    def extended(self, *, critical=(), soft=(), noise=(), name=None) -> 'Lexicon':
        """在原词表上追加条目（行业扩容/临时加固用，不动原词表）。"""
        return Lexicon(name or (self.name + '+ext'),
                       self.critical + tuple(critical),
                       self.soft + tuple(soft),
                       self.noise + tuple(noise))

    @classmethod
    def from_mapping(cls, name: str, mapping: Mapping[str, Any]) -> 'Lexicon':
        """从配置字典（critical/soft/noise）构造词表——外部 YAML/JSON 可直接落地。"""
        m = mapping or {}
        return cls(name,
                   m.get('critical') or (),
                   m.get('soft') or (),
                   m.get('noise') or ())


def _coerce(lexicon) -> Lexicon:
    if isinstance(lexicon, Lexicon):
        return lexicon
    if isinstance(lexicon, Mapping):
        return Lexicon.from_mapping(str(lexicon.get('name') or 'custom'), lexicon)
    raise TypeError('lexicon 必须是 Lexicon 或 {critical,soft,noise} 字典，收到 %r'
                    % type(lexicon).__name__)


# ── 个股口径（默认；2026-10-20 初版词表逐字保留）────────────────────────
#: 强提醒词：可能直接破坏交易逻辑的事件
STOCK_CRITICAL = (
    '立案', '退市', '爆雷', '违规', '处罚', '罚款', '破产', '债务违约', '逾期',
    '巨亏', '商誉减值', '清仓式减持', '强制平仓', '爆仓', 'st风险', '退市风险',
    '暂停上市', '终止上市', '重大诉讼', '实控人失联', '资金占用', '违规担保',
)
#: 弱提醒词：需要关注但未必破坏逻辑
STOCK_SOFT = (
    '减持', '问询函', '警示函', '监管函', '质押', '亏损', '预亏', '裁员',
    '高管辞职', '高管离职', '解禁', '定增', '再融资', '关联交易', '变更会计师',
)
#: 噪声词：标题含这些时降权（业绩说明/回复类公告通常已消化）
STOCK_NOISE = ('业绩说明会', '调研', '回复关注函', '补充公告', '更正公告',
               '摘要', '英文版')

#: 个股默认词表（classify 不传词表时走它，行为与初版逐字一致）
STOCK_LEXICON = Lexicon('stock', STOCK_CRITICAL, STOCK_SOFT, STOCK_NOISE)


# ── 政策口径（2026-10-21）──────────────────────────────────────────
#: 政策强词：直接改交易规则/流动性/行业基本面的定调与管制
POLICY_CRITICAL = (
    # 货币/财政：影响全市场估值
    '降准', '降息', '加息', '上调准备金率', '下调准备金率', 'LPR', 'MLF',
    '逆回购', '特别国债', '专项债', '减税', '退税', '财政贴息',
    # 交易制度/监管：影响流动性
    '印花税', '注册制', '暂停IPO', 'IPO暂停', '退市新规', '减持新规',
    '两融', '转融通', '涨跌幅限制', 'T+0', '量化监管', '程序化交易新规',
    '保证金比例', '窗口指导',
    # 产业/贸易：影响行业基本面
    '出口管制', '实体清单', '加征关税', '反倾销', '反补贴', '制裁', '禁运',
    '稀土管制', '供给侧改革', '能耗双控', '限产', '国补', '以旧换新',
    '带量采购', '集采', '医保谈判', '限购', '限贷', '降首付', '保交楼',
    '收储', '抛储',
    # 定调会议：预期差最大的一类
    '政治局会议', '国常会', '中央经济工作会议', '政府工作报告',
)
#: 政策弱词：方向已知、力度待落地（需关注，不必立刻动手）
POLICY_SOFT = (
    '征求意见', '征求意见稿', '指导意见', '行动方案', '实施细则', '管理办法',
    '试点', '吹风会', '新闻发布会', '答记者问', '表态', '建议', '提案',
    '约谈', '风险提示', '降费', '手续费下调', '降门槛',
)
#: 政策噪声词：解读/纪要/转载类——信息已消化，价值在原文不在二手解读
POLICY_NOISE = (
    '解读', '一图读懂', '图解', '问答', '例行新闻发布会', '综述', '专题报道',
    '转载', '纪要', '培训', '研讨会', '论坛', '招聘',
)

POLICY_LEXICON = Lexicon('policy', POLICY_CRITICAL, POLICY_SOFT, POLICY_NOISE)


# ── 行业口径（2026-10-21）──────────────────────────────────────────
#: 行业通用噪声词（各板块默认并入；板块自己的 noise 排在前）
INDUSTRY_NOISE = (
    '科普', '招聘', '校园招聘', '展会', '论坛', '峰会', '纪要', '调研纪要',
    '投资者关系活动', '转载', '综述', '专题报道', '广告', '宣传片',
)


def _industry(key: str, *, critical=(), soft=(), noise=()) -> Lexicon:
    """构造行业词表：板块自带 noise 在前，通用行业噪声在后。"""
    return Lexicon('industry:%s' % key, critical, soft,
                   _words(noise) + INDUSTRY_NOISE)


#: 行业词表注册表：**加板块 = 加一条**（键即 canonical 板块名）
INDUSTRY_LEXICONS: Dict[str, Lexicon] = {
    '半导体': _industry(
        '半导体',
        critical=('断供', '出口管制', '实体清单', '制裁', '设备禁运',
                  '产能受限', '砍单', '库存高企'),
        soft=('涨价', '扩产', '国产替代', '验证通过', '中标', '投产', '去库存',
              '晶圆代工'),
    ),
    '新能源': _industry(
        '新能源',
        critical=('产能过剩', '价格战', '补贴退坡', '双反', '停产', '限产',
                  '召回', '起火'),
        soft=('扩产', '中标', '装机', '排产', '签约', '开工', '涨价', '新车型'),
    ),
    '医药': _industry(
        '医药',
        critical=('集采', '带量采购', '医保谈判', '降价', '临床失败', '召回',
                  '停产', 'FDA拒绝', '退市'),
        soft=('获批', '受理', '临床', '一致性评价', 'GMP', '中标', '授权合作'),
    ),
    '房地产': _industry(
        '房地产',
        critical=('爆雷', '违约', '停贷', '限购', '限贷', '降首付', '破产',
                  '退市', '重组'),
        soft=('松绑', '收储', '城中村改造', '拿地', '成交回暖', '保交楼'),
    ),
    '银行': _industry(
        '银行',
        critical=('降准', '降息', '不良率上升', '罚单', '接管', '资本充足率',
                  '挤兑'),
        soft=('息差', '信贷投放', '再贷款', '存款利率', '降费'),
    ),
    '券商': _industry(
        '券商',
        critical=('印花税', '暂停IPO', '罚单', '接管', '立案', '降费'),
        soft=('两融', '经纪', '投行', 'IPO受理', '并购重组'),
    ),
    '军工': _industry(
        '军工',
        critical=('制裁', '出口管制', '订单取消', '交付延迟', '事故'),
        soft=('订单', '列装', '定型', '试飞', '预研', '资产注入'),
    ),
    '消费': _industry(
        '消费',
        critical=('食品安全', '塑化剂', '召回', '罚款', '反腐'),
        soft=('提价', '涨价', '控货', '动销', '库存', '新渠道'),
    ),
    'AI': _industry(
        'AI',
        critical=('禁售', '出口限制', '断供', '算力受限', '数据安全审查'),
        soft=('招标', '大模型发布', '算力租赁', '扩容', '备案'),
    ),
    '农业': _industry(
        '农业',
        critical=('猪瘟', '疫情', '减产', '粮价', '禁运'),
        soft=('收储', '抛储', '猪价', '能繁母猪', '出栏', '种植面积'),
    ),
    '资源': _industry(
        '资源',
        critical=('矿难', '事故', '停产整顿', '限产', '安监', '环保督察'),
        soft=('复产', '长协价', '库存', '港口库存', '涨价'),
    ),
}

#: 板块别名 → canonical 键（行业口径的**数据入口**，不参与判定）
SECTOR_ALIASES: Dict[str, str] = {
    # 半导体
    '芯片': '半导体', '集成电路': '半导体', '晶圆': '半导体', '封测': '半导体',
    '存储': '半导体', '半导体设备': '半导体',
    # 新能源
    '光伏': '新能源', '锂电': '新能源', '锂电池': '新能源', '风电': '新能源',
    '储能': '新能源', '新能源汽车': '新能源', '新能源车': '新能源', '新能车': '新能源',
    # 医药
    '医药生物': '医药', '生物医药': '医药', '创新药': '医药', '医疗器械': '医药',
    '中药': '医药', 'CXO': '医药',
    # 房地产
    '地产': '房地产', '房地产开发': '房地产', '物业': '房地产',
    # 金融
    '银行股': '银行', '证券': '券商', '非银': '券商', '非银金融': '券商',
    # 军工
    '国防军工': '军工', '军贸': '军工',
    # 消费
    '白酒': '消费', '食品饮料': '消费', '家电': '消费', '零售': '消费',
    # AI
    '人工智能': 'AI', 'ai': 'AI', '算力': 'AI', '大模型': 'AI', 'AIGC': 'AI',
    '数据中心': 'AI',
    # 农业
    '农牧': '农业', '养殖': '农业', '猪': '农业', '种业': '农业', '禽': '农业',
    # 资源
    '煤炭': '资源', '有色': '资源', '有色金属': '资源', '稀土': '资源',
    '钢铁': '资源', '化工': '资源', '石油': '资源', '油气': '资源',
}

_SECTOR_SUFFIXES = ('产业链', '板块', '行业', '概念', '指数')


# ── 口径解析（全部是查表，没有板块 if 分支）────────────────────────────
def normalize_sector(sector: Optional[str]) -> str:
    """板块名规范化：去空白、去『板块/行业/概念/指数/产业链』后缀。"""
    s = ''.join(str(sector or '').split())
    for suffix in sorted(_SECTOR_SUFFIXES, key=len, reverse=True):
        if len(s) > len(suffix) and s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s


def resolve_sector(sector: Optional[str]) -> str:
    """板块名 → INDUSTRY_LEXICONS 的键；认不出返回 ''（调用方据此回落）。"""
    s = normalize_sector(sector)
    if not s:
        return ''
    if s in INDUSTRY_LEXICONS:
        return s
    canonical = SECTOR_ALIASES.get(s) or SECTOR_ALIASES.get(s.lower(), '')
    return canonical if canonical in INDUSTRY_LEXICONS else ''


def industry_lexicon(sector: Optional[str]) -> Optional[Lexicon]:
    """板块 → 行业词表；未登记返回 None（回落策略由调用方决定）。"""
    key = resolve_sector(sector)
    if not key:
        return None
    return INDUSTRY_LEXICONS.get(key)


def register_industry(sector: str, *, critical=(), soft=(), noise=()) -> Lexicon:
    """登记/覆盖一个板块词表——**扩展行业只加数据**，判定路径零改动。"""
    key = normalize_sector(sector)
    if not key:
        raise ValueError('板块名不能为空')
    lex = _industry(key, critical=critical, soft=soft, noise=noise)
    INDUSTRY_LEXICONS[key] = lex
    return lex


def lexicon_for(sector: Optional[str] = None, *, policy: bool = False,
                include_stock: bool = False) -> Lexicon:
    """按口径取词表（唯一入口）。

    · 只给 policy → 政策词表；
    · 只给 sector → 行业词表；**未登记板块回落到个股词表**（宁可沿用已验证口径，
      也不返回空词表——空词表会把该板块所有新闻判成 none，静默漏报）；
    · policy + sector → 政策在前、行业在后合并（去重、命中词顺序稳定）；
    · include_stock=True → 再并个股词表（行业扫描想同时抓个股级风险词时用）；
    · 什么都不给 → 个股词表（= classify 默认行为，逐字不变）。
    """
    parts = []
    if policy:
        parts.append(POLICY_LEXICON)
    if include_stock:
        parts.append(STOCK_LEXICON)
    lex = industry_lexicon(sector)
    if lex is not None:
        parts.append(lex)
    if not parts:
        return STOCK_LEXICON
    if len(parts) == 1:
        return parts[0]
    return parts[0].merged(*parts[1:])


# ── 分级（唯一实现；三套词表共用，扩行业不碰这里）──────────────────────
def _classify_with(title: str, lexicon: Lexicon) -> Tuple[str, list]:
    t = str(title or '')
    if (any(w in t for w in lexicon.noise)
            and not any(w in t for w in lexicon.critical)):
        return TIER_NONE, []
    hits = [w for w in lexicon.critical if w in t]
    if hits:
        return TIER_CRITICAL, hits
    hits = [w for w in lexicon.soft if w in t]
    if hits:
        return TIER_SOFT, hits
    return TIER_NONE, []


def classify(title: str, lexicon=None, *, sector: Optional[str] = None,
             policy: bool = False, include_stock: bool = False) -> Tuple[str, list]:
    """标题分级（统一入口）：返回 (tier, [命中词])，tier ∈ critical|soft|none。

    lexicon 显式给出（Lexicon 或 {critical,soft,noise} 字典）时优先；
    否则按 sector/policy 取词表；都不给 = 个股词表（与初版行为逐字一致）。
    """
    if lexicon is not None:
        return _classify_with(str(title or ''), _coerce(lexicon))
    return _classify_with(str(title or ''),
                          lexicon_for(sector, policy=policy,
                                      include_stock=include_stock))
