"""
市场风格检测服务（2026-09-03 真实化重写，task 312）

修复前：纯编造实现——硬编码 value=0.45/growth=0.70/cycle=0.35，异常回退
默认 'growth'/0.33，从未读取任何真实行情。审计判定为"壳层假实现"。

修复后：以【真实新浪行业板块截面】驱动风格判定。
  - 数据源：akshare ak.stock_sector_spot(indicator='新浪行业')，49 个行业当日涨跌幅
    （盘中=实时截面；盘后/凌晨=最近一个交易日的收盘截面）。
  - 映射：显式行业→风格桶表（value/growth/cycle + 排除混合题材类），映射规则透明可审计，
    归类依据写于各桶常量注释。无法归类的行业（次新股/开发区/综合等）不计分但统计覆盖率。
  - 分数：桶内行业涨跌幅中位数 → 相对最弱桶平移 → 归一化份额（与旧契约 scores 语义一致）。
    三桶分化不足 0.3 个百分点 → 真实"无显著分化"，返回 style='unknown'/conf=0（真实观测，非降级）。
  - 降级：新浪数据拉取失败 → 回退读 DB 最近真实落库行；DB 亦无真实行 → 显式 degraded
    （style='unknown' + confidence=0 + indicators.degraded=True + error 原因），
    绝不回退到编造的 growth/0.33。
  - lookback_days 参数保留（API 兼容）：当前数据地基仅支持"当日/最近收盘截面"，
    多日窗口需行业历史序列补齐后接入（与 regime 判定同类口径限制，已在 indicators.basis 注明），
    不假装使用 60 日窗口。

响应契约键保持不变：style / confidence / scores / indicators / recommended_factors / detection_date
（下游 strategy_rotation_engine、market_style_async 路由均按此消费，容忍 'unknown'/'degraded'）。
"""
from typing import Any, Dict, List, Optional
from datetime import datetime, date
import structlog

logger = structlog.get_logger(__name__)


# ============================================================
# 风格桶定义与显式映射（透明、可审计）
# ============================================================

STYLE_VALUE = 'value'      # 价值风格
STYLE_GROWTH = 'growth'    # 成长风格
STYLE_CYCLE = 'cycle'      # 周期风格

# 风格对应的推荐因子（供下游策略配置参考）
STYLE_FACTORS = {
    STYLE_VALUE: ['pe', 'pb', 'dividend_yield', 'debt_ratio'],
    STYLE_GROWTH: ['roe', 'revenue_growth', 'macd', 'momentum'],
    STYLE_CYCLE: ['rsi', 'volume', 'bollinger', 'macd']
}

# 无显著分化判定阈值（百分点）：三桶涨跌幅中位数极差小于该值 → 真实无主导风格
MIN_DIFFERENTIATION_PCT = 0.3

# ------------------------------------------------------------
# 新浪行业(49) → 风格桶 显式映射
# 归类原则：
#   value  = 金融/地产/公用/必选消费/红利防御（低估值、稳定现金流）
#   growth = 科技(电子/传媒)/医药/高端制造/新能源设备（高成长弹性）
#   cycle  = 资源/材料/强周期制造/农业（景气周期驱动）
# 排除(不计分，仅覆盖率)：混合或无明确风格归属的题材类板块
# ------------------------------------------------------------
VALUE_BOARDS = {
    '金融行业', '房地产', '电力行业', '公路桥梁', '供水供气', '交通运输',
    '酿酒行业', '食品行业', '家电行业', '商业百货', '酒店旅游', '服装鞋类',
}
GROWTH_BOARDS = {
    '电子信息', '电子器件', '传媒娱乐', '医疗器械', '生物制药', '仪器仪表',
    '飞机制造', '发电设备', '环保行业',
}
CYCLE_BOARDS = {
    '玻璃行业', '船舶制造', '纺织行业', '纺织机械', '钢铁行业', '化工行业',
    '化纤行业', '家具行业', '机械行业', '建筑建材', '煤炭行业', '农林牧渔',
    '农药化肥', '塑料制品', '水泥行业', '石油行业', '陶瓷行业', '印刷包装',
    '有色金属', '造纸行业', '摩托车', '汽车制造', '电器行业',
}
EXCLUDED_BOARDS = {
    '开发区', '次新股', '其它行业', '综合行业', '物资外贸',
}

# 行业名 → 桶 的反查表（覆盖 49 个新浪行业；校验见 tests）
BOARD_STYLE_MAP: Dict[str, str] = {}
for _b in VALUE_BOARDS:
    BOARD_STYLE_MAP[_b] = STYLE_VALUE
for _b in GROWTH_BOARDS:
    BOARD_STYLE_MAP[_b] = STYLE_GROWTH
for _b in CYCLE_BOARDS:
    BOARD_STYLE_MAP[_b] = STYLE_CYCLE
# EXCLUDED_BOARDS 不入映射表，计入 unmapped


# ============================================================
# 纯计算函数（无 IO，可单测；detector 与 market_style_update_job 共用）
# ============================================================

def compute_style_from_boards(boards: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    由真实行业板块涨跌幅计算当日市场风格（纯函数，不访问网络/DB）。

    Args:
        boards: [{'name': '金融行业', 'change_pct': -1.0559}, ...]
                change_pct 单位 = 百分点（新浪行业 涨跌幅 列原生值）。

    Returns: 完整响应契约 dict（与 MarketStyleDetector.detect_market_style 一致）
        style: value/growth/cycle/unknown（unknown=真实无显著分化 或 数据不足）
        confidence / scores / recommended_factors / indicators / detection_date
        indicators 含：映射明细 bucket_members、桶中位涨跌幅 bucket_medians、
        coverage（覆盖率）、basis（'当日截面'）、degraded 等。
    """
    detection_date = date.today().isoformat()
    if not boards:
        return _degraded_result('行业板块数据为空，无法检测市场风格', detection_date)

    # 1. 归桶（统计覆盖率）
    bucket_members: Dict[str, List[str]] = {STYLE_VALUE: [], STYLE_GROWTH: [], STYLE_CYCLE: []}
    bucket_pcts: Dict[str, List[float]] = {STYLE_VALUE: [], STYLE_GROWTH: [], STYLE_CYCLE: []}
    unmapped: List[str] = []
    for b in boards:
        name = str(b.get('name', '')).strip()
        pct = _f(b.get('change_pct'))
        if not name or pct is None:
            unmapped.append(name or '<无名>')
            continue
        style = BOARD_STYLE_MAP.get(name)
        if style is None:
            unmapped.append(name)
            continue
        bucket_members[style].append(name)
        bucket_pcts[style].append(pct)

    mapped_total = sum(len(v) for v in bucket_members.values())
    total = mapped_total + len(unmapped)
    coverage = round(mapped_total / total, 4) if total else 0.0

    # 2. 桶内中位涨跌幅（对极端板块抗噪）
    raw: Dict[str, float] = {}
    bucket_medians: Dict[str, Optional[float]] = {}
    for style in (STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE):
        pcts = bucket_pcts[style]
        if not pcts:
            raw[style] = float('nan')
            bucket_medians[style] = None
        else:
            med = _median(pcts)
            raw[style] = med
            bucket_medians[style] = round(med, 4)

    # 3. 风格判定：极差不足 → 真实无显著分化；否则相对最弱桶平移后归一化
    valid = [raw[s] for s in (STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE)
             if raw[s] == raw[s]]  # 过滤 NaN（空桶）
    if len(valid) < 2 or len(valid) < 3:
        # 空桶过多：数据不足以区分三风格 → 真实 unknown
        return {
            'style': 'unknown',
            'confidence': 0.0,
            'scores': {STYLE_VALUE: 0.0, STYLE_GROWTH: 0.0, STYLE_CYCLE: 0.0},
            'indicators': {
                'basis': '当日截面',
                'bucket_members': bucket_members,
                'bucket_medians': bucket_medians,
                'unmapped': unmapped,
                'coverage': coverage,
                'boards_total': total,
                'mapped_total': mapped_total,
                'degraded': False,
                'note': '有效行业覆盖不足（存在空风格桶），无显著主导风格',
                'detection_date': detection_date,
            },
            'recommended_factors': [],
            'detection_date': detection_date,
        }

    span = max(valid) - min(valid)
    if span < MIN_DIFFERENTIATION_PCT:
        # 真实无显著分化：非降级，是"当日无明显风格"的真实观测
        return {
            'style': 'unknown',
            'confidence': 0.0,
            'scores': {STYLE_VALUE: 0.0, STYLE_GROWTH: 0.0, STYLE_CYCLE: 0.0},
            'indicators': {
                'basis': '当日截面',
                'bucket_members': bucket_members,
                'bucket_medians': bucket_medians,
                'unmapped': unmapped,
                'coverage': coverage,
                'boards_total': total,
                'mapped_total': mapped_total,
                'degraded': False,
                'note': f'三风格分化不足 {MIN_DIFFERENTIATION_PCT}pp，无显著主导风格（真实观测）',
                'detection_date': detection_date,
            },
            'recommended_factors': [],
            'detection_date': detection_date,
        }

    floor = min(raw[s] for s in (STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE)
                if raw[s] == raw[s])
    shifted = {s: (raw[s] - floor) for s in (STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE)
               if raw[s] == raw[s]}
    total_shift = sum(shifted.values())
    scores = {s: round(shifted[s] / total_shift, 4) for s in shifted} if total_shift > 0 else {}
    dominant = max(shifted, key=shifted.get)
    confidence = scores.get(dominant, 0.0)

    indicators = {
        'basis': '当日截面',
        'bucket_members': bucket_members,
        'bucket_medians': bucket_medians,
        'unmapped': unmapped,
        'coverage': coverage,
        'boards_total': total,
        'mapped_total': mapped_total,
        'method': '新浪行业当日涨跌幅 桶内中位数 → 相对最弱桶平移归一化 → argmax',
        'degraded': False,
        'detection_date': detection_date,
    }

    result = {
        'style': dominant,
        'confidence': round(confidence, 4),
        'scores': scores,
        'indicators': indicators,
        'recommended_factors': STYLE_FACTORS[dominant],
        'detection_date': detection_date,
    }
    return result


def _degraded_result(error: str, detection_date: Optional[str] = None) -> Dict[str, Any]:
    """显式降级结果：绝不伪装成真实检测（style=unknown, confidence=0, degraded=True + 原因）"""
    return {
        'style': 'unknown',
        'confidence': 0.0,
        'scores': {STYLE_VALUE: 0.0, STYLE_GROWTH: 0.0, STYLE_CYCLE: 0.0},
        'indicators': {
            'basis': '当日截面',
            'degraded': True,
            'error': error,
            'detection_date': detection_date or date.today().isoformat(),
        },
        'recommended_factors': [],
        'detection_date': detection_date or date.today().isoformat(),
    }


# ============================================================
# 数据拉取（新浪行业截面）
# ============================================================

def fetch_sina_sector_boards() -> Optional[List[Dict[str, Any]]]:
    """
    拉取新浪 49 行业当日/最近收盘截面（akshare，~0.1s）。
    失败/空返回 None（由调用方走 DB 回退或显式降级）。
    """
    try:
        import akshare as ak
    except Exception as e:  # pragma: no cover
        logger.error(f"akshare import failed: {e}")
        return None
    try:
        df = ak.stock_sector_spot(indicator='新浪行业')
    except Exception as e:
        logger.error(f"新浪行业数据拉取失败: {e}")
        return None
    if df is None or df.empty:
        return None
    if '板块' not in df.columns or '涨跌幅' not in df.columns:
        logger.error(f"新浪行业返回列异常: {list(df.columns)}")
        return None
    boards = []
    for _, row in df.iterrows():
        boards.append({'name': str(row['板块']).strip(), 'change_pct': _f(row['涨跌幅'])})
    boards = [b for b in boards if b['name'] and b['change_pct'] is not None]
    if not boards:
        return None
    return boards


class MarketStyleDetector:
    """市场风格检测器（真实数据驱动）

    构造签名保持不变（kline_repo/stock_repo 保留兼容；engine/route 裸构造可用）。
    """

    # 类级常量引用（兼容既有调用方/单测的 detector.STYLE_* / detector.STYLE_FACTORS 用法）
    STYLE_VALUE = STYLE_VALUE
    STYLE_GROWTH = STYLE_GROWTH
    STYLE_CYCLE = STYLE_CYCLE
    STYLE_FACTORS = STYLE_FACTORS

    def __init__(self, kline_repo=None, stock_repo=None):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo

    def detect_market_style(self, lookback_days: int = 60) -> Dict:
        """
        检测市场风格。

        数据路径（优先级）：
          1) DB 最近【真实】落库行（fast path：无网络，engine/route 同步调用不 hang）
             —— 由 market_style_update_job 每交易日收盘后写库；命中即返回真实历史行
          2) DB 无真实行（如从未跑过 job）→ 实时拉取新浪行业截面真实计算（不落库）
          3) 两者皆失败/不可用 → 显式 degraded（indicators.degraded=True + error），不编造

        lookback_days：API 兼容参数。当前数据地基为"当日/最近收盘截面"（indicators.basis），
        不假装使用多日窗口；多日趋势待行业历史序列补齐后接入。

        Returns: 契约 dict（style/confidence/scores/indicators/recommended_factors/detection_date）
        """
        # 1. DB 最近真实落库行（收盘 job 已写库 → 无网络 fast path）
        db_row = self._read_latest_db_row()
        if db_row:
            return db_row

        # 2. 实时真实计算（仅当 DB 从未有真实落库时才走网络）
        boards = fetch_sina_sector_boards()
        if boards:
            result = compute_style_from_boards(boards)
            if not result['indicators'].get('degraded'):
                logger.info(
                    "market_style_detect",
                    source='sina_sector_spot(实时回退, DB无真实行)',
                    style=result['style'],
                    confidence=result['confidence'],
                )
                return result
            # 空数据走 compute 返回的 degraded 也接受（含原因）
            return result

        # 3. 显式降级
        logger.warning("market_style_detect degraded: DB 无真实行且新浪拉取失败")
        return _degraded_result('DB 无真实市场风格记录且新浪行业数据拉取失败')

    # ---------- DB 回退 ----------

    def _read_latest_db_row(self) -> Optional[Dict[str, Any]]:
        """读 market_style_state 最近【真实】落库行（style∈三风格 且 confidence>0）。"""
        try:
            from adapters.outbound.repositories.market_style_repository import (
                MarketStyleORMRepository,
            )
            repo = MarketStyleORMRepository()
            row = repo.get_market_style()  # 按 trade_date desc 取最新
        except Exception as e:
            logger.warning(f"读取 market_style_state 失败: {e}")
            return None
        if not row:
            return None
        style = row.get('style')
        confidence = row.get('confidence') or 0.0
        if style not in (STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE) or confidence <= 0:
            # 忽略历史假行（如 2026-06-02 unknown/0.0）——那不是真实检测结果
            return None
        metrics = row.get('metrics') or {}
        indicators = dict(metrics.get('indicators') or {})
        indicators.setdefault('basis', '当日截面')
        indicators.setdefault('source', 'db_market_style_state')
        indicators.setdefault('db_trade_date', row.get('trade_date'))
        indicators.setdefault('degraded', False)
        indicators.setdefault('note', '来自 DB 最近落库行（job 每日收盘后写库）')
        return {
            'style': style,
            'confidence': float(confidence),
            'scores': metrics.get('scores') or {s: 0.0 for s in (STYLE_VALUE, STYLE_GROWTH, STYLE_CYCLE)},
            'indicators': indicators,
            'recommended_factors': STYLE_FACTORS.get(style, []),
            'detection_date': row.get('trade_date') or date.today().isoformat(),
        }


# ============================================================
# 工具函数
# ============================================================

def _f(value: Any) -> Optional[float]:
    """宽松转 float：None/空/非数值 → None"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace('%', '')
    if s in ('', '-', '--', 'None', 'nan'):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _median(values: List[float]) -> float:
    """中位数（不依赖 statistics，避免额外 import 开销无妨但显式实现更稳）"""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return (s[mid - 1] + s[mid]) / 2.0


__all__ = [
    'MarketStyleDetector',
    'compute_style_from_boards',
    'fetch_sina_sector_boards',
    'BOARD_STYLE_MAP',
    'VALUE_BOARDS',
    'GROWTH_BOARDS',
    'CYCLE_BOARDS',
    'EXCLUDED_BOARDS',
    'STYLE_VALUE',
    'STYLE_GROWTH',
    'STYLE_CYCLE',
    'STYLE_FACTORS',
    'MIN_DIFFERENTIATION_PCT',
]
