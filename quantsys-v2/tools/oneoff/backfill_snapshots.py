"""净值快照历史回填（2026-09-13 w-c8cae280，独立审阅发现）

背景：quant.simulation_equity_snapshot 只在有活动时写入 —— 实测 2026-09-13 近 30 天
覆盖：agent_virtual 20 天、v13 8 天、user_main 6 天，而**投资脑自有账户 agent_brain 仅 3 天**
（08-26 / 09-10 / 09-11）。后果：risk_metrics 的波动率/alpha/IR 与 M4 熔断的净值复算
全部建立在 3 个点上，"最大回撤 -0.13%"这类数字没有统计意义。

本脚本按交易回放 + 最近可得收盘价 mark-to-market 回填缺失交易日（默认不覆盖已有快照——
真实快照优先于回放近似值）。

用法：
  cd quantsys-v2 && source activate-py313.sh && python scripts/backfill_snapshots.py agent_brain 2026-07-21 2026-09-11
"""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 归档到 tools/oneoff/ 后多一层


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    account = sys.argv[1]
    start = datetime.strptime(sys.argv[2], "%Y-%m-%d").date() if len(sys.argv) > 2 else date(2026, 7, 21)
    end = datetime.strptime(sys.argv[3], "%Y-%m-%d").date() if len(sys.argv) > 3 else date.today()
    overwrite = len(sys.argv) > 4 and sys.argv[4] == "--overwrite"

    from infrastructure.services.service_registry import register_all_services
    register_all_services()

    from application.services.evolution.daily_snapshot_service import DailySnapshotService
    svc = DailySnapshotService()
    result = svc.backfill_account(account, start, end, overwrite=overwrite)
    print("backfill_snapshots", account, start, end, "overwrite=" + str(overwrite), result)
    return 0 if result.get("written") is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
