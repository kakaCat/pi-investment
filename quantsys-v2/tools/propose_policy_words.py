#!/usr/bin/env python3
"""政策词表覆盖诊断（2026-10-21）。

用途：拉最近一档全市场新闻（DataProviderManager.get_market_news），逐条跑
policy_lexicon 分级；把**未命中但带政策/行业特征线索**的标题挑出来，附每条的
「疑似线索词」，供人工决定要不要补进词表（POLICY_CRITICAL / POLICY_SOFT /
INDUSTRY_LEXICONS）。

为什么需要：词表是数据，一版写死不等于覆盖真实新闻流。首轮线上扫描 10 条 0 命中
不代表管线坏，而是词与真实标题没对上——用真实样本迭代比凭空堆词有效。

只读：不写库、不发卡、不改词表。

用法：
    PYTHONPATH=. python tools/propose_policy_words.py            # 默认 200 条
    PYTHONPATH=. python tools/propose_policy_words.py --limit 50
    PYTHONPATH=. python tools/propose_policy_words.py --all      # 连命中的一起列
"""
from __future__ import annotations

import argparse
import sys

# 复用线上同一条取数通道与同一套词表——诊断口径必须与生产一致
from qs_watch.application.services.watch_engine.policy_lexicon import (  # noqa: E402
    INDUSTRY_LEXICONS,
    lexicon_for,
)
from qs_watch.application.services.watch_engine.policy_watch_service import (  # noqa: E402
    detect_sectors,
)
from qs_watch.application.services.watch_engine.policy_news_source import (  # noqa: E402
    PolicyNewsSource,
)

#: 「像政策/行业消息」的宽线索（**仅用于挑候选，不是判定词表**）：
#: 判定仍走 policy_lexicon；这里只回答「这条为什么值得看一眼」。
CUE_TOKENS = (
    '发布', '印发', '出台', '推出', '实施', '启动', '部署', '推进', '试点',
    '通知', '意见', '规划', '办法', '规定', '条例', '细则', '标准',
    '监管', '查处', '立案', '约谈', '处罚', '整改', '规范',
    '降准', '降息', '加息', '流动性', '逆回购', 'MLF', 'LPR',
    '关税', '出口', '进口', '制裁', '管制', '配额',
    '补贴', '退税', '减税', '专项债', '国债', '财政',
    '部委', '发改委', '工信部', '财政部', '央行', '证监会', '卫健委', '能源局',
    '会议', '座谈会', '常务会', '国常会', '政治局',
)


def _hits(title: str, words) -> list[str]:
    return [w for w in words if w and w in title]


def diagnose(records, show_all: bool = False) -> list[dict]:
    """对每条标题出诊断：命中层级 + 疑似线索 + 板块识别。纯函数，便于单测。"""
    out: list[dict] = []
    policy_lex = lexicon_for(policy=True, include_stock=False)
    for rec in records:
        title = str(rec.get('title') or '')
        tier, words = policy_lex.classify(title)
        sectors = [s.get('sector') or s.get('name') for s in detect_sectors(title)]
        cues = _hits(title, CUE_TOKENS)
        industry_hits = _hits(title, tuple(
            w for lex in INDUSTRY_LEXICONS.values()
            for w in (lex.critical + lex.soft)))
        out.append({
            'title': title,
            'tier': tier,
            'hit_words': list(words),
            'sectors': sectors,
            'cues': cues,
            'industry_words': industry_hits,
            'candidate': tier == 'none' and bool(cues or industry_hits),
        })
    return out if show_all else [r for r in out if r['candidate']]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='政策词表覆盖诊断（只读）')
    ap.add_argument('--limit', type=int, default=200, help='取样条数（默认 200）')
    ap.add_argument('--all', action='store_true', help='连已命中的一起列出')
    args = ap.parse_args(argv)

    src = PolicyNewsSource(limit=args.limit)
    fetched = src.fetch(limit=args.limit)
    if fetched.get('skipped'):
        print('取数失败（不算「无政策消息」）：%s' % fetched.get('reason'), file=sys.stderr)
        return 2
    records = fetched.get('records') or []
    print('样本：%d 条（provider=%s）' % (len(records), fetched.get('provider') or '?'))

    rows = diagnose(records, show_all=args.all)
    if not rows:
        print('全部未命中候选线索——词表暂时没有明显漏网（或样本太窄）')
        return 0

    print('\n未命中但值得看一眼：%d 条\n' % len(rows))
    for i, r in enumerate(rows, 1):
        marks = []
        if r['cues']:
            marks.append('线索=%s' % '/'.join(r['cues'][:4]))
        if r['industry_words']:
            marks.append('行业词=%s' % '/'.join(r['industry_words'][:4]))
        if r['sectors']:
            marks.append('板块=%s' % '/'.join(r['sectors']))
        print('%2d. %s' % (i, r['title'][:90]))
        if marks:
            print('    %s' % '  '.join(marks))

    print('\n补词建议：')
    print('  · POLICY_CRITICAL/POLICY_SOFT 加词 → policy_lexicon.POLICY_*')
    print('  · 行业词 → INDUSTRY_LEXICONS[板块] 或 register_industry(...)')
    print('  · 新板块别名 → SECTOR_ALIASES（板块解析靠它命中）')
    print('  · 只加「新闻标题里会出现的实词」，别加宽泛到必然命中的词')
    return 0


if __name__ == '__main__':
    sys.exit(main())
