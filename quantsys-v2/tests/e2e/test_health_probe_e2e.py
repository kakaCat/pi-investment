"""端到端场景：launchd 怎么跑探针，这里就怎么跑（REQ-261004102115-d3de · 验收返工项 v1-8）。

## 为什么需要它（以及它不是单测的重复）

单测覆盖"给定日期，解析器算得对不对"；本文件覆盖**整条链**：
真实入口脚本 → 真实交易日历/数据库 → 判定 → 退出码与告警载荷。
它回答单测回答不了的问题：**装到 launchd 上跑起来，这条链还是不是接对的、还会不会响亮报警？**

因此这里**不 mock 任何一层**，断言全部落在可观察终态：
进程退出码、stdout JSON 字段、以及"告警确实**没有**发出"。

## 关于数据库

子进程继承 pytest 的环境（`PGDATABASE=quant_test`），因此查的是**测试库**（本仓硬规则：测试不碰生产库）。
测试库里的日历/行情是合成的，**所以本文件不假设某个具体日期是交易日**，
只断言与"库里装了什么"无关的终态（契约 + 跨进程一致性 + 报警能力）。
"休市日不得被当成交易日"这条语义断言由单测在注入日历上完成（`tests/test_trading_day_resolver.py`）。
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROBE = REPO_ROOT / "tools" / "health_probe.py"


def _run_probe(*extra: str) -> subprocess.CompletedProcess:
    """按 launchd 的方式跑真实入口：独立进程、仓库为工作目录、dry-run 不外发。"""
    return subprocess.run(
        [sys.executable, str(PROBE), "--dry-run", *extra],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )


def _report(stdout: str) -> dict:
    """取 stdout 里的巡检 JSON（脚本先打印报告，再打印（可能的）dry-run 告警）。"""
    start = stdout.index("{")
    end = stdout.index("\n}\n") + 2 if "\n}\n" in stdout else stdout.rindex("}") + 1
    return json.loads(stdout[start:end])


def _freshness(report: dict) -> dict:
    return next(c for c in report["checks"] if c["name"] == "kline_freshness")


@pytest.mark.e2e
def test_probe_chain_uses_the_shared_trading_day_resolver():
    """整条链跑通，且脚本给出的"应有交易日"与库内唯一口径**逐日一致**（跨进程核对）。"""
    from application.services.trading_day_resolver import last_closed_trading_day

    proc = _run_probe()

    # 终态 1：探针自身没有出错（3 = 探针配置/依赖问题，与"被监控对象异常"必须分开）
    assert proc.returncode in (0, 2), f"探针自身出错：\n{proc.stdout}\n{proc.stderr}"

    freshness = _freshness(_report(proc.stdout))

    # 终态 2：输出契约齐全（降级与否必须显式带出）
    assert freshness["expected_source"] in {"calendar", "weekday_fallback"}
    assert freshness["expected_degraded"] is (freshness["expected_source"] == "weekday_fallback")

    # 终态 3：脚本口径 == 库内唯一口径（证明链路真的接到同一实现，而不是各算各的）
    in_process = last_closed_trading_day(datetime.now())
    assert freshness["expected"] == in_process.date.isoformat()

    # 终态 4：lag 与 ok 自洽
    lag = (
        datetime.strptime(freshness["expected"], "%Y-%m-%d").date()
        - datetime.strptime(freshness["kline_latest"], "%Y-%m-%d").date()
    ).days
    assert freshness["lag_days"] == lag
    assert freshness["ok"] is (lag <= freshness["max_lag_days"])


@pytest.mark.e2e
def test_probe_chain_still_fires_loudly_and_never_sends():
    """负向控制：把容差压到"必然不及格"，整条链仍要**响亮报警**，且告警**没有真发**。

    容差按实测 lag 现算（lag-1），因此与"库里数据新不新鲜"无关——永远必然不及格。
    """
    baseline = _freshness(_report(_run_probe().stdout))
    lag = baseline["lag_days"]

    proc = _run_probe("--max-lag-days", str(lag - 1))

    assert proc.returncode == 2, f"容差 {lag - 1} 时仍应判异常并 exit 2：\n{proc.stdout}"

    report = _report(proc.stdout)
    assert report["healthy"] is False
    assert _freshness(report)["ok"] is False

    # 终态：dry-run 路径下告警只打印、不投递
    assert "[--dry-run] 以下告警**未发送**" in proc.stdout
    assert "K线最新" in proc.stdout and "应有" in proc.stdout
