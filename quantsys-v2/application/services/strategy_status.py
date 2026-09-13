"""策略状态语义（2026-09-13, w-a9ec14d7）—— 单一事实源

背景（真实案例）：`validation_status` 一个字段被当成两种含义用——
  · 结构含义：代码能否跑通、参数是否合法（平台验证的本来语义）
  · 性能含义：跑通之后有没有超额收益（用户/agent 实际关心的）
结果是 `validation_status=valid` 被读成"这策略好用"，而实测 14 条 active+valid
策略 OOS CAGR 中位约 -1%，同期同池等权基准 +23.3% —— 没有一条跑赢。
`enrich_strategy_response` 更把它映射成用户可见的 status（invalid → error），
于是"结构无效"在界面上表现为"运行出错"，两种含义彻底混在一起。

本模块把两种含义拆成两个字段，并把判定规则收敛到这里（唯一实现）：
  · structure_status：valid / invalid / pending / unknown
  · performance_status：passing / underperform / failing / unmeasured
"""
from typing import Any, Dict, Optional

# 基准：同池等权、窗口完整覆盖（2024-07~2026-09，800 只、2024H1 定义的最活跃池）
BENCHMARK_CAGR = 0.233
BENCHMARK_NOTE = "2024-07~2026-09 同池等权 CAGR +23.3%（800 只，2024H1 定义）"

STRUCTURE_STATUSES = ("valid", "invalid", "pending", "unknown")
PERFORMANCE_STATUSES = ("passing", "underperform", "failing", "unmeasured")


def classify_structure(legacy_validation_status: Optional[str]) -> str:
    """结构状态：沿用平台验证结论（valid/invalid/pending），空值归 unknown。"""
    if legacy_validation_status in ("valid", "invalid", "pending"):
        return legacy_validation_status
    return "unknown"


def classify_performance(annual_return: Optional[float],
                         sharpe: Optional[float] = None,
                         benchmark: float = BENCHMARK_CAGR) -> str:
    """业绩状态：相对**同池等权基准**（不是绝对收益，绝对阈值在本市场无意义）。

    unmeasured  无回测证据（不判死，也不冒充达标）
    failing     年化 <= 0（亏钱）
    underperform 0 < 年化 < 基准（赚钱但跑输基准）
    passing     年化 >= 基准
    """
    if annual_return is None:
        return "unmeasured"
    try:
        ar = float(annual_return)
    except (TypeError, ValueError):
        return "unmeasured"
    if ar <= 0:
        return "failing"
    if ar < benchmark:
        return "underperform"
    return "passing"


def performance_evidence(annual_return: Optional[float], sharpe: Optional[float],
                         max_drawdown: Optional[float], source: str,
                         window: Optional[str] = None,
                         benchmark: float = BENCHMARK_CAGR) -> Dict[str, Any]:
    """业绩判定证据（R-013：任何判定都要能标注来源、时点与口径）。"""
    return {
        "annual_return": annual_return,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "benchmark_cagr": benchmark,
        "benchmark_note": BENCHMARK_NOTE,
        "source": source,
        "window": window,
        "rule": "ar<=0→failing; 0<ar<benchmark→underperform; ar>=benchmark→passing; 无证据→unmeasured",
    }