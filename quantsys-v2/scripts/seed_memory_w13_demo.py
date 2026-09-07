#!/usr/bin/env python
"""W1.3 检索质量验收种子（≥20 条种子记忆要求）

现有 14 条（8 缠论迁移 + 6 条 v13 案例），本脚本补 7 条真实项目教训，
全部内容可在 quant.simulation_trades / 校准脚本 / 体检报告回查（验收纪律 #4）。
幂等：按 title+source 去重，重复执行不产生重复行。

用法（quantsys-v2 目录下）：
    venv/bin/python scripts/seed_memory_w13_demo.py
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from adapters.outbound.repositories.memory_repository import MemoryRepository  # noqa: E402
from domain.memory.models import MemoryEntry  # noqa: E402
from domain.memory.service import MemoryService  # noqa: E402

SEEDS = [
    {
        "kind": "episode",
        "scope": "strategy:v14",
        "title": "v14 止损桩事故与修复（2026-07-28）",
        "content": (
            "v14 止损原为 TODO 桩，300162 浮亏 -47.6%、300432 浮亏 -22.2% 从未触发止损，深套扩大。"
            "2026-07-28 统一 StrategyService 修复后首跑：SELL 300162 900股@7.08、300432 500股@15.38，"
            "v14_simulation 持仓清零。教训：止损逻辑不能留桩，必须有回归测试。"
        ),
        "evidence": {
            "trades": ["simulation_trades v14_simulation 2026-07-28 SELL 300162/300432"],
            "tests": "tests/test_strategy_service_unified.py",
        },
    },
    {
        "kind": "rule",
        "scope": "global",
        "title": "止损/止盈等保命逻辑禁止 TODO 桩",
        "content": (
            "v14 止损 TODO 桩导致 300162 -47.6% 深套。任何写进调度链路的卖出保护必须当日可运行"
            "并有回归测试；未完成的功能不得挂接生产调度。"
        ),
        "evidence": {"incident": "v14_simulation 300162/300432 深套", "fix_commit": "72ad46f"},
    },
    {
        "kind": "rule",
        "scope": "global",
        "title": "策略评估必须胜率+期望+样本三件套",
        "content": (
            "策略 [365] 胜率 57% 但期望 -0.08%（n=430，赢小亏大）。单看胜率会误留负期望策略。"
            "体检口径：5 交易日前向收益定胜负，≥5 信号才入榜。"
        ),
        "evidence": {"report": "data/strategy_health_2026-08-04.json"},
    },
    {
        "kind": "episode",
        "scope": "global",
        "title": "2026-08-04 首次策略体检：86 策略 50 死码",
        "content": (
            "86 个活跃策略中 50 个三个月零信号（死代码）、6 个 TEST 生产克隆。停用 58 个，活跃 86→28。"
            "默认扫描集 [162,166,179,180] 换血为 [179,178,163,193]"
            "（期望 +0.30%/+0.41%/+0.37%/+1.86%）。"
        ),
        "evidence": {"report": "data/strategy_health_2026-08-04.json", "tasks": "scheduler_task_configs 236/247"},
    },
    {
        "kind": "episode",
        "scope": "strategy:v13",
        "title": "2026-07-13 K线 amount 归零事故",
        "content": (
            "kline_update_job 把 amount 硬编码 0.0，07-13 起创业板池流动性过滤归零、调仓取消。"
            "修复后逐符号回填（1952 符号×100 / 168 符号×1），创业板池恢复 534 只，"
            "v13 全链路调仓买入 5 只验证通过。"
        ),
        "evidence": {"fix": "main 9adc875", "table": "quant.daily_klines"},
    },
    {
        "kind": "rule",
        "scope": "global",
        "title": "K线数据契约：volume=股、amount=元",
        "content": (
            "daily_klines 契约 volume 单位股、amount 单位元。tencent/akshare 原始数据 volume 为手"
            "需 ×100 归一。amount 缺失或归零会让任何按成交额过滤的流动性逻辑团灭。"
        ),
        "evidence": {"table": "quant.daily_klines", "incident": "2026-07-13 amount 归零事故"},
    },
    {
        "kind": "experience",
        "scope": "global",
        "title": "评估模拟盘收益率必须用校准后口径",
        "content": (
            "2026-07-20 多账户迁移用 adjustment 流水强行对齐余额（v13 +60,962.37、v14 +23,584.36），"
            "页面收益率注水（v13 显示约 +49%）。2026-07-23 校准后真实口径：v13 -11.94%、v14 -21.68%（B1）。"
            "引用策略收益率时先确认是校准后数值。"
        ),
        "evidence": {
            "scripts": ["calibrate_20260723_v13_return.py", "calibrate_20260723_v14_return.py"],
            "backup": "quant.sim_calibration_backup_20260723",
        },
    },
]


def main() -> int:
    repo = MemoryRepository()
    service = MemoryService(repo)  # 默认 OllamaEmbeddingService（bge-m3）

    created, skipped = 0, 0
    for seed in SEEDS:
        existing = repo.find_duplicate(
            title=seed["title"], source="seed_w13", provenance=None
        )
        if existing:
            print(f"  ⏭ 已存在 id={existing['id']}：{seed['title'][:40]}")
            skipped += 1
            continue
        entry = MemoryEntry(
            kind=seed["kind"],
            scope=seed["scope"],
            title=seed["title"],
            content=seed["content"],
            evidence=seed["evidence"],
            status="active",
            provenance={"session_kind": "user", "channel": "seed_script"},
            source="seed_w13",
        )
        result = service.create(entry)
        has_vec = "with-embedding" if result.get("embedding") else "NO-EMBEDDING"
        print(f"  ✅ id={result['id']} [{has_vec}] {seed['title'][:40]}")
        created += 1

    print(f"种子完成：新增 {created}，跳过 {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
