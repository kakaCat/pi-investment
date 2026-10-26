from types import SimpleNamespace

from application.risk import IntradayRiskService


class FakePositionRepo:
    def __init__(self, positions=None, fail=False):
        self.positions = positions or []
        self.fail = fail

    def get_all_positions(self, account_name):
        if self.fail:
            raise RuntimeError('db unavailable')
        return self.positions


class FakeTrader:
    def __init__(self, fail=False):
        self.fail = fail
        self.sells = []

    def sell(self, symbol, quantity, price):
        if self.fail:
            raise RuntimeError('sell failed')
        self.sells.append((symbol, quantity, price))
        return {'status': 'filled'}


def _service(positions, price, trader=None, observer=None, fail_repo=False):
    return IntradayRiskService(
        position_repo=FakePositionRepo(positions, fail=fail_repo),
        trader=trader or FakeTrader(),
        engine=SimpleNamespace(account_name='v13_simulation', config={}),
        price_provider=lambda symbol: price,
        price_observer=observer,
    )


def test_fixed_stop_loss_executes_at_realtime_price(monkeypatch):
    monkeypatch.setattr(
        'application.risk.intraday_risk_service.get_notification_facade',
        lambda: None,
    )
    trader = FakeTrader()
    observed = []
    service = _service(
        [{
            'symbol': '301102',
            'avg_cost': 11.42,
            'shares_available': 1000,
            'shares_total': 1000,
            'peak_price': 12.0,
        }],
        price=9.99,
        trader=trader,
        observer=lambda symbol, price: observed.append((symbol, price)),
    )

    result = service.check_positions('2026-10-26')

    assert result['success'] is True
    assert result['checked'] == 1
    assert result['quote_failures'] == 0
    assert trader.sells == [('301102', 1000, 9.99)]
    assert observed == [('301102', 9.99)]
    assert result['actions'][0]['trigger']['rule'] == 'stop_loss'


def test_trailing_stop_uses_persisted_peak_price(monkeypatch):
    monkeypatch.setattr(
        'application.risk.intraday_risk_service.get_notification_facade',
        lambda: None,
    )
    trader = FakeTrader()
    service = _service(
        [{
            'symbol': '300296',
            'avg_cost': 5.64,
            'shares_available': 2000,
            'shares_total': 2000,
            'peak_price': 12.0,
        }],
        price=11.0,
        trader=trader,
    )

    result = service.check_positions('2026-10-26')

    assert result['success'] is True
    assert trader.sells == [('300296', 2000, 11.0)]
    assert result['actions'][0]['trigger']['rule'] == 'trailing_stop'


def test_missing_quote_fails_without_stale_price_fallback(monkeypatch):
    monkeypatch.setattr(
        'application.risk.intraday_risk_service.get_notification_facade',
        lambda: None,
    )
    trader = FakeTrader()
    service = _service(
        [{
            'symbol': '301102',
            'avg_cost': 11.42,
            'shares_available': 1000,
            'shares_total': 1000,
            'current_price': 9.99,
        }],
        price=None,
        trader=trader,
    )

    result = service.check_positions('2026-10-26')

    assert result['success'] is False
    assert result['quote_failures'] == 1
    assert trader.sells == []


def test_failed_sell_fails_check(monkeypatch):
    monkeypatch.setattr(
        'application.risk.intraday_risk_service.get_notification_facade',
        lambda: None,
    )
    service = _service(
        [{
            'symbol': '301102',
            'avg_cost': 11.42,
            'shares_available': 1000,
            'shares_total': 1000,
        }],
        price=9.99,
        trader=FakeTrader(fail=True),
    )

    result = service.check_positions('2026-10-26')

    assert result['success'] is False
    assert result['actions'][0]['status'] == 'failed'


def test_position_fetch_failure_fails_check(monkeypatch):
    monkeypatch.setattr(
        'application.risk.intraday_risk_service.get_notification_facade',
        lambda: None,
    )
    service = _service([], price=10.0, fail_repo=True)

    result = service.check_positions('2026-10-26')

    assert result['success'] is False
    assert result['position_fetch_failed'] is True
    assert result['checked'] == 0


def test_intraday_job_routes_real_strategy_account(monkeypatch):
    captured = {}

    class FakeSimulationTrader:
        def __init__(self, account_name):
            self.account_name = account_name
            self.get_price = lambda symbol: 9.99

    class FakePositionRepository:
        def __init__(self):
            self.updates = []

        def get_all_positions(self, account_name):
            return [
                SimpleNamespace(
                    symbol='301102',
                    shares_total=1000,
                    shares_available=1000,
                    avg_cost=11.42,
                )
            ]

        def upsert_position(self, **kwargs):
            self.updates.append(kwargs)

    class FakeIntradayRiskService:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def check_positions(self, date):
            return {
                'date': date,
                'account_name': captured['engine'].account_name,
                'checked': 1,
                'quote_failures': 0,
                'actions': [{'symbol': '301102'}],
                'success': True,
            }

    import live_trading.simulation_trader as trader_module
    import application.risk as risk_module
    import adapters.outbound.repositories.simulation_position_repository as position_module
    from qs_ops.infrastructure.jobs import strategy_trading_job

    monkeypatch.setattr(trader_module, 'SimulationTrader', FakeSimulationTrader)
    monkeypatch.setattr(risk_module, 'IntradayRiskService', FakeIntradayRiskService)
    monkeypatch.setattr(
        position_module,
        'SimulationPositionRepository',
        FakePositionRepository,
    )
    monkeypatch.setattr(
        strategy_trading_job,
        '_intraday_strategy_targets',
        lambda params: [({
            'strategy': {'account_name': 'v13_simulation'},
            'risk': {
                'single_stock_stop_loss': -0.12,
                'trailing_stop_pct': -0.08,
            },
        }, None)],
    )

    result = strategy_trading_job.intraday_risk_check(date='2026-10-26')

    assert result['success'] is True
    assert result['checked'] == 1
    assert list(result['accounts']) == ['v13_simulation']
    assert captured['engine'].account_name == 'v13_simulation'
    assert captured['stop_loss_pct'] == -0.12
    assert captured['trailing_stop_pct'] == -0.08
    assert captured['price_provider']('301102') == 9.99


def test_intraday_targets_skip_disabled_strategies(monkeypatch):
    from qs_strategy.application.services.strategy_service import StrategyService
    from qs_ops.infrastructure.jobs import strategy_trading_job

    class FakeStrategyService:
        def __init__(self):
            self._configs = {
                'v13': {
                    'strategy': {'account_name': 'v13_simulation', 'enabled': True},
                    'risk': {},
                },
                'v14': {
                    'strategy': {'account_name': 'v14_simulation', 'enabled': False},
                    'risk': {},
                },
            }

        def list_strategies(self):
            return ['v13', 'v14']

        def get_config(self, name):
            return self._configs[name]

    monkeypatch.setattr(StrategyService, '__new__', lambda cls: FakeStrategyService())

    targets = strategy_trading_job._intraday_strategy_targets({})

    assert [target[0]['strategy']['account_name'] for target in targets] == ['v13_simulation']
