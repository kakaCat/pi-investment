"""决策教训生成（REQ-9bcd0a WP1，2026-09-12，w-c8cae280）。

背景：DecisionScoreService 只把 score/band/excess 写回 evaluation_result，
learned_lesson 恒空（实测 27 条已评分决策 0 条有教训）→ Autonomy L2 的
"评估 → 教训 → 规则"回流边断裂：评分器知道决策对错，进化线读不到结论。

本模块是**纯函数**（不碰 DB、无副作用），把打分明细转成可检索、可区分的教训文本。
铁律（R-011 教训 · 禁止模板化废话）：每条教训必须含
  ①标的 + ②日期区间 + ③超额数值 + ④band
并附条件化结论；context 里若有 regime / 信号来源则一并带上，便于后续按场景检索。

方向口径（与 score_calculator 一致）：buy 正向、sell/miss 反向——
即 excess_return 已按方向调整，为正表示"该动作优于基准"。
"""
from typing import Any, Dict, Optional

ACTION_ZH = {'buy': '买入', 'sell': '卖出', 'miss': '观望'}

# (action, band) → 条件化结论。未覆盖组合走兜底。
_CONCLUSION = {
    ('buy', 'big_loss'): '买入显著跑输基准：复核当时是否追高/逆势，同类场景应降级处理',
    ('buy', 'small_loss'): '买入小幅跑输基准：边际不利，需更多维度确认后再动手',
    ('buy', 'neutral'): '买入与基准持平：本笔无 alpha，仓位占用需计入机会成本',
    ('buy', 'small_win'): '买入小幅跑赢基准：可继续跟踪同类场景是否稳定',
    ('buy', 'big_win'): '买入显著跑赢基准：作为同类场景正样本，提炼可复现条件',
    ('sell', 'big_win'): '卖出显著优于持有：减仓/止损判断有效，触发条件可固化',
    ('sell', 'small_win'): '卖出小幅优于持有：方向正确',
    ('sell', 'neutral'): '卖出与持有持平：动作价值中性',
    ('sell', 'small_loss'): '卖出后标的略强于基准：复核是否卖早了',
    ('sell', 'big_loss'): '卖出后标的显著跑赢（割肉/卖飞）：复核卖出触发条件是否过松',
    # 注意方向（score_calculator）：excess_return 已按方向调整——miss 为**反向**，
    # 超额为正 = 标的跑输基准 = 观望正确（躲过下跌）；为负 = 标的跑赢基准 = 踏空。
    ('miss', 'big_win'): '观望显著有效：标的跑输基准，躲过下跌，记录该规避场景特征',
    ('miss', 'small_win'): '观望小幅有效：标的略跑输基准',
    ('miss', 'neutral'): '观望结果中性：未行动未造成损失',
    ('miss', 'small_loss'): '观望小幅踏空：标的略跑赢基准，不行动的机会成本',
    ('miss', 'big_loss'): '观望显著踏空──不行动的代价，纳入踏空台账复盘',
}


def _pct(value: float) -> str:
    return f'{value * 100:+.1f}%'


def _ctx_note(context: Optional[Dict[str, Any]]) -> str:
    if not isinstance(context, dict):
        return ''
    parts = []
    for key, label in (('regime', 'regime'), ('market_phase', '阶段'),
                       ('signal_source', '来源'), ('source', '来源'),
                       ('sector', '板块')):
        val = context.get(key)
        if val:
            parts.append(f'{label}={val}')
    seen, uniq = set(), []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return ('（' + '，'.join(uniq[:3]) + '）') if uniq else ''


def generate_lesson(*, action: str, decision_type: str, symbol: Optional[str],
                    trade_price: float, trade_date: str, ref_date: str,
                    excess_return: float, band: str, score: float,
                    window_trading_days: int = 20, benchmark: str = 'sh000300',
                    benchmark_missing: bool = False,
                    context: Optional[Dict[str, Any]] = None) -> str:
    """生成一条可检索的决策教训（纯函数）。"""
    action_zh = ACTION_ZH.get(action, action)
    sym = symbol or '未知标的'
    conclusion = _CONCLUSION.get(
        (action, band),
        f'{action_zh}结果 {band}：按 band 与超额数值复核该笔决策的适用条件',
    )
    missing = '（基准缺失，超额口径降级）' if benchmark_missing else ''
    return (
        f'{action_zh} {sym}@{trade_price:.2f}（{trade_date}→{ref_date}，{window_trading_days} 交易日）'
        f'超额 {_pct(excess_return)}（band={band}，score={score:+.2f}，基准 {benchmark}{missing}）'
        f'→ {conclusion}{_ctx_note(context)}'
        f'〔来源：decision_score_p0a，{decision_type}〕'
    )
