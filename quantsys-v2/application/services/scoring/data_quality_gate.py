"""
数据质量门（DataQualityGate）

评分前对每只股票做检测与有限自愈：
1. 脏 bar 剔除（close≤0、amount=0 但 volume>0 的 07-13 事故模式）——剔除不重抓
2. 近端缺口补抓（最后一根 K 线距今 >4 天）——走 DataProviderManager 统一入口
3. 修复预算：单实例最多 repair_budget 次补抓，超出降级
4. 全程可见：repairs 文本进 reasons，repair_report 进 diagnostics

不做：不补历史大段缺口（数据管道职责）、不插值编造、不让修复失败炸掉扫描。
"""
from typing import Dict, Any, List, Optional, Tuple
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
    ) -> Tuple[List[Dict], List[str]]:
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
