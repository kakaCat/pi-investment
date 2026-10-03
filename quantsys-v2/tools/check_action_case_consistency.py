#!/usr/bin/env python3
"""大小写一致性检查器（REQ-261001145152-3982 审查沉淀）。

## 为什么需要它

2026-10-02 的审查中发现：库里**同一个枚举列存在两套写法**，而代码里大量
"只认一种写法"的比较 → **静默漏行**（不报错，只是数字变小/为 0）。实测取证：

    quant.simulation_trades.action :  BUY 32 · SELL 21 · sell 16 · buy 9

后果实例（都在本次审查中被修掉，但**根因还在写入侧**）：
  · `PortfolioCalculator.calculate_cash_balance` 只认小写 → **漏掉 53 行大写成交 → 现金余额算错**；
  · `AccountTradingService._check_daily_buy_limits` 只认大写 → **日买入限额护栏失效**；
  · `StrategyCombiner` 遇大写动作 → `KeyError` 崩溃；`Counter` 口径下**同向票数被稀释**；
  · 另 11 处读取侧比较（交易护栏 / 模拟盘 / 绩效归因 / 周报 …）。

**关键教训**：两张表的契约**相反**，不能一刀切 ——
`quant.trades` 有 CHECK 强制小写（大小写敏感比较是**正确**的），
`quant.simulation_trades` 无约束且两套并存（**必须**大小写无关）。
所以判据不能写成"所有比较都必须 lower"，而要问：**这个取值来自哪里？**

## 检查什么

1. **数据侧（连库实查）**：哪些枚举列的取值**大小写不一致** →
   这些列是"必须按大小写无关读取"的对象；
2. **代码侧（静态扫描）**：生产代码里对 `.<枚举列>` 的**大小写敏感比较** →
   若该列在上一步被判定为"不一致"，则为**高危**（会静默漏行）。

## 用法

    python tools/check_action_case_consistency.py            # 报告（默认连生产库只读）
    python tools/check_action_case_consistency.py --db quant_test
    python tools/check_action_case_consistency.py --strict   # 有高危即退出码 2

退出码：0 = 无高危；2 = 有高危（且 `--strict`）；3 = 检查器自身出错。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# 关注的枚举列（扩展到审查中核对过的那些）
WATCH_COLUMNS = ('action', 'status', 'side', 'direction', 'order_type', 'execution_status')

# 生产代码目录（tests/ 不算）
CODE_DIRS = ('domain', 'application', 'infrastructure', 'adapters', 'utils')

# 已知受 CHECK 约束、写法恒定的表（大小写敏感比较在这些表上是**正确**的）
KNOWN_CONSTRAINED = {
    'trades',  # CHECK: action IN ('buy','sell')，两侧库实测均如此
}


def _psql(db: str, sql: str) -> list[str]:
    r = subprocess.run(['psql', '-d', db, '-tAc', sql], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'psql({db}) 失败: {r.stderr.strip()[:160]}')
    return [x for x in r.stdout.strip().split('\n') if x]


def scan_data(db: str) -> dict[tuple[str, str], list[str]]:
    """返回 {(表, 列): [取值...]}，只保留**大小写不一致**的列。"""
    mixed: dict[tuple[str, str], list[str]] = {}
    for col in WATCH_COLUMNS:
        rows = _psql(db, f"""
            select c.table_name
            from information_schema.columns c
            where c.table_schema='quant' and c.column_name='{col}'
              and c.data_type in ('character varying','text')
        """)
        for table in rows:
            vals = _psql(db, f"""
                select distinct {col} from quant."{table}"
                where {col} is not null and {col} <> '' limit 20
            """)
            lowered = {v.lower() for v in vals}
            if len({v for v in vals}) > len(lowered) and len(lowered) > 0:
                # 存在"同一语义的两种写法"（如 BUY 与 buy）
                if any(v != v.lower() for v in vals) and any(v == v.lower() for v in vals):
                    mixed[(table, col)] = sorted(vals)
    return mixed


def _window(path, lineno: int, back: int = 15) -> str:
    """取该行之前的若干行（用于判断变量是否已在局部归一化）。"""
    lines = path.read_text(encoding='utf-8', errors='ignore').split('\n')
    return '\n'.join(lines[max(0, lineno - back - 1):lineno - 1])


def scan_code(mixed_columns: set[str]) -> list[tuple[str, int, str]]:
    """扫描生产代码里对关注列的**大小写敏感**比较；返回 (文件, 行号, 代码)。"""
    hits: list[tuple[str, int, str]] = []
    pat = re.compile(
        r"\.(?:" + '|'.join(WATCH_COLUMNS) + r")\s*[!=]=\s*['\"][A-Za-z_]+['\"]"
        r"|\b(?:action|status|side|direction)\s*[!=]=\s*['\"][A-Za-z_]+['\"]"
    )
    for d in CODE_DIRS:
        for f in Path(d).rglob('*.py'):
            if '__pycache__' in str(f):
                continue
            for i, line in enumerate(f.read_text(encoding='utf-8', errors='ignore').split('\n'), 1):
                s = line.strip()
                if s.startswith('#') or 'str(' in line:
                    continue
                m = pat.search(line)
                if m:
                    col = re.search(r'(action|status|side|direction)', m.group(0))
                    col = col.group(1) if col else '?'
                    # 2026-10-02：**识别"局部已归一化"**，避免误报。
                    # 实测反例：`backtest_stage.py` 先 `action = sig.get("action","HOLD").upper()`
                    # 再 `if action == "BUY"` —— 那是**正确**的；`strategy_adapter.py` 同理。
                    # 判据：本行之前约 15 行内出现过该变量的 .upper()/.lower() 赋值。
                    window = '\n'.join(
                        f.read_text(encoding='utf-8', errors='ignore').split('\n')[max(0, i - 16):i - 1]
                    ) if False else _window(f, i)
                    already = re.search(
                        rf'{col}\s*=\s*[^\n]*\.(?:upper|lower)\(\)', window
                    ) is not None
                    if already:
                        continue
                    level = '高危' if col in mixed_columns else '关注'
                    hits.append((str(f), i, f'[{level}] {s[:110]}'))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default='quant_investment', help='要实查的库（只读）')
    ap.add_argument('--strict', action='store_true', help='有高危时退出码 2')
    args = ap.parse_args()

    try:
        mixed = scan_data(args.db)
    except Exception as e:  # noqa: BLE001
        print(f'❌ 数据侧检查失败: {e}', file=sys.stderr)
        return 3

    print(f'  ── 数据侧（{args.db}）大小写不一致的列 ──')
    if not mixed:
        print('    （无）')
    for (table, col), vals in sorted(mixed.items()):
        tag = '（已知受 CHECK 约束，属正常）' if table in KNOWN_CONSTRAINED else ''
        print(f'    quant.{table}.{col}{tag}: {vals}')

    mixed_cols = {c for (t, c) in mixed if t not in KNOWN_CONSTRAINED}
    print(f'\n  ── 代码侧大小写敏感比较（{len(CODE_DIRS)} 个目录）──')
    hits = scan_code(mixed_cols)
    high = [h for h in hits if h[2].startswith('[高危]')]
    for f, i, line in hits[:20]:
        print(f'    {f}:{i}  {line}')
    if len(hits) > 20:
        print(f'    …另外 {len(hits) - 20} 处')
    print(f'\n  合计 {len(hits)} 处｜其中高危 {len(high)} 处'
          f'（高危 = 该列在库里确有大小写两种写法，敏感比较会静默漏行）')

    if high and args.strict:
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
