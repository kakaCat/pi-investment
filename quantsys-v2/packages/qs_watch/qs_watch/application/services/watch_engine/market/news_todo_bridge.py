"""消息 → P1 待办桥（REQ-261021194640-69b8 FR-3，卡 t-27e8c7）

职责边界：**只做分派**，不做消息抓取与分级（那是 news/policy 扫描服务的事）。
扫描服务把已分级的命中交给本桥，本桥把 **critical 命中持仓标的/板块** 转成
P1 待办（附证据）并唤醒 owner；soft 一律跳过（用户裁定 D-3：soft 只发卡）。

三条纪律：
1. **不抛错**：单条失败进 `errors`，不影响整轮扫描（扫描是主链路，建单是增益）；
2. **窗口内去重**：同标的存在未收敛的「消息类」待办时不再建（避免消息复读刷屏）；
3. **不猜数据**：缺 symbol/account 的命中记 skipped，不编造归属；证据只存摘要，
   不落原文全文（隐私最小化）。

依赖注入（全部端口）：`todo_service`（必填）、`todo_repo`（可选，去重查询用）、
`now_fn`（测试注入）。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

CRITICAL = 'critical'
LEVEL_P1 = 'P1'
ACTION_KIND = 'rule_change'
DEFAULT_SLA_SECONDS = 1800
DEFAULT_DUE_MINUTES = 30
DEDUP_SCAN_LIMIT = 500


class NewsTodoBridge:
    """把 critical 消息命中转成 P1 待办并触发 owner 唤醒。"""

    def __init__(self, todo_service: Any, *, todo_repo: Any = None,
                 now_fn: Any = None, sla_seconds: int = DEFAULT_SLA_SECONDS,
                 due_minutes: int = DEFAULT_DUE_MINUTES):
        self._todo_service = todo_service
        self._todo_repo = todo_repo
        self._now = now_fn or datetime.now
        self._sla_seconds = int(sla_seconds)
        self._due_minutes = int(due_minutes)

    # ── 唯一入口 ────────────────────────────────────────────

    def dispatch(self, alerts: Any) -> Dict[str, Any]:
        """分派一轮命中；永不抛错。返回 {created, skipped, errors}。"""
        created: List[int] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for alert in alerts or []:
            try:
                result = self._dispatch_one(alert)
                if result is None:
                    skipped.append(self._skip_of(alert, '已存在未收敛的消息待办'))
                    continue
                if isinstance(result, dict) and result.get('skipped'):
                    skipped.append(result)
                    continue
                created.append(getattr(result, 'id', None))
            except Exception as e:  # noqa: BLE001 - 单条失败不阻断扫描
                logger.error('消息待办创建失败（跳过该条，不阻断扫描）',
                             symbol=_symbol_of(alert), error=str(e))
                errors.append({'symbol': _symbol_of(alert), 'error': str(e)})
        if created or errors:
            logger.info('消息待办分派完成', created=len(created),
                        skipped=len(skipped), errors=len(errors))
        return {'created': created, 'skipped': skipped, 'errors': errors}

    # ── 单条分派 ────────────────────────────────────────────

    def _dispatch_one(self, alert: Any):
        tier = str(_get(alert, 'tier') or '').strip().lower()
        if tier != CRITICAL:
            return {'skipped': True, 'symbol': _symbol_of(alert),
                    'reason': '只有 critical 建待办（soft 发卡）'}
        symbol = _symbol_of(alert)
        if not symbol:
            return {'skipped': True, 'symbol': '', 'reason': '缺少标的，无法建待办'}
        if self._has_open_news_todo(symbol):
            return None
        account = str(_get(alert, 'account') or '').strip() or None
        now = self._now()
        evidence = {
            'source': str(_get(alert, 'source') or 'news'),
            'tier': tier,
            'alert_id': _get(alert, 'alert_id') or _get(alert, 'message_id'),
            'titles': list(_get(alert, 'titles') or _get(alert, 'title') or []),
            'words': list(_get(alert, 'words') or _get(alert, 'matched_terms') or []),
            'sector': _get(alert, 'sector'),
            'scanned_at': now.isoformat(),
        }
        return self._todo_service.create(
            symbol=symbol, level=LEVEL_P1, sla_seconds=self._sla_seconds,
            due_at=now + timedelta(minutes=self._due_minutes),
            account=account, action_kind=ACTION_KIND, evidence=evidence)

    def _has_open_news_todo(self, symbol: str) -> bool:
        """同标的是否已有未收敛的消息类待办（窗口内去重，不靠 DB 唯一约束）。"""
        if self._todo_repo is None:
            return False
        try:
            rows = self._todo_repo.list_pending(limit=DEDUP_SCAN_LIMIT) or []
        except Exception as e:  # noqa: BLE001 - 去重查询失败按「没有」处理（宁可多建一条）
            logger.warning('消息待办去重查询失败（按无重复处理）', error=str(e))
            return False
        bare = symbol.split('.')[0]
        for row in rows:
            if getattr(row, 'terminal', None):
                continue
            if str(getattr(row, 'action_kind', '') or '') != ACTION_KIND:
                continue
            if str(getattr(row, 'symbol', '') or '').split('.')[0] == bare:
                return True
        return False

    @staticmethod
    def _skip_of(alert: Any, reason: str) -> Dict[str, Any]:
        return {'skipped': True, 'symbol': _symbol_of(alert), 'reason': reason}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _symbol_of(alert: Any) -> str:
    raw = _get(alert, 'symbol') or ''
    return str(raw).strip()
