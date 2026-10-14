"""升级检查器（**兼容壳**：REQ-261007133807-eda6 t4）

## 这个文件现在是什么

「什么时候把一条 L0/L1 触发交给 agent」的判据**唯一事实源**已迁到
`domain/watch/services/escalation_verdict.py` 的 :func:`decide_escalation_paths`
（以及全量出口 :func:`decide_escalation`）。本模块只保留 **兼容壳**：
既有 5 处导入方（engine / escalation_coordinator / services 包 / 两个测试文件）
继续按原签名调用，返回类型与**文案逐字不变**。

## 保留的三条可信路径（业务口径未变）

  1) 规则显式声明：action_hint.escalate is True（规则作者说了算）
  2) 宪法级：intent == 'exit_stop'（止损铁律，无条件）
  3) 异常波动：|涨跌幅| ≥ 阈值（默认 5.0，可按 escalation_policy.anomaly_change_pct 覆写）

已删除（历史五类，均经实证不可信或无人维护，**本需求不复活**）：
触发频率 / 量能异常 / 价格偏差 / 核心区域 / 多规则共振（详见 escalation_verdict 模块头）。

## 为什么壳里不再实现判据

收敛的意义就是**一处判定**：如果壳里再留一份实现，两处必然漂移（本仓「两份真相」教训）。
故这里的 `should_escalate` 只做两件事：取实例级缺省阈值 → 委托出口 → 把理由字符串返回。

消费侧契约（unchanged）：本壳读 `result.value` 前仍由出口声明期望 metric（require_metric），
不符即响亮抛错——这是「现价当量比」不再复发的机制保证。
"""
from typing import Optional

# QuoteData / WatchRule 原先由本模块再导出（domain.watch.services.__init__ 与既有 importer 依赖），
# 本轮收敛保留再导出，避免破坏既有导入路径。
from domain.watch.models import (  # noqa: F401
    DEFAULT_ANOMALY_CHANGE_PCT, MetricKind, QuoteData, WatchRule,
)
from domain.watch.services.escalation_verdict import (
    decide_escalation_paths,
)
from domain.watch.services.disposition import CONSTITUTIONAL_INTENTS  # noqa: F401

__all__ = ['EscalationChecker', 'QuoteData', 'WatchRule',
           'DEFAULT_ANOMALY_CHANGE_PCT', 'CONSTITUTIONAL_INTENTS']


class EscalationChecker:
    """升级检查器（兼容壳；判据见 escalation_verdict.decide_escalation_paths）"""

    def __init__(self, anomaly_change_pct: Optional[float] = None):
        self.anomaly_change_pct = (
            float(anomaly_change_pct) if anomaly_change_pct is not None
            else DEFAULT_ANOMALY_CHANGE_PCT)

    def should_escalate(self, rule, condition: dict, quote, result,
                        recent_trigger_count: int = 0,
                        concurrent_trigger_count: int = 0) -> Optional[str]:
        """检查是否应升级，返回原因（None=不升级）

        recent_trigger_count / concurrent_trigger_count 为**兼容参数**，不参与判定
        （原频率/共振路径已删除；触发计数改供规则自愈 R6 使用）。
        """
        verdict = decide_escalation_paths(rule, condition, quote, result,
                                         default_anomaly_pct=self.anomaly_change_pct)
        return verdict.reason if verdict is not None else None
