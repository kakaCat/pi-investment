"""每日净值稠密化（REQ-342799 P3，w-c8cae280，2026-09-11）

背景：quant.simulation_equity_snapshot 只在账户发生交易/估值活动时写入；
DailySnapshotService.snapshot_all_accounts 的 docstring 自称「收盘后逐账户……（每日调度）」，
但全仓检索无任何生产调用方 → 无活动的交易日就没有快照。
实测 agent_virtual：窗口内 59 个交易日只有 55 条快照（缺 08-10/08-24/08-26/08-27/08-31），
而 risk_metrics 的波动率/alpha/IR 由「相邻快照差分的日收益」算出，缺口会让跨日涨跌被当成单日收益。

本脚本把该服务接上每日调度（由 Agent OS 定时任务在工作日收盘后调用）。

用法：cd quantsys-v2 && source activate-py313.sh && python scripts/snapshot_daily.py [YYYY-MM-DD]
""",
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    target = None
    if len(sys.argv) > 1 and sys.argv[1]:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()

    from infrastructure.services.service_registry import register_all_services
    register_all_services()

    # 交易日/已收盘防护（2026-09-11）：目标日若尚无K线（未收盘或非交易日），
    # snapshot_all_accounts 会用「最近可得收盘价」估值 → 写出「旧价标新日」的假快照。
    # 此处显式跳过，宁可当日不写，也不写错。参考标的取流动性好的 600519。
    from datetime import date as _date
    from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
    from domain.ports import IKlineRepository
    ref = target or _date.today()
    klines = EnhancedServiceFactory.resolve(IKlineRepository).get_daily_klines(
        symbol="600519", start_date=ref.isoformat(), end_date=ref.isoformat()
    )
    has_bar = klines is not None and (not hasattr(klines, "is_empty") or not klines.is_empty())
    if not has_bar:
        print("snapshot_daily skipped: no kline for", ref, "(非交易日或尚未收盘)")
        return 0

    from application.services.evolution.daily_snapshot_service import DailySnapshotService
    svc = DailySnapshotService()
    result = svc.snapshot_all_accounts(target_date=target)
    print("snapshot_daily", result)
    # 有账户失败则以非零退出，便于定时任务侧发现
    return 1 if result.get("skipped", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())