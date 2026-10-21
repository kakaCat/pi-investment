"""市场环境闸（2026-10-20，盯盘确认核验管线的「环境」前置判定）

职责：接一份 MarketState 快照，按三维输出 blocked + reason：
  1) 指数涨跌     —— 系统性风险（暴跌）与过热（追高）两条边；
  2) 板块主线强度 —— 最强板块是否还有赚钱效应（无主线 = 环境不支持进攻）；
  3) 资金氛围     —— 情绪分 / 涨跌家数比是否偏冷（风险偏好不足）。

三条铁律（与既有市场门 `WatchEngine._check_market_gate` 同源）：
  · **纯判定**：无 I/O、无仓储、无时钟；同一份快照永远得到同一结论，可直接单测。
    取数由 IMarketStateProvider 适配器负责，本服务只认快照（ADR-001）。
  · **数据缺失 fail-open**：缺失的维度跳过，并在 decision.skipped（布尔）与
    decision.skipped_dimensions（具体维度）标注；绝不用 0 冒充事实（2026-09-11
    lessons：静默兜底会把缺陷伪装成事实，制造假信号）。
    部分字段缺失（如只有涨跌家数比、没有情绪分）仍用在场数据判定，缺项记入 missing。
  · **拦截语义 = 只记录不动作**：reason 是可直接进通知的中文一句话，不含买卖指令，
    结尾固定「本次信号只记录不动作」——引擎据此归档触发而不下单。

消费方式（引擎侧推荐）::

    blocked, reason = EnvironmentGateService().check(state)
    decision = EnvironmentGateService().evaluate(state)   # 需要 skipped/verdicts 时
"""
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from qs_watch.domain.watch.models import MarketState


#: 三个判定维度（顺序即 reason 的拼接顺序，保持通知文案稳定）
DIM_INDEX = "index"
DIM_SECTOR = "sector"
DIM_CAPITAL = "capital"
DIMENSIONS = (DIM_INDEX, DIM_SECTOR, DIM_CAPITAL)

DIMENSION_LABELS: Dict[str, str] = {
    DIM_INDEX: "指数涨跌",
    DIM_SECTOR: "板块主线强度",
    DIM_CAPITAL: "资金氛围",
}

#: 指数代码 → 人话名（通知里不出现裸代码；未知代码原样回退）
INDEX_LABELS: Dict[str, str] = {
    "000300.SH": "沪深300",
    "000001.SH": "上证指数",
    "399006.SZ": "创业板指",
    "000852.SH": "中证1000",
}

STATUS_OK = "ok"
STATUS_BLOCKED = "blocked"
STATUS_SKIPPED = "skipped"

STATUS_LABELS: Dict[str, str] = {
    STATUS_OK: "环境正常",
    STATUS_BLOCKED: "环境拦截",
    STATUS_SKIPPED: "数据缺失（fail-open 放行）",
}


@dataclass(frozen=True)
class EnvironmentGatePolicy:
    """环境闸阈值（纯值对象；改阈值不改代码）。

    默认值按「系统性风险日不接飞刀、无主线不进攻」的口径：
      · 指数跌幅 ≤ -1.5% 或涨幅 ≥ +3.0% → 拦截；
      · 最强板块涨幅 < +1.0% → 无主线，拦截；
      · 情绪分 < 30 或涨跌家数比 < 0.5 → 资金氛围偏冷，拦截。
    """

    #: 指数优先级：先看大盘（沪深300），无数据再逐级回退
    index_codes: Tuple[str, ...] = ("000300.SH", "000001.SH", "399006.SZ", "000852.SH")
    #: 指数跌幅阈值（含等于）：pct <= 该值 → 系统性风险拦截
    index_drop_pct: float = -1.5
    #: 指数涨幅阈值（含等于）：pct >= 该值 → 过热追高拦截
    index_surge_pct: float = 3.0
    #: 板块主线强度下限（含等于）：最强板块 pct < 该值 → 无主线拦截
    sector_min_mainline_pct: float = 1.0
    #: 情绪分下限（不含等于）：sentiment < 该值 → 偏冷
    sentiment_min: float = 30.0
    #: 涨跌家数比下限（不含等于）：ratio < 该值 → 偏冷
    advance_decline_min: float = 0.5

    def __post_init__(self) -> None:
        # 配置错误应当在构造时炸掉，而不是静默产出错误拦截（纯判定也要守住入参）
        if not self.index_codes:
            raise ValueError("index_codes 不能为空：环境闸至少要看一个指数")
        if self.index_drop_pct > 0:
            raise ValueError("index_drop_pct 必须 <= 0（跌幅阈值）")
        if self.index_surge_pct < 0:
            raise ValueError("index_surge_pct 必须 >= 0（涨幅阈值）")
        if self.advance_decline_min < 0:
            raise ValueError("advance_decline_min 必须 >= 0")


@dataclass(frozen=True)
class GateDimensionVerdict:
    """单维判定结果（纯数据，可直接进日志/JSON）。"""

    dimension: str
    status: str                 # ok | blocked | skipped
    reason: str = ""            # 仅 blocked 时有值；不含最终「只记录不动作」后缀
    value: Optional[float] = None
    detail: str = ""            # 人话细节（ok/skipped 也带，便于复盘）
    missing: Tuple[str, ...] = ()   # 该维度缺失的输入项（含部分缺失）

    @property
    def blocked(self) -> bool:
        return self.status == STATUS_BLOCKED

    @property
    def skipped(self) -> bool:
        return self.status == STATUS_SKIPPED

    @property
    def label(self) -> str:
        return DIMENSION_LABELS.get(self.dimension, self.dimension)

    @property
    def verdict(self) -> str:
        """status 别名（与 LiquidityCheckResult / SectorResonanceResult 同风格）。"""
        return self.status


@dataclass(frozen=True)
class EnvironmentGateDecision:
    """环境闸结论：blocked + reason 是主输出，skipped/missing/verdicts 是诚实标注。

    与同批核验服务（LiquidityCheckResult / SectorResonanceResult）共用一套消费口径：
      · ``verdict``：blocked | ok | skipped（整体三态）；
      · ``ok``：True=三维正常、False=被拦截、None=有维度因缺数据未判定（fail-open，
        绝不等于"通过"）；
      · ``skipped``：是否有维度因数据缺失被跳过；具体是哪些见 ``skipped_dimensions``。
    """

    blocked: bool
    reason: str
    skipped_dimensions: Tuple[str, ...] = ()   # 整体跳过的维度（数据缺失 → fail-open）
    missing: Tuple[str, ...] = ()              # 缺失的输入项（含部分缺失）
    verdicts: Tuple[GateDimensionVerdict, ...] = ()

    @property
    def is_blocked(self) -> bool:
        """blocked 的语义别名（消费方读法不一，给两种都稳）。"""
        return self.blocked

    @property
    def skipped(self) -> bool:
        """是否有维度因数据缺失被跳过（fail-open 的标注位）。"""
        return bool(self.skipped_dimensions)

    @property
    def verdict(self) -> str:
        """整体三态：blocked 优先，其次 skipped（有维度未判定），最后 ok。"""
        if self.blocked:
            return STATUS_BLOCKED
        if self.skipped:
            return STATUS_SKIPPED
        return STATUS_OK

    @property
    def label(self) -> str:
        return STATUS_LABELS.get(self.verdict, self.verdict)

    @property
    def ok(self) -> Optional[bool]:
        """三态：True=环境正常；False=拦截；None=有维度缺数据、无法完整判定。"""
        if self.blocked:
            return False
        if self.skipped:
            return None
        return True

    @property
    def fail_open(self) -> bool:
        """数据缺失时是否放行（本服务口径：放行但标注，不拦信号）。"""
        return self.skipped and not self.blocked

    @property
    def skipped_labels(self) -> Tuple[str, ...]:
        """skipped 维度的人话名（通知/日志用）。"""
        return tuple(DIMENSION_LABELS.get(d, d) for d in self.skipped_dimensions)

    def dimension_verdict(self, dimension: str) -> Optional[GateDimensionVerdict]:
        for item in self.verdicts:
            if item.dimension == dimension:
                return item
        return None

    def __bool__(self) -> bool:
        """`if decision:` 直接读作「是否拦截」，与 check() 的布尔位一致。"""
        return self.blocked

    def __iter__(self):
        """解包兼容：`blocked, reason = decision`（引擎既有市场门就是二元组）。"""
        yield self.blocked
        yield self.reason

    def as_tuple(self) -> Tuple[bool, str]:
        """(blocked, reason) 的显式形式（不想依赖解包时用）。"""
        return self.blocked, self.reason

    def as_dict(self) -> Dict[str, Any]:
        return {
            "blocked": self.blocked,
            "reason": self.reason,
            "verdict": self.verdict,
            "label": self.label,
            "ok": self.ok,
            "skipped": self.skipped,
            "fail_open": self.fail_open,
            "skipped_dimensions": list(self.skipped_dimensions),
            "skipped_labels": list(self.skipped_labels),
            "missing": list(self.missing),
            "verdicts": [
                {
                    "dimension": v.dimension,
                    "label": v.label,
                    "status": v.status,
                    "verdict": v.verdict,
                    "reason": v.reason,
                    "value": v.value,
                    "detail": v.detail,
                    "missing": list(v.missing),
                }
                for v in self.verdicts
            ],
        }

    def to_dict(self) -> Dict[str, Any]:
        """as_dict 别名（与同批核验服务的命名保持一致）。"""
        return self.as_dict()


class EnvironmentGateService:
    """三维环境闸（纯判定，无 I/O）。

    用法::

        svc = EnvironmentGateService()              # 默认阈值
        blocked, reason = svc.check(state)          # 与 WatchEngine._check_market_gate 同形
        decision = svc.evaluate(state)              # 需要 skipped/verdicts 时

    `state` 为 None / 空快照时 fail-open：blocked=False、reason=""，三维全标 skipped。
    """

    def __init__(self, policy: Optional[EnvironmentGatePolicy] = None):
        self.policy = policy or EnvironmentGatePolicy()

    # ── 对外入口 ─────────────────────────────────────────────
    def evaluate(self, state: Optional[MarketState]) -> EnvironmentGateDecision:
        """对一份市场快照求值（幂等、无副作用）。"""
        if state is None:
            verdicts = tuple(
                self._skip(dim, "无市场状态快照（fail-open 放行）")
                for dim in DIMENSIONS
            )
            return EnvironmentGateDecision(
                blocked=False, reason="", skipped_dimensions=tuple(DIMENSIONS),
                missing=(), verdicts=verdicts,
            )

        verdicts = (
            self._judge_index(state),
            self._judge_sector(state),
            self._judge_capital(state),
        )
        blocked_verdicts = [v for v in verdicts if v.blocked]
        skipped_dimensions = tuple(v.dimension for v in verdicts if v.skipped)
        missing = tuple(item for v in verdicts for item in v.missing)

        if not blocked_verdicts:
            # fail-open / 环境正常：reason 为空（与引擎既有市场门语义一致）
            return EnvironmentGateDecision(
                blocked=False, reason="", skipped_dimensions=skipped_dimensions,
                missing=missing, verdicts=verdicts,
            )

        # 多维度命中时逐条列出；结尾只出现一次「只记录不动作」，可直接进通知
        reason = "环境闸拦截：" + "；".join(v.reason for v in blocked_verdicts) \
                 + "——本次信号只记录不动作"
        return EnvironmentGateDecision(
            blocked=True, reason=reason, skipped_dimensions=skipped_dimensions,
            missing=missing, verdicts=verdicts,
        )

    def check(self, state: Optional[MarketState]) -> Tuple[bool, str]:
        """返回 (blocked, reason)，与 `WatchEngine._check_market_gate` 完全同形。"""
        decision = self.evaluate(state)
        return decision.blocked, decision.reason

    # ── 维度一：指数涨跌 ─────────────────────────────────────
    def _judge_index(self, state: MarketState) -> GateDimensionVerdict:
        policy = self.policy
        indices = getattr(state, "indices", None)
        if not isinstance(indices, dict):
            indices = {}
        for code in policy.index_codes:
            raw = indices.get(code) or {}
            pct = self._as_float(raw.get("change_pct")) if isinstance(raw, dict) else None
            if pct is None:
                continue
            label = INDEX_LABELS.get(code, code)
            detail = "%s %+.2f%%" % (label, pct)
            if pct <= policy.index_drop_pct:
                return GateDimensionVerdict(
                    DIM_INDEX, STATUS_BLOCKED, value=pct, detail=detail,
                    reason="%s 跌 %.2f%%（触线 %.2f%%），系统性风险日"
                           % (label, abs(pct), policy.index_drop_pct),
                )
            if pct >= policy.index_surge_pct:
                return GateDimensionVerdict(
                    DIM_INDEX, STATUS_BLOCKED, value=pct, detail=detail,
                    reason="%s 涨 %.2f%%（触线 +%.2f%%），过热追高保护"
                           % (label, pct, policy.index_surge_pct),
                )
            return GateDimensionVerdict(
                DIM_INDEX, STATUS_OK, value=pct, detail=detail,
            )
        return self._skip(
            DIM_INDEX,
            "指数快照缺失（%s 均无涨跌幅）%s"
            % ("/".join(policy.index_codes), self._degraded_hint(state)),
            missing=("index.change_pct",),
        )

    # ── 维度二：板块主线强度 ─────────────────────────────────
    def _judge_sector(self, state: MarketState) -> GateDimensionVerdict:
        policy = self.policy
        raw_sectors = getattr(state, "sectors", None)
        sectors: Dict[str, float] = {}
        for name, raw in (raw_sectors.items() if isinstance(raw_sectors, dict) else ()):
            pct = self._as_float(raw)
            if pct is not None:
                sectors[str(name)] = pct
        if not sectors:
            return self._skip(
                DIM_SECTOR,
                "板块强度快照为空%s" % self._degraded_hint(state),
                missing=("sector.pct",),
            )

        name, pct = max(sectors.items(), key=lambda kv: kv[1])
        up = sum(1 for value in sectors.values() if value > 0)
        detail = ("最强板块 %s %+.2f%%（需 ≥ %+.2f%%）；上涨板块 %d/%d"
                  % (name, pct, policy.sector_min_mainline_pct, up, len(sectors)))
        if pct < policy.sector_min_mainline_pct:
            return GateDimensionVerdict(
                DIM_SECTOR, STATUS_BLOCKED, value=pct, detail=detail,
                reason="板块无主线（最强 %s %+.2f%%，需 ≥ %+.2f%%），赚钱效应缺失"
                       % (name, pct, policy.sector_min_mainline_pct),
            )
        return GateDimensionVerdict(
            DIM_SECTOR, STATUS_OK, value=pct, detail=detail,
        )

    # ── 维度三：资金氛围 ─────────────────────────────────────
    def _judge_capital(self, state: MarketState) -> GateDimensionVerdict:
        policy = self.policy
        sentiment = self._as_float(getattr(state, "sentiment_score", None))
        if sentiment is None:
            # 情绪分缺失时用恐贪指数兜底（同一维度的替代口径，不是编造数据）
            sentiment = self._as_float(getattr(state, "fear_greed_index", None))
        ad_ratio = self._as_float(getattr(state, "advance_decline_ratio", None))

        missing: List[str] = []
        if sentiment is None:
            missing.append("capital.sentiment")
        if ad_ratio is None:
            missing.append("capital.advance_decline_ratio")
        if sentiment is None and ad_ratio is None:
            return self._skip(
                DIM_CAPITAL,
                "资金氛围字段均缺失（情绪分/涨跌家数比）%s" % self._degraded_hint(state),
                missing=tuple(missing),
            )

        detail_bits = []
        if sentiment is not None:
            detail_bits.append("情绪 %.1f" % sentiment)
        if ad_ratio is not None:
            detail_bits.append("涨跌家数比 %.2f" % ad_ratio)
        detail = "；".join(detail_bits)

        cold: List[str] = []
        if sentiment is not None and sentiment < policy.sentiment_min:
            cold.append("情绪 %.1f < %.1f" % (sentiment, policy.sentiment_min))
        if ad_ratio is not None and ad_ratio < policy.advance_decline_min:
            cold.append("涨跌家数比 %.2f < %.2f" % (ad_ratio, policy.advance_decline_min))
        if cold:
            return GateDimensionVerdict(
                DIM_CAPITAL, STATUS_BLOCKED,
                value=sentiment if sentiment is not None else ad_ratio,
                detail=detail, missing=tuple(missing),
                reason="资金氛围偏冷（%s），风险偏好不足" % "、".join(cold),
            )
        return GateDimensionVerdict(
            DIM_CAPITAL, STATUS_OK,
            value=sentiment if sentiment is not None else ad_ratio,
            detail=detail, missing=tuple(missing),
        )

    # ── 内部工具 ─────────────────────────────────────────────
    @staticmethod
    def _skip(dimension: str, detail: str,
              missing: Tuple[str, ...] = ()) -> GateDimensionVerdict:
        return GateDimensionVerdict(
            dimension, STATUS_SKIPPED, detail=detail, missing=missing,
        )

    @staticmethod
    def _as_float(value: Any) -> Optional[float]:
        """数值归一；None/非数值 → None（视为缺失，绝不当 0）。"""
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        # NaN/Inf 是「取数失败」的另一种写法，不能当 0 或当事实参与比较
        return number if math.isfinite(number) else None

    @staticmethod
    def _degraded_hint(state: MarketState) -> str:
        """把快照自带的降级源拼进 detail，便于复盘「为什么跳过」。"""
        degraded = getattr(state, "degraded", None) or []
        if not degraded:
            return ""
        return "；降级源：%s" % "、".join(str(item) for item in degraded)


__all__ = [
    "DIM_CAPITAL",
    "DIM_INDEX",
    "DIM_SECTOR",
    "DIMENSIONS",
    "DIMENSION_LABELS",
    "EnvironmentGateDecision",
    "EnvironmentGatePolicy",
    "EnvironmentGateService",
    "GateDimensionVerdict",
    "STATUS_BLOCKED",
    "STATUS_LABELS",
    "STATUS_OK",
    "STATUS_SKIPPED",
    "check_environment",
]


def check_environment(
    state: Optional[MarketState],
    policy: Optional[EnvironmentGatePolicy] = None,
) -> EnvironmentGateDecision:
    """便捷入口：一次性判定（无需复用服务实例时用，与 check_liquidity 同风格）。"""
    return EnvironmentGateService(policy).evaluate(state)
