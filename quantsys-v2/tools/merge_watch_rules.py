#!/usr/bin/env python
"""盯盘规则重复组合并（2026-10-16 · REQ-261016155500-4f2a §6.2.1，按账户归属修正版）

## 背景

生产 5 组重复盯盘（设计 §6.2.1）。核对 linked_account 后修正：002007 的 59
属 user_main_simulation、157/193/199 属 agent_brain——**跨账户不合**（用户
2026-09-11 定调），故 002007 拆两组，59 仅做 symbol 归一。实际合并 6 条：

  保留 157 ← 并入 193, 199        （002007 / agent_brain）
  保留 59  ← 仅 symbol 归一       （002007 / user_main_simulation）
  保留 256 ← 并入 245             （002027）
  保留 248 ← 并入 249             （300418）
  保留 247 ← 并入 242             （301358）
  保留 259 ← 并入 235             （600011）

## 操作

1. 保留规则 symbol 归一为 6 位纯代码；donor 同步归一（保留审计一致性）。
2. 保留规则 conditions 并入 donor conditions（按 JSON 精确去重）。
3. 元数据回填：保留规则缺失的 intent / cost_price / next_action_hint /
   linked_account（+account）取首个非空 donor 的值。
4. donor：enabled=false；双方 ops_notes 记合并溯源（幂等：同标记已存在则跳过）。

## 安全

- 执行前已备份 quant.watch_rules（backups/watch_rules_20261016_pre_upgrade.dump）；
- 默认 dry-run（打印完整计划），`--apply` 才写库；可重复执行（幂等）。

用法（在 quantsys-v2/ 下）：
    PYTHONPATH=. ./venv/bin/python tools/merge_watch_rules.py            # dry-run
    PYTHONPATH=. ./venv/bin/python tools/merge_watch_rules.py --apply
"""
import argparse
import json
from datetime import datetime, timezone

MERGE_MARKER = 'merge/20261016'

#: (keep_id, [donor_ids], 说明)——donors 条件并入 keep，donor 停用。
#: 59 无 donor：仅 symbol 归一（002007 跨账户不合，设计 §6.2.1 修正）。
GROUPS = [
    (157, [193, 199], '002007/agent_brain：三条同成本持仓管理合一'),
    (59, [], '002007/user_main_simulation：仅 symbol 归一（跨账户不合）'),
    (256, [245], '002027'),
    (248, [249], '300418'),
    (247, [242], '301358'),
    (259, [235], '600011'),
]

META_FIELDS = ('intent', 'cost_price', 'next_action_hint', 'linked_account', 'account')


def _norm_symbol(symbol: str) -> str:
    return (symbol or '').split('.')[0].strip()


def _cond_key(cond: dict) -> str:
    return json.dumps(cond, sort_keys=True, ensure_ascii=False)


def _fmt_cond(c: dict) -> str:
    p = (c or {}).get('params') or {}
    return '%s %s %s' % (c.get('type'), p.get('direction', ''),
                         p.get('price', p.get('pct', p.get('multiple', ''))))


def _note_now(by: str, text: str) -> dict:
    return {'at': datetime.now(timezone.utc).isoformat(), 'by': by, 'text': text}


def _append_note(notes, marker: str, text: str) -> list:
    notes = list(notes or [])
    if any(marker in (n.get('text') or '') for n in notes):
        return notes  # 幂等：同标记注记已存在
    notes.append(_note_now(marker, text))
    return notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true', help='实际写库（默认 dry-run）')
    args = parser.parse_args()

    from adapters.outbound.repositories.watch_rule_repository import WatchRuleRepository

    repo = WatchRuleRepository()
    now_tag = MERGE_MARKER

    n_disabled = 0
    for keep_id, donor_ids, desc in GROUPS:
        keep = repo.get_by_id(keep_id)
        if keep is None:
            print('!! 保留规则 #%s 不存在，跳过（%s）' % (keep_id, desc))
            continue
        donors = [d for d in (repo.get_by_id(i) for i in donor_ids) if d is not None]

        old_sym = keep.symbol
        new_sym = _norm_symbol(keep.symbol)
        merged = list(keep.conditions or [])
        seen = {_cond_key(c) for c in merged}
        added = []
        for d in donors:
            for c in (d.conditions or []):
                if _cond_key(c) not in seen:
                    merged.append(c)
                    seen.add(_cond_key(c))
                    added.append(c)

        fills = {}
        for f in META_FIELDS:
            if getattr(keep, f, None) in (None, ''):
                for d in donors:
                    if getattr(d, f, None) not in (None, ''):
                        fills[f] = getattr(d, f)
                        break

        print('== #%s %s（%s）' % (keep_id, new_sym, desc))
        print('   symbol: %s -> %s%s' % (old_sym, new_sym,
                                          '' if old_sym == new_sym else '  [归一]'))
        print('   条件: %d -> %d 档%s' % (len(keep.conditions or []), len(merged),
              '（新增: %s）' % ', '.join(_fmt_cond(c) for c in added) if added else ''))
        if fills:
            print('   元数据回填: %s' % ', '.join('%s=%s' % (k, v) for k, v in fills.items()))
        for d in donors:
            print('   donor #%s: enabled -> false' % d.id)
        n_disabled += len(donors)

        if not args.apply:
            continue

        keep_note = _note_now(now_tag,
                              '合并入规则 #%s 的重复档（%s）' % (keep_id, desc))
        # ── 保留规则更新 ──────────────────────────────────────
        update = {'symbol': new_sym, 'conditions': merged,
                  'ops_notes': _append_note(
                      keep.ops_notes, now_tag,
                      '重复规则合并（%s）：并入 %s' % (desc, [d.id for d in donors])
                      or 'symbol 归一')}
        if not donor_ids:
            update['ops_notes'] = _append_note(
                keep.ops_notes, now_tag, 'symbol 归一：%s -> %s' % (old_sym, new_sym))
        update.update(fills)
        updated = repo.update_fields(keep_id, **update)
        if updated is None:
            print('!! 保留规则 #%s 更新失败' % keep_id)
            continue

        # ── donor 停用 + 溯源 ──────────────────────────────────
        for d in donors:
            repo.update_fields(
                d.id,
                enabled=False,
                ops_notes=_append_note(
                    d.ops_notes, now_tag,
                    '已并入规则 #%s（%s）后停用；阈值档位并入保留规则' % (keep_id, desc)))

    print('== %s: 停用 donor 共 %d 条 ==' % ('APPLIED' if args.apply else 'DRY-RUN',
                                            n_disabled))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
