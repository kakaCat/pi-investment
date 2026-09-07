"""
财务数据更新 Job - 基础财务指标刷新（quant.stocks 列）

任务：financial_data_update（v2 调度任务 238 修复，2026-09-03）
数据源：东财业绩报表 ak.stock_yjbb_em(date=report_date)（全市场单次批量，~8s）
落库：quant.stocks 的财务指标列（按 column comment 单位，% 数值）：
    roe               ← 净资产收益率
    gross_margin      ← 销售毛利率
    net_profit_growth ← 净利润-同比增长（可为负）
    revenue_growth    ← 营业总收入-同比增长（东财为 % 数值，直接落库）

背景：audit（2026-09-03）发现 scheduler 任务 238 为假实现（per-symbol 循环不落库），
且 quant.stocks 财务列现值口径陈旧/混乱（部分来自历史 bulk 导入：600519 roe=32.53
疑为年报口径、000858 roe=6.89 明显异常、revenue_growth 有 Decimal 小数混入）。
本 job 以「最新披露报告期」的东财业绩报表为权威，统一刷新为一致口径。

口径说明（诚实声明）：
- yjbb 报告期=单期累计口径（如 20260630 为 2026 中报），stocks 现值可能为年报/其他
  口径，刷新后 stocks 列语义=「最近一期已披露业绩快照」。
- debt_ratio：东财 yjbb 接口无此列 → 不更新、保留现值（避免用 NULL 覆盖真实值）。
- pe/pb/market_cap：属估值/市值列，非本任务范围，不动。

调度配置（quant.scheduler_task_configs）：
    task_name: financial_data_update
    command:   infrastructure.jobs.financial_data_update_job.execute

手动执行：
    python -m infrastructure.jobs.financial_data_update_job
    python -m infrastructure.jobs.financial_data_update_job --report-date 20260630
    python -m infrastructure.jobs.financial_data_update_job --symbols 600519 000858
"""
import sys
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# 默认报告期：最近一个已披露的季度末（YYYYMMDD）。调用方可显式覆盖。
DEFAULT_REPORT_DATE = '20260630'
# yjbb 空结果时视为数据源无数据（不静默成功）
MIN_ROWS = 100


def execute(**params) -> Dict[str, Any]:
    """
    用东财业绩报表批量刷新 quant.stocks 基础财务指标列

    Args:
        **params:
            - report_date: 报告期 YYYYMMDD（默认 '20260630'）
            - symbols: 指定股票列表（默认：全市场 A 股中 yjbb 覆盖的股票）
            - dry_run: True 仅统计不写库（默认 False）

    Returns:
        dict: {success, report_date, fetched, universe, updated, skipped,
               failed, elapsed_s, error?, no_symbol_match?}
    """
    started = time.time()
    report_date = str(params.get('report_date') or DEFAULT_REPORT_DATE).strip()
    symbols = params.get('symbols')
    dry_run = bool(params.get('dry_run', False))
    if symbols:
        symbols = _dedup(list(symbols))
        universe_source = 'explicit'
    else:
        symbols = None
        universe_source = 'all-a'

    logger.info("=" * 70)
    logger.info(f"财务数据更新任务开始 (report_date={report_date}, "
                f"universe={universe_source}, dry_run={dry_run})")
    logger.info("=" * 70)

    # 1. 拉取东财业绩报表（单次批量）
    try:
        import akshare as ak
        df = ak.stock_yjbb_em(date=report_date)
    except Exception as e:
        logger.error(f"东财业绩报表获取失败: {type(e).__name__}: {e}")
        return {'success': False, 'report_date': report_date, 'fetched': 0,
                'updated': 0, 'skipped': 0, 'error': f'yjbb fetch failed: {e}',
                'elapsed_s': int(time.time() - started)}

    if df is None or df.empty or len(df) < MIN_ROWS:
        logger.error(f"业绩报表为空或数据量过少 ({0 if df is None else len(df)} 行)，"
                     f"报告期 {report_date} 可能未披露或无数据")
        return {'success': False, 'report_date': report_date, 'fetched': 0,
                'updated': 0, 'skipped': 0,
                'error': f'yjbb empty/insufficient rows for {report_date}',
                'elapsed_s': int(time.time() - started)}

    fetched = int(len(df))
    logger.info(f"业绩报表获取成功: {fetched} 行 (报告期 {report_date})")

    # 2. 去重（按 股票代码，保最后一条）——yjbb 行数可能 > A 股数，需验证唯一性
    code_col = '股票代码'
    if code_col not in df.columns:
        logger.error(f"业绩报表缺少列 {code_col}，实际列: {list(df.columns)[:12]}...")
        return {'success': False, 'report_date': report_date, 'fetched': fetched,
                'updated': 0, 'skipped': 0, 'error': f'missing column {code_col}',
                'elapsed_s': int(time.time() - started)}

    total_before = len(df)
    df = df.drop_duplicates(subset=[code_col], keep='last')
    dupes = total_before - len(df)
    if dupes:
        logger.warning(f"业绩报表存在重复股票代码，去重 {dupes} 行 "
                       f"({total_before} -> {len(df)})")

    # 3. 组装待更新记录（单位：东财 % 数值，直接对应 stocks column comment）
    need_cols = {
        '净资产收益率': 'roe',
        '销售毛利率': 'gross_margin',
        '净利润-同比增长': 'net_profit_growth',
        '营业总收入-同比增长': 'revenue_growth',
    }
    missing_cols = [c for c in need_cols if c not in df.columns]
    if missing_cols:
        logger.error(f"业绩报表缺少指标列: {missing_cols}")
        return {'success': False, 'report_date': report_date, 'fetched': fetched,
                'updated': 0, 'skipped': 0,
                'error': f'missing indicator cols: {missing_cols}',
                'elapsed_s': int(time.time() - started)}

    records: Dict[str, Dict[str, Any]] = {}
    for _, row in df.iterrows():
        code = str(row[code_col]).strip().zfill(6) if str(row[code_col]).strip().isdigit() \
            else str(row[code_col]).strip()
        if not code:
            continue
        vals = {}
        for src_col, dst_col in need_cols.items():
            v = _f(row.get(src_col))
            if v is not None:
                vals[dst_col] = v
        if vals:
            records[code] = vals
    logger.info(f"有效记录 {len(records)} 只（含财务数值）")

    # 4. 确定更新范围：仅 stocks 表存在且 market='A' 的股票
    from infrastructure.persistence.orm.config import get_session
    from sqlalchemy import text

    session = get_session()
    try:
        exist = session.execute(text(
            "SELECT symbol FROM quant.stocks WHERE market='A'"
        )).fetchall()
    except Exception as e:
        logger.error(f"查询 stocks 表失败: {e}")
        return {'success': False, 'report_date': report_date,
                'fetched': fetched, 'updated': 0, 'skipped': 0,
                'error': f'stocks query failed: {e}',
                'elapsed_s': int(time.time() - started)}

    exist_set = {str(r[0]) for r in exist}
    universe = symbols if symbols else sorted(exist_set)
    candidates = [(s, records[s]) for s in universe
                  if s in records and s in exist_set]
    no_match = len(universe) - len(candidates)
    if no_match:
        logger.info(f"{no_match} 只股票无 yjbb 匹配或不在 A 股 stocks 表，跳过")

    if dry_run:
        elapsed = int(time.time() - started)
        logger.info(f"[dry_run] 将更新 {len(candidates)} 只股票（未写库）")
        return {'success': True, 'report_date': report_date, 'fetched': fetched,
                'universe': len(universe), 'universe_source': universe_source,
                'updated': len(candidates), 'skipped': no_match, 'failed': 0,
                'dry_run': True, 'elapsed_s': elapsed}

    # 5. 批量写库（单事务；updated_at 显式刷新）
    if not candidates:
        logger.error("无候选股票可更新，任务失败（不静默成功）")
        return {'success': False, 'report_date': report_date, 'fetched': fetched,
                'universe': len(universe), 'universe_source': universe_source,
                'updated': 0, 'skipped': no_match, 'failed': 0,
                'error': 'no candidates to update',
                'elapsed_s': int(time.time() - started)}

    now = datetime.utcnow()
    updated = 0
    failed: List[str] = []
    try:
        for s in universe:
            if s not in records or s not in exist_set:
                continue
            vals = records[s]
            params_sql = dict(vals)
            params_sql['symbol'] = s
            params_sql['updated_at'] = now
            set_clause = ', '.join(f'{c} = :{c}' for c in vals)
            session.execute(text(
                f"UPDATE quant.stocks SET {set_clause}, updated_at = :updated_at "
                f"WHERE symbol = :symbol AND market='A'"
            ), params_sql)
            updated += 1
    except Exception as e:
        session.rollback()
        logger.error(f"批量写库失败: {type(e).__name__}: {e}")
        return {'success': False, 'report_date': report_date, 'fetched': fetched,
                'universe': len(universe), 'updated': updated,
                'skipped': no_match, 'failed': len(failed) + 1,
                'error': f'bulk update failed: {e}',
                'elapsed_s': int(time.time() - started)}

    session.commit()
    elapsed = int(time.time() - started)
    result = {
        'success': updated > 0,
        'report_date': report_date,
        'fetched': fetched,
        'dupes_removed': dupes,
        'universe': len(universe),
        'universe_source': universe_source,
        'updated': updated,
        'skipped': no_match,
        'failed': len(failed),
        'columns': ['roe', 'gross_margin', 'net_profit_growth', 'revenue_growth'],
        'notes': ('debt_ratio 未更新：东财 yjbb 无资产负债率列；'
                  'pe/pb/market_cap 非本任务范围'),
        'elapsed_s': elapsed,
    }
    logger.info(f"财务数据更新完成: {result}")
    return result


def _f(value) -> Optional[float]:
    """东财同比/比率列数值化；非数值（'--'、空、'-'）→ None（不臆造）"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if s in ('', '-', '--', 'None', 'nan', 'NaN', 'null'):
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _dedup(symbols: List[str]) -> List[str]:
    seen, out = set(), []
    for s in symbols:
        s = str(s).strip()
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def main():
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(description='财务数据更新（基础指标列）')
    parser.add_argument('--report-date', default=DEFAULT_REPORT_DATE,
                        help='报告期 YYYYMMDD（默认 20260630）')
    parser.add_argument('--symbols', nargs='*', default=None,
                        help='指定股票列表（默认全 A 市场）')
    parser.add_argument('--dry-run', action='store_true',
                        help='仅统计不写库')
    args = parser.parse_args()

    result = execute(report_date=args.report_date, symbols=args.symbols,
                     dry_run=args.dry_run)
    print(result)
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
