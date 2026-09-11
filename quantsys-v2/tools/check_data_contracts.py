#!/usr/bin/env python3
"""数据契约统一校验器（步3 契约驱动监控，2026-09-11，w-f4aa1f6a）

替代"一个数据集一个脚本"的散点检查：契约声明在 quant.data_contracts（迁移见
infrastructure/persistence/migrations/20260911_data_contracts.py），这里只负责求值。

用法：
    ./venv/bin/python tools/check_data_contracts.py [--json] [--no-events] [--dataset X]

退出码：
    0  无 high 违约（medium 违约只记录不置位）
    1  存在 severity=high 的违约
    2  校验器自身失败（连不上库 / 契约配置非法 / 表不可读等基础设施问题）

违约写入既有台账 public.error_events（source='v2'，fingerprint 以 'data-contract:' 前缀，
按 fingerprint upsert：已存在 open 行 occurrence_count+1 且刷新 last_seen_at，否则插入），
自动进入采集→处置闭环。重复运行不刷屏（实测见交付报告）。

参考日语义：
    market_latest        = quant.daily_klines 中"完整交易日"的最大 trade_date
                           （某日行数 < market_min_rows 视为未完整/盘中残留，剔除——
                            2026-09-11 实测该日仅 18 行而正常交易日 5.5k 行）
    expected_trading_day = 期望交易日（锚定墙钟/quant.trading_calendar）。这条是防"整体冻结"的：
                           若所有数据集一起冻在旧日期，market_latest 会自洽地跟着变旧，
                           只有外部时间锚才能发现。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FINGERPRINT_PREFIX = 'data-contract:'
UPSTREAM_SOURCE = 'v2'
IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
ALLOWED_OPS = {'>', '>=', '<', '<=', '=', '!='}
SEVERITIES = ('low', 'medium', 'high')

# 市场真源（market_latest 的口径来源；与迁移注释一致）
MARKET_REF = {'schema': 'quant', 'table': 'daily_klines', 'column': 'trade_date'}
DEFAULT_MARKET_MIN_ROWS = 500     # 完整交易日的最小行数（正常 ~5.5k，盘中残留个位数）
DEFAULT_SYNC_CUTOFF = dtime(16, 0)  # 收盘+同步窗口：早于此刻不要求当日数据
DEFAULT_HOLIDAY_SLACK = 5         # 日历不可用时的节假日冗余（周几口径）


class InfraError(RuntimeError):
    """校验器自身故障（对应 exit code 2），与"契约违约"区分开。"""


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------
@dataclass
class Contract:
    dataset: str
    table_name: str
    table_schema: Optional[str] = 'quant'
    owner: Optional[str] = None
    freshness: Optional[dict] = None
    value_ranges: Optional[list] = None
    uniqueness: Optional[list] = None
    nullability: Optional[list] = None
    rowcount: Optional[dict] = None
    severity: str = 'medium'
    enabled: bool = True
    notes: Optional[str] = None
    id: Optional[int] = None

    @property
    def qualified(self) -> str:
        sch = _ident(self.table_schema, 'table_schema') if self.table_schema else None
        tbl = _ident(self.table_name, 'table_name')
        return f'{sch}.{tbl}' if sch else tbl


@dataclass
class CheckResult:
    dataset: str
    check: str            # freshness / value_range / uniqueness / nullability / rowcount
    rule_key: str         # 同 dataset 内唯一，参与 fingerprint
    severity: str
    status: str           # pass / fail / skip
    target: str           # 人类可读的规则描述
    detail: str
    observed: Any = None
    expected: Any = None

    @property
    def failed(self) -> bool:
        return self.status == 'fail'


@dataclass
class CheckContext:
    run: Callable[..., list]
    market_latest: Optional[date]
    market_raw_latest: Optional[date] = None
    market_source_note: str = ''
    expected_trading_day: Optional[date] = None
    calendar_available: bool = False
    holiday_slack_weekdays: int = DEFAULT_HOLIDAY_SLACK
    today: Optional[date] = None

    def __post_init__(self):
        if self.today is None:
            self.today = date.today()


# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------
def _ident(name: Any, what: str) -> str:
    """标识符白名单校验——表名/列名来自库里的契约行，必须挡住注入。"""
    if not isinstance(name, str) or not IDENT_RE.match(name):
        raise InfraError(f'非法{what}: {name!r}（只允许 [A-Za-z_][A-Za-z0-9_]*）')
    return name


def _as_date(v: Any) -> Optional[date]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s.replace('Z', '+00:00')).date()
        except ValueError:
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                raise InfraError(f'无法解析日期值: {v!r}')
    raise InfraError(f'无法解析日期值: {v!r} ({type(v).__name__})')


def _severity(rule_cfg: dict, default: str) -> str:
    sev = (rule_cfg or {}).get('severity') or default or 'medium'
    if sev not in SEVERITIES:
        raise InfraError(f'非法 severity: {sev!r}（允许 {SEVERITIES}）')
    return sev


class _ParamBuilder:
    """过滤器 → WHERE 子句（参数化绑定，键名加前缀避免与规则参数冲突）。"""

    def __init__(self, prefix: str):
        self.prefix = prefix
        self.params: dict = {}
        self._n = 0

    def where(self, filt: Optional[dict]) -> str:
        if not filt:
            return ''
        parts = []
        for col, val in filt.items():
            _ident(col, 'filter column')
            key = f'{self.prefix}_{self._n}'
            self._n += 1
            self.params[key] = val
            parts.append(f'{col} = :{key}')
        return ' WHERE ' + ' AND '.join(parts)


def fingerprint_for(dataset: str, rule_key: str) -> str:
    """稳定指纹：同契约同规则恒等，跨规则/跨数据集不同，总长 <= 64（列宽限制）。"""
    digest = hashlib.sha1(f'{dataset}|{rule_key}'.encode('utf-8')).hexdigest()[:16]
    return f'{FINGERPRINT_PREFIX}{digest}'


# ---------------------------------------------------------------------------
# 参考日计算
# ---------------------------------------------------------------------------
def _prev_weekday(d: date) -> date:
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _weekdays_between(start: date, end: date) -> int:
    """(start, end] 区间内的周一到周五天数（start 之后不含 start，含 end）。"""
    if end <= start:
        return 0
    n = 0
    cur = start + timedelta(days=1)
    while cur <= end:
        if cur.weekday() < 5:
            n += 1
        cur += timedelta(days=1)
    return n


def compute_market_latest(run, min_rows: int = DEFAULT_MARKET_MIN_ROWS,
                          lookback_days: int = 30) -> tuple:
    """市场最新"完整"交易日 = daily_klines 中行数 >= min_rows 的最大 trade_date。

    返回 (latest, raw_latest, note)。raw_latest 是未加完整性门槛的 max(trade_date)，
    两者不一致时说明存在"未完整交易日"（盘中残留），报告里显式提示。
    """
    sch, tbl, col = MARKET_REF['schema'], MARKET_REF['table'], MARKET_REF['column']
    qt = f'{_ident(sch, "schema")}.{_ident(tbl, "table")}'
    _ident(col, 'column')
    rows = run(f'SELECT max({col}) FROM {qt}', {})
    raw = _as_date(rows[0][0]) if rows else None
    if raw is None:
        return None, None, f'{qt} 无任何数据，无法确定市场最新交易日'
    cut = raw - timedelta(days=lookback_days)
    rows = run(
        f'SELECT {col}, count(*) FROM {qt} WHERE {col} >= :cut GROUP BY {col} '
        f'ORDER BY {col} DESC',
        {'cut': cut.isoformat()},   # 传 ISO 字符串：SQLite 文本日期可比较，Postgres 隐式转 date
    )
    for d, n in rows:
        if n >= min_rows:
            latest = _as_date(d)
            if latest != raw:
                return latest, raw, (
                    f'raw max={raw} 仅 {dict((_as_date(x), y) for x, y in rows).get(raw, 0)} 行/日，'
                    f'低于完整性门槛 {min_rows}，判为未完整交易日已剔除'
                )
            return latest, raw, ''
    return None, raw, f'最近 {lookback_days} 天内无任何日期达到完整性门槛 {min_rows} 行'


def compute_expected_trading_day(run, now: datetime, cutoff: dtime = DEFAULT_SYNC_CUTOFF,
                                 calendar_table: str = 'quant.trading_calendar') -> tuple:
    """期望交易日（外部时间锚）。返回 (date, calendar_available)。

    优先用 quant.trading_calendar（is_trading_day）；空表/不可读则降级为"周一~周五"口径
    （降级时调用方会加上 holiday_slack 冗余，见 evaluate_freshness）。
    """
    today = now.date()
    anchor = today if now.time() >= cutoff else today - timedelta(days=1)
    cal_available = False
    try:
        rows = run(
            'SELECT max(trade_date) FROM ' + calendar_table +
            ' WHERE trade_date <= :anchor AND is_trading_day IS NOT FALSE',
            {'anchor': anchor.isoformat()},
        )
        expected = _as_date(rows[0][0]) if rows else None
        if expected is not None:
            cal_available = True
            return expected, True
    except Exception:  # noqa: BLE001 —— 日历表缺失/为空都走降级口径
        pass
    return _prev_weekday(anchor), cal_available


# ---------------------------------------------------------------------------
# 各检查族
# ---------------------------------------------------------------------------
def evaluate_freshness(contract: Contract, cfg: dict, ctx: CheckContext) -> CheckResult:
    col = _ident(cfg.get('column'), 'freshness.column')
    mode = cfg.get('mode', 'market_latest')
    # 配置错误先于任何 SQL 报错（fail fast，避免被"表不可读"这类通用异常掩盖）
    if mode == 'market_latest':
        ref = ctx.market_latest
        ref_name = 'market_latest'
        lag_limit = int(cfg.get('max_lag_days', 0))
    elif mode == 'expected_trading_day':
        ref = ctx.expected_trading_day
        ref_name = 'expected_trading_day'
        lag_limit = int(cfg.get('max_lag_weekdays', 1))
    else:
        raise InfraError(f'{contract.dataset}: 未知 freshness.mode={mode!r}')

    pb = _ParamBuilder('fresh')
    where = pb.where(cfg.get('filter'))
    row = ctx.run(f'SELECT max({col}) FROM {contract.qualified}{where}', pb.params)
    latest = _as_date(row[0][0]) if row and row[0] is not None else None
    target = f'freshness({col}, mode={mode})'

    if ref is None:
        return CheckResult(contract.dataset, 'freshness', f'freshness:{col}:{mode}',
                           _severity(cfg, contract.severity), 'skip', target,
                           f'参考日不可得（{ref_name} 为空），跳过', observed=None, expected=None)

    if latest is None:
        return CheckResult(contract.dataset, 'freshness', f'freshness:{col}:{mode}',
                           _severity(cfg, contract.severity), 'fail', target,
                           f'表内无任何 {col} 数据（空表/未同步），参考日 {ref_name}={ref}',
                           observed=None, expected=str(ref))

    if mode == 'market_latest':
        lag = (ref - latest).days
        passed = lag <= lag_limit
        detail = (f'{col} 最新={latest}，{ref_name}={ref}：已达标（不滞后）' if lag <= 0 else
                  f'{col} 最新={latest}，{ref_name}={ref}，滞后 {lag} 自然日（容忍 ≤ {lag_limit}）')
    else:
        # 交易日口径：日历可用时按日历数，不可用时按周几数 + 节假日冗余
        if ctx.calendar_available:
            rows = ctx.run(
                'SELECT count(*) FROM quant.trading_calendar '
                'WHERE is_trading_day IS NOT FALSE AND trade_date > :a AND trade_date <= :b',
                {'a': latest.isoformat(), 'b': ref.isoformat()},
            )
            lag = int(rows[0][0] or 0)
            unit, slack = '交易日', 0
        else:
            lag = _weekdays_between(latest, ref)
            slack = ctx.holiday_slack_weekdays
            unit = '工作日（交易日历不可用，已加节假日冗余）'
        passed = lag <= lag_limit + slack
        detail = (f'{col} 最新={latest}，{ref_name}={ref}：已达标（不滞后）' if lag <= 0 else
                  f'{col} 最新={latest}，{ref_name}={ref}，滞后 {lag} {unit}'
                  f'（容忍 ≤ {lag_limit + slack}）')

    return CheckResult(contract.dataset, 'freshness', f'freshness:{col}:{mode}',
                       _severity(cfg, contract.severity), 'pass' if passed else 'fail',
                       target, detail, observed=str(latest), expected=str(ref))


def evaluate_value_ranges(contract: Contract, rules: Sequence[dict], ctx: CheckContext) -> list:
    out = []
    for i, rule in enumerate(rules or []):
        col = _ident(rule.get('column'), 'value_ranges.column')
        op = rule.get('op')
        if op not in ALLOWED_OPS:
            raise InfraError(f'{contract.dataset}: 非法 value_ranges.op={op!r}（允许 {sorted(ALLOWED_OPS)}）')
        val = rule.get('value')
        if val is None or isinstance(val, (dict, list, bool)):
            raise InfraError(f'{contract.dataset}: value_ranges[{i}].value 必须是标量')
        pb = _ParamBuilder(f'vr{i}')
        filt = pb.where(rule.get('filter'))
        params = dict(pb.params)
        params[f'vr{i}v'] = val
        # NULL 不参与区间判定（那是 nullability 族的职责）
        cond = f'{col} IS NOT NULL AND NOT ({col} {op} :vr{i}v)'
        where = f'{filt} AND {cond}' if filt else f' WHERE {cond}'
        rows = ctx.run(f'SELECT count(*) FROM {contract.qualified}{where}', params)
        bad = int(rows[0][0] or 0)
        rule_key = f'value_range:{col}:{op}:{val}'
        out.append(CheckResult(
            contract.dataset, 'value_range', rule_key, _severity(rule, contract.severity),
            'pass' if bad == 0 else 'fail',
            f'value_ranges({col} {op} {val})',
            (rule.get('note') or '') + (f'；实测 {bad} 行越界' if bad else '；无越界行'),
            observed=bad, expected=0))
    return out


def evaluate_uniqueness(contract: Contract, rules: Sequence[dict], ctx: CheckContext) -> list:
    out = []
    for i, rule in enumerate(rules or []):
        cols = rule.get('columns') or []
        if not cols:
            raise InfraError(f'{contract.dataset}: uniqueness[{i}].columns 不能为空')
        cols = [_ident(c, 'uniqueness.column') for c in cols]
        pb = _ParamBuilder(f'uq{i}')
        filt = pb.where(rule.get('filter'))
        collist = ', '.join(cols)
        sub = f'SELECT {collist} FROM {contract.qualified}{filt} GROUP BY {collist} HAVING count(*) > 1'
        rows = ctx.run(f'SELECT count(*) FROM ({sub}) dup', pb.params)
        dups = int(rows[0][0] or 0)
        out.append(CheckResult(
            contract.dataset, 'uniqueness', f'unique:{",".join(cols)}',
            _severity(rule, contract.severity), 'pass' if dups == 0 else 'fail',
            f'uniqueness({",".join(cols)})',
            f'重复键组 {dups} 组', observed=dups, expected=0))
    return out


def evaluate_nullability(contract: Contract, rules: Sequence[dict], ctx: CheckContext) -> list:
    out = []
    for i, rule in enumerate(rules or []):
        col = _ident(rule.get('column'), 'nullability.column')
        max_ratio = float(rule.get('max_null_ratio', 0.0))
        pb = _ParamBuilder(f'nn{i}')
        filt = pb.where(rule.get('filter'))
        rows = ctx.run(f'SELECT count(*) FROM {contract.qualified}{filt}', pb.params)
        total = int(rows[0][0] or 0)
        where = f'{filt} AND {col} IS NULL' if filt else f' WHERE {col} IS NULL'
        rows = ctx.run(f'SELECT count(*) FROM {contract.qualified}{where}', pb.params)
        nulls = int(rows[0][0] or 0)
        ratio = (nulls / total) if total else 0.0
        passed = ratio <= max_ratio + 1e-12
        out.append(CheckResult(
            contract.dataset, 'nullability', f'null:{col}',
            _severity(rule, contract.severity), 'pass' if passed else 'fail',
            f'nullability({col} <= {max_ratio:.0%})',
            f'空值 {nulls}/{total}（{ratio:.2%}）', observed=nulls, expected=f'<= {max_ratio:.0%}'))
    return out


def evaluate_rowcount(contract: Contract, cfg: dict, ctx: CheckContext) -> CheckResult:
    pb = _ParamBuilder('rc')
    filt = pb.where(cfg.get('filter'))
    rows = ctx.run(f'SELECT count(*) FROM {contract.qualified}{filt}', pb.params)
    n = int(rows[0][0] or 0)
    lo, hi = cfg.get('min'), cfg.get('max')
    passed = True
    if lo is not None and n < int(lo):
        passed = False
    if hi is not None and n > int(hi):
        passed = False
    return CheckResult(
        contract.dataset, 'rowcount', 'rowcount',
        _severity(cfg, contract.severity), 'pass' if passed else 'fail',
        f'rowcount([{lo if lo is not None else "-∞"}, {hi if hi is not None else "+∞"}])',
        f'实测 {n} 行' + ('（空表！）' if n == 0 else ''), observed=n,
        expected=f'[{lo}, {hi}]')


def evaluate_contract(contract: Contract, ctx: CheckContext) -> list:
    results = []
    try:
        if contract.freshness:
            results.append(evaluate_freshness(contract, contract.freshness, ctx))
        if contract.value_ranges:
            results.extend(evaluate_value_ranges(contract, contract.value_ranges, ctx))
        if contract.uniqueness:
            results.extend(evaluate_uniqueness(contract, contract.uniqueness, ctx))
        if contract.nullability:
            results.extend(evaluate_nullability(contract, contract.nullability, ctx))
        if contract.rowcount:
            results.append(evaluate_rowcount(contract, contract.rowcount, ctx))
    except InfraError:
        raise
    except Exception as e:  # noqa: BLE001 —— 表不存在/权限/类型错 = 契约违约（数据集不可读）
        msg = str(e).strip().splitlines()[0] if str(e).strip() else e.__class__.__name__
        results.append(CheckResult(
            contract.dataset, 'readability', 'readable', contract.severity, 'fail',
            f'read({contract.qualified})', f'数据集不可读：{msg}', observed=None, expected='可读'))
    if not results:
        results.append(CheckResult(
            contract.dataset, 'noop', 'noop', contract.severity, 'skip',
            f'{contract.qualified}', '契约未声明任何检查项', None, None))
    return results


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def summarize(results: Sequence[CheckResult]) -> dict:
    fails = [r for r in results if r.failed]
    high = [r for r in fails if r.severity == 'high']
    return {
        'total': len(results),
        'passed': len([r for r in results if r.status == 'pass']),
        'failed': len(fails),
        'skipped': len([r for r in results if r.status == 'skip']),
        'high_failed': len(high),
        'medium_failed': len([r for r in fails if r.severity == 'medium']),
        'low_failed': len([r for r in fails if r.severity == 'low']),
    }


def exit_code_for(results: Sequence[CheckResult]) -> int:
    return 1 if any(r.failed and r.severity == 'high' for r in results) else 0


ICON = {'pass': 'PASS', 'fail': 'FAIL', 'skip': 'SKIP'}


def render_report(contracts: Sequence[Contract], results: Sequence[CheckResult],
                  ctx: CheckContext, generated_at: datetime, events_summary: list) -> str:
    s = summarize(results)
    lines = []
    lines.append('=' * 78)
    lines.append(f'数据契约校验报告  {generated_at:%Y-%m-%d %H:%M:%S}  （窗口 w-f4aa1f6a）')
    lines.append('=' * 78)
    lines.append(f'参考日 market_latest        = {ctx.market_latest}'
                 f'（源 {MARKET_REF["schema"]}.{MARKET_REF["table"]}）')
    if ctx.market_source_note:
        lines.append(f'                              注：{ctx.market_source_note}')
    lines.append(f'参考日 expected_trading_day = {ctx.expected_trading_day}'
                 f'（{"交易日历" if ctx.calendar_available else "墙钟降级：quant.trading_calendar 为空/不可读"}）')
    lines.append(f'契约 {len(contracts)} 条 enabled → 检查项 {s["total"]}：'
                 f'通过 {s["passed"]}，违约 {s["failed"]}（high {s["high_failed"]} / '
                 f'medium {s["medium_failed"]} / low {s["low_failed"]}），跳过 {s["skipped"]}')
    lines.append('-' * 78)
    by_dataset: dict = {}
    for r in results:
        by_dataset.setdefault(r.dataset, []).append(r)
    for c in contracts:
        rs = by_dataset.get(c.dataset, [])
        bad = [r for r in rs if r.failed]
        head = f'{"✗" if bad else "✓"} {c.dataset}  [{c.severity}]  {c.qualified}'
        lines.append(head)
        for r in rs:
            lines.append(f'    [{ICON.get(r.status, r.status)}][{r.severity}] {r.target}')
            lines.append(f'        {r.detail}')
    lines.append('-' * 78)
    if events_summary:
        lines.append('error_events（public，fingerprint 前缀 data-contract:）：')
        for e in events_summary:
            lines.append(f'    {e["action"]:>10}  {e["fingerprint"]}  occurrence_count={e["occurrence_count"]}'
                         f'  {e["dataset"]}')
    else:
        lines.append('error_events：本次未写入（无违约或 --no-events）')
    lines.append('-' * 78)
    code = exit_code_for(results)
    lines.append(f'结论：{"存在 high 违约 → exit 1" if code else "无 high 违约 → exit 0"}')
    lines.append('=' * 78)
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# error_events upsert
# ---------------------------------------------------------------------------
UPSERT_EVENT = """
INSERT INTO public.error_events
    (source, level, msg, detail, fingerprint, status, occurrence_count,
     first_seen_at, last_seen_at, metadata)
VALUES
    (:source, :level, :msg, :detail, :fingerprint, 'open', 1,
     now(), now(), CAST(:metadata AS jsonb))
ON CONFLICT (fingerprint) DO UPDATE SET
    occurrence_count = public.error_events.occurrence_count + 1,
    last_seen_at     = now(),
    updated_at       = now(),
    level            = EXCLUDED.level,
    msg              = EXCLUDED.msg,
    detail           = EXCLUDED.detail,
    metadata         = EXCLUDED.metadata,
    status           = 'open',
    resolved_at      = NULL,
    resolution_note  = CASE WHEN public.error_events.status <> 'open'
                            THEN '自动重开：契约违约再次出现（data-contract 校验器）'
                            ELSE public.error_events.resolution_note END
WHERE public.error_events.fingerprint LIKE :fp_like
RETURNING fingerprint, occurrence_count, (xmax = 0) AS inserted
"""


def build_event_row(contract: Contract, result: CheckResult, generated_at: datetime) -> dict:
    fp = fingerprint_for(result.dataset, result.rule_key)
    msg = f'数据契约违约：{result.dataset} 规则 {result.target}'
    detail = json.dumps({
        'dataset': result.dataset,
        'table': contract.qualified,
        'check': result.check,
        'rule': result.target,
        'rule_key': result.rule_key,
        'severity': result.severity,
        'detail': result.detail,
        'observed': result.observed,
        'expected': result.expected,
        'checked_at': generated_at.isoformat(timespec='seconds'),
    }, ensure_ascii=False)
    return {
        'source': UPSTREAM_SOURCE,
        'level': 'error' if result.severity == 'high' else 'warning',
        'msg': msg,
        'detail': detail,
        'fingerprint': fp,
        'metadata': json.dumps({
            'probe': 'data-contract',
            'dataset': result.dataset,
            'rule_key': result.rule_key,
            'severity': result.severity,
            'owner': contract.owner,
            'window': 'w-f4aa1f6a',
        }, ensure_ascii=False),
    }


def write_events(run, contracts_by_dataset: dict, failures: Sequence[CheckResult],
                 generated_at: datetime) -> list:
    """按 fingerprint upsert（只碰 data-contract: 前缀的行）。"""
    summary = []
    for r in failures:
        contract = contracts_by_dataset.get(r.dataset)
        if contract is None:
            continue
        row = build_event_row(contract, r, generated_at)
        row['fp_like'] = f'{FINGERPRINT_PREFIX}%'
        rows = run(UPSERT_EVENT, row, write=True)
        if not rows:
            continue  # WHERE 护栏未命中（理论上不会发生：fingerprint 带前缀）
        fp, occ, inserted = rows[0][0], rows[0][1], rows[0][2]
        summary.append({
            'fingerprint': fp,
            'occurrence_count': int(occ),
            'action': 'INSERT' if inserted else 'UPSERT(+1)',
            'dataset': r.dataset,
        })
    return summary


# ---------------------------------------------------------------------------
# DB 接入
# ---------------------------------------------------------------------------
def _engine():
    from sqlalchemy import create_engine

    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / '.env')
    except Exception:  # noqa: BLE001
        pass
    dsn = os.environ.get('QUANT_DATABASE_URL') or os.environ.get('DATABASE_URL') \
        or os.environ.get('POSTGRES_DSN')
    if not dsn:
        dsn = 'postgresql+psycopg2:///quant_investment'
    return create_engine(dsn)


class SqlRunner:
    """把 (sql, params) 求值成行列表。测试里换成 SQLite 连接即可复用全部检查逻辑。"""

    def __init__(self, engine):
        self.engine = engine

    def __call__(self, sql: str, params: Optional[dict] = None, write: bool = False) -> list:
        from sqlalchemy import text

        stmt = text(sql)
        if write:
            with self.engine.begin() as conn:
                return [tuple(r) for r in conn.execute(stmt, params or {}).fetchall()]
        with self.engine.connect() as conn:
            return [tuple(r) for r in conn.execute(stmt, params or {}).fetchall()]


LOAD_CONTRACTS = """
SELECT id, dataset, table_schema, table_name, owner, freshness, value_ranges,
       uniqueness, nullability, rowcount, severity, enabled, notes
FROM quant.data_contracts
WHERE enabled = TRUE
ORDER BY dataset
"""


def load_contracts(run) -> list:
    rows = run(LOAD_CONTRACTS, {})
    out = []
    for r in rows:
        out.append(Contract(
            id=r[0], dataset=r[1], table_schema=r[2], table_name=r[3], owner=r[4],
            freshness=r[5], value_ranges=r[6], uniqueness=r[7], nullability=r[8],
            rowcount=r[9], severity=r[10] or 'medium', enabled=bool(r[11]), notes=r[12],
        ))
    return out


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def _select_contracts(contracts: Sequence[Contract], selector: Optional[str]) -> list:
    if not selector:
        return list(contracts)
    sel = selector.strip()
    for c in contracts:
        if c.dataset == sel:
            return [c]
    hits = [c for c in contracts if sel.lower() in c.dataset.lower()]
    if not hits:
        raise InfraError(f'--dataset {sel!r} 未匹配到任何 enabled 契约（共 {len(contracts)} 条）')
    return hits


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description='数据契约统一校验器（quant.data_contracts → public.error_events）')
    ap.add_argument('--json', action='store_true', help='输出 JSON（机器可读）')
    ap.add_argument('--no-events', action='store_true', help='只校验不写 error_events')
    ap.add_argument('--dataset', default=None, help='只校验指定数据集（精确匹配优先，否则子串匹配）')
    ap.add_argument('--market-min-rows', type=int, default=DEFAULT_MARKET_MIN_ROWS,
                    help=f'完整交易日的最小行数（默认 {DEFAULT_MARKET_MIN_ROWS}）')
    ap.add_argument('--sync-cutoff', default=DEFAULT_SYNC_CUTOFF.strftime('%H:%M'),
                    help=f'当日数据未就绪的时刻（早于此不期望当日数据，默认 {DEFAULT_SYNC_CUTOFF:%H:%M}）')
    ap.add_argument('--now', default=None, help='伪造当前时间 YYYY-MM-DD[THH:MM:SS]（用于复现/测试）')
    args = ap.parse_args(argv)

    generated_at = datetime.now()
    if args.now:
        generated_at = datetime.fromisoformat(args.now)
    cutoff = datetime.strptime(args.sync_cutoff, '%H:%M').time()

    try:
        engine = _engine()
        run = SqlRunner(engine)
        contracts = load_contracts(run)
        if not contracts:
            raise InfraError('quant.data_contracts 无 enabled 契约（先跑迁移 20260911_data_contracts.py）')
        selected = _select_contracts(contracts, args.dataset)

        market_latest, market_raw, note = compute_market_latest(run, args.market_min_rows)
        expected, cal_available = compute_expected_trading_day(run, generated_at, cutoff)
        ctx = CheckContext(run=run, market_latest=market_latest, market_raw_latest=market_raw,
                           market_source_note=note, expected_trading_day=expected,
                           calendar_available=cal_available, today=generated_at.date())

        results = []
        for c in selected:
            results.extend(evaluate_contract(c, ctx))
    except InfraError as e:
        print(f'[data-contract] 校验器故障（exit 2）：{e}', file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 —— 连不上库等
        print(f'[data-contract] 基础设施故障（exit 2）：{e.__class__.__name__}: {e}', file=sys.stderr)
        return 2

    events_summary = []
    if not args.no_events:
        failures = [r for r in results if r.failed]
        if failures:
            try:
                events_summary = write_events(run, {c.dataset: c for c in selected},
                                              failures, generated_at)
            except Exception as e:  # noqa: BLE001 —— 台账写不进去不该吞掉违约本身
                print(f'[data-contract] 写 error_events 失败：{e.__class__.__name__}: {e}', file=sys.stderr)

    code = exit_code_for(results)
    if args.json:
        print(json.dumps({
            'generated_at': generated_at.isoformat(timespec='seconds'),
            'window': 'w-f4aa1f6a',
            'reference': {
                'market_latest': str(market_latest) if market_latest else None,
                'market_raw_latest': str(market_raw) if market_raw else None,
                'market_source_note': note,
                'expected_trading_day': str(expected) if expected else None,
                'calendar_available': cal_available,
                'market_min_rows': args.market_min_rows,
            },
            'summary': summarize(results),
            'results': [{
                'dataset': r.dataset, 'check': r.check, 'rule_key': r.rule_key,
                'target': r.target, 'status': r.status, 'severity': r.severity,
                'detail': r.detail, 'observed': r.observed, 'expected': r.expected,
                'fingerprint': fingerprint_for(r.dataset, r.rule_key),
            } for r in results],
            'error_events': events_summary,
            'exit_code': code,
        }, ensure_ascii=False, indent=2))
    else:
        print(render_report(selected, results, ctx, generated_at, events_summary))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
