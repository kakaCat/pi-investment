"""
分红数据源抽象层

提供统一的数据源接口，支持未来扩展到 tushare 或其他数据源。
"""
from abc import ABC, abstractmethod
import pandas as pd
import structlog
import requests
from typing import Optional

logger = structlog.get_logger(__name__)


class DividendDataSource(ABC):
    """分红数据源抽象基类"""

    @abstractmethod
    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        获取股票分红数据

        Args:
            symbol: 股票代码（如 600000.SH 或 600000）

        Returns:
            pd.DataFrame: 分红数据

        Raises:
            Exception: 数据获取失败
        """
        pass


class AkshareDividendSource(DividendDataSource):
    """akshare 数据源实现（已弃用，存在 py_mini_racer 兼容性问题）"""

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        从 akshare 获取分红数据

        Args:
            symbol: 股票代码（如 600000.SH 或 600000）

        Returns:
            pd.DataFrame: 分红数据

        Raises:
            Exception: akshare API 调用失败（py_mini_racer 问题）
        """
        import akshare as ak

        # 移除后缀（akshare 只需要6位代码）
        code = symbol.split('.')[0]

        logger.info(f"Fetching dividends from akshare for {code}")
        df = ak.stock_dividend_cninfo(symbol=code)

        logger.info(f"Fetched {len(df)} dividend records for {code}")
        return df


class EastMoneyDividendSource(DividendDataSource):
    """东方财富 HTTP 数据源实现（推荐，无 py_mini_racer 依赖）"""

    def __init__(self, timeout: int = 10):
        """
        初始化东方财富数据源

        Args:
            timeout: HTTP 请求超时时间（秒）
        """
        self.timeout = timeout
        self.base_url = "https://datacenter-web.eastmoney.com/api/data/v1/get"

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        从东方财富获取分红数据

        Args:
            symbol: 股票代码（如 600000.SH 或 600000）

        Returns:
            pd.DataFrame: 分红数据，包含列：
                - 分红年度
                - 送转总比例
                - 每股派息
                - 股息率
                - 除权除息日
                - 等

        Raises:
            Exception: HTTP 请求失败
        """
        # 移除后缀
        code = symbol.split('.')[0]

        # 判断市场
        if code.startswith('6'):
            market_code = f"{code}.SH"
        elif code.startswith(('0', '3')):
            market_code = f"{code}.SZ"
        else:
            market_code = f"{code}.BJ"

        logger.info(f"Fetching dividends from EastMoney for {market_code}")

        try:
            # 东方财富分红送配接口
            params = {
                "reportName": "RPT_SHAREBONUS_DET",
                "columns": "ALL",
                "filter": f"(SECURITY_CODE=\"{code}\")",
                "pageNumber": "1",
                "pageSize": "500",
                "sortTypes": "-1",
                "sortColumns": "REPORT_DATE",
                "source": "WEB",
                "client": "WEB"
            }

            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
            )
            response.raise_for_status()

            data = response.json()

            if data.get("code") != 0:
                raise Exception(f"API returned error code: {data.get('code')}")

            result = data.get("result", {})
            records = result.get("data", [])

            if not records:
                logger.warning(f"No dividend records found for {code}")
                return pd.DataFrame()

            # 转换为 DataFrame
            df = pd.DataFrame(records)

            # 字段映射（东方财富 → akshare 格式）
            column_mapping = {
                "SECURITY_CODE": "股票代码",
                "SECURITY_NAME_ABBR": "股票简称",
                "REPORT_DATE": "分红年度",
                "IMPL_PLAN_PROFILE": "分红方案",
                "BONUS_RATIO": "送股比例",
                "IT_RATIO": "转增比例",
                "PRETAX_BONUS_RMB": "每股派息",
                "DIVIDENT_RATIO": "股息率",
                "EX_DIVIDEND_DATE": "除权除息日",
                "EQUITY_RECORD_DATE": "股权登记日",
                "PUBLISH_DATE": "派息日",
                "NOTICE_DATE": "公告日期",
                "PLAN_NOTICE_DATE": "预案公告日"
            }

            # 重命名列
            df = df.rename(columns=column_mapping)

            # 数据清洗
            if "分红年度" in df.columns:
                df["分红年度"] = pd.to_datetime(df["分红年度"], errors='coerce').dt.year.astype(str)

            # 处理每股派息（东方财富单位是"元"，直接使用）
            if "每股派息" in df.columns:
                df["每股派息"] = pd.to_numeric(df["每股派息"], errors='coerce').fillna(0)
            else:
                df["每股派息"] = 0

            # 处理股息率（东方财富 DIVIDENT_RATIO 返回小数形式，如 0.0494 表示 4.94%）。
            # 下游（筛选/格式化/摘要）均按百分比数值处理，故在数据源层统一转换为百分比，
            # 保持与 akshare 一致的契约（3.5 表示 3.5%）。
            if "股息率" in df.columns:
                df["股息率"] = pd.to_numeric(df["股息率"], errors='coerce').fillna(0) * 100
            else:
                df["股息率"] = 0

            # 处理送转比例
            if "送股比例" in df.columns:
                df["送股比例"] = pd.to_numeric(df["送股比例"], errors='coerce').fillna(0)
            else:
                df["送股比例"] = 0

            if "转增比例" in df.columns:
                df["转增比例"] = pd.to_numeric(df["转增比例"], errors='coerce').fillna(0)
            else:
                df["转增比例"] = 0

            # 计算送转总比例
            df["送转总比例"] = df["送股比例"] + df["转增比例"]

            # 确保必需字段存在
            required_fields = ["股票代码", "股票简称", "分红年度", "每股派息", "股息率",
                             "送股比例", "转增比例", "送转总比例", "除权除息日",
                             "股权登记日", "公告日期"]

            for field in required_fields:
                if field not in df.columns:
                    df[field] = "" if field in ["除权除息日", "股权登记日", "公告日期"] else 0

            # 归一化日期为 YYYY-MM-DD（EastMoney 返回 "YYYY-MM-DD 00:00:00"）。
            # 否则下游按字符串做日期范围比较时，会把恰好落在区间末日当天的事件错误排除。
            for date_col in ["除权除息日", "股权登记日", "派息日", "公告日期"]:
                if date_col in df.columns:
                    df[date_col] = (
                        df[date_col]
                        .astype(str)
                        .str.slice(0, 10)
                        .replace({"None": "", "nan": "", "NaT": ""})
                    )

            logger.info(f"Fetched {len(df)} dividend records for {code} from EastMoney")
            return df

        except requests.RequestException as e:
            logger.error(f"HTTP request failed for {code}: {e}")
            raise Exception(f"Failed to fetch dividends from EastMoney: {e}")
        except Exception as e:
            logger.error(f"Failed to parse dividend data for {code}: {e}")
            raise


class TushareDividendSource(DividendDataSource):
    """tushare 数据源实现（预留）"""

    def __init__(self, token: str):
        """
        初始化 tushare 数据源

        Args:
            token: tushare API token
        """
        self.token = token

    def fetch_dividends(self, symbol: str) -> pd.DataFrame:
        """
        从 tushare 获取分红数据（预留实现）

        Args:
            symbol: 股票代码

        Returns:
            pd.DataFrame: 分红数据

        Raises:
            NotImplementedError: 功能未实现
        """
        raise NotImplementedError("Tushare source not implemented yet")
