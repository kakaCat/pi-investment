import asyncio

from qs_ops.application.jobs.signal_jobs import OpportunityScanDailyJob, SIGNAL_JOBS


class FakeGuard:
    def __init__(self, trading_day=True):
        self.trading_day = trading_day
        self.calls = 0

    def is_trading_day(self):
        self.calls += 1
        return self.trading_day


class FakeScoring:
    def __init__(self, opportunities, scored=None):
        self.opportunities = opportunities
        self.last_diagnostics = {
            "scored": len(opportunities) if scored is None else scored,
            "errors": 0,
        }
        self.calls = []

    def score_stocks(self, **kwargs):
        self.calls.append(kwargs)
        return [dict(opp) for opp in self.opportunities]


class FakePool:
    def __init__(self, symbols=None):
        self.symbols = symbols if symbols is not None else ["000001.SZ", "000002.SZ"]
        self.watchlists = []

    def get_scan_universe(self, watchlist):
        self.watchlists.append(watchlist)
        return list(self.symbols) + list(watchlist)


class FakeRuleService:
    def __init__(self, results=None):
        self.results = results
        self.calls = []

    def auto_create_rules(self, opportunities, **kwargs):
        self.calls.append(opportunities)
        self.kwargs = kwargs
        if self.results is not None:
            return list(self.results)
        return [{"symbol": opp["symbol"], "action": "created", "rule_id": index + 1}
                for index, opp in enumerate(opportunities)]


class FakeNotificationSender:
    def __init__(self, delivered=True):
        self.delivered = delivered
        self.calls = []

    def __call__(self, title, body):
        self.calls.append((title, body))
        return self.delivered


def opportunity(symbol, score=85, risk_level="medium", signal_type="buy"):
    return {
        "symbol": symbol,
        "score": score,
        "risk_level": risk_level,
        "signal_type": signal_type,
    }


def make_job(opportunities=None, scored=None, rule_results=None, trading_day=True,
             symbols=None, notification_sender=None):
    scoring = FakeScoring(opportunities or [], scored=scored)
    pool = FakePool(symbols=symbols)
    rules = FakeRuleService(results=rule_results)
    guard = FakeGuard(trading_day=trading_day)
    job = OpportunityScanDailyJob(
        scoring_service=scoring,
        stock_pool_service=pool,
        watchlist_reader=lambda: {"items": [{"symbol": "600000.SH"}]},
        rule_service=rules,
        trading_day_guard=guard,
        notification_sender=notification_sender or FakeNotificationSender(),
    )
    return job, scoring, pool, rules, guard


def test_non_trading_day_skips_without_scanning():
    job, scoring, pool, rules, guard = make_job(trading_day=False)

    result = asyncio.run(job.execute({}))

    assert result.success is True
    assert result.details["skipped"] == "non_trading_day"
    assert guard.calls == 1
    assert scoring.calls == [] and pool.watchlists == [] and rules.calls == []


def test_daily_scan_filters_sorts_and_creates_top_ten_rules():
    opportunities = [opportunity(f"{index:06d}.SZ", score=80 + index)
                     for index in range(12)]
    opportunities.append(opportunity("799999.SZ", score=79))
    job, scoring, pool, rules, _ = make_job(opportunities)

    result = asyncio.run(job.execute({
        "auto_create_rules": True, "account_name": "agent_brain", "decision_audit_id": "DA-scan",
    }))

    assert result.success is True
    assert result.details["scanned"] == 3
    assert result.details["candidates"] == 10
    assert result.details["created"] == 10
    assert pool.watchlists == [["600000.SH"]]
    assert scoring.calls[0]["symbols"] == ["000001.SZ", "000002.SZ", "600000.SH"]
    assert scoring.calls[0]["weights"] is None
    scores = [opp["score"] for opp in rules.calls[0]]
    assert scores == sorted(scores, reverse=True)
    assert len(rules.calls[0]) == 10
    assert all(opp["scoring_method"] == "ddd_industry_neutral_smooth"
               for opp in rules.calls[0])


def test_min_score_and_risk_filters():
    job, _, _, rules, _ = make_job([
        opportunity("000001.SZ", score=90, risk_level="low"),
        opportunity("000002.SZ", score=85, risk_level="medium"),
        opportunity("000003.SZ", score=95, risk_level="high"),
        opportunity("000004.SZ", score=79, risk_level="low"),
    ])

    result = asyncio.run(job.execute({
        "max_risk_level": "medium", "auto_create_rules": True,
        "account_name": "agent_brain", "decision_audit_id": "DA-scan",
    }))

    assert result.success is True
    assert [opp["symbol"] for opp in rules.calls[0]] == ["000001.SZ", "000002.SZ"]


def test_no_qualified_opportunity_is_success():
    job, _, _, rules, _ = make_job(
        [opportunity("000001.SZ", score=70)], scored=1)

    result = asyncio.run(job.execute({}))

    assert result.success is True
    assert result.details["candidates"] == 0
    assert result.details["created"] == 0
    assert rules.calls == []


def test_empty_universe_is_failure():
    job, scoring, _, _, _ = make_job(symbols=[])
    job._watchlist_reader = lambda: {"items": []}

    result = asyncio.run(job.execute({}))

    assert result.success is False
    assert "宇宙为空" in result.error
    assert scoring.calls == []


def test_zero_successful_scores_is_failure_with_diagnostics():
    job, _, _, rules, _ = make_job([], scored=0)

    result = asyncio.run(job.execute({}))

    assert result.success is False
    assert result.error == "all_scoring_failed"
    assert result.details["scanned"] == 3
    assert result.details["diagnostics"]["scored"] == 0
    assert rules.calls == []


def test_rule_creation_failure_is_not_fake_success():
    job, _, _, _, _ = make_job(
        [opportunity("000001.SZ")],
        rule_results=[{"symbol": "000001.SZ", "action": "failed", "reason": "db"}],
    )

    result = asyncio.run(job.execute({
        "auto_create_rules": True, "account_name": "agent_brain", "decision_audit_id": "DA-scan",
    }))

    assert result.success is False
    assert result.details["failed"] == 1
    assert result.details["rule_results"][0]["reason"] == "db"


def test_default_scan_is_read_only():
    job, _, _, rules, _ = make_job([opportunity("000001.SZ")])
    result = asyncio.run(job.execute({}))
    assert result.success is True
    assert result.details["auto_create_rules"] is False
    assert rules.calls == []


def test_auto_create_job_requires_account_and_audit():
    job, _, _, rules, _ = make_job([opportunity("000001.SZ")])
    result = asyncio.run(job.execute({"auto_create_rules": True}))
    assert result.success is False
    assert rules.calls == []


def test_read_only_scan_does_not_create_rules():
    job, _, _, rules, _ = make_job([opportunity("000001.SZ")])

    result = asyncio.run(job.execute({"auto_create_rules": False}))

    assert result.success is True
    assert result.details["auto_create_rules"] is False
    assert result.details["candidates"] == 1
    assert rules.calls == []


def test_symbols_override_skips_universe_lookup():
    job, scoring, pool, _, _ = make_job([opportunity("000001.SZ")])

    result = asyncio.run(job.execute({"symbols": ["000001.SZ"]}))

    assert result.success is True
    assert scoring.calls[0]["symbols"] == ["000001.SZ"]
    assert pool.watchlists == []


def test_job_is_registered_in_signal_jobs():
    assert any(job.name == "opportunity_scan_daily" for job in SIGNAL_JOBS)


def test_high_score_candidates_send_summary_with_rule_results():
    job, _, _, _, _ = make_job([opportunity("600519.SH", score=92)])

    result = asyncio.run(job.execute({
        "trade_date": "2026-10-27", "auto_create_rules": True,
        "account_name": "agent_brain", "decision_audit_id": "DA-scan",
    }))

    assert result.success is True
    assert result.details["notified"] is True
    title, body = job._notification_sender.calls[0]
    assert title == "【每日机会扫描】2026-10-27｜1 个高分机会"
    assert "600519.SH" in body and "92 分" in body
    assert "已建规则 #1" in body


def test_zero_or_low_score_candidates_do_not_send_notification():
    job, _, _, _, _ = make_job([opportunity("000001.SZ", score=75)], scored=1)

    result = asyncio.run(job.execute({"min_score": 70}))

    assert result.success is True
    assert result.details["candidates"] == 1
    assert result.details["notified"] is False
    assert job._notification_sender.calls == []


def test_notification_failure_marks_job_failed():
    sender = FakeNotificationSender(delivered=False)
    job, _, _, _, _ = make_job(
        [opportunity("000001.SZ")], notification_sender=sender)

    result = asyncio.run(job.execute({
        "auto_create_rules": True, "account_name": "agent_brain", "decision_audit_id": "DA-scan",
    }))

    assert result.success is False
    assert result.details["notified"] is False
    assert result.details["notification_error"] == "sender_returned_false"
    assert result.details["created"] == 1
    assert "盯盘群通知失败" in result.error


def test_notify_false_disables_delivery():
    job, _, _, _, _ = make_job([opportunity("000001.SZ")])

    result = asyncio.run(job.execute({"notify": False}))

    assert result.success is True
    assert result.details["notified"] is False
    assert job._notification_sender.calls == []


def test_rule_failure_still_sends_summary_with_failure_status():
    job, _, _, _, _ = make_job(
        [opportunity("000001.SZ")],
        rule_results=[{"symbol": "000001.SZ", "action": "failed", "reason": "db"}],
    )

    result = asyncio.run(job.execute({
        "auto_create_rules": True, "account_name": "agent_brain", "decision_audit_id": "DA-scan",
    }))

    assert result.success is False
    assert result.details["notified"] is True
    assert "创建失败：db" in job._notification_sender.calls[0][1]
