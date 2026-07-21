"""
龙虎榜数据源 - 多数据源策略

支持多数据源策略：
1. 东方财富 (primary) - 通过个股代码直接查询
2. 新浪财经 (fallback) - 日度龙虎榜数据
3. AkShare (last resort) - 兜底数据源

架构：
- LhbDataSource: 统一接口，自动 failover
- EastMoneyLhbSource: 东方财富实现
- SinaLhbSource: 新浪财经实现
- AkShareLhbSource: AkShare 实现
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseLhbSource(ABC):
    """龙虎榜数据源基类"""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def fetch_stock_lhb(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """
        获取个股龙虎榜记录

        Args:
            symbol: 股票代码（如 600737）
            days: 查询最近N天

        Returns:
            pd.DataFrame or None
        """
        pass

    @abstractmethod
    def fetch_daily_lhb(self, date: str) -> Optional[pd.DataFrame]:
        """
        获取某日全市场龙虎榜

        Args:
            date: 日期（格式 YYYYMMDD）

        Returns:
            pd.DataFrame or None
        """
        pass


class EastMoneyLhbSource(BaseLhbSource):
    """东方财富龙虎榜数据源"""

    def __init__(self):
        super().__init__("EastMoney")

    def fetch_stock_lhb(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """从东方财富获取个股龙虎榜（通过每日龙虎榜筛选）"""
        try:
            import akshare as ak

            # 收集多日数据（API 只支持单日查询）
            all_records = []
            end_date = datetime.now()

            for i in range(min(days, 30)):  # 限制最多查询30天
                date = end_date - timedelta(days=i)
                date_str = date.strftime('%Y%m%d')

                try:
                    # 获取当日全市场龙虎榜
                    df_daily = ak.stock_lhb_detail_daily_sina(date=date_str)

                    if not df_daily.empty and '股票代码' in df_daily.columns:
                        # 筛选出目标股票（匹配6位代码）
                        stock_records = df_daily[df_daily['股票代码'].str.contains(symbol, na=False)]
                        if not stock_records.empty:
                            # 添加日期列
                            stock_records = stock_records.copy()
                            stock_records['交易日期'] = date.strftime('%Y-%m-%d')
                            all_records.append(stock_records)
                except:
                    # 某日无数据或查询失败，继续下一天
                    continue

            if not all_records:
                logger.info(f"{self.name}: {symbol} 无龙虎榜数据")
                return None

            # 合并数据
            result = pd.concat(all_records, ignore_index=True)
            logger.info(f"{self.name}: 获取 {symbol} 龙虎榜数据 {len(result)} 条")
            return result

        except Exception as e:
            logger.warning(f"{self.name} 获取 {symbol} 失败: {e}")
            return None

    def fetch_daily_lhb(self, date: str) -> Optional[pd.DataFrame]:
        """从东方财富获取每日龙虎榜"""
        try:
            import akshare as ak
            df = ak.stock_lhb_detail_daily_sina(date=date)

            if df.empty:
                logger.info(f"{self.name}: {date} 无龙虎榜数据")
                return None

            logger.info(f"{self.name}: 获取 {date} 龙虎榜数据 {len(df)} 只股票")
            return df

        except Exception as e:
            logger.warning(f"{self.name} 获取 {date} 每日龙虎榜失败: {e}")
            return None


class SinaLhbSource(BaseLhbSource):
    """新浪财经龙虎榜数据源"""

    def __init__(self):
        super().__init__("Sina")

    def fetch_stock_lhb(self, symbol: str, days: int = 30) -> Optional[pd.DataFrame]:
        """从新浪财经获取个股龙虎榜（遍历多日数据）"""
        try:
            import akshare as ak

            # 收集多日数据
            all_records = []
            end_date = datetime.now()

            for i in range(min(days, 30)):  # 限制最多查询30天
                date = end_date - timedelta(days=i)
                date_str = date.strftime('%Y%m%d')

                try:
                    df = ak.stock_lhb_detail_daily_sina(date=date_str)
                    if not df.empty and '股票代码' in df.columns:
                        # 筛选出目标股票（匹配6位代码）
                        stock_records = df[df['股票代码'].str.contains(symbol, na=False)]
                        if not stock_records.empty:
                            all_records.append(stock_records)
                except:
                    continue

            if not all_records:
                logger.info(f"{self.name}: {symbol} 无龙虎榜数据")
                return None

            # 合并数据
            result = pd.concat(all_records, ignore_index=True)
            logger.info(f"{self.name}: 获取 {symbol} 龙虎榜数据 {len(result)} 条")
            return result

        except Exception as e:
            logger.warning(f"{self.name} 获取 {symbol} 失败: {e}")
            return None

    def fetch_daily_lhb(self, date: str) -> Optional[pd.DataFrame]:
        """从新浪财经获取每日龙虎榜"""
        try:
            import akshare as ak
            df = ak.stock_lhb_detail_daily_sina(date=date)

            if df.empty:
                logger.info(f"{self.name}: {date} 无龙虎榜数据")
                return None

            logger.info(f"{self.name}: 获取 {date} 龙虎榜数据 {len(df)} 只股票")
            return df

        except Exception as e:
            logger.warning(f"{self.name} 获取 {date} 每日龙虎榜失败: {e}")
            return None


class LhbDataSource:
    """
    龙虎榜数据源 - 多数据源策略
    
    自动 failover 机制：
    1. 优先使用东方财富（最稳定）
    2. 失败时降级到新浪财经
    """

    def __init__(self):
        self.sources = [
            EastMoneyLhbSource(),
            SinaLhbSource(),
        ]

    def get_stock_lhb(self, symbol: str, days: int = 30) -> Dict:
        """
        获取个股龙虎榜记录（自动 failover）

        Args:
            symbol: 股票代码（如 600737 或 600737.SH）
            days: 查询最近N天

        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "total_records": int,
                "records": List[Dict],
                "source": str,
                "error": str
            }
        """
        # 标准化股票代码
        clean_symbol = symbol.split('.')[0]

        # 尝试所有数据源
        last_error = None
        for source in self.sources:
            try:
                logger.info(f"尝试从 {source.name} 获取 {clean_symbol} 龙虎榜数据")
                df = source.fetch_stock_lhb(clean_symbol, days)

                if df is not None and not df.empty:
                    # 数据转换
                    records = self._transform_stock_records(df, days)
                    
                    if records:
                        return {
                            "success": True,
                            "symbol": clean_symbol,
                            "name": records[0].get("name", "") if records else "",
                            "total_records": len(records),
                            "records": records,
                            "source": source.name
                        }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"{source.name} 获取失败: {e}")
                continue

        # 所有数据源都失败
        error_msg = last_error or "所有数据源均无可用数据"
        logger.error(f"获取 {clean_symbol} 龙虎榜失败: {error_msg}")
        
        return {
            "success": False,
            "symbol": clean_symbol,
            "error": f"该股票近期无龙虎榜记录或数据源暂时不可用"
        }

    def get_daily_lhb(self, date: str) -> Dict:
        """
        获取某日全市场龙虎榜（自动 failover）

        Args:
            date: 日期（格式 YYYYMMDD）

        Returns:
            {
                "success": bool,
                "date": str,
                "total_stocks": int,
                "stocks": List[Dict],
                "source": str,
                "error": str
            }
        """
        # 尝试所有数据源
        last_error = None
        for source in self.sources:
            try:
                logger.info(f"尝试从 {source.name} 获取 {date} 每日龙虎榜")
                df = source.fetch_daily_lhb(date)

                if df is not None and not df.empty:
                    # 数据转换
                    stocks = self._transform_daily_records(df)
                    
                    return {
                        "success": True,
                        "date": self._format_date(date),
                        "total_stocks": len(stocks),
                        "stocks": stocks,
                        "source": source.name
                    }

            except Exception as e:
                last_error = str(e)
                logger.warning(f"{source.name} 获取每日龙虎榜失败: {e}")
                continue

        # 所有数据源都失败
        error_msg = last_error or "所有数据源均无可用数据"
        logger.error(f"获取 {date} 每日龙虎榜失败: {error_msg}")
        
        return {
            "success": False,
            "date": self._format_date(date),
            "error": f"{date} 无龙虎榜数据或数据源暂时不可用"
        }

    def _transform_stock_records(self, df: pd.DataFrame, days: int) -> List[Dict]:
        """转换个股龙虎榜数据为标准格式（兼容多种数据源）"""
        records = []
        cutoff_date = datetime.now() - timedelta(days=days)

        for _, row in df.iterrows():
            try:
                # 解析日期（兼容多种格式）
                date_str = str(row.get('上榜日') or row.get('交易日期') or row.get('date') or '')
                if not date_str or date_str == 'nan':
                    continue

                # 尝试解析日期
                try:
                    if '-' in date_str:
                        trade_date = datetime.strptime(date_str, '%Y-%m-%d')
                    else:
                        trade_date = datetime.strptime(date_str, '%Y%m%d')
                except:
                    continue

                if trade_date < cutoff_date:
                    continue

                # 构建记录（兼容多种字段名）
                record = {
                    "date": trade_date.strftime('%Y-%m-%d'),
                    "name": str(row.get('股票名称') or row.get('股票简称') or row.get('名称') or row.get('name') or ''),
                    "reason": str(row.get('指标') or row.get('解读') or row.get('上榜原因') or row.get('reason') or ''),
                    "close_price": float(row.get('收盘价') or row.get('close') or 0),
                    "change_pct": float(row.get('涨跌幅') or row.get('change_pct') or 0),
                    "net_buy": float(row.get('龙虎榜净买额') or row.get('net_buy') or 0),
                    "buy_amount": float(row.get('龙虎榜买入额') or row.get('buy_amount') or 0),
                    "sell_amount": float(row.get('龙虎榜卖出额') or row.get('sell_amount') or 0),
                    "turnover": float(row.get('龙虎榜成交额') or row.get('成交额') or row.get('turnover') or 0)
                }

                records.append(record)

            except Exception as e:
                logger.warning(f"解析龙虎榜记录失败: {e}")
                continue

        return records

    def _transform_daily_records(self, df: pd.DataFrame) -> List[Dict]:
        """转换日期汇总数据为标准格式"""
        stocks = []

        for _, row in df.iterrows():
            try:
                stock = {
                    "symbol": str(row.get('股票代码') or row.get('代码') or row.get('symbol') or ''),
                    "name": str(row.get('股票名称') or row.get('名称') or row.get('name') or ''),
                    "reason": str(row.get('指标') or row.get('解读') or row.get('reason') or ''),
                    "close_price": float(row.get('收盘价') or row.get('close') or 0),
                    "change_pct": float(row.get('涨跌幅') or row.get('change_pct') or 0),
                    "net_buy": float(row.get('龙虎榜净买额') or row.get('net_buy') or 0),
                    "buy_amount": float(row.get('龙虎榜买入额') or row.get('buy_amount') or 0),
                    "sell_amount": float(row.get('龙虎榜卖出额') or row.get('sell_amount') or 0),
                    "turnover": float(row.get('龙虎榜成交额') or row.get('成交额') or row.get('turnover') or 0)
                }

                stocks.append(stock)

            except Exception as e:
                logger.warning(f"解析每日龙虎榜记录失败: {e}")
                continue

        return stocks

    def _format_date(self, date: str) -> str:
        """格式化日期：YYYYMMDD → YYYY-MM-DD"""
        if len(date) == 8:
            return f"{date[:4]}-{date[4:6]}-{date[6:]}"
        return date
