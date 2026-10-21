"""规则健康检查「预案日期」误伤修复的回归测试（2026-10-21）

事故：2026-10-21 16:30:15 规则健康巡检把 **#269**（600000 浦发银行 R-022
分批止盈）与 **#295**（601600 止盈阶梯）自动禁用，理由是
「预案日期已过期（01/03，已过去 291 天）」。

根因：预案日期检测用宽松正则从 context **散文**里抓任意「M/D」：
  「卖出 1/3 锁定利润」 → 被读成「1 月 3 日」。
R-022 分批止盈的文案天然含 "1/3"（卖三分之一），所以**每一条分批止盈规则
都会中招**。全库扫描：80 条规则带同款雷。

修复口径：只认**带标签**的日期（预案日期：/ 有效期至：/ 截止日期：…），
散文里的裸数字一律不解释为日期。

本测试以**故障注入为主**（CLAUDE.md 事故沉淀：只测成功路径等于没测）——
每个用例都要能证明"旧实现会误伤、新实现不会"。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from adapters.inbound.fastapi_app.daily_jobs.health import (  # noqa: E402
    find_labelled_preplan_date,
)


# ── 事故现场的真实文案（取自 quant.watch_rules.context）────────────

#: #269 的 context（R-022 分批止盈，agent_brain）——含「1/3」「1/3」「+10%」
RULE_269_CONTEXT = (
    'R-022(candidate) 分批止盈纪律补挂：600000 浦发银行 100股@9.03。'
    '浮盈 ≥+10% 卖 1/3 锁定利润；≥+15% 再卖 1/3；剩余移动止盈，'
    '自最高浮盈回撤 5 个百分点清仓。'
)

#: #295 的 context（601600 止盈阶梯）——含「1/3」
RULE_295_CONTEXT = (
    '【中国铝业止盈阶梯】① 触及9.90 → 第一目标达成，卖出1/3仓位锁定利润（+12%）；'
    '② 触及11.20 → 第二目标，卖出1/3；③ 剩余仓位移动止盈。'
)

#: 买入区间文案——含「8.40」「8.20~8.40」等裸数字
RULE_293_CONTEXT = (
    '【中国铝业买入信号】调研结论：底部区域分批布局。'
    '① 跌破8.40 → 进入主仓买入区(8.20~8.40)，应评估加仓。'
)


class TestPreplanDateNotInferredFromProse:
    """核心：散文里的裸数字**不得**被解释为日期。"""

    def test_r022_take_profit_context_not_treated_as_date(self):
        """事故现场：#269 的「卖出 1/3」不得被读成 1 月 3 日。

        故障注入：旧实现对这段文本会匹配到 ("1","3") → 构造 1月3日 →
        已过去 291 天 → OUTDATED → 自动禁用。
        """
        assert find_labelled_preplan_date(RULE_269_CONTEXT) is None, (
            'R-022 分批止盈文案含「1/3」，绝不能被当成 1 月 3 日')

    def test_r295_take_profit_context_not_treated_as_date(self):
        """事故现场：#295 的「卖出1/3仓位」同样不得被读成日期。"""
        assert find_labelled_preplan_date(RULE_295_CONTEXT) is None

    def test_buy_zone_context_not_treated_as_date(self):
        """含裸数字的买入区间文案不得被当成预案日期。"""
        assert find_labelled_preplan_date(RULE_293_CONTEXT) is None

    @pytest.mark.parametrize('text', [
        '1/3 仓位',
        '12/31 结算',
        '10/20 跌破8.40',
        '2026-01-03 复盘',
        '今日 3/5 信号',
        '1、2、3 条',
    ])
    def test_bare_numbers_never_parse_as_date(self, text):
        """任何无标签的裸数字/日期形态都不得被识别为预案日期。"""
        assert find_labelled_preplan_date(text) is None


class TestLabelledDateStillWorks:
    """修复不能变成"完全不认日期"——带标签的必须照常生效。"""

    @pytest.mark.parametrize('label', [
        '预案日期', '有效期至', '有效期', '截止日期', '到期日', '失效日期',
    ])
    def test_each_label_recognised(self, label):
        text = f'本规则 {label}：2026-01-03 到期'
        found = find_labelled_preplan_date(text)
        assert found == datetime(2026, 1, 3), f'标签 {label} 应被识别'

    def test_fullwidth_colon_supported(self):
        """中文全角冒号也是合法写法。"""
        assert find_labelled_preplan_date('预案日期：2026-01-03') == datetime(2026, 1, 3)

    def test_halfwidth_colon_supported(self):
        assert find_labelled_preplan_date('预案日期: 2026-01-03') == datetime(2026, 1, 3)

    def test_label_must_precede_date(self):
        """标签是锚：日期在前、标签在后不构成标注。"""
        assert find_labelled_preplan_date('2026-01-03 预案日期') is None

    def test_first_labelled_date_wins(self):
        """多个带标签日期时取第一个（先写的那个才是生效日期）。"""
        text = '预案日期：2026-01-03；备注：有效期至：2026-12-31'
        assert find_labelled_preplan_date(text) == datetime(2026, 1, 3)

    def test_invalid_date_after_label_is_skipped(self):
        """标签后是非法日期（13 月）→ 不应抛异常，也不应误判。"""
        assert find_labelled_preplan_date('预案日期：2026-13-45') is None

    def test_empty_context_returns_none(self):
        assert find_labelled_preplan_date('') is None
        assert find_labelled_preplan_date(None) is None


class TestRegressionAgainstLiveRuleContexts:
    """回归：拿库里真实 context 过一遍，确保不误伤。"""

    def test_all_enabled_rule_contexts_yield_no_inferred_date(self):
        """把当前库里所有启用规则的 context 喂进判定函数。

        期望：**没有任何一条**因为散文推断被判为过期——
        这正是本次误伤的形态（80 条规则带雷）。
        """
        import re as _re
        try:
            import psycopg2
            conn = psycopg2.connect(
                host='127.0.0.1', user='mac', dbname='quant_investment')
            cur = conn.cursor()
            cur.execute(
                "select id, context from quant.watch_rules where context is not null")
            rows = cur.fetchall()
            cur.close()
            conn.close()
        except Exception as e:  # pragma: no cover - 环境不可用时跳过
            pytest.skip(f'无法连接测试库，跳过库级回归：{e}')

        assert rows, '库中应存在带 context 的规则'
        # 旧实现的判法（宽松正则抓任意 M/D 或 YYYY-MM-DD）会命中多少条
        old_would_hit = 0
        # 新实现（只认带标签日期）判为过期的条数
        new_hits = []
        for rule_id, context in rows:
            old_hits = (_re.findall(r'(\d{1,2})/(\d{1,2})', context)
                        or _re.findall(r'(\d{4})-(\d{2})-(\d{2})', context))
            if old_hits:
                old_would_hit += 1
            found = find_labelled_preplan_date(context)
            if found is not None and (datetime.now() - found).days > 7:
                new_hits.append((rule_id, found.date().isoformat()))

        # 新实现：没有带标签日期的规则，一律不得被判过期
        assert new_hits == [], (
            f'新实现仍误判 {len(new_hits)} 条规则，例：{new_hits[:5]}')
        # 旧实现的误伤面（供人工核对规模；库为空时跳过断言）
        assert old_would_hit > 0, (
            '预期旧正则会命中一批规则——若为 0 说明库数据变了，请人工复核')
