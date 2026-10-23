"""政策/宏观新闻来源（2026-10-21 政策盯盘闭环）：全市场财经新闻 → 统一 records

职责边界：**只取数 + 归一 + 去重**。不做分级、不落库、不发通知——
分级由 `policy_lexicon.classify(title, policy=True)` 承担（词表口径唯一），
路由与通知由上层（policy-scope-router / watch_engine）编排。

取数通道：`DataProviderManager.get_market_news()`——provider 层 `symbol` 为空即
**全市场财经新闻**（区别于 `get_news` 的个股新闻）。本模块**不直连 akshare**
（项目铁律 ADR-001：外部数据一律经统一数据访问层），akshare 只是 provider 内部实现。

fail-open 口径（**重要，调用方必读**）：
  · 取数失败 → `skipped=True` + `reason`，records=[]。这**不等于「无利空」**：
    只有 `skipped=False` 才代表「这次真的看过了」；失败时不能据此下"没有坏消息"的结论。
  · 源健康但无数据 → `skipped=False` + `empty=True`（诚实回答"确实没有"）。
  · 返回结构不可识别 / 记录全部缺标题 → 按**取数失败**处理（skipped=True）：
    宁可不判，也不把坏数据当成「没有坏消息」。

输出（dict，JSON 友好）：
  {
    'records': [{'title', 'time', 'source', 'url'}, ...],  # 去重后、按源顺序
    'skipped': bool,             # True = 本次没取到（失败），**不是**「无新闻」
    'empty': bool,               # True = 源健康但确实无数据
    'reason': str,               # skipped/empty 的原因；正常取到时为空串
    'provider': str,             # 本条数据实际来自哪个 provider（如 akshare）
    'attempted_sources': list,   # 降级链上实际尝试过的源（manager 透出）
    'fetched_at': str,           # 本次取数时间（ISO）
  }

用法：
    src = PolicyNewsSource()
    out = src.fetch(limit=50)
    if out['skipped']:
        ...  # 取数失败：本轮不做「无政策利空」判断（可下轮重试/降级提示）
    elif out['empty']:
        ...  # 确实没有新消息
    else:
        for rec in out['records']:
            tier, words = classify(rec['title'], policy=True)
"""
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger(__name__)

__all__ = ['PolicyNewsSource', 'DEFAULT_LIMIT', 'MAX_LIMIT']

#: 单次默认返回条数（源常见一次给几十~上百条，政策扫盘不需要全量）
DEFAULT_LIMIT = 50
#: 单次硬上限（防止调用方传超大值把整轮扫盘拖长）
MAX_LIMIT = 200

#: 归一字段的候选键（英文统一键优先，其次 akshare 中文列名；顺序即优先级）
_TITLE_KEYS = ('title', '新闻标题', '标题')
_TIME_KEYS = ('time', 'datetime', '发布时间', '时间', '日期')
_SOURCE_KEYS = ('source', '文章来源', '来源')
_URL_KEYS = ('url', '新闻链接', '链接')


def _default_manager():
    """默认数据源管理器（惰性 import：模块导入不拉起 qs_market_data 重依赖，也便于测试注入）。"""
    from qs_market_data.adapters.outbound.datasources import get_data_provider_manager
    return get_data_provider_manager()


def _text(value: Any) -> str:
    """任意值 → 去空白字符串；None / NaN / 空值 → ''（日期时间转 ISO）。"""
    if value is None:
        return ''
    if isinstance(value, float) and value != value:   # NaN
        return ''
    if hasattr(value, 'isoformat'):
        try:
            return str(value.isoformat()).strip()
        except Exception:   # noqa: BLE001 - 怪异对象退回 str
            pass
    text = str(value).strip()
    return '' if text.lower() in ('nan', 'nat', 'none') else text


def _pick(record: Dict[str, Any], keys: Tuple[str, ...]) -> str:
    for key in keys:
        text = _text(record.get(key))
        if text:
            return text
    return ''


def _limit(value: Any, default: int = DEFAULT_LIMIT) -> int:
    """条数归一：非法/非正数退回默认，超过硬上限截断。"""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if number <= 0:
        return default
    return min(number, MAX_LIMIT)


def _normalise(record: Dict[str, Any], provider: str) -> Optional[Dict[str, str]]:
    """单条原始记录 → {title,time,source,url}；缺标题返回 None（不可判定）。"""
    title = _pick(record, _TITLE_KEYS)
    if not title:
        return None
    return {
        'title': title,
        'time': _pick(record, _TIME_KEYS),
        'source': _pick(record, _SOURCE_KEYS) or provider,
        'url': _pick(record, _URL_KEYS),
    }


def _extract_records(data: Any) -> Tuple[Optional[List[Any]], str]:
    """从 manager 返回的 data 里剥出原始记录列表。

    Returns:
        (records, '')            解析成功（records 可能是空列表）
        (None, 不可识别原因)      结构不符——调用方按取数失败处理
    """
    if data is None:
        return None, '数据源返回 success 但 data 为空（契约不符）'

    if isinstance(data, list):
        return data, ''

    if isinstance(data, dict):
        if 'records' in data:
            records = data.get('records')
            if records is None:
                return [], ''
            if isinstance(records, list):
                return records, ''
            return None, 'data.records 不是列表（%s）' % type(records).__name__
        if any(key in data for key in _TITLE_KEYS):
            return [data], ''   # 单条记录直接给出
        return None, '返回结构不可识别（无 records 列表）'

    # MarketData 等对象：真实载荷在 .data 属性里（_try_providers 成功时不剥壳）
    payload = getattr(data, 'data', None)
    if payload is not None:
        return _extract_records(payload)

    return None, '返回结构不可识别（data 类型 %s）' % type(data).__name__


def _provider_errors_text(errors: Any, limit: int = 3) -> str:
    """provider_errors → 简短原因串（失败时给 reason 留证据，不吞掉失败源）。"""
    if not isinstance(errors, dict):
        return ''
    parts = []
    for name, reason in list(errors.items())[:limit]:
        text = _text(reason)
        if text:
            parts.append('%s=%s' % (_text(name), text[:200]))
    return '；'.join(parts)


class PolicyNewsSource:
    """全市场政策/宏观新闻来源（fail-open，失败如实标注 skipped）。

    Args:
        manager: 数据源管理器（默认惰性解析 DataProviderManager，测试可注入假实现）。
        limit: 单次默认返回条数（fetch(limit=...) 可覆盖）。
    """

    def __init__(self, manager: Any = None, limit: int = DEFAULT_LIMIT):
        self._manager = manager
        self._limit = _limit(limit)

    def fetch(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """取全市场财经新闻并归一。

        永不抛异常（fail-open）：失败返回 skipped=True + reason，records=[]。
        调用方**必须**先看 skipped 再决定是否把结果当作「无政策利空」。
        """
        cap = _limit(limit, self._limit)
        out: Dict[str, Any] = {
            'records': [],
            'skipped': False,
            'empty': False,
            'reason': '',
            'provider': '',
            'attempted_sources': [],
            'channel': 'policy',
            'fetched_at': datetime.now().isoformat(),
        }

        try:
            manager = self._manager if self._manager is not None else _default_manager()
        except Exception as exc:   # noqa: BLE001 - fail-open：源不可用不炸扫盘
            return self._skipped(out, '数据源不可用：%s: %s'
                                 % (type(exc).__name__, exc))

        # 政策口径优先（2026-10-21 实测修正）：全市场新闻源实际是个股/盘面快讯，
        # 政策浓度极低；数据引擎为此新增 get_policy_news（财联社电报优先）。
        # 政策方法不存在（旧数据引擎）或硬失败时才退全市场口径——健康但为空**不退**，
        # 否则会把盘面快讯灌进政策扫描（那是噪音，不是降级）。
        channel = 'policy'
        result = None
        fetch = getattr(manager, 'get_policy_news', None)
        if callable(fetch):
            try:
                result = fetch(self._limit)
            except Exception:   # noqa: BLE001 - 政策源异常 → 退全市场口径再判
                result = None
        if not (isinstance(result, dict) and result.get('success')):
            channel = 'market'
            try:
                result = manager.get_market_news()
            except Exception as exc:   # noqa: BLE001 - fail-open：取数异常不炸扫盘
                return self._skipped(out, '取数异常：%s: %s'
                                     % (type(exc).__name__, exc))
        out['channel'] = channel

        if not isinstance(result, dict):
            return self._skipped(out, '返回非 dict（%s）'
                                 % type(result).__name__)

        out['provider'] = _text(result.get('source'))
        attempted = result.get('attempted_sources')
        if isinstance(attempted, list):
            out['attempted_sources'] = [
                text for text in (_text(item) for item in attempted) if text
            ]

        if 'success' not in result:
            return self._skipped(out, '返回缺少 success 标记（契约不符）')
        if not result.get('success'):
            reason = _text(result.get('error')) or '数据源返回失败'
            detail = _provider_errors_text(result.get('provider_errors'))
            return self._skipped(out, reason + ('；' + detail if detail else ''))

        raw, shape_reason = _extract_records(result.get('data'))
        if raw is None:
            return self._skipped(out, shape_reason)

        records: List[Dict[str, str]] = []
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            record = _normalise(item, out['provider'])
            if record is None or record['title'] in seen:
                continue
            seen.add(record['title'])
            records.append(record)
            if len(records) >= cap:
                break

        if raw and not records:
            # 有原始记录却一条都归一不出来（全缺标题/结构不符）——不能当「无新闻」
            return self._skipped(out, '返回 %d 条记录均无法归一（缺标题）' % len(raw))

        out['records'] = records
        if not records:
            out['empty'] = True
            out['reason'] = '全市场新闻源健康但无数据'
        return out

    @staticmethod
    def _skipped(out: Dict[str, Any], reason: str) -> Dict[str, Any]:
        """失败口径：skipped=True（**不是**「无利空」），并留下去失败的证据。"""
        out['skipped'] = True
        out['empty'] = False
        out['reason'] = reason
        logger.warning('政策新闻取数失败（fail-open，skipped=true）', reason=reason)
        return out
