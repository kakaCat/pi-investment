"""策略进化引擎单测（RFC 012 P1，2026-09-03 w-8366e526）

覆盖：数值参数提取、确定性变体网格、批内 fitness 归一数学、run 全流程
（真实回测 mock 腿）、degraded 诚实路径（script/无参数/零交易）、落库调用。
"""
import pytest
from unittest.mock import Mock

from application.services.strategy_evolution_service import (
    StrategyEvolutionService,
    _normalize,
    FITNESS_WEIGHTS,
)

# 635 macd-golden-cross-v1 同形参数（int 三个）
BASE_PARAMS = {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}

# 可复用 metrics 构造：trade>0 的"有效"回测结果
def mk_metrics(total_return=0.1, sharpe=1.0, win_rate=0.5, trades=20):
    return {
        'total_return': total_return, 'annual_return': total_return,
        'sharpe_ratio': sharpe, 'sortino_ratio': sharpe, 'calmar_ratio': sharpe,
        'max_drawdown': -0.08, 'volatility': 0.2, 'downside_volatility': 0.15,
        'win_rate': win_rate, 'profit_loss_ratio': 1.5, 'avg_holding_days': 5,
        'total_trades': trades, 'profit_factor': 1.2,
        'trades': [{'x': 1}], 'equity_curve': [{'y': 1}],
    }


class TestCollectNumericParams:
    def test_dict_shape(self):
        parsed = {'fast_period': 12, 'slow_period': '26', 'signal_period': 9,
                  'use_bull_filter': True, 'note': 'keep'}
        out = StrategyEvolutionService._collect_numeric_params(parsed)
        assert out == {'fast_period': 12, 'slow_period': 26, 'signal_period': 9}
        assert 'use_bull_filter' not in out  # bool 不可进化
        assert 'note' not in out  # 字符串不可数值化

    def test_list_declaration_shape(self):
        parsed = [
            {'name': 'fast_period', 'type': 'int', 'default': 12, 'description': '快线'},
            {'name': 'slow_period', 'type': 'int', 'default': 26},
            {'name': 'signal_period', 'type': 'float', 'default': 9.5},
            {'name': 'strategy_name', 'type': 'str', 'default': 'macd'},
        ]
        out = StrategyEvolutionService._collect_numeric_params(parsed)
        assert out == {'fast_period': 12, 'slow_period': 26, 'signal_period': 9.5}

    def test_blacklist_and_empty(self):
        assert StrategyEvolutionService._collect_numeric_params(
            {'stop_loss_pct': -8, 'fast_period': 12}) == {'fast_period': 12}
        assert StrategyEvolutionService._collect_numeric_params({}) == {}
        assert StrategyEvolutionService._collect_numeric_params(None) == {}

    def test_normalize(self):
        assert _normalize('12') == 12
        assert _normalize('9.5') == 9.5
        assert _normalize(True) is None
        assert _normalize('abc') is None
        assert _normalize(None) is None


class TestGenerateVariants:
    def test_deterministic_int_grid(self):
        vs = StrategyEvolutionService._generate_variants(BASE_PARAMS, 0.10)
        # 3 参 × ± = 6 变体（无跨参组合、无 base 副本）
        assert len(vs) == 6
        keys = {StrategyEvolutionService._variant_key(v) for v in vs}
        assert len(keys) == 6
        # 只改 fast 的变体：12*1.1→13、12*0.9→11（int 圆整）
        fast_only = [v for v in vs if v['slow_period'] == 26 and v['signal_period'] == 9]
        assert {v['fast_period'] for v in fast_only} == {11, 13}
        slow_only = [v for v in vs if v['fast_period'] == 12 and v['signal_period'] == 9]
        assert {v['slow_period'] for v in slow_only} == {23, 29}
        # 确定性：两次生成一致
        vs2 = StrategyEvolutionService._generate_variants(BASE_PARAMS, 0.10)
        assert vs == vs2

    def test_float_params_and_min_floor(self):
        vs = StrategyEvolutionService._generate_variants({'p': 1.0, 'q': 2.5}, 0.05)
        p_only = [v for v in vs if v['q'] == 2.5]
        assert {v['p'] for v in p_only} == {0.95, 1.05}
        q_only = [v for v in vs if v['p'] == 1.0]
        assert {v['q'] for v in q_only} == {2.375, 2.625}
        # int 下限 1：period=1 无论 ±20% 圆整后都回到 1 == 原值 → 无有效变体
        vs2 = StrategyEvolutionService._generate_variants({'period': 1}, 0.20)
        assert vs2 == []

    def test_skip_nonpositive_float(self):
        # base 为 0.05 的 float 参数 ±5% 下界非正被跳过
        vs = StrategyEvolutionService._generate_variants({'fee': 0.01}, 0.20)
        for v in vs:
            assert v['fee'] > 0


class TestNormalizeBatch:
    def _batch_results(self, metrics_list):
        results = []
        for i, m in enumerate(metrics_list):
            p = {'p': i}
            results.append({'ok': True, 'params': p,
                            'params_key': StrategyEvolutionService._variant_key(p),
                            'metrics': m})
        return results

    def test_minmax_extremes(self):
        # 两个变体：一个全维最差(0)、一个全维最好(1) → fitness 0 与 1
        results = self._batch_results([
            mk_metrics(0.05, 0.5, 0.30),
            mk_metrics(0.25, 2.5, 0.80),
        ])
        out = StrategyEvolutionService._normalize_batch(results)
        k0 = StrategyEvolutionService._variant_key({'p': 0})
        k1 = StrategyEvolutionService._variant_key({'p': 1})
        assert out[k0] == pytest.approx(0.0, abs=1e-9)
        assert out[k1] == pytest.approx(1.0, abs=1e-9)

    def test_middle_value_weighted(self):
        # 3 变体：A=中、B=最差、C=最好；A 每维 0.5 → fitness=0.5
        results = self._batch_results([
            mk_metrics(0.15, 1.5, 0.55),   # A 中间
            mk_metrics(0.05, 0.5, 0.30),   # B 最差
            mk_metrics(0.25, 2.5, 0.80),   # C 最好
        ])
        out = StrategyEvolutionService._normalize_batch(results)
        ka = StrategyEvolutionService._variant_key({'p': 0})
        assert out[ka] == pytest.approx(0.5, abs=1e-9)

    def test_all_equal_neutral(self):
        results = self._batch_results([mk_metrics(0.1, 1.0, 0.5), mk_metrics(0.1, 1.0, 0.5)])
        out = StrategyEvolutionService._normalize_batch(results)
        assert all(v == pytest.approx(0.5, abs=1e-9) for v in out.values())

    def test_missing_dim_neutral(self):
        # 一个变体缺 win_rate（NaN 语义）→ 该维 0.5
        m_ok = mk_metrics(0.05, 0.5, 0.30)
        m_bad = dict(mk_metrics(0.25, 2.5, 0.80))
        del m_bad['win_rate']
        results = self._batch_results([m_ok, m_bad])
        out = StrategyEvolutionService._normalize_batch(results)
        kb = StrategyEvolutionService._variant_key({'p': 1})
        # total_return/sharpe 都归一为 1，win_rate 0.5 → 0.5*1+0.3*1+0.2*0.5 = 0.9
        assert out[kb] == pytest.approx(0.9, abs=1e-9)


def _make_fake_service(params_metrics_pairs):
    """构造 mock StrategyCodeService：backtest_strategy 按 params_override 返回指定 metrics。

    params_metrics_pairs: [(params_dict, metrics_dict), ...]（dict 不可哈希，用列表）；
    未命中默认返回平庸有效结果（trade>0）。
    """
    svc = Mock()
    svc.strategy_repo.get_by_id.return_value = {
        'strategy_id': 635, 'code_type': 'indicator',
        'parsed_params': {'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
    }
    def _backtest(strategy_id=None, symbol=None, start_date=None, end_date=None,
                  initial_cash=None, params_override=None, **kw):
        for cand, m in params_metrics_pairs:
            if cand == params_override:
                return m
        return mk_metrics(0.05, 0.3, 0.40, trades=5)  # 未命中：有效但平庸
    svc.backtest_strategy.side_effect = _backtest
    return svc


class TestRunFullFlow:
    def _service(self, params_metrics_pairs):
        svc = _make_fake_service(params_metrics_pairs)
        repo = Mock()
        return StrategyEvolutionService(strategy_service=svc, evolution_repo=repo), svc, repo

    def test_run_picks_best_variant_and_persists(self):
        base = dict(BASE_PARAMS)
        # fast_period=13 变体明显优于 base 与其他 → 应选为 best
        better = {k: v for k, v in base.items()}
        better['fast_period'] = 13
        service, svc, repo = self._service([
            (base, mk_metrics(0.15, 1.5, 0.55, trades=30)),
            (better, mk_metrics(0.30, 2.8, 0.80, trades=40)),
        ])
        result = service.run(strategy_id=635, symbol='600519',
                             start_date='2025-01-01', end_date='2025-12-31',
                             generations=1, initial_cash=100000)
        assert result['success'] is True
        assert result['data_source'] == 'qv2_real'
        assert result['degraded_reason'] is None
        assert result['best_params'] == better
        # better 每维全批最优 → fitness=1
        assert result['fitness'] == pytest.approx(1.0, abs=1e-9)
        # improvement = best(1) − base 同批分（base 非 0：tr 0.4/sh 0.48/wr 0.375 → ≈0.419）
        # → 0 < improvement < fitness
        assert 0 < result['fitness_improvement'] < result['fitness']
        assert result['fitness_improvement'] == pytest.approx(0.5808, abs=0.01)
        # 变体数：3 参 ±10% ×2 + base = 7
        assert result['total_variants'] == 7
        assert result['success_variants'] == 7
        assert result['degraded_variants'] == 0
        # proposals 按 fitness 降序、首条是 best
        assert len(result['proposals']) == 7
        assert result['proposals'][0]['params'] == better
        assert '真实回测' in result['proposals'][0]['rationale']
        # 落库一次（全批单次 record_batch），7 行
        repo.record_batch.assert_called_once()
        batch = repo.record_batch.call_args[0][0]
        assert len(batch) == 7
        # 每行有 status/params/metrics 裁剪（无 trades/equity_curve 大数组）
        for row in batch:
            assert row['status'] in ('ok', 'degraded')
            if row['metrics']:
                assert 'equity_curve' not in row['metrics']
                assert 'trades' not in row['metrics']
                assert 'total_return' in row['metrics']

    def test_zero_trade_base_is_degraded_not_fake_zero(self):
        service, svc, repo = self._service([(dict(BASE_PARAMS), mk_metrics(trades=0))])
        result = service.run(strategy_id=635, symbol='600519',
                             start_date='2025-01-01', end_date='2025-12-31')
        assert result['data_source'] == 'degraded'
        assert result['fitness'] is None
        assert result['best_params'] is None
        assert result['proposals'] == []
        assert '零交易' in result['degraded_reason']
        # 防并行回归：base 判定 degraded 后必须短路——只回测了 base（1 次），
        # 变体不得进 ThreadPoolExecutor 空跑（若先并行全跑再判 degraded 这里会是 7）
        assert svc.backtest_strategy.call_count == 1
        # 不产任何"0 分"假基线；但落库 degraded 行留痕
        repo.record_batch.assert_called_once()
        row = repo.record_batch.call_args[0][0][0]
        assert row['status'] == 'degraded'

    def test_script_code_type_honest_degraded(self):
        svc = Mock()
        svc.strategy_repo.get_by_id.return_value = {
            'strategy_id': 999, 'code_type': 'script',
            'parsed_params': [{'name': 'x', 'type': 'int', 'default': 1}],
        }
        service = StrategyEvolutionService(strategy_service=svc, evolution_repo=Mock())
        result = service.run(strategy_id=999, symbol='600519',
                             start_date='2025-01-01', end_date='2025-12-31')
        assert result['data_source'] == 'degraded'
        assert 'script' in result['degraded_reason']
        svc.backtest_strategy.assert_not_called()  # 不该白跑回测

    def test_no_numeric_params_honest_degraded(self):
        svc = Mock()
        svc.strategy_repo.get_by_id.return_value = {
            'strategy_id': 100, 'code_type': 'indicator',
            'parsed_params': [{'name': 'mode', 'type': 'str', 'default': 'trend'}],
        }
        service = StrategyEvolutionService(strategy_service=svc, evolution_repo=Mock())
        result = service.run(strategy_id=100, symbol='600519',
                             start_date='2025-01-01', end_date='2025-12-31')
        assert result['data_source'] == 'degraded'
        assert '无数值进化参数' in result['degraded_reason']
        svc.backtest_strategy.assert_not_called()

    def test_missing_strategy_honest_degraded(self):
        svc = Mock()
        svc.strategy_repo.get_by_id.return_value = None
        service = StrategyEvolutionService(strategy_service=svc, evolution_repo=Mock())
        result = service.run(strategy_id=404, symbol='600519',
                             start_date='2025-01-01', end_date='2025-12-31')
        assert result['data_source'] == 'degraded'
        assert '不存在' in result['degraded_reason']

    def test_generations_3_full_grid_and_propose_mode(self):
        base = dict(BASE_PARAMS)
        service, svc, repo = self._service([(base, mk_metrics(0.1, 1.0, 0.5, trades=10))])
        # generations=1（propose 快评，±10% 单档）：3 参 × ± + base = 7 变体
        rp = service.run(strategy_id=635, symbol='600519',
                         start_date='2025-01-01', end_date='2025-12-31', mode='propose')
        assert rp['total_variants'] == 7
        assert rp['success_variants'] == 7
        # generations=3：档 20/10/5 全开 → 单档 7、跨档整数圆整去重后 11< n ≤ 19
        # （12±% → {10,11,13,14}、26±% → {21,23,25,27,29,31}、9±% → {7,8,10,11}，
        #   base + 去重后合计 = 1+4+6+4 = 15）
        r3 = service.run(strategy_id=635, symbol='600519',
                         start_date='2025-01-01', end_date='2025-12-31', generations=3)
        assert 15 <= r3['total_variants'] <= 19
        assert r3['total_variants'] > rp['total_variants']
        assert r3['success_variants'] == r3['total_variants']
