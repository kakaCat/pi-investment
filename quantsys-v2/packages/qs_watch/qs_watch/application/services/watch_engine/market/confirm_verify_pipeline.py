"""确认核验流水线（2026-10-20，机会闭环 M2）

为什么要有它：两段式伏击的「确认成立」只回答**价格形态**（站稳 / 收复 / 放量），
但形态成立 ≠ 值得跟。2026-10-20 的复盘里有两类反复出现的假信号：

  · 消息面：确认当天突发立案/减持/问询函，K 线形态是「利空出尽」前的反抽；
  · 盘口面：成交额/量比不足，大单占比却很高——挂着的大单是诱多话术；
  · 板块面：个股孤立异动（无同板块核心标的同步），多半是消息/游资/噪声。

本流水线把三道核验串起来，**只在 staged_break 确认成立后**跑一次：

    利空核验（news） → 流动性核验（liquidity） → 板块共振核验（resonance）

全过才放行到触发流水线（通知/待办）；任一项明确失败即判「假信号」，由引擎
归档 suppressed 样本进复盘序列，**不通知、不进摘要队列、不建待办**。

三态语义（三道核验服务同源，本流水线只做汇总，不重造判定）：

    passed  ok=True   通过
    failed  ok=False  明确不通过 → 整条流水线不通过（假信号）
    skipped ok=None   未核验（缺服务/缺数据/取数异常）→ **fail-open** 放行但如实标注

为什么 skipped 不拦：三道服务都按「数据缺失 ≠ 事实」设计（R-013）。把「没取到数」
当成「利空/枯竭/孤立」会因数据源抖动冤枉好信号；把「没取到数」当成「全过」又会
伪造核验结论。故 skipped 不阻断、但 `ConfirmVerifyResult.verified=False`，复盘侧
一眼能看出这条信号「核验不完整」，不会被当成「三项全过」。

执行顺序与短路：按 STAGE_ORDER **全部执行**（不在首个失败处短路）。理由：失败样本
的价值在于「三项各自什么结论」，只留第一项会让复盘无法区分「利空 + 流动性枯竭」
与「利空 + 孤立异动」。三道都是只读查询，无写副作用；staged_break 确认本身是低频
事件，全量执行的成本可接受。

依赖注入（全部可替身，单测零外呼）：
  · news_service      —— NewsWatchService（用 query_negative_news，候选池只读口径）
  · liquidity_service —— LiquidityCheckService（可给 thresholds 自动装配）
  · resonance_service —— SectorResonanceService（映射快照由 sidecar 预先 refresh）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

import structlog

from qs_watch.application.services.watch_engine.liquidity_check_service import (
    LiquidityCheckService,
)

logger = structlog.get_logger(__name__)

#: 核验阶段（顺序即执行顺序，也是 reason 的拼接顺序）
STAGE_NEWS = 'news'
STAGE_LIQUIDITY = 'liquidity'
STAGE_RESONANCE = 'resonance'
STAGE_ORDER: Tuple[str, ...] = (STAGE_NEWS, STAGE_LIQUIDITY, STAGE_RESONANCE)

STAGE_LABELS: Dict[str, str] = {
    STAGE_NEWS: '利空核验',
    STAGE_LIQUIDITY: '流动性核验',
    STAGE_RESONANCE: '板块共振核验',
}

VERDICT_PASSED = 'passed'
VERDICT_FAILED = 'failed'
VERDICT_SKIPPED = 'skipped'

__all__ = [
    'ConfirmVerifyPipeline',
    'ConfirmVerifyResult',
    'STAGE_LABELS',
    'STAGE_LIQUIDITY',
    'STAGE_NEWS',
    'STAGE_ORDER',
    'STAGE_RESONANCE',
    'StageVerdict',
    'VERDICT_FAILED',
    'VERDICT_PASSED',
    'VERDICT_SKIPPED',
]


@dataclass(frozen=True)
class StageVerdict:
    """单道核验的结论（纯数据，可直接进日志/归档 detail）。"""

    stage: str
    verdict: str
    reason: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return STAGE_LABELS.get(self.stage, self.stage)

    @property
    def ok(self) -> Optional[bool]:
        """True=通过 / False=明确失败 / None=未核验（skipped）"""
        if self.verdict == VERDICT_PASSED:
            return True
        if self.verdict == VERDICT_FAILED:
            return False
        return None

    @property
    def passed(self) -> bool:
        return self.verdict == VERDICT_PASSED

    @property
    def failed(self) -> bool:
        return self.verdict == VERDICT_FAILED

    @property
    def skipped(self) -> bool:
        return self.verdict == VERDICT_SKIPPED

    def to_dict(self) -> Dict[str, Any]:
        return {
            'stage': self.stage,
            'label': self.label,
            'verdict': self.verdict,
            'ok': self.ok,
            'reason': self.reason,
            'detail': dict(self.detail or {}),
        }


@dataclass(frozen=True)
class ConfirmVerifyResult:
    """确认核验汇总。

    ``passed`` 是流水线闸门（False=假信号，引擎归档不通知）；
    ``verified`` 是「三项都真的核验过」（False=有 skipped，结论不完整但 fail-open 放行）。
    两者**不是同义词**：skipped 时 passed=True 且 verified=False——复盘必须能区分
    「三项全过」与「没核验但没发现失败」。
    """

    symbol: str
    passed: bool
    stages: Tuple[StageVerdict, ...]
    reason: str

    @property
    def failures(self) -> Tuple[StageVerdict, ...]:
        return tuple(s for s in self.stages if s.failed)

    @property
    def skips(self) -> Tuple[StageVerdict, ...]:
        return tuple(s for s in self.stages if s.skipped)

    @property
    def failed_stages(self) -> Tuple[str, ...]:
        return tuple(s.stage for s in self.failures)

    @property
    def skipped_stages(self) -> Tuple[str, ...]:
        return tuple(s.stage for s in self.skips)

    @property
    def verified(self) -> bool:
        """三道都通过才算「完整核验」；任一 skipped 即 False。"""
        return all(s.passed for s in self.stages)

    @property
    def first_failure(self) -> Optional[StageVerdict]:
        failures = self.failures
        return failures[0] if failures else None

    @property
    def false_signal(self) -> bool:
        """是否判为假信号（= 有明确失败的核验项）。"""
        return not self.passed

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'passed': self.passed,
            'verified': self.verified,
            'false_signal': self.false_signal,
            'reason': self.reason,
            'failed_stages': list(self.failed_stages),
            'skipped_stages': list(self.skipped_stages),
            'stages': [s.to_dict() for s in self.stages],
        }


def _stage(stage: str, verdict: str, reason: str,
           detail: Optional[Mapping[str, Any]] = None) -> StageVerdict:
    return StageVerdict(stage=stage, verdict=verdict, reason=str(reason or ''),
                        detail=detail or {})


def _detail_of(value: Any) -> Dict[str, Any]:
    """把服务结果转成可归档的 dict（优先 to_dict / as_dict，Mapping 直接浅拷贝）。"""
    if value is None:
        return {}
    for name in ('to_dict', 'as_dict'):
        method = getattr(value, name, None)
        if callable(method):
            try:
                data = method()
                return dict(data) if isinstance(data, Mapping) else {'result': data}
            except Exception:  # noqa: BLE001 - detail 只是留痕，不能因此丢掉结论
                return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {'result': str(value)}


def _value_of(value: Any, *names: str, default: Any = None) -> Any:
    """从 Mapping 或对象属性取第一个非 None 值（兼容 dataclass 与 dict 两种结果）。"""
    if value is None:
        return default
    if isinstance(value, Mapping):
        for name in names:
            if value.get(name) is not None:
                return value.get(name)
        return default
    for name in names:
        item = getattr(value, name, None)
        if item is not None:
            return item
    return default


class ConfirmVerifyPipeline:
    """staged_break 确认后的三道核验（无状态；每标的调用一次 verify）。"""

    def __init__(self, news_service=None, liquidity_service=None,
                 resonance_service=None, *,
                 liquidity_thresholds: Optional[Mapping[str, Any]] = None,
                 liquidity_quote_provider: Optional[Callable[[str, Any], Any]] = None,
                 now_fn: Callable[[], datetime] = datetime.now) -> None:
        """
        Args:
            news_service: 提供 ``query_negative_news(symbol, now=...)`` 的只读服务；
                None = 该阶段 skipped（fail-open）。
            liquidity_service: 提供 ``check(quote)``；None 且给了 thresholds 时
                自动装配 LiquidityCheckService。
            resonance_service: 提供 ``verify(symbol, change_pct, quote=...)``；
                None = 该阶段 skipped。
            liquidity_thresholds: 流动性阈值（min_amount / min_volume_ratio /
                trap_big_order_ratio）；仅在 liquidity_service 未注入时用于自动装配。
            liquidity_quote_provider: ``(symbol, quote) -> quote|mapping``；用于把
                引擎的轻量 quote 补成含 amount/volume_ratio/big_order_ratio 的盘口视图。
                抛错按 skipped fail-open 处理。
            now_fn: 时钟注入（核验时间进 detail 与新闻 48h 窗口）。
        """
        self.news_service = news_service
        if liquidity_service is None and liquidity_thresholds is not None:
            liquidity_service = LiquidityCheckService(liquidity_thresholds)
        self.liquidity_service = liquidity_service
        self.resonance_service = resonance_service
        self.liquidity_quote_provider = liquidity_quote_provider
        self.now_fn = now_fn

    # ── 主入口 ──────────────────────────────────────────────

    def verify(self, symbol: Any, quote: Any = None,
               now: Optional[datetime] = None, *,
               change_pct: Optional[float] = None) -> ConfirmVerifyResult:
        """跑完三道核验，返回汇总（passed=False 即假信号，调用方归档不通知）。

        单阶段异常按 skipped fail-open 处理：三道核验都是旁路只读，任何一道自身
        故障都不应让盯盘信号全体失明；异常原文进 reason/detail 供复盘。
        """
        at = now or self.now_fn()
        sym = str(symbol or '').strip()
        stages = []
        for stage in STAGE_ORDER:
            try:
                stages.append(self._run_stage(
                    stage, sym, quote, at, change_pct=change_pct))
            except Exception as e:  # noqa: BLE001 - 单阶段异常 fail-open，不拦信号
                logger.warning('确认核验阶段异常（fail-open）', stage=stage,
                               symbol=sym, error=str(e))
                stages.append(_stage(
                    stage, VERDICT_SKIPPED,
                    '%s未完成（fail-open）：%s' % (STAGE_LABELS[stage], e),
                    {'error': str(e)}))

        failures = [s for s in stages if s.failed]
        skips = [s for s in stages if s.skipped]
        passed = not failures
        return ConfirmVerifyResult(
            symbol=sym,
            passed=passed,
            stages=tuple(stages),
            reason=self._compose_reason(passed, failures, skips),
        )

    # ── 三阶段 ──────────────────────────────────────────────

    def _run_stage(self, stage: str, symbol: str, quote: Any,
                   now: datetime, *, change_pct: Optional[float]) -> StageVerdict:
        if stage == STAGE_NEWS:
            return self._check_news(symbol, now)
        if stage == STAGE_LIQUIDITY:
            return self._check_liquidity(symbol, quote)
        return self._check_resonance(symbol, quote, change_pct)

    def _check_news(self, symbol: str, now: datetime) -> StageVerdict:
        service = self.news_service
        query = getattr(service, 'query_negative_news', None)
        if not callable(query):
            return _stage(STAGE_NEWS, VERDICT_SKIPPED,
                          '利空核验未装配（fail-open，不据此拦信号）')
        result = query(symbol, now=now) or {}
        detail = dict(result) if isinstance(result, Mapping) else {'result': result}
        if isinstance(result, Mapping) and result.get('skipped'):
            return _stage(
                STAGE_NEWS, VERDICT_SKIPPED,
                '利空查询未完成（fail-open）：%s' % (result.get('error') or '取数失败'),
                detail)
        if isinstance(result, Mapping) and result.get('has_negative'):
            tier = str(result.get('tier') or '')
            hits = result.get('hits') or []
            titles = [str(h.get('title') or '').strip()
                      for h in hits if isinstance(h, Mapping)]
            titles = [t for t in titles if t]
            tier_label = {'critical': '强利空', 'soft': '弱利空'}.get(tier, tier or '利空')
            evidence = '；'.join(titles[:3]) or '命中利空词表'
            return _stage(
                STAGE_NEWS, VERDICT_FAILED,
                '发现%s（%d 条命中）：%s' % (tier_label, len(hits), evidence),
                detail)
        checked = result.get('checked', 0) if isinstance(result, Mapping) else 0
        total = result.get('total', 0) if isinstance(result, Mapping) else 0
        return _stage(
            STAGE_NEWS, VERDICT_PASSED,
            '48h 内无突发利空（检查 %s/%s 条）' % (checked, total), detail)

    def _check_liquidity(self, symbol: str, quote: Any) -> StageVerdict:
        service = self.liquidity_service
        if service is None:
            return _stage(STAGE_LIQUIDITY, VERDICT_SKIPPED,
                          '流动性核验未装配（fail-open，不据此拦信号）')
        payload = quote
        if self.liquidity_quote_provider is not None:
            payload = self.liquidity_quote_provider(symbol, quote)
        if payload is None:
            return _stage(STAGE_LIQUIDITY, VERDICT_SKIPPED,
                          '流动性核验行情缺失（fail-open，不据此拦信号）')
        result = service.check(payload)
        detail = _detail_of(result)
        ok = _value_of(result, 'ok')
        reason = str(_value_of(result, 'reason', default='') or '')
        if ok is True:
            return _stage(STAGE_LIQUIDITY, VERDICT_PASSED, reason, detail)
        if ok is False:
            return _stage(STAGE_LIQUIDITY, VERDICT_FAILED, reason, detail)
        return _stage(STAGE_LIQUIDITY, VERDICT_SKIPPED, reason, detail)

    def _check_resonance(self, symbol: str, quote: Any,
                         change_pct: Optional[float]) -> StageVerdict:
        service = self.resonance_service
        checker = (getattr(service, 'verify', None)
                   or getattr(service, 'check', None))
        if not callable(checker):
            return _stage(STAGE_RESONANCE, VERDICT_SKIPPED,
                          '板块共振核验未装配（fail-open，不据此拦信号）')
        result = checker(symbol, change_pct, quote=quote)
        detail = _detail_of(result)
        passed = _value_of(result, 'passed', 'ok', 'resonance')
        reason = str(_value_of(result, 'reason', default='') or '')
        if passed is True:
            return _stage(STAGE_RESONANCE, VERDICT_PASSED, reason, detail)
        if passed is False:
            return _stage(STAGE_RESONANCE, VERDICT_FAILED, reason, detail)
        return _stage(STAGE_RESONANCE, VERDICT_SKIPPED, reason, detail)

    # ── reason ──────────────────────────────────────────────

    @staticmethod
    def _compose_reason(passed: bool, failures, skips) -> str:
        skipped_text = '、'.join(
            STAGE_LABELS.get(s.stage, s.stage) for s in skips)
        if passed:
            if not skips:
                return '确认核验通过：利空 / 流动性 / 板块共振全过'
            return ('确认核验通过（fail-open：%s未核验，不据此拦信号）'
                    % skipped_text)
        failed_text = '；'.join(
            '%s未通过——%s' % (s.label, s.reason or '未说明') for s in failures)
        reason = '确认核验未通过：%s' % failed_text
        if skips:
            reason += '；另有%s未核验（fail-open）' % skipped_text
        return reason
