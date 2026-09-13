"""core_plan_service 测试（2026-09-13 w-c8cae280）

为什么补这组测试：core_plan_service 是**每个交易日 09:05 无人值守自动跑**的账户建仓决策入口，
但它此前**零测试**，且本周刚被两处静默故障咬过（commit 19c70d57：cron 6 段 + 缺 account，
失败表现为"计划文件悄悄不更新"，消费端只看到 is_stale=true）。

覆盖四类不变量（不依赖全市场数据、毫秒级）：
  1. 硬约束：单只≤cap / 持仓≥min_names / 每只买得起≥1手 —— 三条**联立**不被互相破坏
  2. 新鲜度：缺失/不可解析/昨天/今天早于截止/今天晚于截止
  3. 差额：BUY/SELL/NONE/held_only 四类行 + 资金充足性 + 不把机械差额当委托清单（caveats 必须在）
  4. 任务契约：失败必须显式 fail（不得静默成功）；注册名与超时

E2E（真跑 generate + 全市场数据）由环境变量 CORE_PLAN_E2E=1 开启，默认跳过（单次几十秒）。
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from application.services import core_plan_service as S  # noqa: E402


# --------------------------------------------------------------------------- #
# 1. 硬约束
# --------------------------------------------------------------------------- #
def _tilt_noop(industry):
    return 1.0, "测试用 tilt"


def _u(symbol, industry, close, amt=1e8):
    return {"symbol": symbol, "industry": industry, "close": close, "amt": amt,
            "roe": 10.0, "pe": 15.0}


def _uni(specs):
    return pd.DataFrame([dict(symbol=s, industry=i, close=c, amt=a, roe=10.0, pe=15.0)
                         for s, i, c, a in specs])


class TestApplyWeightCap:
    """"单只≤cap" 与 "权重和为 100%" 必须**同时**成立；不可兼得时必须报错而非静默少投。

    背景（这组用例当场抓到的真 bug）：原实现在 N×cap < 100% 时静默丢弃多余权重，
    3 只 × 15% 得到权重和仅 45%，下游按 weight 算手数 → 只投一半的钱且无任何报错。
    """

    def test_cap_enforced_and_sums_to_100(self):
        ts = [{"symbol": "A", "mult": 9.0}] + [{"symbol": "B%d" % i, "mult": 1.0} for i in range(7)]
        S.apply_weight_cap(ts, 0.15)
        w = [x["weight_pct_of_core"] for x in ts]
        assert max(w) <= 15.0 + 1e-9, "单只超上限：%r" % w
        assert abs(sum(w) - 100.0) < 0.05, "权重和不为 100%%：%r" % w

    def test_equal_weights_untouched_when_under_cap(self):
        ts = [{"symbol": "S%d" % i, "mult": 1.0} for i in range(8)]
        S.apply_weight_cap(ts, 0.15)
        assert all(abs(x["weight_pct_of_core"] - 12.5) < 0.01 for x in ts)

    def test_15_equal_names_unaffected(self):
        # 生产口径：15 只等权 = 6.67%，远低于 15% 上限，不应被改动
        ts = [{"symbol": str(i), "mult": 1.0} for i in range(15)]
        S.apply_weight_cap(ts, 0.15)
        assert all(abs(x["weight_pct_of_core"] - 6.67) < 0.01 for x in ts)

    @pytest.mark.parametrize("n", [1, 3, 6])
    def test_infeasible_cap_raises_instead_of_silently_under_investing(self, n):
        ts = [{"symbol": str(i), "mult": 1.0} for i in range(n)]
        with pytest.raises(ValueError, match="不可行"):
            S.apply_weight_cap(ts, 0.15)

    def test_empty_is_noop(self):
        ts = []
        S.apply_weight_cap(ts, 0.15)
        assert ts == []


class TestRefillCore:
    def test_respects_used_set(self):
        ts = [{"symbol": "A", "industry": "X", "mult": 1.0, "weight_pct_of_core": 100.0}]
        used = {"A"}
        pk = {}
        uni = _uni([("A", "X", 10.0, 1e8), ("B", "Y", 10.0, 9e7)])
        added = S.refill_core(ts, used, 2, uni, pk, _tilt_noop)
        assert added == 1 and ts[-1]["symbol"] == "B" and "B" in used and "B" in pk

    def test_prefers_industry_with_fewer_members(self):
        ts = [{"symbol": "A", "industry": "X", "mult": 1.0, "weight_pct_of_core": 100.0}]
        uni = _uni([("B", "X", 10.0, 5e8), ("C", "Y", 10.0, 1e7)])
        S.refill_core(ts, {"A"}, 1, uni, {}, _tilt_noop)
        assert ts[-1]["symbol"] == "C", "补位不得抬高行业集中度（应先补行业成员少的）"

    def test_zero_or_negative_k_is_noop(self):
        ts = []
        assert S.refill_core(ts, set(), 0, _uni([("A", "X", 1.0, 1.0)]), {}, _tilt_noop) == 0
        assert S.refill_core(ts, set(), -3, _uni([("A", "X", 1.0, 1.0)]), {}, _tilt_noop) == 0
        assert ts == []


class TestJointConstraints:
    def test_unaffordable_names_are_dropped_and_backfilled(self):
        # 预算极小：只有 close<=4 的买得起 1 手；高价必须被剔除，且回补到 min_names
        ts = [{"symbol": "P1", "industry": "I1", "mult": 1.0, "weight_pct_of_core": 0.0},
              {"symbol": "P2", "industry": "I2", "mult": 1.0, "weight_pct_of_core": 0.0}]
        pk = {"P1": {"close": 500.0}, "P2": {"close": 500.0}}
        uni = _uni([("C%d" % i, "J%d" % i, 2.0, 1e8) for i in range(10)])
        tilts, dropped = S.enforce_core_constraints(ts, {"P1", "P2"}, pk, uni, _tilt_noop,
                                                    single_cap=0.15, min_names=8,
                                                    amt_total_pre=10000.0)
        assert dropped == 2, "买不起 1 手的必须被剔除"
        assert len(tilts) >= 8, "剔除后必须回补到下限"
        assert all(t["lots"] >= 1 for t in tilts), "留下的每只都必须买得起 ≥1 手"
        assert max(t["weight_pct_of_core"] for t in tilts) <= 15.0 + 1e-9

    def test_cap_and_affordability_simultaneously_hold(self):
        # 一只 mult 极高的便宜票：封顶后权重 15%，且必须仍有 ≥1 手
        ts = [{"symbol": "H", "industry": "I", "mult": 50.0, "weight_pct_of_core": 0.0},
              {"symbol": "L", "industry": "J", "mult": 1.0, "weight_pct_of_core": 0.0}]
        pk = {"H": {"close": 1.0}, "L": {"close": 1.0}}
        uni = _uni([("B%d" % i, "K%d" % i, 1.0, 1e8) for i in range(10)])
        tilts, _ = S.enforce_core_constraints(ts, {"H", "L"}, pk, uni, _tilt_noop,
                                              single_cap=0.15, min_names=8,
                                              amt_total_pre=100000.0)
        assert max(t["weight_pct_of_core"] for t in tilts) <= 15.0 + 1e-9
        assert all(t["lots"] >= 1 for t in tilts)
        assert len(tilts) >= 8

    def test_universe_insufficient_raises_not_downgrade(self):
        # 池子只有 1 只，无法满足"单只≤15% 需要 ≥7 只" → 必须报错而不是降格产出一张假计划
        with pytest.raises(ValueError, match="合格池不足"):
            S.enforce_core_constraints([], set(), {}, _uni([("A", "X", 1.0, 1e8)]),
                                       _tilt_noop, single_cap=0.15, min_names=8,
                                       amt_total_pre=100000.0)

    def test_min_names_auto_raised_for_cap_feasibility(self):
        # 调用方给不可行组合（下限 2 只 + 上限 15%）时，向上修正到 ≥7 只，而不是少投
        uni = _uni([("C%d" % i, "J%d" % i, 2.0, 1e8) for i in range(12)])
        tilts, _ = S.enforce_core_constraints([], set(), {}, uni, _tilt_noop,
                                              single_cap=0.15, min_names=2,
                                              amt_total_pre=100000.0)
        assert len(tilts) >= 7, "15%% 上限要求 ≥7 只，实际 %d" % len(tilts)
        w = [t["weight_pct_of_core"] for t in tilts]
        assert abs(sum(w) - 100.0) < 0.05, "权重和 %r" % sum(w)
        assert max(w) <= 15.0 + 1e-9

    def test_weights_always_sum_to_100_in_joint_case(self):
        ts = [{"symbol": "H", "industry": "I", "mult": 30.0, "weight_pct_of_core": 0.0}]
        pk = {"H": {"close": 1.0}}
        uni = _uni([("B%d" % i, "K%d" % i, 1.0, 1e8) for i in range(10)])
        tilts, _ = S.enforce_core_constraints(ts, {"H"}, pk, uni, _tilt_noop,
                                              single_cap=0.15, min_names=8,
                                              amt_total_pre=100000.0)
        assert abs(sum(t["weight_pct_of_core"] for t in tilts) - 100.0) < 0.05


# --------------------------------------------------------------------------- #
# 2. 新鲜度
# --------------------------------------------------------------------------- #
class TestFreshness:
    def _now(self):
        return datetime(2026, 9, 14, 9, 30)

    def test_missing_generated_at_is_stale(self):
        r = S._plan_freshness({}, now=self._now())
        assert r["is_stale"] is True and r["generated_at"] is None
        assert "缺少 generated_at" in r["stale_reason"]

    def test_unparseable_is_stale(self):
        r = S._plan_freshness({"generated_at": "not-a-time"}, now=self._now())
        assert r["is_stale"] is True and "无法解析" in r["stale_reason"]

    def test_yesterday_is_stale(self):
        y = (self._now() - timedelta(days=1)).isoformat()
        r = S._plan_freshness({"generated_at": y}, now=self._now())
        assert r["is_stale"] is True and r["generated_today"] is False
        assert "不是今天" in r["stale_reason"]

    def test_today_before_deadline_is_stale(self):
        r = S._plan_freshness({"generated_at": "2026-09-14T08:55:00"}, now=self._now())
        assert r["is_stale"] is True and r["generated_today"] is True
        assert r["generated_after_deadline"] is False and "早于当天" in r["stale_reason"]

    def test_today_after_deadline_is_fresh(self):
        r = S._plan_freshness({"generated_at": "2026-09-14T09:05:00"}, now=self._now())
        assert r["is_stale"] is False and r["stale_reason"] is None
        assert r["generated_after_deadline"] is True and 0 < r["age_hours"] < 1


# --------------------------------------------------------------------------- #
# 3. 差额
# --------------------------------------------------------------------------- #
def _pos(symbol, total, avail):
    return SimpleNamespace(symbol=symbol, shares_total=total, shares_available=avail)


PLAN = {
    "account": "test_acct",
    "holdings": [{"symbol": "600000", "close": 10.0, "lots": 5},     # 目标 500 股
                 {"symbol": "600001", "close": 20.0, "lots": 3}],    # 目标 300 股
    "growth_sleeve": {"holdings": [{"symbol": "300001", "close": 5.0, "lots": 2}]},
}


class TestPlanDelta:
    def _run(self, positions, cash=100000.0):
        with patch("adapters.outbound.repositories.simulation_position_repository"
                   ".SimulationPositionRepository.get_all_positions", return_value=positions), \
             patch.object(S, "query_rows", return_value=[(cash,)]):
            return S._plan_delta(PLAN, "test_acct")

    def test_actions_and_amounts(self):
        d = self._run([_pos("600000", 200, 200),   # 目标 500 → BUY 300
                       _pos("600001", 500, 100),   # 目标 300 → SELL 200
                       _pos("300001", 200, 0),     # 目标 200 → NONE
                       _pos("999999", 100, 100)])  # 计划外 → REVIEW
        rows = {r["symbol"]: r for r in d["rows"]}
        assert rows["600000"]["action"] == "BUY" and rows["600000"]["delta_shares"] == 300
        assert rows["600000"]["est_amount"] == 3000.0
        assert rows["600001"]["action"] == "SELL" and rows["600001"]["delta_shares"] == -200
        assert rows["300001"]["action"] == "NONE"
        assert rows["999999"]["action"] == "REVIEW" and rows["999999"]["in_plan"] is False
        assert d["summary"]["est_buy_amount"] == 3000.0
        assert d["summary"]["cash_after_full_delta"] == 97000.0
        assert d["summary"]["cash_sufficient"] is True

    def test_caveats_always_present(self):
        d = self._run([])
        assert d["caveats"], "差额必须自带免责：机械差额 ≠ 委托清单"
        joined = " ".join(d["caveats"])
        assert "分批" in joined, "必须写明不含分批节奏（一次打满是误用）"

    def test_insufficient_cash_flagged(self):
        d = self._run([_pos("600000", 0, 0), _pos("600001", 0, 0), _pos("300001", 0, 0)], cash=100.0)
        assert d["summary"]["cash_sufficient"] is False
        assert d["summary"]["cash_after_full_delta"] < 0

    def test_duplicate_symbol_across_buckets_counted_once(self):
        plan = {"account": "test_acct",
                "holdings": [{"symbol": "600000", "close": 10.0, "lots": 5}],
                "growth_sleeve": {"holdings": [{"symbol": "600000", "close": 10.0, "lots": 5}]}}
        with patch("adapters.outbound.repositories.simulation_position_repository"
                   ".SimulationPositionRepository.get_all_positions", return_value=[]), \
             patch.object(S, "query_rows", return_value=[(100000.0,)]):
            d = S._plan_delta(plan, "test_acct")
        assert len([r for r in d["rows"] if r["symbol"] == "600000"]) == 1, \
            "同一标的出现在 core 与子额度时不得重复计一条"


# --------------------------------------------------------------------------- #
# 4. plan_snapshot 与任务契约
# --------------------------------------------------------------------------- #
class TestPlanSnapshot:
    def test_missing_file_explains_cause(self, tmp_path):
        r = S.plan_snapshot(path=tmp_path / "nope.json")
        assert r["available"] is False and "core_plan_generate" in r["unavailable_reason"]

    def test_unparseable_file(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not json", encoding="utf-8")
        r = S.plan_snapshot(path=f)
        assert r["available"] is False and "无法解析" in r["unavailable_reason"]

    def test_account_mismatch_skips_delta(self, tmp_path):
        f = tmp_path / "plan.json"
        f.write_text(json.dumps({"account": "acct_a", "generated_at": "2026-09-14T09:05:00"}),
                     encoding="utf-8")
        with patch.object(S, "_plan_delta") as m:
            r = S.plan_snapshot(account="acct_b", path=f)
        assert r["account_mismatch"] is True and r["delta"] is None
        m.assert_not_called()
        assert "不计算跨账户差额" in r["unavailable_reason"]

    def test_delta_failure_does_not_break_plan_read(self, tmp_path):
        f = tmp_path / "plan.json"
        f.write_text(json.dumps({"account": "acct_a", "generated_at": "2026-09-14T09:05:00"}),
                     encoding="utf-8")
        with patch.object(S, "_plan_delta", side_effect=RuntimeError("boom")):
            r = S.plan_snapshot(path=f)
        assert r["plan"] is not None, "差额失败不该让读计划整体失败"
        assert "差额计算失败" in r["unavailable_reason"]


class TestJobContract:
    def test_job_identity(self):
        j = S.build_core_plan_jobs()
        assert len(j) == 1 and j[0].name == "core_plan_generate"
        assert j[0].timeout_seconds == 600

    @pytest.mark.asyncio
    async def test_failure_is_explicit_not_silent(self):
        job = S.CorePlanGenerateJob()
        with patch.object(S, "generate", side_effect=RuntimeError("db down")):
            res = await job.execute({})
        assert res.success is False, "失败必须显式失败（调度器据此标红），不得静默成功"
        assert "db down" in (res.error or ""), "失败原因必须带上（否则调度器只看到红灯不知为什么）"
        assert res.action == "core_plan_generate"

    @pytest.mark.asyncio
    async def test_success_reports_counts(self):
        job = S.CorePlanGenerateJob()
        fake = {"account": "test_acct",
                "holdings": [{"symbol": "600000"}], "growth_sleeve": {"holdings": [{"symbol": "300001"}]},
                "exposure": {"target_pct": 0.125}}
        with patch.object(S, "generate", return_value=fake):
            res = await job.execute({})
        assert "core=1 sleeve=1" in (res.message or "")


# --------------------------------------------------------------------------- #
# 5. 账户解析（R-019：账户名不得写死，事实源 agents.json）
# --------------------------------------------------------------------------- #
class TestResolveAccount:
    def test_explicit_wins(self):
        assert S.resolve_account("my_acct") == "my_acct"

    def test_env_used_when_no_explicit(self, monkeypatch):
        monkeypatch.setenv("DSH_INVESTMENT_ACCOUNT", "env_acct")
        assert S.resolve_account(None) == "env_acct"

    def test_agents_json_is_source_of_truth(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DSH_INVESTMENT_ACCOUNT", raising=False)
        monkeypatch.setenv("DSH_PROFILE_DIR", str(tmp_path))
        (tmp_path / "agents.json").write_text(json.dumps({"instance": {"account": "json_acct"}}),
                                              encoding="utf-8")
        assert S.resolve_account(None) == "json_acct"

    def test_no_source_raises_instead_of_defaulting(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DSH_INVESTMENT_ACCOUNT", raising=False)
        monkeypatch.setenv("DSH_PROFILE_DIR", str(tmp_path))
        with pytest.raises(ValueError, match="无法解析投资账户"):
            S.resolve_account(None)

    def test_empty_account_in_agents_json_raises(self, monkeypatch, tmp_path):
        monkeypatch.delenv("DSH_INVESTMENT_ACCOUNT", raising=False)
        monkeypatch.setenv("DSH_PROFILE_DIR", str(tmp_path))
        (tmp_path / "agents.json").write_text(json.dumps({"instance": {}}), encoding="utf-8")
        with pytest.raises(ValueError, match="instance.account 为空"):
            S.resolve_account(None)


# --------------------------------------------------------------------------- #
# 6. E2E（真跑全市场，默认跳过）
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not __import__("os").environ.get("CORE_PLAN_E2E"),
                    reason="E2E 需全市场数据且耗时数十秒；设 CORE_PLAN_E2E=1 开启")
class TestEndToEnd:
    def test_generate_respects_hard_constraints(self, tmp_path, monkeypatch):
        monkeypatch.setattr(S, "OUT", tmp_path / "plan.json")
        plan = S.generate()
        hs = plan["holdings"]
        assert len(hs) >= 8, "持仓数下限被破坏：%d" % len(hs)
        avg = max(h["weight_pct_of_core"] for h in hs)
        assert avg <= 15.0 + 1e-9, "单只上限被破坏：%.2f%%" % avg
        assert all(h.get("lots", 0) >= 1 for h in hs), "存在买不起 1 手的标的"
        assert plan["exposure"]["target_pct"] <= plan["exposure"]["first_phase_cap_pct"]
        gs = plan.get("growth_sleeve") or {}
        expo = (gs.get("meta") or {}).get("exposure_pct_of_total") or 0
        assert expo <= 0.05 + 1e-9, "成长板子额度超 5%% 上限：%r" % expo
        assert plan.get("data_date"), "计划必须自描述行情时点（R-013）"

# --------------------------------------------------------------------------- #
# 7. 宪法限额静态复检（_limit_check）
# --------------------------------------------------------------------------- #
class TestLimitCheck:
    """机械差额由计划权重推导、**从不校验宪法限额**（可能已持有某股 15% 再按计划加仓）。

    此前只写在 caveats 文案里"下单前必须复核"，等于把校验推给下游人工；这里钉住机器判定。
    """

    def _row(self, symbol, held, delta, close, action):
        return {"symbol": symbol, "held_shares": held, "delta_shares": delta,
                "plan_close": close, "action": action, "est_amount": abs(delta) * close}

    def test_unchecked_when_total_value_unknown(self):
        r = S._limit_check([self._row("600000", 0, 100, 10.0, "BUY")], {}, 1000.0, None)
        assert r["checked"] is False and r["passed"] is None
        assert "未校验" in r["note"]

    def test_passes_in_normal_case(self):
        rows = [self._row("600000", 0, 100, 10.0, "BUY")]
        with patch.object(S, "_industries", return_value={"600000": "银行"}):
            r = S._limit_check(rows, {}, 100000.0, 200000.0)
        assert r["passed"] is True and r["violations"] == []
        assert r["max_single"]["pct"] == 0.5
        # 现金 100000 / 总资产 200000 = 50%；买入 1000 后 49.5%（远高于 10% 下限）
        assert r["cash_after_pct"] == 49.5

    def test_single_stock_limit_violation(self):
        # 已持 19%（38000/200000），再买 300 股 → 41000/200000 = 20.5% > 20%
        rows = [self._row("600000", 3800, 300, 10.0, "BUY")]
        with patch.object(S, "_industries", return_value={"600000": "银行"}):
            r = S._limit_check(rows, {}, 100000.0, 200000.0)
        kinds = [v["type"] for v in r["violations"]]
        assert "single_stock" in kinds and r["passed"] is False

    def test_industry_limit_violation(self):
        rows = [self._row("600000", 0, 4000, 10.0, "BUY"),   # 40000
                self._row("601288", 0, 4500, 10.0, "BUY")]   # 45000 → 同行业 85000/200000=42.5%
        with patch.object(S, "_industries", return_value={"600000": "银行", "601288": "银行"}):
            r = S._limit_check(rows, {}, 100000.0, 200000.0)
        kinds = [v["type"] for v in r["violations"]]
        assert "industry" in kinds and r["passed"] is False
        assert r["max_industry"]["industry"] == "银行"

    def test_cash_min_violation(self):
        rows = [self._row("600000", 0, 1900, 10.0, "BUY")]   # 花 19000，现金 20000 → 剩 1000 = 0.5%
        with patch.object(S, "_industries", return_value={"600000": "银行"}):
            r = S._limit_check(rows, {}, 20000.0, 200000.0)
        kinds = [v["type"] for v in r["violations"]]
        assert "cash_min" in kinds

    def test_sell_reduces_exposure_not_flagged(self):
        rows = [self._row("600000", 5000, -4000, 10.0, "SELL")]
        with patch.object(S, "_industries", return_value={"600000": "银行"}):
            r = S._limit_check(rows, {}, 100000.0, 200000.0)
        assert r["passed"] is True and r["max_single"]["pct"] == 5.0


# --------------------------------------------------------------------------- #
# 8. 分批节奏（execution_plan）
# --------------------------------------------------------------------------- #
class TestExecutionPlan:
    def _core(self, n=15):
        return [{"symbol": "C%02d" % i, "weight_pct_of_core": round(100.0 / n, 2),
                 "lots": 1, "close": 10.0} for i in range(n)]

    def test_every_name_appears_exactly_once(self):
        ep = S.build_execution_plan(self._core(), [], 100000.0, 0.0)
        syms = [s for b in ep["batches"] for s in b["symbols"]]
        assert len(syms) == len(set(syms)) == 15

    def test_batches_are_balanced(self):
        ep = S.build_execution_plan(self._core(), [], 100000.0, 0.0)
        amts = [b["amount"] for b in ep["batches"]]
        assert len(amts) == 4
        assert max(amts) - min(amts) <= max(amts) * 0.5, "各批金额差异过大：%r" % amts

    def test_sleeve_rows_carried_with_bucket(self):
        sleeve = [{"symbol": "300014", "weight_pct_of_sleeve": 50.0, "lots": 1, "close": 20.0},
                  {"symbol": "300456", "weight_pct_of_sleeve": 50.0, "lots": 2, "close": 10.0}]
        ep = S.build_execution_plan(self._core(4), sleeve, 40000.0, 20000.0)
        got = {x["symbol"]: x["bucket"] for b in ep["batches"] for x in b["detail"]}
        assert got["300014"] == "growth_sleeve" and got["C00"] == "core"

    def test_rule_states_no_one_shot(self):
        ep = S.build_execution_plan(self._core(2), [], 10000.0, 0.0)
        assert "一次性打满" in ep["rule"] or "不得" in ep["rule"]

    def test_empty_input_is_safe(self):
        ep = S.build_execution_plan([], [], 0.0, 0.0)
        assert len(ep["batches"]) == 4 and all(b["amount"] == 0 for b in ep["batches"])


# --------------------------------------------------------------------------- #
# 9. 风险透镜（risk_lens）——必须 best-effort，绝不拖垮 09:05 的计划任务
# --------------------------------------------------------------------------- #
def _fake_klines(n_days=80, n_syms=3, seed=7):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2026-01-01", periods=n_days)
    frames = []
    for i in range(n_syms):
        px = 10.0 * np.cumprod(1 + rng.normal(0.0005, 0.015, n_days))
        frames.append(pd.DataFrame({"symbol": "60000%d" % i, "trade_date": dates, "close": px}))
    return pd.concat(frames, ignore_index=True)


class TestRiskLens:
    def test_too_few_names_degrades_not_raises(self):
        r = S.risk_lens({"600000": 0.1}, 100000.0)
        assert r["unavailable_reason"] and r["ann_vol"] is None

    def test_no_kline_data_degrades(self):
        with patch.object(S, "kline_history", return_value=pd.DataFrame(columns=["symbol", "trade_date", "close"])):
            r = S.risk_lens({"600000": 0.1, "600001": 0.1}, 100000.0)
        assert "无日线数据" in (r["unavailable_reason"] or "")

    def test_happy_path_computes_effective_bets(self):
        with patch.object(S, "kline_history", return_value=_fake_klines()):
            r = S.risk_lens({"600000": 0.1, "600001": 0.1, "600002": 0.05}, 100000.0)
        assert r["unavailable_reason"] is None
        # 有效注数（特征值口径、不含权重）的上界是**标的数**（Cauchy-Schwarz: Σλ² ≥ n），不是名义注数：
        # 权重不均时特征值口径反而可能更大（实测 3 只 (0.4,0.4,0.2) → 2.93 > 名义 2.78）。两者不可直接比。
        assert 1.0 <= r["effective_bets"] <= 3 + 1e-6, "有效注数必须落在 [1, 标的数]：%r" % r["effective_bets"]
        assert "不可直接比大小" in r["bets_note"]
        assert r["ann_vol"] > 0 and r["var95_daily"] < 0
        assert r["var95_amount"] is not None and r["trading_days"] > 20

    def test_benchmark_failure_only_loses_beta(self):
        with patch.object(S, "kline_history", return_value=_fake_klines()), \
             patch.dict("sys.modules", {"akshare": None}):
            r = S.risk_lens({"600000": 0.1, "600001": 0.1}, 100000.0)
        assert r["beta_vs_hs300"] is None and r["ann_vol"] is not None
        assert r["benchmark_note"]

    def test_malformed_exposure_ignored(self):
        with patch.object(S, "kline_history", return_value=_fake_klines()):
            r = S.risk_lens({"600000": 0.1, "600001": "bad", "600002": None}, 100000.0)
        assert r["unavailable_reason"], "剔掉非法权重后只剩 1 只 → 应显式降级"

# --------------------------------------------------------------------------- #
# 10. 整手残差再投（deploy_residual / realized_block）
# --------------------------------------------------------------------------- #
class TestDeployResidual:
    """A股按 100 股整手买入 → 等权目标金额几乎不可能被整除。

    实测：core 目标 62500 元整手后只投出 50906 元（残差 18.6%）、子额度残差 35.6%，
    合计"声明暴露 16.16%、实际只能投 12.54%"。本组用例钉住"残差要被尽量投出去、且不得超投/超限"。
    """

    def test_deploys_slack_toward_targets(self):
        rows = [{"close": 10.0, "lots": 1, "_target_amt": 4000.0},
                {"close": 20.0, "lots": 1, "_target_amt": 4000.0}]
        added = S.deploy_residual(rows, 8000.0)
        deployed = sum(r["close"] * 100 * r["lots"] for r in rows)
        assert added > 0 and deployed > 3000.0, "残差应被再投出去：%.0f" % deployed
        assert deployed <= 8000.0 + 1e-9, "不得超投：%.0f" % deployed

    def test_never_exceeds_total_budget(self):
        rows = [{"close": 3.33, "lots": 0, "_target_amt": 1000.0} for _ in range(3)]
        S.deploy_residual(rows, 1000.0)
        deployed = sum(r["close"] * 100 * r["lots"] for r in rows)
        assert deployed <= 1000.0 + 1e-9

    def test_respects_single_name_cap(self):
        rows = [{"close": 1.0, "lots": 0, "_target_amt": 0.0},
                {"close": 1.0, "lots": 0, "_target_amt": 0.0}]
        S.deploy_residual(rows, 10000.0, cap_pct=30.0)   # 单只 ≤ 30% = 3000 元 = 30 手
        for r in rows:
            assert r["close"] * 100 * r["lots"] <= 3000.0 + 1e-9, "超单只上限：%r" % r

    def test_returns_zero_when_nothing_affordable(self):
        rows = [{"close": 50.0, "lots": 0, "_target_amt": 40.0}]   # 1 手 = 5000 > 预算 100
        assert S.deploy_residual(rows, 100.0) == 0
        assert rows[0]["lots"] == 0

    def test_empty_and_zero_budget_are_safe(self):
        assert S.deploy_residual([], 1000.0) == 0
        assert S.deploy_residual([{"close": 1.0, "lots": 0}], 0.0) == 0


class TestRealizedBlock:
    def test_reports_residual(self):
        rows = [{"close": 10.0, "lots": 1}]     # 1000 元
        rb = S.realized_block(rows, 2000.0)
        assert rb["actual_amount"] == 1000.0 and rb["residual_amount"] == 1000.0
        assert rb["residual_pct"] == 50.0

    def test_zero_target_does_not_divide_by_zero(self):
        rb = S.realized_block([{"close": 10.0, "lots": 1}], 0.0)
        assert rb["residual_pct"] is None
