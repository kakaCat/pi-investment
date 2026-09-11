"""端口装配单测（REQ-f08def DDD 整改，w-c8cae280）

为什么加：2026-09-11 一次重构用 str.replace 改 InterventionLedger 时**静默没命中**
（原类没有 __init__），结果工厂传参 TypeError、**引擎起不来**，而测试全绿——因为没有任何
测试构造过这些应用服务。装配签名必须有测试守着。
"""
from application.services.watch_engine.intervention_ledger import InterventionLedger


class FakeInterventionRepo:
    def __init__(self):
        self.records = []

    def count_today(self):
        return 7

    def record(self, **kw):
        self.records.append(kw)

    def summary_today(self):
        return {"interventions_today": 7, "by_outcome": {}, "valuable_actions": 0, "yield_per_wake": None}


def test_ledger_accepts_injected_port():
    repo = FakeInterventionRepo()
    led = InterventionLedger(repo)
    assert led.count_today() == 7
    led.record(symbol="600150", rule_id=135, trigger_ids=[1])
    assert repo.records and repo.records[0]["symbol"] == "600150"
    assert led.summary_today()["interventions_today"] == 7


def test_ledger_is_safe_without_port():
    led = InterventionLedger()
    assert led.count_today() == 0
    led.record(symbol="600150")
    assert led.summary_today()["interventions_today"] == 0
