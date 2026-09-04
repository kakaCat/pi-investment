"""策略进化引擎（RFC 012 P1，2026-09-03 w-8366e526）

替代链：Agent OS legacy evolution（evolution_handler.go 的 0.05×i 占位阶梯，见
docs/rfcs/012-strategy-evolution-engine.md）→ 基于 qv2 真实回测的策略级参数进化。

设计要点（全部对齐 RFC 012 §2/§4）：
- 只做**策略参数邻域网格**进化，不修改策略代码（无任意代码变异，§4）。
- 网格 = 默认参数(base) + 每参 × 每档步长 ± 两个变体（单维，避免笛卡尔爆炸）；
  步长档序列 (20%, 10%, 5%) 由 generations 截取：gen=1 只 ±10%（快评）、
  gen=2 ±20/±10、gen=3 全档（默认）。mode=propose 等价 generations=1。
- 每变体都用 StrategyCodeService.backtest_strategy(params_override=...) **真实回测**，
  拒绝一切占位/估计数值（Agent OS 0.05×i 是反面教材）。
- **单批一次归一**：fitness = 0.5·收益百分位 + 0.3·夏普百分位 + 0.2·胜率百分位
  （§4：同一批变体窗口内相对 min-max 归一，防跨窗口/跨批不可比）。
  best 与 fitness_improvement 都在同批内比较，无跨批混比。
- 零交易 / 回测失败的变体记 status=degraded + degraded_reason，绝不产出 0 分冒充有效。
- 无数值参数的代码策略（script/常量写死）→ 诚实报错不可进化，不生成任何变体。

错误哲学：宁可 degraded 也不给假数。单变体失败只记该变体 degraded 不中断整轮；
整轮全部失败（含 base）才整体 degraded。
"""
from __future__ import annotations

import math
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

#: 网格步长档序列（RFC 012 §P1：±20% → ±10% → ±5%）
GRID_STEPS = (0.20, 0.10, 0.05)
#: fitness 权重（RFC 012 §4：0.5·收益 + 0.3·夏普 + 0.2·胜率）
FITNESS_WEIGHTS = {'total_return': 0.5, 'sharpe_ratio': 0.3, 'win_rate': 0.2}
#: 落库 metrics 裁剪键（丢弃 trades/equity_curve 大数组）
METRICS_PERSIST_KEYS = (
    'total_return', 'annual_return', 'sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
    'max_drawdown', 'volatility', 'downside_volatility', 'win_rate', 'profit_loss_ratio',
    'avg_holding_days', 'total_trades', 'profit_factor',
)
MIN_TRADES = 1  # 回测零交易视为无信号退化为 degraded，不产出 0 分

#: 策略参数里应跳过不作为进化参数的键（strategy 级控制字段，非可调数值参数）
NON_EVOLVABLE_KEYS = {
    'stop_loss_pct', 'take_profit_pct', 'entry_pct',
    'stopLossPct', 'takeProfitPct', 'entryPct',
    'bear_filter_enabled',
}


def _normalize(v: Any) -> Any:
    """从声明/落库混入类型里取出可数值化的参数值（否则 None）。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            f = float(v)
            return int(f) if f.is_integer() else f
        except (TypeError, ValueError):
            return None
    return None


class StrategyEvolutionService:
    """基于 qv2 真实回测的策略参数进化服务（单批邻域网格）"""

    def __init__(
        self,
        strategy_service: Any = None,
        evolution_repo: Any = None,
        max_workers: int = 6,
    ):
        """
        Args:
            strategy_service: StrategyCodeService（backtest_strategy 执行腿），
                不传则运行时懒加载（见 run 内 _resolve_strategy_service）
            evolution_repo: 进化结果落库仓库；不传则运行时懒加载
            max_workers: 并行回测线程数
        """
        self._strategy_service = strategy_service
        self._evolution_repo = evolution_repo
        self.max_workers = max_workers
        self._resolved = {'strategy_service': False, 'evolution_repo': False}

    # ---------------- 运行时依赖解析（延迟 import，避免启动时序耦合） ----------------

    def _resolve_strategy_service(self) -> Any:
        if self._strategy_service is None and not self._resolved['strategy_service']:
            from infrastructure.services.service_factory import ServiceFactory
            self._strategy_service = ServiceFactory.get_strategy_code_service()
            self._resolved['strategy_service'] = True
        return self._strategy_service

    def _resolve_evolution_repo(self) -> Any:
        if self._evolution_repo is None and not self._resolved['evolution_repo']:
            from adapters.outbound.repositories.strategy_evolution_run_repository import (
                StrategyEvolutionRunORMRepository,
            )
            self._evolution_repo = StrategyEvolutionRunORMRepository()
            self._resolved['evolution_repo'] = True
        return self._evolution_repo

    # ---------------- 主入口 ----------------

    def run(
        self,
        strategy_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        mode: str = 'full',
        generations: int = 3,
        initial_cash: float = 1000000,
    ) -> Dict[str, Any]:
        """对策略跑一轮真实回测进化（单批网格）。

        Returns:
            {
                'success': True,
                'run_id': str,
                'strategy_id': int, 'symbol': str, 'mode': str,
                'kline_window': 'start~end',
                'fitness': float|None,          # best 变体同批百分位合成（None=data_source=degraded）
                'fitness_improvement': float|None,  # best − base 同批分差
                'best_params': Dict|None,
                'best_metrics': Dict|None,
                'data_source': 'qv2_real' | 'degraded',
                'degraded_reason': str|None,
                'proposals': [ {variant, params, estimated_fitness, metrics, rationale} ... ],
                'total_variants': int, 'success_variants': int, 'degraded_variants': int,
                'run_at': 'YYYY-MM-DD HH:MM:SS',
            }
        """
        strategy_service = self._resolve_strategy_service()
        evolution_repo = self._resolve_evolution_repo()

        strategy_id = int(strategy_id)
        generations = max(1, min(int(generations or 1), 3))
        if mode == 'propose':
            generations = 1
        # 步长档：gen=1 快评 ±10%；gen=2 ±20/±10；gen=3 全档 ±20/±10/±5
        steps = (GRID_STEPS[1],) if generations == 1 else GRID_STEPS[:generations]
        run_id = uuid.uuid4().hex[:12]
        kline_window = f"{start_date}~{end_date}"
        run_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # 1. 取策略 + 数值参数面（无参数 → 诚实不可进化）
        try:
            strategy = strategy_service.strategy_repo.get_by_id(strategy_id)
        except Exception as e:
            return self._degraded_run(run_id, strategy_id, symbol, kline_window, mode, run_at,
                                      f"策略读取失败: {e}")
        if not strategy:
            return self._degraded_run(run_id, strategy_id, symbol, kline_window, mode, run_at,
                                      f"策略不存在: {strategy_id}")
        code_type = strategy.get('code_type')
        if code_type != 'indicator':
            return self._degraded_run(run_id, strategy_id, symbol, kline_window, mode, run_at,
                                      f"code_type={code_type}：仅 indicator 数值参数策略可自动进化"
                                      f"（script/代码常量无参数网格，RFC 012 §4 禁止代码变异）")

        parsed_params = strategy.get('parsed_params') or {}
        numeric_params = self._collect_numeric_params(parsed_params)
        if not numeric_params:
            return self._degraded_run(run_id, strategy_id, symbol, kline_window, mode, run_at,
                                      f"策略 {strategy_id} 无数值进化参数"
                                      f"（parsed_params={parsed_params!r}）")

        base_params = dict(numeric_params)

        # 2. 生成网格变体（含 base 对照组）
        variants: List[Dict[str, Any]] = [dict(base_params)]  # variant 0 = base
        for step in steps:
            for v in self._generate_variants(base_params, step):
                if v not in variants:
                    variants.append(v)
        logger.info(f"策略进化开始: run_id={run_id} strategy={strategy_id} {symbol} "
                    f"{kline_window} base_params={base_params} 档位={steps} "
                    f"变体数={len(variants)} mode={mode}")

        # 3. 真实回测：base（variant 0）串行先行做 degraded 判定，通过后余量变体
        #    并行执行（StrategyOptimizer 同款 ThreadPoolExecutor 腿——先例证明
        #    backtest_strategy 线程安全）；按 variant index 保序组装，fitness 归一不依赖顺序。
        base_result = self._run_one(variants[0], strategy_id, symbol, start_date, end_date,
                                    initial_cash)
        base_result['variant'] = 0
        base_result['params'] = dict(variants[0])
        results: List[Dict[str, Any]] = [base_result]
        if not base_result['ok']:
            return self._degraded_run(
                run_id, strategy_id, symbol, kline_window, mode, run_at,
                f"基线回测失败：{base_result['reason']}（未评估任何变体）")
        if base_result['metrics'].get('total_trades', 0) < MIN_TRADES:
            return self._degraded_run(
                run_id, strategy_id, symbol, kline_window, mode, run_at,
                f"基线回测零交易（total_trades=0，窗口 {kline_window} 无信号），"
                f"拒绝以 0 收益为基线进化——先检查标的/窗口/策略参数有效性")

        rest_indices = list(range(1, len(variants)))
        if rest_indices:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_idx = {
                    executor.submit(self._run_one, variants[i], strategy_id, symbol,
                                    start_date, end_date, initial_cash): i
                    for i in rest_indices
                }
                by_idx: Dict[int, Dict[str, Any]] = {}
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    res = future.result()
                    res['variant'] = idx
                    res['params'] = dict(variants[idx])
                    by_idx[idx] = res
            results.extend(by_idx[i] for i in rest_indices)

        # 4. 单批 fitness 归一（base 与所有变体同批，best/improvement 同批可比）
        valid = [r for r in results
                 if r['ok'] and r['metrics'].get('total_trades', 0) >= MIN_TRADES]
        normed = self._normalize_batch(valid)
        for r in results:
            r['fitness'] = normed.get(self._variant_key(r['params']))
        base_fitness = normed.get(self._variant_key(base_params))

        # 5. 选优 + proposals
        best = max(
            (r for r in results if r['fitness'] is not None),
            key=lambda r: r['fitness'], default=None)
        proposals: List[Dict[str, Any]] = []
        for r in sorted((x for x in results if x['fitness'] is not None),
                        key=lambda x: x['fitness'], reverse=True):
            proposals.append({
                'variant': r['variant'],
                'params': dict(r['params']),
                'estimated_fitness': round(r['fitness'], 6),
                'metrics': self._clip_metrics(r['metrics']),
                'rationale': self._rationale(r['params'], r['metrics']),
            })

        # 6. 落库（含 base 对照组与全部 degraded 行，供 leaderboard/审计）
        rows = [self._row_for(run_id, strategy_id, symbol, kline_window, mode, initial_cash,
                              r, run_at) for r in results]
        try:
            evolution_repo.record_batch(rows)
        except Exception as e:
            logger.warning(f"run_id={run_id} 落库失败: {e}")

        success_variants = sum(1 for r in results if r['fitness'] is not None)
        result = {
            'success': True,
            'run_id': run_id,
            'strategy_id': strategy_id,
            'symbol': symbol,
            'mode': mode,
            'kline_window': kline_window,
            'data_source': 'qv2_real',
            'total_variants': len(results),
            'success_variants': success_variants,
            'degraded_variants': len(results) - success_variants,
            'run_at': run_at,
            'proposals': proposals,
        }
        if best is not None:
            result['fitness'] = round(best['fitness'], 6)
            result['fitness_improvement'] = round(best['fitness'] - (base_fitness or 0.5), 6)
            result['best_params'] = dict(best['params'])
            result['best_metrics'] = self._clip_metrics(best['metrics'])
            result['degraded_reason'] = None
        else:
            # 理论不可达（base 已 valid），防御性降级
            result.update({
                'fitness': None, 'fitness_improvement': None, 'best_params': None,
                'data_source': 'degraded',
                'degraded_reason': '所有候选变体回测失败/零交易，无有效 fitness',
            })
        logger.info(f"策略进化完成: run_id={run_id} fitness={result.get('fitness')} "
                    f"improvement={result.get('fitness_improvement')} "
                    f"variants={len(results)} (degraded={result['degraded_variants']})")
        return result

    # ---------------- 参数/变体 ----------------

    @staticmethod
    def _collect_numeric_params(parsed_params: Any) -> Dict[str, Any]:
        """从策略 parsed_params 提取可进化的数值参数（int/float/可数值化字符串）。

        兼容两种形状：list[{'name','type','default',...}]（create 时 params 声明）
        与 dict[name→value]（DB parsed_params JSON 落库形状）。
        """
        out: Dict[str, Any] = {}
        if isinstance(parsed_params, dict):
            for k, v in parsed_params.items():
                if k in NON_EVOLVABLE_KEYS:
                    continue
                nv = _normalize(v)
                if nv is not None:
                    out[k] = nv
            return out
        if isinstance(parsed_params, list):
            for item in parsed_params:
                if not isinstance(item, dict):
                    continue
                name = item.get('name')
                if not name or name in NON_EVOLVABLE_KEYS:
                    continue
                raw = item.get('default')
                if raw is None:
                    raw = item.get('value')
                nv = _normalize(raw)
                if nv is not None:
                    out[name] = nv
            return out
        return out

    @classmethod
    def _generate_variants(cls, base: Dict[str, Any], step: float) -> List[Dict[str, Any]]:
        """围绕 base 生成单维 ±step 邻域变体（每参两个，避免笛卡尔爆炸）。

        确定性：纯算术无随机。int 参数圆整 ≥1（周期下限）；float 参数保留 4 位。
        网格语义：本方法 = base 邻域百分比（进化用，先跑 base 再试邻近），与
        application/services/search_space.py 的 SearchSpace（min/max/step 显式搜索域，
        strategies/optimize 人工调参用）互补——改动任一前先核对另一处，勿让两套
        网格逻辑漂移。
        """
        variants: List[Dict[str, Any]] = []
        for name, value in base.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            for direction in (1, -1):
                raw = value * (1 + direction * step)
                if isinstance(value, int):
                    new_val = int(round(raw))
                    if new_val < 1:
                        new_val = 1
                else:
                    new_val = round(raw, 4)
                    if new_val <= 0:
                        continue
                if new_val == value:
                    continue
                v = dict(base)
                v[name] = new_val
                variants.append(v)
        return variants

    @staticmethod
    def _variant_key(params: Dict[str, Any]) -> str:
        """参数组合稳定指纹（去重/归一键）。"""
        return '|'.join(f"{k}={params[k]}" for k in sorted(params))

    # ---------------- 单次回测 ----------------

    def _run_one(self, params: Dict[str, Any], strategy_id: int, symbol: str,
                 start_date: str, end_date: str, initial_cash: float) -> Dict[str, Any]:
        """调 backtest_strategy 跑一个变体。异常/零交易记原因，不抛到外层。"""
        strategy_service = self._resolve_strategy_service()
        try:
            metrics = strategy_service.backtest_strategy(
                strategy_id=strategy_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                params_override=params,
            )
        except Exception as e:
            return {'ok': False, 'reason': f"回测异常: {e}"}
        if not metrics:
            return {'ok': False, 'reason': '回测返回空'}
        return {'ok': True, 'metrics': metrics}

    # ---------------- fitness（RFC 012 §4 批内百分位合成） ----------------

    @staticmethod
    def _neutral_fitness() -> float:
        return 0.5  # 同值/缺失维度的中性分

    @classmethod
    def _normalize_batch(cls, results: List[Dict[str, Any]]) -> Dict[str, float]:
        """单批相对归一：metrics→fitness（键=variant_key）。

        每维 min-max 到 [0,1]（收益/夏普/胜率均单调增）；某维全部同值 → 每变体 0.5 中性；
        某变体该维缺失/NaN → 0.5 中性。权重 0.5/0.3/0.2（RFC 012 §4）。
        """
        if not results:
            return {}
        keys = [cls._variant_key(r['params']) for r in results]
        dims = ('total_return', 'sharpe_ratio', 'win_rate')
        vals: Dict[str, Dict[str, float]] = {k: {} for k in keys}
        for dim in dims:
            raw: Dict[str, float] = {}
            for r, k in zip(results, keys):
                m = r['metrics'] or {}
                try:
                    fv = float(m.get(dim))
                except (TypeError, ValueError):
                    fv = float('nan')
                raw[k] = fv
            finite = {k: v for k, v in raw.items() if math.isfinite(v)}
            if not finite:
                for k in keys:
                    vals[k][dim] = 0.5
                continue
            lo, hi = min(finite.values()), max(finite.values())
            span = hi - lo
            for k in keys:
                v = raw.get(k)
                if not math.isfinite(v):
                    vals[k][dim] = 0.5
                elif span <= 1e-12:
                    vals[k][dim] = 0.5
                else:
                    vals[k][dim] = (v - lo) / span
        out: Dict[str, float] = {}
        for k in keys:
            out[k] = (FITNESS_WEIGHTS['total_return'] * vals[k]['total_return']
                      + FITNESS_WEIGHTS['sharpe_ratio'] * vals[k]['sharpe_ratio']
                      + FITNESS_WEIGHTS['win_rate'] * vals[k]['win_rate'])
        return out

    # ---------------- 落库行 / 文案 ----------------

    def _row_for(self, run_id: str, strategy_id: int, symbol: str, kline_window: str,
                 mode: str, initial_cash: float, result: Dict[str, Any],
                 run_at: str) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            'run_id': run_id,
            'strategy_id': strategy_id,
            'symbol': symbol,
            'variant_key': self._variant_key(result['params']),
            'variant': result['variant'],
            'params': result['params'],
            'kline_window': kline_window,
            'mode': mode,
            'initial_cash': initial_cash,
            'computed_at': run_at,
        }
        if result.get('fitness') is not None:
            row['status'] = 'ok'
            row['fitness'] = result['fitness']
            row['metrics'] = self._clip_metrics(result['metrics'])
            row['degraded_reason'] = None
        else:
            row['status'] = 'degraded'
            row['fitness'] = None
            row['metrics'] = None
            row['degraded_reason'] = result.get('reason', '零交易或无信号')[:500]
        return row

    @classmethod
    def _clip_metrics(cls, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """裁剪大数组，只留标量指标（record 防爆表）。"""
        if not isinstance(metrics, dict):
            return {}
        return {k: metrics[k] for k in METRICS_PERSIST_KEYS if k in metrics}

    @staticmethod
    def _rationale(params: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        m = metrics or {}
        return (f"真实回测 params={params}：总收益 {m.get('total_return', 0):.2%}"
                f" 夏普 {m.get('sharpe_ratio', 0):.3f} 胜率 {m.get('win_rate', 0):.1%}"
                f" 最大回撤 {m.get('max_drawdown', 0):.2%} 交易 {m.get('total_trades', 0)} 次"
                f"（qv2 backtest_strategy，非估计）")

    # ---------------- degraded 汇总 ----------------

    def _degraded_run(self, run_id: str, strategy_id: int, symbol: str, kline_window: str,
                      mode: str, run_at: str, reason: str) -> Dict[str, Any]:
        """整轮不可进化的诚实返回（占位时代反面：不给任何假 fitness）。"""
        logger.warning(f"策略进化 degraded: run_id={run_id} strategy={strategy_id} reason={reason}")
        try:
            repo = self._resolve_evolution_repo()
            repo.record_batch([{
                'run_id': run_id, 'strategy_id': strategy_id, 'symbol': symbol,
                'variant': 0, 'variant_key': 'baseline',
                'params': {}, 'kline_window': kline_window, 'mode': mode,
                'status': 'degraded', 'degraded_reason': reason[:500],
                'fitness': None, 'metrics': None, 'initial_cash': None,
                'computed_at': run_at,
            }])
        except Exception as e:
            logger.warning(f"run_id={run_id} degraded 行落库失败: {e}")
        return {
            'success': True,
            'run_id': run_id,
            'strategy_id': strategy_id,
            'symbol': symbol,
            'mode': mode,
            'kline_window': kline_window,
            'data_source': 'degraded',
            'degraded_reason': reason,
            'fitness': None,
            'fitness_improvement': None,
            'best_params': None,
            'best_metrics': None,
            'proposals': [],
            'total_variants': 0,
            'success_variants': 0,
            'degraded_variants': 0,
            'run_at': run_at,
        }
