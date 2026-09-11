# domain/trading/services/trading_status_policy.py
"""交易状态领域策略（纯领域逻辑，零外部依赖）

RFC 015 §4.1/§4.3（2026-09-11 REQ-cf627b）：
- 涨跌幅限制：ST=5%；创业板 300/301、科创板 688/689=20%；其余=10%
- 停牌判定：基础状态 is_suspended/is_delisted，或行情「成交量为 0 且现价==昨收」
- 涨跌停：现价 >= 昨收×(1+limit_ratio) - 0.005 / <= 昨收×(1-limit_ratio) + 0.005
- 可交易 = 未停牌 且 非涨停（涨停难以买入）；ST 不影响可交易性
- **跨源冲突保守裁决**：基础状态与行情推导矛盾（停牌口径冲突、ST 标记冲突）
  → 取「不可交易」并在 reason 中标注 conflict（宁可错杀一次委托，
  不可在停牌票上误下单）
"""
from datetime import datetime
from typing import Dict, List, Optional

from domain.trading.models.trading_status import TradingStatus


class TradingStatusPolicy:
    """交易状态裁决策略"""

    # 涨跌停价比较容差：报价最小变动 0.01 元，浮点比较留 0.005 容差
    PRICE_EPS = 0.005

    ST_LIMIT = 0.05
    STAR_LIMIT = 0.20
    DEFAULT_LIMIT = 0.10
    BSE_LIMIT = 0.30   # 北交所（2026-09-11 修正，w-f436d4ea：真实限幅 30%，且不适用沪深 ST 的 5%）

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _num(value) -> Optional[float]:
        """安全转 float（None/NaN/非数 → None）"""
        if value is None:
            return None
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if f != f:  # NaN
            return None
        return f

    # ------------------------------------------------------------ 涨跌幅限制

    def limit_ratio_for(self, symbol: str, is_st: bool) -> float:
        """该标的的涨跌幅限制比例

        口径（按真实交易规则）：
        - 北交所（430/83x/87x/88x/920xxx）= **30%**，且北交所不适用沪深 ST 的 5% 限幅
          → 北交所判定必须放在 is_st **之前**（2026-09-11 修正：此前按简化写成 10%，
            会把北交所 10%~30% 的正常波动误判为涨停，从而**误禁合法交易**——
            这不是"保守"，是错误）
        - ST（含 *ST，沪深）= 5%
        - 创业板 300/301、科创板 688/689 = 20%
        - 其余（沪深主板）= 10%
        """
        bare = str(symbol or '').split('.')[0]
        # 北交所优先：其限幅 30% 且不受沪深 ST 5% 规则约束
        if bare.startswith(('43', '83', '87', '88', '920')):
            return self.BSE_LIMIT
        if is_st:
            return self.ST_LIMIT
        if bare.startswith(('300', '301', '688', '689')):
            return self.STAR_LIMIT
        return self.DEFAULT_LIMIT

    # ------------------------------------------------------------ 冲突检测

    def detect_conflicts(self, base: Optional[Dict], quote: Optional[Dict]) -> List[Dict]:
        """跨源冲突检测（基础状态 vs 实时行情）

        仅在**两源都有结论**时才判冲突：行情不可用（quote 为空/无价）不算冲突。
        """
        base = base or {}
        quote = quote or {}
        conflicts: List[Dict] = []

        price = self._num(quote.get('price'))
        if price is None or price <= 0:
            return conflicts  # 行情不可用 → 无法交叉校验

        prev_close = self._num(quote.get('prev_close')) or self._num(base.get('prev_close')) or 0.0
        volume = self._num(quote.get('volume'))
        base_suspended = bool(base.get('is_suspended')) or bool(base.get('is_delisted'))
        quote_suspended = bool(
            volume is not None and volume == 0 and prev_close > 0
            and abs(price - prev_close) < 1e-9
        )
        if base_suspended != quote_suspended:
            conflicts.append({
                'field': 'is_suspended',
                'base': base_suspended,
                'quote': quote_suspended,
                'detail': (
                    '基础状态 is_suspended=' + str(base_suspended) + '，行情推导 is_suspended='
                    + str(quote_suspended) + '（volume=' + str(volume) + ', price=' + str(price)
                    + ', prev_close=' + str(prev_close) + '）'
                ),
                'resolution': 'conservative: 取不可交易',
            })

        name = str(quote.get('name') or '')
        quote_st = ('ST' in name.upper()) if name else False
        if quote_st and not bool(base.get('is_st')):
            conflicts.append({
                'field': 'is_st',
                'base': bool(base.get('is_st')),
                'quote': True,
                'detail': '基础表 is_st=False，行情名称为「' + name + '」含 ST 标记',
                'resolution': 'conservative: 取不可交易',
            })

        return conflicts

    # ---------------------------------------------------------------- 裁决

    def evaluate(self, base: Optional[Dict], quote: Optional[Dict]) -> TradingStatus:
        """综合基础状态与实时行情，裁决 TradingStatus

        Args:
            base: ITradingStatusRepository.get_stock_status() 的返回（可为 None）
            quote: 实时行情 dict（symbol/name/price/prev_close/volume/source...，可为 None）

        Returns:
            TradingStatus（不可变值对象）
        """
        base = base or {}
        quote = quote or {}
        as_of = datetime.now().isoformat()

        symbol = str(base.get('symbol') or quote.get('symbol') or '')
        price = self._num(quote.get('price'))
        volume = self._num(quote.get('volume'))
        quote_prev_close = self._num(quote.get('prev_close'))
        has_quote = price is not None and price > 0

        name = str(quote.get('name') or '')
        quote_st = ('ST' in name.upper()) if name else False

        base_st = bool(base.get('is_st'))
        is_st = base_st or quote_st

        base_suspended = bool(base.get('is_suspended')) or bool(base.get('is_delisted'))
        limit_ratio = self.limit_ratio_for(symbol, is_st)

        prev_close = quote_prev_close if (quote_prev_close and quote_prev_close > 0) else (
            self._num(base.get('prev_close')) or 0.0
        )

        quote_suspended = False
        limit_up = False
        limit_down = False
        if has_quote:
            if volume is not None and volume == 0 and prev_close > 0 and abs(price - prev_close) < 1e-9:
                quote_suspended = True
            if prev_close > 0:
                if price >= prev_close * (1 + limit_ratio) - self.PRICE_EPS:
                    limit_up = True
                elif price <= prev_close * (1 - limit_ratio) + self.PRICE_EPS:
                    limit_down = True

        conflicts = self.detect_conflicts(base, quote)
        is_suspended = base_suspended or quote_suspended

        # 可交易 = 未停牌 且 非涨停；跨源冲突一律保守取不可交易
        tradeable = (not is_suspended) and (not limit_up) and (not conflicts)

        # ---- reason 组装（人可读、可复核，冲突以 'conflict' 关键字标注）
        parts: List[str] = []
        if conflicts:
            parts.append('conflict（跨源冲突，保守取不可交易）: ' + '; '.join(c['detail'] for c in conflicts))
        if is_st:
            # 限幅取实际值：沪深 ST=5%，北交所 ST 仍为 30%（硬编码 5% 会误导复核者）
            parts.append('ST/*ST（限幅 ' + str(int(limit_ratio * 100)) + '%）')
        if base_suspended:
            parts.append('停牌/退市（来自 stocks 表基础状态）')
        if quote_suspended:
            parts.append('停牌（行情推导：成交量为 0 且现价=昨收）')
        if limit_up:
            parts.append('涨停（现价 ' + str(price) + ' >= 涨停价 '
                         + str(round(prev_close * (1 + limit_ratio), 2)) + '）')
        if limit_down:
            parts.append('跌停（现价 ' + str(price) + ' <= 跌停价 '
                         + str(round(prev_close * (1 - limit_ratio), 2)) + '）')
        if not has_quote:
            parts.append('实时行情不可用（仅按基础状态判定）')
        if not parts:
            parts.append('正常交易（限幅 ' + str(int(limit_ratio * 100)) + '%）')
        parts.append('可交易' if tradeable else '不可交易')

        return TradingStatus(
            symbol=symbol,
            is_st=is_st,
            is_suspended=is_suspended,
            limit_up=limit_up,
            limit_down=limit_down,
            tradeable=tradeable,
            reason='；'.join(parts),
            as_of=as_of,
            prev_close=float(prev_close or 0.0),
            limit_ratio=limit_ratio,
        )
