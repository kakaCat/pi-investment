"""Akshare dividend data provider."""
import logging
from typing import Optional, List
from datetime import datetime
from adapters.outbound.datasources.base import DividendProvider
from adapters.outbound.datasources.models import DividendData

logger = logging.getLogger(__name__)


class AkshareDividendProvider(DividendProvider):
    """Akshare dividend data provider"""

    @property
    def name(self) -> str:
        return 'akshare'

    def get_dividends(self, symbol: str, years: int = 5) -> Optional[List[DividendData]]:
        """Get dividend history

        Args:
            symbol: Stock symbol
            years: Number of years to fetch

        Returns:
            List of DividendData or None if failed
        """
        try:
            import akshare as ak

            # Extract code without suffix (e.g., 600519.SH -> 600519)
            code = symbol.split('.')[0]
            df = ak.stock_dividend_cninfo(symbol=code)

            if df is None or df.empty:
                logger.warning(f"{self.name}: No dividend data for {symbol}")
                return None

            # Convert to DividendData list
            # 2026-09-11（REQ-cf627b，w-f436d4ea）字段映射修复：
            # akshare stock_dividend_cninfo 实测列名为
            #   实施方案公告日期/分红类型/送股比例/转增比例/派息比例/股权登记日/除权日/派息日/...
            # 而旧代码读的是 '每股派息'/'股息率'/'除权除息日' —— 这些列**不存在**，
            # 导致 dividend_per_share 恒 0、ex_dividend_date 恒 None（即「分红源返回全 0 行」
            # 被误判为『该公司不分红』）。此处按实测真实列名映射，派息比例（每10股）→ 每股派息。
            def _num(v):
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            def _date(v):
                s = str(v) if v is not None else ''
                return s[:10] if s and s not in ('None', 'nan', 'NaT') else None

            result = []
            for _, row in df.head(years * 2).iterrows():  # *2 to get more records
                dps_per10 = _num(row.get('派息比例'))  # 每10股派息(元,含税)
                # 从说明文本兜底解析（如 "10派1.511元(含税)"）
                if dps_per10 is None:
                    import re
                    m = re.search(r'10派([0-9.]+)元', str(row.get('实施方案分红说明', '') or ''))
                    dps_per10 = _num(m.group(1)) if m else None
                dps = (dps_per10 / 10.0) if dps_per10 is not None else None
                if dps is None:
                    continue  # 纯送转/未实施方案不产出派息记录
                result.append(DividendData(
                    symbol=symbol,
                    dividend_per_share=round(dps, 4),
                    dividend_yield=None,  # 股息率需现价，由东财源或工具层补
                    ex_dividend_date=_date(row.get('除权日')),
                    record_date=_date(row.get('股权登记日')),
                    pay_date=_date(row.get('派息日')),
                    source=self.name,
                    timestamp=datetime.now().isoformat()
                ))

            return result if result else None

        except Exception as e:
            logger.warning(f"{self.name} get_dividends failed: {e}")
            return None

    def get_dividend_calendar(self, start_date: str, end_date: str) -> Optional[List[DividendData]]:
        """Get dividend calendar within date range

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of DividendData or None if failed
        """
        # TODO: Extract logic from services/dividend_service.py when refactoring Phase 3
        logger.warning(f"{self.name} get_dividend_calendar not yet implemented")
        return None

    def screen_high_dividend(self, min_yield: float = 3.0, min_years: int = 5) -> Optional[List[DividendData]]:
        """Screen high dividend stocks

        Args:
            min_yield: Minimum dividend yield (%)
            min_years: Minimum consecutive dividend years

        Returns:
            List of DividendData or None if failed
        """
        # TODO: Extract logic from services/dividend_service.py when refactoring Phase 3
        logger.warning(f"{self.name} screen_high_dividend not yet implemented")
        return None
