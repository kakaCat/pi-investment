# 机会扫描动态评分系统实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 OpportunityScoringService 升级为按股票类型（程序分类）和市场环境（连续信号）动态打分，输出完整证据链（breakdown + reasons + applied_context），并具备数据自愈能力。

**Architecture:** 在现有 OpportunityScoringService 上分层叠加：批量取数（季度财报/资金流）→ DataQualityGate → 逐股 profile 分类 → 四维评分（技术/基本面/资金/周期位置）→ profile 插值权重 × regime 连续修正 → 证据链响应。`/api/signals/scan`（Flask + FastAPI parity）已在调该服务，增强即双端受益。死路由 opportunities.py 和无主服务 opportunity_scoring_service_v2.py 删除。

**Tech Stack:** Python 3.13 / Flask / SQLAlchemy ORM / pytest（quant_test 库）/ 少量 agent-ts TypeScript 改动。

**Spec:** `docs/superpowers/specs/2026-07-30-opportunity-dynamic-scoring-design.md`

**⚠️ 前置要求（仓库强制规则）:** 实施必须在独立 worktree 中进行（`git worktree add .claude/worktrees/dynamic-scoring -b feat/dynamic-scoring`），全部测试通过后合并回 main。pytest 必须在 `quantsys-v2/` 目录下用 venv python 运行（`quantsys-v2/venv/bin/python -m pytest`），测试自动切 quant_test 库。

**已知预存在失败**（区分回归用，见记忆 baseline-failing-tests）：pytest 有 5 个预存在失败。开始前先跑一遍相关测试文件记录基线。

---

## 文件结构

| 文件 | 责任 | 动作 |
|---|---|---|
| `adapters/outbound/repositories/financial_repository.py` | +`batch_get_quarterly_margins` | Modify |
| `adapters/outbound/repositories/fund_flow_repository.py` | +`batch_get_latest_flows` | Modify |
| `application/services/scoring/capital_scorer.py` | 资金面评分（主力净流入+量能） | Create |
| `application/services/scoring/cycle_position_scorer.py` | 周期位置评分（毛利率QoQ+52周位置） | Create |
| `application/services/scoring/stock_profile_classifier.py` | 逐股程序化分类 growth/value/cyclical/balanced | Create |
| `application/services/scoring/weight_calculator.py` | profile 插值权重 × regime 连续修正 | Create |
| `application/services/scoring/regime_signal_provider.py` | regime 连续信号 + 30min 缓存 + 兜底 | Create |
| `application/services/scoring/data_quality_gate.py` | 数据检测/自动修复/修复预算 | Create |
| `application/services/market_regime_detector.py` | +`detect_from_dataframe` 公共方法 | Modify |
| `application/services/opportunity_scoring_service.py` | 编排整合 + key 映射修复 + 证据链 | Modify |
| `adapters/inbound/api/routes/signals.py` | 响应补 diagnostics 透传 | Modify |
| `adapters/inbound/api/routes/opportunities.py` | 死代码 | Delete |
| `application/services/opportunity_scoring_service_v2.py` | 无主服务 | Delete |
| `adapters/inbound/fastapi_app/routes/signals_async.py` | parity 检查 + diagnostics | Modify |
| `agent-ts/.../quant/formatters.ts` | 展示 profile/regime/breakdown | Modify |
| `agent-ts/.../quant/quant-v2-client.ts` | Opportunity 类型补字段 | Modify |

---

## Task 1: 批量取数方法（季度财报 + 资金流）

**Files:**
- Modify: `quantsys-v2/adapters/outbound/repositories/financial_repository.py`
- Modify: `quantsys-v2/adapters/outbound/repositories/fund_flow_repository.py`
- Test: `quantsys-v2/tests/services/scoring/test_batch_data_methods.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_batch_data_methods.py`（目录已存在则直接建文件）：

```python
"""批量取数方法测试（Task 1）"""
import pytest
from datetime import datetime, timedelta
from adapters.outbound.repositories.financial_repository import FinancialORMRepository
from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository


TEST_SYMBOLS = ['TEST001.SH', 'TEST002.SH']


@pytest.fixture
def financial_repo(db_connection):
    repo = FinancialORMRepository()
    repo.db = db_connection
    yield repo
    # 清理
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM quant.income_statements WHERE symbol LIKE 'TEST%'")
    db_connection.commit()
    cursor.close()


@pytest.fixture
def fund_flow_repo(db_connection):
    repo = FundFlowORMRepository()
    repo.db = db_connection
    yield repo
    cursor = db_connection.cursor()
    cursor.execute("DELETE FROM quant.stock_fund_flow WHERE symbol LIKE 'TEST%'")
    db_connection.commit()
    cursor.close()


def _insert_income(db, symbol, report_date, gross_margin, period_type='Q'):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO quant.income_statements
        (symbol, report_date, period_type, revenue, gross_margin, net_profit)
        VALUES (%s, %s, %s, 1000000, %s, 100000)
    """, (symbol, report_date, period_type, gross_margin))
    db.commit()
    cursor.close()


def test_batch_get_quarterly_margins(financial_repo, db_connection):
    """批量查询近8个季度毛利率，按报告期倒序、每股最多8期"""
    # TEST001 插 10 个季度（应只返回 8 期），TEST002 插 3 期
    base = datetime(2026, 3, 31)
    for i in range(10):
        d = (base - timedelta(days=90 * i)).strftime('%Y-%m-%d')
        _insert_income(db_connection, 'TEST001.SH', d, 30.0 + i)
    for i in range(3):
        d = (base - timedelta(days=90 * i)).strftime('%Y-%m-%d')
        _insert_income(db_connection, 'TEST002.SH', d, 25.0)

    result = financial_repo.batch_get_quarterly_margins(TEST_SYMBOLS, quarters=8)

    assert set(result.keys()) == set(TEST_SYMBOLS)
    assert len(result['TEST001.SH']) == 8
    assert len(result['TEST002.SH']) == 3
    # 倒序：最新一期在前
    dates = [r['report_date'] for r in result['TEST001.SH']]
    assert dates == sorted(dates, reverse=True)
    # 只查 Q，不混入年报
    for r in result['TEST001.SH']:
        assert r['period_type'] == 'Q'
    # 未知股票返回空列表
    assert result.get('NOTEXIST.SH', []) == [] or 'NOTEXIST.SH' not in result


def test_batch_get_latest_flows(fund_flow_repo, db_connection):
    """批量查询近5日资金流，按交易日倒序、每股最多5条"""
    base = datetime(2026, 7, 29)
    cursor = db_connection.cursor()
    for i in range(7):  # 7 天数据，应只返回 5
        d = (base - timedelta(days=i)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO quant.stock_fund_flow
            (symbol, trade_date, close_price, change_pct, main_net_inflow, source)
            VALUES (%s, %s, 10.0, 1.5, %s, 'test')
        """, ('TEST001.SH', d, 1000000 * (i + 1)))
    db_connection.commit()
    cursor.close()

    result = fund_flow_repo.batch_get_latest_flows(['TEST001.SH'], days=5)

    assert len(result['TEST001.SH']) == 5
    dates = [str(r['trade_date']) for r in result['TEST001.SH']]
    assert dates == sorted(dates, reverse=True)
    # 倒序第一条是最新日期的净流入（i=0 → 1000000）
    assert float(result['TEST001.SH'][0]['main_net_inflow']) == 1000000.0
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_batch_data_methods.py -v
```
预期：FAILED，`AttributeError: 'FinancialORMRepository' object has no attribute 'batch_get_quarterly_margins'`

- [ ] **Step 3: 实现 batch_get_quarterly_margins**

在 `financial_repository.py` 的 `FinancialORMRepository` 类中（`get_balance_sheets` 方法之后）添加：

```python
    def batch_get_quarterly_margins(
        self, symbols: List[str], quarters: int = 8
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量查询多只股票近 N 个季度利润表（用于周期/成长分类）

        Args:
            symbols: 股票代码列表
            quarters: 每股最多返回季度数（默认 8）

        Returns:
            {symbol: [income_dict, ...]}，按 report_date 倒序，仅 period_type='Q'
        """
        if not symbols:
            return {}
        try:
            rows = (self.session.query(IncomeStatement)
                    .filter(IncomeStatement.symbol.in_(symbols),
                            IncomeStatement.period_type == 'Q')
                    .order_by(IncomeStatement.symbol,
                              IncomeStatement.report_date.desc())
                    .all())
            result: Dict[str, List[Dict[str, Any]]] = {s: [] for s in symbols}
            for r in rows:
                lst = result.get(r.symbol)
                if lst is not None and len(lst) < quarters:
                    lst.append(_row_to_dict(r))
            return result
        except SQLAlchemyError as e:
            logger.error(f"Error batch querying quarterly margins: {e}")
            return {s: [] for s in symbols}
```

- [ ] **Step 4: 实现 batch_get_latest_flows**

在 `fund_flow_repository.py` 的 `FundFlowORMRepository` 类中（`get_latest_fund_flow` 之后）添加：

```python
    def batch_get_latest_flows(
        self, symbols: List[str], days: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """批量查询多只股票最近 N 条资金流（按交易日倒序）

        Returns:
            {symbol: [flow_dict, ...]}，每股最多 days 条，最新在前
        """
        if not symbols:
            return {}
        try:
            rows = (self.session.query(self.model)
                    .filter(self.model.symbol.in_(symbols))
                    .order_by(self.model.symbol,
                              self.model.trade_date.desc())
                    .all())
            result: Dict[str, List[Dict[str, Any]]] = {s: [] for s in symbols}
            for r in rows:
                lst = result.get(r.symbol)
                if lst is not None and len(lst) < days:
                    lst.append({c.name: getattr(r, c.name)
                                for c in self.model.__table__.columns})
            return result
        except Exception as e:
            logger.error(f"Error in batch_get_latest_flows: {e}")
            return {s: [] for s in symbols}
```

确认文件头部 import 包含 `from typing import List, Dict, Any, Optional`（`financial_repository.py` 已有则跳过；缺的补上）。

- [ ] **Step 5: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_batch_data_methods.py -v
```
预期：2 passed

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/adapters/outbound/repositories/financial_repository.py \
        quantsys-v2/adapters/outbound/repositories/fund_flow_repository.py \
        quantsys-v2/tests/services/scoring/test_batch_data_methods.py
git commit -m "feat(scoring): 批量取数方法——季度财报 batch_get_quarterly_margins + 资金流 batch_get_latest_flows"
```

---

## Task 2: CapitalScorer（资金面评分）

**Files:**
- Create: `quantsys-v2/application/services/scoring/capital_scorer.py`
- Test: `quantsys-v2/tests/services/scoring/test_capital_scorer.py`

评分口径：base 50 + 主力净流入(±30) + 流入加速(0-20) + 量比(-10~+20) + 量能趋势(0-15) + 共振(0-15)，clamp 0-100。fund_flows 缺失时降级纯量能并在 reasons 注明。

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_capital_scorer.py`：

```python
"""CapitalScorer 单元测试"""
import pytest
from application.services.scoring.capital_scorer import CapitalScorer


def _flows(amounts):
    """构造资金流列表（倒序，最新在前），amounts 单位元"""
    return [{'main_net_inflow': a, 'trade_date': f'2026-07-{29-i}'}
            for i, a in enumerate(amounts)]


class TestMainInflow:
    def test_strong_inflow_full_score(self):
        """5日累计净流入达流通市值2% → +30"""
        s = CapitalScorer()
        # 市值 100 亿，5 日每日流入 4000 万 = 累计 2 亿 = 2%
        result = s.score({
            'fund_flows': _flows([4e7] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['main_inflow'] == 30.0
        assert any('净流入' in r for r in result['reasons'])

    def test_outflow_negative_score(self):
        """连续净流出 → 负分"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([-4e7] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['main_inflow'] == -30.0

    def test_outlier_winsorized(self):
        """单日净流入 > 流通市值20% → 截断并标记"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([1e12, 0, 0, 0, 0]),  # 1 万亿，明显异常
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['main_inflow'] <= 30.0
        assert any('截断' in r for r in result['reasons'])


class TestAcceleration:
    def test_acceleration_bonus(self):
        """近2日均值 > 前3日均值 → +20"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([5e6, 5e6, 1e6, 1e6, 1e6]),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['acceleration'] == 20.0
        assert any('加速' in r for r in result['reasons'])

    def test_insufficient_flows_no_accel(self):
        """资金流不足5条 → 加速分 0"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([5e6, 5e6]),
            'market_cap': 1e10,
            'volume_ratio_5d': 1.0, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert result['breakdown']['acceleration'] == 0.0


class TestDegradation:
    def test_no_flows_degrades_to_volume(self):
        """无资金流 → 降级纯量能，reasons 注明"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': [],
            'market_cap': 1e10,
            'volume_ratio_5d': 2.0, 'volume_ma5': 200, 'volume_ma20': 100,
        })
        assert result['breakdown'].get('main_inflow') is None
        assert result['breakdown']['volume_ratio'] == 20.0
        assert result['breakdown']['volume_trend'] == 15.0
        assert any('资金流数据缺失' in r for r in result['reasons'])
        assert result['total'] == 85.0  # 50 + 20 + 15


class TestResonance:
    def test_resonance(self):
        """主力流入+放量+上涨 → +15"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([1e6] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 2.0, 'volume_ma5': 0, 'volume_ma20': 1,
            'change_pct': 2.5,
        })
        assert result['breakdown']['resonance'] == 15.0
        assert any('共振' in r for r in result['reasons'])

    def test_no_resonance_when_price_falls(self):
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([1e6] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 2.0, 'volume_ma5': 0, 'volume_ma20': 1,
            'change_pct': -1.0,
        })
        assert result['breakdown']['resonance'] == 0.0


class TestTotalRange:
    def test_total_clamped(self):
        """总分 clamp 在 0-100"""
        s = CapitalScorer()
        result = s.score({
            'fund_flows': _flows([-4e7] * 5),
            'market_cap': 1e10,
            'volume_ratio_5d': 0.5, 'volume_ma5': 0, 'volume_ma20': 1,
        })
        assert 0 <= result['total'] <= 100
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_capital_scorer.py -v
```
预期：FAILED，`ModuleNotFoundError: No module named 'application.services.scoring.capital_scorer'`

- [ ] **Step 3: 实现 CapitalScorer**

创建 `quantsys-v2/application/services/scoring/capital_scorer.py`：

```python
"""
资金面评分器

数据：fund_flows 表近 5 日主力净流入 + K 线量比。
fund_flows 缺失时降级纯量能评分，reasons 注明（不许静默降级）。

评分口径：
总分 = base(50) + 主力净流入(±30) + 流入加速(0-20) + 量比(-10~+20)
       + 量能趋势(0-15) + 共振(0-15)，clamp 0-100
"""
from typing import Dict, Any, List, Optional, Tuple
import logging
from .base_scorer import BaseScorer

logger = logging.getLogger(__name__)


class CapitalScorer(BaseScorer):
    """资金面评分器"""

    INFLOW_MAX = 30.0          # 主力净流入满分（累计达流通市值 2%）
    INFLOW_FULL_RATIO = 0.02
    ACCEL_MAX = 20.0
    VOLUME_MAX = 20.0
    TREND_MAX = 15.0
    RESONANCE_MAX = 15.0
    BASE = 50.0
    OUTLIER_RATIO = 0.20       # 单日净流入 > 流通市值 20% = 异常值

    def score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            data: {
                fund_flows: [{main_net_inflow, trade_date, ...}] 倒序，最新在前,
                market_cap: 流通市值（元），用于归一化,
                volume_ratio_5d, volume_ma5, volume_ma20, change_pct
            }

        Returns:
            {'total': float, 'breakdown': {...}, 'reasons': [str]}
        """
        flows = list(data.get('fund_flows') or [])
        volume_ratio = self._f(data.get('volume_ratio_5d'), 1.0)
        volume_ma5 = self._f(data.get('volume_ma5'), 0.0)
        volume_ma20 = self._f(data.get('volume_ma20'), 0.0)
        change_pct = self._f(data.get('change_pct'), 0.0)
        market_cap = self._f(data.get('market_cap'), None)

        breakdown: Dict[str, Optional[float]] = {}
        reasons: List[str] = []
        degraded = len(flows) == 0

        if not degraded:
            flows, truncated = self._winsorize(flows, market_cap)
            if truncated:
                reasons.append('资金流异常值已截断')
            inflow, inflow_reasons = self._score_main_inflow(flows, market_cap)
            accel, accel_reasons = self._score_acceleration(flows)
            breakdown['main_inflow'] = inflow
            breakdown['acceleration'] = accel
            reasons.extend(inflow_reasons)
            reasons.extend(accel_reasons)
        else:
            breakdown['main_inflow'] = None
            breakdown['acceleration'] = None
            reasons.append('资金流数据缺失，按量能评分')

        vol_score = self._score_volume_ratio(volume_ratio)
        breakdown['volume_ratio'] = vol_score
        if vol_score > 0:
            reasons.append(f'成交量放大({volume_ratio:.1f}倍)')
        elif vol_score < 0:
            reasons.append(f'量能萎缩(量比{volume_ratio:.2f})')

        trend_score = self.TREND_MAX if (volume_ma20 > 0 and volume_ma5 > volume_ma20) else 0.0
        breakdown['volume_trend'] = trend_score
        if trend_score > 0:
            reasons.append('量能趋势向上(5日均量>20日均量)')

        resonance = 0.0
        if not degraded:
            total_inflow = sum(self._f(f.get('main_net_inflow'), 0.0) for f in flows)
            if total_inflow > 0 and volume_ratio > 1.5 and change_pct > 0:
                resonance = self.RESONANCE_MAX
                reasons.append('量价资共振：主力流入+放量+上涨')
        breakdown['resonance'] = resonance

        raw = sum(v for v in breakdown.values() if v is not None)
        total = max(0.0, min(100.0, self.BASE + raw))

        return {
            'total': round(total, 2),
            'breakdown': {k: (round(v, 2) if v is not None else None)
                          for k, v in breakdown.items()},
            'reasons': reasons,
        }

    # ---------- 子项 ----------

    def _score_main_inflow(
        self, flows: List[Dict], market_cap: Optional[float]
    ) -> Tuple[float, List[str]]:
        """主力净流入方向（±30）：5 日累计净流入相对流通市值归一化"""
        amounts = [self._f(f.get('main_net_inflow'), 0.0) for f in flows]
        total_inflow = sum(amounts)

        if market_cap and market_cap > 0:
            ratio = total_inflow / market_cap
        else:
            # 无市值数据：用绝对额粗判（±1 亿为满分线）
            ratio = total_inflow / 1e8 * self.INFLOW_FULL_RATIO
        score = max(-1.0, min(1.0, ratio / self.INFLOW_FULL_RATIO)) * self.INFLOW_MAX

        reasons = []
        if total_inflow > 0:
            consecutive = 0
            for a in amounts:
                if a > 0:
                    consecutive += 1
                else:
                    break
            yi = total_inflow / 1e8
            if consecutive >= 3:
                reasons.append(f'主力资金连续{consecutive}日净流入(累计{yi:.1f}亿)')
            else:
                reasons.append(f'主力资金净流入(累计{yi:.1f}亿)')
        elif total_inflow < 0:
            reasons.append(f'主力资金净流出(累计{total_inflow / 1e8:.1f}亿)')
        return score, reasons

    def _score_acceleration(self, flows: List[Dict]) -> Tuple[float, List[str]]:
        """流入加速（0-20）：近 2 日均值 > 前 3 日均值"""
        if len(flows) < 5:
            return 0.0, []
        recent2 = sum(self._f(f.get('main_net_inflow'), 0.0) for f in flows[:2]) / 2
        prev3 = sum(self._f(f.get('main_net_inflow'), 0.0) for f in flows[2:5]) / 3
        if prev3 > 0 and recent2 > prev3:
            return self.ACCEL_MAX, ['资金流入加速(近2日均值>前3日均值)']
        if prev3 <= 0 and recent2 > 0:
            return self.ACCEL_MAX / 2, ['资金由流出转流入']
        return 0.0, []

    def _score_volume_ratio(self, ratio: float) -> float:
        """量比（-10~+20），口径与 TechnicalScorer 一致"""
        if ratio > 1.5:
            return min(self.VOLUME_MAX, (ratio - 1) * 20)
        if ratio < 0.8:
            return -10.0
        return 0.0

    def _winsorize(
        self, flows: List[Dict], market_cap: Optional[float]
    ) -> Tuple[List[Dict], bool]:
        """异常值截断：单日净流入 > 流通市值 20% → 截到边界"""
        if not market_cap or market_cap <= 0:
            return flows, False
        limit = market_cap * self.OUTLIER_RATIO
        truncated = False
        out = []
        for f in flows:
            v = self._f(f.get('main_net_inflow'), 0.0)
            if abs(v) > limit:
                f = dict(f)
                f['main_net_inflow'] = limit if v > 0 else -limit
                truncated = True
            out.append(f)
        return out, truncated

    @staticmethod
    def _f(value, default):
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_capital_scorer.py -v
```
预期：8 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/scoring/capital_scorer.py \
        quantsys-v2/tests/services/scoring/test_capital_scorer.py
git commit -m "feat(scoring): CapitalScorer 资金面评分（主力净流入+加速+量比+共振，支持降级与异常截断）"
```

---

## Task 3: CyclePositionScorer（周期位置评分）

**Files:**
- Create: `quantsys-v2/application/services/scoring/cycle_position_scorer.py`
- Test: `quantsys-v2/tests/services/scoring/test_cycle_position_scorer.py`

评分口径：base 50 + 毛利率 QoQ(±35) + 距 52 周高点(±35) + 同向/背离(±30)，clamp 0-100。数据不足返回中性 50 并注明。

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_cycle_position_scorer.py`：

```python
"""CyclePositionScorer 单元测试"""
import pytest
from application.services.scoring.cycle_position_scorer import CyclePositionScorer


def _margins(values):
    """构造季度毛利率列表（倒序，最新在前）"""
    return [{'gross_margin': v, 'report_date': f'2026-0{7-i}-01'}
            for i, v in enumerate(values)]


class TestMarginQoq:
    def test_two_quarters_expansion(self):
        """连续2季扩张 → +35"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([35, 32, 30, 28]),
                     'pct_from_52w_high': -0.4})
        assert r['breakdown']['margin_qoq'] == 35.0
        assert any('扩张' in x for x in r['reasons'])

    def test_two_quarters_contraction(self):
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([28, 30, 32, 35]),
                     'pct_from_52w_high': -0.4})
        assert r['breakdown']['margin_qoq'] == -35.0


class TestFromHigh:
    def test_priced_in_zone(self):
        """回撤 30-50% → +35（已定价区）"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 30, 30, 30]),
                     'pct_from_52w_high': -0.38})
        assert r['breakdown']['from_52w_high'] == 35.0

    def test_near_high_warning(self):
        """距高点 <10% → -35（顶部警惕）"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 30, 30, 30]),
                     'pct_from_52w_high': -0.05})
        assert r['breakdown']['from_52w_high'] == -35.0


class TestAlignment:
    def test_golden_pit(self):
        """盈利扩张+深跌 → 黄金坑 +30"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([35, 32, 30, 28]),
                     'pct_from_52w_high': -0.38})
        assert r['breakdown']['alignment'] == 30.0
        assert any('黄金坑' in x for x in r['reasons'])
        assert r['total'] == 100.0  # 50+35+35+30 clamp

    def test_top_trap(self):
        """盈利收缩+新高 → 顶部陷阱 -30"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([28, 30, 32, 35]),
                     'pct_from_52w_high': -0.05})
        assert r['breakdown']['alignment'] == -30.0
        assert any('顶部陷阱' in x for x in r['reasons'])
        assert r['total'] == 0.0  # 50-35-35-30 clamp


class TestInsufficientData:
    def test_insufficient_quarters_neutral(self):
        """季度数据 <4 期 → 中性 50 并注明"""
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 28]),
                     'pct_from_52w_high': -0.3})
        assert r['total'] == 50.0
        assert any('不足' in x for x in r['reasons'])

    def test_missing_high_neutral(self):
        s = CyclePositionScorer()
        r = s.score({'quarterly_margins': _margins([30, 29, 28, 27]),
                     'pct_from_52w_high': None})
        assert r['total'] == 50.0
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_cycle_position_scorer.py -v
```
预期：FAILED，ModuleNotFoundError

- [ ] **Step 3: 实现 CyclePositionScorer**

创建 `quantsys-v2/application/services/scoring/cycle_position_scorer.py`：

```python
"""
周期位置评分器（仅 cyclical 股票使用）

两个输入：
1. 季度毛利率序列 → 盈利拐点（扩张 vs 收缩）
2. 股价距 52 周高点回撤 → 是否已定价

两者同向（扩张+深跌=黄金坑 / 收缩+新高=顶部陷阱）时加减成。

评分口径：base(50) + 毛利率QoQ(±35) + 距高点(±35) + 同向/背离(±30)，clamp 0-100
"""
from typing import Dict, Any, List, Optional
import logging
from .base_scorer import BaseScorer

logger = logging.getLogger(__name__)


class CyclePositionScorer(BaseScorer):
    """周期位置评分器"""

    MIN_QUARTERS = 4
    BASE = 50.0
    QOQ_MAX = 35.0
    HIGH_MAX = 35.0
    ALIGN_MAX = 30.0

    def score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            data: {
                quarterly_margins: [{gross_margin, report_date}, ...] 倒序最新在前,
                pct_from_52w_high: (close - high_52w) / high_52w，≤0
            }
        """
        margins = [m for m in (data.get('quarterly_margins') or [])
                   if m.get('gross_margin') is not None]
        pct_from_high = data.get('pct_from_52w_high')
        if pct_from_high is not None:
            try:
                pct_from_high = float(pct_from_high)
            except (TypeError, ValueError):
                pct_from_high = None

        if len(margins) < self.MIN_QUARTERS or pct_from_high is None:
            return {
                'total': self.BASE,
                'breakdown': {'base': self.BASE},
                'reasons': ['周期数据不足，按中性评分'],
            }

        reasons: List[str] = []
        values = [float(m['gross_margin']) for m in margins]
        deltas = [values[i] - values[i + 1] for i in range(2)]  # 最近两个 QoQ

        # --- 毛利率 QoQ（±35）---
        expanding = sum(deltas) > 0
        if all(d > 0 for d in deltas):
            qoq = self.QOQ_MAX
            reasons.append(f'毛利率连续2季扩张(+{sum(deltas):.1f}pp)')
        elif expanding:
            qoq = 15.0
            reasons.append(f'毛利率环比改善(+{sum(deltas):.1f}pp)')
        elif all(d < 0 for d in deltas):
            qoq = -self.QOQ_MAX
            reasons.append(f'毛利率连续2季收缩({sum(deltas):.1f}pp)')
        else:
            qoq = -15.0
            reasons.append(f'毛利率环比走弱({sum(deltas):.1f}pp)')

        # --- 距 52 周高点（±35）---
        dd = -pct_from_high  # 回撤幅度，≥0
        if 0.30 <= dd <= 0.50:
            high = self.HIGH_MAX
            reasons.append(f'股价距52周高点回撤{dd:.0%}，或已定价')
        elif 0.15 <= dd < 0.30:
            high = 20.0
            reasons.append(f'股价回撤{dd:.0%}，部分定价')
        elif dd > 0.50:
            high = 10.0
            reasons.append(f'股价深度回撤{dd:.0%}')
        elif dd < 0.10:
            high = -self.HIGH_MAX
            reasons.append(f'接近52周高点(回撤仅{dd:.0%})，周期顶部警惕')
        else:
            high = 5.0

        # --- 同向/背离（±30）---
        if expanding and dd >= 0.30:
            align = self.ALIGN_MAX
            reasons.append('黄金坑：盈利拐点向上+股价深跌，同向加分')
        elif (not expanding) and dd < 0.10:
            align = -self.ALIGN_MAX
            reasons.append('顶部陷阱：盈利收缩+股价新高，背离重扣分')
        else:
            align = 0.0

        total = max(0.0, min(100.0, self.BASE + qoq + high + align))
        return {
            'total': round(total, 2),
            'breakdown': {
                'base': self.BASE,
                'margin_qoq': round(qoq, 2),
                'from_52w_high': round(high, 2),
                'alignment': round(align, 2),
            },
            'reasons': reasons,
        }
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_cycle_position_scorer.py -v
```
预期：8 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/scoring/cycle_position_scorer.py \
        quantsys-v2/tests/services/scoring/test_cycle_position_scorer.py
git commit -m "feat(scoring): CyclePositionScorer 周期位置评分（毛利率QoQ+52周位置+同向背离）"
```

---

## Task 4: StockProfileClassifier（逐股程序化分类）

**Files:**
- Create: `quantsys-v2/application/services/scoring/stock_profile_classifier.py`
- Test: `quantsys-v2/tests/services/scoring/test_stock_profile_classifier.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_stock_profile_classifier.py`：

```python
"""StockProfileClassifier 单元测试"""
import pytest
from application.services.scoring.stock_profile_classifier import StockProfileClassifier


def _q(values):
    return [{'gross_margin': v} for v in values]


def _fund(pe=None, roe=None, gross_margin=None, revenue_growth=None):
    return {'pe_ratio': pe, 'roe': roe, 'gross_margin': gross_margin,
            'revenue_growth': revenue_growth}


def _run(symbols, quarterly_map, fundamentals_map):
    c = StockProfileClassifier()
    return c.classify_batch(symbols, quarterly_map, fundamentals_map)


class TestCyclical:
    def test_high_earnings_volatility_is_cyclical(self):
        """毛利率波动 ≥8pp → cyclical，且优先级高于 value 特征"""
        # 毛利率 10~30 大幅摆动（std≈7.07→用更大摆幅确保≥8）
        margins = _q([30, 10, 30, 10, 30, 10, 30, 10])  # std ≈ 10
        result = _run(
            ['A'], {'A': margins},
            {'A': _fund(pe=8, roe=18, gross_margin=20, revenue_growth=5)})
        assert result['A']['profile'] == 'cyclical'
        assert '波动' in result['A']['reason']
        assert result['A']['signals']['earnings_volatility_pp'] >= 8.0


class TestGrowthValue:
    def test_growth_by_percentile(self):
        """成长强度池内前30% → growth"""
        symbols = ['G1', 'G2', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8']
        quarterly = {s: _q([30, 30, 30, 30]) for s in symbols}
        funds = {s: _fund(pe=40, roe=10, gross_margin=30, revenue_growth=2)
                 for s in symbols}
        funds['G1'] = _fund(pe=40, roe=10, gross_margin=50, revenue_growth=60)
        funds['G2'] = _fund(pe=40, roe=10, gross_margin=45, revenue_growth=50)
        result = _run(symbols, quarterly, funds)
        assert result['G1']['profile'] == 'growth'
        assert result['G2']['profile'] == 'growth'
        assert result['N1']['profile'] == 'balanced'

    def test_value_by_percentile(self):
        """价值强度池内前30% → value"""
        symbols = ['V1', 'V2', 'N1', 'N2', 'N3', 'N4', 'N5', 'N6', 'N7', 'N8']
        quarterly = {s: _q([20, 20, 20, 20]) for s in symbols}
        funds = {s: _fund(pe=30, roe=8, gross_margin=20, revenue_growth=3)
                 for s in symbols}
        funds['V1'] = _fund(pe=5, roe=25, gross_margin=20, revenue_growth=3)
        funds['V2'] = _fund(pe=6, roe=20, gross_margin=20, revenue_growth=3)
        result = _run(symbols, quarterly, funds)
        assert result['V1']['profile'] == 'value'
        assert result['V2']['profile'] == 'value'


class TestFallback:
    def test_insufficient_quarters_balanced(self):
        """季度数据 <4 期 → balanced 并注明"""
        result = _run(['A'], {'A': _q([30, 28])}, {'A': _fund()})
        assert result['A']['profile'] == 'balanced'
        assert '不足' in result['A']['reason']

    def test_missing_fundamentals_no_crash(self):
        result = _run(['A'], {'A': _q([30, 30, 30, 30])}, {'A': None})
        assert result['A']['profile'] in ('balanced', 'cyclical')
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_stock_profile_classifier.py -v
```
预期：FAILED，ModuleNotFoundError

- [ ] **Step 3: 实现 StockProfileClassifier**

创建 `quantsys-v2/application/services/scoring/stock_profile_classifier.py`：

```python
"""
股票类型分类器（程序化，无行业名单/无配置文件）

从财务时间序列计算三个连续指标：
- earnings_volatility: 近 8 季度毛利率标准差（pp）→ 周期特征
- growth_strength:     营收增速 × 毛利率 / 100      → 成长特征
- value_strength:      ROE / PE                     → 价值特征

分类规则（按优先级）：
1. earnings_volatility ≥ 8pp        → cyclical（周期股基本面会伪装成 value，先看波动）
2. growth_strength 池内分位 ≥ 0.70  → growth（相对分位，自适应池子尺度）
3. value_strength 池内分位 ≥ 0.70   → value
4. 其余/数据不足                    → balanced
"""
from typing import Dict, Any, List, Optional
from statistics import pstdev
import logging

logger = logging.getLogger(__name__)


class StockProfileClassifier:
    """逐股程序化分类"""

    CYCLICAL_VOLATILITY_PP = 8.0
    TOP_PERCENTILE = 0.70      # 分位 ≥0.70 = 池内前 30%
    MIN_QUARTERS = 4

    def classify_batch(
        self,
        symbols: List[str],
        quarterly_map: Dict[str, List[Dict]],
        fundamentals_map: Dict[str, Optional[Dict]],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Returns:
            {symbol: {'profile': str, 'signals': {...}, 'reason': str}}
        """
        raw: Dict[str, Dict[str, Optional[float]]] = {}
        for s in symbols:
            quarters = quarterly_map.get(s) or []
            fund = fundamentals_map.get(s) or {}
            raw[s] = {
                'earnings_volatility_pp': self._earnings_volatility(quarters),
                'growth_strength': self._growth_strength(fund),
                'value_strength': self._value_strength(fund),
                'quarters_available': len([q for q in quarters
                                           if q.get('gross_margin') is not None]),
            }

        growth_pct = self._percentiles(
            {s: v['growth_strength'] for s, v in raw.items()})
        value_pct = self._percentiles(
            {s: v['value_strength'] for s, v in raw.items()})

        result: Dict[str, Dict[str, Any]] = {}
        for s in symbols:
            sig = raw[s]
            ev = sig['earnings_volatility_pp']
            g_pct = growth_pct.get(s)
            v_pct = value_pct.get(s)

            if sig['quarters_available'] < self.MIN_QUARTERS:
                profile, reason = 'balanced', '季度数据不足4期，按平衡型处理'
            elif ev is not None and ev >= self.CYCLICAL_VOLATILITY_PP:
                profile = 'cyclical'
                reason = f'盈利波动率{ev:.1f}pp≥{self.CYCLICAL_VOLATILITY_PP:.0f}pp，判定为周期股'
            elif g_pct is not None and g_pct >= self.TOP_PERCENTILE:
                profile = 'growth'
                reason = f'成长强度池内分位{g_pct:.0%}，判定为成长股'
            elif v_pct is not None and v_pct >= self.TOP_PERCENTILE:
                profile = 'value'
                reason = f'价值强度池内分位{v_pct:.0%}，判定为价值股'
            else:
                profile, reason = 'balanced', '无显著类型特征，按平衡型处理'

            result[s] = {
                'profile': profile,
                'signals': {
                    'earnings_volatility_pp': (round(ev, 2)
                                               if ev is not None else None),
                    'growth_pct': (round(g_pct, 2)
                                   if g_pct is not None else None),
                    'value_pct': (round(v_pct, 2)
                                  if v_pct is not None else None),
                },
                'reason': reason,
            }
        return result

    # ---------- 指标 ----------

    def _earnings_volatility(self, quarters: List[Dict]) -> Optional[float]:
        values = [float(q['gross_margin']) for q in quarters
                  if q.get('gross_margin') is not None]
        if len(values) < self.MIN_QUARTERS:
            return None
        return pstdev(values)

    def _growth_strength(self, fund: Dict) -> Optional[float]:
        rg = self._f(fund.get('revenue_growth'))
        gm = self._f(fund.get('gross_margin'))
        if rg is None or gm is None:
            return None
        return rg * gm / 100.0

    def _value_strength(self, fund: Dict) -> Optional[float]:
        pe = self._f(fund.get('pe_ratio'))
        roe = self._f(fund.get('roe'))
        if pe is None or pe <= 0 or roe is None:
            return None
        return roe / pe

    @staticmethod
    def _percentiles(values: Dict[str, Optional[float]]) -> Dict[str, float]:
        """池内相对分位（0-1），None 不参与"""
        valid = {s: v for s, v in values.items() if v is not None}
        n = len(valid)
        if n < 2:
            return {}
        sorted_vals = sorted(valid.values())
        out = {}
        for s, v in valid.items():
            rank = sum(1 for x in sorted_vals if x < v)
            out[s] = rank / (n - 1)
        return out

    @staticmethod
    def _f(value) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_stock_profile_classifier.py -v
```
预期：6 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/scoring/stock_profile_classifier.py \
        quantsys-v2/tests/services/scoring/test_stock_profile_classifier.py
git commit -m "feat(scoring): StockProfileClassifier 程序化逐股分类（盈利波动率+池内相对分位，无行业名单）"
```

---

## Task 5: 权重计算器（profile 插值 × regime 连续修正）

**Files:**
- Create: `quantsys-v2/application/services/scoring/weight_calculator.py`
- Test: `quantsys-v2/tests/services/scoring/test_weight_calculator.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_weight_calculator.py`：

```python
"""权重计算器单元测试"""
import pytest
from application.services.scoring.weight_calculator import (
    base_weights, apply_regime, PROFILE_WEIGHT_ENDPOINTS,
)


NEUTRAL_REGIME = {'label': 'sideways', 'trend_strength': 0.5,
                  'market_risk': 0.4, 'liquidity_heat': 0.5}


class TestBaseWeights:
    def test_balanced_fixed(self):
        w = base_weights('balanced', None)
        assert w == {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}

    def test_cyclical_has_cycle_dim(self):
        w = base_weights('cyclical', None)
        assert w['cycle'] == 0.30
        assert abs(sum(w.values()) - 1.0) < 1e-9

    def test_growth_interpolation(self):
        """growth 分位越高 fundamental 权重越大、technical 越小"""
        w_low = base_weights('growth', 0.0)
        w_high = base_weights('growth', 1.0)
        assert w_high['fundamental'] > w_low['fundamental']
        assert w_high['technical'] < w_low['technical']
        # 端点值
        assert w_low['technical'] == 0.45 and w_high['technical'] == 0.35
        assert w_low['fundamental'] == 0.30 and w_high['fundamental'] == 0.40


class TestApplyRegime:
    def test_neutral_regime_near_unchanged(self):
        """中性 regime（信号=中点）→ 权重基本不变"""
        w = {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        out = apply_regime(w, NEUTRAL_REGIME)
        for k in w:
            assert abs(out[k] - w[k]) < 0.01

    def test_bull_raises_technical(self):
        """强趋势（trend_strength=1）→ 技术权重上升"""
        w = {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        out = apply_regime(w, {'label': 'bull', 'trend_strength': 1.0,
                               'market_risk': 0.2, 'liquidity_heat': 0.8})
        assert out['technical'] > 0.5

    def test_high_risk_raises_fundamental(self):
        """高风险（market_risk=1）→ 基本面权重上升"""
        w = {'technical': 0.5, 'fundamental': 0.3, 'capital': 0.2}
        out = apply_regime(w, {'label': 'bear', 'trend_strength': 0.3,
                               'market_risk': 1.0, 'liquidity_heat': 0.2})
        assert out['fundamental'] > 0.3

    def test_cycle_dim_not_adjusted(self):
        """cycle 维度不参与 regime 修正（归一化前比例不变）"""
        w = {'technical': 0.25, 'fundamental': 0.20, 'capital': 0.25, 'cycle': 0.30}
        out = apply_regime(w, NEUTRAL_REGIME)
        assert abs(out['cycle'] - 0.30) < 0.01

    def test_clamp_and_normalize(self):
        """单维限幅 [0.15, 0.60] 且总和=1（限幅在归一化前）"""
        w = {'technical': 0.6, 'fundamental': 0.2, 'capital': 0.2}
        out = apply_regime(w, {'label': 'bull', 'trend_strength': 1.0,
                               'market_risk': 0.0, 'liquidity_heat': 1.0})
        # tech: 0.6×1.25=0.75 → 限幅 0.60；fund: 0.2×0.76=0.152；cap: 0.2×1.25=0.25
        assert abs(sum(out.values()) - 1.0) < 1e-9
        assert out['technical'] > 0.55   # 限幅生效（未达到 0.75/1.05≈0.714）
        assert out['fundamental'] >= 0.14
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_weight_calculator.py -v
```
预期：FAILED，ModuleNotFoundError

- [ ] **Step 3: 实现 weight_calculator**

创建 `quantsys-v2/application/services/scoring/weight_calculator.py`：

```python
"""
动态权重计算

两段式：
1. base_weights: profile 基础权重，growth/value 按特征分位在端点间插值（权重随特征
   强度连续变化，不是死表）
2. apply_regime: regime 连续信号修正（趋势强度→技术、市场风险→基本面、量能热度→
   资金），cycle 维度不修正；单维限幅 [0.15, 0.60] 后归一化

调用方显式传 weights 时本模块不被调用（显式 > 隐式）。
"""
from typing import Dict, Optional, Any

# 端点 = (分位0时权重, 分位1时权重)；标量 = 固定权重
PROFILE_WEIGHT_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    'growth':   {'technical': (0.45, 0.35), 'fundamental': (0.30, 0.40),
                 'capital': (0.25, 0.25)},
    'value':    {'technical': (0.30, 0.20), 'fundamental': (0.45, 0.55),
                 'capital': (0.25, 0.25)},
    'cyclical': {'technical': 0.25, 'fundamental': 0.20,
                 'capital': 0.25, 'cycle': 0.30},
    'balanced': {'technical': 0.50, 'fundamental': 0.30, 'capital': 0.20},
}

# profile → 用哪个特征分位插值
_PROFILE_FEATURE_KEY = {'growth': 'growth_pct', 'value': 'value_pct'}

# regime 修正系数与中性点
_TECH_COEF, _TECH_MID = 0.5, 0.5     # trend_strength
_FUND_COEF, _FUND_MID = 0.6, 0.4     # market_risk
_CAP_COEF, _CAP_MID = 0.5, 0.5       # liquidity_heat

_MIN_W, _MAX_W = 0.15, 0.60


def base_weights(profile: str, feature_pct: Optional[float]) -> Dict[str, float]:
    """profile 基础权重（growth/value 按特征分位插值）

    Args:
        profile: growth/value/cyclical/balanced
        feature_pct: 特征分位（growth→growth_pct, value→value_pct），None 按 0.5
    """
    endpoints = PROFILE_WEIGHT_ENDPOINTS.get(
        profile, PROFILE_WEIGHT_ENDPOINTS['balanced'])
    pct = feature_pct if feature_pct is not None else 0.5
    out: Dict[str, float] = {}
    for dim, spec in endpoints.items():
        if isinstance(spec, tuple):
            lo, hi = spec
            out[dim] = lo + (hi - lo) * pct
        else:
            out[dim] = float(spec)
    return out


def apply_regime(
    weights: Dict[str, float], regime_signals: Dict[str, float]
) -> Dict[str, float]:
    """regime 连续信号修正权重 → 限幅 → 归一化

    Args:
        weights: base_weights 输出
        regime_signals: {trend_strength, market_risk, liquidity_heat}（0-1）
    """
    ts = float(regime_signals.get('trend_strength', _TECH_MID))
    mr = float(regime_signals.get('market_risk', _FUND_MID))
    lh = float(regime_signals.get('liquidity_heat', _CAP_MID))

    adjusted = dict(weights)
    if 'technical' in adjusted:
        adjusted['technical'] *= (1 + _TECH_COEF * (ts - _TECH_MID))
    if 'fundamental' in adjusted:
        adjusted['fundamental'] *= (1 + _FUND_COEF * (mr - _FUND_MID))
    if 'capital' in adjusted:
        adjusted['capital'] *= (1 + _CAP_COEF * (lh - _CAP_MID))
    # cycle 维度不修正

    for k in adjusted:
        adjusted[k] = min(_MAX_W, max(_MIN_W, adjusted[k]))

    total = sum(adjusted.values())
    if total <= 0:
        return dict(PROFILE_WEIGHT_ENDPOINTS['balanced'])
    return {k: v / total for k, v in adjusted.items()}


def feature_pct_for(profile: str, signals: Dict[str, Any]) -> Optional[float]:
    """从分类器 signals 中取插值用的特征分位"""
    key = _PROFILE_FEATURE_KEY.get(profile)
    if key is None:
        return None
    return signals.get(key)
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_weight_calculator.py -v
```
预期：8 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/scoring/weight_calculator.py \
        quantsys-v2/tests/services/scoring/test_weight_calculator.py
git commit -m "feat(scoring): 动态权重计算——profile 分位插值 × regime 连续信号修正（限幅归一化）"
```

---

## Task 6: RegimeSignalProvider（regime 连续信号 + 缓存）

**Files:**
- Modify: `quantsys-v2/application/services/market_regime_detector.py`（抽公共方法）
- Create: `quantsys-v2/application/services/scoring/regime_signal_provider.py`
- Test: `quantsys-v2/tests/services/scoring/test_regime_signal_provider.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_regime_signal_provider.py`：

```python
"""RegimeSignalProvider 单元测试"""
import pytest
import pandas as pd
from application.services.scoring.regime_signal_provider import RegimeSignalProvider


class FakeCache:
    def __init__(self):
        self.store = {}
    def get(self, ns, key):
        return self.store.get((ns, key))
    def set(self, ns, key, value, ttl=None):
        self.store[(ns, key)] = value
        return True


class FakeKlineRepo:
    def __init__(self, klines):
        self._klines = klines
    def batch_get_recent_klines(self, symbols, days=150):
        return {s: self._klines for s in symbols}


def _uptrend_klines(n=150):
    """稳定上涨序列"""
    return [{'trade_date': f'2026-01-{(i % 28) + 1:02d}', 'open': 100 + i,
             'high': 101 + i, 'low': 99 + i, 'close': 100.5 + i,
             'volume': 1000000 * (1 + i / n)} for i in range(n)]


class TestSignals:
    def test_uptrend_high_trend_strength(self):
        """单边上涨 → trend_strength 高、label 有效"""
        p = RegimeSignalProvider(FakeKlineRepo(_uptrend_klines()),
                                 cache=FakeCache())
        sig = p.get_signals()
        assert sig['label'] in ('bull', 'bear', 'sideways')
        assert 0 <= sig['trend_strength'] <= 1
        assert 0 <= sig['market_risk'] <= 1
        assert 0 <= sig['liquidity_heat'] <= 1

    def test_insufficient_data_returns_default(self):
        """指数K线不足 → 兜底 sideways 不调整"""
        p = RegimeSignalProvider(FakeKlineRepo([]), cache=FakeCache())
        sig = p.get_signals()
        assert sig == RegimeSignalProvider.DEFAULT_SIGNALS

    def test_error_returns_default(self):
        class BoomRepo:
            def batch_get_recent_klines(self, symbols, days=150):
                raise RuntimeError('db down')
        p = RegimeSignalProvider(BoomRepo(), cache=FakeCache())
        assert p.get_signals() == RegimeSignalProvider.DEFAULT_SIGNALS

    def test_cache_hit_skips_repo(self):
        """第二次调用走缓存，不再查库"""
        repo = FakeKlineRepo(_uptrend_klines())
        cache = FakeCache()
        p = RegimeSignalProvider(repo, cache=cache)
        p.get_signals()
        repo._klines = []  # 改数据，若走缓存结果不变
        sig2 = p.get_signals()
        assert sig2 != RegimeSignalProvider.DEFAULT_SIGNALS

    def test_no_cache_forces_recompute(self):
        repo = FakeKlineRepo(_uptrend_klines())
        cache = FakeCache()
        p = RegimeSignalProvider(repo, cache=cache)
        p.get_signals()
        repo._klines = []
        assert p.get_signals(no_cache=True) == RegimeSignalProvider.DEFAULT_SIGNALS


class TestDetectorDataframeMethod:
    def test_detect_from_dataframe(self):
        """MarketRegimeDetector 新增公共方法：直接接受 DataFrame"""
        from application.services.market_regime_detector import MarketRegimeDetector
        df = pd.DataFrame(_uptrend_klines()).rename(
            columns={'trade_date': 'date'})
        detector = MarketRegimeDetector()
        result = detector.detect_from_dataframe(df)
        assert result['regime'] in ('bull', 'bear', 'sideways')
        assert 'signals' in result
        assert 'adx' in result['signals']
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_regime_signal_provider.py -v
```
预期：FAILED，ModuleNotFoundError（regime_signal_provider 不存在）

- [ ] **Step 3: MarketRegimeDetector 抽公共方法**

在 `market_regime_detector.py` 中，把 `detect_current_regime` 里"计算各项指标"到 return 之间的逻辑抽成公共方法。修改 `detect_current_regime`（第 106-137 行附近）：

```python
            # 计算各项指标（委托给公共方法）
            return self.detect_from_dataframe(df)

        except Exception as e:
```

（即：保留前面的数据获取和 df 构建，`signals = {}` 到 return 段落整体移入新方法。）

在类中新增：

```python
    def detect_from_dataframe(self, df: pd.DataFrame) -> Dict[str, Any]:
        """从已构建的指数K线 DataFrame 识别市场环境（公共方法）

        Args:
            df: 含 date/open/high/low/close/volume 列，按日期升序，≥120 行

        Returns:
            {'regime', 'confidence', 'signals', 'characteristics', 'detected_at'}
        """
        signals = {}

        # 1. 趋势强度（ADX）
        signals['adx'] = self._calculate_adx(df)
        signals['trend_strength'] = 'strong' if signals['adx'] > 25 else 'weak'

        # 2. 价格相对位置（52周高低点）
        signals['price_position'] = self._calculate_price_position(df)

        # 3. 均线排列
        signals['ma_arrangement'] = self._analyze_ma_arrangement(df)

        # 4. 波动率水平
        signals['volatility'] = self._calculate_volatility(df)
        signals['volatility_level'] = self._classify_volatility(signals['volatility'])

        # 5. 价格动量
        signals['momentum_20'] = (df['close'].iloc[-1] / df['close'].iloc[-21] - 1) if len(df) >= 21 else 0
        signals['momentum_60'] = (df['close'].iloc[-1] / df['close'].iloc[-61] - 1) if len(df) >= 61 else 0

        # 综合判断
        regime, confidence = self._determine_regime(signals)

        return {
            'regime': regime,
            'confidence': round(confidence, 2),
            'signals': {k: round(v, 4) if isinstance(v, float) else v
                       for k, v in signals.items()},
            'characteristics': self.REGIME_CHARACTERISTICS[regime],
            'detected_at': datetime.now().isoformat(),
        }
```

- [ ] **Step 4: 实现 RegimeSignalProvider**

创建 `quantsys-v2/application/services/scoring/regime_signal_provider.py`：

```python
"""
Regime 连续信号提供者

把 MarketRegimeDetector 的离散判定升级为评分可用的连续信号（0-1）：
- trend_strength: ADX/50 截断        → 驱动技术面权重
- market_risk:    波动率+空头排列+价格位置 → 驱动基本面权重
- liquidity_heat: 指数量能比截断      → 驱动资金面权重

缓存 30 分钟；任何失败回退 DEFAULT_SIGNALS（sideways，不调整），不抛异常。
"""
from typing import Dict, Any, Optional
import logging
import pandas as pd

from application.services.market_regime_detector import MarketRegimeDetector
from infrastructure.cache.cache_service import get_cache_service

logger = logging.getLogger(__name__)


class RegimeSignalProvider:
    """regime 连续信号 + 缓存 + 兜底"""

    NAMESPACE = 'scoring'
    CACHE_KEY = 'regime_signals'
    TTL_SECONDS = 1800  # 30 分钟

    DEFAULT_SIGNALS: Dict[str, Any] = {
        'label': 'sideways',
        'trend_strength': 0.5,
        'market_risk': 0.4,
        'liquidity_heat': 0.5,
    }

    def __init__(self, kline_repo, detector=None, cache=None,
                 index_symbol: str = '000001.SH'):
        self.kline_repo = kline_repo
        self.detector = detector or MarketRegimeDetector()
        self.cache = cache or get_cache_service()
        self.index_symbol = index_symbol

    def get_signals(self, no_cache: bool = False) -> Dict[str, Any]:
        """获取 regime 连续信号（带 30min 缓存，失败兜底 sideways）"""
        if not no_cache:
            cached = self.cache.get(self.NAMESPACE, self.CACHE_KEY)
            if cached is not None:
                return cached
        signals = self._compute()
        if signals != self.DEFAULT_SIGNALS:
            self.cache.set(self.NAMESPACE, self.CACHE_KEY, signals,
                           self.TTL_SECONDS)
        return signals

    def _compute(self) -> Dict[str, Any]:
        try:
            klines_map = self.kline_repo.batch_get_recent_klines(
                [self.index_symbol], days=150)
            klines = klines_map.get(self.index_symbol) or []
            if len(klines) < 120:
                logger.warning(f'指数K线不足({len(klines)}条)，regime 兜底 sideways')
                return dict(self.DEFAULT_SIGNALS)

            df = pd.DataFrame(klines).rename(columns={'trade_date': 'date'})
            for col in ('open', 'high', 'low', 'close', 'volume'):
                df[col] = df[col].astype(float)
            result = self.detector.detect_from_dataframe(df)
            signals = self._to_continuous(result, df)
            return signals
        except Exception as e:
            logger.error(f'regime 信号计算失败: {e}')
            return dict(self.DEFAULT_SIGNALS)

    def _to_continuous(self, result: Dict[str, Any],
                       df: pd.DataFrame) -> Dict[str, Any]:
        s = result.get('signals', {})

        trend_strength = min(float(s.get('adx', 0)) / 50.0, 1.0)

        vol = float(s.get('volatility', 0.20))
        ma = s.get('ma_arrangement', 'mixed')
        ma_risk = {'bearish': 1.0, 'mixed': 0.5}.get(ma, 0.0)
        price_pos = float(s.get('price_position', 0.5))
        market_risk = (0.5 * min(vol / 0.30, 1.0)
                       + 0.3 * ma_risk
                       + 0.2 * (1.0 - price_pos))

        liquidity_heat = self._volume_heat(df)

        return {
            'label': result.get('regime', 'sideways'),
            'trend_strength': round(trend_strength, 4),
            'market_risk': round(min(market_risk, 1.0), 4),
            'liquidity_heat': round(liquidity_heat, 4),
        }

    @staticmethod
    def _volume_heat(df: pd.DataFrame) -> float:
        """指数量能热度：近 5 日均量 / 前 20 日均量，截断 [0,2] 后 /2"""
        try:
            if len(df) < 25:
                return 0.5
            recent5 = df['volume'].iloc[-5:].mean()
            prev20 = df['volume'].iloc[-25:-5].mean()
            if prev20 <= 0:
                return 0.5
            return min(recent5 / prev20, 2.0) / 2.0
        except Exception:
            return 0.5
```

- [ ] **Step 5: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_regime_signal_provider.py -v
```
预期：6 passed

- [ ] **Step 6: 跑 detector 原有测试防回归**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/test_tool_optimization.py -v
```
预期：全绿（该文件使用 MarketRegimeDetector，基线若有预存在失败先记录对比）

- [ ] **Step 7: Commit**

```bash
git add quantsys-v2/application/services/market_regime_detector.py \
        quantsys-v2/application/services/scoring/regime_signal_provider.py \
        quantsys-v2/tests/services/scoring/test_regime_signal_provider.py
git commit -m "feat(scoring): RegimeSignalProvider——detector 抽 detect_from_dataframe + 连续信号 + 30min 缓存兜底"
```

---

## Task 7: DataQualityGate（数据检测与自动修复）

**Files:**
- Create: `quantsys-v2/application/services/scoring/data_quality_gate.py`
- Test: `quantsys-v2/tests/services/scoring/test_data_quality_gate.py`

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_data_quality_gate.py`：

```python
"""DataQualityGate 单元测试"""
import pytest
from datetime import datetime, timedelta
from application.services.scoring.data_quality_gate import DataQualityGate


def _klines(n, end_date=None, dirty=False):
    """构造 n 根日K（升序），end_date 为最后一根日期"""
    end = end_date or datetime.now().strftime('%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')
    out = []
    for i in range(n):
        d = (end_dt - timedelta(days=n - 1 - i)).strftime('%Y-%m-%d')
        bar = {'trade_date': d, 'open': 10, 'high': 11, 'low': 9,
               'close': 10.5, 'volume': 1000, 'amount': 10500}
        if dirty and i == n - 1:
            bar['amount'] = 0  # 07-13 事故模式：amount=0 但 volume>0
        out.append(bar)
    return out


class FakeProvider:
    """模拟 DataProviderManager"""
    def __init__(self, new_bars):
        self._new = new_bars
        self.calls = 0
    def get_klines(self, symbol, period, start_date, end_date):
        self.calls += 1
        return {'success': True, 'data': self._new}


class TestDirtyBars:
    def test_dirty_bar_removed(self):
        """amount=0 且 volume>0 的 bar 被剔除，修复记录可见"""
        gate = DataQualityGate(data_provider=None)
        report = gate.check('A', _klines(130, dirty=True))
        assert report.ok
        assert len(report.klines) == 129
        assert any('剔除' in r for r in report.repairs)

    def test_too_few_after_cleaning_skips(self):
        """剔除脏 bar 后不足 120 根 → 跳过"""
        gate = DataQualityGate(data_provider=None)
        report = gate.check('A', _klines(120, dirty=True))
        assert not report.ok
        assert report.skip_reason == 'insufficient_klines'


class TestGapRepair:
    def test_recent_gap_triggers_repair(self):
        """最后一根 K 线距今 >4 天 → 触发补抓并合并"""
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        new_bars = _klines(3)
        provider = FakeProvider(new_bars)
        gate = DataQualityGate(data_provider=provider)
        report = gate.check('A', _klines(130, end_date=old_end))
        assert provider.calls == 1
        assert report.ok
        assert len(report.klines) == 133
        assert any('补抓' in r for r in report.repairs)
        assert gate.repair_report['succeeded'] == 1

    def test_no_provider_no_repair(self):
        """无 data_provider → 不补抓，数据旧但可用则照常评分"""
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        gate = DataQualityGate(data_provider=None)
        report = gate.check('A', _klines(130, end_date=old_end))
        assert report.ok  # 130 根够用，照常评分
        assert any('数据截至' in r for r in report.repairs)

    def test_repair_budget(self):
        """修复预算：超过 budget 后不再尝试"""
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        provider = FakeProvider(_klines(1))
        gate = DataQualityGate(data_provider=provider, repair_budget=2)
        for i in range(4):
            gate.check(f'S{i}', _klines(130, end_date=old_end))
        assert provider.calls == 2
        assert gate.repair_report['skipped_over_budget'] == 2

    def test_failed_repair_counted(self):
        """补抓失败 → failed 计数，不炸"""
        class BoomProvider:
            def get_klines(self, *a, **k):
                raise RuntimeError('network')
        old_end = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        gate = DataQualityGate(data_provider=BoomProvider())
        report = gate.check('A', _klines(130, end_date=old_end))
        assert report.ok  # 旧数据仍可用
        assert gate.repair_report['failed'] == 1
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_data_quality_gate.py -v
```
预期：FAILED，ModuleNotFoundError

- [ ] **Step 3: 实现 DataQualityGate**

创建 `quantsys-v2/application/services/scoring/data_quality_gate.py`：

```python
"""
数据质量门（DataQualityGate）

评分前对每只股票做检测与有限自愈：
1. 脏 bar 剔除（close≤0、amount=0 但 volume>0 的 07-13 事故模式）——剔除不重抓
2. 近端缺口补抓（最后一根 K 线距今 >4 天）——走 DataProviderManager 统一入口
3. 修复预算：单实例最多 repair_budget 次补抓，超出降级
4. 全程可见：repairs 文本进 reasons，repair_report 进 diagnostics

不做：不补历史大段缺口（数据管道职责）、不插值编造、不让修复失败炸掉扫描。
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    symbol: str
    klines: List[Dict]
    ok: bool
    skip_reason: Optional[str] = None
    repairs: List[str] = field(default_factory=list)


class DataQualityGate:
    """数据质量检测与自动修复"""

    MIN_KLINES = 120
    STALE_DAYS = 4           # 最后一根 K 线距今超过此天数 = 近端缺口

    def __init__(self, data_provider=None, repair_budget: int = 20):
        self.data_provider = data_provider
        self.repair_budget = repair_budget
        self.repair_report = {
            'attempted': 0, 'succeeded': 0,
            'failed': 0, 'skipped_over_budget': 0,
        }

    def check(self, symbol: str, klines: List[Dict]) -> QualityReport:
        repairs: List[str] = []
        bars = list(klines or [])

        # 1. 近端缺口补抓
        bars, gap_notes = self._repair_recent_gap(symbol, bars)
        repairs.extend(gap_notes)

        # 2. 脏 bar 剔除
        before = len(bars)
        bars = [b for b in bars if self._is_clean(b)]
        removed = before - len(bars)
        if removed:
            repairs.append(f'剔除脏K线{removed}根(amount=0/价格异常)')

        # 3. 长度检查
        if len(bars) < self.MIN_KLINES:
            return QualityReport(symbol, bars, False,
                                 skip_reason='insufficient_klines',
                                 repairs=repairs)
        return QualityReport(symbol, bars, True, repairs=repairs)

    # ---------- 内部 ----------

    @staticmethod
    def _is_clean(bar: Dict) -> bool:
        try:
            if float(bar.get('close') or 0) <= 0:
                return False
            vol = float(bar.get('volume') or 0)
            amt = bar.get('amount')
            if amt is not None and vol > 0 and float(amt) == 0:
                return False
            return True
        except (TypeError, ValueError):
            return False

    def _repair_recent_gap(
        self, symbol: str, bars: List[Dict]
    ) -> tuple:
        notes: List[str] = []
        if not bars:
            return bars, notes

        last_date = self._bar_date(bars[-1])
        if not last_date:
            return bars, notes
        try:
            last_dt = datetime.strptime(last_date, '%Y-%m-%d')
        except ValueError:
            return bars, notes

        gap_days = (datetime.now() - last_dt).days
        if gap_days <= self.STALE_DAYS:
            return bars, notes

        if self.data_provider is None:
            notes.append(f'数据截至{last_date}（无补抓通道）')
            return bars, notes

        if self.repair_report['attempted'] >= self.repair_budget:
            self.repair_report['skipped_over_budget'] += 1
            notes.append(f'数据截至{last_date}（修复预算已用尽）')
            return bars, notes

        self.repair_report['attempted'] += 1
        try:
            start = (last_dt + timedelta(days=1)).strftime('%Y-%m-%d')
            end = datetime.now().strftime('%Y-%m-%d')
            result = self.data_provider.get_klines(symbol, 'daily', start, end)
            new_bars = result.get('data') if result.get('success') else []
            if new_bars:
                existing = {self._bar_date(b) for b in bars}
                merged = bars + [b for b in new_bars
                                 if self._bar_date(b) not in existing]
                added = len(merged) - len(bars)
                if added > 0:
                    self.repair_report['succeeded'] += 1
                    notes.append(f'K线缺口已自动补抓({added}根)')
                    return merged, notes
            self.repair_report['failed'] += 1
            notes.append(f'数据截至{last_date}（补抓无新数据）')
            return bars, notes
        except Exception as e:
            self.repair_report['failed'] += 1
            logger.warning(f'{symbol} K线补抓失败: {e}')
            notes.append(f'数据截至{last_date}（补抓失败）')
            return bars, notes

    @staticmethod
    def _bar_date(bar: Dict) -> Optional[str]:
        d = bar.get('trade_date') or bar.get('date')
        return str(d)[:10] if d else None
```

- [ ] **Step 4: 跑测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_data_quality_gate.py -v
```
预期：7 passed

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/application/services/scoring/data_quality_gate.py \
        quantsys-v2/tests/services/scoring/test_data_quality_gate.py
git commit -m "feat(scoring): DataQualityGate 数据自愈——脏bar剔除+近端缺口补抓+修复预算，全程可见"
```

---

## Task 8: OpportunityScoringService 编排整合

**Files:**
- Modify: `quantsys-v2/application/services/opportunity_scoring_service.py`
- Test: `quantsys-v2/tests/services/scoring/test_scoring_service_integration.py`

核心改动：
1. 构造函数新增可选依赖（financial_repo / fund_flow_repo / regime_provider / quality_gate / cache），缺省惰性构造（不破坏 stock_pool_service 等现有调用方）
2. `score_stocks` 新增 `no_cache=False` 参数；K线 120→250 天；批量取季度财报+资金流（带 per-symbol 缓存）；regime 信号一次；profile 批量分类
3. `_score_single_stock` 走完整新链路：quality gate → 四维评分 → 动态权重 → 证据链输出
4. **修复 fundamental key 错位**：`pe_ratio`→`pe` 映射（latent bug，PE 维度恒 0 分）
5. 旧方法（`_calculate_capital_score` 等）保留不动，避免破坏现有测试

- [ ] **Step 1: 写失败测试**

创建 `quantsys-v2/tests/services/scoring/test_scoring_service_integration.py`：

```python
"""OpportunityScoringService 动态评分集成测试"""
import pytest
from datetime import datetime, timedelta
from application.services.opportunity_scoring_service import OpportunityScoringService
from adapters.outbound.repositories import KlineORMRepository, StockORMRepository
from domain.quantlib.adapters import get_factor_adapter


@pytest.fixture
def service(db_connection):
    kline_repo = KlineORMRepository()
    kline_repo.db = db_connection
    stock_repo = StockORMRepository()
    stock_repo.db = db_connection
    return OpportunityScoringService(kline_repo, stock_repo, get_factor_adapter())


def _seed_stock(db, symbol, name, pe, roe, gross_margin, revenue_growth):
    cursor = db.cursor()
    cursor.execute("""
        INSERT INTO quant.stocks (symbol, name, pe, roe, gross_margin,
                                  revenue_growth, debt_ratio, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, 40, NOW())
        ON CONFLICT (symbol) DO UPDATE SET
          pe=EXCLUDED.pe, roe=EXCLUDED.roe,
          gross_margin=EXCLUDED.gross_margin,
          revenue_growth=EXCLUDED.revenue_growth
    """, (symbol, name, pe, roe, gross_margin, revenue_growth))
    db.commit()
    cursor.close()


def _seed_klines(db, symbol, days=250):
    cursor = db.cursor()
    for i in range(days):
        date = (datetime.now() - timedelta(days=days - i - 1)).strftime('%Y-%m-%d')
        price = 100 + (i % 20) - 10  # 波动序列，RSI 有值
        cursor.execute("""
            INSERT INTO quant.daily_klines
            (symbol, trade_date, open, high, low, close, volume, amount)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (symbol, trade_date) DO NOTHING
        """, (symbol, date, price, price + 2, price - 2, price,
              1000000 + i * 1000, (1000000 + i * 1000) * price))
    db.commit()
    cursor.close()


def _seed_quarterly(db, symbol, margins):
    cursor = db.cursor()
    base = datetime(2026, 3, 31)
    for i, gm in enumerate(margins):
        d = (base - timedelta(days=90 * i)).strftime('%Y-%m-%d')
        cursor.execute("""
            INSERT INTO quant.income_statements
            (symbol, report_date, period_type, revenue, gross_margin, net_profit)
            VALUES (%s, %s, 'Q', 1000000, %s, 100000)
        """, (symbol, d, gm))
    db.commit()
    cursor.close()


@pytest.fixture
def seeded(db_connection):
    symbols = ['TESTA.SH', 'TESTB.SH', 'TESTC.SH']
    _seed_stock(db_connection, 'TESTA.SH', '测试成长', 40, 10, 50, 60)
    _seed_stock(db_connection, 'TESTB.SH', '测试价值', 5, 25, 20, 3)
    _seed_stock(db_connection, 'TESTC.SH', '测试周期', 8, 18, 20, 5)
    for s in symbols:
        _seed_klines(db_connection, s)
    _seed_quarterly(db_connection, 'TESTA.SH', [30, 30, 30, 30, 30, 30, 30, 30])
    _seed_quarterly(db_connection, 'TESTB.SH', [20, 20, 20, 20, 20, 20, 20, 20])
    # 周期股：毛利率大幅摆动（std≥8）
    _seed_quarterly(db_connection, 'TESTC.SH', [30, 10, 30, 10, 30, 10, 30, 10])
    yield symbols
    cursor = db_connection.cursor()
    for s in symbols + ['000001.SH']:
        cursor.execute("DELETE FROM quant.daily_klines WHERE symbol=%s", (s,))
        cursor.execute("DELETE FROM quant.income_statements WHERE symbol=%s", (s,))
        cursor.execute("DELETE FROM quant.stocks WHERE symbol=%s", (s,))
    db_connection.commit()
    cursor.close()


def test_scan_returns_evidence_chain(service, seeded):
    """响应含完整证据链：breakdown + reasons + applied_context"""
    results = service.score_stocks(seeded, filters={}, no_cache=True)
    assert len(results) >= 2
    for opp in results:
        assert 'score_breakdown' in opp
        assert 'reasons' in opp and len(opp['reasons']) > 0
        assert 'applied_context' in opp
        ctx = opp['applied_context']
        assert ctx['profile'] in ('growth', 'value', 'cyclical', 'balanced')
        assert 'final_weights' in ctx
        assert abs(sum(ctx['final_weights'].values()) - 1.0) < 0.01
        assert 'market_regime' in ctx
        # 证据链可复算：Σ(total × weight) ≈ score
        recomputed = sum(d['total'] * d['weight']
                         for d in opp['score_breakdown'].values())
        assert abs(recomputed - opp['score']) < 1.0


def test_profile_classification_in_scan(service, seeded):
    """周期股被正确分类且带 cycle 维度"""
    results = {r['symbol']: r for r in
               service.score_stocks(seeded, filters={}, no_cache=True)}
    if 'TESTC.SH' in results:
        ctx = results['TESTC.SH']['applied_context']
        assert ctx['profile'] == 'cyclical'
        assert 'cycle' in ctx['final_weights']
        assert 'cycle' in results['TESTC.SH']['score_breakdown']


def test_fundamental_pe_not_always_zero(service, seeded):
    """key 映射修复回归：低 PE 价值股 PE 维度应得正分（此前恒 0）"""
    results = {r['symbol']: r for r in
               service.score_stocks(seeded, filters={}, no_cache=True)}
    if 'TESTB.SH' in results:
        pe_score = results['TESTB.SH']['score_breakdown'] \
            ['fundamental']['details']['pe']
        assert pe_score > 0


def test_weights_override(service, seeded):
    """显式 weights 覆盖动态机制并注明"""
    results = service.score_stocks(
        seeded, filters={},
        weights={'technical': 0.6, 'fundamental': 0.3, 'capital': 0.1})
    for opp in results:
        ctx = opp['applied_context']
        assert ctx['weights_source'] == 'override'
        assert any('指定权重' in r for r in opp['reasons'])


def test_diagnostics_extended(service, seeded):
    """diagnostics 含 degraded / repair_report / elapsed_ms"""
    service.score_stocks(seeded, filters={}, no_cache=True)
    diag = service.last_diagnostics
    assert 'degraded' in diag
    assert 'repair_report' in diag
    assert 'elapsed_ms' in diag
    assert diag['scored'] >= 1


def test_legacy_fields_kept(service, seeded):
    """旧字段保留（web 前端/老调用方不破）"""
    results = service.score_stocks(seeded, filters={}, no_cache=True)
    for opp in results:
        for f in ('symbol', 'name', 'score', 'technical_score',
                  'fundamental_score', 'capital_score', 'reason',
                  'risk_level', 'signal_type'):
            assert f in opp, f'missing legacy field: {f}'
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_scoring_service_integration.py -v
```
预期：FAILED（score_breakdown 等字段不存在 / no_cache 参数不存在）

- [ ] **Step 3: 改造 OpportunityScoringService**

在 `opportunity_scoring_service.py` 顶部 import 区追加：

```python
import time
from application.services.scoring.capital_scorer import CapitalScorer
from application.services.scoring.cycle_position_scorer import CyclePositionScorer
from application.services.scoring.stock_profile_classifier import StockProfileClassifier
from application.services.scoring.weight_calculator import (
    base_weights, apply_regime, feature_pct_for)
from application.services.scoring.regime_signal_provider import RegimeSignalProvider
from application.services.scoring.data_quality_gate import DataQualityGate
from infrastructure.cache.cache_service import get_cache_service
```

构造函数改为（保持向后兼容，新参数全部可选惰性构造）：

```python
    def __init__(
        self,
        kline_repo: KlineORMRepository,
        stock_repo: StockORMRepository,
        factor_adapter,
        financial_repo=None,
        fund_flow_repo=None,
        regime_provider=None,
        quality_gate=None,
        cache=None,
    ):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo
        self.factor_adapter = factor_adapter
        # 初始化评分器
        self.technical_scorer = TechnicalScorer(factor_adapter)
        self.fundamental_scorer = FundamentalScorer()
        # 动态评分组件
        self.capital_scorer = CapitalScorer()
        self.cycle_scorer = CyclePositionScorer()
        self.profile_classifier = StockProfileClassifier()
        self.cache = cache or get_cache_service()
        if financial_repo is None:
            from adapters.outbound.repositories.financial_repository import FinancialORMRepository
            financial_repo = FinancialORMRepository()
        if fund_flow_repo is None:
            from adapters.outbound.repositories.fund_flow_repository import FundFlowORMRepository
            fund_flow_repo = FundFlowORMRepository()
        self.financial_repo = financial_repo
        self.fund_flow_repo = fund_flow_repo
        self.regime_provider = regime_provider or RegimeSignalProvider(
            kline_repo, cache=self.cache)
        if quality_gate is None:
            data_provider = None
            try:
                from adapters.outbound.datasources.manager import get_data_provider_manager
                data_provider = get_data_provider_manager()
            except Exception as e:
                logger.warning(f"DataProviderManager 不可用，K线补抓禁用: {e}")
            quality_gate = DataQualityGate(data_provider=data_provider)
        self.quality_gate = quality_gate
```

`score_stocks` 签名与取数段改为（替换原 `def score_stocks` 到 `klines_map`/`fundamentals_map` 段）：

```python
    # 缓存 TTL（秒）
    TTL_QUARTERLY = 86400    # 季度财报 24h
    TTL_FUND_FLOW = 300      # 资金流 5min
    TTL_FUNDAMENTALS = 3600  # 基本面快照 1h

    def score_stocks(
        self,
        symbols: List[str],
        filters: Dict,
        weights: Optional[Dict] = None,
        no_cache: bool = False
    ) -> List[Dict]:
        """批量评分股票（动态 profile + regime 权重）

        Args:
            symbols: 股票代码列表
            filters: 筛选条件 {'technical': [...], 'fundamental': [...], 'conditions': [...]}
            weights: 显式权重（传入=覆盖动态机制）
            no_cache: True=跳过所有缓存强制重算

        Returns:
            评分结果列表，含 score_breakdown/reasons/applied_context 证据链
        """
        started = time.time()
        if not symbols:
            self.last_diagnostics = {
                'universe_size': 0, 'scored': 0,
                'skipped_insufficient_klines': 0,
                'skipped_condition_filter': 0, 'errors': 0,
                'degraded': {}, 'repair_report': {}, 'elapsed_ms': 0,
            }
            return []

        if weights is not None:
            weights = self._normalize_weights(weights)

        # regime 信号（全扫描一次）
        regime_signals = self.regime_provider.get_signals(no_cache=no_cache)

        # 批量取数（K线 250 天：52 周高点需要）
        klines_map = self.kline_repo.batch_get_recent_klines(symbols, days=250)
        fundamentals_map, fund_status = self._cached_batch(
            symbols, 'fund', self.TTL_FUNDAMENTALS, no_cache,
            lambda miss: self.stock_repo.batch_get_fundamentals(miss))
        quarterly_map, q_status = self._cached_batch(
            symbols, 'quarterly', self.TTL_QUARTERLY, no_cache,
            lambda miss: self.financial_repo.batch_get_quarterly_margins(miss, quarters=8))
        flows_map, flow_status = self._cached_batch(
            symbols, 'flow', self.TTL_FUND_FLOW, no_cache,
            lambda miss: self.fund_flow_repo.batch_get_latest_flows(miss, days=5))

        # 逐股 profile 分类（一次，池内分位需要全池数据）
        profiles = self.profile_classifier.classify_batch(
            symbols, quarterly_map, fundamentals_map)

        diagnostics = {
            'universe_size': len(symbols),
            'scored': 0,
            'skipped_insufficient_klines': 0,
            'skipped_condition_filter': 0,
            'errors': 0,
            'degraded': {'fund_flow_missing': 0, 'quarterly_insufficient': 0},
        }

        # 并行处理每只股票
        opportunities = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(
                    self._score_single_stock,
                    symbol,
                    klines_map.get(symbol, []),
                    fundamentals_map.get(symbol),
                    filters,
                    weights,
                    {
                        'profile': profiles.get(symbol),
                        'regime': regime_signals,
                        'fund_flows': flows_map.get(symbol) or [],
                        'quarterly': quarterly_map.get(symbol) or [],
                        'cache_status': {
                            'fundamentals': fund_status.get(symbol, 'computed'),
                            'fund_flow': flow_status.get(symbol, 'computed'),
                            'quarterly': q_status.get(symbol, 'computed'),
                            'regime': 'hit' if not no_cache else 'computed',
                        },
                        'no_cache': no_cache,
                    }
                ): symbol
                for symbol in symbols
            }

            for future in as_completed(futures):
                try:
                    result = future.result()
                    if result is not None:
                        skipped = result.pop('_skipped', None)
                        if skipped == 'insufficient_klines':
                            diagnostics['skipped_insufficient_klines'] += 1
                        elif skipped == 'condition_filter':
                            diagnostics['skipped_condition_filter'] += 1
                        elif skipped == 'error':
                            diagnostics['errors'] += 1
                        else:
                            diagnostics['scored'] += 1
                            if result.pop('_degraded_flow', False):
                                diagnostics['degraded']['fund_flow_missing'] += 1
                            if result.pop('_degraded_quarterly', False):
                                diagnostics['degraded']['quarterly_insufficient'] += 1
                            opportunities.append(result)
                except Exception as e:
                    diagnostics['errors'] += 1
                    symbol = futures[future]
                    logger.error(f"{symbol}: 评分失败 - {e}")

        diagnostics['repair_report'] = dict(self.quality_gate.repair_report)
        diagnostics['elapsed_ms'] = int((time.time() - started) * 1000)
        self.last_diagnostics = diagnostics

        opportunities.sort(key=lambda x: x.get('score', 0), reverse=True)
        return opportunities

    def _cached_batch(self, symbols, kind, ttl, no_cache, fetch):
        """per-symbol 缓存的批量取数。返回 (map, {symbol: 'hit'|'computed'})"""
        result, status, missing = {}, {}, []
        for s in symbols:
            cached = None if no_cache else self.cache.get('scoring', f'{kind}:{s}')
            if cached is not None:
                result[s] = cached
                status[s] = 'hit'
            else:
                missing.append(s)
        if missing:
            fresh = fetch(missing) or {}
            for s in missing:
                value = fresh.get(s)
                if value is not None:
                    self.cache.set('scoring', f'{kind}:{s}', value, ttl)
                result[s] = value
                status[s] = 'computed'
        return result, status
```

`_score_single_stock` 整体替换为：

```python
    def _score_single_stock(
        self,
        symbol: str,
        klines: List[Dict],
        fundamental: Optional[Dict],
        filters: Dict,
        weights: Optional[Dict] = None,
        context: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """评分单只股票（动态 profile + regime 权重 + 证据链）"""
        try:
            context = context or {}
            profile_info = context.get('profile') or {
                'profile': 'balanced', 'signals': {},
                'reason': '无分类信息，按平衡型处理'}
            regime = context.get('regime') or RegimeSignalProvider.DEFAULT_SIGNALS
            flows = context.get('fund_flows') or []
            quarterly = context.get('quarterly') or []

            reasons: List[str] = [profile_info['reason']]

            # === 数据质量门（脏bar剔除 + 近端补抓）===
            report = self.quality_gate.check(symbol, klines)
            reasons.extend(report.repairs)
            if not report.ok:
                return {'_skipped': report.skip_reason or 'insufficient_klines'}
            klines = report.klines

            # 计算技术指标因子
            factors = self._calculate_factors(klines)

            # 筛选条件（保持原逻辑）
            conditions = filters.get('conditions', [])
            logic = filters.get('logic', 'AND')
            if conditions:
                if not self._evaluate_conditions(conditions, logic,
                                                 fundamental or {}, factors):
                    return {'_skipped': 'condition_filter'}

            # === 技术面 ===
            tech_result = self.technical_scorer.score(factors)
            tech_score = tech_result['total']
            reasons.extend(self._tech_reasons(factors, tech_result))

            # === 基本面（修复 key 错位：pe_ratio→pe 等）===
            fund_input = self._map_fundamental_keys(fundamental or {})
            fund_result = self.fundamental_scorer.score(fund_input)
            fund_score = fund_result['total']

            # === 资金面 ===
            cap_result = self.capital_scorer.score({
                'fund_flows': flows,
                'market_cap': (fundamental or {}).get('market_cap'),
                'volume_ratio_5d': factors.get('volume_ratio_5d', 1.0),
                'volume_ma5': factors.get('volume_ma5', 0),
                'volume_ma20': factors.get('volume_ma20', 0),
                'change_pct': self._latest_change_pct(klines),
            })
            capital_score = cap_result['total']
            reasons.extend(cap_result['reasons'])

            # === 周期位置（仅 cyclical）===
            profile = profile_info['profile']
            cycle_result = None
            if profile == 'cyclical':
                cycle_result = self.cycle_scorer.score({
                    'quarterly_margins': quarterly,
                    'pct_from_52w_high': self._pct_from_52w_high(klines),
                })
                reasons.extend(cycle_result['reasons'])

            # === 权重 ===
            if weights is not None:
                final_weights = weights
                weights_source = 'override'
                reasons.append('使用调用方指定权重')
            else:
                pct = feature_pct_for(profile, profile_info.get('signals') or {})
                final_weights = apply_regime(base_weights(profile, pct), regime)
                weights_source = 'auto'
                reasons.append(
                    f"当前{self._regime_label(regime.get('label'))}，"
                    f"权重已按市场环境调整")

            # === 综合分 ===
            dim_scores = {'technical': tech_score, 'fundamental': fund_score,
                          'capital': capital_score}
            if cycle_result is not None:
                dim_scores['cycle'] = cycle_result['total']
            total_score = sum(dim_scores[d] * final_weights.get(d, 0)
                              for d in dim_scores)

            # === 证据链 ===
            details_map = {
                'technical': tech_result.get('breakdown', {}),
                'fundamental': fund_result.get('breakdown', {}),
                'capital': cap_result.get('breakdown', {}),
            }
            if cycle_result is not None:
                details_map['cycle'] = cycle_result.get('breakdown', {})
            score_breakdown = {
                d: {
                    'total': round(dim_scores[d], 2),
                    'weight': round(final_weights.get(d, 0), 4),
                    'weighted': round(dim_scores[d] * final_weights.get(d, 0), 2),
                    'details': details_map[d],
                }
                for d in dim_scores
            }

            stock_obj = self.stock_repo.get_by_symbol(symbol)
            stock_name = stock_obj.name if stock_obj and stock_obj.name else symbol

            result = {
                'symbol': symbol,
                'name': stock_name,
                'score': round(total_score),
                'technical_score': round(tech_score),
                'fundamental_score': round(fund_score),
                'capital_score': round(capital_score),
                'confidence': round(total_score / 100, 2),
                'risk_level': self._calculate_risk_level(total_score),
                'signal_type': 'buy',
                'timestamp': datetime.now().isoformat(),
                'score_breakdown': score_breakdown,
                'reasons': reasons,
                'reason': reasons[0] if reasons else '',
                'applied_context': {
                    'profile': profile,
                    'profile_signals': profile_info.get('signals') or {},
                    'market_regime': regime,
                    'final_weights': {k: round(v, 4)
                                      for k, v in final_weights.items()},
                    'weights_source': weights_source,
                    'cache': context.get('cache_status', {}),
                },
                '_degraded_flow': len(flows) == 0,
                '_degraded_quarterly': (
                    profile == 'cyclical' and len(quarterly) < 4),
            }
            return result

        except Exception as e:
            logger.error(f"{symbol}: 评分失败 - {e}", exc_info=True)
            return {'_skipped': 'error'}
```

新增辅助方法（加在 `_score_single_stock` 之后）：

```python
    @staticmethod
    def _map_fundamental_keys(fundamental: Dict) -> Dict:
        """修复 key 错位：repo 返回 pe_ratio，FundamentalScorer 读 pe"""
        return {
            'pe': fundamental.get('pe_ratio'),
            'roe': fundamental.get('roe'),
            'gross_margin': fundamental.get('gross_margin'),
            'debt_ratio': fundamental.get('debt_ratio'),
            'revenue_growth': fundamental.get('revenue_growth'),
            'net_profit_margin': fundamental.get('net_profit_margin'),
        }

    @staticmethod
    def _pct_from_52w_high(klines: List[Dict]) -> Optional[float]:
        try:
            highs = [float(k['high']) for k in klines
                     if k.get('high') is not None]
            close = float(klines[-1]['close'])
            if not highs or close <= 0:
                return None
            high_52w = max(highs)
            if high_52w <= 0:
                return None
            return (close - high_52w) / high_52w
        except (TypeError, ValueError, IndexError, KeyError):
            return None

    @staticmethod
    def _latest_change_pct(klines: List[Dict]) -> float:
        try:
            if len(klines) < 2:
                return 0.0
            prev = float(klines[-2]['close'])
            cur = float(klines[-1]['close'])
            return (cur / prev - 1) * 100 if prev > 0 else 0.0
        except (TypeError, ValueError, IndexError, KeyError):
            return 0.0

    @staticmethod
    def _regime_label(label) -> str:
        return {'bull': '牛市', 'bear': '熊市', 'sideways': '震荡市'}.get(
            label, '震荡市')

    @staticmethod
    def _tech_reasons(factors: Dict, tech_result: Dict) -> List[str]:
        """从技术面因子生成可读理由"""
        reasons = []
        rsi = factors.get('rsi')
        if rsi is not None and rsi < 30:
            reasons.append(f'RSI超卖({rsi:.1f})')
        elif rsi is not None and rsi > 70:
            reasons.append(f'RSI超买({rsi:.1f})')
        if tech_result.get('breakdown', {}).get('macd', 0) > 10:
            reasons.append('MACD金叉')
        if rsi is not None and rsi < 30 and \
                tech_result.get('breakdown', {}).get('macd', 0) > 10:
            reasons.append('RSI超卖+MACD金叉共振')
        return reasons
```

`_map_fundamental_keys` 需要在 `_score_single_stock` 用到 `Optional` 返回类型标注，`from typing import Optional` 文件已有（原文件有 `Optional` import）。

- [ ] **Step 4: 跑集成测试确认通过**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/scoring/test_scoring_service_integration.py -v
```
预期：6 passed。若 `quant.stocks` 表缺少 `gross_margin`/`revenue_growth` 列导致 seed 失败，查看 `stock_repository.py` 的 Stock model 实际列名调整 `_seed_stock` 的 INSERT 列。

- [ ] **Step 5: 跑既有回归**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/services/test_opportunity_scoring_service.py tests/integration/test_opportunity_radar_integration.py -v
```
预期：全绿。**注意**：旧测试构造 120 根 K线，新 gate 要求 ≥120 根（边界含 120，应通过）；若有测试只构造 30-119 根，它们会转为 `skipped_insufficient_klines`——这是设计行为变更，需在测试里补足 120 根并注明。

- [ ] **Step 6: Commit**

```bash
git add quantsys-v2/application/services/opportunity_scoring_service.py \
        quantsys-v2/tests/services/scoring/test_scoring_service_integration.py
git commit -m "feat(scoring): OpportunityScoringService 动态评分整合——profile分类+regime权重+四维评分+证据链+key映射修复"
```

---

## Task 9: 路由收尾（diagnostics 透传 + 删死代码）

**Files:**
- Modify: `quantsys-v2/adapters/inbound/api/routes/signals.py`
- Modify: `quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py`
- Delete: `quantsys-v2/adapters/inbound/api/routes/opportunities.py`
- Delete: `quantsys-v2/application/services/opportunity_scoring_service_v2.py`
- Modify: `quantsys-v2/adapters/inbound/api/server.py`（移除 opportunities_bp 注册）

- [ ] **Step 1: signals.py 补 no_cache + diagnostics**

`signals.py` 的 `scan_signals` 中，`snake_data` 解析段后加：

```python
    no_cache = bool(snake_data.get('no_cache', False))
```

`scoring_service.score_stocks(...)` 调用改为：

```python
            opportunities = scoring_service.score_stocks(
                symbols=symbols,
                filters={
                    'technical': technical,
                    'fundamental': fundamental
                },
                weights=weights,
                no_cache=no_cache
            )
```

找到该路由 return 响应的位置（分页切片之后），在响应 dict 中补 diagnostics。先读当前 return 结构，把 `scoring_service.last_diagnostics` 加入 `data`：

```python
        # 在原有 return jsonify({...}) 的 data 部分追加：
        'diagnostics': sanitize_for_json(
            getattr(scoring_service, 'last_diagnostics', {})),
```

（具体位置：`_scan_strategy_opportunities` 分支之外的统一 return 处；保持原有字段不变。）

- [ ] **Step 2: signals_async.py 同步 parity**

同样补 `no_cache` 解析、传参、`last_diagnostics` 透传（该文件有自己的 `api_response`/`error_response`，按现有风格加字段）。

- [ ] **Step 3: 删除死代码**

```bash
git rm quantsys-v2/adapters/inbound/api/routes/opportunities.py \
       quantsys-v2/application/services/opportunity_scoring_service_v2.py
```

在 `server.py` 删除两行：

```python
    from adapters.inbound.api.routes.opportunities import opportunities_bp
    app.register_blueprint(opportunities_bp)
```

全局确认无残留引用：

```bash
grep -rn "opportunities_bp\|OpportunityScoringServiceV2\|opportunity_scoring_service_v2" quantsys-v2 --include="*.py" | grep -v __pycache__ | grep -v archived
```
预期：无输出（若 tests 里有引用，同步删除/更新）。

- [ ] **Step 4: 冒烟验证路由可注册**

```bash
cd quantsys-v2 && venv/bin/python -c "
from adapters.inbound.api.server import create_app
app = create_app()
rules = sorted(r.rule for r in app.url_map.iter_rules())
assert '/api/signals/scan' in rules
assert '/api/opportunities/scan' not in rules
print('routes OK')
"
```
预期输出 `routes OK`（若 server 入口函数名不同，用实际的 app 工厂函数）。

- [ ] **Step 5: Commit**

```bash
git add quantsys-v2/adapters/inbound/api/routes/signals.py \
        quantsys-v2/adapters/inbound/fastapi_app/routes/signals_async.py \
        quantsys-v2/adapters/inbound/api/server.py
git commit -m "refactor(scoring): signals/scan 透传 diagnostics+no_cache；删除死路由 opportunities.py 与无主 v2 评分服务"
```

---

## Task 10: agent-ts 类型与展示

**Files:**
- Modify: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`（Opportunity 类型）
- Modify: `agent-ts/src/infrastructure/adapters/quant/formatters.ts`
- Test: `agent-ts/src/infrastructure/tools/invest/opportunity-scan-tool.test.ts`

- [ ] **Step 1: Opportunity 类型补字段**

在 `quant-v2-client.ts` 中找到 `Opportunity` 接口（scanOpportunities 的返回元素类型），追加可选字段：

```typescript
  reasons?: string[];
  reason?: string;
  score_breakdown?: Record<string, {
    total: number;
    weight: number;
    weighted: number;
    details: Record<string, number | null>;
  }>;
  applied_context?: {
    profile: 'growth' | 'value' | 'cyclical' | 'balanced';
    profile_signals: Record<string, number | null>;
    market_regime: {
      label: string; trend_strength: number;
      market_risk: number; liquidity_heat: number;
    };
    final_weights: Record<string, number>;
    weights_source: 'auto' | 'override';
    cache: Record<string, string>;
  };
```

同时 `OpportunityScanParams` 追加 `no_cache?: boolean;`。

- [ ] **Step 2: formatOpportunities 展示证据链**

`formatters.ts` 的 `formatOpportunities` 中，`资金得分` 行之后插入：

```typescript
    if (opp.applied_context) {
      const ctx = opp.applied_context;
      const profileLabel: Record<string, string> = {
        growth: '成长股', value: '价值股',
        cyclical: '周期股', balanced: '平衡型',
      };
      const regimeLabel: Record<string, string> = {
        bull: '牛市', bear: '熊市', sideways: '震荡市',
      };
      lines.push(`   股票类型: ${profileLabel[ctx.profile] || ctx.profile}`);
      lines.push(`   市场环境: ${regimeLabel[ctx.market_regime.label] || ctx.market_regime.label}` +
        `（趋势${ctx.market_regime.trend_strength.toFixed(2)} ` +
        `风险${ctx.market_regime.market_risk.toFixed(2)}）`);
      const w = Object.entries(ctx.final_weights)
        .map(([k, v]) => `${k}:${(v * 100).toFixed(0)}%`).join(' ');
      lines.push(`   实际权重: ${w}${ctx.weights_source === 'override' ? '（指定）' : ''}`);
    }
    if (opp.score_breakdown) {
      const bd = Object.entries(opp.score_breakdown)
        .map(([k, v]) => `${k} ${v.total.toFixed(0)}×${(v.weight * 100).toFixed(0)}%=${v.weighted.toFixed(1)}`)
        .join(' | ');
      lines.push(`   得分构成: ${bd}`);
    }
```

（`reasons` 展示已有，不动。）

- [ ] **Step 3: 更新工具 description**

`opportunity-scan-tool.ts` 的 description 中，把"三维评分"相关表述更新为：

```
"• 动态评分：技术面+基本面+资金面+周期位置（周期股专属），按股票类型(成长/价值/周期)和市场环境(牛/熊/震荡)自动调权重\n" +
"• 证据链：每个机会附带打分明细、理由列表和实际权重，可复算可归因\n" +
```

（保留 💾 持久化说明和三种权重模式说明——weights 传入仍是覆盖语义。）

- [ ] **Step 4: 跑 TS 测试**

```bash
cd agent-ts && npm test -- --testPathPattern="opportunity-scan" 2>&1 | tail -20
```
预期：全绿。若有断言旧描述文案（如"三维评分"字样）的测试，同步更新断言；注意 apiClient 信封解包教训——mock 必须用解包后形状。

- [ ] **Step 5: Commit**

```bash
git add agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts \
        agent-ts/src/infrastructure/adapters/quant/formatters.ts \
        agent-ts/src/infrastructure/tools/invest/opportunity-scan-tool.ts \
        agent-ts/src/infrastructure/tools/invest/opportunity-scan-tool.test.ts
git commit -m "feat(agent): opportunity_scan 展示动态评分证据链（profile/regime/权重/得分构成）"
```

---

## Task 11: 全量回归与合并

- [ ] **Step 1: Python 全量回归**

```bash
cd quantsys-v2 && venv/bin/python -m pytest tests/ -x --ignore=tests/slow 2>&1 | tail -15
```
对比预存在失败基线（5 个已知失败）：只允许那 5 个失败，新增任何失败都必须修复。

- [ ] **Step 2: TS 全量回归**

```bash
cd agent-ts && npm test 2>&1 | tail -15
```
对比 jest 37 套件预存在失败清单，无新增失败。

- [ ] **Step 3: 真实 API 冒烟（可选但推荐）**

worktree 中启动 Flask server（注意端口占用，测完即停），调真实接口：

```bash
curl -s -X POST http://127.0.0.1:5001/api/signals/scan \
  -H 'Content-Type: application/json' \
  -d '{"symbols": ["600519.SH"], "limit": 5}' | python3 -m json.tool | head -60
```
确认返回含 `score_breakdown`/`reasons`/`applied_context`/`diagnostics`，且 score 不再是固定值。

- [ ] **Step 4: 合并回 main**

按仓库 merge-back 流程（临时 worktree 或 update-ref 模式，避开主工作区 git 写钩子）合并 `feat/dynamic-scoring` → main，推送 GitHub。

- [ ] **Step 5: 部署到 prod-5001 worktree**

线上 5001 跑在 prod-main-5001 worktree：快进该 worktree 并用 **venv python** 重启服务（见 prod-5001-worktree-deployment 记忆）。
