"""
分红数据服务

提供分红数据查询、筛选、日历等功能。
"""
from typing import List, Dict, Optional
import pandas as pd
import structlog
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from domain.ports.datasource_ports import IDataProviderManager

from application.services.base_service import ServiceBase
from application.services.dividend_data_source import EastMoneyDividendSource, DividendDataSource

logger = structlog.get_logger(__name__)


class DividendService(ServiceBase):
    """分红数据服务"""

    def __init__(self, data_source: Optional[DividendDataSource] = None):
        """
        初始化分红服务

        Args:
            data_source: 数据源实现，默认使用 EastMoneyDividendSource
        """
        super().__init__()
        self.data_source = data_source or EastMoneyDividendSource()
        # TODO: Phase 3 future work - migrate methods to use provider_manager
        # 延迟导入避免顶层依赖
        from adapters.outbound.datasources.manager import get_data_provider_manager
        self.provider_manager = get_data_provider_manager()

    def get_stock_dividends(self, symbol: str, years: int = 10) -> Dict:
        """
        获取单股历史分红

        Args:
            symbol: 股票代码（如 600000.SH）
            years: 查询最近N年

        Returns:
            {
                "success": bool,
                "symbol": str,
                "name": str,
                "total_records": int,
                "dividends": List[Dict],
                "summary": Dict
            }
        """
        try:
            logger.info(f"Fetching dividends for {symbol}, years={years}")

            # 1. 调用数据源
            df = self.data_source.fetch_dividends(symbol)

            if df.empty:
                return {
                    "success": False,
                    "error": "该股票暂无分红记录"
                }

            # 2. 数据清洗和转换
            records = self._transform_records(df, years)

            if not records:
                return {
                    "success": False,
                    "error": f"最近{years}年无分红记录"
                }

            # 3. 计算摘要指标
            summary = self._calculate_summary(records)

            return {
                "success": True,
                "symbol": symbol,
                "name": records[0].get("name", ""),
                "total_records": len(records),
                "dividends": records,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Failed to get dividends for {symbol}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _transform_records(self, df: pd.DataFrame, years: int) -> List[Dict]:
        """
        转换 akshare 数据为标准格式

        Args:
            df: akshare 返回的 DataFrame
            years: 查询最近N年

        Returns:
            List[Dict]: 标准化的分红记录列表
        """
        records = []
        current_year = datetime.now().year
        cutoff_year = current_year - years

        for _, row in df.iterrows():
            try:
                # 解析年度
                fiscal_year = str(row.get("分红年度", ""))
                if not fiscal_year or not fiscal_year.isdigit():
                    continue

                year = int(fiscal_year)
                if year < cutoff_year:
                    continue

                # 解析派息金额
                cash_dividend = float(row.get("每股派息", 0) or 0)
                cash_per_share = cash_dividend / 10.0  # 每10股派息 -> 每股派息

                # 解析股息率
                dividend_yield_str = str(row.get("股息率", "0"))
                dividend_yield = float(dividend_yield_str.replace("%", "") or 0)

                # 解析日期
                ex_dividend_date = str(row.get("除权除息日", ""))
                record_date = str(row.get("股权登记日", ""))
                pay_date = str(row.get("派息日", ""))

                record = {
                    "symbol": row.get("股票代码", ""),
                    "name": row.get("股票简称", ""),
                    "fiscal_year": fiscal_year,
                    "dividend_type": "年度分红",
                    "cash_dividend": cash_dividend,
                    "cash_per_share": cash_per_share,
                    "stock_dividend": float(row.get("送股比例", 0) or 0),
                    "bonus_shares": float(row.get("转增比例", 0) or 0),
                    "dividend_yield": dividend_yield,
                    "payout_ratio": 0.0,  # akshare 不提供此字段
                    "announce_date": str(row.get("公告日期", "")),
                    "shareholder_meeting_date": "",
                    "ex_dividend_date": ex_dividend_date,
                    "record_date": record_date,
                    "pay_date": pay_date,
                    "status": "已实施" if ex_dividend_date else "预案",
                    "total_dividend": 0.0,
                    "is_implemented": bool(ex_dividend_date)
                }

                records.append(record)

            except Exception as e:
                logger.warning(f"Failed to parse dividend record: {e}")
                continue

        # 按年度倒序排列
        records.sort(key=lambda x: x["fiscal_year"], reverse=True)

        return records

    def _calculate_summary(self, records: List[Dict]) -> Dict:
        """
        计算分红摘要指标

        Args:
            records: 分红记录列表

        Returns:
            Dict: 摘要指标
        """
        if not records:
            return {
                "consecutive_years": 0,
                "avg_yield": 0.0,
                "total_cash_dividend": 0.0
            }

        # 连续分红年数：按"分红年度"去重后，从最新年度向前连续计数（一年内多次分红只算一年）。
        # 注意不能用 len(records)，否则同一年的中报+年报会被重复计数。
        years = sorted(
            {int(r["fiscal_year"]) for r in records if str(r["fiscal_year"]).isdigit()},
            reverse=True,
        )
        consecutive_years = 0
        prev_year = None
        for year in years:
            if prev_year is None or prev_year - year == 1:
                consecutive_years += 1
                prev_year = year
            else:
                break

        # 平均股息率
        yields = [r["dividend_yield"] for r in records if r["dividend_yield"] > 0]
        avg_yield = sum(yields) / len(yields) if yields else 0.0

        # 累计每股派息
        total_cash_dividend = sum(r["cash_per_share"] for r in records)

        return {
            "consecutive_years": consecutive_years,
            "avg_yield": round(avg_yield, 2),
            "total_cash_dividend": round(total_cash_dividend, 2)
        }

    def screen_dividend_stocks(self, params: Dict) -> Dict:
        """
        筛选高股息股票

        Args:
            params: {
                "min_yield": float,  # 最低股息率（%）
                "min_years": int,    # 最少连续分红年数
                "min_payout_ratio": float,  # 最低分红率（%）
                "max_payout_ratio": float,  # 最高分红率（%）
                "limit": int         # 返回数量限制
            }

        Returns:
            {
                "success": bool,
                "total": int,
                "stocks": List[Dict]
            }
        """
        try:
            logger.info(f"Screening dividend stocks with params: {params}")

            # 1. 获取股票池
            stock_pool = self._get_stock_pool()
            logger.info(f"Stock pool size: {len(stock_pool)}")

            # 2. 并发查询分红数据
            results = self._batch_query_dividends(stock_pool)
            logger.info(f"Successfully queried {len(results)} stocks")

            # 3. 应用筛选条件
            filtered = self._apply_filters(results, params)
            logger.info(f"Filtered to {len(filtered)} stocks")

            # 4. 排序并限制数量
            sorted_stocks = sorted(
                filtered,
                key=lambda x: x["latest_yield"],
                reverse=True
            )[:params.get("limit", 50)]

            return {
                "success": True,
                "total": len(sorted_stocks),
                "stocks": sorted_stocks
            }

        except Exception as e:
            logger.error(f"Failed to screen dividend stocks: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_stock_pool(self) -> List[str]:
        """
        获取股票池（沪深300 + 创业板50 + 科创50）

        Returns:
            List[str]: 股票代码列表
        """
        try:
            pool = []

            def _fetch_index(index_code: str) -> list:
                # 2026-09-05 修复：call_akshare 方法不存在，改走
                # DataProviderManager.get_index_constituents()（provider 内已含
                # csindex 优先 + sina 兜底；StockData.data=[{'symbol': '600519'}, ...]）。
                resp = self.provider_manager.get_index_constituents(index_code)
                if not resp.get('success') or resp.get('data') is None:
                    return []
                records = resp['data'].data or []
                return [str(r.get('symbol', '')).zfill(6) for r in records if r.get('symbol')]

            # 沪深300
            try:
                pool.extend(_fetch_index("000300"))
            except Exception as e:
                logger.warning(f"Failed to fetch HS300: {e}")

            # 创业板50
            try:
                pool.extend(_fetch_index("399673"))
            except Exception as e:
                logger.warning(f"Failed to fetch CYB50: {e}")

            # 科创50
            try:
                pool.extend(_fetch_index("000688"))
            except Exception as e:
                logger.warning(f"Failed to fetch KC50: {e}")

            # 去重
            pool = list(set(pool))

            # 添加市场后缀
            pool_with_suffix = []
            for code in pool:
                if code.startswith("6"):
                    pool_with_suffix.append(f"{code}.SH")
                else:
                    pool_with_suffix.append(f"{code}.SZ")

            return pool_with_suffix

        except Exception as e:
            logger.error(f"Failed to get stock pool: {e}")
            return []

    def _batch_query_dividends(self, symbols: List[str]) -> List[Dict]:
        """
        并发批量查询分红数据

        Args:
            symbols: 股票代码列表

        Returns:
            List[Dict]: 查询成功的股票分红数据
        """
        results = []

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_symbol = {
                executor.submit(self._query_single_stock, symbol): symbol
                for symbol in symbols
            }

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    data = future.result(timeout=5)
                    if data:
                        results.append(data)
                except Exception as e:
                    logger.warning(f"Failed to query {symbol}: {e}")
                    continue

        return results

    def _query_single_stock(self, symbol: str) -> Optional[Dict]:
        """
        查询单只股票的分红数据

        Args:
            symbol: 股票代码

        Returns:
            Dict or None: 股票分红摘要数据（包含完整分红记录）
        """
        try:
            result = self.get_stock_dividends(symbol, years=10)

            if not result["success"] or not result["dividends"]:
                return None

            dividends = result["dividends"]
            summary = result["summary"]

            # 最新股息率：取最近一个"分红年度"的全部分红合计（中报+年报），
            # 而不是仅取最近一次派息，否则会低估高股息股票（如工行中报 only ~2%，全年 ~5%）。
            latest_year = dividends[0]["fiscal_year"] if dividends else None
            latest_yield = sum(
                d["dividend_yield"] for d in dividends if d["fiscal_year"] == latest_year
            ) if latest_year is not None else 0.0

            return {
                "symbol": symbol,
                "name": result["name"],
                "latest_yield": latest_yield,
                "consecutive_years": summary["consecutive_years"],
                "avg_payout_ratio": 0.0,  # akshare 不提供此字段
                "dividends": dividends  # 包含完整分红记录，避免 N+1 查询
            }

        except Exception as e:
            logger.warning(f"Failed to query single stock {symbol}: {e}")
            return None

    def _apply_filters(self, results: List[Dict], params: Dict) -> List[Dict]:
        """
        应用筛选条件

        Args:
            results: 查询结果列表
            params: 筛选参数

        Returns:
            List[Dict]: 筛选后的结果
        """
        filtered = results

        # 最低股息率
        if "min_yield" in params:
            min_yield = params["min_yield"]
            filtered = [r for r in filtered if r["latest_yield"] >= min_yield]

        # 最少连续分红年数
        if "min_years" in params:
            min_years = params["min_years"]
            filtered = [r for r in filtered if r["consecutive_years"] >= min_years]

        # 分红率范围（当前数据源不提供 payout_ratio，avg_payout_ratio 恒为 0.0）。
        # 数据不可用时若强行按 min/max 过滤，会把所有结果错误地筛成 0，因此忽略并告警。
        wants_payout_filter = "min_payout_ratio" in params or "max_payout_ratio" in params
        payout_available = any(r.get("avg_payout_ratio", 0) > 0 for r in filtered)

        if wants_payout_filter and not payout_available:
            logger.warning(
                "payout_ratio 数据不可用，忽略 min_payout_ratio/max_payout_ratio 筛选条件"
            )
        elif wants_payout_filter:
            if "min_payout_ratio" in params:
                min_ratio = params["min_payout_ratio"]
                filtered = [r for r in filtered if r["avg_payout_ratio"] >= min_ratio]

            if "max_payout_ratio" in params:
                max_ratio = params["max_payout_ratio"]
                filtered = [r for r in filtered if r["avg_payout_ratio"] <= max_ratio]

        return filtered

    def get_dividend_calendar(
        self,
        start_date: str,
        end_date: str,
        event: str = "ex_dividend"
    ) -> Dict:
        """
        分红日历

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            event: 事件类型 (ex_dividend/record_date/pay_date)

        Returns:
            {
                "success": bool,
                "period": str,
                "event_type": str,
                "total": int,
                "events": List[Dict]
            }
        """
        try:
            logger.info(f"Fetching dividend calendar: {start_date} to {end_date}, event={event}")

            # 1. 获取股票池
            stock_pool = self._get_stock_pool()

            # 2. 批量查询分红数据
            results = self._batch_query_dividends(stock_pool)

            # 3. 筛选日期范围内的事件
            events = self._filter_by_date_range(results, start_date, end_date, event)

            # 4. 按日期排序
            sorted_events = sorted(events, key=lambda x: x["date"])

            event_type_map = {
                "ex_dividend": "除权除息日",
                "record_date": "股权登记日",
                "pay_date": "派息日"
            }

            return {
                "success": True,
                "period": f"{start_date} 至 {end_date}",
                "event_type": event_type_map.get(event, "未知事件"),
                "total": len(sorted_events),
                "events": sorted_events
            }

        except Exception as e:
            logger.error(f"Failed to get dividend calendar: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _filter_by_date_range(
        self,
        results: List[Dict],
        start: str,
        end: str,
        event: str
    ) -> List[Dict]:
        """
        筛选日期范围内的事件

        Args:
            results: 股票分红数据列表（包含完整分红记录）
            start: 开始日期 (YYYY-MM-DD)
            end: 结束日期 (YYYY-MM-DD)
            event: 事件类型

        Returns:
            List[Dict]: 符合条件的事件列表
        """
        events = []

        # 事件字段映射
        event_field_map = {
            "ex_dividend": "ex_dividend_date",
            "record_date": "record_date",
            "pay_date": "pay_date"
        }

        date_field = event_field_map.get(event, "ex_dividend_date")

        for stock_data in results:
            symbol = stock_data["symbol"]
            name = stock_data["name"]
            dividends = stock_data.get("dividends", [])  # 使用缓存的分红记录，避免 N+1 查询

            for dividend in dividends:
                event_date = dividend.get(date_field, "")

                if not event_date:
                    continue

                # 检查日期是否在范围内
                if start <= event_date <= end:
                    events.append({
                        "date": event_date,
                        "symbol": symbol,
                        "name": name,
                        "cash_per_share": dividend["cash_per_share"],
                        "dividend_yield": dividend["dividend_yield"]
                    })

        return events
