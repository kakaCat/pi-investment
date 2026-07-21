"""baostock 数据源
提供 A股数据的备用数据源，当 akshare 不可用时自动切换
"""

from typing import List, Dict, Any, Optional
import logging
from .base import MarketDataSource, DataSourceResponse

logger = logging.getLogger(__name__)

# 尝试导入 baostock
try:
    import baostock as bs
    BAOSTOCK_AVAILABLE = True
    logger.info("baostock is available")
except ImportError:
    BAOSTOCK_AVAILABLE = False
    logger.warning("baostock not available. Install with: pip install baostock")


class BaostockSource(MarketDataSource):
    """
    baostock 数据源

    特点:
    - 免费、无需注册
    - 支持 A股历史数据
    - 数据质量稳定
    - 适合作为 akshare 的备用源

    数据范围:
    - 股票基本信息
    - K线数据（日/周/月）
    - 复权数据

    限制:
    - 不支持实时行情（仅历史数据）
    - 查询速度较 akshare 慢
    """

    def __init__(self):
        super().__init__(name="baostock", requires_api_key=False)
        self._is_logged_in = False

        if not BAOSTOCK_AVAILABLE:
            logger.warning("baostock not available, source will not work")

    def validate_config(self) -> bool:
        """验证配置（baostock 无需配置）"""
        return BAOSTOCK_AVAILABLE

    def _login(self) -> bool:
        """登录 baostock"""
        if not BAOSTOCK_AVAILABLE:
            return False

        if self._is_logged_in:
            return True

        try:
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"baostock login failed: {lg.error_msg}")
                return False

            self._is_logged_in = True
            logger.debug("baostock login successful")
            return True
        except Exception as e:
            logger.error(f"baostock login exception: {e}")
            return False

    def _logout(self):
        """登出 baostock"""
        if BAOSTOCK_AVAILABLE and self._is_logged_in:
            try:
                bs.logout()
                self._is_logged_in = False
                logger.debug("baostock logout successful")
            except Exception as e:
                logger.warning(f"baostock logout exception: {e}")

    def _convert_symbol_to_bs(self, symbol: str) -> str:
        """
        转换符号格式为 baostock 格式

        600000.SH -> sh.600000
        000001.SZ -> sz.000001
        """
        try:
            code, exchange = symbol.split('.')
            return f"{exchange.lower()}.{code}"
        except:
            logger.warning(f"Invalid symbol format: {symbol}, returning as-is")
            return symbol

    def _convert_symbol_from_bs(self, bs_symbol: str) -> str:
        """
        转换符号格式从 baostock 格式

        sh.600000 -> 600000.SH
        sz.000001 -> 000001.SZ
        """
        try:
            exchange, code = bs_symbol.split('.')
            return f"{code}.{exchange.upper()}"
        except:
            logger.warning(f"Invalid baostock symbol format: {bs_symbol}, returning as-is")
            return bs_symbol

    def test_connection(self) -> DataSourceResponse:
        """测试连接"""
        try:
            if not self._login():
                return DataSourceResponse.error_response("baostock login failed")

            # 测试查询（查询沪深300成分股）
            rs = bs.query_hs300_stocks()
            if rs.error_code != '0':
                return DataSourceResponse.error_response(f"baostock query failed: {rs.error_msg}")

            self._logout()
            return DataSourceResponse.success_response(
                {"status": "connected"},
                metadata={"source": "baostock"}
            )
        except Exception as e:
            return self._handle_error("test_connection", e)

    def get_stock_info(self, symbol: str) -> DataSourceResponse:
        """
        获取股票基本信息

        Args:
            symbol: 股票代码（如 600000.SH）

        Returns:
            DataSourceResponse 包含股票信息
        """
        try:
            if not self._login():
                return DataSourceResponse.error_response("baostock login failed")

            bs_symbol = self._convert_symbol_to_bs(symbol)

            # 查询股票基本信息
            rs = bs.query_stock_basic(code=bs_symbol)

            if rs.error_code != '0':
                return DataSourceResponse.error_response(f"Query failed: {rs.error_msg}")

            # 获取数据
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())

            if not data_list:
                return DataSourceResponse.error_response(f"No data found for {symbol}")

            # 转换为统一格式
            row = data_list[0]
            stock_info = {
                'symbol': symbol,
                'code': row[0] if len(row) > 0 else '',
                'name': row[1] if len(row) > 1 else '',
                'industry': row[2] if len(row) > 2 else '',
                'ipo_date': row[3] if len(row) > 3 else '',
                'status': row[4] if len(row) > 4 else '',
            }

            return DataSourceResponse.success_response(
                stock_info,
                metadata={"source": "baostock"}
            )

        except Exception as e:
            return self._handle_error("get_stock_info", e)
        finally:
            self._logout()

    def get_klines(
        self,
        symbol: str,
        period: str = "daily",
        start_date: str = "20200101",
        end_date: str = "20260101",
        adjust_flag: str = "3"  # 1=后复权, 2=前复权, 3=不复权
    ) -> DataSourceResponse:
        """
        获取 K线数据

        Args:
            symbol: 股票代码（如 600000.SH）
            period: 周期（daily/weekly/monthly）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            adjust_flag: 复权类型（1=后复权, 2=前复权, 3=不复权）

        Returns:
            DataSourceResponse 包含K线数据列表
        """
        try:
            if not self._login():
                return DataSourceResponse.error_response("baostock login failed")

            bs_symbol = self._convert_symbol_to_bs(symbol)

            # 转换周期
            frequency_map = {
                'daily': 'd',
                'weekly': 'w',
                'monthly': 'm',
                '5min': '5',
                '15min': '15',
                '30min': '30',
                '60min': '60'
            }
            frequency = frequency_map.get(period, 'd')

            # 格式化日期（确保格式正确）
            start_date = start_date.replace('-', '').replace('/', '')
            end_date = end_date.replace('-', '').replace('/', '')

            # 验证日期格式（必须是8位数字）
            if len(start_date) != 8 or len(end_date) != 8:
                return DataSourceResponse.error_response(
                    f"Invalid date format. Expected YYYYMMDD, got: {start_date}, {end_date}"
                )

            # 查询K线数据
            rs = bs.query_history_k_data_plus(
                bs_symbol,
                "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjust_flag
            )

            # 检查返回值
            if rs is None:
                return DataSourceResponse.error_response("baostock query returned None (invalid parameters)")

            if rs.error_code != '0':
                return DataSourceResponse.error_response(f"Query failed: {rs.error_msg}")

            # 获取数据
            klines = []
            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()

                # 转换为统一格式
                kline = {
                    'symbol': symbol,
                    'trade_date': row[0],  # date
                    'open': float(row[2]) if row[2] else 0,
                    'high': float(row[3]) if row[3] else 0,
                    'low': float(row[4]) if row[4] else 0,
                    'close': float(row[5]) if row[5] else 0,
                    'pre_close': float(row[6]) if row[6] else 0,
                    'volume': int(float(row[7])) if row[7] else 0,
                    'amount': float(row[8]) if row[8] else 0,
                    'turnover': float(row[9]) if row[9] else 0,
                    'pct_change': float(row[10]) if row[10] else 0,
                }
                klines.append(kline)

            return DataSourceResponse.success_response(
                klines,
                metadata={
                    "source": "baostock",
                    "count": len(klines),
                    "period": period,
                    "adjust_flag": adjust_flag
                }
            )

        except Exception as e:
            return self._handle_error("get_klines", e)
        finally:
            self._logout()

    def get_realtime_quote(self, symbols: List[str]) -> DataSourceResponse:
        """
        获取实时行情（baostock 不支持实时数据）

        返回错误提示
        """
        return DataSourceResponse.error_response(
            "baostock does not support realtime quotes. Use akshare instead.",
            metadata={"source": "baostock", "feature": "not_supported"}
        )

    def search_stocks(self, keyword: str) -> DataSourceResponse:
        """
        搜索股票（简单实现：查询所有股票并过滤）

        Args:
            keyword: 搜索关键词（股票代码或名称）

        Returns:
            DataSourceResponse 包含匹配的股票列表
        """
        try:
            if not self._login():
                return DataSourceResponse.error_response("baostock login failed")

            # 查询所有A股股票
            rs = bs.query_stock_basic()

            if rs.error_code != '0':
                return DataSourceResponse.error_response(f"Query failed: {rs.error_msg}")

            # 获取数据并过滤
            matches = []
            keyword_lower = keyword.lower()

            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()
                code = row[0] if len(row) > 0 else ''
                name = row[1] if len(row) > 1 else ''

                # 简单匹配：代码或名称包含关键词
                if keyword_lower in code.lower() or keyword_lower in name.lower():
                    matches.append({
                        'symbol': self._convert_symbol_from_bs(code),
                        'code': code,
                        'name': name,
                        'industry': row[2] if len(row) > 2 else '',
                    })

                # 限制返回数量
                if len(matches) >= 50:
                    break

            return DataSourceResponse.success_response(
                matches,
                metadata={"source": "baostock", "keyword": keyword}
            )

        except Exception as e:
            return self._handle_error("search_stocks", e)
        finally:
            self._logout()

    def __del__(self):
        """析构时确保登出"""
        self._logout()
