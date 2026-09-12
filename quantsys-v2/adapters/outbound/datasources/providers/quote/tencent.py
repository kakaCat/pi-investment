"""
TencentQuoteProvider - 腾讯财经实时行情数据源
"""
import re
import requests
from datetime import datetime
from typing import Optional
from adapters.outbound.datasources.base import QuoteProvider
from adapters.outbound.datasources.models import QuoteData


class TencentQuoteProvider(QuoteProvider):
    """腾讯财经行情数据提供者

    数据源：腾讯财经 qt.gtimg.cn
    优点：免费，响应快
    """

    @property
    def name(self) -> str:
        return "tencent"

    def get_quote(self, symbol: str) -> Optional[QuoteData]:
        """
        获取实时行情数据

        Args:
            symbol: 股票代码 (e.g., "600519.SH", "000001.SZ")

        Returns:
            QuoteData if successful, None if empty response

        Raises:
            Exception: 网络错误或解析失败
        """
        self.last_error = None
        try:
            # Convert symbol to Tencent format
            tencent_code = self._convert_to_tencent_code(symbol)

            # Call Tencent API
            url = f"http://qt.gtimg.cn/q={tencent_code}"
            response = requests.get(
                url,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.encoding = 'gbk'

            # Check for empty response
            if not response.text or '""' in response.text:
                self.last_error = f"腾讯无 {tencent_code} 数据（代码不存在或该市场不支持）"
                return None

            quote = self._parse_quote(symbol, response.text)
            if quote is None:
                self.last_error = f"腾讯返回数据无法解析或代码无匹配 ({tencent_code})"
            return quote

        except Exception as e:
            raise Exception(f"腾讯财经查询失败: {e}") from e

    def get_quotes(self, symbols):
        """批量行情：**一次 HTTP 请求**取回多只（2026-09-13，w-adb088f2）

        腾讯接口本身支持 `q=sz300677,sh600887,...` 一次多只，响应是按标的逐行的
        `v_CODE="..."`。原实现逐只 get_quote，N 只 = N 次新建连接；在本机 IPv6 兜底
        场景下每只要多付约 8s（实测 2 只 = 16.4s，超出工具 10s 超时）。

        解析复用单只路径（把每个 `v_CODE="..."` 段切出来交回 _parse_quote），
        保证字段口径只有一份，避免批量/单只两条解析逻辑漂移。

        Returns:
            {symbol: QuoteData}（只含成功且 price>0 的标的；整批失败时抛异常交给降级链）
        """
        self.last_error = None
        out = {}
        symbols = list(symbols or [])
        if not symbols:
            return out

        codes = [self._convert_to_tencent_code(s) for s in symbols]
        code_to_symbol = dict(zip(codes, symbols))
        url = f"http://qt.gtimg.cn/q={','.join(codes)}"

        try:
            response = requests.get(
                url,
                timeout=self.timeout,
                proxies={'http': None, 'https': None}
            )
            response.encoding = 'gbk'
            text = response.text or ''
        except Exception as e:
            raise Exception(f"腾讯财经批量查询失败: {e}") from e

        for segment in re.split(r'[;\n]', text):
            if '="' not in segment:
                continue
            raw_code = segment.split('=', 1)[0].strip()
            code = raw_code[2:] if raw_code.startswith('v_') else raw_code
            symbol = code_to_symbol.get(code)
            if symbol is None:
                continue
            try:
                quote = self._parse_quote(symbol, segment)
            except Exception:
                # 单只解析失败不影响整批（该只算缺口，交给降级链补齐）
                continue
            if quote is not None:
                out[symbol] = quote

        if not out:
            self.last_error = f"腾讯批量无 {len(codes)} 只数据（代码不存在或该市场不支持）"
        return out

    def _convert_to_tencent_code(self, symbol: str) -> str:
        """
        Convert standard symbol to Tencent code format

        Args:
            symbol: Standard symbol (e.g., "600519.SH", "000001.SZ")

        Returns:
            Tencent code (e.g., "sh600519", "sz000001")
        """
        if symbol.endswith('.SH'):
            code = symbol.split('.')[0]
            return f"sh{code}"
        elif symbol.endswith('.SZ'):
            code = symbol.split('.')[0]
            return f"sz{code}"
        else:
            # Auto-detect by code prefix
            code = symbol.split('.')[0] if '.' in symbol else symbol
            if code.startswith('6'):
                return f"sh{code}"
            else:
                return f"sz{code}"

    def _parse_quote(self, symbol: str, raw: str) -> Optional[QuoteData]:
        """
        Parse Tencent API response

        Response format:
        v_sh600519="1~贵州茅台~600519~1295.00~1.03~0.08~52477~26205~26272~1294.50~50~1295.00~100~..."

        Field positions (updated 2026-06-22):
        [1] = 股票名称 (name)
        [2] = 股票代码 (code)
        [3] = 当前价格 (price)
        [4] = 昨收 (prev_close)
        [5] = 今开 (open)
        [6] = 成交量手 (volume_lots)
        [7] = 外盘手 (outer_volume_lots，**不是成交额**)
        [37] = 成交额万元 (amount_10k)
        [31] = 涨跌额 (change)
        [32] = 涨跌幅% (change_pct)
        [33] = 最高 (high)
        [34] = 最低 (low)

        Args:
            symbol: Standard symbol
            raw: Raw response text

        Returns:
            QuoteData object or None
        """
        try:
            # Extract data between quotes
            parts = raw.split('"')
            if len(parts) < 2:
                return None

            fields = parts[1].split('~')
            if len(fields) < 10:
                return None

            # Extract and convert fields
            name = fields[1]
            price = float(fields[3])
            if price <= 0:
                return None

            change = float(fields[31]) if len(fields) > 31 and fields[31] else 0.0
            change_pct = float(fields[32]) if len(fields) > 32 and fields[32] else 0.0
            volume = int(fields[6]) * 100  # Convert lots to shares
            # [7] 是外盘手数，成交额在 [37]（2026-09-10 修正：原按 [7] 取值导致 amount 系统性偏大）
            amount = float(fields[37]) * 10000 if len(fields) > 37 and fields[37] else 0.0
            open_price = float(fields[5]) if len(fields) > 5 and fields[5] else 0.0

            # prev_close, high, low (correct positions)
            prev_close = float(fields[4]) if len(fields) > 4 and fields[4] else price - change
            high = float(fields[33]) if len(fields) > 33 and fields[33] else price
            low = float(fields[34]) if len(fields) > 34 and fields[34] else price

            return QuoteData(
                symbol=symbol,
                name=name,
                price=price,
                open=open_price,
                high=high,
                low=low,
                prev_close=prev_close,
                volume=volume,
                amount=amount,
                change=change,
                change_pct=change_pct,
                timestamp=datetime.now().isoformat(),
                source=self.name
            )

        except (IndexError, ValueError, TypeError) as e:
            raise Exception(f"腾讯财经行情解析失败: {e}") from e
