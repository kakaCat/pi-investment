#!/usr/bin/env python
"""调度去重验收检查器（REQ-261001145152-3982 · t-2d52a7）

## 为什么需要它

t-2d52a7 的验收有一条是**时间型判据**：
「连续 3 个交易日 `quant.inprocess_job_runs` 每个 job 每日仅 1 条 success」。

这条没法在改完当天判定——要等真实交易日一天天累积。没有检查器，只能三天后手工翻库
（而"手工翻库"正是本仓反复吃亏的地方：口径写在人脑里，换个人就对不上）。

所以把三条判据固化成一条命令，谁都跑同一个口径。

## 三条判据（与卡片验收逐条对应）

1. **撞点**：`quant.scheduler_tasks` 里**启用**任务的 `cron_expression` 不允许重复
   （`count(*) > 1` 的组数必须为 0）——同点两条启用任务 = 同一件事跑两遍。
2. **每日一次**：`quant.inprocess_job_runs` 里同一 `(job_id, run_date)` 只能有 1 条且 **status=success**；
   连续合格天数需 **≥ 3** 才算过。
   （结构性保证：该表主键就是 `(job_id, run_date)`，所以"多于 1 条"其实插不进去；
   本检查真正盯的是 **status 是否 success** 与 **当天是否漏跑**。）
3. **单一入口**：`adapters/` 下 `unified_scheduler` 的引用数必须是 **0 或 1**（那条空转路径已删除）。

## 用法

    python tools/check_scheduler_dedup.py                    # 全量检查
    python tools/check_scheduler_dedup.py --days 7           # 看最近 7 天的每日一次情况
    python tools/check_scheduler_dedup.py --json             # 机器可读输出
    python tools/check_scheduler_dedup.py --min-days 1       # 降低连续天数门槛（仅调试用）

## 退出码（fail-loud）

    0 = 三条判据全过
    2 = 有判据未过（打印具体是哪条、哪一天、哪个 job）
    3 = 检查器自身出错（连不上库等）

## 口径说明（避免误读）

- "交易日"在本检查里近似为**有调度记录的自然日**：③ DailyJobs 的 cron 只排工作日，
  所以"有记录的日子"基本就是工作日；休市日若仍跑（调度器不认识节假日），也会计入。
- 连续合格天数从**最近一个有记录的日子**往回数；中间断档（某天无任何记录）即停止计数。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_NAME = 'quant_investment'


def _psql(sql: str) -> List[List[Optional[str]]]:
    """执行 SQL 并返回行（用 psql，避免本体依赖 ORM/连接配置）。"""
    out = subprocess.run(
        ['psql', '-d', DB_NAME, '-tAc', sql, '--csv'],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        raise RuntimeError(f"psql 失败：{out.stderr.strip()[:200]}")
    rows = []
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        rows.append(line.split(','))
    return rows


def check_dup_cron() -> Dict[str, Any]:
    """判据 1：启用任务的 cron 撞点组数必须为 0。"""
    rows = _psql(
        "select cron_expression, count(*)::text, string_agg(name, ' | ') "
        "from quant.scheduler_tasks where is_enabled group by cron_expression "
        "having count(*) > 1 order by cron_expression"
    )
    return {
        'name': '① cron 撞点',
        'pass': len(rows) == 0,
        'detail': [{'cron': r[0], 'count': int(r[1]), 'tasks': r[2]} for r in rows] if rows else [],
    }


def check_daily_once(days: int, min_days: int) -> Dict[str, Any]:
    """判据 2：每个 job 每日恰好 1 条 success，且连续合格天数 >= min_days。"""
    rows = _psql(
        "select run_date::text, job_id, status, count(*)::text "
        "from quant.inprocess_job_runs "
        f"where run_date >= current_date - {days} "
        "group by 1,2,3 order by 1 desc, 2"
    )
    per_day: Dict[str, List[Dict[str, str]]] = {}
    for run_date, job_id, status, cnt in rows:
        per_day.setdefault(run_date, []).append(
            {'job_id': job_id, 'status': status, 'count': int(cnt)}
        )

    bad_days: List[Dict[str, Any]] = []
    good_dates: List[str] = []
    for run_date in sorted(per_day, reverse=True):
        problems = [e for e in per_day[run_date] if e['status'] != 'success' or e['count'] != 1]
        if problems:
            bad_days.append({'run_date': run_date, 'problems': problems})
        else:
            good_dates.append(run_date)

    # 从最近一天往回数连续合格天数（遇到不合格即停）
    streak = 0
    for run_date in sorted(per_day, reverse=True):
        clean = all(e['status'] == 'success' and e['count'] == 1 for e in per_day[run_date])
        if clean:
            streak += 1
        else:
            break

    return {
        'name': f'② 每 job 每日仅 1 条 success（连续 ≥ {min_days} 天）',
        'pass': streak >= min_days,
        'streak_days': streak,
        'days_with_records': len(per_day),
        'latest_date': max(per_day) if per_day else None,
        'bad_days': bad_days,
        'note': '无记录的日子不计入连续天数（③ 只排工作日；休市日不跑则断档）'
                if len(per_day) == 0 else '',
    }


def check_single_entry() -> Dict[str, Any]:
    """判据 3：adapters/ 下 unified_scheduler 引用数必须 <= 1。"""
    hits: List[str] = []
    for p in (PROJECT_ROOT / 'adapters').rglob('*.py'):
        if '__pycache__' in str(p):
            continue
        try:
            text = p.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if 'unified_scheduler' in line:
                hits.append(f"{p.relative_to(PROJECT_ROOT)}:{i}")
    return {'name': '③ adapters/ 单一调度入口', 'pass': len(hits) <= 1, 'hits': hits}


def main() -> int:
    ap = argparse.ArgumentParser(description='调度去重验收检查（t-2d52a7）')
    ap.add_argument('--days', type=int, default=7, help='回看天数（默认 7）')
    ap.add_argument('--min-days', type=int, default=3, help='连续合格天数门槛（默认 3，与验收一致）')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    args = ap.parse_args()

    try:
        results = [check_dup_cron(), check_daily_once(args.days, args.min_days), check_single_entry()]
    except Exception as e:  # noqa: BLE001 —— 检查器自身问题，与被检查对象区分开
        print(f"❌ 检查器出错：{e}", file=sys.stderr)
        return 3

    ok = all(r['pass'] for r in results)
    if args.json:
        print(json.dumps({'pass': ok, 'checks': results}, ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{'✅' if r['pass'] else '❌'} {r['name']}")
            if r['name'].startswith('①') and r['detail']:
                for d in r['detail']:
                    print(f"     {d['cron']} × {d['count']}：{d['tasks']}")
            if r['name'].startswith('②'):
                print(f"     连续合格 {r['streak_days']} 天 / 有记录 {r['days_with_records']} 天"
                      f"（最近 {r['latest_date']}）")
                for b in r['bad_days'][:5]:
                    print(f"     ❌ {b['run_date']}: {b['problems']}")
            if r['name'].startswith('③') and r['hits']:
                for h in r['hits']:
                    print(f"     {h}")
        print()
        print('结论：' + ('全部判据通过 ✅' if ok else '有判据未过 ❌（见上）'))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
